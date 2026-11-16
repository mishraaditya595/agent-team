---
name: team-init
description: Use when setting up agent-team in a product repo for the first time — creates .agent-team/, drafts project.md from the codebase, and writes the permission settings for hands-off runs. Also use (`team-init upgrade`) to bring a repo set up by an older agent-team version up to date.
metadata:
  kind: workflow
---

# team-init · `team-init upgrade`

Run once per product repo. Afterwards every role can work on this project. The person running it is the **owner** unless they say otherwise.

## Steps

1. **Check the repo.** It must be a git repo with a GitHub remote (`gh repo view` works). `D=$(agent-team default-branch)` (if `agent-team` isn't on PATH, use `python3 <team-build skill folder>/scripts/agent_team.py`; suggest running `install.sh`). If anything is missing, stop and say what.
2. **Create `.agent-team/`** with an empty `features/` folder, and add `.agent-team/worktrees/` to the repo's `.gitignore` (team-build keeps its worktrees there, inside the project, so tool permissions and sandboxes cover them). If `.agent-team/project.md` already exists, don't redo it: run the **Upgrade** steps below instead, and mention that `team-init` from scratch is still possible if the owner asks for it explicitly.
3. **Draft `project.md`** from `references/project-template.md`. Fill it by reading only what's cheap and telling: README, package manifests (`pubspec.yaml`, `package.json`, `pyproject.toml`, …), CI config, test config, top-level folder names. Don't read the whole codebase. Keep it ≤ 60 lines. `## Owner`: the owner's name and `gh api user -q .login`. Write `unknown — owner to fill` rather than guessing positioning, voice or channels. If the project uses code generation the template's defaults don't cover, list its output globs under `## Diff excludes`.
4. **Write the permission settings** so the build workflow doesn't stop for prompts:
   - Claude Code: merge `references/claude-settings.json` into `.claude/settings.json`. Keep every existing key; add only missing allow entries. Replace `{{TEST_COMMANDS}}` with one `Bash(<cmd>:*)` entry per install/build/test command from `## Build & test`.
   - Codex: merge `references/codex-project.toml` into the project's `.codex/config.toml` (create it if needed; keep existing keys).
   - Gemini CLI: nothing to write; see the team-build skill's `references/dispatch-gemini.md` for its approval settings.
   Anything not on the list still prompts — that's intended.
5. **Commit on the default branch, only these paths.** If the checkout isn't on `$D`, stop and tell the owner. Commit without sweeping in anything the owner has staged: `git add` exactly these paths, then `git commit -m "chore: init agent-team" -- .agent-team .gitignore .claude/settings.json .codex/config.toml`.
6. **Push.** `git push origin $D`. If it's rejected because `$D` is protected: `git push origin HEAD:refs/heads/agent-team/meta`, open (or reuse) a PR from `agent-team/meta` into `$D` titled "agent-team: setup", and tell the owner to merge it. Other workflows read `.agent-team/` from `agent-team/meta` until then.
7. **Tell the owner** to read `project.md` once and fix anything wrong — especially `## Positioning & voice` and `## Channels`. Next step: run `team-ideate`.

## Upgrade (repos set up by an older version)

Adds only what's missing; never rewrites what the owner wrote.

1. Same checks as step 1, and the checkout must be on `$D` (else stop and tell the owner). `git pull --ff-only`.
2. `agent-team upgrade`. It adds missing `project.md` sections (filling `## Owner` from git/gh), merges the current permission allow-list (with this project's install/build/test commands) into `.claude/settings.json`, creates `.codex/config.toml` if missing, and adds `.agent-team/worktrees/` to `.gitignore`. It prints what changed.
3. If it printed `nothing — already up to date`, say so and stop.
4. Fill any new section you can from cheap reads (as in step 3 above); leave voice, positioning and channels as `unknown — owner to fill`.
5. Commit only the paths it listed — `git add <paths> && git commit -m "chore: upgrade agent-team setup" -- <paths>` — then push as in step 6 above.
6. Tell the owner what was added, and which sections still say `unknown — owner to fill`.

## Never

- Never overwrite an existing `.claude/settings.json` or `.codex/config.toml`; merge into them.
- Never add broad permissions (`Bash(*)`, full-auto/danger modes, `--approval-mode yolo`).
- Never force-push or bypass branch protection.
