# Dispatch in Codex

`install.sh` writes three profiles to `~/.codex/config.toml`: `at-deep`, `at-standard`, `at-fast` (models from `config/models.yaml` → `tools.codex`).

Run each role as its own non-interactive run from the worktree:

```bash
codex exec --profile at-<tier> "Load and follow the <role> skill. Slug: <slug>. Mode/round: <…>. Inputs: <paths>."
```

Read the role's output file afterwards; don't rely on the run's chat output. If profiles are missing, use `codex exec -m <model id from models.yaml> …`.
