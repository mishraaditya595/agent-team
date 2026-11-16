# Dispatch anywhere else (fallback)

When the tool can't start a separate run on a chosen model, or this skill's `references/models.yaml` has no entry for it (`agent-team tier` prints `model=session`):

- Run the role in the current session: load its skill, do only that role's job, write its output file, then continue as the orchestrator.
- Log it with `agent-team log … --model session` and the note `intended=<tier> fallback`, so cost and quality can be checked later.
- Keep roles separated anyway: re-read only the role's inputs before each role, and don't let the reviewer rely on what you remember from implementing.
