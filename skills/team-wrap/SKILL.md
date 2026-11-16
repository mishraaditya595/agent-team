---
name: team-wrap
description: Use after the owner has merged a feature's PR — marks it shipped, captures lessons from its reviews and QA into .agent-team/lessons.md, and cleans up the worktree and branches.
metadata:
  kind: workflow
---

# team-wrap `<slug>`

Closes a merged feature so the next one starts cleaner. Run it on a standard-tier session; it's short.

1. **On the default branch.** `D=$(agent-team default-branch)`. If the checkout isn't on `$D`, stop and tell the owner. `git pull --ff-only` (if it can't fast-forward, stop), then `agent-team docs-pull`.
2. **Check the merge.** Read `pr:` from `.agent-team/features/<slug>/status.md` (it arrived with the merge). `gh pr view <pr> --json state,mergedAt`. Not merged → stop: "merge the PR first". If the status already says `retro: done`, skip to step 6.
3. **Clean up:** `agent-team cleanup <slug> --remote` — removes this machine's worktree, the local branch and the merged remote branch. It refuses if that would lose anything (uncommitted changes, commits that are neither pushed nor in the merged PR): then stop and show the owner its message; use `--force` only if they say so. (Other machines' worktrees are cleaned when they run `git worktree prune`.)
4. **Mark it shipped:** `agent-team status <slug> --set stage=merged owner=none` and `agent-team idea <slug> --set shipped`.
5. **Retro → lessons.** Read this feature's `review-*.md`, `qa-*.md` and the `status.md` log, then `.agent-team/lessons.md` (create it from `references/lessons-template.md` if missing). Add **at most 3** lessons, only patterns likely to recur in future features of this product:
   - a must-fix finding that took more than one round, or the same kind of finding in several places;
   - a QA bug whose cause is a project convention or a trap in the codebase;
   - a task tagged `[fast]` that had to escalate, and why;
   - a stop reason and what would have prevented it.
   One line each: what to do or avoid, and why, ending `(<slug>)`. Skip anything already covered, one-off typos and things a linter catches. Nothing worth keeping → add nothing; that's a fine outcome. Keep the file ≤ 40 lines: when it would grow past that, merge similar lines and drop lessons that no longer hold. Then `agent-team status <slug> --set retro=done`.
6. **Commit only agent-team files:** `agent-team docs-commit -m "docs(<slug>): wrap up" --title "agent-team: docs" .agent-team/features/<slug> .agent-team/ideas.md .agent-team/lessons.md`. `agent-team docs-commit` commits from a temporary worktree — never on your local default branch — and pushes to `$D`, or, if `$D` is protected or an `agent-team/meta` PR is still open, to `agent-team/meta`, opening or reusing its PR.
7. **Tell the owner** in two lines: the lessons added (or "none"), and "Run `team-market <slug>` for outreach drafts."

## Never

- Never delete a branch whose PR isn't merged, and never force-push.
- Never write a lesson that isn't backed by this feature's review, QA or status files.
