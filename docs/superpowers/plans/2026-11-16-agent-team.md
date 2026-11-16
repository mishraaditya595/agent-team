# Agent Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `agent-team` repo: six portable role skills (PM, Tech Lead, Developer, Reviewer, QA, Marketing), the workflow skills that chain them, model tiers per role, and installers for Claude Code, Codex and other Agent Skills tools.

**Architecture:** Everything is a standard SKILL.md under `skills/`, using portable frontmatter only (`name`, `description`, `metadata`). `metadata.kind` marks a skill as `role` or `workflow`. Roles carry `metadata.tier` and `metadata.allowed-tiers`. `config/models.yaml` maps tiers to models for each tool. A Python validator keeps all of this consistent. Thin adapters sit on top: Claude plugin manifests plus subagent files, Codex profiles written by `install.sh`, and `npx skills` for everything else.

**Tech Stack:** Markdown (SKILL.md, Agent Skills standard); Python 3.10+ with PyYAML and pytest for the validator and config tools; Bash for `install.sh`; `gh` CLI used by the workflows at runtime.

**Spec:** `docs/superpowers/specs/2026-11-16-agent-team-design.md`

## Global Constraints

- Frontmatter uses only the portable fields `name`, `description`, `metadata` (plus `license`). No tool-specific fields in `skills/**/SKILL.md`.
- `name` equals the skill's folder name.
- Tiers are exactly `deep`, `standard`, `fast`.
- Role → default tier / allowed tiers: pm `deep`/[deep]; tech-lead `deep`/[deep, standard]; developer `fast`/[fast, standard]; reviewer `standard`/[deep, standard]; qa `fast`/[fast, standard]; marketing `standard`/[deep, standard].
- Human gates are exactly two: Gate 1 (Adi picks an idea from `ideas.md`), Gate 2 (Adi merges the PR). No other step waits for approval.
- Caps: review rounds max **3**; QA rounds max **2**. Developer escalates `fast` → `standard` after the **same task fails tests twice**. Reviewer escalates to `deep` when the diff exceeds **400 changed lines or 15 files**, or touches auth, payments, data migrations or security. QA escalates to `standard` when browser/UI or exploratory testing is needed. Marketing escalates to `deep` for launch-level positioning or a new product.
- Per-project artifacts live under `.agent-team/` exactly as in spec §6.3, including `qa-N.md`. The `status.md` stages are `spec | plan | implement | review | qa | pr-open | merged | marketed`.
- Developer branches are `feature/<slug>`, each in its own git worktree, pushed after every stage change. `ideas.md` is committed to `main` as a docs-only change.
- The Reviewer never edits code. QA may add acceptance tests but never changes feature code. The Developer never merges. The PM never starts implementation.
- No runtime dependency on superpowers, gstack, ponytail or any other plugin. Borrowed ideas are credited in `NOTICE`.
- Target lengths: `project.md` about one screen (≤ 60 lines); each role SKILL.md ≤ 150 lines, with anything longer moved to `references/`.

## Review Focus

1. **`install.sh` run twice, or on a machine whose `~/.codex/config.toml` already has the user's own settings** → no duplicate profiles, and user content is kept untouched (Task 9 test).
2. **`models.yaml` is missing a tool or a tier** → the validator names exactly what's missing, and dispatch falls back to the session model with a note in `status.md` (Tasks 1 and 7).
3. **`team-build <slug>` resumed on another machine when the branch was never pushed or `status.md` is missing** → it stops and says which of the two is missing instead of starting over (Task 7 content check, Task 11 scenario).
4. **A product repo with no tests or no known build command** → the plan defines how tests run, the Developer adds them, and a broken build before review stops with a draft PR (Tasks 5 and 7 content checks, Task 11 scenario).
5. **A dirty working tree or uncommitted changes when `team-build` starts** → the run happens in a fresh worktree, so Adi's changes are never touched (Task 7 content check).

---

## File Structure

