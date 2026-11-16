# End-to-end trial

**Status: not run yet.** This needs a machine with Claude Code and Codex signed in, and a GitHub repo `gh` can push to. The build sandbox had neither, so the trial runs on Adi's machine. Record results in the table at the bottom.

Use a throwaway clone of a small product (a tiny Flutter or Node app with at least one test).

| # | Do | Expect |
|---|---|---|
| 1 | `scripts/install.sh` (check `agent-team -h` works), then in the product repo run `team-init` | `.agent-team/project.md` ≤ 60 lines; `.claude/settings.json` + `.codex/config.toml` merged; commit `chore: init agent-team` on main |
| 2 | `team-ideate` | ≤ 5 ideas in `ideas.md`, each with a slug; `status`-style log shows PM on opus |
| 3 | Make an uncommitted edit, then `team-build <slug>` | Edit untouched; worktree created; `spec.md` has AC1…; plan tasks tagged `[fast]/[standard]`; developer on haiku; `review-1.md` has 3 passes; `qa-1.md` has the AC table; PR opens with links; `status.md` log lines show tier + model |
| 4 | Interrupt during review; run `team-build <slug>` from a second clone (or in Codex) | Resumes at `review`. On a scratch branch, delete `status.md` and retry → stops with "status.md is missing" |
| 5 | Repeat 3 on a repo with no tests | `plan.md` `## Test plan` says how tests are added; developer adds them |
| 6 | Merge the PR, then `team-market <slug>` | `marketing.md` has all four sections; nothing posted; stage `marketed` |
| 7 | Run `team-build` for a tiny idea in Codex | Roles run via `codex exec --profile at-<tier>`; models and `model_reasoning_effort` match `skills/team-build/references/models.yaml` |
| 8 | Merge, then `team-wrap <slug>` | worktree and branches removed; idea `Status: shipped`; ≤ 3 lines in `lessons.md` (or none); `retro: done` |
| 9 | Start `team-build <slug>` on machine A, then on machine B during the run | B stops with "running on A"; `--takeover` works after A is killed |
| 10 | Push a conflicting change to main mid-run | stops at review/pr with "merge conflict", draft PR |
| 11 | Repo with a CI workflow that fails on the branch | one CI fix round, then draft PR "CI failing" |
| 12 | `team-status` | table with stages, rounds, tokens where reported |
| 13 | Protected `main` (branch protection on) → `team-ideate` | ideas pushed to `agent-team/meta` with a PR; local `main` has no extra commit; `team-build` still finds the slug; then `team-ideate` again **before** merging, then squash-merge the PR: `agent-team pull` fast-forwards and the next workflow runs |
| 14 | `team-ideate add "<a one-line idea>"`, then `team-build <new slug>` | one `mode: owner` entry with slug, value/effort, ≤ 2 open questions; PM ran on standard; build starts from it |
| 15 | In a repo set up with v0.1, run `team-init upgrade` | only missing `project.md` sections and allow entries added; existing text untouched; second run says "already up to date" |

## Results

| # | Date | Tool | Result | Notes / fixes |
|---|---|---|---|---|
| | | | | |
