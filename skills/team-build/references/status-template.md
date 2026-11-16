<!-- .agent-team/features/<slug>/status.md — the workflow's memory; any machine resumes from it. Edit with `agent-team status <slug> --set key=value`. -->
stage: spec            # spec | grill | plan | implement | review | qa | pr | ci | pr-open | merged | marketed | stopped
branch: feature/<slug>
pr: none               # PR number once opened
owner: none            # "<host> <utc time>" while a machine runs it (lease); none when idle
worktree: .agent-team/worktrees/<slug>
grill_round: 0
review_round: 0
qa_round: 0
ci_round: 0
last_reviewed_commit: none
tests: none            # "<code commit> pass|fail(...)" — cached test result
stop_reason: none
stopped_at: none       # the stage that hit the limit; a rerun after the owner's fix resumes here
retro: none            # done once lessons were captured (team-wrap)

## Log
<!-- YYYY-MM-DDTHH:MMZ <stage> <role> tier=<tier> model=<model> [tokens=<n>] [cost=<$>] <note> -->
