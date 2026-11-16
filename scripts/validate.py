#!/usr/bin/env python3
"""Validate agent-team skills and model config. Usage: python scripts/validate.py [root]"""
import sys
from pathlib import Path

import yaml

TIERS = ("deep", "standard", "fast")
TOP_LEVEL = {"name", "description", "license", "metadata"}
KINDS = {"role", "workflow", "guideline"}
ROLE_HEADINGS = ("## Reads", "## Writes", "## Never")
ROLE_MAX_LINES = 150


def load_models(path: Path) -> dict[str, dict[str, str]]:
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("tools") or {}


def parse_frontmatter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i, l in enumerate(lines[1:], 1) if l.strip() == "---")
    except StopIteration:
        return None
    return yaml.safe_load("\n".join(lines[1:end])) or {}


def _check_models(root: Path) -> list[str]:
    path = root / "config" / "models.yaml"
    if not path.exists():
        return ["models.yaml: missing config/models.yaml"]
    errors = []
    tools = load_models(path)
    if not tools:
        errors.append("models.yaml: no tools defined")
    for tool, tiers in tools.items():
        for tier in TIERS:
            if not (tiers or {}).get(tier):
                errors.append(f"models.yaml: tool '{tool}' missing tier '{tier}'")
    return errors


def _check_skill(skill_md: Path) -> list[str]:
    folder = skill_md.parent.name
    where = f"skills/{folder}"
    text = skill_md.read_text()
    fm = parse_frontmatter(text)
    if fm is None:
        return [f"{where}: no frontmatter"]
    errors = [f"{where}: non-portable field '{k}'" for k in fm if k not in TOP_LEVEL]
    if fm.get("name") != folder:
        errors.append(f"{where}: name '{fm.get('name')}' != folder '{folder}'")
    if not str(fm.get("description", "")).strip():
        errors.append(f"{where}: missing description")
    meta = fm.get("metadata") or {}
    kind = meta.get("kind")
    if kind not in KINDS:
        errors.append(f"{where}: metadata.kind must be one of {sorted(KINDS)}")
    if kind == "role":
        tier, allowed = meta.get("tier"), meta.get("allowed-tiers") or []
        for t in [tier, *allowed]:
            if t not in TIERS:
                errors.append(f"{where}: unknown tier '{t}'")
        if tier not in allowed:
            errors.append(f"{where}: tier '{tier}' not in allowed-tiers {allowed}")
        for h in ROLE_HEADINGS:
            if not any(l.strip() == h for l in text.splitlines()):
                errors.append(f"{where}: missing heading '{h}'")
        n = len(text.splitlines())
        if n > ROLE_MAX_LINES:
            errors.append(f"{where}: {n} lines exceeds {ROLE_MAX_LINES} lines")
    return errors


def validate_repo(root: Path) -> list[str]:
    root = Path(root)
    errors = _check_models(root)
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        errors += _check_skill(skill_md)
    return errors


def main(argv: list[str]) -> int:
    errors = validate_repo(Path(argv[1] if len(argv) > 1 else "."))
    for e in errors:
        print(e)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
