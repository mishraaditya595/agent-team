# Dispatch in Claude Code

Run each role as a **subagent** (Task/Agent tool) so it gets a fresh, lean context:

- `subagent_type`: the plugin's agent for the role (`pm`, `tech-lead`, `developer`, `reviewer`, `qa`, `marketing` — defined in `agents/`, each already pinned to its default model). If it isn't found by its bare name, use the namespaced form `agent-team:<role>`.
- `model`: pass only when `agent-team tier` picks a tier other than the agent's default (e.g. `sonnet` for a `[standard]` developer batch or a fix, `opus` for a deep review).
- Prompt — paths, not pasted contents:
  `Load and follow the <role> skill. Slug: <slug>. Worktree: .agent-team/worktrees/<slug>. Mode/round: <…>. Tasks: <T2,T3 | findings R1,R4 | none>. Since: <commit | none>. Inputs: <paths>.`
- **Usage:** if the subagent's result reports token usage, pass it to `agent-team log --tokens`. Claude Code doesn't report cost per subagent; leave `--cost` out.

Without the plugin's agents installed, use a general-purpose subagent with the same prompt and the `model` from `agent-team tier … --tool claude` (this skill's `references/models.yaml`).
