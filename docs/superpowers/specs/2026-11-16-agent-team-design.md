# Agent Team — Design

Date: 2026-11-16 · Owner: Adi · Status: approved by Adi 2026-11-16 (QA agent added on approval)

## 1. Intent

Adi has several products that are already built, with very different domains and scopes. He wants AI to take them further as a small product team:

1. a **PM agent** brainstorms and proposes new features and product-level enhancements,
2. a **Tech Lead agent** plans the architecture and implementation for the chosen feature,
3. a **Developer agent** implements it,
4. a **Code Reviewer agent** reviews the implementation against *both* the product spec and the technical plan,
5. a **QA agent** tests the feature once code review passes, checking it against the spec's acceptance criteria,
6. a **Marketing agent** is triggered afterwards for outreach and marketing.

The agents must be **model-independent** (usable from Claude Code and Codex at minimum), **available on all of Adi's machines**, and **extensible**, because more roles will be added as needs and products grow.

## 2. Goals, non-goals, anti-goals

**Goals**
- One source of truth for every role, written once, usable from Claude Code and Codex (and other tools that support Agent Skills).
- Roles are generic. Everything specific to a project lives in that project's repo.
- Human approval at exactly two points: **product level** (which feature gets built) and **merge level** (merging the PR). Everything in between runs on its own.
- Work can be stopped and resumed on any machine, with any supported tool, from what's in the repo.
- Adding a new role means adding a folder. No existing role has to change.

**Non-goals (for v1)**
- Unattended or scheduled runs without a coding-agent CLI open (approach C, possible later).
- Calling model APIs directly or building a custom orchestrator.
- Auto-publishing marketing content to social platforms. The marketing agent produces drafts only.
- Multi-user or team permissions.

**Anti-goals (failure even if it "works")**
- The PM agent effectively deciding the roadmap. Nothing gets built without Adi picking it.
- Code reaching `main` without Adi's merge.
- Role logic duplicated per tool and drifting apart.
- Roles that only work well on one project because project specifics leaked into them.
- Over-built output: agents adding dependencies, abstractions or scope nobody asked for.
- A costly, token-hungry process: expensive models on routine work, or agents re-reading the whole repo at every stage.

## 3. Constraints

- Tools: Claude Code and Codex CLI today. Others (Gemini CLI, Cursor, Copilot CLI) may follow.
- **New, dedicated GitHub repo** (`agent-team`, name can change). The existing ADE repo is not used.
- Sync across machines through git and plugin marketplaces.
- Products differ widely (Flutter apps, backends, websites), so roles can't assume a stack.
- Artifacts are plain markdown in the project repo, so any model can read them.

## 4. Approaches considered

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | One repo of portable skills, with a thin manifest per tool | Single source of truth; small behavioural differences between tools |
| B | Separate native plugin per tool | Best per-tool features, but every role is maintained twice and the copies drift. Works against model independence |
| C | Own orchestrator script calling model APIs | Most model-independent, but rebuilds the file editing, testing and git handling that coding agents already provide; API costs instead of subscriptions |

Adi picked **A**: one source of truth, works with both tools he uses, and leaves C open for unattended runs later.

## 5. Research: what we borrow (all MIT-licensed)

