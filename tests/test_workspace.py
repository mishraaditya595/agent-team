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


# ---------- Task 4: team-init / upgrade ----------

def test_upgrade_adds_repos_only_when_nested(repo, tmp_path, capsys):
    assert at.main(["upgrade"]) == 0
    assert "Repos" not in capsys.readouterr().out
    assert "## Repos" not in (repo / ".agent-team" / "project.md").read_text()
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "upgrade", cwd=repo)
    for name in ("app", "api"):
        product(tmp_path, repo, name)
    (repo / ".gitignore").write_text(".agent-team/worktrees/\n/app/\n/api/\n")
    sh("git", "commit", "-qam", "ignore", cwd=repo)
    assert at.main(["upgrade"]) == 0
    assert "Repos, Cross-repo rules" in capsys.readouterr().out
    text = (repo / ".agent-team" / "project.md").read_text()
    assert [r["path"] for r in at.repos(text)] == ["api", "app"]
    assert "- Order: api, app" in at.section(text, "Cross-repo rules")
    assert at.block_command(at.repos(text)[0]["block"], "Test") is None       # owner/agent fills commands


def test_upgrade_ignores_unignored_nested_repo(repo, tmp_path, capsys):
    product(tmp_path, repo, "extra")                      # nested repo, but not gitignored by the workspace
    assert at.nested_repos(repo) == []
    assert at.main(["upgrade"]) == 0
    assert "## Repos" not in (repo / ".agent-team" / "project.md").read_text()


def test_merged_allow_includes_repo_commands(workspace):
    allow = at.merged_allow([], (workspace / ".agent-team" / "project.md").read_text())
    assert "Bash(npm ci:*)" in allow and allow.count("Bash(true:*)") == 1


# ---------- Task 5: ideation ----------

def test_idea_repos_line(workspace, capsys):
    i = workspace / ".agent-team" / "ideas.md"
    i.write_text(i.read_text() + "\n### xr — Cross\n- **Repos:** api, `app`\n- **Value:** H · **Effort:** M · **Risk:** x\n")
    assert at.idea_info("xr")["repos"] == ["api", "app"]
    assert at.idea_info("tiny")["repos"] == []
    assert out(capsys, "idea", "xr")[1] == "status=proposed effort=M repos=api,app"
    assert out(capsys, "idea", "tiny")[1] == "status=proposed effort=S"


# ---------- Task 6: product worktrees, status keys, lease ----------

XR_IDEA = "\n### xr — Cross\n- **Repos:** api\n- **Value:** H · **Effort:** M · **Risk:** x\n"


@pytest.fixture
def feature(workspace, capsys):
    """Workspace feature 'xr' (idea touches api) with its workspace worktree and status.md committed."""
    i = workspace / ".agent-team" / "ideas.md"
    i.write_text(i.read_text() + XR_IDEA)
    sh("git", "commit", "-qam", "idea", cwd=workspace); sh("git", "push", "-q", cwd=workspace)
    wt, fd = new_feature(workspace, "xr", capsys)
    return wt, fd


def branches(repo_dir, remote=False):
    ref = "refs/remotes/origin/feature/" if remote else "refs/heads/feature/"
    return sh("git", "for-each-ref", "--format=%(refname:short)", ref, cwd=repo_dir).split()


def test_ensure_creates_product_worktrees_from_idea(feature, workspace, capsys):
    wt, fd = feature
    code, o, err = out(capsys, "repos", "xr", "--ensure")
    assert code == 0, err
    assert o == "api created"
    assert sh("git", "branch", "--show-current", cwd=wt / "api") == "feature/xr"
    sh("git", "fetch", "-q", "origin", cwd=workspace / "api")
    assert branches(workspace / "api", remote=True) == ["origin/feature/xr"]
    st = at.read_status(fd / "status.md")
    assert st["repos"] == "api" and st["repo_prs"] == "none"
    assert out(capsys, "repos", "xr", "--ensure")[1] == "api exists"


def test_ensure_adds_plan_repos(feature, capsys):
    wt, fd = feature
    (fd / "plan.md").write_text((fd / "plan.md").read_text() + "\n## Files\n- `app/lib/x.dart` — modify — y\n")
    assert out(capsys, "repos", "xr", "--ensure")[1] == "api created\napp created"
    assert at.read_status(fd / "status.md")["repos"] == "api app"


def test_ensure_reuses_remote_branch(feature, workspace, capsys):
    wt, fd = feature
    assert at.main(["repos", "xr", "--ensure"]) == 0
    (wt / "api" / "new.txt").write_text("x\n")
    sh("git", "add", "-A", cwd=wt / "api"); sh("git", "commit", "-qm", "work", cwd=wt / "api")
    sh("git", "push", "-q", "origin", "feature/xr", cwd=wt / "api")
    head = sh("git", "rev-parse", "HEAD", cwd=wt / "api")
    sh("git", "worktree", "remove", "--force", str(wt / "api"), cwd=workspace / "api")   # another machine: no local copy
    sh("git", "branch", "-D", "feature/xr", cwd=workspace / "api")
    assert out(capsys, "repos", "xr", "--ensure")[1] == "api created"
    assert sh("git", "rev-parse", "HEAD", cwd=wt / "api") == head


def test_ensure_refuses_unignored_path(feature, capsys):
    wt, fd = feature
    (wt / ".gitignore").write_text(".agent-team/worktrees/\n/app/\n")
    code, _, err = out(capsys, "repos", "xr", "--ensure")
    assert code == 1 and "api" in err and "gitignore" in err
    assert not (wt / "api").exists()


def test_lease_catches_up_products(feature, workspace, tmp_path, capsys):
    wt, fd = feature
    assert at.main(["repos", "xr", "--ensure"]) == 0
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-qm", "status", cwd=wt); sh("git", "push", "-q", "-u", "origin", "feature/xr", cwd=wt)
    other = tmp_path / "other-api"
    sh("git", "clone", "-q", "-b", "feature/xr", str(tmp_path / "api.git"), str(other), cwd=tmp_path)
    sh("git", "config", "user.email", "o@o", cwd=other); sh("git", "config", "user.name", "o", cwd=other)
    (other / "o.txt").write_text("o\n"); sh("git", "add", "-A", cwd=other); sh("git", "commit", "-qm", "o", cwd=other)
    sh("git", "push", "-q", cwd=other)
    (wt / "api" / "l.txt").write_text("l\n"); sh("git", "add", "-A", cwd=wt / "api"); sh("git", "commit", "-qm", "l", cwd=wt / "api")
    code, _, err = out(capsys, "lease", "xr", "acquire")
    assert code == 1 and "diverged" in err


def test_single_repo_status_and_ensure_unchanged(repo, capsys):
    wt, fd = new_feature(repo)
    before = (fd / "status.md").read_text()
    assert "repos:" not in before
    assert out(capsys, "repos", "tiny", "--ensure")[1] == "single-repo"
    assert (fd / "status.md").read_text() == before
