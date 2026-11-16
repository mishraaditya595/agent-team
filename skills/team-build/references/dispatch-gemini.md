# Dispatch in Gemini CLI

Run each role as its own headless run from the repo root, with the model from `agent-team tier … --tool gemini` (this skill's `references/models.yaml` → `tools.gemini`):

```bash
gemini -m <model id> --approval-mode auto_edit --skip-trust --output-format json \
  -p "Load and follow the <role> skill. Worktree: .agent-team/worktrees/<slug>. Slug: <slug>. Mode/round: <…>. Tasks: <…>. Since: <…>. Inputs: <paths>."
```

- **Approvals:** headless runs can't answer prompts. `auto_edit` approves file edits only; the git, `agent-team` and test commands a role runs must be allowed by Gemini's policy engine — add rules for `agent-team`, the git/`gh` commands in team-init's `references/claude-settings.json`, and the project's build/test commands, per the current Gemini CLI docs. Don't use `--approval-mode yolo` outside a container or throwaway VM.
- `--skip-trust` lets a headless run work in a folder that isn't in Gemini's trusted-folders list.
- Read the role's output file afterwards. The JSON output's `stats` include token counts; pass the total to `agent-team log --tokens`.
