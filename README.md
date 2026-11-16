# agent-team

A portable AI product team for products you've already built. Six roles — **PM, Tech Lead, Developer, Reviewer, QA, Marketing** — written as standard Agent Skills (`SKILL.md`), so they run in Claude Code, Codex, Gemini CLI and other tools that support skills. Each role runs on the cheapest model that suits it.

You approve twice: **which feature to build**, and **the merge**. Everything in between runs on its own.

```
team-ideate ─► PM proposes ideas ─► you pick one (Gate 1)
team-build <slug>
   PM spec ─► Tech Lead plan ─► Developer (TDD) ─► Reviewer (3 passes, ≤3 rounds)
           ─► QA vs acceptance criteria (≤2 rounds) ─► PR
you merge (Gate 2)
team-market <slug> ─► Marketing drafts (nothing is posted)
```

If a limit is hit (too many review/QA rounds, a broken build, a spec problem), you get a **draft PR** with the reason instead of a question mid-run.

## Install (on every machine)

```bash
git clone https://github.com/<owner>/agent-team ~/agent-team
pip install pyyaml            # for the Codex profiles step
~/agent-team/scripts/install.sh
```

`install.sh` links the skills into `~/.claude/skills` and `~/.agents/skills` (read by Codex and other tools), and writes `at-deep` / `at-standard` / `at-fast` profiles into `~/.codex/config.toml` without touching your other settings. It's safe to re-run; `git pull` + re-run to update.

Alternatives:
- **Claude Code plugin** (also installs the role subagents pinned to their models): `/plugin marketplace add <owner>/agent-team`, then `/plugin install agent-team@agent-team`.
- **Any Agent Skills tool:** `npx skills add <owner>/agent-team`.

## First run in a product repo

1. `team-init` — creates `.agent-team/`, drafts `project.md` from the codebase, and writes permission settings so builds don't stop for prompts. Read `project.md` once and fix it (especially positioning, voice and channels).
2. `team-ideate [expand|hold|reduce]` — up to 5 ideas in `.agent-team/ideas.md`.
3. `team-build <slug>` — runs in its own git worktree on `feature/<slug>`; your checkout is never touched. Resumable on any machine from `.agent-team/features/<slug>/status.md`.
4. Review and merge the PR.
5. `team-market <slug>` — drafts in `marketing.md`.

## Models and cost

Roles name a **tier**; `config/models.yaml` (a link to `skills/team-build/references/models.yaml`, so it ships with the skills however you install them) maps tiers to each tool's models. Check the Codex and Gemini model ids there against your accounts.

| Role | Default | Moves up when |
|---|---|---|
| PM | deep (Opus) | — |
| Tech Lead | deep | drops to standard for tiny specs (≤ 2 ACs, effort S) |
| Developer | fast (Haiku) per task tag | a task fails twice → standard (Sonnet) |
| Reviewer | standard | > 400 lines, > 15 files, or auth/payments/migrations/security → deep |
| QA | fast | UI/browser or exploratory testing → standard |
| Marketing | standard | launch or new product → deep |

Override per project in `project.md` → `## Model overrides`. Each feature's `status.md` logs the tier and model every stage used.

## Add a role

1. `skills/<role>/SKILL.md` with `metadata: {kind: role, tier: …, allowed-tiers: […]}` and `## Reads`, `## Writes`, `## Never` sections (≤ 150 lines; detail in `references/`).
2. `agents/<role>.md` with the Claude model for its tier.
3. Reference it from a workflow skill (`team-build`, or a new `team-*`).
4. Run `python3 -m pytest -q && python3 scripts/validate.py .`

## Develop

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q && bash tests/test_install.sh && python3 scripts/validate.py .
```

Credits: see [NOTICE](NOTICE). License: MIT.
