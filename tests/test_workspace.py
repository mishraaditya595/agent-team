"""Workspace mode (#8): a workspace repo with nested, gitignored product repos listed under ## Repos."""
import pytest

from test_agent_team import at, new_feature, repo, sh  # noqa: F401  (fixture)

REPOS = """
## Repos
### app
- Role: mobile app
- Test: `true`
### api
- Role: REST API
- Branch: main
- Install: `npm ci`
- Test: `true`

## Cross-repo rules
- Order: api, app
- app: shipped builds keep working (additive API changes only).
"""


def product(tmp_path, work, name):
    remote = tmp_path / f"{name}.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    d = work / name
    sh("git", "clone", "-q", str(remote), str(d), cwd=tmp_path)
    for k, v in (("user.name", "t"), ("user.email", "t@t")):
        sh("git", "config", k, v, cwd=d)
    sh("git", "checkout", "-q", "-b", "main", cwd=d)
    (d / "src.txt").write_text(f"{name}\n")
    sh("git", "add", "-A", cwd=d); sh("git", "commit", "-qm", "init", cwd=d)
    sh("git", "push", "-q", "-u", "origin", "main", cwd=d)
    sh("git", "remote", "set-head", "origin", "main", cwd=d)
    return d


@pytest.fixture
def workspace(repo, tmp_path):
    for name in ("app", "api"):
        product(tmp_path, repo, name)
    (repo / ".gitignore").write_text(".agent-team/worktrees/\n/app/\n/api/\n")
    p = repo / ".agent-team" / "project.md"
    p.write_text(p.read_text() + REPOS)
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "workspace", cwd=repo); sh("git", "push", "-q", cwd=repo)
    return repo


def out(capsys, *args):
    capsys.readouterr()
    code = at.main(list(args))
    o = capsys.readouterr()
    return code, o.out.strip(), o.err.strip()


# ---------- Task 3: ## Repos ----------

def test_repos_parsed_and_ordered(workspace):
    rs = at.repos()
    assert [r["path"] for r in rs] == ["api", "app"]          # Order: wins over listing order
    api = rs[0]
    assert api["role"] == "REST API" and api["branch"] == "main"
    assert at.block_command(api["block"], "Install") == "npm ci"
    assert rs[1]["branch"] is None


def test_repos_none_section_is_single_repo(repo, capsys):
    p = repo / ".agent-team" / "project.md"
    p.write_text(p.read_text() + "\n## Repos\n<!-- ### api -->\nnone\n")
    assert at.repos() == []
    assert out(capsys, "repos")[1] == "single-repo"


def test_block_command_matches_project_command(repo):
    text = (repo / ".agent-team" / "project.md").read_text()
    assert at.block_command(at.section(text, "Build & test"), "Test") == at.project_command("Test", text) == "true"


def test_repos_cmd_lists_and_rejects_non_repo(workspace, capsys):
    code, o, _ = out(capsys, "repos")
    assert code == 0 and [l.split()[:2] for l in o.splitlines()] == [["api", "main"], ["app", "main"]]
    p = workspace / ".agent-team" / "project.md"
    p.write_text(p.read_text().replace("### app", "### missing\n- Test: `true`\n### app"))
    code, _, err = out(capsys, "repos")
    assert code == 1 and "missing" in err


def test_rules_noarg_includes_repo_roots(workspace, capsys):
    (workspace / "AGENTS.md").write_text("ws\n")
    (workspace / "api" / "AGENTS.md").write_text("api\n")
    (workspace / "api" / "deep").mkdir()
    (workspace / "api" / "deep" / "AGENTS.md").write_text("deep\n")
    assert out(capsys, "rules")[1] == "AGENTS.md\napi/AGENTS.md"
