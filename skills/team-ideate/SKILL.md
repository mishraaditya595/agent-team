---
name: team-ideate
description: Use when Adi wants new feature or product-enhancement ideas for the current product — runs the PM agent and lists the ideas for him to pick from.
metadata:
  kind: workflow
---

# team-ideate `[expand|hold|reduce]`

1. Needs `.agent-team/project.md` (else: "run team-init first").
2. Dispatch the `pm` role in **ideation mode** on the `deep` tier, with the mode Adi named (default `hold`). Use the dispatch notes in the `team-build` skill's `references/` for your tool.
3. Commit only the ideas file, on the default branch. If the checkout isn't on the default branch, stop and tell Adi. `git add .agent-team/ideas.md && git commit -m "docs: update ideas" -- .agent-team/ideas.md`, then push. Docs only — anything else Adi has staged stays uncommitted.
4. Show Adi the new ideas as a short list (slug, title, value/effort), best first.
5. End with: "Pick one and run `team-build <slug>`." That pick is Gate 1 — don't start building.

Never pick an idea for Adi, and never start team-build yourself.
