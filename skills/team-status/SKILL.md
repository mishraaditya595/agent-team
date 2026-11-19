---
name: team-status
description: Use when the owner asks where agent-team features stand — which are running, stopped, waiting for merge or shipped, and what each cost.
metadata:
  kind: workflow
---

# team-status

1. Run `agent-team summary` from the product repo. It fetches, then reads `status.md` from every `feature/*` branch and from the default branch, and prints one row per feature: stage, review and QA rounds, PR, tokens, cost and any stop reason.
2. Show the table as printed. Tokens and cost appear only where the tool reported them (see the team-build skill's dispatch notes); `-` means not reported.
3. Under it, one line per feature that needs the owner, with the next command:
   - `stopped` → the stop reason, and "fix it on `feature/<slug>`, then `team-build <slug>`";
   - `pr-open` → "merge PR #<n>, then `team-wrap <slug>`" (in a workspace the PR column reads `api#12 app#40 ws#5`: merge in that order);
   - `merged` → "`team-market <slug>` if you want outreach drafts".
4. Don't change any files.