```
agent-team/
  skills/
    engineering-guidelines/SKILL.md
    pm/SKILL.md, references/{ideation-modes.md, ideas-template.md, spec-template.md}
    tech-lead/SKILL.md, references/{plan-template.md, plan-checklist.md}
    developer/SKILL.md
    reviewer/SKILL.md, references/review-template.md
    qa/SKILL.md, references/{qa-template.md, test-by-platform.md}
    marketing/SKILL.md, references/{launch-copy.md, release-notes.md, social-posts.md, marketing-template.md}
    team-init/SKILL.md, references/{project-template.md, claude-settings.json, codex-project.toml}
    team-ideate/SKILL.md
    team-build/SKILL.md, references/{status-template.md, dispatch-claude.md, dispatch-codex.md, dispatch-gemini.md, dispatch-generic.md}
    team-market/SKILL.md
  agents/{pm,tech-lead,developer,reviewer,qa,marketing}.md   # Claude subagents
  config/models.yaml
  .claude-plugin/{plugin.json, marketplace.json}
  AGENTS.md
  scripts/{validate.py, codex_profiles.py, install.sh}
  tests/{test_validate.py, test_codex_profiles.py, test_install.sh, fixtures/}
  docs/superpowers/{specs,plans}/   # this spec + plan
  README.md, NOTICE, LICENSE, requirements-dev.txt
```

---

### Task 1: Repo scaffold, models config and validator

**Files:**
- Create: `README.md` (install + usage stub), `LICENSE` (MIT), `NOTICE`, `requirements-dev.txt` (`pyyaml`, `pytest`), `config/models.yaml`, `scripts/validate.py`, `tests/test_validate.py`, `tests/fixtures/` (good and bad skill trees)
- Copy: the spec and this plan into `docs/superpowers/`

**Interfaces:**
- Produces: `validate_repo(root: Path) -> list[str]`, which returns error strings (an empty list means valid). CLI: `python scripts/validate.py [root]` exits 0 or 1 and prints the errors.
- Produces: `load_models(path: Path) -> dict[str, dict[str, str]]` (tool → tier → model id).
- Produces the frontmatter contract every later task follows:
  ```yaml
  name: <folder>
  description: <one line, starts with "Use when">
  metadata:
    kind: role | workflow | guideline
    tier: <tier>              # roles only
    allowed-tiers: [<tier>…]  # roles only
  ```

`models.yaml` shape: top-level `tools:` with keys `claude`, `codex`, `gemini`, each mapping `deep`/`standard`/`fast` to a model id. Claude uses `opus`/`sonnet`/`haiku`. For Codex and Gemini, look up the current model ids at build time, put them in, and add a dated comment.

- [ ] **Step 1: Write failing tests** in `tests/test_validate.py`:
  - `test_valid_fixture_passes`: `validate_repo(fixtures/good) == []`
  - `test_name_must_match_folder`: an error containing `"name 'x' != folder 'y'"`
  - `test_non_portable_frontmatter_rejected`: a `model:` key gives an error containing `"non-portable field 'model'"`
  - `test_role_tier_must_be_allowed`: tier `deep` with allowed `[fast]` gives an error containing `"tier 'deep' not in allowed-tiers"`
  - `test_unknown_tier_rejected`: tier `ultra` gives an error containing `"unknown tier 'ultra'"`
  - `test_models_yaml_missing_tier`: codex without `fast` gives an error `"models.yaml: tool 'codex' missing tier 'fast'"`
  - `test_role_needs_sections`: a role SKILL.md without the headings `## Reads`, `## Writes`, `## Never` gives one error per missing heading
  - `test_role_length_limit`: a role SKILL.md over 150 lines gives an error containing `"exceeds 150 lines"`
