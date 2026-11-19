# Reference

Technical details for solo-squad. For the overview, see the [README](../README.md).

## Install (on every machine)

```bash
git clone https://github.com/mishraaditya595/agent-team ~/agent-team
pip install pyyaml            # for the Codex profiles step
~/agent-team/scripts/install.sh
```

`install.sh` links the skills into `~/.claude/skills` and `~/.agents/skills` (read by Codex and other tools), puts the **`agent-team` helper CLI** on your PATH (`~/.local/bin`), and writes `at-deep` / `at-standard` / `at-fast` profiles (model + reasoning effort) into `~/.codex/config.toml` without touching your other settings. It's safe to re-run; `git pull` + re-run to update.

Alternatives (both skip the PATH step — the workflows then call `python3 <team-build skill>/scripts/agent_team.py`, which asks for permission the first time):
- **Claude Code plugin** (also installs the role subagents pinned to their models): `/plugin marketplace add mishraaditya595/agent-team`, then `/plugin install solo-squad@solo-squad`.
- **Any Agent Skills tool:** `npx skills add mishraaditya595/agent-team`.

**Upgrading from the `agent-team` plugin (0.3.0 or earlier):** `/plugin uninstall agent-team@agent-team`, `/plugin marketplace remove agent-team`, then add the marketplace again and `/plugin install solo-squad@solo-squad`. The `agent-team` CLI and `.agent-team/` folders don't change.

## First run in a product repo

1. `team-init` — creates `.agent-team/`, drafts `project.md` from the codebase (owner, build/test commands, voice, channels), and writes permission settings so builds don't stop for prompts. Read `project.md` once and fix it.
2. `team-ideate [expand|hold|reduce]` — up to 5 ideas in `.agent-team/ideas.md`. **Got your own idea?** `team-ideate add "field reps lose drafts when offline — keep them on the device"` — the PM turns it into an entry with a slug, value/effort and open questions. Then `team-build <slug>` (or say "add … and build it" to do both).
3. `team-build <slug>` — runs in its own git worktree on `feature/<slug>`; your checkout is never touched. Resumable on any machine from `.agent-team/features/<slug>/status.md`; a lease stops two machines running the same feature at once. Start it in a standard-tier session (e.g. Sonnet) — the roles pick their own models.
4. Review and merge the PR.
5. `team-wrap <slug>`, then optionally `team-market <slug>`.

Anytime: `team-audit [quick|deep] [<category>]` — the Tech Lead audits the codebase across nine categories (correctness, security, performance, tests, tech debt, dependencies, DX, docs, direction). Every finding cites `file:line` and is re-checked before it's kept. The full report goes to `.agent-team/audits/<date>.md`; the top 5 become ideas (`mode: audit`) you pick from like any other, then `team-build <slug>`. `quick` runs on the standard tier.

Anytime: `team-market --topic "<idea, plan path or topic>" [--channels instagram,blog,linkedin,reddit]` drafts content for something that isn't a merged feature, into `.agent-team/marketing/`.

**The grill.** Before planning, the Tech Lead questions the PM in rounds (`grill.md`, at most 3). The PM answers from the spec, makes minor calls itself (`assumed`), or marks a question `owner` when it changes scope or what users see — then the run stops with a draft PR until you answer in `grill.md` and re-run `team-build <slug>`. The PR's **Decisions to check** section lists every `assumed` answer and every developer ruling.

**Set up with an earlier version?** Merge the update, re-run `install.sh`, then run `team-init upgrade` in each product repo — it adds the new `project.md` sections and permissions without touching what you wrote.

If `main` is branch-protected (or `project.md` `## Conventions` has `- docs-push: pr-only`, for owners who want every agent-team docs push reviewed), `team-init`, `team-ideate`, `team-wrap` and `team-market` push their docs to an `agent-team/meta` branch and open a PR for it instead. Your local `main` never gets a commit of its own. While a meta PR is open, the workflows also put its newer docs into your checkout as uncommitted copies; to update `main` in that repo, use **`agent-team pull`** rather than `git pull` — it puts back copies nobody edited, so the fast-forward works after a squash merge (manual fix if needed: `git checkout -- .agent-team`). Merge the setup PR before the first `team-build`.

## The helper CLI

