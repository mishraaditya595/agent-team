"""Regression tests for the second review of PR #2."""
import json
import os
import subprocess

import pytest

from test_agent_team import PROJECT, at, new_feature, repo, sh  # noqa: F401  (fixture)
from test_review_fixes import fake_gh, protect_main


def clone(tmp_path, name, branch="main"):
    d = tmp_path / name
    sh("git", "clone", "-q", "-b", branch, str(tmp_path / "remote.git"), str(d), cwd=tmp_path)
    sh("git", "config", "user.email", "x@x", cwd=d); sh("git", "config", "user.name", "x", cwd=d)
    return d


def squash_meta_into_main(tmp_path, allow):
    allow.write_text("")
    o = clone(tmp_path, "squash")
    sh("git", "merge", "-q", "--squash", "origin/agent-team/meta", cwd=o)
    sh("git", "commit", "-qm", "squash docs", cwd=o); sh("git", "push", "-q", cwd=o)
    return o


def test_stale_meta_does_not_override_main(repo, tmp_path, capsys):
    """Bug 1: after the meta PR is squash-merged (branch kept), a later edit on main must win."""
    allow = protect_main(tmp_path)
    proj = repo / ".agent-team" / "project.md"
    proj.write_text(proj.read_text().replace("# Demo", "# Demo v2"))
    at.main(["docs-commit", "-m", "setup", ".agent-team/project.md"])
    o = squash_meta_into_main(tmp_path, allow)                       # meta branch is kept, like GitHub
    p = o / ".agent-team" / "project.md"
    p.write_text(p.read_text().replace("- Test: `true`", "- Test: `echo NEW`"))
    sh("git", "commit", "-qam", "new test command", cwd=o); sh("git", "push", "-q", cwd=o)
    sh("git", "pull", "-q", "--ff-only", cwd=repo)
    assert at.project_command("Test") == "echo NEW"
    capsys.readouterr()
    at.main(["docs-pull"])
    assert "echo NEW" in proj.read_text()


def test_stale_meta_does_not_capture_unprotected_commits(repo, tmp_path, capsys):
    """After the meta PR merged and protection is lifted, docs go straight to main again."""
    allow = protect_main(tmp_path)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### one — One\n- **Status:** proposed\n")
    at.main(["docs-commit", "-m", "a", ".agent-team/ideas.md"])
    squash_meta_into_main(tmp_path, allow)
    sh("git", "pull", "-q", "--ff-only", cwd=repo)
    ideas.write_text(ideas.read_text() + "\n### two — Two\n- **Status:** proposed\n")
    capsys.readouterr()
    assert at.main(["docs-commit", "-m", "b", ".agent-team/ideas.md"]) == 0
    assert "pushed to main" in capsys.readouterr().out


def test_open_meta_still_wins(repo, tmp_path):
    protect_main(tmp_path)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### one — One\n- **Status:** proposed\n")
    at.main(["docs-commit", "-m", "a", ".agent-team/ideas.md"])
    assert "### one" in at.read_doc(".agent-team/ideas.md")


def test_gh_says_meta_pr_closed(repo, tmp_path, monkeypatch):
    protect_main(tmp_path)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### one — One\n- **Status:** proposed\n")
    at.main(["docs-commit", "-m", "a", ".agent-team/ideas.md"])
    fake_gh(tmp_path, monkeypatch, [[0, ""]])                       # gh pr list: no open PR
    assert "### one" not in at.read_doc(".agent-team/ideas.md")


def test_cleanup_remote_refuses_unmerged_feature(repo, capsys):
    """Bug 2: pushed, never merged, no PR -> --remote must not delete it."""
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    assert at.main(["cleanup", "tiny", "--remote"]) == 1
    assert "not merged" in capsys.readouterr().err
    assert sh("git", "ls-remote", "--heads", "origin", "feature/tiny", cwd=repo)
    assert at.main(["cleanup", "tiny"]) == 0                         # local-only cleanup is safe
    assert sh("git", "ls-remote", "--heads", "origin", "feature/tiny", cwd=repo)