| Source | What it is | What we take |
|---|---|---|
| **Agent Skills open standard** (agentskills.io) + `npx skills` (vercel-labs/skills) | One SKILL.md format read by Claude Code, Codex, Gemini CLI, Cursor, Copilot and others; a CLI that installs into each agent's folder | **Roles are standard SKILL.md files** using only the portable frontmatter (`name`, `description`). No custom ROLE.md format and no code-generation step |
| **obra/superpowers** | Brainstorm → write-plans → subagent-driven development, TDD, verification-before-completion; ships to Claude Code, Codex, Gemini, Cursor and more from one `skills/` folder | Packaging layout (one `skills/` dir + per-tool manifests). Per-task fresh subagents. **Two-stage review: spec compliance first, then code quality.** Plans with exact files and verification steps. "Evidence before claiming done." |
| **garrytan/gstack** | Role skills: `/plan-ceo-review` (finds the "10-star product"; expand / hold / reduce scope modes), `/plan-eng-review`, `/review` (paranoid staff engineer), `/ship`, `/retro`, `/autoplan` (runs the review chain and surfaces only taste decisions to the human) | PM ideation modes (expand / hold / reduce). Tech-lead plan checklist (data flow, edge cases, test plan, diagrams). Paranoid "bugs that pass CI" review lens. The idea that only taste decisions reach the human → our Gate 1 |
| **BMAD-METHOD** | Agile personas (Analyst, PM, Architect, Dev, QA) passing work through story files; "dev agents code, planning agents plan"; lean dev context | Hand-offs only through files. **Keep the developer's context lean**: it gets the plan and `project.md`, not the whole ideation history |
| **Karpathy guidelines** (forrestchang / multica-ai/andrej-karpathy-skills) | Four rules: think before coding, simplicity first, surgical changes, goal-driven execution | Always-on **engineering guidelines** shared by Developer and Reviewer, and shipped as an AGENTS.md / CLAUDE.md snippet |
| **DietrichGebert/ponytail** | Anti-over-engineering skill: reuse existing code, stdlib and native platform features first ("YAGNI ladder"); `ponytail-review` audits for over-engineering; installs on 12+ agents | YAGNI ladder in Developer and Tech Lead. A third **simplicity pass** in the reviewer. Its multi-agent packaging as a second reference |
| **coreyhaines31/marketingskills** | 30+ marketing skills (copywriting, launch, SEO, CRO…) that all read one `product-marketing-context` file first | Marketing agent = an orchestrator role plus a few focused sub-skills. **Positioning and voice live in one context section that the marketing skills read first** |

We adapt ideas and wording with attribution (a `NOTICE` file). We don't take any of these as runtime dependencies (see 7).

## 6. Design

### 6.1 The `agent-team` repo (shared, cloned or installed on every machine)

```
agent-team/
  skills/
    pm/SKILL.md                 # role: ideate + write spec
    pm/references/ideation-modes.md, spec-template.md
    tech-lead/SKILL.md          # role: plan
    tech-lead/references/plan-template.md, plan-checklist.md
    developer/SKILL.md          # role: implement (TDD, surgical, YAGNI)
    reviewer/SKILL.md           # role: 3-pass review
    reviewer/references/review-template.md
    qa/SKILL.md                 # role: test against acceptance criteria
    qa/references/qa-template.md, test-by-platform.md
    marketing/SKILL.md          # role: orchestrates the marketing sub-skills
    marketing/references/launch-copy.md, release-notes.md, social-posts.md
    engineering-guidelines/SKILL.md   # Karpathy + ponytail rules, shared
    team-ideate/SKILL.md        # workflow: PM → ideas.md
    team-build/SKILL.md         # workflow: spec → plan → build → review loop → PR
    team-market/SKILL.md        # workflow: post-merge marketing
    team-init/SKILL.md          # set up .agent-team/ in a product repo
  .claude-plugin/plugin.json, marketplace.json   # Claude Code plugin + marketplace
  .codex-plugin/ (or equivalent)                 # Codex plugin manifest
  agents/                       # optional Claude subagent definitions that point at the role skills
  AGENTS.md                     # always-on guidelines for tools that read AGENTS.md
  scripts/install.sh            # fallback: symlink skills/ into ~/.claude/skills, ~/.agents/skills, etc.
  NOTICE, LICENSE, README.md
```

Install on any machine with one of these:
- Claude Code: `/plugin marketplace add <you>/agent-team` → `/plugin install agent-team`
- Codex: its plugin install, or `npx skills add <you>/agent-team -a codex`
- Anything else: `npx skills add <you>/agent-team`, or `install.sh`

Updates: push to the repo, then update the plugin or re-run the install on each machine.

### 6.2 Role skill format

Standard SKILL.md, portable frontmatter only:

```yaml
---
name: tech-lead
description: Use when an approved product spec needs an architecture and implementation plan for the existing codebase.
---
```

The body says who the role is, what it **reads** and **writes** (paths under `.agent-team/`), how it works, what good output looks like, and hard limits (the developer never merges; the PM never starts implementation; the reviewer never fixes code itself). Longer material goes in `references/` so it only loads when needed. Every role reads `.agent-team/project.md` first.

### 6.3 Per-project layout (inside each product repo)

