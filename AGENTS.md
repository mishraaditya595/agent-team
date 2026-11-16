# agent-team

This repo is a portable AI product team: PM, Tech Lead, Developer, Reviewer, QA and Marketing roles written as Agent Skills. Skills live in `skills/`; each is a `SKILL.md` with portable frontmatter only. Model tiers live in `config/models.yaml`.

## Rules for any agent working here or using these skills

- **Think before coding** — restate the task, name assumptions, read before editing.
- **Simplicity first** — least code that meets the acceptance criteria; no speculative abstractions.
- **Surgical changes** — touch only what the task needs; note unrelated problems instead of fixing them.
- **Goal-driven execution** — know the passing test before starting; show evidence before claiming done.
- **YAGNI ladder** — reuse existing code → stdlib/native → small new code → new dependency (with a reason in `plan.md`).

Full text: `skills/engineering-guidelines/SKILL.md`.

## Working on this repo

- Run `python3 -m pytest -q` and `python3 scripts/validate.py .` before committing.
- Never put tool-specific frontmatter (e.g. `model:`) in `skills/**/SKILL.md`; tool-specific bits go in `agents/`, `.claude-plugin/` or `scripts/install.sh`.
