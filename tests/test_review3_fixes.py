"""Regression tests for the third review of PR #2 (protected default branch)."""
from test_agent_team import at, new_feature, repo, sh  # noqa: F401  (fixture)
from test_review_fixes import fake_gh, protect_main
from test_review2_fixes import clone, squash_meta_into_main


def test_docs_commit_after_squash_with_conflicting_edit(repo, tmp_path, capsys):
    """Bug 1: stale meta + a later main edit to a line meta also changed must not block docs commits."""
    allow = protect_main(tmp_path)
    proj = repo / ".agent-team" / "project.md"
    proj.write_text(proj.read_text().replace("# Demo", "# Demo meta"))
    assert at.main(["docs-commit", "-m", "a", ".agent-team/project.md"]) == 0
    o = squash_meta_into_main(tmp_path, allow)
    p = o / ".agent-team" / "project.md"
    p.write_text(p.read_text().replace("# Demo meta", "# Demo main"))      # same line, edited on main
    sh("git", "commit", "-qam", "main edit", cwd=o); sh("git", "push", "-q", cwd=o)
    allow.unlink()                                                         # protected again
    sh("git", "pull", "-q", "--ff-only", cwd=repo)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### later — Later\n- **Status:** proposed\n")
    capsys.readouterr()
    assert at.main(["docs-commit", "-m", "b", ".agent-team/ideas.md"]) == 0
    assert "pushed to agent-team/meta" in capsys.readouterr().out
    meta_proj = sh("git", "show", "origin/agent-team/meta:.agent-team/project.md", cwd=repo)
    assert "# Demo main" in meta_proj                                       # new meta starts from main
    assert "### later" in sh("git", "show", "origin/agent-team/meta:.agent-team/ideas.md", cwd=repo)


def test_upgrade_not_blocked_by_docs_pull(repo, tmp_path, capsys):
    """Bug 2: files docs-pull wrote are not the owner's edits."""
    protect_main(tmp_path)
    proj = repo / ".agent-team" / "project.md"
    proj.write_text(proj.read_text().replace("# Demo", "# Demo meta"))
    at.main(["docs-commit", "-m", "a", ".agent-team/project.md"])
    at.main(["docs-pull"])
    assert "# Demo meta" in proj.read_text()
    capsys.readouterr()
    assert at.main(["upgrade"]) == 0, capsys.readouterr().err
    proj.write_text(proj.read_text() + "\nmy own edit\n")                    # a real owner edit still blocks
    assert at.main(["upgrade"]) == 1


def test_gh_asked_once_per_command(repo, tmp_path, monkeypatch, capsys):
    protect_main(tmp_path)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### one — One\n- **Status:** proposed\n")
    at.main(["docs-commit", "-m", "a", ".agent-team/ideas.md"])
    calls = []
    real = at.run
    def counting(cmd, *a, **k):
        if cmd[:3] == ["gh", "pr", "list"]:
            calls.append(cmd)
        return real(cmd, *a, **k)
    monkeypatch.setattr(at, "run", counting)
    at.main(["docs-pull"])
    assert len(calls) <= 1


def test_protected_feature_push_not_called_a_race(repo, tmp_path, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    hook = tmp_path / "remote.git" / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\necho "remote: error: GH006: Protected branch update failed." >&2\nexit 1\n')
    hook.chmod(0o755)
    assert at.main(["push", "tiny"]) == 1
    err = capsys.readouterr().err
    assert "refused by the server" in err and "elsewhere" not in err


def test_cleanup_remote_message_fits(repo, capsys):
    new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    assert at.main(["cleanup", "tiny", "--remote"]) == 1
    err = capsys.readouterr().err
    assert "Push or discard" not in err and "merge" in err.lower()
