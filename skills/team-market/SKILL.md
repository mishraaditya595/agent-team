---
name: team-market
description: Use after the owner has merged a feature's PR, to produce marketing drafts for it with the marketing agent.
metadata:
  kind: workflow
---

# team-market `<slug>`

1. **On the default branch.** `D=$(agent-team default-branch)`. If the checkout isn't on `$D`, stop and tell the owner. `git pull --ff-only` (if it can't fast-forward, stop), then `agent-team docs-pull`.
2. **Merged only.** Read `pr:` from `.agent-team/features/<slug>/status.md` and check `gh pr view <pr> --json state,mergedAt,url` (no status file on `$D` means it isn't merged). If it isn't merged, stop: "merge the PR first". Marketing never describes unshipped work.
3. If the status's `stage` isn't `merged` yet, run the `team-wrap` skill for `<slug>` first.
4. Pick the tier: `agent-team tier marketing <slug> --tool <tool>` (`deep` for `launch: true` in the spec, else `standard`; respects `project.md` `## Model overrides`).
5. Dispatch the `marketing` role (dispatch notes: the `team-build` skill's `references/`) → `marketing.md`.
6. `agent-team status <slug> --set stage=marketed`, `agent-team log <slug> marketed marketing --tier <t> --model <m> [--tokens <n>]`, then commit and push only those files: `agent-team docs-commit -m "docs(<slug>): marketing drafts" --title "agent-team: docs" .agent-team/features/<slug>`. `agent-team docs-commit` commits from a temporary worktree — never on your local default branch — and pushes to `$D`, or, if `$D` is protected or an `agent-team/meta` PR is still open, to `agent-team/meta`, opening or reusing its PR.
7. Tell the owner the drafts are ready and list the channels covered. Nothing is posted.
