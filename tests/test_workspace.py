"""Workspace mode: a parent repo whose project.md lists nested product repos."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "team-build" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import agent_team as at  # noqa: E402
from test_agent_team import repo, sh  # noqa: E402,F401

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

WS_IDEAS = """## 2026-11-18 — mode: hold

### both — Both
- **Repos:** app-backend, app-flutter
- **Value:** H · **Effort:** S · **Risk:** low
"""


def _clone(tmp_path, name, fname=None):
    sh("git", "init", "-q", "--bare", "-b", "main", str(tmp_path / f"{name}.git"), cwd=tmp_path)
    d = tmp_path / "work" / name if name != "remote" else tmp_path / "work"
    sh("git", "clone", "-q", str(tmp_path / f"{name}.git"), str(d), cwd=tmp_path)
    for k, v in (("user.name", "t"), ("user.email", "t@t"), ("init.defaultBranch", "main")):
        sh("git", "config", k, v, cwd=d)
    sh("git", "checkout", "-q", "-b", "main", cwd=d)
    return d


def _push(d, files):
    for rel, text in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(text)
    sh("git", "add", "-A", cwd=d)
    sh("git", "commit", "-q", "-m", "init", cwd=d)
    sh("git", "push", "-q", "-u", "origin", "main", cwd=d)
    sh("git", "remote", "set-head", "origin", "main", cwd=d)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    work = _clone(tmp_path, "remote")
    _push(work, {".gitignore": ".agent-team/worktrees/\n/app-backend/\n/app-flutter/\n",
                 ".agent-team/project.md": WS_PROJECT, ".agent-team/ideas.md": WS_IDEAS})
    # product clones live inside the (gitignored) workspace checkout
    for name, f in (("backend", "api.txt"), ("app", "ui.txt")):
        d = _clone(tmp_path, name)
        _push(d, {f: "x\n"})
        d.rename(work / {"backend": "app-backend", "app": "app-flutter"}[name])
    monkeypatch.chdir(work)
    monkeypatch.setenv("AGENT_TEAM_HOST", "box-a")
    return work


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


def test_upgrade_adds_repos_when_nested(ws, capsys):
    p = ws / ".agent-team" / "project.md"
    p.write_text(p.read_text().split("## Repos")[0] + "## Model overrides\nnone\n")
    sh("git", "commit", "-qam", "drop repos", cwd=ws)
    assert at.main(["upgrade"]) == 0
    text = p.read_text()
    assert "### app-backend\n" in text and "### app-flutter\n" in text
    assert "- Order: app-backend, app-flutter" in text
    assert text.index("## Repos") < text.index("## Model overrides")
    assert "Repos, Cross-repo rules\n" in capsys.readouterr().out


def test_upgrade_single_repo_never_adds_repos(repo, capsys):
    at.main(["upgrade"])
    assert "## Repos" not in (repo / ".agent-team" / "project.md").read_text()


def test_unignored_nested_repo_not_detected(ws):
    (ws / ".gitignore").write_text(".agent-team/worktrees/\n/app-backend/\n")
    assert at.nested_repos(ws) == ["app-backend"]


def test_allow_list_covers_repo_commands():
    allow = at.merged_allow([], WS_PROJECT)
    assert "Bash(test -f api.txt:*)" in allow and "Bash(test -f ui.txt:*)" in allow


def test_idea_info_repos(ws):
    assert at.idea_info("both")["repos"] == ["app-backend", "app-flutter"]


def new_ws_feature(work, slug="both", ensure=True):
    wt = work / ".agent-team" / "worktrees" / slug
    sh("git", "worktree", "add", "-q", "-b", f"feature/{slug}", str(wt), "origin/main", cwd=work)
    assert at.main(["init-status", slug]) == 0
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-qm", "status", cwd=wt)
    sh("git", "push", "-q", "-u", "origin", f"feature/{slug}", cwd=wt)
    if ensure:
        assert at.main(["repos", slug, "--ensure"]) == 0
    return wt


def test_ensure_creates_product_worktrees_and_pushes(ws, capsys):
    wt = new_ws_feature(ws)
    for p, f in (("app-backend", "api.txt"), ("app-flutter", "ui.txt")):
        assert (wt / p / f).exists()
        assert sh("git", "rev-parse", "--abbrev-ref", "HEAD", cwd=wt / p) == "feature/both"
        assert sh("git", "ls-remote", "--heads", "origin", "feature/both", cwd=ws / p)
    assert at.read_status(wt / ".agent-team/features/both/status.md")["repos"] == "app-backend app-flutter"
    assert sh("git", "status", "--porcelain", cwd=wt) == "M .agent-team/features/both/status.md"  # only the status write; nested checkouts are ignored


def test_ensure_resumes_from_pushed_product_branch(ws, tmp_path):
    wt = new_ws_feature(ws)
    (wt / "app-backend" / "new.txt").write_text("x")
    sh("git", "add", "-A", cwd=wt / "app-backend"); sh("git", "commit", "-qm", "work", cwd=wt / "app-backend")
    sh("git", "push", "-q", cwd=wt / "app-backend")
    # Task 7 switches this to cleanup: this machine forgets everything
    for p in ("app-backend", "app-flutter"):
        sh("git", "worktree", "remove", "--force", str(wt / p), cwd=ws / p)
        sh("git", "branch", "-qD", "feature/both", cwd=ws / p)
    sh("git", "worktree", "remove", "--force", str(wt), cwd=ws)
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


def test_ensure_rerun_pushes_after_failed_push(ws):
    new_ws_feature(ws, ensure=False)
    sh("git", "config", "remote.origin.pushurl", "/nonexistent.git", cwd=ws / "app-flutter")
    assert at.main(["repos", "both", "--ensure"]) == 1
    sh("git", "config", "--unset", "remote.origin.pushurl", cwd=ws / "app-flutter")
    assert at.main(["repos", "both", "--ensure"]) == 0
    assert sh("git", "ls-remote", "--heads", "origin", "feature/both", cwd=ws / "app-flutter")


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
    assert sh("git", "status", "--porcelain", cwd=wt / "app-backend").startswith("??")   # nothing staged or committed


def test_commit_is_atomic_across_repos(ws, capsys):
    wt = new_ws_feature(ws)
    before = sh("git", "rev-parse", "HEAD", cwd=wt / "app-backend")
    (wt / "app-backend/a.txt").write_text("a")
    assert at.main(["commit", "both", "-m", "x", "app-backend/a.txt", "app-flutter/typo.txt"]) == 1
    assert "app-flutter:" in capsys.readouterr().err
    assert sh("git", "rev-parse", "HEAD", cwd=wt / "app-backend") == before


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


def test_parse_since():
    assert at.parse_since("a:x b:y") == {"a": "x", "b": "y"}
    assert at.parse_since("abc123") == "abc123" and at.parse_since(None) is None
