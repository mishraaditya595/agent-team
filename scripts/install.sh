#!/usr/bin/env bash
# Install agent-team skills for Claude Code, Codex and other Agent Skills tools on this machine.
# Safe to re-run. Usage: scripts/install.sh [--dry-run]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DRY=0; [ "${1:-}" = "--dry-run" ] && DRY=1
CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
AGENTS_SKILLS_DIR="${AGENTS_SKILLS_DIR:-$HOME/.agents/skills}"
CODEX_CONFIG="${CODEX_HOME:-$HOME/.codex}/config.toml"

run() { if [ "$DRY" = 1 ]; then echo "would: $*"; else "$@"; fi; }

link_skills() {
  local target="$1"
  run mkdir -p "$target"
  for dir in "$REPO"/skills/*/; do
    local src="${dir%/}" name; name="$(basename "$src")"
    local dest="$target/$name"
    if [ -L "$dest" ]; then
      [ "$(readlink "$dest")" = "$src" ] && continue
      run ln -sfn "$src" "$dest"          # our link moved (repo relocated): repoint
    elif [ -e "$dest" ]; then
      echo "skip: $dest exists and is not a link (leaving it alone)" >&2
    else
      run ln -s "$src" "$dest"
    fi
  done
  echo "skills linked into $target"
}

link_skills "$CLAUDE_SKILLS_DIR"
link_skills "$AGENTS_SKILLS_DIR"

if command -v python3 >/dev/null && python3 -c "import yaml" 2>/dev/null; then
  run python3 "$REPO/scripts/codex_profiles.py" "$REPO/skills/team-build/references/models.yaml" "$CODEX_CONFIG"
else
  echo "skip: Codex profiles need python3 + pyyaml (pip install pyyaml)" >&2
fi

cat <<MSG

Done. Alternatives:
  Claude Code plugin (adds the role subagents too):
    /plugin marketplace add <owner>/agent-team   then   /plugin install agent-team@agent-team
  Any Agent Skills tool:
    npx skills add <owner>/agent-team
MSG
