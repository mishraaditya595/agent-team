"""Content checks on the real skills: each pins a rule from the spec."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "skills"


def read(rel):
    return (ROOT / rel).read_text()


RULES = ("Think before coding", "Simplicity first", "Surgical changes", "Goal-driven execution")


def test_guidelines_have_rules():
    text = read("skills/engineering-guidelines/SKILL.md")
    for h in (*RULES, "YAGNI ladder"):
        assert re.search(rf"^#+ .*{h}", text, re.M), h
    agents = read("AGENTS.md")
    for r in RULES:
        assert r in agents, r


PROJECT_HEADINGS = ("## Product", "## Users", "## Domain", "## Stack", "## Build & test",
                    "## Conventions", "## Positioning & voice", "## Channels", "## Model overrides")


def test_project_template_headings():
    text = read("skills/team-init/references/project-template.md")
    for h in PROJECT_HEADINGS:
        assert re.search(rf"^{re.escape(h)}\s*$", text, re.M), h


def test_claude_settings_valid_json():
    import json
    data = json.loads(read("skills/team-init/references/claude-settings.json"))
    allow = data["permissions"]["allow"]
    assert "Bash(gh pr create:*)" in allow
    assert "Bash(git push origin feature/*)" in allow
    assert "{{TEST_COMMANDS}}" in allow


def test_codex_project_toml_parses():
    import tomllib
    data = tomllib.loads(read("skills/team-init/references/codex-project.toml"))
    assert data["sandbox_mode"] == "workspace-write"


def test_spec_template_has_numbered_ac():
    text = read("skills/pm/references/spec-template.md")
    for h in ("## Problem", "## Users affected", "## Proposal", "## Out of scope",
              "## Acceptance criteria", "## Success signal"):
        assert h in text, h
    assert re.search(r"^\s*-?\s*AC1\b", text, re.M)


def test_ideation_modes_listed():
    text = read("skills/pm/references/ideation-modes.md")
    for m in ("expand", "hold", "reduce"):
        assert re.search(rf"^#+ .*`?{m}`?", text, re.M), m


def test_pm_role_frontmatter():
    from validate import parse_frontmatter
    fm = parse_frontmatter(read("skills/pm/SKILL.md"))
    assert fm["metadata"]["tier"] == "deep" and fm["metadata"]["allowed-tiers"] == ["deep"]


TASK_LINE = re.compile(r"- \[ \] T\d+ \[(fast|standard)\] .+ — files: .+ — maps to: AC\d+")


def test_plan_template_task_format():
    assert TASK_LINE.search(read("skills/tech-lead/references/plan-template.md"))


def test_plan_template_has_test_plan_heading():
    text = read("skills/tech-lead/references/plan-template.md")
    for h in ("## Approach", "## Data flow", "## Edge cases", "## Test plan", "## Tasks"):
        assert h in text, h


def section(text, heading):
    m = re.search(rf"^{re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, heading
    return m.group(1)


def test_review_template_three_passes():
    text = read("skills/reviewer/references/review-template.md")
    for h in ("## Pass 1 — Spec compliance", "## Pass 2 — Plan & code quality",
              "## Pass 3 — Simplicity", "## Verdict"):
        assert h in text, h
    assert "APPROVED" in text and "CHANGES REQUESTED" in text


def test_qa_template_columns():
    assert "| AC | Method | Result (PASS/FAIL) | Evidence |" in read("skills/qa/references/qa-template.md")
    assert "UNVERIFIED" in read("skills/qa/references/test-by-platform.md")


def test_reviewer_never_edits():
    assert "edit" in section(read("skills/reviewer/SKILL.md"), "## Never").lower()


def test_qa_never_changes_feature_code():
    assert "feature code" in section(read("skills/qa/SKILL.md"), "## Never").lower()


def test_developer_escalation_rule():
    text = read("skills/developer/SKILL.md")
    assert "fails twice" in text
