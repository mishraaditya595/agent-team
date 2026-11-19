# Repo agent rules + multi-repo workspaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Roles read the repo's own `AGENTS.md`/`CLAUDE.md` via `agent-team rules` (#11), and agent-team runs a cross-repo feature from a workspace repo with nested product repos (#8 Parts 2–3), in one PR.

**Architecture:** All deterministic logic goes into the single stdlib file `skills/team-build/scripts/agent_team.py`. Workspace mode is on iff `project.md` `## Repos` has ≥ 1 `### <path>` block; every workspace code path branches on `repos()`/the status `repos` key being non-empty, so single-repo behaviour stays byte-identical. Role and workflow behaviour changes are SKILL.md / template text.

**Tech Stack:** Python 3 stdlib, git, gh (stubbed in tests), pytest.

**Spec:** `docs/superpowers/specs/2026-11-19-agent-rules-design.md` and `docs/superpowers/specs/2026-11-18-multi-repo-workspaces-design.md` (Parts 2–3). Read both.

## Global Constraints

- `agent_team.py` stays stdlib-only (PyYAML optional), single file.
- `skills/**/SKILL.md`: portable frontmatter only (no `model:`).
- A project whose `project.md` has no `## Repos` `### ` block: every command's output and side effects unchanged. Existing tests pass without edits.
- Lease, stage machine, stop rules and the two owner gates unchanged.
- No agent-team file is ever written into a product repo.
- Never force-push; never push to a default branch.
- Rules file names: exactly `AGENTS.md` and `CLAUDE.md`.
- `python3 -m pytest -q` and `python3 scripts/validate.py .` pass after every task.

## Review Focus

- `## Repos` present but holding only `none`/comments (no `### `) → single-repo mode, no error. Test in Task 3.
- A `### <path>` that isn't a git repo, or isn't gitignored by the workspace → one-line `Fail`, never a traceback or a product worktree created. Test in Task 6.
- `last_reviewed_commit` is a plain SHA (feature started before workspace mode) or lacks an entry for a repo added later → that repo diffs against its base branch, no crash. Test in Task 7.
- `rules` given a path outside the root (`../x`, absolute) → `Fail`, not a walk of the filesystem above the root. Test in Task 1.
- Product PR exists but workspace PR doesn't yet (stopped mid-pr stage) → `ci` and `cleanup` still work on what exists. Test in Task 9/10.

---

### Task 1: `agent-team rules`

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (new section `# ---------- agent rules ----------` after `# ---------- diff ----------`; parser entry)
- Test: `tests/test_rules.py`

**Interfaces:**
- Produces:
  - `RULES_FILES = ("AGENTS.md", "CLAUDE.md")`
  - `rules_root() -> Path`: nearest ancestor of `Path.cwd()` (inclusive) containing `.agent-team/`; falls back to `repo_root()`.
  - `rule_files(root: Path, paths: list[str], fallback: Path | None = None) -> list[str]`: root-relative POSIX paths, root-most first, deduped by `os.path.realpath`; include-only `CLAUDE.md` (every non-blank line `@<path>` naming a file already listed) dropped. `fallback`: a folder missing under `root` is looked up at the same relative path under `fallback` (printed path stays root-relative). Raises `Fail` for a path that is absolute or resolves outside `root`.
  - `feature_paths(slug) -> list[str]`: diff file names (Task 7 extends to workspace) + `plan_files()` of plan.md if present.
  - `cmd_rules(a)`; parser: `rules [targets…]` — a single target equal to an existing feature dir slug (`feature_dir(work_dir(t), t)` exists) means slug mode, else paths.
  - No targets: `rule_files(root, ["."])` plus (Task 3 adds) each `## Repos` path's top-level files.

- [ ] **Step 1: Write failing tests** in `tests/test_rules.py` using the `repo` fixture from `test_agent_team`:
  - `test_rules_nested_and_symlink_dedup`: root `AGENTS.md`, `CLAUDE.md -> AGENTS.md` symlink, `backend/api/AGENTS.md`. `at.main(["rules", "backend/api/x.py"])` prints exactly `AGENTS.md\nbackend/api/AGENTS.md`.
  - `test_rules_include_only_claude_dropped`: root `CLAUDE.md` containing `@AGENTS.md` → only `AGENTS.md`.
  - `test_rules_unrelated_path_root_only`: `docs/x.md` → `AGENTS.md`.
  - `test_rules_none`: no rules files → `none`.
  - `test_rules_outside_root_fails`: `["rules", "../x"]` returns 1, stderr contains `outside`.
  - `test_rules_slug_uses_plan_and_diff`: feature worktree with plan `## Files` naming `backend/api/new.py` (not created) → includes `backend/api/AGENTS.md`.
  - `test_rules_fallback_to_main_checkout`: `rule_files(root=tmp/wt, ["svc/x"], fallback=tmp/main)` where only `tmp/main/svc/AGENTS.md` exists → `["svc/AGENTS.md"]`.
