# Multi-repo workspaces — design

Issue: [#8](https://github.com/mishraaditya595/agent-team/issues/8). Status: approved approach A1, design for review.

## Intent

Some products are several repos cloned (gitignored) inside one parent **workspace** repo that holds the cross-repo docs and agent memory. Most real features span repos (backend endpoint + app consumer + admin UI) and have ordering rules (backend ships first, older app builds keep working). agent-team today assumes one product == one repo: ideation cites the workspace's own `git log`, and `team-build` creates a worktree with no product code in it.

Goal: run agent-team from the workspace, keep **all agent-team state in the workspace**, and have a cross-repo feature end as one PR per touched product repo, with no hand-editing.

## Goals

1. `team-ideate` in a workspace cites evidence from each product repo's history and labels each idea with the repos it touches.
2. `team-build <slug>` in a workspace builds a cross-repo feature in one run and ends with one green PR per touched product repo (plus one workspace PR carrying the artifacts), cross-linked, with merge order stated.
3. `docs-push: pr-only` makes every agent-team docs push go via `agent-team/meta` + PR, even when the default branch isn't protected.

## Non-goals

- Monorepos, git submodules, or repos outside the workspace folder.
- Enforcing merge order on GitHub (the owner merges at Gate 2, as today; agent-team only states the order).
- An `idea export` command or per-product `.agent-team/` (option 3 in the issue; rejected — state stays in the workspace).
- Cross-repo integration test runners. Each repo runs its own Build/Test.
- Code or doc changes to the workspace itself during `team-build` (owner decision). Every plan task lives in exactly one product repo; the workspace branch carries only agent-team artifacts. Cross-repo docs stay owner-maintained.

## Anti-goals (failure even if it works)

- Any behaviour change for a project whose `project.md` has no `## Repos` section.
- Any agent-team command pushing to a default branch when `pr-only` is set.
- Product repos receiving `.agent-team/`, `.claude/` or other agent-team files.

## Constraints

- `agent_team.py` stays stdlib-only, single file.
- `skills/**/SKILL.md` keep portable frontmatter only.
- Lease, stage machine, stop rules and the two owner gates are unchanged.
- `python3 -m pytest -q` and `python3 scripts/validate.py .` pass.

## Approaches considered

- **A1 — one run, nested worktrees mirroring the workspace (picked).** The workspace worktree on `feature/<slug>` holds spec/grill/plan/status/reviews as today; each touched product repo gets its own worktree on `feature/<slug>` *inside it*, at the same relative path as in the workspace. One reviewer/QA sees both sides of the cross-repo contract. Cost: ~8 helper commands loop over repos.
- **A2 — one pipeline per repo, in order.** Smaller CLI change (`--repo` flag), but the backend PR must merge before the app run starts (an owner gate mid-feature) and the contract is reviewed in halves. Rejected by the owner.
- **Export to product repo (issue option 3).** Needs `team-init` in every product repo and splits state. Rejected: state lives in the workspace.
- **Keep `status.md` uncommitted in the workspace checkout.** Breaks the lease (the lease is a push of `status.md`). Dropped.

## Delivery order (three independent PRs)

1. `docs-push: pr-only` — smallest, independent.
2. Workspace config + ideation.
3. Workspace build (A1).

Each part leaves single-repo behaviour byte-identical.

---

## Part 1 — `docs-push: pr-only`

- Setting: a line `- docs-push: pr-only` in `project.md` `## Conventions`. Absent or any other value → today's behaviour.
- `cmd_docs_commit`: when set, call `_docs_attempt(..., to_meta=True)` from the first attempt. That is the only path that pushes to a default branch today (`agent_team.py` `_docs_attempt`; feature pushes go to `feature/*`, cleanup only deletes branches), so this satisfies the acceptance line.
- `project.md` itself is read via `read_doc` (newest of checkout / `agent-team/meta`), so a freshly set `pr-only` on an unmerged meta PR still applies.
- Mention the setting in `project-template.md` (commented example) and `team-init` step 5 wording.
- Test: with `pr-only` and an unprotected default branch, `docs-commit` pushes to `agent-team/meta` and opens/reuses the PR; without it, behaviour unchanged.

## Part 2 — Workspace config + ideation

### `## Repos` in `project.md`

Workspace mode ⇔ `project.md` has a `## Repos` section with at least one `### <path>` subsection. Each `### <path>` block uses the same `- Build: \`cmd\`` lines as `## Build & test`. `section()` stops only at `## `, so the builder splits `## Repos` into `### ` blocks and generalises `project_command()` to take a block of text (small refactor):

```markdown
## Repos
### app-backend
- Role: REST API + admin endpoints
- Branch: main            <!-- optional; default: that repo's origin/HEAD -->
- Install: `npm ci`
- Build: `npm run build`
- Test: `npm test`
### app-flutter
- Role: mobile app (consumes app-backend)
- Test: `flutter test`

## Cross-repo rules
- Order: app-backend, app-website, app-flutter   <!-- merge/ship order; first = earliest -->
- app-flutter: builds already in stores must keep working against the new backend (additive API changes only).
```

- `<path>` is relative to the workspace root and must be a git repo with a GitHub remote.
- Workspace-level `## Build & test` stays (usually `none`).
- `## Cross-repo rules`: `Order:` line is parsed (helper uses it for PR merge order); every other line is free text for the PM, Tech Lead and Reviewer.
- Line budget: ≤ 60 lines plus ≤ 8 per listed repo (my call; the 60-line cap can't hold three stacks).

### Helper

- `repos()` → ordered list of `(path, role, branch, commands)` from `## Repos`, ordered by `Order:` then listing order; `[]` in single-repo mode. Every workspace code path branches on `repos()` being non-empty.
- `agent-team repos` prints them (path, default branch, last commit) — used by skills, and as a cheap check that each path is a git repo.

### `team-init`

- Step 3: detect nested repos (`git -C <dir> rev-parse --show-toplevel` equals `<dir>` for each top-level dir, depth 1) that are gitignored by the workspace. If any, draft `## Repos` (one subsection per repo, commands filled from that repo's manifests/CI like today) and `## Cross-repo rules` (`unknown — owner to fill`).
- Nothing is written into product repos. `.agent-team/` and `.claude/settings.json` are committed to the workspace (that is where Claude is launched and where memory lives). Settings get `Bash(<cmd>:*)` entries for every repo's commands.
- `agent-team upgrade` adds `## Repos` / `## Cross-repo rules` only when nested repos are detected. This needs a special case: `add_missing_sections()` adds every template heading a `project.md` lacks, so these two must not be plain headings in `project-template.md` (keep them as a commented example) or be skipped explicitly — otherwise every single-repo project gains them.

### PM ideation

- `pm` SKILL.md ideation mode: in workspace mode, evidence is `git -C <path> log --oneline -30` per listed repo (not the workspace log), plus each repo's README and main routes/screens.
- `ideas-template.md`: optional `**Repos:** app-backend, app-flutter` line per idea; required in workspace mode, omitted in single-repo mode. Intake mode fills it too.
- `idea_info()` exposes `repos` (list, empty if absent).

---

## Part 3 — Workspace build (A1)

### Layout

```
workspace/.agent-team/worktrees/<slug>/      # workspace worktree, branch feature/<slug> (artifacts, status, lease)
├── .agent-team/features/<slug>/…
├── app-backend/                              # worktree of app-backend, branch feature/<slug> off its origin/<branch>
└── app-flutter/                              # worktree of app-flutter, branch feature/<slug>
```

- Product worktrees are created with `git -C <workspace>/<path> worktree add -b feature/<slug> <wt>/<path> origin/<branch>`. They are registered in the product repo's own `.git`, so cleanup goes through that repo.
- The workspace worktree ignores them through the workspace `.gitignore` (which is checked out at the worktree root, so `/app-backend/` matches `<wt>/app-backend`). `team-init`/`upgrade` must ensure each repo path is gitignored; the helper refuses to create a product worktree whose path the workspace doesn't ignore (`git check-ignore`).
- Roles see the same relative paths as in the real workspace, so plan `files:` paths like `app-backend/src/routes.ts` work unchanged.

### Which repos are touched

- Step 1 (new run): create product worktrees for the idea's `**Repos:**` line.
- `agent-team repos <slug> --ensure` creates each product worktree from `origin/feature/<slug>` when that branch exists (resume, other machine), else `-b feature/<slug>` off `origin/<branch>`. team-build step 0 resume calls it after re-adding the workspace worktree.
- `lease acquire` also fast-forwards every product worktree to its `origin/feature/<slug>`; a product branch that has diverged fails the acquire exactly like the workspace branch does today.
- After plan: touched repos = repos that are a path prefix of any task's `files:` entries. `agent-team repos <slug> --ensure` creates missing product worktrees (and pushes their branches); repos with no tasks keep their worktree but are dropped from PR/CI if their diff is empty at the pr stage.
- `status.md` gains `repos: app-backend app-flutter` (touched, in order) and `repo_prs: app-backend#12 app-flutter#40` (or `none`). Existing `pr` is the workspace PR.

### Helper commands that become repo-aware

All loop over `status.md` `repos` (in order); with no `repos` key they behave exactly as today.

| Command | Workspace behaviour |
|---|---|
| `test` | Runs the workspace `## Build & test` first if not `none`, then each repo's Build/Test in `<wt>/<path>`; cache key = joined per-repo `code_key`s + command hash; first failure reports `fail(<path>:test)`. |
| `diff` | Per-repo diffs against that repo's `origin/<branch>`, each prefixed with the repo path (paths shown as `app-backend/…`). Excludes: global `## Diff excludes` + defaults. |
| `diff --since` | In workspace mode `last_reviewed_commit` holds one SHA per repo: `app-backend:abc123 app-flutter:def456`. The orchestrator sets it with `agent-team heads <slug>` (new, prints that string); `diff --since` parses it. Single-repo: a plain SHA as today. |
| `diffstat` / tier rule | Summed across repos. |
| `sync` | Merges each repo's own `origin/<branch>`; conflict exit 2 names the repo. Workspace worktree syncs its default too. |
| `push` | Pushes each product `feature/<slug>`, then the workspace branch (the lease lives there, so it goes last). Exit 3 semantics unchanged per branch. |
| `ci` | Checks each `repo_prs` entry and the workspace `pr`; `pass` only if all pass/none; `fail` lists `<repo>#<n>` with failing checks. |
| `pr-body` | `--repo <path>` prints a product PR body: summary, link to the workspace PR for artifacts, "Part of <slug>: <other PRs>", and "Merge order: app-backend#12 → app-flutter#40". Without `--repo`: the workspace PR body as today plus the list of product PRs. |
| `cleanup` | Removes product worktrees/branches via each repo, then the workspace one; same safety checks per repo. |

### team-build skill changes (workspace mode only)

- Step 1: create the workspace worktree as today, then product worktrees (above).
- Plan stage: Tech Lead reads `## Repos` and `## Cross-repo rules`; every task's `files:` live in exactly one product repo (a task with workspace-level paths is a `## Spec problems` entry, which stops the run); tasks for an earlier repo in `Order:` come first. Then `agent-team repos <slug> --ensure`.
- Developer: commits inside the product worktree for the task's repo (each product worktree is its own git checkout). `status.md` commits stay in the workspace worktree.
- Reviewer: reads `## Cross-repo rules` and checks them as findings (e.g. non-additive API change breaking shipped app builds → Critical).
- pr stage: one `gh pr create -R <owner/repo>` per touched repo with a non-empty diff, in `Order:`; then the workspace PR (artifacts). Set `repo_prs` and `pr`.
- pr-open message: lists PRs in merge order; workspace PR last.
- Stop: draft/undo-ready applies to every PR that exists.

### team-wrap / team-status

- `team-wrap` treats the feature as merged only when every `repo_prs` entry **and** the workspace `pr` are merged (it reads `status.md` from the workspace default branch, so the workspace PR must be in). Today wrap runs `gh pr view <pr> --json state,mergedAt` itself; it now loops that over each PR with `-R <repo>`. Some merged, some not → wrap stops and lists the unmerged ones.
- `summary` shows `repo_prs` in the `pr` column.

## Testing

- Every part: a test that a single-repo fixture produces identical output/commands to today.
- Part 3 e2e fixture: a workspace repo + two bare-remote product repos nested and gitignored; run worktree creation, `test`, `diff`, `sync`, `push`, `pr-body --repo`, `cleanup` (gh calls stubbed as existing tests do).

## Left to the builder

- Function boundaries inside `agent_team.py`, and whether `repos()` returns tuples or dicts.
- Exact wording of skill text and template comments.
- How the e2e fixture stubs `gh`.

## Calls I made (owner to check)

- Workspace mode is detected only from `## Repos`; no flag.
- Repo of a task is derived from its `files:` path prefix, not a new `[repo:]` tag.
- `project.md` line budget grows by ≤ 8 lines per repo.
- Workspace PR (artifacts) is opened last and merged last; it counts for CI and for wrap like any product PR.
- `last_reviewed_commit` becomes a per-repo list in workspace mode, set via a new `agent-team heads <slug>`.
- Resume and lease cover product branches too; a diverged product branch stops the run like today.
- Workspace `## Build & test` still runs in workspace mode when it isn't `none`.
- Repos the plan doesn't touch get no PR, even if listed on the idea.
- Merge order is stated in PR bodies, not enforced.