- [ ] **Step 2: Run** `pytest tests/test_validate.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `scripts/validate.py` (PyYAML `safe_load` on the frontmatter between the first two `---` lines; allowed top-level keys `{name, description, license, metadata}`).
- [ ] **Step 4: Run** `pytest -v`. Expected: PASS. Then run `python scripts/validate.py .`, expected exit 0 (no skills yet; `models.yaml` is valid).
- [ ] **Step 5: Commit** `feat: scaffold repo, models config and validator`

---

### Task 2: Engineering guidelines skill + AGENTS.md

**Files:**
- Create: `skills/engineering-guidelines/SKILL.md` (kind `guideline`), `AGENTS.md`
- Modify: `tests/test_validate.py`

Content: the Karpathy four rules (Think before coding · Simplicity first · Surgical changes · Goal-driven execution) and the ponytail YAGNI ladder (reuse existing code → stdlib/native platform → small new code → new dependency only with a reason in `plan.md`), plus "evidence before claiming done". Everything is in our own words. `AGENTS.md` = a short repo description + the same rules + "skills live in `skills/`".

- [ ] **Step 1: Failing test** `test_guidelines_have_rules`: the SKILL.md contains the headings `Think before coding`, `Simplicity first`, `Surgical changes`, `Goal-driven execution`, `YAGNI ladder`, and `AGENTS.md` contains the same four rule names.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write both files** (≤ 80 lines each).
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS, exit 0.
- [ ] **Step 5: Commit** `feat: add shared engineering guidelines`

---

### Task 3: team-init skill and project template

**Files:**
- Create: `skills/team-init/SKILL.md` (kind `workflow`), `references/project-template.md`, `references/claude-settings.json`, `references/codex-project.toml`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Produces: the `project.md` section headings that every role reads: `## Product`, `## Users`, `## Domain`, `## Stack`, `## Build & test`, `## Conventions`, `## Positioning & voice`, `## Channels`, `## Model overrides`.
- Produces: the permission allowlist. Claude `permissions.allow`: `Edit`, `Write`, `Bash(git add:*)`, `Bash(git commit:*)`, `Bash(git push origin feature/*)`, `Bash(git worktree:*)`, `Bash(gh pr create:*)`, plus a `{{TEST_COMMANDS}}` placeholder that team-init fills from `## Build & test`. Codex: the matching sandbox and approval settings for this project.

The skill's steps: check this is a git repo → create `.agent-team/` → read the codebase (README, manifests, test config) and draft `project.md` (≤ 60 lines) → merge the allowlist into `.claude/settings.json` without dropping existing keys → write the Codex project settings → commit `chore: init agent-team` on `main` → tell Adi to review `project.md` once.

- [ ] **Step 1: Failing tests:**
  - `test_project_template_headings`: all nine headings are present
  - `test_claude_settings_valid_json`: it parses, and `permissions.allow` contains `Bash(gh pr create:*)` and `Bash(git push origin feature/*)`
  - `test_codex_project_toml_parses` (`tomllib`)
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write the skill and references.**
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add team-init and project template`

---

### Task 4: PM role

**Files:**
- Create: `skills/pm/SKILL.md` (role, tier `deep`, allowed `[deep]`), `references/ideation-modes.md`, `references/ideas-template.md`, `references/spec-template.md`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Reads: `project.md`, the code (for ideation), optional feedback notes.
- Writes: `ideas.md` (ideation) and `features/<slug>/spec.md` (spec mode).
- Produces the spec format that Tech Lead and QA consume: headings `## Problem`, `## Users affected`, `## Proposal`, `## Out of scope`, `## Acceptance criteria` (numbered `AC1`, `AC2`, …, each testable), `## Success signal`.
- Produces the ideas entry format: `### <slug> — <title>`, with lines for value, effort (S/M/L), risk and mode.

Ideation modes (gstack-inspired): `expand` (find the bigger product inside it), `hold` (polish what exists), `reduce` (cut scope or complexity). Default `hold` unless Adi names a mode. At most 5 ideas per run. Never says it will implement anything.

- [ ] **Step 1: Failing tests:** `test_spec_template_has_numbered_ac` (the template contains `## Acceptance criteria` and `AC1`); `test_ideation_modes_listed` (`expand`, `hold`, `reduce`); the validator passes on `skills/pm`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write the files.**
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add PM role`

---

### Task 5: Tech Lead role

**Files:**
- Create: `skills/tech-lead/SKILL.md` (role, tier `deep`, allowed `[deep, standard]`), `references/plan-template.md`, `references/plan-checklist.md`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Reads: `project.md`, `spec.md`, the code it needs.
- Writes: `plan.md` with headings `## Approach`, `## Data flow`, `## Edge cases`, `## Test plan` (states the exact test command; if the project has no tests, how they'll be added and run), `## Tasks`. Each task line in `## Tasks` is `- [ ] T<n> [fast|standard] <title> — files: <paths> — maps to: AC<k>`.
- The checklist (gstack eng-review style): data flow, failure modes, migrations, security touchpoints, the YAGNI ladder applied, every AC mapped to at least one task.