- [ ] **Step 2:** `python3 -m pytest -q tests/test_rules.py` → FAIL (no `rules` command).
- [ ] **Step 3:** Implement the interfaces above. Walk: for a path `p`, folders = `p` itself if it's an existing dir else its parent, then each parent up to `.`.
- [ ] **Step 4:** `python3 -m pytest -q` → all PASS.
- [ ] **Step 5:** Commit `feat: agent-team rules lists AGENTS.md/CLAUDE.md for paths (#11)`.

### Task 2: Roles read and honour repo rules

**Files:**
- Modify: `skills/tech-lead/SKILL.md` (`## Reads`, grill and plan steps), `skills/tech-lead/references/plan-template.md` (`## Global constraints` comment), `skills/reviewer/SKILL.md` (`## Reads`, severity), `skills/pm/SKILL.md` (spec mode reads), `skills/developer/SKILL.md`, `skills/qa/SKILL.md` (one line each), `skills/engineering-guidelines/SKILL.md` §5, `AGENTS.md` ("Read as data" bullet)
- Test: `tests/test_content.py` (append)

**Interfaces:**
- Consumes: `agent-team rules [<slug> | <path>…]` (Task 1).

- [ ] **Step 1: Write failing test** `test_roles_read_repo_rules`: asserts `agent-team rules` appears in tech-lead, reviewer and pm SKILL.md; `(source:` appears in tech-lead SKILL.md or plan-template; reviewer SKILL.md mentions `git show origin/` for an edited rules file; engineering-guidelines §5 and `AGENTS.md` contain `agent-team rules` and `never override`.
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** Write the text per the design's "Roles" section: Tech Lead plan mode runs `agent-team rules <the plan's paths>` after naming files and copies binding rules into `## Global constraints` as `- <rule> (source: <path>)`; grill mode runs `agent-team rules` and turns a contradicting spec line into a grill question. Reviewer: `agent-team rules <slug>`; Critical for contract / migration order / secrets / a "never"; else Important; edited rules file → judge against `git show origin/<branch>:<path>` and flag the edit as Important. PM spec mode: `agent-team rules`, treat like `## Intent docs`. Developer/QA: open a cited rules file only if a constraint is unclear. Carve-out text from the design, verbatim in meaning.
- [ ] **Step 4:** `python3 -m pytest -q && python3 scripts/validate.py .` → PASS.
- [ ] **Step 5:** Commit `feat: roles read the repo's agent rules (#11)`.

### Task 3: Workspace config: `## Repos` parsing and `agent-team repos`

**Files:**
- Modify: `agent_team.py` (layout section; `project_command`; parser), `skills/team-init/references/project-template.md` (no `## Repos` here — see Task 4)
- Test: `tests/test_workspace.py` (new; holds a `workspace` fixture used by Tasks 3–10)

**Interfaces:**
- Produces:
  - `block_command(block: str, name: str) -> str | None` — the old body of `project_command` minus the `section()` call; `project_command(name, text=None)` becomes `block_command(section(text or project_md(), "Build & test"), name)`.
  - `repos(text: str | None = None) -> list[dict]` with keys `path` (str, no trailing `/`), `role` (str or `""`), `branch` (str or `None`), `block` (str, comments stripped). Ordered by `## Cross-repo rules` `Order:` (comma-separated) then listing order. `[]` when no `### ` block.
  - `repo_branch(r: dict) -> str`: `r["branch"]` or `default_branch(repo_root() / r["path"])`.
  - `cmd_repos(a)`: no slug → one line per repo `<path> <branch> <last commit %h %s>`; `Fail` naming the path if `repo_root()/path` isn't a git top-level. Single-repo → prints `single-repo`. Task 6 adds `<slug> --ensure`.
  - `rules` no-arg form (Task 1) adds each repo's top-level rules files.
- `workspace` fixture: bare remote + clone for the workspace (as `repo`), plus two product repos `api` and `app` each with its own bare remote, cloned into `work/api`, `work/app`, both listed in workspace `.gitignore`; `project.md` with `## Repos` (`### api` Test `true`, `### app` Test `true`) listed `app` then `api`, and `## Cross-repo rules` `- Order: api, app` (so order differs from listing).

