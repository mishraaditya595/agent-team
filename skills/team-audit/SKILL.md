---
name: team-audit
description: Use when the owner wants the codebase audited for bugs, security issues, missing tests, tech debt, dependency or tooling problems, or grounded direction — runs the Tech Lead in audit mode and turns the best findings into ideas to pick from.
metadata:
  kind: workflow
---

# team-audit `[quick|deep] [<category>]`

Finds what's worth fixing across the codebase and adds the best of it to `ideas.md`, so it goes through the same Gate 1 → `team-build` flow as any feature. Nothing is fixed here.

1. Needs `.agent-team/project.md` (else: "run team-init first"). The checkout must be on the default branch (`D=$(agent-team default-branch)`); if not, stop and tell the owner. `agent-team pull`; if it fails, stop and show the owner its message.
2. **Level and scope.** `quick`, `deep` or neither (= `standard`). A category (`correctness`, `security`, `performance`, `tests`, `tech-debt`, `dependencies`, `dx`, `docs`, `direction`) narrows the audit to that one.
3. **Report file.** `agent-team audit-path` prints `path: <report path>` — the next free `.agent-team/audits/<date>[-n].md`, counting reports here, on `$D` and on `agent-team/meta` — and one `earlier: …` line per earlier report. Never pick the name yourself, and never overwrite an earlier audit.
4. **Dispatch** the `tech-lead` role in **audit mode** on the tier from `agent-team tier tech-lead-audit --tool <tool>` (`tech-lead-audit-quick` for `quick`), using the dispatch notes in the `team-build` skill's `references/`. Pass: the level, the category (if any), the report path, the `earlier:` list, and today's date for the `## <date> — mode: audit` heading in `ideas.md`.
5. **Commit and push only these:** `agent-team docs-commit -m "docs: audit" --title "agent-team: audit" .agent-team/audits .agent-team/ideas.md` (same rules as `team-ideate`: a temporary worktree, pushed to `$D` or to the `agent-team/meta` PR).
6. **Report** to the owner: the new ideas (slug, title, value/effort), best first; how many findings were found and rejected; what wasn't audited; the report path. End with: "Pick one and run `team-build <slug>`, or `team-ideate reject <slug>`."

That pick is Gate 1 — don't start building.

## Never

- Never edit code, fix a finding, or start `team-build` — the audit only advises.
- Never pick an idea for the owner.
- Never copy a secret's value into the report, an idea or a message — location and credential type only.
