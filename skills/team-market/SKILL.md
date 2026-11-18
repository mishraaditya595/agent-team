---
name: team-market
description: Use after the owner has merged a feature's PR to produce marketing drafts for it, or when the owner hands over an idea, plan or topic (`--topic`) to turn into Instagram, blog, LinkedIn and Reddit drafts.
metadata:
  kind: workflow
---

# team-market `<slug>` · `team-market --topic "<idea, plan path or topic>" [--channels a,b]`

Two ways in: a merged feature (`<slug>`, steps 1–7) or anything the owner wants to talk about (`--topic`, the last section).

## Feature

1. **On the default branch.** `D=$(agent-team default-branch)`. If the checkout isn't on `$D`, stop and tell the owner. `agent-team pull` (instead of `git pull`: it first puts back any doc copy `docs-pull` wrote that nobody edited, then pulls `--ff-only` and brings in docs still waiting on an `agent-team/meta` PR). If it fails, stop and show the owner its message.
2. **Merged only.** Read `pr:` from `.agent-team/features/<slug>/status.md` and check `gh pr view <pr> --json state,mergedAt,url` (no status file on `$D` means it isn't merged). If it isn't merged, stop: "merge the PR first". Marketing never describes unshipped work.
3. If the status's `stage` isn't `merged` yet, run the `team-wrap` skill for `<slug>` first.
4. Pick the tier: `agent-team tier marketing <slug> --tool <tool>` (`deep` for `launch: true` in the spec, else `standard`; respects `project.md` `## Model overrides`).
5. Dispatch the `marketing` role (dispatch notes: the `team-build` skill's `references/`) → `marketing.md`.
6. `agent-team status <slug> --set stage=marketed`, `agent-team log <slug> marketed marketing --tier <t> --model <m> [--tokens <n>]`, then commit and push only those files: `agent-team docs-commit -m "docs(<slug>): marketing drafts" --title "agent-team: docs" .agent-team/features/<slug>`. `agent-team docs-commit` commits from a temporary worktree — never on your local default branch — and pushes to `$D`, or, if `$D` is protected, an `agent-team/meta` PR is still open, or `project.md` sets `docs-push: pr-only`, to `agent-team/meta`, opening or reusing its PR.
7. Tell the owner the drafts are ready and list the channels covered. Nothing is posted.

## Topic

The owner gives an idea, a plan (file path or pasted text) or just a topic — nothing has to be built or merged.

1. **On the default branch**, as step 1 above (`agent-team pull`; stop on failure).
2. Pick the tier: `agent-team tier marketing-topic --tool <tool>` (standard; respects `## Model overrides`).
3. Choose a short kebab-case topic slug and the file `.agent-team/marketing/<YYYY-MM-DD>-<topic-slug>.md`.
4. Dispatch the `marketing` role in **topic mode** with the owner's input (as given, or the plan's path), the channels from `--channels` if any, and the output path.
5. Commit and push only that file: `agent-team docs-commit -m "docs(marketing): <topic-slug> drafts" --title "agent-team: docs" .agent-team/marketing/<file>`.
6. Tell the owner the drafts are ready, the angle the agent took, and the channels covered. Nothing is posted.