The workflows hand every deterministic step to `agent-team` (stdlib Python, `skills/team-build/scripts/agent_team.py`) instead of having the model work it out each time — cheaper and exact:

| Command | Does |
|---|---|
| `tier <role> <slug>` | picks tier, model and effort from the rules, `models.yaml` and project overrides |
| `tasks <slug>` | unticked plan tasks, batched by tier, for per-batch developer dispatch |
| `diff <slug> [--since SHA]` | the review diff without `.agent-team/`, lockfiles and generated code (`*.g.dart`, `*.freezed.dart`, …) |
| `test <slug> [--build]` | runs the project's tests in the worktree; caches the result per code commit |
| `sync <slug>` | merges the default branch in; reports conflicts |
| `drift <slug>` | files in `plan.md`'s `## Files` changed on the default branch since the plan's `planned-at`; `unchecked` when the plan has no usable stamp |
| `audit-path` | the next free `.agent-team/audits/<date>.md` name (checking here, the default branch and `agent-team/meta`) and the earlier reports |
| `push <slug>` / `lease <slug>` | push with a clear message on rejection (never forced); a lease that's committed and pushed, so only one machine runs a feature |
| `next <slug> review\|qa` | the next review/QA file number — continues across stops, so earlier reports are never overwritten |
| `status` / `log` / `init-status` | read and write `status.md` with a fixed schema |
| `ci <slug>` / `pr-body <slug>` | PR checks result; PR body with artifact links, the decisions to check (assumed grill answers, developer rulings) and the tier/cost log |
| `idea <slug> [--set …\|--show]` / `summary` | idea lifecycle and lookup; all-feature summary |
| `cleanup <slug> [--remote]` | post-merge cleanup; refuses if it would lose uncommitted or unpushed work, and `--remote` deletes the remote branch only if it was merged (`--force` to override) |
| `pull` / `docs-pull` / `docs-commit` | agent-team docs are committed from a temporary worktree — never on your local default branch — to `main`, or to `agent-team/meta` + PR when `main` is protected or `docs-push: pr-only` is set; `pull` replaces `git pull` in the workflows |
| `upgrade` | adds missing `project.md` sections and permissions to a repo set up by an older version |

## Workspaces

A workspace is a directory (its own git repo) that holds several product repos side by side. Its `project.md` has `## Repos` (path, `Order:` = merge order, `## Cross-repo rules`). Features run in a worktree of the workspace repo with nested product worktrees under it (`agent-team repos <slug> --ensure`). Each touched repo gets its own `feature/<slug>` PR, plus one workspace PR that carries the spec and plan and lists the product PRs. Merge product PRs in `Order:`, the workspace PR last; `team-wrap` checks all of them. Without `## Repos`, nothing changes.

## Models and cost

Roles name a **tier**; `skills/team-build/references/models.yaml` maps tiers to each tool's models and reasoning effort. Check the Codex and Gemini model ids there against your accounts.

| Role | Default | Moves |
|---|---|---|
| PM | deep (Opus) | standard when shaping your own idea (`add`), and for the spec when the idea's effort is S |
| Tech Lead (grill + plan) | deep | standard for tiny specs (≤ 2 ACs, effort S) |
| PM answering the grill | as PM spec | |
| Developer | each task's tag (fast/standard) | a task that fails twice → standard; fixes for findings run at standard |
| Reviewer | standard | diff > 400 lines or > 15 files (noise excluded), or security touchpoints in the plan → deep |
| QA | fast | plan says `qa-ui: yes` → standard |
| Marketing | standard | `launch: true` → deep; topic mode (`marketing-topic`) stays standard |

Override per project in `project.md` → `## Model overrides`. Each feature's `status.md` logs the tier, model and (where the tool reports it) tokens and cost of every stage; `team-status` totals them.

## Add a role

1. `skills/<role>/SKILL.md` with `metadata: {kind: role, tier: …, allowed-tiers: […]}` and `## Reads`, `## Writes`, `## Never` sections (≤ 150 lines; detail in `references/`).
2. `agents/<role>.md` with the Claude model for its tier and the skill's description.
3. Add its tier rule to `agent_team.py` (`ROLES`, `rule_tier`) and reference it from a workflow skill.
4. Run `python3 -m pytest -q && python3 scripts/validate.py .`

## Develop

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q && bash tests/test_install.sh && python3 scripts/validate.py .
```

