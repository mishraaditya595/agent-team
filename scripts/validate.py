#!/usr/bin/env python3
"""Validate agent-team skills and model config. Usage: python scripts/validate.py [root]"""
import re
import sys
from pathlib import Path

import yaml

TIERS = ("deep", "standard", "fast")
TOOLS = ("claude", "codex", "gemini")
EFFORTS = ("none", "minimal", "low", "medium", "high", "xhigh")
TOP_LEVEL = {"name", "description", "license", "metadata"}
KINDS = {"role", "workflow", "guideline"}
ROLE_HEADINGS = ("## Reads", "## Writes", "## Never")
ROLE_MAX_LINES = 150
MODELS_REL = Path("skills") / "team-build" / "references" / "models.yaml"
STATUS_REL = Path("skills") / "team-build" / "references" / "status-template.md"
CLI_REL = Path("skills") / "team-build" / "scripts" / "agent_team.py"
# A file path a skill tells the agent to open, e.g. `references/plan-template.md` or scripts/agent_team.py.
REF_PATH = re.compile(r"(?<![\w/.-])((?:references|scripts)/[\w.-]+\.\w+)")


def models_path(root: Path) -> Path:
    return Path(root) / MODELS_REL


def _load(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text()) or {}


def load_models(path: Path) -> dict[str, dict[str, str]]:
    return _load(path).get("tools") or {}


def load_effort(path: Path) -> dict[str, str]:
    return _load(path).get("effort") or {}


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
    path = models_path(root)
    if not path.exists():
        return [f"models.yaml: missing {MODELS_REL}"]
    if path.is_symlink():
        return [f"models.yaml: {MODELS_REL} must be a real file, not a link"]
    errors = []
    tools = load_models(path)
    for tool in TOOLS:
        if tool not in tools:
            errors.append(f"models.yaml: missing tool '{tool}'")
    for tool, tiers in tools.items():
        for tier in TIERS:
            if not (tiers or {}).get(tier):
                errors.append(f"models.yaml: tool '{tool}' missing tier '{tier}'")
    effort = load_effort(path)
    for tier, value in effort.items():
        if tier not in TIERS:
            errors.append(f"models.yaml: effort for unknown tier '{tier}'")
        elif value not in EFFORTS:
            errors.append(f"models.yaml: effort '{value}' for '{tier}' not one of {list(EFFORTS)}")
    return errors


def _check_refs(root: Path, skill_md: Path, text: str) -> list[str]:
    """Every references/... or scripts/... path a skill mentions exists in that skill or another skill."""
    errors = []
    skills = Path(root) / "skills"
    for rel in sorted(set(REF_PATH.findall(text))):
        if (skill_md.parent / rel).exists():
            continue
        if not any((d / rel).exists() for d in skills.iterdir() if d.is_dir()):
            errors.append(f"skills/{skill_md.parent.name}: mentions '{rel}' but no skill has it")
    return errors


def _check_skill(root: Path, skill_md: Path) -> list[str]:
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
    errors += _check_refs(root, skill_md, text)
    return errors


def _check_agents(root: Path, roles: dict[str, dict]) -> list[str]:
    """Claude subagent files: one per role, model = models.yaml claude[role tier], same description as the skill."""
    agents = root / "agents"
    if not agents.is_dir():
        return []
    claude = load_models(models_path(root)).get("claude") or {}
    errors = []
    for name, info in roles.items():
        path = agents / f"{name}.md"
        if not path.exists():
            errors.append(f"agents/{name}.md: missing")
            continue
        fm = parse_frontmatter(path.read_text()) or {}
        want = claude.get(info["tier"])
        if fm.get("model") != want:
            errors.append(f"agents/{name}.md: model '{fm.get('model')}' != '{want}'")
        desc = str(fm.get("description", ""))
        if info["description"] and info["description"] not in desc:
            errors.append(f"agents/{name}.md: description doesn't match skills/{name} description")
    return errors


def _check_status_schema(root: Path) -> list[str]:
    """The status template's keys are exactly the keys the helper CLI accepts."""
    tpl, cli = root / STATUS_REL, root / CLI_REL
    if not (tpl.exists() and cli.exists()):
        return []
    head = tpl.read_text().split("\n## Log", 1)[0]
    keys = {m.group(1) for m in re.finditer(r"^([a-z_]+):", head, re.M)}
    m = re.search(r"STATUS_KEYS = \((.*?)\)", cli.read_text(), re.S)
    known = set(re.findall(r'"([a-z_]+)"', m.group(1))) if m else set()
    if keys != known:
        return [f"status-template.md keys {sorted(keys)} != agent_team.py STATUS_KEYS {sorted(known)}"]
    return []


def validate_repo(root: Path) -> list[str]:
    root = Path(root)
    errors = _check_models(root)
    roles = {}
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        errors += _check_skill(root, skill_md)
        fm = parse_frontmatter(skill_md.read_text()) or {}
        meta = fm.get("metadata") or {}
        if meta.get("kind") == "role":
            roles[skill_md.parent.name] = {"tier": meta.get("tier"),
                                           "description": str(fm.get("description", "")).strip()}
    if models_path(root).exists():
        errors += _check_agents(root, roles)
    errors += _check_status_schema(root)
    return errors


def main(argv: list[str]) -> int:
    errors = validate_repo(Path(argv[1] if len(argv) > 1 else "."))
    for e in errors:
        print(e)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
