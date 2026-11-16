# Review <N>: <slug>

branch: `feature/<slug>` · reviewed up to: `<commit>` · since: `<commit or default branch>` · tier: <standard|deep> · tests: `agent-team test` → <pass|fail>

## Previous findings
<!-- "(first review)" if there's no previous review. Otherwise one line per Critical/Important finding still open in the previous review file. -->
- R1 — resolved — <evidence: file:line or test name>
- R3 — open — <what's still wrong>

## Strengths
- `path:line` — <what's done well, specifically>

## Pass 1 — Spec compliance
- R4 [critical] `path:line` — <what's wrong> — <why it matters / which AC> — <fix, if not obvious>

## Pass 2 — Plan & code quality
- R5 [important] `path:line` — …
- R6 [minor] `path:line` — …

## Pass 3 — Simplicity
- (none)

## Review focus & rulings
<!-- One line per plan `## Review focus` line and per `## Rulings` line: covered/sound, or the R<n> it became. -->
- <review focus line> — covered by `<test>` | R<n>
- T3 ruling — sound | R<n>

## Declined to judge
<!-- Every behaviour you considered and set aside as outside the spec or plan, with the reason. "(none)" if nothing. -->
- (none)

## Verdict
APPROVED | CHANGES REQUESTED — <one line; list the Critical/Important ids still blocking>
