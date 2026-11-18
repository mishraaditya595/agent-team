# Audit <YYYY-MM-DD>

level: quick|standard|deep · categories: <all | list> · commit: `<short sha>` · tier: <deep|standard>

## Not audited
<!-- What this level or category choice left out, so nobody assumes it was checked. -->
- <area or category> — <why>

## Findings
<!-- Vetted findings only, best leverage first. Full entries (Finding format in references/audit-playbook.md) below the table. -->
| A# | Finding | Category | Impact | Effort | Risk | Confidence | Evidence |
|----|---------|----------|--------|--------|------|------------|----------|
| A1 | … | security | … | S | LOW | HIGH | `path:line` |

### A1 [<category>] <title>
- Evidence: …
- Impact: …
- Effort: …
- Risk: …
- Confidence: …
- Fix sketch: …

## Direction
<!-- 2–4 grounded options for where the product could go next, each with evidence and trade-offs in 2–3 sentences. Not ranked against the findings. -->
- A<n> <title> — <evidence> — <trade-offs>

## Sent to ideas
<!-- Up to 5, best leverage first: the A# and the slug it became in .agent-team/ideas.md. -->
- A1 → `<slug>`

## Considered and rejected
<!-- Everything vetted out or judged not worth doing, one line each, so the next audit skips it. "(none)" if nothing. -->
- <finding> `path:line` — <by design | wrong evidence | duplicate | already in ideas | not worth doing> — <one line why>
