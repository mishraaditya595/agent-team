# Plan checklist

Adapted from gstack's eng-manager plan review (garrytan/gstack, MIT) and the obra/superpowers `writing-plans` self-review (MIT). Every item gets a yes, or a fix to the plan.

## Self-review (read the spec again with fresh eyes)

1. **Spec coverage** — every AC and every `## Decisions` line maps to at least one task, and every task maps to one. A requirement with no task gets a task.
2. **Step scan** — every task block lets the developer write exactly one reasonable thing. A line that decides nothing ("handle errors", "add tests") is a gap; a function body the signature and test already determine is a transcript. Fix both.
3. **Name consistency** — functions, types and fields named in one task's Interfaces are spelled the same everywhere they're used.
4. **Review focus** — for every input or failure mode the spec implies, some task's test exercises it; the uncovered ones most likely to bite are listed in `## Review focus`, each with a test added to its owning task.
5. **Proportion** — the plan is shorter than the code it describes. If code blocks are most of it, replace bodies with signatures and assertions.

## Engineering checks

- Every task names its files; no task says "and related files".
- Every task starts with a failing test, with its run command and expected result.
- Data flow covers where the data is read, written and shown.
- Failure modes: network down, empty data, bad input, permission denied — each has a behaviour or is out of scope.
- Data migrations: none, or a migration task with a rollback note.
- `## Security touchpoints` (auth, payments, personal data, secrets, migrations): listed, or exactly `none`. Any listed → the review runs on the `deep` tier.
- `qa-ui:` in the header is `yes` only if some AC can only be checked through the UI.
- YAGNI ladder applied; any new dependency has a reason.
- The test command is exact, runnable from the repo root, and matches `project.md` `## Build & test`.
- Nothing in the plan repeats a mistake listed in `.agent-team/lessons.md`.
- Tasks tagged `[fast]` really are mechanical; `[standard]` ones say why.
