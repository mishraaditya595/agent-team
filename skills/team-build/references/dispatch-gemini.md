# Dispatch in Gemini CLI

Run each role as its own headless run from the worktree, with the model from this skill's `references/models.yaml` → `tools.gemini`:

```bash
gemini -m <model id> -p "Load and follow the <role> skill. Slug: <slug>. Mode/round: <…>. Inputs: <paths>."
```

Read the role's output file afterwards.
