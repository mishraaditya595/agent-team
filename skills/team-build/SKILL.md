---
name: team-build
description: Use when Adi has picked an idea from .agent-team/ideas.md (or wants to resume a feature) and it should go spec → plan → build → review → QA → PR without further approvals.
metadata:
  kind: workflow
---

# team-build `<slug>`

Runs the hands-off middle: from Adi's pick (Gate 1) to an open PR for Adi to merge (Gate 2). No other step asks Adi anything. You are the orchestrator: you dispatch roles, move files between them, and keep `status.md` true. You don't do the roles' work yourself.

## 0. Start or resume

- Must be in a git repo with `.agent-team/project.md` (else: "run team-init first").
- `git fetch`. If `feature/<slug>` exists on the remote, this is a **resume**:
  - read `.agent-team/features/<slug>/status.md` on that branch and continue from its `stage`;
  - if the branch exists but `status.md is missing`, stop and say so; don't start over.
- If the slug isn't in `ideas.md` and there's no branch, stop: "unknown slug".
- If the branch exists only locally (never pushed), say so and stop — another machine can't resume it.

## 1. Workspace

Create a git **worktree** for `feature/<slug>` off the default branch (e.g. `../<repo>-<slug>`). All work happens there. Never touch the current checkout, even if it has uncommitted changes. Record the path in `status.md` (template: `references/status-template.md`).

## 2. Pick tiers

Tier lookup order: `project.md` `## Model overrides` → the role's default (`metadata.tier`) → the rules below. Map tier → model via `config/models.yaml` for the tool you're running in. Dispatch per `references/dispatch-<tool>.md` (claude, codex, gemini; anything else → `dispatch-generic.md`). If the tool or tier is missing from `models.yaml`, use the generic dispatch and log `fallback`.

| Role | Tier |
|---|---|
| PM (spec) | deep |
| Tech Lead | standard if the spec has ≤ 2 ACs and effort `S`, else deep |
| Developer | each task's tag (`[fast]`/`[standard]`); a task that fails twice is re-run once at standard |
| Reviewer | standard; deep if `git diff --shortstat main...` shows > 400 changed lines or > 15 files, or the plan lists auth, payments, migrations or security |
| QA | fast; standard if any AC needs a browser/UI or exploratory testing |

## 3. Run the stages

After every stage: commit the artifacts, `git push origin feature/<slug>`, update `stage` and append a log line (role, tier, model, note) to `status.md`.

1. **spec** — dispatch `pm` in spec mode → `spec.md`.
2. **plan** — dispatch `tech-lead` → `plan.md`. If it wrote `## Spec problems`, go to *Stop*.
3. **implement** — dispatch `developer` with `plan.md`. Re-dispatch a task that failed twice at standard; if it fails again, go to *Stop*. If the build or tests are broken before review, go to *Stop*.
4. **review** — dispatch `reviewer` (round N) → `review-N.md`. `CHANGES REQUESTED` → developer fixes the must-fix findings → review again (changed files only). Max **3 review rounds**.
5. **qa** — dispatch `qa` (round N) → `qa-N.md`. `FAILED` → developer fixes the `Q<n>` bugs → reviewer checks the changed files → QA again. Max **2 QA rounds**.
6. **pr-open** — `gh pr create --base <default> --head feature/<slug>` with title `<spec title>` and a body linking `spec.md`, `plan.md`, every `review-N.md` and `qa-N.md`, plus a 3-line summary and the tier/model log. Tell Adi: "PR ready to merge; afterwards run team-market <slug>."

**Stop** (any limit hit: 3 review rounds, 2 QA rounds, a task failing at standard, spec problems, broken build): open the PR with `gh pr create --draft`, put the reason at the top of the body and in `status.md`, and tell Adi in one line what needs his decision.

## Keep it cheap

- Hand each role only its inputs (see each role's `## Reads`). Never paste whole artifacts into prompts when a path will do.
- Don't re-run the PM or Tech Lead when resuming past their stages.

## Never

- Never merge the PR or push to the default branch.
- Never ask Adi for approval between Gate 1 and Gate 2; stop conditions open a draft PR instead.
- Never skip review or QA, even for a tiny change.
