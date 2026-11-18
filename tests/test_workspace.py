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