- [ ] **Step 1: Write failing tests:** `test_repos_parsed_and_ordered` (Order reverses listing → order follows Order), `test_repos_none_section_is_single_repo` (`## Repos\nnone` → `[]`, `repos` prints `single-repo`), `test_block_command_matches_project_command` (existing PROJECT text gives same Test), `test_repos_cmd_lists_and_rejects_non_repo` (a `### missing` block → exit 1, stderr names `missing`), `test_rules_noarg_includes_repo_roots` (`api/AGENTS.md` listed).
- [ ] **Step 2:** run → FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** full suite PASS.
- [ ] **Step 5:** Commit `feat: parse ## Repos and add agent-team repos (#8)`.

### Task 4: team-init / upgrade detect nested repos

**Files:**
- Modify: `agent_team.py` (`cmd_upgrade`, `merged_allow`), `skills/team-init/SKILL.md` (step 3, upgrade step 4), `skills/team-init/references/project-template.md` (commented note only; no `## Repos` heading)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `nested_repos(root: Path) -> list[str]`: depth-1 dirs `d` where `git -C d rev-parse --show-toplevel` == `d` and `git check-ignore -q d` succeeds in `root`; sorted.
  - `WORKSPACE_SECTIONS(paths) -> str`: the `## Repos` block (`### <path>` + `- Role: unknown — owner to fill` + `- Test: \`none\`` …) and `## Cross-repo rules` (`- Order: <paths, comma-separated>` + `unknown — owner to fill`).
  - `cmd_upgrade`: when `## Repos` missing and `nested_repos()` non-empty, appends those two sections and reports `project.md: added sections Repos, Cross-repo rules`. Never adds them otherwise.
  - `merged_allow(existing, project_text)`: also adds `Bash(<cmd>:*)` for every repo block's Install/Build/Test.

- [ ] **Step 1: Write failing tests:** `test_upgrade_adds_repos_only_when_nested` (single-repo `repo` fixture: upgrade output has no `Repos`; workspace fixture with `## Repos` removed: adds both sections listing `api`, `app`), `test_upgrade_ignores_unignored_nested_repo`, `test_merged_allow_includes_repo_commands`.
- [ ] **Step 2–4:** fail, implement, full suite PASS. team-init SKILL step 3: detect with `agent-team repos`-style rule (depth-1, gitignored), draft `## Repos` from each repo's manifests, `## Cross-repo rules` `unknown — owner to fill`; budget ≤ 60 + 8 per repo; ensure each repo path is in `.gitignore`.
- [ ] **Step 5:** Commit `feat: team-init/upgrade draft ## Repos for nested repos (#8)`.

### Task 5: Ideation in a workspace

**Files:**
- Modify: `agent_team.py` (`idea_info`), `skills/pm/SKILL.md` (ideation + intake), `skills/pm/references/ideas-template.md`, `skills/team-ideate/SKILL.md` if it names `git log`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Produces: `idea_info(slug)` adds `"repos": list[str]` parsed from `- **Repos:** a, b` (`[]` if absent). `cmd_idea` prints `repos=<a,b>` only when non-empty (single-repo output unchanged).

- [ ] **Steps:** failing test `test_idea_repos_line` (+ existing `test_idea_lookup_and_set` unchanged), implement, PM text: in workspace mode evidence is `git -C <path> log --oneline -30` per repo plus each repo's README and main routes; `**Repos:**` required then. Commit `feat: workspace ideation labels ideas with repos (#8)`.

### Task 6: Product worktrees, status keys, lease

**Files:**
- Modify: `agent_team.py` (`STATUS_KEYS`, `cmd_repos --ensure`, `cmd_lease`), `skills/team-build/references/status-template.md` (no new lines; keys are added by `--ensure` via `write_status`, so single-repo status files stay identical)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `STATUS_KEYS` += `repos`, `repo_prs`.
  - `status_repos(slug) -> list[dict]`: `repos()` entries whose path is in status `repos` (space-separated), in `repos()` order; `[]` when key missing/`none`.
  - `product_wt(slug, path) -> Path`: `worktree(slug) / path`.
  - `cmd_repos` with `<slug> --ensure`: wanted = status repos ∪ idea `repos` ∪ repos that prefix any `plan_files()` entry, ∩ `repos()`; for each missing worktree: `git check-ignore -q <path>` in the workspace root must pass (else `Fail("<path> isn't gitignored by the workspace…")`); `git -C <root>/<path> fetch origin`; if `origin/feature/<slug>` exists → `worktree add <wt> feature/<slug>` tracking it, else `worktree add -b feature/<slug> <wt> origin/<repo_branch>` and push `-u`. Writes status `repos=<ordered paths>` (and `repo_prs=none` if unset). Prints `<path> <created|exists>` per repo.
  - `cmd_lease` acquire: after the workspace `_catch_up`, `_catch_up(product_wt, branch)` for each `status_repos` worktree that exists.

