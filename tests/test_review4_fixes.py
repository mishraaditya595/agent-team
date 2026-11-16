"""Regression tests for the fourth review of PR #2: docs-pull copies must not block the next pull."""
import subprocess

from test_agent_team import at, repo, sh  # noqa: F401  (fixture)
from test_review_fixes import protect_main
from test_review2_fixes import squash_meta_into_main


def setup_on_meta_then_pull(repo, tmp_path):
    """team-init on a protected main (docs to meta), then team-ideate's docs-pull, with no commit."""
    allow = protect_main(tmp_path)
    proj = repo / ".agent-team" / "project.md"
    proj.write_text(proj.read_text().replace("# Demo", "# Demo setup"))
    assert at.main(["docs-commit", "-m", "setup", ".agent-team/project.md"]) == 0
    assert at.main(["docs-pull"]) == 0
    assert "# Demo setup" in proj.read_text()                    # seeded, uncommitted
    return allow, proj


def test_plain_git_pull_is_blocked_by_seeded_copy(repo, tmp_path):
    """Documents the underlying problem (why workflows must use `agent-team pull`)."""
    allow, proj = setup_on_meta_then_pull(repo, tmp_path)
    squash_meta_into_main(tmp_path, allow)
    r = subprocess.run(["git", "pull", "-q", "--ff-only"], cwd=repo, capture_output=True, text=True)
    assert r.returncode != 0


def test_agent_team_pull_after_docs_pull_and_squash(repo, tmp_path, capsys):
    allow, proj = setup_on_meta_then_pull(repo, tmp_path)
    squash_meta_into_main(tmp_path, allow)
    capsys.readouterr()
    assert at.main(["pull"]) == 0, capsys.readouterr().err
    assert sh("git", "rev-parse", "HEAD", cwd=repo) == sh("git", "rev-parse", "origin/main", cwd=repo)
    assert "# Demo setup" in proj.read_text()
    assert sh("git", "status", "--porcelain", cwd=repo) == ""
    assert not at._seed_record(repo, ".agent-team/project.md").exists()


def test_agent_team_pull_while_meta_still_open_reseeds(repo, tmp_path, capsys):
    allow, proj = setup_on_meta_then_pull(repo, tmp_path)
    assert at.main(["pull"]) == 0
    assert "# Demo setup" in proj.read_text()                    # still the live meta copy


def test_agent_team_pull_keeps_real_edits(repo, tmp_path, capsys):
    allow, proj = setup_on_meta_then_pull(repo, tmp_path)
    proj.write_text(proj.read_text() + "\nowner edit\n")          # edited after docs-pull
    squash_meta_into_main(tmp_path, allow)
    capsys.readouterr()
    assert at.main(["pull"]) == 1
    err = capsys.readouterr().err
    assert ".agent-team/project.md" in err and "edited" in err
    assert "owner edit" in proj.read_text()                       # never thrown away


def test_pull_needs_default_branch(repo, capsys):
    sh("git", "checkout", "-q", "-b", "other", cwd=repo)
    assert at.main(["pull"]) == 1
    assert "default branch" in capsys.readouterr().err
