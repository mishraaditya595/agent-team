"""Content checks on the real skills: each pins a rule from the spec."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SK = ROOT / "skills"


def read(rel):
    return (ROOT / rel).read_text()


RULES = ("Think before coding", "Simplicity first", "Surgical changes", "Goal-driven execution")


def test_guidelines_have_rules():
    text = read("skills/engineering-guidelines/SKILL.md")
    for h in (*RULES, "YAGNI ladder"):
        assert re.search(rf"^#+ .*{h}", text, re.M), h
    agents = read("AGENTS.md")
    for r in RULES:
        assert r in agents, r


PROJECT_HEADINGS = ("## Product", "## Users", "## Domain", "## Stack", "## Build & test",
                    "## Conventions", "## Intent docs", "## Positioning & voice", "## Channels", "## Model overrides")


def test_project_template_headings():
    text = read("skills/team-init/references/project-template.md")
    for h in PROJECT_HEADINGS:
        assert re.search(rf"^{re.escape(h)}\s*$", text, re.M), h


def test_claude_settings_valid_json():
    import json
    data = json.loads(read("skills/team-init/references/claude-settings.json"))
    allow = data["permissions"]["allow"]
    assert "Bash(gh pr create:*)" in allow
    assert not any(a.startswith("Bash(git push") for a in allow)
    assert "{{TEST_COMMANDS}}" in allow


def test_codex_project_toml_parses():
    import tomllib
    data = tomllib.loads(read("skills/team-init/references/codex-project.toml"))
    assert data["sandbox_mode"] == "workspace-write"


def test_spec_template_has_numbered_ac():
    text = read("skills/pm/references/spec-template.md")
    for h in ("## Problem", "## Users affected", "## Proposal", "## Out of scope",
              "## Acceptance criteria", "## Success signal"):
        assert h in text, h
    assert re.search(r"^\s*-?\s*AC1\b", text, re.M)


def test_ideation_modes_listed():
    text = read("skills/pm/references/ideation-modes.md")
    for m in ("expand", "hold", "reduce"):
        assert re.search(rf"^#+ .*`?{m}`?", text, re.M), m


def test_pm_role_frontmatter():
    from validate import parse_frontmatter
    fm = parse_frontmatter(read("skills/pm/SKILL.md"))
    assert fm["metadata"]["tier"] == "deep" and fm["metadata"]["allowed-tiers"] == ["deep", "standard"]


TASK_LINE = re.compile(r"- \[ \] T\d+ \[(fast|standard)\] .+ — files: .+ — maps to: AC\d+")


def test_plan_template_task_format():
    assert TASK_LINE.search(read("skills/tech-lead/references/plan-template.md"))


def test_plan_template_has_test_plan_heading():
    text = read("skills/tech-lead/references/plan-template.md")
    for h in ("## Approach", "## Data flow", "## Edge cases", "## Test plan", "## Tasks"):
        assert h in text, h


def section(text, heading):
    m = re.search(rf"^{re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, heading
    return m.group(1)


def test_review_template_three_passes():
    text = read("skills/reviewer/references/review-template.md")
    for h in ("## Pass 1 — Spec compliance", "## Pass 2 — Plan & code quality",
              "## Pass 3 — Simplicity", "## Verdict"):
        assert h in text, h
    assert "APPROVED" in text and "CHANGES REQUESTED" in text


def test_qa_template_columns():
    assert "| AC | Method | Result (PASS/FAIL) | Evidence |" in read("skills/qa/references/qa-template.md")
    assert "UNVERIFIED" in read("skills/qa/references/test-by-platform.md")


def test_reviewer_never_edits():
    assert "edit" in section(read("skills/reviewer/SKILL.md"), "## Never").lower()


def test_qa_never_changes_feature_code():
    assert "feature code" in section(read("skills/qa/SKILL.md"), "## Never").lower()


def test_developer_escalation_rule():
    text = read("skills/developer/SKILL.md")
    assert "fails twice" in text


def test_status_template_fields():
    text = read("skills/team-build/references/status-template.md")
    for k in ("stage:", "branch:", "review_round:", "qa_round:", "worktree:", "## Log"):
        assert k in text, k
    for s in ("spec", "plan", "implement", "review", "qa", "pr-open", "merged", "marketed"):
        assert s in text, s


def test_team_build_mentions_safeguards():
    text = read("skills/team-build/SKILL.md")
    for k in ("worktree", "--draft", "status.md is missing", "review rounds", "QA rounds",
              "fallback", "400", "15 files", "Model overrides"):
        assert k in text, k


def test_dispatch_refs_exist():
    expect = {"claude": "subagent", "codex": "codex exec --profile", "gemini": "gemini -m",
              "generic": "intended="}
    for tool, needle in expect.items():
        assert needle in read(f"skills/team-build/references/dispatch-{tool}.md"), tool


def test_marketing_template_headings():
    text = read("skills/marketing/references/marketing-template.md")
    for h in ("## Release notes", "## Announcement", "## Social posts", "## Landing page changes"):
        assert h in text, h


def test_marketing_never_posts():
    never = section(read("skills/marketing/SKILL.md"), "## Never").lower()
    assert "post" in never or "publish" in never


def test_team_market_requires_merged():
    text = read("skills/team-market/SKILL.md")
    assert "merged" in text and "gh pr view" in text


def test_team_ideate_gate1():
    assert "team-build" in read("skills/team-ideate/SKILL.md")


def test_notice_credits_sources():
    text = read("NOTICE")
    for repo in ("obra/superpowers", "garrytan/gstack", "bmad-code-org/BMAD-METHOD",
                 "multica-ai/andrej-karpathy-skills", "DietrichGebert/ponytail",
                 "coreyhaines31/marketingskills", "shadcn/improve"):
        assert repo in text, repo


def test_team_build_pushes_branch_before_first_stage():
    text = read("skills/team-build/SKILL.md")
    assert "initial `status.md`" in text and "that push is the lease" in text


def test_team_build_resume_reuses_branch_worktree():
    text = read("skills/team-build/SKILL.md")
    assert "git worktree add .agent-team/worktrees/<slug> feature/<slug>" in text
    assert "local-only" in text


def test_worktrees_live_inside_repo():
    assert ".agent-team/worktrees/" in read("skills/team-build/SKILL.md")
    assert ".agent-team/worktrees/" in read("skills/team-init/SKILL.md")
    assert "-s workspace-write" in read("skills/team-build/references/dispatch-codex.md")


def test_dispatch_points_at_skill_models_file():
    for tool in ("claude", "codex", "gemini", "generic"):
        assert "references/models.yaml" in read(f"skills/team-build/references/dispatch-{tool}.md"), tool
    assert "references/models.yaml" in read("skills/team-build/SKILL.md")


def test_docs_workflows_commit_only_their_paths():
    for wf in ("team-init", "team-ideate", "team-market", "team-audit"):
        text = read(f"skills/{wf}/SKILL.md")
        assert "agent-team docs-commit -m" in text and " .agent-team" in text, wf
        assert "default branch" in text and "stop" in text.lower(), wf


def test_team_build_runs_build_before_review():
    assert "agent-team test <slug> --build" in read("skills/team-build/SKILL.md")


def test_allowlist_has_no_switch_and_has_resume_reads():
    import json
    allow = json.loads(read("skills/team-init/references/claude-settings.json"))["permissions"]["allow"]
    assert "Bash(git switch:*)" not in allow
    assert "Bash(git show:*)" in allow and "Bash(git ls-remote:*)" in allow


def test_resume_from_stopped_defined():
    assert "stopped_at:" in read("skills/team-build/references/status-template.md")
    text = read("skills/team-build/SKILL.md")
    assert "`stopped`" in text and "`pr-open`" in text and "stopped_at" in text


def test_no_hardcoded_main():
    for p in ("skills/reviewer/SKILL.md", "skills/team-build/SKILL.md"):
        assert "main..." not in read(p), p


def test_review_loop_tracks_reviewed_commit_and_open_findings():
    build = read("skills/team-build/SKILL.md")
    assert "Set `last_reviewed_commit`" in build
    reviewer = read("skills/reviewer/SKILL.md")
    assert "previous findings" in reviewer.lower() and "never drop out silently" in reviewer
    assert "## Previous findings" in read("skills/reviewer/references/review-template.md")


def test_qa_fix_review_has_a_stop():
    assert "review after QA fixes" in read("skills/team-build/SKILL.md")


def test_team_build_phase1_safeguards():
    text = read("skills/team-build/SKILL.md")
    for k in ("agent-team tasks <slug>", "agent-team sync <slug>", "agent-team ci <slug> --watch",
              "agent-team lease <slug> acquire", "agent-team push <slug>", "Never force-push",
              "gh pr ready <pr> --undo", "set `pr=<number>`".replace("set ", "Set "), "standard-tier session"):
        assert k in text, k


def test_developer_works_only_on_given_tasks():
    text = read("skills/developer/SKILL.md")
    assert "Work only on the task ids in your prompt" in text


def test_plan_template_feeds_tier_rules():
    text = read("skills/tech-lead/references/plan-template.md")
    assert "qa-ui: yes|no" in text and "## Security touchpoints" in text


def test_allowlist_covers_helper_and_ci():
    import json
    allow = json.loads(read("skills/team-init/references/claude-settings.json"))["permissions"]["allow"]
    for k in ("Bash(agent-team:*)", "Bash(gh pr checks:*)",
              "Bash(gh pr ready:*)", "Bash(git symbolic-ref:*)", "Bash(gh repo view:*)"):
        assert k in allow, k
    # pushes go through `agent-team push` / `docs-commit`; no raw git push patterns (they can match --force or main)
    assert not any(a == "Bash(*)" or a.startswith("Bash(git push") for a in allow)


def test_gemini_dispatch_is_headless_safe():
    text = read("skills/team-build/references/dispatch-gemini.md")
    assert "--approval-mode auto_edit" in text and "--skip-trust" in text


def test_protected_main_fallback():
    for wf in ("team-init", "team-ideate", "team-wrap", "team-market", "team-audit"):
        assert "agent-team/meta" in read(f"skills/{wf}/SKILL.md"), wf


def test_no_hardcoded_owner_name():
    for p in list((ROOT / "skills").rglob("*.md")) + list((ROOT / "agents").glob("*.md")):
        assert not re.search(r"\bAdi\b", p.read_text()), p


def test_lessons_loop_wired():
    assert "lessons.md" in read("skills/team-wrap/SKILL.md")
    for role in ("tech-lead", "developer", "reviewer", "pm"):
        assert ".agent-team/lessons.md" in read(f"skills/{role}/SKILL.md"), role


def test_ideas_have_status():
    assert "**Status:** proposed" in read("skills/pm/references/ideas-template.md")
    assert "reject" in read("skills/team-ideate/SKILL.md")


def test_project_template_has_owner_and_excludes():
    text = read("skills/team-init/references/project-template.md")
    assert "## Owner" in text and "## Diff excludes" in text


def test_owner_can_add_own_idea():
    ideate = read("skills/team-ideate/SKILL.md")
    assert 'team-ideate add "<idea>"' in ideate and "pm-intake" in ideate
    pm = read("skills/pm/SKILL.md")
    assert "**Intake**" in pm and "Intake mode" in pm and "Keep the owner's intent" in pm


def test_team_init_upgrade_mode():
    text = read("skills/team-init/SKILL.md")
    assert "## Upgrade" in text and "agent-team upgrade" in text


def test_docs_workflows_never_commit_on_default_branch():
    for wf in ("team-init", "team-ideate", "team-wrap", "team-market", "team-audit"):
        text = read(f"skills/{wf}/SKILL.md")
        assert "agent-team docs-commit" in text and "git commit" not in text and "git push" not in text, wf


def test_team_build_review_fixes_wired():
    text = read("skills/team-build/SKILL.md")
    for k in ("agent-team next <slug> review", "agent-team next <slug> qa", "agent-team idea <slug> --show",
              "stop **without** the *Stop* steps", "CI fix broke the tests", "merge the agent-team/meta PR first"):
        assert k in text, k


def test_ci_fix_is_reviewed():
    assert "review of the CI fix" in read("skills/team-build/SKILL.md")


def test_team_init_guards_owner_edits():
    assert "must not sweep in their edits" in read("skills/team-init/SKILL.md")


def test_workflows_pull_with_agent_team_pull():
    for wf in ("team-ideate", "team-wrap", "team-market", "team-audit"):
        text = read(f"skills/{wf}/SKILL.md")
        assert "`agent-team pull`" in text and "git pull --ff-only" not in text, wf
    assert "`agent-team pull`" in read("skills/team-init/SKILL.md")


# ---------- upstream practices (2026-11-16) ----------

def test_tech_lead_grill_mode():
    text = read("skills/tech-lead/SKILL.md")
    for k in ("Grill mode", "references/grilling.md", "grill.md", "## Decisions"):
        assert k in text, k
    g = read("skills/tech-lead/references/grilling.md")
    for k in ("design tree", "frontier", "recommended answer", "look it up", "3 rounds"):
        assert k in g, k
    t = read("skills/tech-lead/references/grill-template.md")
    for k in ("## Round 1", "G1", "**Answer:**", "answered", "assumed", "owner"):
        assert k in t, k


def test_pm_answer_mode():
    text = read("skills/pm/SKILL.md")
    for k in ("Answer mode", "grill.md", "answered", "assumed", "owner", "scope", "users see"):
        assert k in text, k


def test_team_build_grill_stage():
    text = read("skills/team-build/SKILL.md")
    for k in ("**grill**", "grill_round", "stopped_at=grill", "owner question", "3 grill rounds"):
        assert k in text, k
    assert "spec | grill | plan" in read("skills/team-build/references/status-template.md")


def test_plan_template_writing_plans_blocks():
    text = read("skills/tech-lead/references/plan-template.md")
    for k in ("## Global constraints", "## Review focus", "## Rulings", "Interfaces:", "Failing test:",
              "Run:", "Expected:"):
        assert k in text, k


def test_tech_lead_tdd_and_self_review():
    text = read("skills/tech-lead/SKILL.md")
    for k in ("watch it fail", "Review focus", "Interfaces", "self-review"):
        assert k in text, k
    chk = read("skills/tech-lead/references/plan-checklist.md")
    for k in ("Spec coverage", "Step scan", "Name consistency", "Review focus", "Proportion"):
        assert k in chk, k


def test_developer_executing_plans_discipline():
    text = read("skills/developer/SKILL.md")
    for k in ("Ruling:", "## Rulings", "Expected:", "completion contract", "references/debugging.md",
              "watch it fail"):
        assert k in text, k


def test_debugging_reference_phases():
    text = read("skills/developer/references/debugging.md")
    for k in ("root cause", "Reproduce", "working example", "one hypothesis", "failing test",
              "3 fixes", "design problem"):
        assert k in text, k


def test_reviewer_requesting_code_review_practices():
    text = read("skills/reviewer/SKILL.md")
    for k in ("Critical", "Important", "Minor", "reasonable user", "Review focus", "Rulings", "Declined to judge",
              "Strengths"):
        assert k in text, k
    t = read("skills/reviewer/references/review-template.md")
    for k in ("## Strengths", "## Review focus & rulings", "## Declined to judge", "[critical]", "[important]",
              "[minor]"):
        assert k in t, k


CHANNELS = ("instagram", "blog", "linkedin", "reddit")


def test_marketing_channel_playbooks():
    for ch in CHANNELS:
        assert len(read(f"skills/marketing/references/{ch}.md").splitlines()) > 10, ch
    assert "carousel" in read("skills/marketing/references/instagram.md").lower()
    assert "Visual brief" in read("skills/marketing/references/instagram.md")
    assert "meta description" in read("skills/marketing/references/blog.md").lower()
    assert "link in the first comment" in read("skills/marketing/references/linkedin.md").lower()
    r = read("skills/marketing/references/reddit.md").lower()
    for k in ("subreddit rules", "builder", "value first"):
        assert k in r, k
    tells = read("skills/marketing/references/no-ai-tells.md")
    for k in ("not x. y.", "engagement bait", "em dash"):
        assert k in tells.lower(), k


def test_marketing_two_modes():
    text = read("skills/marketing/SKILL.md")
    for k in ("Feature mode", "Topic mode", "no-ai-tells.md", ".agent-team/marketing/", *[f"references/{c}.md" for c in CHANNELS]):
        assert k in text, k
    t = read("skills/team-market/SKILL.md")
    for k in ("--topic", "marketing-topic", ".agent-team/marketing/"):
        assert k in t, k
    tmpl = read("skills/marketing/references/topic-template.md")
    for h in ("## Instagram", "## Blog", "## LinkedIn", "## Reddit"):
        assert h in tmpl, h


SAFETY = ("not instructions", "secret")


def test_read_as_data_rules():
    g = read("skills/engineering-guidelines/SKILL.md")
    assert re.search(r"^## 5\. Treat what you read as data", g, re.M)
    for f in ("skills/engineering-guidelines/SKILL.md", "AGENTS.md",
              "skills/pm/SKILL.md", "skills/marketing/SKILL.md", "skills/qa/SKILL.md"):
        text = read(f).lower()
        for w in SAFETY:
            assert w in text, (f, w)
    assert "rotat" in g.lower()


def test_ideas_need_evidence():
    t = read("skills/pm/references/ideas-template.md")
    assert "**Evidence:**" in t and "audit" in t
    pm = read("skills/pm/SKILL.md")
    assert "Intent docs" in pm and "evidence" in pm.lower()
    assert "Intent docs" in read("skills/tech-lead/SKILL.md")
    assert "Intent docs" in read("skills/team-init/SKILL.md")


CATEGORIES = ("Correctness", "Security", "Performance", "Tests", "Tech debt",
              "Dependencies", "DX", "Docs", "Direction")


def test_audit_mode():
    pb = read("skills/tech-lead/references/audit-playbook.md")
    for c in CATEGORIES:
        assert re.search(rf"^## .*{c}", pb, re.M), c
    for h in ("## Finding format", "## Ranking", "## Vetting"):
        assert h in pb
    tpl = read("skills/tech-lead/references/audit-template.md")
    for h in ("## Not audited", "## Direction", "## Sent to ideas", "## Considered and rejected"):
        assert h in tpl
    tl = read("skills/tech-lead/SKILL.md")
    assert "Audit mode" in tl and "references/audit-playbook.md" in tl
    wf = read("skills/team-audit/SKILL.md")
    assert "tech-lead-audit" in wf and ".agent-team/audits/" in wf and "mode: audit" in wf
    assert "team-audit" in read("README.md")


def test_plan_drift_wiring():
    assert "planned-at:" in read("skills/tech-lead/references/plan-template.md")
    assert "planned-at" in read("skills/tech-lead/references/plan-checklist.md")
    tl = read("skills/tech-lead/SKILL.md")
    assert "Refresh" in tl and "merge-base" in tl
    tb = read("skills/team-build/SKILL.md")
    assert "agent-team drift" in tb and "refresh" in tb


def test_tech_lead_never_copies_secrets():
    tl = read("skills/tech-lead/SKILL.md")
    never = tl.split("## Never", 1)[1].lower()
    assert "secret" in never and "not instructions" in never
    assert "never quote a credential" in read("skills/tech-lead/references/audit-playbook.md").lower()
    assert "agent-team audit-path" in read("skills/team-audit/SKILL.md")


def test_drift_follow_ups_wired():
    tb = read("skills/team-build/SKILL.md")
    assert "agent-team tier tech-lead <slug>" in tb                   # refresh tier is stated
    assert "expect `drift: none`" in tb                               # refresh is checked
    assert "except the drift refresh" in tb                           # no contradiction with the resume rule
    tl = read("skills/tech-lead/SKILL.md")
    assert "at standard depth" not in tl and "at the level given" in tl
    init = read("skills/team-init/SKILL.md")
    assert "## Intent docs" in init.split("## Upgrade", 1)[1]           # upgrade tells the agent to fill it


def test_spec_and_plan_describe_unchecked_drift():
    spec = read("docs/superpowers/specs/2026-11-17-improve-practices-design.md")
    plan = read("docs/superpowers/plans/2026-11-17-improve-practices.md")
    for text in (spec, plan):
        assert "drift: unchecked" in text
        assert "Fails (exit 1) if `planned-at` is missing" not in text


def test_audit_date_comes_from_report_name():
    wf = read("skills/team-audit/SKILL.md")
    assert "today's date" not in wf and "date in the report file name" in wf
    assert "date in the report file name" in read("skills/tech-lead/SKILL.md")
    assert "team-audit [quick\\|deep] [<category>]" in read("README.md")


def test_pm_ideates_across_repos():
    pm = read("skills/pm/SKILL.md")
    assert "agent-team repos --log" in pm and "**Repos:**" in pm
    assert "**Repos:**" in read("skills/pm/references/ideas-template.md")


def test_workspace_mode_wired_in_skills():
    tb = read("skills/team-build/SKILL.md")
    lease = tb[tb.index("agent-team lease <slug> acquire"):]
    assert lease.index("--takeover") < lease.index("agent-team repos <slug> --ensure")   # only once the lease is held
    assert tb.count("agent-team repos <slug> --ensure") >= 3
    assert "agent-team heads <slug>" in tb and "pr-body <slug> --repo" in tb and "-R <owner/repo>" in tb
    assert "agent-team commit <slug>" in read("skills/developer/SKILL.md")
    assert "Cross-repo rules" in read("skills/reviewer/SKILL.md")
    assert "Spec problems" in read("skills/tech-lead/SKILL.md") and "## Repos" in read("skills/tech-lead/SKILL.md")
    assert "repo_prs" in read("skills/team-wrap/SKILL.md")
    assert "--summary '<3 lines>')\"` for each product PR" in tb and tb.index("repo_prs=") < tb.index("Then the workspace PR")
    assert '"last_reviewed_commit=$(agent-team heads <slug>)"' in tb and tb.count("last_reviewed_commit=$(") == 3
    assert '--since "<since>"' in read("skills/reviewer/SKILL.md")
    assert tb.index("If it's rejected") < tb.index("Otherwise, in a workspace, run")
    assert "Once you hold the lease, in a workspace (`project.md` has `## Repos`) run `agent-team repos <slug> --ensure`" in tb
    assert "`<owner/repo>` = `repo=` and `<branch>` = `branch=`" in tb and "--log-failed`, with `-R <owner/repo>`" in tb
    assert "-R <owner/repo> --json number" in tb
    assert "plain `git add`/`git commit`" in read("skills/developer/SKILL.md")
    assert "not `git log`" in read("skills/pm/SKILL.md")
    assert "git -C" not in tb + read("skills/developer/SKILL.md") + read("skills/pm/SKILL.md")


def test_team_build_pr_step_workspace_first_and_needs_github_remote():
    tb = read("skills/team-build/SKILL.md")
    pr = tb[tb.index("7. **pr**"):tb.index("8. **ci**")]
    assert pr.index("In a workspace") < pr.index("if `gh pr view feature/<slug> --json number` finds a PR")
    assert "(instead of the single-repo steps below)" in pr
    assert "`repo=` is `-`" in pr and "has no GitHub remote" in pr


def test_roles_read_repo_rules():
    for role in ("tech-lead", "reviewer", "pm"):
        assert "agent-team rules" in read(f"skills/{role}/SKILL.md"), role
    assert "(source:" in read("skills/tech-lead/SKILL.md") + read("skills/tech-lead/references/plan-template.md")
    assert "git show origin/" in read("skills/reviewer/SKILL.md")
    for f in ("skills/developer/SKILL.md", "skills/qa/SKILL.md"):
        assert "rules file" in read(f), f
    for f in ("skills/engineering-guidelines/SKILL.md", "AGENTS.md"):
        assert "agent-team rules" in read(f) and "never override" in read(f), f
