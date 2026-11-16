---
name: team-build
description: Use when the owner has picked an idea from .agent-team/ideas.md (or wants to resume a feature) and it should go spec → plan → build → review → QA → PR → CI without further approvals.
metadata:
  kind: workflow
---

# team-build `<slug>`

Runs the hands-off middle: from the owner's pick (Gate 1) to a green PR for the owner to merge (Gate 2). No step asks the owner anything. You are the orchestrator: you dispatch roles, run the helper, and keep `status.md` true. You don't do the roles' work yourself.

Run the orchestrator in a **standard-tier session** (Sonnet, or Codex `--profile at-standard`). Orchestration is mechanical; the roles get their own models.

**The helper.** `agent-team <command>` (put on PATH by `install.sh`; otherwise `python3 <this skill's folder>/scripts/agent_team.py`). It does the deterministic parts exactly: status, leases, tiers, diffs, tests, sync, push, CI, PR body. Use it instead of working those out yourself. Exit codes: 0 ok, 1 failed, 2 merge conflict, 3 push rejected. `agent-team -h` lists the commands.

## 0. Start or resume

- Needs a git repo with `.agent-team/project.md` on the default branch: `D=$(agent-team default-branch)`, then `git fetch origin` and `git show origin/$D:.agent-team/project.md`. Missing → stop: "run team-init first" (or, if it's only on `agent-team/meta`, "merge the agent-team/meta PR first" — the feature branch starts from `$D`).
- Then:
  - **Remote `feature/<slug>` exists → resume.** If this machine has no `.agent-team/worktrees/<slug>`, run `git worktree add .agent-team/worktrees/<slug> feature/<slug>` (tracking `origin/feature/<slug>`). If the branch has no `status.md`, stop: "status.md is missing" — don't start over.
  - **Only a local-only `feature/<slug>` exists** (never pushed) → resume it here; `agent-team push <slug>` first, and stop if that fails.
  - **Neither exists → new run.** `agent-team idea <slug>`: unknown slug → stop; status `shipped` or `rejected` → stop and say so.
- **Lease (resume only; a new run takes it in step 1):** `agent-team lease <slug> acquire`. It fast-forwards the worktree to `origin/feature/<slug>`, then commits and pushes the lease, so another machine sees it. If it fails (another machine holds it, won the race, or the branches diverged), stop and relay the message — **don't touch `status.md` or the PR**: they belong to the other run. Use `--takeover` only when the owner says that run is dead.
- Resume by `stage` (`agent-team status <slug> stage`):
  - `stopped` — read `stop_reason`; continue from `stopped_at` (the owner fixed the cause on the branch). Reset that stage's counter (`review_round`, `qa_round` or `ci_round`) to 0.
  - `pr-open` — the PR is waiting for the owner's merge: `agent-team lease <slug> release` and say so; nothing else.
  - `merged` / `marketed` — nothing to build; point to `team-wrap <slug>` / `team-market <slug>`.
  - any other stage — continue from it.

## 1. Workspace

Worktrees live inside the project at `.agent-team/worktrees/<slug>` (gitignored by team-init), so tool permissions and sandboxes cover them. Never touch the current checkout, even if it has uncommitted changes.

New run: `git worktree add -b feature/<slug> .agent-team/worktrees/<slug> origin/$D`, then `agent-team init-status <slug>` (writes the initial `status.md` with `stage: spec` and this machine as owner), commit it, and `agent-team push <slug>` right away — that push is the lease. If it's rejected, another machine started the same feature: remove this worktree and branch (`agent-team cleanup <slug> --force` — nothing of value is in it yet) and stop.

## 2. Tiers

`agent-team tier <role> <slug> --tool <claude|codex|gemini|other> [--task T<n>] [--escalate]` prints `tier`, `model`, `effort` and the reason. It applies `project.md` `## Model overrides`, the rules below, and each role's `allowed-tiers`, with this skill's `references/models.yaml`. Dispatch per `references/dispatch-<tool>.md` (anything else → `dispatch-generic.md`); `model=session` means fallback — log it.

| Role (`tier` name) | Tier |
|---|---|
| PM spec (`pm-spec`) | deep; standard if the idea's effort is S |
| Tech Lead | standard if the spec has ≤ 2 ACs and effort `S`, else deep |
| Developer | each task's tag; a task that fails twice reruns once at standard (`--escalate`); fixes for findings run at standard |
| Reviewer | standard; deep if the diff — without `.agent-team/`, lockfiles and generated code — has > 400 changed lines or > 15 files, or the plan lists security touchpoints |
| QA | fast; standard if the plan says `qa-ui: yes` |

## 3. Run the stages

After every stage, in this order: set the next `stage` and `agent-team log <slug> <stage> <role> --tier <t> --model <m> [--tokens <n>] [--cost <usd>] <note>` (add tokens and cost whenever the tool reports them — see the dispatch notes); commit the artifacts and `status.md` together; `agent-team push <slug>`. Exit 3 means another machine pushed to this branch: stop **without** the *Stop* steps (no status edit, no PR change, no lease release) and tell the owner. Never force-push.

1. **spec** — dispatch `pm` in spec mode, giving it the idea's entry from `agent-team idea <slug> --show` → `spec.md`.
2. **plan** — dispatch `tech-lead` → `plan.md`. If it wrote `## Spec problems`, go to *Stop*.
3. **implement** — `agent-team tasks <slug>` prints the unticked tasks in batches, e.g. `fast T2,T3` / `standard T4`. Dispatch `developer` once per batch, in order, at that batch's tier, naming exactly those task ids. If it reports `T<n> failed twice`, re-dispatch only `T<n>` at `agent-team tier developer <slug> --escalate`; if it fails again (or was already standard), go to *Stop* ("T<n> failed at standard") — the remaining tasks stay unticked for the resume. When `tasks` prints `all tasks done`, run `agent-team test <slug> --build`; if it fails, go to *Stop* ("broken build before review").
4. **review** — First `agent-team sync <slug>` (exit 2 → *Stop*: "merge conflict with $D"; exit 1 → *Stop* with its message); if it merged anything, `agent-team test <slug>` (fail → *Stop*: "tests fail after merging $D"). Then each round:
   - `review_round` +1. `agent-team next <slug> review` gives the file number N and the previous review file — numbers continue across stops, so earlier reviews are never overwritten. Dispatch `reviewer` with: review N, `since` = `last_reviewed_commit` (`none` only if no review exists yet), and the previous review file (if any). → `review-N.md`.
   - Set `last_reviewed_commit` to the worktree's `git rev-parse --short HEAD` (the commit just reviewed).
   - `APPROVED` → qa. `CHANGES REQUESTED` → dispatch `developer` (standard) with the must-fix `R<n>` findings → next round. Still `CHANGES REQUESTED` when `review_round` reaches **3** → *Stop* ("3 review rounds").
5. **qa** — Each round: `qa_round` +1; `agent-team next <slug> qa` gives the file number M; dispatch `qa` → `qa-M.md`. `PASSED` → pr. `FAILED` → developer (standard) fixes the `Q<n>` bugs → reviewer checks the changes since `last_reviewed_commit` (file number from `agent-team next <slug> review`; not counted in `review_round`), then set `last_reviewed_commit`. If that review says `CHANGES REQUESTED`: developer fixes, one more such review; still `CHANGES REQUESTED` → *Stop* ("review after QA fixes"). Then QA again. `FAILED` when `qa_round` reaches **2** → *Stop* ("2 QA rounds").
6. **pr** — `agent-team sync <slug>` again (conflict → *Stop*; merged anything → `agent-team test <slug>`, fail → *Stop*), push. If `gh pr view feature/<slug> --json number` finds a PR, reuse it; else `gh pr create --base $D --head feature/<slug> --title "<spec title>" --body "$(agent-team pr-body <slug> --summary '<3 lines>')"`. Set `pr=<number>`.
7. **ci** — `agent-team ci <slug> --watch`. `pass` or `none` → pr-open. It waits up to 5 minutes for checks to appear before deciding there's no CI. `fail` → set `ci_round` +1; if it's 1, dispatch `developer` (standard) with the failing checks (`gh run view <run-id> --log-failed`, last ~60 lines), then `agent-team test <slug>` (fail → *Stop*: "CI fix broke the tests"), commit, push, watch again. A second `fail` → *Stop* ("CI failing").
8. **pr-open** — commit and push `status.md`, then `agent-team lease <slug> release` (it commits and pushes the release), and tell the owner: "PR #<n> is green and ready to merge; afterwards run `team-wrap <slug>` (and `team-market <slug>` for outreach)."

**Stop** (a limit hit, spec problems, broken build, merge conflict, failing CI — *not* a rejected push or a lost lease, see above): `agent-team status <slug> --set stage=stopped stopped_at=<stage> "stop_reason=<reason>"`, commit, `agent-team push <slug>` (exit 3 → stop here, change nothing else), then `agent-team lease <slug> release`. No PR yet → `gh pr create --draft … --body "$(agent-team pr-body <slug> --stopped '<reason>')"` and set `pr`. PR already open → `gh pr ready <pr> --undo` and `gh pr edit <pr> --body "$(agent-team pr-body <slug> --stopped '<reason>')"`. Tell the owner in one line what needs their decision. After they fix it on the branch, `team-build <slug>` resumes from `stopped_at`.

## Keep it cheap

- Hand each role only its inputs (see each role's `## Reads`), as paths — never pasted file contents.
- Don't re-run the PM or Tech Lead when resuming past their stages.
- Reviewer and QA use `agent-team test`, which reuses the cached result while the code commit hasn't changed, and `agent-team diff`, which leaves out `.agent-team/`, lockfiles and generated code.

## Never

- Never merge the PR, push to the default branch, or force-push.
- Never ask the owner for approval between Gate 1 and Gate 2; stop conditions open (or turn back into) a draft PR instead.
- Never skip review, QA or CI, even for a tiny change.
