# Multi-repo workspaces (Parts 2 + 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run agent-team from a workspace repo holding nested, gitignored product repos: ideation cites each repo's history, and `team-build` builds a cross-repo feature in one run ending in one PR per touched repo plus a workspace PR.

**Architecture:** Workspace mode switches on from a `## Repos` section in `project.md`. The workspace worktree (`.agent-team/worktrees/<slug>`, branch `feature/<slug>`) keeps the artifacts, status and lease as today; each touched product repo gets its own worktree on `feature/<slug>` nested at `<wt>/<path>`. Helper commands loop over `status.md` `repos`; with `repos: none` every command runs exactly today's code path. All git in product repos goes through `agent-team` (permissions).

**Tech Stack:** Python 3 stdlib (`agent_team.py`, single file), git, `gh`, pytest; Markdown skills.

**Spec:** `docs/superpowers/specs/2026-11-18-multi-repo-workspaces-design.md` (Parts 2 and 3; Part 1 shipped in #9).

## Global Constraints

- `agent_team.py` stays stdlib-only, single file (PyYAML optional).
- No tool-specific frontmatter (`model:` etc.) in `skills/**/SKILL.md`; role SKILL.md ≤ 150 lines (`scripts/validate.py`).
- `status-template.md` keys == `STATUS_KEYS` (validate.py checks).
- No behaviour change for a project without `## Repos` (only inert `repos: none` / `repo_prs: none` lines in new `status.md`).
- Never `Bash(git -C:*)` or other broad allow entries; nested-repo git goes through `agent-team`.
- No agent-team files written into product repos.
- `python3 -m pytest -q` and `python3 scripts/validate.py .` pass before each commit.

## Review Focus

1. A product path the workspace does *not* gitignore → `repos --ensure` refuses with a message naming the path (else the workspace PR would commit a whole product checkout). Test in Task 4.
2. Resume on a second machine where `origin/feature/<slug>` already exists in a product repo → worktree tracks it, no new branch off `origin/<branch>`. Test in Task 4.
3. A product branch diverged from its origin during `lease acquire` → acquire fails like the workspace branch, lease not taken. Test in Task 5.
4. `commit` given a path outside every product repo (e.g. `docs/x.md`) → refused, nothing committed anywhere. Test in Task 5.
5. `ci` with one product PR failing and the workspace PR passing → overall `fail`, output names `<repo>#<n>`. Test in Task 7.

---

## Shared test fixture (defined in Task 1, reused by all later tasks)

`tests/test_workspace.py` fixture `ws(tmp_path, monkeypatch)`:
- bare remotes `remote.git` (workspace), `backend.git`, `app.git`, each `main`.
- `work/` = workspace clone (user/email/defaultBranch config as `test_agent_team.repo`), `.gitignore` = `.agent-team/worktrees/\n/app-backend/\n/app-flutter/\n`, `.agent-team/project.md` = `WS_PROJECT` below, `.agent-team/ideas.md` with idea `### both — Both` containing `- **Repos:** app-backend, app-flutter` and `**Effort:** S`; committed, pushed, `remote set-head origin main`.
- `work/app-backend` and `work/app-flutter` = clones of `backend.git` / `app.git`, each with one committed+pushed file (`api.txt` / `ui.txt`), `remote set-head origin main`.
- `monkeypatch.chdir(work)`, `AGENT_TEAM_HOST=box-a`. Returns `work`.

```python
WS_PROJECT = """# WS — project context

## Build & test
- Test: `none`

## Repos
### app-backend
- Role: API
- Test: `test -f api.txt`
### app-flutter
- Role: app
- Branch: main
- Test: `test -f ui.txt`

## Cross-repo rules
- Order: app-backend, app-flutter
- app-flutter: shipped builds keep working.

## Model overrides
none
"""
```

Helper `new_ws_feature(work, slug="both", ensure=True)`: workspace worktree via `git worktree add -b feature/<slug> .agent-team/worktrees/<slug> origin/main`, `agent-team init-status`, commit, push; then, if `ensure`, `assert at.main(["repos", slug, "--ensure"]) == 0`. Returns `wt`. (Defined in Task 4, where `--ensure` first exists.)

---

### Task 1: `## Repos` parsing and `agent-team repos`

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (next to `project_command`, ~line 296; parser in `build_parser`)
- Create: `tests/test_workspace.py` (fixture above + this task's tests)

**Interfaces:**
- Produces:
  - `block_command(name: str, body: str) -> str | None` — the `- <name>: \`cmd\`` lookup `project_command` does today, on any text; `project_command` calls it with `section(text, "Build & test")`.
  - `repos(text: str | None = None) -> list[dict]` — `text` defaults to `project_md()`. One dict per `### <path>` under `## Repos`: `{"path": str, "role": str, "branch": str | None, "body": str}`; ordered by `## Cross-repo rules` `- Order: a, b` first, then listing order; `[]` when no `## Repos` or no `###` block.
  - `repo_branch(r: dict) -> str` — `r["branch"]` or `default_branch(repo_root() / r["path"])`.
  - `gh_slug(cwd: Path) -> str` — `owner/repo` from `origin` URL (same regex as `github_blob_base`), `""` if not GitHub.
  - CLI `agent-team repos [--log]` — one line per repo `"<path> branch=<b> repo=<owner/repo or -> head=<short sha>"`; with `--log` each line is followed by that repo's `git log --oneline -30`; prints `single-repo (no ## Repos)` and exits 0 when `repos()` is empty. Fails (exit 1) naming the path if a listed path isn't a git toplevel.

- [ ] **Step 1: Write the failing tests** in `tests/test_workspace.py` (with the fixture):

```python
def test_repos_parsed_in_order_with_commands():
    rs = at.repos(WS_PROJECT)
    assert [r["path"] for r in rs] == ["app-backend", "app-flutter"]
    assert rs[1]["branch"] == "main" and rs[0]["branch"] is None and rs[0]["role"] == "API"
    assert at.block_command("Test", rs[0]["body"]) == "test -f api.txt"

def test_order_line_wins_over_listing_order():
    t = WS_PROJECT.replace("- Order: app-backend, app-flutter", "- Order: app-flutter, app-backend")
    assert [r["path"] for r in at.repos(t)] == ["app-flutter", "app-backend"]

def test_single_repo_has_no_repos():
    from test_agent_team import PROJECT
    assert at.repos(PROJECT.format(test="true", overrides="none")) == []
    assert at.project_command("Test", PROJECT.format(test="true", overrides="none")) == "true"

def test_repos_cli_lists_and_logs(ws, capsys):
    assert at.main(["repos", "--log"]) == 0
    out = capsys.readouterr().out
    assert "app-backend branch=main" in out and "app-flutter branch=main" in out
    assert out.count("init") >= 2      # each product's first commit message, from its own log

def test_repos_cli_fails_on_missing_repo(ws, capsys):
    import shutil; shutil.rmtree(ws / "app-flutter")
    assert at.main(["repos"]) == 1
    assert "app-flutter" in capsys.readouterr().err
```

(Product repos' first commit message in the fixture is `init`.)

- [ ] **Step 2: Run to verify they fail**
Run: `python3 -m pytest -q tests/test_workspace.py`
Expected: FAIL — `AttributeError: … 'repos'` / `'block_command'`.

- [ ] **Step 3: Implement** `block_command`, `repos`, `repo_branch`, `gh_slug`, `cmd_repos` and its parser entry (`repos`, `slug` optional positional — used by Task 4 — and `--log`). Split `section(text, "Repos")` on `^###\s+(\S+)\s*$`; `Role:`/`Branch:` read with `^\s*-\s*Role:\s*(.+)$`. Order line from `section(text, "Cross-repo rules")`.

- [ ] **Step 4: Run to verify they pass, then the full suite**
Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit** — `feat: parse ## Repos and add agent-team repos (#8)`

### Task 2: `team-init` / `upgrade` detect nested repos

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (`merged_allow`, `cmd_upgrade`, new `nested_repos`, `draft_repos_sections`)
- Modify: `skills/team-init/SKILL.md` (step 3, step 4, Upgrade step 4)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `repos`, `block_command` (Task 1).
- Produces:
  - `nested_repos(root: Path) -> list[str]` — sorted top-level dir names `d` where `git -C root/d rev-parse --show-toplevel` == `root/d` and `git -C root check-ignore -q d/` succeeds.
  - `draft_repos_sections(paths: list[str]) -> str` — exact text:
    `"## Repos\n" + "".join(f"### {p}\n- Role: unknown — owner to fill\n- Test: `none`\n" for p in paths) + "\n## Cross-repo rules\n- Order: " + ", ".join(paths) + "\n- unknown — owner to fill\n"`
  - `cmd_upgrade`: when `nested_repos(root)` is non-empty and `project.md` has no `## Repos`, appends `draft_repos_sections(...)` before `## Model overrides` (or at the end) and prints `project.md: added sections Repos, Cross-repo rules`. `project-template.md` gets no `## Repos` heading (spec: a commented one would still be added by `add_missing_sections`).
  - `merged_allow(existing, project_text)` also emits `Bash(<cmd>:*)` for every repo's Install/Build/Test.

- [ ] **Step 1: Write the failing tests**

```python
def test_upgrade_adds_repos_when_nested(ws, capsys):
    p = ws / ".agent-team" / "project.md"
    p.write_text(p.read_text().split("## Repos")[0] + "## Model overrides\nnone\n")
    sh("git", "commit", "-qam", "drop repos", cwd=ws)
    assert at.main(["upgrade"]) == 0
    text = p.read_text()
    assert "### app-backend\n" in text and "### app-flutter\n" in text
    assert "- Order: app-backend, app-flutter" in text
    assert text.index("## Repos") < text.index("## Model overrides")

def test_upgrade_single_repo_never_adds_repos(repo, capsys):   # repo fixture from test_agent_team
    at.main(["upgrade"])
    assert "## Repos" not in (repo / ".agent-team" / "project.md").read_text()

def test_unignored_nested_repo_not_detected(ws):
    (ws / ".gitignore").write_text(".agent-team/worktrees/\n/app-backend/\n")
    assert at.nested_repos(ws) == ["app-backend"]

def test_allow_list_covers_repo_commands():
    allow = at.merged_allow([], WS_PROJECT)
    assert "Bash(test -f api.txt:*)" in allow and "Bash(test -f ui.txt:*)" in allow
```

- [ ] **Step 2: Run to verify they fail**
Run: `python3 -m pytest -q tests/test_workspace.py -k "upgrade or nested or allow"`
Expected: FAIL (`nested_repos` missing; no `### app-backend` added).

- [ ] **Step 3: Implement** the four interfaces above.

- [ ] **Step 4: team-init text.** Step 3: "If top-level folders are their own git repos and gitignored here (a **workspace**), add `## Repos` (one `### <path>` per repo: `- Role:`, optional `- Branch:`, its `- Install/Build/Test:` from that repo's manifests/CI) and `## Cross-repo rules` (`- Order: …` earliest-shipping first, then `unknown — owner to fill`). Budget: ≤ 60 lines plus ≤ 8 per repo. Never write anything into the product repos." Step 4: settings get each repo's commands too (`agent-team upgrade` / `merged_allow` does this). Upgrade step 4: fill the drafted `### <path>` blocks the same way.

- [ ] **Step 5: Verify** — `python3 -m pytest -q && python3 scripts/validate.py .` → all pass, `OK`.

- [ ] **Step 6: Commit** — `feat: team-init/upgrade draft ## Repos for workspaces (#8)`

### Task 3: Ideation across repos

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (`idea_info`)
- Modify: `skills/pm/SKILL.md` (Reads: ideation and intake), `skills/pm/references/ideas-template.md`
- Test: `tests/test_workspace.py`, `tests/test_content.py`

**Interfaces:**
- Produces: `idea_info(slug)` dict gains `"repos": list[str]` from `- **Repos:** a, b` (split on `,`, stripped); `[]` if absent. `agent-team idea <slug>` output unchanged.

- [ ] **Step 1: Failing tests**

```python
def test_idea_info_repos(ws):
    assert at.idea_info("both")["repos"] == ["app-backend", "app-flutter"]

# tests/test_content.py
def test_pm_ideates_across_repos():
    pm = read("skills/pm/SKILL.md")
    assert "agent-team repos --log" in pm and "**Repos:**" in pm
    assert "**Repos:**" in read("skills/pm/references/ideas-template.md")
```

- [ ] **Step 2: Run** `python3 -m pytest -q tests/test_workspace.py::test_idea_info_repos tests/test_content.py::test_pm_ideates_across_repos` → FAIL (`KeyError: 'repos'`; text missing).

- [ ] **Step 3: Implement.** `idea_info`: regex `\*\*Repos:\*\*\s*(.+)`. PM Reads, ideation: "In a workspace (`project.md` has `## Repos`): run `agent-team repos --log` for each repo's recent history instead of `git log`, and skim each repo's README and main routes/screens; read `## Cross-repo rules`." Writes: "In a workspace every idea (ideation and intake) gets `- **Repos:** <paths it touches>`." Template: add the line `- **Repos:** <workspace only: repo paths it touches, in ship order>` after **Idea**.

- [ ] **Step 4: Verify** — `python3 -m pytest -q && python3 scripts/validate.py .` → pass, `OK`.

- [ ] **Step 5: Commit** — `feat: PM ideates across workspace repos (#8)`

### Task 4: Status keys and product worktrees (`repos <slug> --ensure`)

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (`STATUS_KEYS`, new helpers, `cmd_repos`, `cmd_drift`)
- Modify: `skills/team-build/references/status-template.md`
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `repos`, `repo_branch`, `idea_info()["repos"]`.
- Produces:
  - `STATUS_KEYS` += `"repos"`, `"repo_prs"`; template lines `repos: none   # workspace: touched product repos, in ship order` and `repo_prs: none   # workspace: "<path>#<n> …" product PRs` (after `pr:`).
  - `task_files(plan: str) -> list[str]` — paths from each `## Tasks` checkbox line's `files: a, b` segment (up to the next ` — `), backticks stripped.
  - `ws_repos(slug: str) -> list[dict]` — for each path in status `repos` (none → `[]`): the `repos()` dict plus `"wt": worktree(slug) / path`, `"src": repo_root() / path`.
  - `ensure_repo_worktrees(slug: str) -> list[str]` — touched = status `repos` ∪ idea `repos` ∪ repos that prefix any `task_files(plan.md)` path (plan if present), kept in `repos()` order; for each missing `<wt>/<path>`: refuse unless `git -C <wt> check-ignore -q <path>/` succeeds (`Fail: "<path> is not gitignored by the workspace; add /<path>/ to .gitignore"`); if `git ls-remote --heads origin feature/<slug>` in `src` is non-empty → `git fetch` + `worktree add --track -b feature/<slug> <wt>/<path> origin/feature/<slug>` (or without `-b` if the local branch exists); else `worktree add -b feature/<slug> <wt>/<path> origin/<repo_branch>` then `git push -u origin feature/<slug>`. Writes status `repos=<space-joined>`; returns the list.
  - CLI `agent-team repos <slug> --ensure` prints `repos: app-backend app-flutter`.
  - `cmd_drift`: in workspace mode prints `drift: unchecked (workspace mode)` and returns 0 (planned-at is one repo's sha; per-repo drift is out of scope).

- [ ] **Step 1: Failing tests**

```python
def test_ensure_creates_product_worktrees_and_pushes(ws, capsys):
    wt = new_ws_feature(ws)
    for p, f in (("app-backend", "api.txt"), ("app-flutter", "ui.txt")):
        assert (wt / p / f).exists()
        assert sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=wt / p) == "feature/both"
        assert sh("git", "ls-remote", "--heads", "origin", "feature/both", cwd=ws / p)
    assert at.read_status(wt / ".agent-team/features/both/status.md")["repos"] == "app-backend app-flutter"
    assert sh("git", "status", "--porcelain", cwd=wt) == ""          # nested checkouts are ignored

def test_ensure_resumes_from_pushed_product_branch(ws, tmp_path):
    wt = new_ws_feature(ws)
    (wt / "app-backend" / "new.txt").write_text("x")
    sh("git", "add", "-A", cwd=wt / "app-backend"); sh("git", "commit", "-qm", "work", cwd=wt / "app-backend")
    sh("git", "push", "-q", cwd=wt / "app-backend")
    at.main(["cleanup", "both", "--force"])                          # this machine forgets everything
    sh("git", "worktree", "add", "-q", str(wt), "feature/both", cwd=ws)
    assert at.main(["repos", "both", "--ensure"]) == 0
    assert (wt / "app-backend" / "new.txt").exists()

def test_ensure_refuses_unignored_repo(ws, capsys):
    (ws / ".gitignore").write_text(".agent-team/worktrees/\n/app-flutter/\n")
    sh("git", "commit", "-qam", "unignore", cwd=ws); sh("git", "push", "-q", cwd=ws)
    new_ws_feature(ws, ensure=False)
    assert at.main(["repos", "both", "--ensure"]) == 1
    assert "app-backend is not gitignored" in capsys.readouterr().err

def test_task_files_and_plan_adds_repo(ws):
    assert at.task_files("## Tasks\n- [ ] T1 [fast] x — files: `app-backend/a.py`, app-flutter/b — maps to: AC1\n") \
        == ["app-backend/a.py", "app-flutter/b"]

def test_drift_unchecked_in_workspace(ws, capsys):
    wt = new_ws_feature(ws)
    (wt / ".agent-team/features/both/plan.md").write_text("planned-at: abc1234\n## Files\n- `app-backend/a`\n")
    at.main(["drift", "both"])
    assert "drift: unchecked (workspace mode)" in capsys.readouterr().out
```


- [ ] **Step 2: Run** `python3 -m pytest -q tests/test_workspace.py -k "ensure or task_files or drift"` → FAIL (unknown command / key).

- [ ] **Step 3: Implement** the interfaces. Note the resume test depends on Task 7's cleanup for products; until then use `git worktree remove --force` on each product worktree in that test, and switch it to `cleanup` in Task 7.

- [ ] **Step 4: Verify** — `python3 -m pytest -q && python3 scripts/validate.py .` → pass, `OK` (validate checks the template/key match).

- [ ] **Step 5: Commit** — `feat: nested product worktrees for workspace features (#8)`

### Task 5: `commit`, `heads`, lease, `push`, `sync` across repos

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (`cmd_lease`, `cmd_push`, `cmd_sync`, new `cmd_commit`, `cmd_heads`)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `ws_repos(slug)` (Task 4).
- Produces:
  - CLI `agent-team commit <slug> -m <msg> <paths…>` — paths relative to the workspace worktree; each must start with `<path>/` of a `ws_repos` entry, else `Fail("<p> is not inside a product repo of <slug>")` before anything is staged. Per repo (ws order): `git add -- <rel paths>` + `git commit -q -m <msg>` in its `wt`; prints `committed <path> <short sha>` per repo. Fails in single-repo mode: `"commit is for workspace features; use git commit"`.
  - CLI `agent-team heads <slug>` — workspace: `app-backend:<short> app-flutter:<short>` (ws order); single-repo: the worktree's short `HEAD`.
  - `parse_since(since: str | None) -> dict[str, str] | str | None` — `"a:x b:y"` → `{"a": "x", "b": "y"}`; plain sha → sha.
  - `cmd_lease`: after the workspace `_catch_up`, `_catch_up(r["wt"], branch)` for each `ws_repos` entry whose `wt` exists (divergence → same `Fail`, before the lease commit).
  - `cmd_push`: pushes each product branch first, then the workspace branch, same messages and exit codes, product messages prefixed `<path>: `.
  - `cmd_sync`: workspace merges `origin/<d>` as today; each product merges `origin/<repo_branch>`; conflict `Fail(..., code=2)` message starts `<path>: merge conflict with origin/<branch> in: …`; prints one `up to date` / `merged` line per repo.

- [ ] **Step 1: Failing tests**

```python
def test_commit_routes_paths_to_their_repos(ws, capsys):
    wt = new_ws_feature(ws)
    (wt / "app-backend/a.txt").write_text("a"); (wt / "app-flutter/b.txt").write_text("b")
    assert at.main(["commit", "both", "-m", "feat(both): T1", "app-backend/a.txt", "app-flutter/b.txt"]) == 0
    assert sh("git", "log", "-1", "--format=%s", cwd=wt / "app-backend") == "feat(both): T1"
    assert sh("git", "status", "--porcelain", cwd=wt / "app-flutter") == ""

def test_commit_refuses_workspace_path(ws, capsys):
    wt = new_ws_feature(ws)
    (wt / "app-backend/a.txt").write_text("a"); (wt / "notes.md").write_text("n")
    assert at.main(["commit", "both", "-m", "x", "app-backend/a.txt", "notes.md"]) == 1
    assert "notes.md is not inside a product repo" in capsys.readouterr().err
    assert "a.txt" in sh("git", "status", "--porcelain", cwd=wt / "app-backend")   # nothing committed

def test_heads_lists_each_repo(ws, capsys):
    wt = new_ws_feature(ws); capsys.readouterr()
    at.main(["heads", "both"])
    out = capsys.readouterr().out.strip()
    assert out.startswith("app-backend:") and " app-flutter:" in out

def test_lease_fails_when_product_branch_diverged(ws, tmp_path, capsys):
    wt = new_ws_feature(ws)
    o = tmp_path / "o"; sh("git", "clone", "-q", "-b", "feature/both", str(tmp_path / "backend.git"), str(o), cwd=tmp_path)
    sh("git", "config", "user.email", "x@x", cwd=o); sh("git", "config", "user.name", "x", cwd=o)
    (o / "r.txt").write_text("r"); sh("git", "add", "-A", cwd=o); sh("git", "commit", "-qm", "remote", cwd=o); sh("git", "push", "-q", cwd=o)
    (wt / "app-backend/l.txt").write_text("l"); sh("git", "add", "-A", cwd=wt / "app-backend"); sh("git", "commit", "-qm", "local", cwd=wt / "app-backend")
    assert at.main(["lease", "both", "acquire"]) == 1
    assert "diverged" in capsys.readouterr().err

def test_push_and_sync_cover_products(ws, tmp_path, capsys):
    wt = new_ws_feature(ws)
    (wt / "app-flutter/c.txt").write_text("c"); at.main(["commit", "both", "-m", "c", "app-flutter/c.txt"])
    assert at.main(["push", "both"]) == 0
    assert sh("git", "rev-parse", "origin/feature/both", cwd=wt / "app-flutter") == sh("git", "rev-parse", "HEAD", cwd=wt / "app-flutter")
    o = tmp_path / "o2"; sh("git", "clone", "-q", str(tmp_path / "backend.git"), str(o), cwd=tmp_path)
    sh("git", "config", "user.email", "x@x", cwd=o); sh("git", "config", "user.name", "x", cwd=o)
    (o / "m.txt").write_text("m"); sh("git", "add", "-A", cwd=o); sh("git", "commit", "-qm", "main moved", cwd=o); sh("git", "push", "-q", cwd=o)
    capsys.readouterr()
    assert at.main(["sync", "both"]) == 0
    assert (wt / "app-backend/m.txt").exists()
```

- [ ] **Step 2: Run** `python3 -m pytest -q tests/test_workspace.py -k "commit or heads or lease or push_and_sync"` → FAIL.

- [ ] **Step 3: Implement.** Extract today's `cmd_push` body into `_push_branch(wt, branch, label="") -> None` and `cmd_sync`'s into `_sync_one(wt, base, dirty_excludes, label="") -> bool` (True = merged); single-repo calls them once with today's arguments so messages stay identical.

- [ ] **Step 4: Verify** — `python3 -m pytest -q` → all pass (existing push/sync/lease tests unchanged).

- [ ] **Step 5: Commit** — `feat: commit/heads and repo-aware lease, push, sync (#8)`

### Task 6: `test`, `diff`, `diffstat` across repos

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (`diff_args`, `diffstat`, `cmd_diff`, `cmd_test`)
- Test: `tests/test_workspace.py`

**Interfaces:**
- Consumes: `ws_repos`, `parse_since`, `block_command`, `repo_branch`.
- Produces:
  - `cmd_diff`: workspace mode concatenates, per repo in order, `git diff` in `r["wt"]` with range `<since[path]>..HEAD` (when `--since` gave that repo) else `origin/<repo_branch>...HEAD`, pathspec `.` + `exclude_specs(project_md())`, and `--src-prefix=a/<path>/ --dst-prefix=b/<path>/`; with `--stat`, a `## <path>` line before each repo's stat. Single-repo unchanged.
  - `diffstat(slug, since)`: sums lines/files over repos in workspace mode (reviewer tier rule uses it unchanged).
  - `cmd_test`: workspace mode runs the workspace `## Build & test` Build/Test (when set and not `none`) in `wt`, then each repo's Build (with `--build`) and Test in `r["wt"]`; skipped repo commands print `<path> <Name>: none configured`. Cache key = `"+".join(code_key(r["wt"]) per repo)` + 6-char sha1 of all commands; `None` if any repo is dirty. Failure writes `tests: <key> fail(<path>:<name>)` and prints `<path> <Name>: FAILED (exit N)`.

- [ ] **Step 1: Failing tests**

```python
def test_diff_prefixes_repo_paths(ws, capsys):
    wt = new_ws_feature(ws)
    (wt / "app-backend/a.txt").write_text("a\n"); at.main(["commit", "both", "-m", "a", "app-backend/a.txt"])
    capsys.readouterr(); at.main(["diff", "both"])
    assert "b/app-backend/a.txt" in capsys.readouterr().out
    assert at.diffstat("both") == (1, 1)

def test_diff_since_per_repo(ws, capsys):
    wt = new_ws_feature(ws)
    (wt / "app-backend/a.txt").write_text("a\n"); at.main(["commit", "both", "-m", "a", "app-backend/a.txt"])
    capsys.readouterr(); at.main(["heads", "both"]); since = capsys.readouterr().out.strip()
    (wt / "app-flutter/b.txt").write_text("b\n"); at.main(["commit", "both", "-m", "b", "app-flutter/b.txt"])
    capsys.readouterr(); at.main(["diff", "both", "--since", since])
    out = capsys.readouterr().out
    assert "app-flutter/b.txt" in out and "app-backend/a.txt" not in out

def test_test_runs_each_repo_and_names_failure(ws, capsys):
    wt = new_ws_feature(ws); capsys.readouterr()
    assert at.main(["test", "both"]) == 0
    (wt / "app-flutter/ui.txt").unlink(); at.main(["commit", "both", "-m", "rm", "app-flutter/ui.txt"])
    assert at.main(["test", "both"]) == 1
    assert "app-flutter Test: FAILED" in capsys.readouterr().out
    assert "fail(app-flutter:test)" in at.read_status(wt / ".agent-team/features/both/status.md")["tests"]
```

- [ ] **Step 2: Run** `python3 -m pytest -q tests/test_workspace.py -k "diff or test_test"` → FAIL.

- [ ] **Step 3: Implement** the interfaces.

- [ ] **Step 4: Verify** — `python3 -m pytest -q` → all pass.

- [ ] **Step 5: Commit** — `feat: repo-aware test and diff (#8)`

### Task 7: `ci`, `pr-body --repo`, `cleanup`, `summary`

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (`cmd_ci`, `cmd_pr_body`, `cmd_cleanup`, `cmd_summary`)
- Test: `tests/test_workspace.py` (gh stub like `tests/test_docs_pr_only.py::gh_stub`, keyed on `-R <owner/repo>` and PR number)

**Interfaces:**
- Consumes: `ws_repos`, `gh_slug`, status `repo_prs` (`"app-backend#12 app-flutter#40"`).
- Produces:
  - `repo_prs(slug) -> dict[str, str]` — path → PR number; `{}` for `none`.
  - `cmd_ci`: extract today's loop into `_ci_one(pr, cwd, grace, watch, repo=None) -> tuple[str, str]` (`state` in pass/none/pending/fail, output); `-R <repo>` added when `repo`. Workspace mode checks each product PR (`repo=gh_slug(r["src"])`) then the workspace `pr`; result `fail` if any fail (prints `<path>#<n>:` before each failing block, `workspace#<n>:` for the workspace PR), else `pending` if any pending, else `pass` if any pass, else `none`. Exit codes as today.
  - `cmd_pr_body --repo <path>`: `## Summary`, `Part of <slug>. Artifacts and reviews: <workspace PR link or "workspace PR">`, `## Merge order` listing `<owner/repo>#<n>` in ws order with `→`, marking this one `(this PR)`. Without `--repo` in workspace mode: today's body plus `## Product PRs` with the same ordered list and `Merge these first, this one last.`
  - `cmd_cleanup`: before the workspace worktree, for each `ws_repos` entry: same three safety checks as today run against the product repo (`src`) and its PR (`merged_pr_head(pr, src)` with `gh pr view <n> -R <repo>`), then `git -C src worktree remove --force <wt>`, `branch -D`, and `--remote` delete. Extract the checks into `_cleanup_one(root, wt, branch, pr_head, remote, force) -> None`.
  - `cmd_summary`: `pr` column shows `<pr> + <repo_prs>` when `repo_prs` isn't `none`.

- [ ] **Step 1: Failing tests**

```python
def test_ci_fails_when_one_product_pr_fails(ws, tmp_path, monkeypatch, capsys):
    wt = new_ws_feature(ws)
    at.main(["status", "both", "--set", "pr=3", "repo_prs=app-backend#12 app-flutter#40"])
    ws_gh(tmp_path, monkeypatch, checks={"12": (0, "ok"), "40": (1, "build\tfail\t1m\turl"), "3": (0, "ok")})
    assert at.main(["ci", "both", "--grace", "0"]) == 1
    out = capsys.readouterr().out
    assert "app-flutter#40:" in out and "ci: fail" in out

def test_pr_body_for_product_lists_merge_order(ws, capsys):
    new_ws_feature(ws)
    at.main(["status", "both", "--set", "pr=3", "repo_prs=app-backend#12 app-flutter#40"])
    capsys.readouterr(); at.main(["pr-body", "both", "--repo", "app-flutter", "--summary", "s"])
    out = capsys.readouterr().out
    assert "## Merge order" in out and out.index("#12") < out.index("#40") and "(this PR)" in out

def test_cleanup_removes_product_worktrees(ws):
    wt = new_ws_feature(ws)
    assert at.main(["cleanup", "both", "--force"]) == 0
    assert not wt.exists()
    assert "feature/both" not in sh("git", "branch", cwd=ws / "app-backend")

def test_cleanup_refuses_unpushed_product_commit(ws, capsys):
    wt = new_ws_feature(ws)
    (wt / "app-backend/u.txt").write_text("u"); at.main(["commit", "both", "-m", "u", "app-backend/u.txt"])
    assert at.main(["cleanup", "both"]) == 1
    assert "app-backend" in capsys.readouterr().err
```

`ws_gh(tmp_path, monkeypatch, checks)`: stub `gh` whose `pr checks <n> …` exits/prints `checks[n]`, `pr view` prints `OPEN x`; on PATH; `monkeypatch.setattr(at, "POLL_SECONDS", 0)`.

- [ ] **Step 2: Run** `python3 -m pytest -q tests/test_workspace.py -k "ci or pr_body or cleanup"` → FAIL.

- [ ] **Step 3: Implement** the interfaces; switch Task 4's resume test to `agent-team cleanup both --force`.

- [ ] **Step 4: Verify** — `python3 -m pytest -q` → all pass (existing ci/pr-body/cleanup/summary tests unchanged).

- [ ] **Step 5: Commit** — `feat: repo-aware ci, pr-body, cleanup, summary (#8)`

### Task 8: Workflow and role skills for workspace mode

**Files:**
- Modify: `skills/team-build/SKILL.md`, `skills/developer/SKILL.md`, `skills/reviewer/SKILL.md`, `skills/tech-lead/SKILL.md`, `skills/tech-lead/references/plan-template.md`, `skills/team-wrap/SKILL.md`, `skills/team-status/SKILL.md`, `docs/reference.md`
- Test: `tests/test_content.py`

**Interfaces:**
- Consumes: CLI from Tasks 1–7: `repos [--log]`, `repos <slug> --ensure`, `commit`, `heads`, `pr-body --repo`, status `repos`/`repo_prs`.

Text to add (each only "in a workspace (`project.md` has `## Repos`)"; single-repo text stays):
- **team-build** — §0 resume: after re-adding the workspace worktree, `agent-team repos <slug> --ensure`. §1 new run: after the first push, `agent-team repos <slug> --ensure`. §3 plan: after `plan.md`, `agent-team repos <slug> --ensure`. Review/QA/CI loops: set `last_reviewed_commit` to `$(agent-team heads <slug>)` (replace the `git rev-parse --short HEAD` wording in both modes — identical value in single-repo). §3 pr: per repo in `repos` order with a non-empty `agent-team diff`: `gh pr view feature/<slug> -R <owner/repo>` or `gh pr create -R <owner/repo> --base <branch> --head feature/<slug> …`; then the workspace PR as today; set `repo_prs` and `pr`; then `gh pr edit` each product PR with `agent-team pr-body <slug> --repo <path>` (numbers exist now). pr-open message lists PRs in merge order, workspace last. *Stop*: draft / `ready --undo` / edit body for every PR that exists.
- **developer** — in a workspace commit with `agent-team commit <slug> -m "<msg>" <paths>`; never `git -C`.
- **reviewer** — Reads: `## Cross-repo rules`; a change breaking one (e.g. non-additive API change that shipped app builds depend on) is Critical.
- **tech-lead** — plan mode: every task's `files:` inside exactly one `### <path>` repo; tasks for earlier repos in `Order:` first; a task needing workspace-level files → `## Spec problems`. Template comment on `files:` saying so.
- **team-wrap** — step 2: workspace → every `repo_prs` entry and `pr` must be merged (`gh pr view <n> -R <owner/repo> --json state,mergedAt`; owner/repo from `agent-team repos`); some unmerged → stop and list them.
- **team-status** — `pr-open` line lists product PRs in merge order.
- **docs/reference.md** — short "Workspaces" section: layout, `## Repos`, one PR per repo + workspace PR, merge order.

- [ ] **Step 1: Failing test** (`tests/test_content.py`):

```python
def test_workspace_mode_wired_in_skills():
    tb = read("skills/team-build/SKILL.md")
    assert tb.count("agent-team repos <slug> --ensure") >= 3
    assert "agent-team heads <slug>" in tb and "pr-body <slug> --repo" in tb and "-R <owner/repo>" in tb
    assert "agent-team commit <slug>" in read("skills/developer/SKILL.md")
    assert "Cross-repo rules" in read("skills/reviewer/SKILL.md")
    assert "Spec problems" in read("skills/tech-lead/SKILL.md") and "## Repos" in read("skills/tech-lead/SKILL.md")
    assert "repo_prs" in read("skills/team-wrap/SKILL.md")
    assert "git -C" not in tb + read("skills/developer/SKILL.md")
```

- [ ] **Step 2: Run** `python3 -m pytest -q tests/test_content.py::test_workspace_mode_wired_in_skills` → FAIL.

- [ ] **Step 3: Edit the skills** as listed.

- [ ] **Step 4: Verify** — `python3 -m pytest -q && python3 scripts/validate.py .` → all pass, `OK` (role SKILL.md ≤ 150 lines).

- [ ] **Step 5: Commit** — `docs: wire workspace mode into the workflow and role skills (#8)`
