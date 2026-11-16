<!-- .agent-team/features/<slug>/status.md — the workflow's memory; any machine resumes from it. -->
stage: spec            # spec | plan | implement | review | qa | pr-open | merged | marketed | stopped
branch: feature/<slug>
review_round: 0
qa_round: 0
worktree: <path>
last_reviewed_commit: <sha or none>
stop_reason: none
stopped_at: none      # the stage that hit the limit; a rerun after Adi's fix resumes here

## Log
<!-- YYYY-MM-DD HH:MM <stage> <role> tier=<tier> model=<model> <note> -->
