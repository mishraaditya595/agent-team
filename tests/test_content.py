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
