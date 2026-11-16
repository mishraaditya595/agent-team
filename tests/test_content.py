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
