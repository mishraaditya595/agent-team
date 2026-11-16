---
name: team-market
description: Use after Adi has merged a feature's PR, to produce marketing drafts for it with the marketing agent.
metadata:
  kind: workflow
---

# team-market `<slug>`

1. Find the feature's PR and check it's **merged**: `gh pr view feature/<slug> --json state,mergedAt,url`. If it isn't merged, stop: "merge the PR first". (Marketing never describes unshipped work.)
2. Pull the default branch; read `.agent-team/features/<slug>/status.md`. Set `stage: merged` if it isn't already.
3. Pick the tier: `deep` if `spec.md` says `launch: true` or this is a new product, else `standard` (respect `project.md` `## Model overrides`).
4. Dispatch the `marketing` role (dispatch notes: the `team-build` skill's `references/`) → `marketing.md`.
5. Set `stage: marketed`, log the tier and model, commit `docs(<slug>): marketing drafts` on the default branch and push.
6. Tell Adi the drafts are ready and list the channels covered. Nothing is posted.