def test_cleanup_remote_ok_when_merged_into_main(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    sh("git", "merge", "-q", "--no-edit", "origin/feature/tiny", cwd=repo); sh("git", "push", "-q", cwd=repo)
    assert at.main(["cleanup", "tiny", "--remote"]) == 0
    assert not sh("git", "ls-remote", "--heads", "origin", "feature/tiny", cwd=repo)


def test_lease_commit_skips_ci(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    at.main(["lease", "tiny", "release"])
    assert "[skip ci]" in sh("git", "log", "-1", "--format=%s", cwd=wt)


def test_lease_network_error_not_blamed_on_other_machine(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    sh("git", "remote", "set-url", "--push", "origin", "/nonexistent/remote.git", cwd=repo)
    head = sh("git", "rev-parse", "HEAD", cwd=wt)
    assert at.main(["lease", "tiny", "release"]) == 1
    err = capsys.readouterr().err
    assert "another machine" not in err and "push failed" in err
    assert sh("git", "rev-parse", "HEAD", cwd=wt) == head            # lease commit undone


def test_push_rejection_message_is_readable(repo, tmp_path, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    b = clone(tmp_path, "b", "feature/tiny")
    (b / "x").write_text("x"); sh("git", "add", "-A", cwd=b); sh("git", "commit", "-qm", "b", cwd=b)
    sh("git", "push", "-q", cwd=b)
    (wt / "y").write_text("y"); sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-qm", "a", cwd=wt)
    assert at.main(["push", "tiny"]) == 3
    err = capsys.readouterr().err
    assert "['" not in err and "push rejected" in err


def test_docs_commit_refuses_unrelated_edits_outside_docs(repo, capsys):
    gi = repo / ".gitignore"
    gi.write_text(gi.read_text() + "my-local-junk/\n")                # owner's own uncommitted edit
    assert at.main(["upgrade"]) == 1
    assert ".gitignore" in capsys.readouterr().err
    assert "## Owner" not in (repo / ".agent-team" / "project.md").read_text()   # nothing written


def test_upgrade_validates_settings_before_writing(repo, capsys):
    (repo / ".claude").mkdir(); (repo / ".claude" / "settings.json").write_text("{ not json")
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "bad settings", cwd=repo)
    assert at.main(["upgrade"]) == 1
    assert "settings.json" in capsys.readouterr().err
    assert "## Owner" not in (repo / ".agent-team" / "project.md").read_text()


def test_docs_commit_handles_deleted_doc(repo, capsys):
    (repo / ".agent-team" / "ideas.md").unlink()
    assert at.main(["docs-commit", "-m", "drop ideas", ".agent-team/ideas.md"]) == 0
    assert subprocess.run(["git", "show", "origin/main:.agent-team/ideas.md"], cwd=repo,
                          capture_output=True).returncode != 0


def test_test_cache_keyed_on_command(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["test", "tiny"]) == 0
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-qm", "s", cwd=wt)
    (repo / ".agent-team" / "project.md").write_text(PROJECT.format(test="exit 4", overrides="none"))
    capsys.readouterr()
    assert at.main(["test", "tiny"]) == 1
    assert "cached" not in capsys.readouterr().out


def test_summary_reads_default_branch_not_working_tree(repo, capsys):
    fd = repo / ".agent-team" / "features" / "local-only"
    fd.mkdir(parents=True)
    (fd / "status.md").write_text(at.STATUS_TEMPLATE.read_text().replace("<slug>", "local-only"))
    at.main(["summary"])
    assert "local-only" not in capsys.readouterr().out


def test_log_timestamp_matches_template(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    at.main(["log", "tiny", "spec", "pm", "--tier", "deep", "--model", "opus"])
    last = (fd / "status.md").read_text().strip().splitlines()[-1]
    import re
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\dZ spec pm ", last)
