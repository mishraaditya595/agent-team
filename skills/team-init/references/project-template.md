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

<!-- Workspace with product repos cloned inside it (gitignored)? team-init adds `## Repos` (one `### <path>` block per repo, with its own Install/Build/Test lines) and `## Cross-repo rules` (`- Order: …` plus free text). -->

## Intent docs
<!-- Paths of docs that record decisions and direction: ADRs (docs/adr/, docs/decisions/), PRDs or specs, PRODUCT.md, CONTEXT.md, DESIGN.md. Roles read these before proposing or flagging anything; a decision recorded here is settled. -->
none

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
