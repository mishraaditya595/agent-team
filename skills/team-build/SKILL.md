---
name: team-build
description: Use when Adi has picked an idea from .agent-team/ideas.md (or wants to resume a feature) and it should go spec → plan → build → review → QA → PR without further approvals.
metadata:
  kind: workflow
---

# team-build `<slug>`

Runs the hands-off middle: from Adi's pick (Gate 1) to an open PR for Adi to merge (Gate 2). No other step asks Adi anything. You are the orchestrator: you dispatch roles, move files between them, and keep `status.md` true. You don't do the roles' work yourself.

## 0. Start or resume

- Must be in a git repo with `.agent-team/project.md` (else: "run team-init first"). Default branch: `git symbolic-ref --short refs/remotes/origin/HEAD` (strip `origin/`).
- `git fetch`. Then:
  - **Remote `feature/<slug>` exists → resume.** Read `.agent-team/features/<slug>/status.md` from that branch (`git show origin/feature/<slug>:.agent-team/features/<slug>/status.md`). If the branch exists but `status.md is missing`, stop and say so; don't start over.
  - **Only a local-only `feature/<slug>` exists** (never pushed) → resume it on this machine from its `status.md`, and push it first; if the push fails, stop.
  - **Neither exists** → new run, if the slug is in `ideas.md`; otherwise stop: "unknown slug".
- Resuming by `stage`:
  - `stage: stopped` — read `stop_reason`; continue from `stopped_at` (Adi has fixed the cause, e.g. edited the spec or plan on the branch). Round counters for that stage restart at 0.
  - `stage: pr-open` — say the PR is open and waiting for Adi's merge; do nothing else.
  - `merged` / `marketed` — nothing to build; point to `team-market <slug>`.
  - any other stage — continue from it.

## 1. Workspace

Worktrees live inside the project at `.agent-team/worktrees/<slug>` (gitignored by team-init), so tool permissions and sandboxes cover them. Never touch the current checkout, even if it has uncommitted changes.

- **New run:** `git worktree add -b feature/<slug> .agent-team/worktrees/<slug> origin/<default-branch>`. Write an initial `status.md` (`references/status-template.md`, `stage: spec`), commit it, and push the branch right away. If the push fails, stop — another machine must be able to see this run.
- **Resume:** if `.agent-team/worktrees/<slug>` doesn't exist on this machine, `git worktree add .agent-team/worktrees/<slug> feature/<slug>` (tracking `origin/feature/<slug>`). Ignore the `worktree:` path recorded by another machine; write this machine's path.

## 2. Pick tiers

Tier lookup order: `project.md` `## Model overrides` → the rules below → the role's default (`metadata.tier`). Map tier → model with this skill's `references/models.yaml` for the tool you're running in. Dispatch per `references/dispatch-<tool>.md` (claude, codex, gemini; anything else → `dispatch-generic.md`). If the tool or tier is missing from `references/models.yaml`, use the generic dispatch and log `fallback`.

| Role | Tier |
|---|---|
| PM (spec) | deep |
| Tech Lead | standard if the spec has ≤ 2 ACs and effort `S`, else deep |
| Developer | each task's tag (`[fast]`/`[standard]`); a task that fails twice is re-run once at standard |
| Reviewer | standard; deep if `git diff --shortstat <default-branch>...` shows > 400 changed lines or > 15 files, or the plan lists auth, payments, migrations or security |
| QA | fast; standard if any AC needs a browser/UI or exploratory testing |

## 3. Run the stages

After every stage: commit the artifacts, `git push origin feature/<slug>`, update `stage` and append a log line (role, tier, model, note) to `status.md`.

1. **spec** — dispatch `pm` in spec mode → `spec.md`.
2. **plan** — dispatch `tech-lead` → `plan.md`. If it wrote `## Spec problems`, go to *Stop*.
3. **implement** — dispatch `developer` with `plan.md`. Re-dispatch a task that failed twice at standard; if it fails again, go to *Stop*. When all tasks are ticked, run the `Build` and `Test` commands from `project.md` `## Build & test` yourself in the worktree; if either fails, go to *Stop* ("broken build before review").
4. **review** — dispatch `reviewer` (round N) → `review-N.md`. `CHANGES REQUESTED` → developer fixes the must-fix findings → review again (changed files only). Max **3 review rounds** in this stage.
5. **qa** — dispatch `qa` (round N) → `qa-N.md`. `FAILED` → developer fixes the `Q<n>` bugs → reviewer checks the changed files (one review, not counted in the review rounds) → QA again. Max **2 QA rounds**.
6. **pr-open** — `gh pr create --base <default-branch> --head feature/<slug>` with title `<spec title>` and a body linking `spec.md`, `plan.md`, every `review-N.md` and `qa-N.md`, plus a 3-line summary and the tier/model log. Tell Adi: "PR ready to merge; afterwards run team-market <slug>."

**Stop** (any limit hit: 3 review rounds, 2 QA rounds, a task failing at standard, spec problems, broken build): set `stage: stopped`, `stopped_at: <stage>`, `stop_reason`; open the PR with `gh pr create --draft`, put the reason at the top of the body, and tell Adi in one line what needs his decision. After he fixes it on the branch, `team-build <slug>` resumes from `stopped_at`.

## Keep it cheap

- Hand each role only its inputs (see each role's `## Reads`). Never paste whole artifacts into prompts when a path will do.
- Don't re-run the PM or Tech Lead when resuming past their stages.

## Never

- Never merge the PR or push to the default branch.
- Never ask Adi for approval between Gate 1 and Gate 2; stop conditions open a draft PR instead.
- Never skip review or QA, even for a tiny change.
