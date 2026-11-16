#!/usr/bin/env python3
"""Write agent-team tier profiles (at-deep/at-standard/at-fast) into a Codex config.toml.

Usage: python scripts/codex_profiles.py <models.yaml> <config.toml>
Only the block between the markers is ours; everything else in the file is left byte-for-byte.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import TIERS, load_effort, load_models  # noqa: E402

BEGIN = "# >>> agent-team profiles >>>"
END = "# <<< agent-team profiles <<<"


def render_profiles(models: dict, effort: dict | None = None) -> str:
    codex, effort = models["codex"], effort or {}
    lines = [BEGIN, "# Managed by agent-team scripts/install.sh — edit skills/team-build/references/models.yaml instead.",
             "# Keep your own top-level keys ABOVE this block (TOML puts keys below a table inside it)."]
    for tier in TIERS:
        lines += [f"[profiles.at-{tier}]", f'model = "{codex[tier]}"']
        if effort.get(tier):
            lines.append(f'model_reasoning_effort = "{effort[tier]}"')
    lines.append(END)
    return "\n".join(lines) + "\n"


def merge_into_config(existing: str, block: str) -> str:
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.S)
    if pattern.search(existing):
        return pattern.sub(lambda _: block, existing, count=1)
    sep = "" if not existing or existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block


def main(argv: list[str]) -> int:
    models_path, config_path = Path(argv[1]), Path(argv[2])
    models = load_models(models_path)
    codex = models.get("codex")
    if not codex:
        print("models.yaml: no 'codex' tool — skipping Codex profiles")
        return 0
    missing = [t for t in TIERS if not codex.get(t)]
    if missing:
        print(f"models.yaml: codex missing tier '{missing[0]}' — skipping Codex profiles")
        return 0
    config_path.parent.mkdir(parents=True, exist_ok=True)
    existing = config_path.read_text() if config_path.exists() else ""
    config_path.write_text(merge_into_config(existing, render_profiles(models, load_effort(models_path))))
    print(f"codex profiles written to {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