- [ ] **Steps:** failing tests `test_ensure_creates_product_worktrees_from_idea` (idea `**Repos:** api` → `wt/api` on `feature/<slug>`, `origin/feature/<slug>` exists in api's remote, status `repos: api`), `test_ensure_adds_plan_repos`, `test_ensure_reuses_remote_branch` (second clone path), `test_ensure_refuses_unignored_path`, `test_lease_catches_up_products` (diverged product branch → acquire fails with `diverged`), `test_single_repo_status_unchanged` (init-status output byte-equal to template). Implement. Commit `feat: product worktrees and repos status keys (#8)`.

### Task 7: `test`, `diff`, `heads`, `diff --since`, tier diffstat

**Files:**
- Modify: `agent_team.py` (`diff_args`, `diffstat`, `cmd_diff`, `cmd_test`, new `cmd_heads`, `feature_paths`)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `parse_since(since: str | None) -> dict[str, str]`: `"api:abc app:def"` → map; plain SHA → `{".": sha}`; `None`/`none` → `{}`.
  - `repo_diff(slug, r, since_map, extra: list[str]) -> str`: `git diff <extra> <rng> -- . <excludes>` in `product_wt`, `rng` = `<since_map[path]>..HEAD` if present else `origin/<repo_branch>...HEAD`; patch output uses `--src-prefix=a/<path>/ --dst-prefix=b/<path>/`; `--stat`/`--name-only` output has each line prefixed with `<path>/` (name-only) or preceded by a `# <path>` header (stat).
  - `cmd_diff` workspace: workspace diff (as today, `since_map.get(".")`) then each `status_repos` repo in order. `--shortstat` and `diffstat()` sum lines/files across all.
  - `cmd_heads(a)`: prints `<path>:<short HEAD>` for each status repo, space-separated; single-repo → workspace short HEAD (same as `git rev-parse --short HEAD`).
  - `cmd_test` workspace: key = `"+".join(code_key(wt), *code_key(product_wt))` (any `None` → no cache) + cmd hash over all commands; runs workspace Build/Test if configured, then each repo's (`block_command(r["block"], …)`) with `cwd=product_wt`; failure writes `fail(<path>:<step>)`.
  - `feature_paths(slug)` includes product diff names (prefixed).

- [ ] **Steps:** failing tests `test_ws_diff_prefixes_paths`, `test_ws_diff_since_per_repo_and_plain_sha` (plain SHA → product repos diff against base; missing repo key → base), `test_ws_shortstat_sums`, `test_ws_test_runs_each_repo_and_caches`, `test_ws_test_failure_names_repo`, `test_heads_format`, `test_rules_slug_reaches_product_and_workspace_rules`. Existing `test_diff_excludes_noise`, `test_test_cache_*` unchanged. Implement. Commit `feat: workspace-aware test, diff and heads (#8)`.

### Task 8: `sync` and `push`

**Files:** Modify `agent_team.py` (`cmd_sync`, `cmd_push`); Test `tests/test_workspace.py`

**Interfaces:**
- Produces: `cmd_sync` workspace: dirty check and merge per product worktree against `origin/<repo_branch>` first, then the workspace as today; conflict → `Fail("merge conflict with origin/<b> in <path>: <files>", code=2)`; prints one line per repo (`<path>: up to date with …` / `<path>: merged …`). `cmd_push`: each product branch then the workspace branch; rejection messages prefixed with `<path>: `; exit codes unchanged.

- [ ] **Steps:** failing tests `test_ws_sync_merges_each_repo`, `test_ws_sync_conflict_names_repo` (exit 2), `test_ws_push_pushes_products_then_workspace`, `test_ws_push_rejected_product_exit3`. Implement (factor the existing bodies into `_sync_one(wt, d, label)` / `_push_one(wt, branch, label)` with `label=""` reproducing today's text exactly). Commit `feat: workspace-aware sync and push (#8)`.

### Task 9: `ci`, `pr-body`, `summary`

**Files:** Modify `agent_team.py` (`cmd_ci`, `cmd_pr_body`, `cmd_summary`, parser `--repo`); Test `tests/test_workspace.py` (gh stubbed like `tests/test_docs_pr_only.py::gh_stub`)

**Interfaces:**
- Consumes: status `repo_prs` = `"api#12 app#40"` or `none`.
- Produces:
  - `parse_repo_prs(v: str) -> list[tuple[str, str]]`.
  - `cmd_ci`: checks each `(path, n)` with `gh pr checks n` in `product_wt`, then the workspace `pr` if not `none`; `--watch` per PR; `pass` only if all pass/none; `pending` if any pending and none failed; `fail` prints `<path>#<n>: <failing lines>`. No `pr` and no `repo_prs` → existing `Fail("no pr in status.md")`.
  - `cmd_pr_body --repo <path>`: `## Summary`, `## Artifacts` linking to the workspace PR (`<workspace github url>/pull/<pr>` or `the workspace PR` when `pr=none`) plus artifact links on the workspace branch, `Part of <slug>: <other PRs>`, `Merge order: api#12 → app#40 → workspace #<pr>`. Without `--repo` in workspace mode: today's body plus `## Product PRs` listing `repo_prs` in order.
  - `cmd_summary`: `pr` column = `repo_prs` + ` ws#<pr>` when `repo_prs` set.

- [ ] **Steps:** failing tests `test_ws_ci_all_pass`, `test_ws_ci_one_fails_names_repo`, `test_ws_ci_without_workspace_pr`, `test_pr_body_repo_merge_order`, `test_summary_shows_repo_prs`. Implement. Commit `feat: workspace-aware ci, pr-body and summary (#8)`.

### Task 10: `cleanup`, `drift`

**Files:** Modify `agent_team.py` (`cmd_cleanup`, `cmd_drift`); Test `tests/test_workspace.py`

**Interfaces:**
- Produces:
  - `_cleanup_one(root: Path, wt: Path, branch: str, pr: str, remote: bool) -> (problems: list[str], do: callable)` — today's checks and actions for one repo, with `root` the repo whose `.git` owns the worktree; problems prefixed with `<path>: ` in workspace mode.
  - `cmd_cleanup` workspace: collect problems for every product (root = `repo_root()/path`, pr from `repo_prs`) and the workspace; any problem and no `--force` → one `Fail` listing all, nothing removed; else remove products first, then workspace.
  - `cmd_drift`: when `status_repos(slug)` is non-empty → `drift: unchecked (workspace mode)`, exit 0.

- [ ] **Steps:** failing tests `test_ws_cleanup_removes_products_then_workspace`, `test_ws_cleanup_refuses_unpushed_product_commit` (nothing removed), `test_ws_drift_unchecked`. Existing `test_cleanup_*` unchanged. Implement. Commit `feat: workspace-aware cleanup; drift unchecked in workspaces (#8)`.

### Task 11: Workflow skills and docs

**Files:**
- Modify: `skills/team-build/SKILL.md` (steps 0, 1, 3.3–3.9 workspace notes), `skills/tech-lead/SKILL.md` (workspace plan rules), `skills/reviewer/SKILL.md` (`## Cross-repo rules`), `skills/developer/SKILL.md` (commit in the task's product worktree), `skills/team-wrap/SKILL.md` (all PRs merged; loop `gh pr view -R`), `skills/team-status/SKILL.md` if it describes the pr column, `README.md`, `docs/reference.md` (new commands `rules`, `repos`, `heads`, `pr-body --repo`), `tests/e2e/README.md` (rows: workspace build, rules finding)
- Test: `tests/test_content.py`

- [ ] **Step 1: Failing test** `test_workflow_skills_cover_workspace`: team-build mentions `agent-team repos <slug> --ensure`, `agent-team heads`, `pr-body <slug> --repo`; team-wrap mentions `repo_prs`; reviewer mentions `## Cross-repo rules`; tech-lead mentions `exactly one product repo`; reference.md lists `rules`, `repos`, `heads`.
- [ ] **Step 2–4:** fail; write the text per #8 design "team-build skill changes" and "team-wrap / team-status" (resume: re-add workspace worktree then `repos <slug> --ensure`; new run: `--ensure` after `init-status`; plan stage: `--ensure` after plan; review: `last_reviewed_commit=$(agent-team heads <slug>)` in both modes; pr: one `gh pr create` per status repo whose `git -C <wt>/<path> diff --quiet origin/<branch>...HEAD` reports changes, in `repos` order, `pr-body --repo`, set `repo_prs`, then workspace PR; stop: draft/undo-ready every PR that exists); suite + validate PASS.
- [ ] **Step 5:** Commit `docs: workspace mode and repo rules in workflow skills (#8, #11)`.

### Task 12: Final verification

- [ ] `python3 -m pytest -q` → all pass; `python3 scripts/validate.py .` → ok.
- [ ] `git diff main --stat` reviewed: no file outside the plan's lists.
- [ ] Commit any fixes.
