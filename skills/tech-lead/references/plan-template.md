# Plan: <title>

spec: `.agent-team/features/<slug>/spec.md` · modelled on: <existing feature/path> · qa-ui: yes|no · planned-at: <short sha of `git merge-base HEAD origin/<default>`>

<!-- qa-ui: yes if any AC can only be checked by driving the UI (browser, emulator); QA then runs on the standard tier. -->

## Approach
<2–5 lines: the shape of the solution and why it fits this codebase. YAGNI ladder rung used for each new piece.>

## Files
- `<path>` — create|modify — <its one job>

## Data flow
<Where data comes from, how it moves, where it's stored. A small ASCII diagram if it helps.>

## Global constraints
<!-- The spec's hard values, copied verbatim: limits, copy text, version floors, platform rules. Every task obeys these. "none" if there are none. -->
- <constraint>

## Edge cases
- <Input/state> → <expected behaviour>

## Security touchpoints
none
<!-- Or a list: auth, payments, personal data, secrets, data migrations. Anything listed → the review runs on the deep tier. -->

## Test plan
- Command: `<exact test command>`
- Manual ACs: none | <AC ids QA can't exercise here, and why>
- If no tests exist yet: <framework, location, how to run>

## Review focus
<!-- Up to 5 inputs or failure modes the spec implies but no test covers yet, most likely to bite a user first. Each one gets a test added to its owning task below. "none — checked" if you found none. -->
- <input or condition> → <what a reasonable user expects> — test in T<n>

## Tasks
- [ ] T1 [fast] <title> — files: <path>, <path> — maps to: AC1
  - Interfaces: consumes <none | T<n>'s `name(args) -> Type`> · produces `<name(args) -> Type>`
  - Failing test: `<test file>::<test name>` — asserts <exact values from the spec>
  - Run: `<command for this test>` · Expected: fails (<reason>) → passes after the change
  - Approach: <one line only if the signature and test leave a real choice>
- [ ] T2 [standard] <title> — files: <path> — maps to: AC2 — why standard: <few words>
  - Interfaces: …
  - Failing test: …
  - Run: … · Expected: …

## Out of scope for the developer
- <Tempting change not to make.>

## Rulings
<!-- The developer appends here when the plan turns out wrong: `- T<n>: Ruling: <what was decided> — <why> — <cost if wrong>`. Listed in the PR for the owner. -->
