# Upstream practices — Implementation plan

Spec: `docs/superpowers/specs/2026-11-16-upstream-practices-design.md` · Execution: inline · Test: `python3 -m pytest -q && python3 scripts/validate.py .`

- [ ] T1 Helper: `grill` stage + `grill_round` status key; `pr-body` lists `grill.md`, assumed decisions and Rulings — files: `skills/team-build/scripts/agent_team.py`, `skills/team-build/references/status-template.md`, `tests/test_agent_team.py`
- [ ] T2 Grill: tech-lead grill mode + `references/grilling.md` + `references/grill-template.md`; PM answer mode; `team-build` grill stage and stop/resume — files: `skills/tech-lead/**`, `skills/pm/SKILL.md`, `skills/team-build/SKILL.md`
- [ ] T3 Plans: plan template task blocks, Global constraints, Review focus, Rulings; checklist self-review; TDD rules — files: `skills/tech-lead/**`
- [ ] T4 Developer: executing discipline, Rulings, completion contract; `references/debugging.md` — files: `skills/developer/**`
- [ ] T5 Reviewer: severity, strengths, reasonable-user rule, review focus, rulings, declined-to-judge — files: `skills/reviewer/**`
- [ ] T6 Marketing: channel playbooks, no-AI-tells, topic mode in role + `team-market` — files: `skills/marketing/**`, `skills/team-market/SKILL.md`
- [ ] T7 NOTICE, README, content tests; full suite + validate

Each content change gets an assertion in `tests/test_content.py` first (red), then the edit (green).
