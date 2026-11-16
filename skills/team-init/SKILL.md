---
name: team-init
description: Use when setting up agent-team in a product repo for the first time — creates .agent-team/, drafts project.md from the codebase, and writes the permission settings for hands-off runs.
metadata:
  kind: workflow
---

# team-init

Run once per product repo. Afterwards every role can work on this project.

## Steps

1. **Check the repo.** It must be a git repo with a `main` (or default) branch and a GitHub remote (`gh repo view` works). If not, stop and say what's missing.
2. **Create `.agent-team/`** with an empty `features/` folder. If `.agent-team/project.md` already exists, stop and ask Adi whether to redo it.
3. **Draft `project.md`** from `references/project-template.md`. Fill it by reading only what's cheap and telling: README, package manifests (`pubspec.yaml`, `package.json`, `pyproject.toml`, …), CI config, test config, top-level folder names. Don't read the whole codebase. Keep it ≤ 60 lines. Write `unknown — Adi to fill` rather than guessing positioning, voice or channels.
4. **Write the permission settings** so the build workflow doesn't stop for prompts:
   - Claude Code: merge `references/claude-settings.json` into `.claude/settings.json`. Keep every existing key; add only missing allow entries. Replace `{{TEST_COMMANDS}}` with one `Bash(<cmd>:*)` entry per install/build/test command from `## Build & test`.
   - Codex: merge `references/codex-project.toml` into the project's `.codex/config.toml` (create it if needed; keep existing keys).
   Anything not on the list still prompts — that's intended.
5. **Commit on the default branch:** `chore: init agent-team` with `.agent-team/` and the settings files.
6. **Tell Adi** to read `project.md` once and fix anything wrong — especially `## Positioning & voice` and `## Channels`. Next step: run `team-ideate`.

## Never

- Never overwrite an existing `.claude/settings.json` or `.codex/config.toml`; merge into them.
- Never add broad permissions (`Bash(*)`, full-auto/danger modes).
