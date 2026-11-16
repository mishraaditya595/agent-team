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
                    "## Conventions", "## Positioning & voice", "## Channels", "## Model overrides")


def test_project_template_headings():
    text = read("skills/team-init/references/project-template.md")
    for h in PROJECT_HEADINGS:
        assert re.search(rf"^{re.escape(h)}\s*$", text, re.M), h


def test_claude_settings_valid_json():
    import json
    data = json.loads(read("skills/team-init/references/claude-settings.json"))
    allow = data["permissions"]["allow"]
    assert "Bash(gh pr create:*)" in allow
    assert "Bash(git push origin feature/*)" in allow
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
                 "coreyhaines31/marketingskills"):
        assert repo in text, repo


def test_team_build_pushes_branch_before_first_stage():
    text = read("skills/team-build/SKILL.md")
    assert "initial `status.md`" in text and "push fails" in text


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
    for wf in ("team-init", "team-ideate", "team-market"):
        text = read(f"skills/{wf}/SKILL.md")
        assert "git commit -m" in text and " -- .agent-team" in text, wf
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
              "agent-team lease <slug> acquire", "agent-team push <slug>", "never force-push",
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
    for k in ("Bash(agent-team:*)", "Bash(git push -u origin feature/*)", "Bash(gh pr checks:*)",
              "Bash(gh pr ready:*)", "Bash(git symbolic-ref:*)", "Bash(gh repo view:*)"):
        assert k in allow, k
    assert not any(a in allow for a in ("Bash(*)", "Bash(git push:*)", "Bash(git push origin main)"))


def test_gemini_dispatch_is_headless_safe():
    text = read("skills/team-build/references/dispatch-gemini.md")
    assert "--approval-mode auto_edit" in text and "--skip-trust" in text


def test_protected_main_fallback():
    for wf in ("team-init", "team-ideate", "team-wrap", "team-market"):
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
