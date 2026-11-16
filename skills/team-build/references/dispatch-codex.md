# Dispatch in Codex

`install.sh` writes three profiles to `~/.codex/config.toml`: `at-deep`, `at-standard`, `at-fast` (models from this skill's `references/models.yaml` → `tools.codex`).

Run each role as its own non-interactive run **from the repo root** (the worktree lives inside it at `.agent-team/worktrees/<slug>`, so the sandbox can write both the worktree and the git metadata in `.git/`), with the sandbox set explicitly:

```bash
codex exec --profile at-<tier> -s workspace-write "Load and follow the <role> skill. Work in .agent-team/worktrees/<slug>. Slug: <slug>. Mode/round: <…>. Inputs: <paths>."
```

Read the role's output file afterwards; don't rely on the run's chat output. If profiles are missing, use `codex exec -m <model id from models.yaml> …`.
