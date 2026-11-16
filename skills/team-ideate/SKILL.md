---
name: team-ideate
description: Use when the owner wants new feature or product-enhancement ideas for the current product, has an idea of their own to add ("team-ideate add …"), or wants to reject an idea — runs the PM agent and lists the ideas to pick from.
metadata:
  kind: workflow
---

# team-ideate `[expand|hold|reduce]` · `team-ideate add "<idea>"` · `team-ideate reject <slug>`

1. Needs `.agent-team/project.md` (else: "run team-init first"). The checkout must be on the default branch (`D=$(agent-team default-branch)`); if not, stop and tell the owner. `agent-team pull` (instead of `git pull`: it first puts back any doc copy `docs-pull` wrote that nobody edited, then pulls `--ff-only` and brings in docs still waiting on an `agent-team/meta` PR). If it fails, stop and show the owner its message.
2. Pick the action:
   - **Reject** (`reject <slug>`): `agent-team idea <slug> --set rejected`, then commit and push (step 3), and stop. The PM never re-proposes rejected ideas.
   - **Add the owner's idea** (`add "<idea>"`, or the owner describes an idea and wants it built): dispatch the `pm` role in **intake mode** on the tier from `agent-team tier pm-intake --tool <tool>`, passing the owner's words verbatim (and any file or link they gave). It appends one entry, or reports that the idea already exists.
   - **Brainstorm** (default): dispatch the `pm` role in **ideation mode** on the tier from `agent-team tier pm-ideate --tool <tool>`, with the mode the owner named (default `hold`).
   Use the dispatch notes in the `team-build` skill's `references/` for your tool.
3. Commit and push only the ideas file: `agent-team docs-commit -m "docs: update ideas" --title "agent-team: ideas" .agent-team/ideas.md`. `agent-team docs-commit` commits from a temporary worktree — never on your local default branch — and pushes to `$D`, or, if `$D` is protected or an `agent-team/meta` PR is still open, to `agent-team/meta`, opening or reusing its PR. If it went to `agent-team/meta`, mention the PR; team-build finds ideas there too, so the owner can build before merging it.
4. Report:
   - **Add:** the slug, title, value/effort and the PM's open questions (at most two), then: "Run `team-build <slug>` to build it." If the PM found the idea already exists, give that slug and its status instead.
   - **Brainstorm:** the new ideas as a short list (slug, title, value/effort), best first; mention any earlier idea that has a `feature/<slug>` branch as in progress. End with: "Pick one and run `team-build <slug>`, or `team-ideate reject <slug>`."
   That pick is Gate 1 — don't start building.

Never pick an idea for the owner. Don't start team-build yourself — except when the owner, in this same request, added their own idea and asked for it to be built ("add … and build it"): that is their Gate 1 pick, so continue with the `team-build` skill for the new slug.
