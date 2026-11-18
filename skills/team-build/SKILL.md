---
name: team-build
description: Use when the owner has picked an idea from .agent-team/ideas.md (or wants to resume a feature) and it should go spec → grill → plan → build → review → QA → PR → CI without further approvals.
metadata:
  kind: workflow
---

# team-build `<slug>`

Runs the hands-off middle: from the owner's pick (Gate 1) to a green PR for the owner to merge (Gate 2). The only step that can ask the owner anything is the grill, and only for questions that change scope or what users see. You are the orchestrator: you dispatch roles, run the helper, and keep `status.md` true. You don't do the roles' work yourself.

Run the orchestrator in a **standard-tier session** (Sonnet, or Codex `--profile at-standard`). Orchestration is mechanical; the roles get their own models.

**The helper.** `agent-team <command>` (put on PATH by `install.sh`; otherwise `python3 <this skill's folder>/scripts/agent_team.py`). It does the deterministic parts exactly: status, leases, tiers, diffs, tests, sync, push, CI, PR body. Use it instead of working those out yourself. Exit codes: 0 ok, 1 failed, 2 merge conflict, 3 push rejected. `agent-team -h` lists the commands.

## 0. Start or resume

- Needs a git repo with `.agent-team/project.md` on the default branch: `D=$(agent-team default-branch)`, then `git fetch origin` and `git show origin/$D:.agent-team/project.md`. Missing → stop: "run team-init first" (or, if it's only on `agent-team/meta`, "merge the agent-team/meta PR first" — the feature branch starts from `$D`).
- Then:
  - **Remote `feature/<slug>` exists → resume.** If this machine has no `.agent-team/worktrees/<slug>`, run `git worktree add .agent-team/worktrees/<slug> feature/<slug>` (tracking `origin/feature/<slug>`); in a workspace (`project.md` has `## Repos`) then run `agent-team repos <slug> --ensure` to re-create the nested product worktrees. If the branch has no `status.md`, stop: "status.md is missing" — don't start over.
  - **Only a local-only `feature/<slug>` exists** (never pushed) → resume it here; `agent-team push <slug>` first, and stop if that fails.
  - **Neither exists → new run.** `agent-team idea <slug>`: unknown slug → stop; status `shipped` or `rejected` → stop and say so.
- **Lease (resume only; a new run takes it in step 1):** `agent-team lease <slug> acquire`. It fast-forwards the worktree to `origin/feature/<slug>`, then commits and pushes the lease, so another machine sees it. In a workspace, then always run `agent-team repos <slug> --ensure` (idempotent): another machine may have added product repos this one lacks worktrees for. If it fails (another machine holds it, won the race, or the branches diverged), stop and relay the message — **don't touch `status.md` or the PR**: they belong to the other run. Use `--takeover` only when the owner says that run is dead.
- Resume by `stage` (`agent-team status <slug> stage`):
  - `stopped` — read `stop_reason`; continue from `stopped_at` (the owner fixed the cause on the branch). Reset that stage's counter (`grill_round`, `review_round`, `qa_round` or `ci_round`) to 0. Stopped at `grill`: the owner has answered the `owner` questions in `grill.md` — check none is left blank (any blank → stop again with the same reason).
  - `pr-open` — the PR is waiting for the owner's merge: `agent-team lease <slug> release` and say so; nothing else.
  - `merged` / `marketed` — nothing to build; point to `team-wrap <slug>` / `team-market <slug>`.
  - any other stage — continue from it.
- **Drift check (resume at `implement`, or `stopped_at=implement`):** `agent-team drift <slug>`. `drift: none` → continue. `drift: unchecked (…)` (no stamp, no paths in `## Files`, or the stamp isn't in this clone) → continue, and put the reason in the next `agent-team log` note. Files listed → the default branch changed code the plan relies on: `agent-team sync <slug>` (exit 2 → *Stop*: "merge conflict with $D"; exit 1 → *Stop* with its message), then dispatch `tech-lead` in plan **refresh** mode (tier from `agent-team tier tech-lead <slug>`) with the drifted files, log it as `plan tech-lead refresh`, commit and push. Re-run `agent-team drift <slug>` and expect `drift: none`; anything else → *Stop*: "plan refresh didn't update planned-at" (otherwise every later resume pays for another refresh). Then implement. Exit 1 → *Stop* with its message.

## 1. Workspace

Worktrees live inside the project at `.agent-team/worktrees/<slug>` (gitignored by team-init), so tool permissions and sandboxes cover them. Never touch the current checkout, even if it has uncommitted changes.

New run: `git worktree add -b feature/<slug> .agent-team/worktrees/<slug> origin/$D`, then `agent-team init-status <slug>` (writes the initial `status.md` with `stage: spec` and this machine as owner), commit it, and `agent-team push <slug>` right away — that push is the lease. If it's rejected, another machine started the same feature: remove this worktree and branch (`agent-team cleanup <slug> --force` — nothing of value is in it yet) and stop. Otherwise, in a workspace, run `agent-team repos <slug> --ensure`.

## 2. Tiers

`agent-team tier <role> <slug> --tool <claude|codex|gemini|other> [--task T<n>] [--escalate]` prints `tier`, `model`, `effort` and the reason. It applies `project.md` `## Model overrides`, the rules below, and each role's `allowed-tiers`, with this skill's `references/models.yaml`. Dispatch per `references/dispatch-<tool>.md` (anything else → `dispatch-generic.md`); `model=session` means fallback — log it.

| Role (`tier` name) | Tier |
|---|---|
| PM spec (`pm-spec`) | deep; standard if the idea's effort is S |
| Tech Lead (grill and plan) | standard if the spec has ≤ 2 ACs and effort `S`, else deep |
| PM answering the grill | same as PM spec (`agent-team tier pm-spec <slug>`) |
| Developer | each task's tag; a task that fails twice reruns once at standard (`--escalate`); fixes for findings run at standard |
| Reviewer | standard; deep if the diff — without `.agent-team/`, lockfiles and generated code — has > 400 changed lines or > 15 files, or the plan lists security touchpoints |
| QA | fast; standard if the plan says `qa-ui: yes` |

## 3. Run the stages

After every stage, in this order: set the next `stage` and `agent-team log <slug> <stage> <role> --tier <t> --model <m> [--tokens <n>] [--cost <usd>] <note>` (add tokens and cost whenever the tool reports them — see the dispatch notes); commit the artifacts and `status.md` together; `agent-team push <slug>`. Exit 3 means another machine pushed to this branch: stop **without** the *Stop* steps (no status edit, no PR change, no lease release) and tell the owner. Never force-push.

1. **spec** — dispatch `pm` in spec mode, giving it the idea's entry from `agent-team idea <slug> --show` → `spec.md`.
2. **grill** — the Tech Lead grills the spec before planning (its `references/grilling.md`). Each round:
   - `grill_round` +1. Dispatch `tech-lead` in grill mode → it appends a round to `grill.md`, or reports `grill done`.
   - `grill done` → `spec.md` now has `## Decisions`; go to plan.
   - Otherwise dispatch `pm` in answer mode → it fills the round's answers.
   - Any `owner` answer → *Stop* with `stopped_at=grill` ("owner question: G<n>, … in grill.md"). The owner answers on the branch; the resume continues the grill.
   - After **3 grill rounds** the Tech Lead turns whatever is still open into `owner` questions, so the next round either finishes or stops.
   Log each dispatch as `grill tech-lead` / `grill pm`.
3. **plan** — dispatch `tech-lead` in plan mode → `plan.md`. If it wrote `## Spec problems`, go to *Stop*. In a workspace, then run `agent-team repos <slug> --ensure` (it creates worktrees for the repos the plan touches and records them in `repos`).
4. **implement** — `agent-team tasks <slug>` prints the unticked tasks in batches, e.g. `fast T2,T3` / `standard T4`. Dispatch `developer` once per batch, in order, at that batch's tier, naming exactly those task ids. If it reports `T<n> failed twice`, re-dispatch only `T<n>` at `agent-team tier developer <slug> --escalate`; if it fails again (or was already standard), go to *Stop* ("T<n> failed at standard") — the remaining tasks stay unticked for the resume. When `tasks` prints `all tasks done`, run `agent-team test <slug> --build`; if it fails, go to *Stop* ("broken build before review").
5. **review** — First `agent-team sync <slug>` (exit 2 → *Stop*: "merge conflict with $D"; exit 1 → *Stop* with its message); if it merged anything, `agent-team test <slug>` (fail → *Stop*: "tests fail after merging $D"). Then each round:
   - `review_round` +1. `agent-team next <slug> review` gives the file number N and the previous review file — numbers continue across stops, so earlier reviews are never overwritten. Dispatch `reviewer` with: review N, `since` = `last_reviewed_commit` (`none` only if no review exists yet), and the previous review file (if any). → `review-N.md`.
   - Set `last_reviewed_commit` with `"last_reviewed_commit=$(agent-team heads <slug>)"` (the commit just reviewed; per-repo heads in a workspace).
   - `APPROVED` → qa. `CHANGES REQUESTED` → dispatch `developer` (standard) with the Critical and Important `R<n>` findings → next round. Still `CHANGES REQUESTED` when `review_round` reaches **3** → *Stop* ("3 review rounds").
6. **qa** — Each round: `qa_round` +1; `agent-team next <slug> qa` gives the file number M; dispatch `qa` → `qa-M.md`. `PASSED` → pr. `FAILED` → developer (standard) fixes the `Q<n>` bugs → reviewer checks the changes since `last_reviewed_commit` (file number from `agent-team next <slug> review`; not counted in `review_round`), then set `"last_reviewed_commit=$(agent-team heads <slug>)"`. If that review says `CHANGES REQUESTED`: developer fixes, one more such review; still `CHANGES REQUESTED` → *Stop* ("review after QA fixes"). Then QA again. `FAILED` when `qa_round` reaches **2** → *Stop* ("2 QA rounds").
7. **pr** — `agent-team sync <slug>` again (conflict → *Stop*; merged anything → `agent-team test <slug>`, fail → *Stop*), push. If `gh pr view feature/<slug> --json number` finds a PR, reuse it; else `gh pr create --base $D --head feature/<slug> --title "<spec title>" --body "$(agent-team pr-body <slug> --summary '<3 lines>')"`. Set `pr=<number>`.
   In a workspace, first, for each repo in `repos` order that has changes (`<owner/repo>` = `repo=` and `<branch>` = `branch=` from `agent-team repos`) (`agent-team diff <slug> --stat` prints a `## <path>` section per repo; skip empty ones): `gh pr view feature/<slug> -R <owner/repo> --json number`, else `gh pr create -R <owner/repo> --base <branch> --head feature/<slug> --title "<spec title>" --body "$(agent-team pr-body <slug> --repo <path> --summary '<3 lines>')"`. Set `"repo_prs=<path>#<n> …"` before the workspace PR, so its body lists the product PRs. Then the workspace PR as above and `pr=<number>`; finally `gh pr edit <n> -R <owner/repo> --body "$(agent-team pr-body <slug> --repo <path> --summary '<3 lines>')"` for each product PR (the numbers exist now).
8. **ci** — `agent-team ci <slug> --watch`. `pass` or `none` → pr-open. It waits up to 5 minutes for checks to appear before deciding there's no CI. `fail` → set `ci_round` +1; if it's 1, dispatch `developer` (standard) with the failing checks (`gh run view <run-id> --log-failed`, with `-R <owner/repo>` for a product PR; last ~60 lines), then `agent-team test <slug>` (fail → *Stop*: "CI fix broke the tests"), then `reviewer` checks the changes since `last_reviewed_commit` (file number from `agent-team next <slug> review`; not counted in `review_round`) and you set `"last_reviewed_commit=$(agent-team heads <slug>)"` — `CHANGES REQUESTED` → *Stop* ("review of the CI fix"). Commit, push, watch again. A second `fail` → *Stop* ("CI failing").
9. **pr-open** — commit and push `status.md`, then `agent-team lease <slug> release` (it commits and pushes the release), and tell the owner: "PR #<n> is green and ready to merge; afterwards run `team-wrap <slug>` (and `team-market <slug>` for outreach)." In a workspace, list the PRs in merge order (product PRs in `repos` order, the workspace PR last).

**Stop** (a limit hit, an owner question from the grill, spec problems, broken build, merge conflict, failing CI — *not* a rejected push or a lost lease, see above): `agent-team status <slug> --set stage=stopped stopped_at=<stage> "stop_reason=<reason>"`, commit, `agent-team push <slug>` (exit 3 → stop here, change nothing else), then `agent-team lease <slug> release`. No PR yet → `gh pr create --draft … --body "$(agent-team pr-body <slug> --stopped '<reason>')"` and set `pr`. PR already open → `gh pr ready <pr> --undo` and `gh pr edit <pr> --body "$(agent-team pr-body <slug> --stopped '<reason>')"`. In a workspace, do this (draft, `ready --undo`, edit body) for every PR that exists, product PRs with `-R <owner/repo>` and `--repo <path>`. Tell the owner in one line what needs their decision. After they fix it on the branch, `team-build <slug>` resumes from `stopped_at`.

**Design problems.** If the developer reports `<id>: 3 fixes failed — design problem` while fixing any finding, go to *Stop* ("design problem: <id>") instead of another round.

## Keep it cheap

- Hand each role only its inputs (see each role's `## Reads`), as paths — never pasted file contents.
- Don't re-run the PM or Tech Lead when resuming past their stages (except the drift refresh in step 0); a resumed grill continues from the last round in `grill.md`.
- Reviewer and QA use `agent-team test`, which reuses the cached result while the code commit hasn't changed, and `agent-team diff`, which leaves out `.agent-team/`, lockfiles and generated code.

## Never

- Never merge the PR, push to the default branch, or force-push.
- Never ask the owner for approval between Gate 1 and Gate 2; stop conditions open (or turn back into) a draft PR instead.
- Never skip review, QA or CI, even for a tiny change.
