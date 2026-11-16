---
name: team-ideate
description: Use when the owner wants new feature or product-enhancement ideas for the current product — runs the PM agent and lists the ideas to pick from. Also use to reject an idea.
metadata:
  kind: workflow
---

# team-ideate `[expand|hold|reduce]` · `team-ideate reject <slug>`

1. Needs `.agent-team/project.md` (else: "run team-init first"). The checkout must be on the default branch (`D=$(agent-team default-branch)`); if not, stop and tell the owner. `git pull --ff-only` (if it can't fast-forward, stop).
2. **Reject:** for `reject <slug>`, run `agent-team idea <slug> --set rejected`, then commit and push as in steps 4–5, and stop. The PM never re-proposes rejected ideas.
3. Dispatch the `pm` role in **ideation mode** on the tier from `agent-team tier pm-ideate --tool <tool>`, with the mode the owner named (default `hold`). Use the dispatch notes in the `team-build` skill's `references/` for your tool.
4. Commit only the ideas file: `git add .agent-team/ideas.md && git commit -m "docs: update ideas" -- .agent-team/ideas.md`. Docs only — anything else the owner has staged stays uncommitted.
5. `git push origin $D`. If it's rejected because `$D` is protected: `git push origin HEAD:refs/heads/agent-team/meta`, open (or reuse) a PR from `agent-team/meta` into `$D` titled "agent-team: ideas", and mention it. team-build finds ideas on `agent-team/meta` too, so the owner can pick before merging it.
6. Show the owner the new ideas as a short list (slug, title, value/effort), best first. Mention any earlier idea that has a `feature/<slug>` branch as in progress.
7. End with: "Pick one and run `team-build <slug>`, or `team-ideate reject <slug>`." That pick is Gate 1 — don't start building.

Never pick an idea for the owner, and never start team-build yourself.
