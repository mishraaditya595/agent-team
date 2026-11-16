# Plan: <title>

spec: `.agent-team/features/<slug>/spec.md` · modelled on: <existing feature/path> · qa-ui: yes|no

<!-- qa-ui: yes if any AC can only be checked by driving the UI (browser, emulator); QA then runs on the standard tier. -->

## Approach
<2–5 lines: the shape of the solution and why it fits this codebase. YAGNI ladder rung used for each new piece.>

## Data flow
<Where data comes from, how it moves, where it's stored. A small ASCII diagram if it helps.>

## Edge cases
- <Input/state> → <expected behaviour>

## Security touchpoints
none
<!-- Or a list: auth, payments, personal data, secrets, data migrations. Anything listed → the review runs on the deep tier. -->

## Test plan
- Command: `<exact test command>`
- New tests: <file paths and test names, mapped to ACs>
- Manual ACs: none | <AC ids QA can't exercise here, and why>
- If no tests exist yet: <framework, location, how to run>

## Tasks
- [ ] T1 [fast] <title> — files: <path>, <path> — maps to: AC1
- [ ] T2 [standard] <title> — files: <path> — maps to: AC2 — why standard: <few words>

## Out of scope for the developer
- <Tempting change not to make.>
