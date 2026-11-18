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


def test_pr_only_on_origin_main_applies_to_stale_checkout(repo, tmp_path, capsys):
    """Another machine merged the setting into main; this checkout hasn't pulled yet."""
    o = tmp_path / "other"
    sh("git", "clone", "-q", str(tmp_path / "remote.git"), str(o), cwd=tmp_path)
    sh("git", "config", "user.email", "x@x", cwd=o); sh("git", "config", "user.name", "x", cwd=o)
    p = o / ".agent-team" / "project.md"
    p.write_text(p.read_text() + "\n## Conventions\n- docs-push: pr-only\n")
    sh("git", "commit", "-qam", "pr-only", cwd=o); sh("git", "push", "-q", cwd=o)
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", ".agent-team/ideas.md"]) == 0
    assert "pushed to agent-team/meta" in capsys.readouterr().out


def test_pr_only_pasted_with_markup_still_applies():
    base = "# x\n\n## Conventions\n{}\n"
    assert at.docs_pr_only(base.format("`- docs-push: pr-only`"))
    assert at.docs_pr_only(base.format("- **docs-push:** `pr-only`"))


def test_pr_only_other_list_styles_still_apply():
    base = "# x\n\n## Conventions\n{}\n"
    for line in ("* docs-push: pr-only", "+ docs-push: pr-only", "docs-push: pr-only",
                 "- docs-push: pr_only", "- Docs push: pr only"):
        assert at.docs_pr_only(base.format(line)), line
    assert not at.docs_pr_only(base.format("- docs-push: direct"))
    assert not at.docs_pr_only(base.format("- no docs-push here, pr-only reviews are a team habit"))


def gh_stub(tmp_path, monkeypatch, open_pr_url=""):
    """gh stub for the meta PR: `pr list` reports open_pr_url (or none); `pr create` logs and prints a URL."""
    import os
    bin_ = tmp_path / "fakebin"; bin_.mkdir(exist_ok=True)
    log = tmp_path / "gh.log"
    (bin_ / "gh").write_text(f'''#!/usr/bin/env python3
import sys
a = sys.argv[1:]
open("{log}", "a").write(" ".join(a) + "\\n")
if a[:2] == ["pr", "create"]:
    print("https://github.com/o/r/pull/9")
elif a[:2] == ["pr", "list"]:
    url = "{open_pr_url}"
    print(url if "url" in a else ("1" if url else "0"))
''')
    (bin_ / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    return log


def test_pr_only_opens_meta_pr(repo, tmp_path, monkeypatch, capsys):
    set_conventions(repo, "- docs-push: pr-only")
    log = gh_stub(tmp_path, monkeypatch)
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", "--title", "agent-team: ideas", ".agent-team/ideas.md"]) == 0
    assert "PR: https://github.com/o/r/pull/9" in capsys.readouterr().out
    assert "pr create --base main --head agent-team/meta --title agent-team: ideas" in log.read_text()


def test_pr_only_reuses_open_meta_pr(repo, tmp_path, monkeypatch, capsys):
    set_conventions(repo, "- docs-push: pr-only")
    log = gh_stub(tmp_path, monkeypatch, open_pr_url="https://github.com/o/r/pull/5")
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", ".agent-team/ideas.md"]) == 0
    assert "PR: https://github.com/o/r/pull/5" in capsys.readouterr().out
    assert "pr create" not in log.read_text()
