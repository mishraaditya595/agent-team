#!/usr/bin/env bash
# Runs install.sh twice against a temp HOME and checks links + Codex config are idempotent.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export HOME="$T" CODEX_HOME="$T/.codex" AGENT_TEAM_BIN_DIR="$T/bin"
mkdir -p "$CODEX_HOME"; printf 'model = "user-choice"\n' > "$CODEX_HOME/config.toml"
mkdir -p "$T/.claude/skills/pm-mine"   # unrelated user skill must survive
bash "$REPO/scripts/install.sh" >/dev/null
bash "$REPO/scripts/install.sh" >/dev/null
fail() { echo "FAIL: $*"; exit 1; }
for d in "$REPO"/skills/*/; do
  n="$(basename "$d")"
  for base in "$T/.claude/skills" "$T/.agents/skills"; do
    [ -L "$base/$n" ] || fail "$base/$n not a symlink"
    [ "$(readlink "$base/$n")" = "${d%/}" ] || fail "$base/$n points elsewhere"
  done
done
[ -d "$T/.claude/skills/pm-mine" ] || fail "user skill removed"
grep -q 'model = "user-choice"' "$CODEX_HOME/config.toml" || fail "user codex config lost"
[ "$(grep -c '>>> agent-team profiles >>>' "$CODEX_HOME/config.toml")" = 1 ] || fail "profiles duplicated"
grep -q '\[profiles.at-fast\]' "$CODEX_HOME/config.toml" || fail "no at-fast profile"
grep -q 'model_reasoning_effort = "low"' "$CODEX_HOME/config.toml" || fail "no reasoning effort"
[ -L "$T/bin/agent-team" ] || fail "agent-team CLI not linked"
"$T/bin/agent-team" -h >/dev/null || fail "agent-team CLI doesn't run"
# a real directory with a skill's name is left alone with a warning
rm "$T/.agents/skills/pm"; mkdir "$T/.agents/skills/pm"
out="$(bash "$REPO/scripts/install.sh" 2>&1)"
echo "$out" | grep -q "skip" || fail "no warning for existing real dir"
[ -d "$T/.agents/skills/pm" ] && [ ! -L "$T/.agents/skills/pm" ] || fail "real dir replaced"
echo "install tests: PASS"
