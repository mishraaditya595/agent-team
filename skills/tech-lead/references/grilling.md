# Grilling the spec

Adapted from mattpocock/skills `grilling` (MIT). Before you plan, interview the PM until nothing about *what* to build is silently assumed. You ask; the PM answers. Every question costs a dispatch, so ask only what changes the plan.

## The design tree

Read `spec.md` and the code it touches, then map the open decisions as a **design tree**: each decision branches into the decisions that depend on it ("does a guest see saved items?" → "where are a guest's items stored?").

A decision is open when the spec, `project.md` and the code together don't settle it, *and* a different answer would change the plan — the files, the data, the tests, or what the user sees. Typical branches:

- who exactly can do this, and what everyone else sees;
- empty, first-run, error and offline states;
- limits: how many, how long, how big;
- what happens to existing data and existing users;
- what the spec's words mean when they could mean two things;
- the edges of scope: what's in and what's out.

**Facts are yours, decisions are the PM's.** If the code, the docs or the git history can answer it ("is there a cache already?", "which date library?"), look it up yourself and never ask it.

## Rounds

The **frontier** is every open decision whose prerequisites are already settled — the questions you can ask now without guessing at answers you haven't heard. A question that depends on another question still open in this round waits for a later round.

Each round:
1. Recompute the frontier from the answers so far.
2. Append `## Round <n>` to `grill.md` (`references/grill-template.md`) with **the whole frontier**: numbered `G<n>` (numbering continues across rounds), each with the question, the choices when they can be named, and your **recommended answer** with its reason. Word each question so "yes" accepts the recommendation.
3. Stop and hand back; the PM answers in the file.

**Cap: 3 rounds.** If decisions are still open after round 3, write them in a final round marked `owner` yourself — the owner settles them.

## Done

The grill is done when the frontier is empty: every branch visited, nothing left silently assumed, no `owner` answer pending. Then:

1. Add `## Decisions` to `spec.md`: one line per `G<n>` — `- G<n> (answered|assumed|owner): <decision> — <source or reason>`.
2. Don't change the spec's scope or acceptance criteria yourself. If an answer adds or removes behaviour, it's an `owner` answer and the owner has already settled it; reflect it as a decision line.
3. Plan from the spec *with* its decisions.

A spec with nothing open is fine: write `## Round 1` with `(no open decisions)`, add `## Decisions` with `- none`, and go straight to the plan.