- [ ] **Step 1: Failing tests:** `test_plan_template_task_format` (the template contains a sample line matching the regex `- \[ \] T\d+ \[(fast|standard)\] .+ — files: .+ — maps to: AC\d+`); `test_plan_template_has_test_plan_heading`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write the files.**
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add tech lead role`

---

### Task 6: Developer, Reviewer and QA roles

**Files:**
- Create: `skills/developer/SKILL.md` (tier `fast`, allowed `[fast, standard]`); `skills/reviewer/SKILL.md` (tier `standard`, allowed `[deep, standard]`), `references/review-template.md`; `skills/qa/SKILL.md` (tier `fast`, allowed `[fast, standard]`), `references/qa-template.md`, `references/test-by-platform.md`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Developer reads `project.md`, `plan.md`, the files the plan names, and the latest `review-N.md`/`qa-N.md` when fixing. It writes code, tests and commits on `feature/<slug>`. It works task by task with TDD, ticks the task boxes in `plan.md`, and follows `engineering-guidelines`. It reports a task's failure count so the workflow can escalate.
- Reviewer reads `spec.md`, `plan.md` and `git diff main...feature/<slug>` (in later rounds, only files changed since the last review). It writes `review-N.md` with headings `## Pass 1 — Spec compliance`, `## Pass 2 — Plan & code quality`, `## Pass 3 — Simplicity`, `## Verdict` (`APPROVED` or `CHANGES REQUESTED`) and numbered findings `R<n>`, each with file:line.
- QA reads `spec.md` (ACs), `project.md` `## Build & test` and the feature branch. It writes `qa-N.md` with a table `| AC | Method | Result (PASS/FAIL) | Evidence |`, `## Bugs` (numbered `Q<n>` with repro steps) and `## Verdict` (`PASSED` or `FAILED`). It may commit acceptance tests only under the project's test directory.
- `test-by-platform.md`: web → Playwright or browser tool if available; Flutter → `flutter test` + `integration_test` on an emulator if available, otherwise widget tests; backend/API → real requests against a local run; when no way to exercise the feature exists, mark the AC `UNVERIFIED` with the reason (this counts as FAIL unless the plan says manual).