```
.agent-team/
  project.md                  # product, users, domain, stack, conventions,
                              # build/test commands, brand voice, positioning, channels
  ideas.md                    # PM's backlog of proposals
  features/<slug>/
    spec.md                   # PM (product level)
    plan.md                   # Tech Lead
    review-1.md, review-2.md  # Reviewer, one per round
    qa-1.md, qa-2.md          # QA, one per round
    marketing.md              # Marketing drafts
    status.md                 # state + history (see 6.5)
```

`team-init` creates `.agent-team/` and drafts `project.md` by reading the codebase. Adi corrects it once.

### 6.4 Flow and human gates

```
team-ideate ──► PM reads project.md + code (+ feedback notes) ──► ideas.md
                  (mode: expand / hold / reduce scope)                │
                                    GATE 1 (Adi): pick an idea ───────┘
                                                                      ▼
team-build <idea>
   PM writes spec.md
   Tech Lead writes plan.md (data flow, edge cases, test plan, files, YAGNI check)
   Developer implements on feature/<slug> in its own worktree, TDD, runs tests
   Reviewer, 3 passes ──► review-N.md
      1. spec compliance   (did we build what spec.md says, nothing extra?)
      2. plan + code quality (built the way plan.md says; bugs that pass CI)
      3. simplicity        (over-engineering, unneeded deps/abstractions)
      ├─ changes needed → back to Developer (max 3 rounds)
      └─ approved → QA
   QA ──► qa-N.md
      builds the app, runs the full test suite, and exercises the feature against
      each acceptance criterion in spec.md (browser for web, integration tests /
      emulator for Flutter, real requests for APIs; see test-by-platform.md);
      adds missing acceptance tests
      ├─ bugs found → Developer fixes → Reviewer re-checks changed files → QA again (max 2 QA rounds)
      └─ passed → open PR (body links spec/plan/reviews/QA report)
   Stop and open a draft PR flagged for Adi if: 3 review rounds or 2 QA rounds fail, or the build/tests are broken before review
                                                                      ▼
                                    GATE 2 (Adi): merge PR ───────────┘
                                                                      ▼
team-market <slug> ──► Marketing reads project.md + spec.md + merged diff ──► marketing.md
```

- The spec and plan are not approved separately. Per Adi's choice, approval happens only at Gate 1 and Gate 2.
- Marketing is triggered by Adi running `team-market` after merging (a manual trigger in v1).
- Where the tool supports subagents, each role runs in a fresh context, so the reviewer doesn't grade its own work and the developer's context stays lean. Where it doesn't, roles run one after another in a single session.

### 6.5 Resumability (`status.md`)

A small state file per feature: `stage: spec | plan | implement | review | qa | pr-open | merged | marketed`, the current review round, the branch name, and a dated log line for each transition. `team-build <slug>` on any machine or tool reads it and resumes from the recorded stage.

### 6.6 Model tiers and cost

Adi wants the process cheap and light on tokens, with each role on a fitting model and **the cheapest model that can do the job used by default**, in every tool (Claude Code, Codex, Gemini CLI and others).

**Tiers, not model names.** Roles name a tier. A single config file maps tiers to models for each tool, so a new model or tool means editing one file, not the roles.

| Tier | Claude | Codex / Gemini / others |
|---|---|---|
| `deep` | Opus | that tool's top model (mapped in config) |
| `standard` | Sonnet | its mid-tier model |
| `fast` | Haiku | its cheapest capable model |

