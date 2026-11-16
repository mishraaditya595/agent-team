# Upstream practices in the roles — Design

Date: 2026-11-16 · Owner: Adi · Status: agreed in conversation 2026-11-16 (Adi: "start the implementation")

## Intent

Make the existing roles sharper by folding in the working practices of a few proven skills — in our own words, as part of our skills, never as runtime dependencies or links the agents follow:

| Role | Practice adapted from |
|---|---|
| Tech Lead grills the PM before planning | mattpocock/skills `grilling` (via `grill-me`) |
| Tech Lead writes the plan | obra/superpowers `writing-plans`, with `test-driven-development` built into every task |
| Developer executes the plan | obra/superpowers `executing-plans` |
| Developer fixes anything | obra/superpowers `systematic-debugging` |
| Reviewer reviews | obra/superpowers `requesting-code-review` (its `code-reviewer.md`) |
| Marketing writes content | coreyhaines31/marketingskills (`social`, `content-strategy`, `community-marketing`, `copywriting`) |

## Goals

- Catch spec gaps before the plan is written, at the cost of at most three cheap rounds.
- Plans precise enough for a fast model to build without guessing.
- Fixes that address root causes, not symptoms.
- Reviews with calibrated severity that never drop a concern silently.
- Marketing drafts for Instagram, blog, LinkedIn and Reddit — for a shipped feature *or* for any idea, plan or topic Adi hands over.

## Non-goals / anti-goals

- No new human gates except where the grill hits a scope or user-visible decision (see below).
- No dependency on the upstream repos at runtime; nothing auto-posted.
- Not a token blow-up: grill rounds are capped, plans stay shorter than the code.

## Approaches

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Edit the existing role skills in place; add a `grill` stage to `team-build`; add a topic mode to `team-market` | One source of truth per role; small helper change |
| B | Add separate skills (`grill`, `debug`, …) the roles call | More files, roles depend on each other, and cheap models skip "also load X" instructions |
| C | Vendor the upstream skills unchanged | Their human-in-the-loop wording conflicts with our hands-off build; Adi asked for points, not copies |

**Who decides an open grill question** — Adi picked **C (mix)**: the PM answers what it can and may assume minor calls (listed in the PR); anything that changes scope or what users see stops the run for Adi.

## Design

### Grill stage (`spec → grill → plan`)
- The Tech Lead (grill mode) maps the spec's open decisions as a tree, looks up facts in code itself, and writes one round to `grill.md`: every question whose prerequisites are settled, numbered `G<n>`, each with a recommended answer.
- The PM (answer mode) answers each `G<n>` as **answered** (from spec/product), **assumed** (its call + one-line reason), or **owner** (changes scope or user-visible behaviour).
- Any `owner` → *Stop* (`stopped_at=grill`): draft PR, one line to Adi. He answers in `grill.md`; `team-build` resumes at `grill`.
- Max 3 rounds (`grill_round`); anything still open after round 3 becomes an `owner` question.
- Done → Tech Lead folds settled answers into `spec.md` `## Decisions`; the PR body lists every `assumed` decision.

### Plans (Tech Lead)
- Keep `- [ ] T<n> [tier] …` task lines (the helper batches on them); add a short block per task: files, Interfaces (consumes/produces), the failing test (name + assertions), run command + expected result.
- New `## Global constraints` and `## Review focus` (≤ 5 untested inputs or failure modes, each with a test added to its owning task).
- Self-review: spec coverage, step scan, name consistency, review focus, proportion.

### Developer
- Read the task block fresh; red → green → commit; compare every command to its expected result.
- Plan wrong → smallest spec-satisfying change, recorded in `plan.md` `## Rulings` as `T<n>: Ruling: <what> — <why> — <cost if wrong>`; the PR lists them.
- Completion contract: named tests exist, ran, final run passed, deviations ruled.
- Every fix follows the systematic-debugging phases (root cause → pattern → one hypothesis → failing test → one fix); 3 failed fixes → stop, it's a design problem.

### Reviewer
- Strengths first; issues as Critical / Important / Minor (Critical + Important block; Minor never does).
- Spec silence ≠ permission: judge by what a reasonable user expects.
- Check every `## Review focus` line and every Ruling; end with a `Declined to judge` list.

### Marketing
- Four channel playbooks (Instagram carousel + caption + visual brief, blog draft, LinkedIn post, Reddit value-first post per subreddit) plus a shared no-AI-tells check.
- Two modes: **feature** (after merge, as today) and **topic** (Adi gives an idea, plan or topic; drafts land in `.agent-team/marketing/<date>-<topic-slug>.md`).

## Left to the builder

File names inside `references/`, exact wording, test details.