- [ ] **Step 1: Failing tests:** `test_review_template_three_passes` (all four headings); `test_qa_template_columns` (the table header and `UNVERIFIED` mentioned in `test-by-platform.md`); `test_reviewer_never_edits` (the reviewer SKILL.md's `## Never` section contains "edit"); `test_qa_never_changes_feature_code`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write the files.**
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add developer, reviewer and QA roles`

---

### Task 7: team-build workflow, status file and dispatch

**Files:**
- Create: `skills/team-build/SKILL.md` (kind `workflow`), `references/status-template.md`, `references/dispatch-claude.md`, `references/dispatch-codex.md`, `references/dispatch-gemini.md`, `references/dispatch-generic.md`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Consumes: every role skill's Reads/Writes (Tasks 4–6), the plan task format (Task 5), the review/QA verdict strings (Task 6), and `models.yaml` (Task 1).
- `status.md` format: front block `stage:`, `branch:`, `review_round:`, `qa_round:`, `worktree:`, then `## Log` with lines `YYYY-MM-DD HH:MM <stage> <role> tier=<tier> model=<model> <note>`.

The workflow, in order: (1) the input is an idea slug from `ideas.md`, or an existing slug to resume; (2) if resuming, it fetches `feature/<slug>`. If the branch doesn't exist on the remote, or `status.md` is missing, it stops and says which one. Otherwise it continues from `stage`; (3) new runs create a worktree for `feature/<slug>` off `main` and never touch the current checkout; (4) PM spec → Tech Lead plan → Developer per task (tier from the task tag; escalate after the same task fails twice) → Reviewer (tier `standard`, or `deep` per the Global Constraints thresholds, measured with `git diff --shortstat`) → loop ≤ 3 → QA (`fast`, or `standard` if any AC needs UI/exploratory) → on QA FAIL: Developer fix → Reviewer on changed files → QA, ≤ 2 QA rounds → `gh pr create` with links to the artifacts; (5) stop conditions from the spec give `gh pr create --draft` and a note for Adi; (6) push the branch and update `status.md` after every stage.

Dispatch references: Claude → run each role as the matching subagent in `agents/` (the model comes from the subagent file; the escalated tier passes a `model` override). Codex → `codex exec --profile at-<tier> "<role prompt: load skill X, inputs …>"` per role. Gemini → `gemini -m <model> -p "<role prompt>"`. Generic → run in the current session, and log `model=session intended=<tier>`. When a tool or tier is missing from `models.yaml`, use the generic dispatch and log `fallback`. Tier lookup order: `project.md` `## Model overrides` → `models.yaml`. The Tech Lead runs at `standard` when `spec.md` has ≤ 2 ACs and the PM marks effort `S`; otherwise `deep`.

- [ ] **Step 1: Failing tests:** `test_status_template_fields` (all front-block keys + `## Log`); `test_team_build_mentions_safeguards` (the SKILL.md contains `worktree`, `--draft`, `status.md is missing`, `review rounds`, `QA rounds`, `fallback`); `test_dispatch_refs_exist` (all four files are present and each names its command: `Task`/subagent, `codex exec --profile`, `gemini -m`, `intended=`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write the files** (SKILL.md ≤ 150 lines; detail goes in the references).
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add team-build workflow with tiered dispatch`

---

### Task 8: Marketing role, team-ideate and team-market workflows

**Files:**
- Create: `skills/marketing/SKILL.md` (tier `standard`, allowed `[deep, standard]`), `references/{launch-copy.md, release-notes.md, social-posts.md, marketing-template.md}`; `skills/team-ideate/SKILL.md`; `skills/team-market/SKILL.md`
- Modify: `tests/test_validate.py`

**Interfaces:**
- Marketing reads `project.md` (especially `## Positioning & voice` and `## Channels`, read first), `spec.md` and the merged diff summary. It writes `marketing.md` with headings `## Release notes`, `## Announcement`, `## Social posts` (one subsection per channel listed in `project.md`) and `## Landing page changes`. It produces drafts only and never posts anything.
- team-ideate: dispatches PM (deep) in ideation mode, commits `ideas.md` to `main` as `docs: update ideas`, then shows Adi the list and says "pick one and run team-build <slug>" (Gate 1).
- team-market `<slug>`: checks that `status.md` stage is `merged` (or that the PR is merged, via `gh pr view`). If not, it stops. Tier is `standard`, or `deep` when the spec is marked as a launch or a new product. It sets the stage to `marketed`.

- [ ] **Step 1: Failing tests:** `test_marketing_template_headings`; `test_marketing_never_posts` (`## Never` mentions posting/publishing); `test_team_market_requires_merged` (the SKILL.md contains `merged` and `gh pr view`); `test_team_ideate_gate1` (it contains `team-build`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Write the files.**
- [ ] **Step 4: Run** `pytest -v && python scripts/validate.py .`. Expected: PASS.
- [ ] **Step 5: Commit** `feat: add marketing role, team-ideate and team-market`

---

### Task 9: Tool adapters and installer

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `agents/{pm,tech-lead,developer,reviewer,qa,marketing}.md`, `scripts/codex_profiles.py`, `scripts/install.sh`, `tests/test_codex_profiles.py`, `tests/test_install.sh`
- Modify: `scripts/validate.py`, `tests/test_validate.py`

**Interfaces:**
- Consumes: `load_models()` (Task 1) and each role's `metadata.tier` (Tasks 4–8).
- Produces: `render_profiles(models: dict) -> str`, which returns a TOML block with `[profiles.at-deep]`, `[profiles.at-standard]` and `[profiles.at-fast]` (each `model = "<id>"`), wrapped in the marker lines `# >>> agent-team profiles >>>` and `# <<< agent-team profiles <<<`.
- Produces: `merge_into_config(existing: str, block: str) -> str`, which replaces the text between the markers if present and appends otherwise. Everything outside the markers stays byte-for-byte the same.
- Claude subagent files: frontmatter `name`, `description`, and `model` = the role's default tier mapped through `models.yaml` `claude`. The body is one line: "Load and follow the `<role>` skill; inputs are given in the prompt."
- `install.sh [--dry-run]`: symlinks every `skills/*` into `~/.claude/skills/` and `~/.agents/skills/` (override with the env vars `CLAUDE_SKILLS_DIR` and `AGENTS_SKILLS_DIR`). Then it runs `codex_profiles.py` against `${CODEX_HOME:-~/.codex}/config.toml`. If a target is already a symlink to us, it skips it. If a real directory with the same name exists, it warns and skips. It prints the Claude plugin alternative (`/plugin marketplace add <owner>/agent-team`) and `npx skills add <owner>/agent-team`.
- Codex plugin manifest: check the current Codex plugin format in its docs at build time and add the manifest if a stable format exists. If not, record in the README that Codex installs via `install.sh` or `npx skills`.

- [ ] **Step 1: Failing tests:**
  - `test_render_profiles_has_three`; `test_merge_appends_when_absent`; `test_merge_replaces_between_markers`; `test_merge_preserves_user_content` (user lines before and after are kept, and running twice gives an identical result)
  - `test_agents_model_matches_tier` (validator: `agents/developer.md` has `model: haiku`, and so on for every role)
  - `tests/test_install.sh`: run with temp `HOME`/env dirs twice → each skill link exists once; a pre-existing `config.toml` line `model = "user-choice"` survives
- [ ] **Step 2: Run** `pytest -v && bash tests/test_install.sh`. Expected: FAIL.
- [ ] **Step 3: Implement** the scripts and write the manifests and agent files (look up the current `.claude-plugin` schema in the Claude Code docs).
- [ ] **Step 4: Run** `pytest -v && bash tests/test_install.sh && python scripts/validate.py .`. Expected: all PASS.
- [ ] **Step 5: Commit** `feat: add Claude/Codex adapters and installer`

---

### Task 10: README and NOTICE

**Files:**
- Modify: `README.md`, `NOTICE`

The README covers what it is, the flow diagram (from spec §6.4), install per tool, the first run (`team-init` → `team-ideate` → pick → `team-build <slug>` → merge → `team-market <slug>`), editing `models.yaml`, and adding a role (folder + `metadata` + a reference from a workflow + an `agents/` file + run the validator). NOTICE credits obra/superpowers, garrytan/gstack, bmad-code-org/BMAD-METHOD, multica-ai/andrej-karpathy-skills, DietrichGebert/ponytail and coreyhaines31/marketingskills (all MIT), plus the Agent Skills standard.

- [ ] **Step 1: Failing test** `test_notice_credits_sources`: NOTICE names all six repos.
- [ ] **Step 2: Run, expect FAIL.** **Step 3: Write.** **Step 4: Run** `pytest -v`. Expected: PASS.
- [ ] **Step 5: Commit** `docs: README and NOTICE`

---

### Task 11: End-to-end trial on a sample product

**Files:**
- Create: `tests/e2e/README.md` (the scenario script and results)

This is a manual verification. Do it in a throwaway clone of a small sample repo (a tiny Flutter or Node app with one test) using Claude Code, then repeat the build stage in Codex.

- [ ] **Step 1:** `install.sh`, then `/team-init`. Expected: `.agent-team/project.md` ≤ 60 lines, settings written, commit on `main`.
- [ ] **Step 2:** `team-ideate`. Expected: ≤ 5 ideas in `ideas.md`, each with a slug; PM ran on Opus (check the log/subagent).
- [ ] **Step 3:** `team-build <slug>` with a working tree that has an uncommitted edit. Expected: the edit is untouched; a worktree is created; `spec.md` has `AC1…`; plan tasks are tagged; the developer subagent is on Haiku; `review-1.md` has all three passes; `qa-1.md` has the AC table; a PR opens with links; `status.md` log lines show tier and model.
- [ ] **Step 4: Resume:** interrupt during review, then run `team-build <slug>` on a second clone (or in Codex). Expected: it resumes at `review`. Delete `status.md` on a scratch branch and retry. Expected: it stops with "status.md is missing".
- [ ] **Step 5: No-tests repo:** repeat Step 3 on a repo without tests. Expected: `plan.md` `## Test plan` says how tests are added, and the developer adds them.
- [ ] **Step 6:** Merge, then `team-market <slug>`. Expected: `marketing.md` with all four headings, nothing posted, stage `marketed`.
- [ ] **Step 7:** Record the results and any fixes in `tests/e2e/README.md`, then commit `test: record e2e trial`.
