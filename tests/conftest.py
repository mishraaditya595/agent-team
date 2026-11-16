import sys
from pathlib import Path
import textwrap
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

GOOD_MODELS = """\
tools:
  claude: {deep: opus, standard: sonnet, fast: haiku}
  codex: {deep: m-deep, standard: m-std, fast: m-fast}
  gemini: {deep: g-deep, standard: g-std, fast: g-fast}
"""

ROLE_BODY = "## Reads\n- x\n\n## Writes\n- y\n\n## Never\n- z\n"


def role_md(name, tier="fast", allowed="[fast, standard]", extra_fm="", body=ROLE_BODY):
    return (
        f"---\nname: {name}\ndescription: Use when testing.\n{extra_fm}"
        f"metadata:\n  kind: role\n  tier: {tier}\n  allowed-tiers: {allowed}\n---\n\n# {name}\n\n{body}"
    )


@pytest.fixture
def make_repo(tmp_path):
    """Build a throwaway repo: make_repo({'dev': role_md('dev')}, models=...)"""
    def _make(skills=None, models=GOOD_MODELS):
        ref = tmp_path / "skills" / "team-build" / "references"
        ref.mkdir(parents=True, exist_ok=True)
        (ref / "models.yaml").write_text(models)
        for folder, text in (skills or {}).items():
            d = tmp_path / "skills" / folder
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(text)
        return tmp_path
    return _make
