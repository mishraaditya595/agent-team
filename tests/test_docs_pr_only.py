"""docs-push: pr-only — docs-commit never pushes to the default branch when project.md says so."""
from test_agent_team import at, repo, sh  # noqa: F401  (fixture)


def set_conventions(repo, line):
    p = repo / ".agent-team" / "project.md"
    p.write_text(p.read_text() + f"\n## Conventions\n{line}\n")
    sh("git", "commit", "-qam", "conventions", cwd=repo); sh("git", "push", "-q", cwd=repo)


def add_idea(repo):
    i = repo / ".agent-team" / "ideas.md"
    i.write_text(i.read_text() + "\n### new — New\n- **Status:** proposed\n")


def test_pr_only_goes_to_meta_even_when_unprotected(repo, capsys):
    set_conventions(repo, "- docs-push: pr-only")
    main_before = sh("git", "rev-parse", "origin/main", cwd=repo)
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", ".agent-team/ideas.md"]) == 0
    assert "pushed to agent-team/meta" in capsys.readouterr().out
    sh("git", "fetch", "-q", "origin", cwd=repo)
    assert sh("git", "rev-parse", "origin/main", cwd=repo) == main_before


def test_without_setting_pushes_to_main(repo, capsys):
    set_conventions(repo, "- Commits: conventional")
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", ".agent-team/ideas.md"]) == 0
    assert "pushed to main" in capsys.readouterr().out


def test_docs_pr_only_parsing():
    base = "# x\n\n## Conventions\n{}\n\n## Channels\nnone\n"
    assert at.docs_pr_only(base.format("- Docs-push:  PR-only"))
    assert not at.docs_pr_only(base.format("<!-- - docs-push: pr-only -->"))
    assert not at.docs_pr_only(base.format("- docs-push: direct"))
    assert not at.docs_pr_only("# x\n\n## Channels\n- docs-push: pr-only\n")   # wrong section
    assert not at.docs_pr_only(None)


def test_template_example_does_not_enable_it():
    from test_agent_team import ROOT
    assert not at.docs_pr_only((ROOT / "skills/team-init/references/project-template.md").read_text())
