---
name: team-ideate
description: Use when the owner wants new feature or product-enhancement ideas for the current product, has an idea of their own to add ("team-ideate add …"), or wants to reject an idea — runs the PM agent and lists the ideas to pick from.
metadata:
  kind: workflow
---

# team-ideate `[expand|hold|reduce]` · `team-ideate add "<idea>"` · `team-ideate reject <slug>`

1. Needs `.agent-team/project.md` (else: "run team-init first"). The checkout must be on the default branch (`D=$(agent-team default-branch)`); if not, stop and tell the owner. `git pull --ff-only` (if it can't fast-forward, stop).
2. Pick the action:
   - **Reject** (`reject <slug>`): `agent-team idea <slug> --set rejected`, then commit and push (steps 3–4), and stop. The PM never re-proposes rejected ideas.
   - **Add the owner's idea** (`add "<idea>"`, or the owner describes an idea and wants it built): dispatch the `pm` role in **intake mode** on the tier from `agent-team tier pm-intake --tool <tool>`, passing the owner's words verbatim (and any file or link they gave). It appends one entry, or reports that the idea already exists.
   - **Brainstorm** (default): dispatch the `pm` role in **ideation mode** on the tier from `agent-team tier pm-ideate --tool <tool>`, with the mode the owner named (default `hold`).
   Use the dispatch notes in the `team-build` skill's `references/` for your tool.
3. Commit only the ideas file: `git add .agent-team/ideas.md && git commit -m "docs: update ideas" -- .agent-team/ideas.md`. Docs only — anything else the owner has staged stays uncommitted. (Nothing changed → skip the commit.)
4. `git push origin $D`. If it's rejected because `$D` is protected: `git push origin HEAD:refs/heads/agent-team/meta`, open (or reuse) a PR from `agent-team/meta` into `$D` titled "agent-team: ideas", and mention it. team-build finds ideas on `agent-team/meta` too, so the owner can build before merging it.
5. Report:
   - **Add:** the slug, title, value/effort and the PM's open questions (at most two), then: "Run `team-build <slug>` to build it." If the PM found the idea already exists, give that slug and its status instead.
   - **Brainstorm:** the new ideas as a short list (slug, title, value/effort), best first; mention any earlier idea that has a `feature/<slug>` branch as in progress. End with: "Pick one and run `team-build <slug>`, or `team-ideate reject <slug>`."
   That pick is Gate 1 — don't start building.

Never pick an idea for the owner. Don't start team-build yourself — except when the owner, in this same request, added their own idea and asked for it to be built ("add … and build it"): that is their Gate 1 pick, so continue with the `team-build` skill for the new slug.
