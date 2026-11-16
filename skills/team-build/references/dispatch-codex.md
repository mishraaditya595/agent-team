# Dispatch in Codex

`install.sh` writes three profiles to `~/.codex/config.toml`: `at-deep`, `at-standard`, `at-fast` — model and `model_reasoning_effort` from this skill's `references/models.yaml` (`tools.codex` and `effort`). `agent-team tier … --tool codex` tells you which.

Run each role as its own non-interactive run **from the repo root** (the worktree lives inside it at `.agent-team/worktrees/<slug>`, so the sandbox can write both the worktree and the git metadata in `.git/`), with the sandbox set explicitly:

```bash
codex exec --profile at-<tier> -s workspace-write --json \
  "Load and follow the <role> skill. Worktree: .agent-team/worktrees/<slug>. Slug: <slug>. Mode/round: <…>. Tasks: <…>. Since: <…>. Inputs: <paths>." \
  | tail -n 5
```

- Read the role's output file afterwards; don't rely on the run's chat output.
- **Usage:** with `--json` the last events include a `turn.completed` event whose `usage` has the token counts; pass the total to `agent-team log --tokens`. (Check the event name with your Codex version if it differs.)
- If the profiles are missing, use `codex exec -m <model> -c model_reasoning_effort=<effort> …` with the values `agent-team tier` printed.
