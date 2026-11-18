# <Product name> — project context

<!-- Every agent-team role reads this first. Keep it to ~one screen (≤ 60 lines). Facts, not essays. -->

## Owner
<Name (and GitHub handle) of the person who picks features and merges PRs. Roles address them as "the owner".>

## Product
<What it is and what it does, 2–3 lines.>

## Users
<Who uses it and what they come to do.>

## Domain
<Domain terms an outsider would get wrong, one line each.>

## Stack
<Languages, frameworks, key services. Where the main code lives (paths).>

## Build & test
- Install: `<command>`
- Build: `<command>`
- Test: `<command>`   <!-- `none yet` if there are no tests; `agent-team test` runs Build and Test from here -->
- Run locally: `<command>`

## Conventions
<Code style, branching, commit style, folders to never touch.>
<!-- Optional: `- docs-push: pr-only` sends every agent-team docs push through an agent-team/meta PR, even if the default branch isn't protected. -->

## Positioning & voice
<One-line positioning. Tone of voice in 3 adjectives. Words to use / avoid.>

## Channels
<Where marketing goes: e.g. Instagram, LinkedIn, X, Play Store listing, website, email list.>

## Diff excludes
<!-- Optional. Extra glob patterns left out of review diffs (lockfiles, .agent-team/ and common generated code are already excluded), e.g.:
- `lib/l10n/generated/**`
-->
none

## Model overrides
<!-- Optional. Overrides the team-build skill's references/models.yaml for this project, e.g.:
- developer: standard   # this codebase is tricky; skip the fast tier
-->
none