**Role → tier (Adi's assignment), starting at the cheapest allowed tier:**

| Role | Allowed | Default | Escalate when |
|---|---|---|---|
| PM | deep | deep | — |
| Tech Lead | deep | deep | — (a tiny feature may drop to `standard`) |
| Developer | standard, fast | **fast** for mechanical tasks (plan marks each task `fast` or `standard`) | the same task fails tests twice → `standard` |
| Reviewer | deep, standard | **standard** | diff is large, or touches auth, payments, data migrations or security → `deep` |
| QA | standard, fast | **fast** when the checks are test runs and API calls | browser/UI or exploratory testing needed → `standard` |
| Marketing | deep, standard | **standard** | launch-level positioning or a new product → `deep` |

**Where the tiers live:**
- `skills/<role>/SKILL.md` carries `metadata: { tier: ..., allowed-tiers: ... }`. `metadata` is a portable frontmatter field, and tools that don't use it ignore it.
- `config/models.yaml` holds the tier → model map for each tool. Adi edits it, and it can be overridden per project in `.agent-team/project.md`.

**How each tool runs a role on its tier.** The workflow skills dispatch each role as a separate run:
- Claude Code: subagent definitions in `agents/` with a `model:` field (`opus`, `sonnet`, `haiku`).
- Codex: one profile per tier in `~/.codex/config.toml` (model + reasoning effort), with roles run through `codex exec --profile <tier>`.
- Gemini CLI and others: their headless mode with a `-m <model>` flag.
- A tool that can't switch models mid-run: the run uses the session's model, and `status.md` notes which tier was intended.

Per-tool dispatch notes live in `skills/team-build/references/dispatch-<tool>.md`, and `install.sh` writes the Codex profiles.

**Token-saving rules (all roles):**
- Lean context: each role reads only its inputs. The Developer gets `plan.md` + `project.md` + the files the plan names, never the ideation history (BMAD).
- The Tech Lead's plan names the exact files and functions for each task, so the Developer doesn't explore the repo.
- The Reviewer reads `spec.md`, `plan.md` and the diff, not the whole codebase. It opens other files only to check something specific.
- Short, template-driven artifacts with a hard length guide in each template. Long guidance stays in `references/` and loads only when needed.
- `project.md` is kept short (target: one screen) because every role reads it.
- Review rounds are capped at 3, and only changed files are re-reviewed in later rounds.
- `status.md` logs the tier used per stage, so cost hot-spots are visible.

### 6.7 Adding roles later

Add `skills/<new-role>/SKILL.md` (plus references) and reference it from a workflow skill (new or existing). Nothing else changes. Roles that fit this shape: designer/UX, security reviewer, docs writer, a retro/analytics role.

## 7. Decisions

**Decided with Adi:** approach A; a new dedicated repo (not ADE); six initial roles (QA added); two human gates (pick the feature, merge); the reviewer checks against spec + plan; marketing is triggered manually after merge and produces drafts only; built from the referenced repos' ideas.

**Claude's calls (Adi to check):**
- Roles use the Agent Skills standard (SKILL.md, portable frontmatter) instead of a custom format, so no build/generation step is needed.
- The skills are self-contained. They adapt ideas from superpowers, gstack and the others but don't require those plugins installed, so they behave the same on Codex.
- The reviewer does three passes (spec, plan + quality, simplicity), each in its own section of `review-N.md`.
- Permissions for the hands-off middle: a pre-approved list in each tool (file edits, the project's test/build commands, `git push` to `feature/*`, `gh pr create`); everything else still prompts. Each feature runs in its own git worktree. `team-init` writes these settings for the project.
- `ideas.md` is committed to `main` as a docs-only change. Feature artifacts live on `feature/<slug>`, and the branch is pushed after every stage change so another machine can resume.
- A project with no tests: the Developer adds tests for the new feature, and `plan.md` says how they run.
- Repo name `agent-team`; workflow skill names `team-ideate`, `team-build`, `team-market`, `team-init`.

**Model tiers (Adi):** PM and Tech Lead on `deep` (Opus or equivalent); Developer on `standard` or `fast` (Sonnet or Haiku); Reviewer and Marketing on `deep` or `standard` depending on scope; the cheapest allowed tier by default, in every tool.

**QA agent (Adi, on approval):** runs after code review passes and before the PR. **Claude's calls:** the spec template requires numbered acceptance criteria; QA can add acceptance tests but never changes feature code; bugs go back to the Developer, then a re-review of changed files, with a cap of 2 QA rounds; QA uses the `fast` or `standard` tier (above).

**Claude's calls on cost (Adi to check):** the escalation triggers in 6.6 (two failed test runs for the Developer; large or sensitive diffs for the Reviewer; launch-level work for Marketing); the Tech Lead tags each task `fast` or `standard`; a single `config/models.yaml` maps tiers to models.

**Left to the builder:** current model IDs for each tool in `models.yaml` (check at build time); what "large diff" means in numbers (suggested: more than 400 changed lines or more than 15 files); exact Codex plugin manifest format and the current Claude plugin schema (check the docs at build time); template contents; install-script details; how the PR is opened (`gh` CLI suggested).
