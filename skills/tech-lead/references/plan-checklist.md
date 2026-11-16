# Plan checklist

Adapted from gstack's eng-manager plan review (garrytan/gstack, MIT). Every item gets a yes, or a fix to the plan.

- Every AC in the spec maps to at least one task, and every task maps to an AC.
- Every task names its files; no task says "and related files".
- Data flow covers where the data is read, written and shown.
- Failure modes: network down, empty data, bad input, permission denied — each has a behaviour or is out of scope.
- Data migrations: none, or a migration task with a rollback note.
- Security touchpoints (auth, payments, personal data, secrets): listed, or "none". Any listed → the review will run on the `deep` tier.
- YAGNI ladder applied; any new dependency has a reason.
- The test command is exact and runnable from the repo root.
- Tasks tagged `[fast]` really are mechanical; `[standard]` ones say why.
- The plan is shorter than the code it describes.
