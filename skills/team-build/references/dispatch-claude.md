# Dispatch in Claude Code

Run each role as a **subagent** (Task/Agent tool) so it gets a fresh, lean context:

- `subagent_type`: the plugin's agent for the role (`pm`, `tech-lead`, `developer`, `reviewer`, `qa`, `marketing` — defined in `agents/`, each already pinned to its default model).
- `model`: pass only when escalating or overriding (e.g. `sonnet` for a developer task tagged `[standard]`, `opus` for a deep review).
- Prompt: "Load and follow the `<role>` skill. Slug: `<slug>`. Worktree: `<path>`. Mode/round: `<…>`. Inputs: `<paths>`." Paths, not pasted contents.

Without the plugin's agents installed, use a general-purpose subagent with the same prompt and the `model` set from `config/models.yaml` (`tools.claude`).
