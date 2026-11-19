"""agent-team rules: the repo's AGENTS.md / CLAUDE.md files that govern a set of paths (#11)."""
import os

from test_agent_team import at, new_feature, repo, sh  # noqa: F401  (fixture)


def write(p, text="rule\n"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def rules(capsys, *args):
    capsys.readouterr()
    code = at.main(["rules", *args])
    out = capsys.readouterr()
    return code, out.out.strip(), out.err


def test_rules_nested_and_symlink_dedup(repo, capsys):
    write(repo / "AGENTS.md")
    os.symlink("AGENTS.md", repo / "CLAUDE.md")
    write(repo / "backend" / "api" / "AGENTS.md")
    assert rules(capsys, "backend/api/x.py")[:2] == (0, "AGENTS.md\nbackend/api/AGENTS.md")


def test_rules_include_only_claude_dropped(repo, capsys):
    write(repo / "AGENTS.md")
    write(repo / "CLAUDE.md", "@AGENTS.md\n")
    assert rules(capsys, "x.py")[1] == "AGENTS.md"


def test_rules_claude_with_own_content_kept(repo, capsys):
    write(repo / "AGENTS.md")
    write(repo / "CLAUDE.md", "@AGENTS.md\n- never touch vendor/\n")
    assert rules(capsys, "x.py")[1] == "AGENTS.md\nCLAUDE.md"


def test_rules_unrelated_path_root_only(repo, capsys):
    write(repo / "AGENTS.md")
    write(repo / "backend" / "AGENTS.md")
    assert rules(capsys, "docs/x.md")[1] == "AGENTS.md"


def test_rules_none(repo, capsys):
    assert rules(capsys, "x.py")[:2] == (0, "none")


def test_rules_no_args_root_only(repo, capsys):
    write(repo / "AGENTS.md")
    write(repo / "backend" / "AGENTS.md")
    assert rules(capsys)[1] == "AGENTS.md"


def test_rules_outside_root_fails(repo, capsys):
    code, _, err = rules(capsys, "../x")
    assert code == 1 and "outside" in err
    code, _, err = rules(capsys, "/etc/passwd")
    assert code == 1 and "outside" in err


def test_rules_slug_uses_plan_and_diff(repo, capsys):
    write(repo / "backend" / "api" / "AGENTS.md")
    write(repo / "lib" / "AGENTS.md")
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "rules", cwd=repo); sh("git", "push", "-q", cwd=repo)
    wt, fd = new_feature(repo)
    (fd / "plan.md").write_text((fd / "plan.md").read_text() + "\n## Files\n- `backend/api/new.py` — create — x\n")
    write(wt / "lib" / "util.py", "x\n")
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-qm", "code", cwd=wt)
    assert rules(capsys, "tiny")[1] == "lib/AGENTS.md\nbackend/api/AGENTS.md"


def test_rules_fallback_to_main_checkout(tmp_path):
    wt, main = tmp_path / "wt", tmp_path / "main"
    wt.mkdir()
    write(main / "svc" / "AGENTS.md")
    assert at.rule_files(wt, ["svc/x"], fallback=main) == ["svc/AGENTS.md"]
