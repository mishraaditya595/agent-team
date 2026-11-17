"""Behaviour of the agent-team helper CLI against throwaway git repos."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "team-build" / "scripts"))
import agent_team as at  # noqa: E402

PROJECT = """# Demo — project context

## Build & test
- Install: `none`
- Build: `true`
- Test: `{test}`

## Diff excludes
- `vendor/**`

## Model overrides
<!-- e.g.
- developer: standard
-->
{overrides}
"""

IDEAS = """## 2026-11-16 — mode: hold

### tiny — Tiny thing
- **User & problem:** x
- **Value:** H · **Effort:** S · **Risk:** low

### big — Big thing
- **Status:** shipped
- **Value:** H · **Effort:** L · **Risk:** high
"""

SPEC = "# Tiny thing\n\nslug: tiny · effort: S · launch: false\n\n## Acceptance criteria\n- AC1: a\n- AC2: b\n"
PLAN = """# Plan: tiny

spec: x · modelled on: y · qa-ui: no

## Security touchpoints
none

## Tasks
- [x] T1 [fast] one — files: a — maps to: AC1
- [ ] T2 [fast] two — files: a — maps to: AC1
- [ ] T3 [fast] three — files: a — maps to: AC2
- [ ] T4 [standard] four — files: b — maps to: AC2 — why standard: state
- [ ] T5 [fast] five — files: c — maps to: AC2
"""


def sh(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    work = tmp_path / "work"
    sh("git", "clone", "-q", str(remote), str(work), cwd=tmp_path)
    for k, v in (("user.name", "t"), ("user.email", "t@t"), ("init.defaultBranch", "main")):
        sh("git", "config", k, v, cwd=work)
    sh("git", "checkout", "-q", "-b", "main", cwd=work)
    (work / ".agent-team").mkdir()
    (work / ".agent-team" / "project.md").write_text(PROJECT.format(test="true", overrides="none"))
    (work / ".agent-team" / "ideas.md").write_text(IDEAS)
    (work / "app.txt").write_text("hello\n")
    (work / ".gitignore").write_text(".agent-team/worktrees/\n")
    sh("git", "add", "-A", cwd=work)
    sh("git", "commit", "-q", "-m", "init", cwd=work)
    sh("git", "push", "-q", "-u", "origin", "main", cwd=work)
    sh("git", "remote", "set-head", "origin", "main", cwd=work)
    monkeypatch.chdir(work)
    monkeypatch.setenv("AGENT_TEAM_HOST", "box-a")
    return work


def new_feature(work, slug="tiny", capsys=None):
    wt = work / ".agent-team" / "worktrees" / slug
    sh("git", "worktree", "add", "-q", "-b", f"feature/{slug}", str(wt), "origin/main", cwd=work)
    assert at.main(["init-status", slug]) == 0
    fd = wt / ".agent-team" / "features" / slug
    (fd / "spec.md").write_text(SPEC)
    (fd / "plan.md").write_text(PLAN)
    sh("git", "add", "-A", cwd=wt)
    sh("git", "commit", "-q", "-m", "spec+plan", cwd=wt)
    if capsys:
        capsys.readouterr()
    return wt, fd


def test_default_branch(repo, capsys):
    at.main(["default-branch"])
    assert capsys.readouterr().out.strip() == "main"


def test_mini_yaml_matches_models_file():
    text = at.MODELS.read_text()
    data = at.mini_yaml(text)
    assert data["tools"]["claude"] == {"deep": "opus", "standard": "sonnet", "fast": "haiku"}
    assert data["effort"]["fast"] == "low"
    assert at.mini_yaml("a: {x: 1, y: 2}\nb: [p, q]\n") == {"a": {"x": "1", "y": "2"}, "b": ["p", "q"]}


def test_status_set_keeps_comments_and_validates(repo):
    wt, fd = new_feature(repo)
    p = fd / "status.md"
    at.write_status(p, {"stage": "plan", "review_round": "2"})
    text = p.read_text()
    assert "stage: plan            # spec |" in text and "review_round: 2" in text
    assert at.read_status(p)["owner"].startswith("box-a ")
    with pytest.raises(at.Fail):
        at.write_status(p, {"stage": "bogus"})
    with pytest.raises(at.Fail):
        at.write_status(p, {"colour": "red"})


def test_template_keys_match_cli():
    keys = set(at.read_status_text(at.STATUS_TEMPLATE.read_text()))
    assert keys == set(at.STATUS_KEYS)


def test_log_appends(repo):
    wt, fd = new_feature(repo)
    at.main(["log", "tiny", "spec", "pm", "--tier", "deep", "--model", "opus", "--tokens", "1200", "--cost", "0.40", "ok"])
    last = (fd / "status.md").read_text().strip().splitlines()[-1]
    assert "spec pm tier=deep model=opus tokens=1200 cost=0.40 ok" in last


def test_lease_blocks_other_host(repo, monkeypatch, capsys):
    new_feature(repo)
    monkeypatch.setenv("AGENT_TEAM_HOST", "box-b")
    assert at.main(["lease", "tiny", "acquire"]) == 1
    assert "running on box-a" in capsys.readouterr().err
    assert at.main(["lease", "tiny", "acquire", "--takeover"]) == 0
    monkeypatch.setenv("AGENT_TEAM_HOST", "box-a")
    assert at.main(["lease", "tiny", "acquire"]) == 1


def test_lease_release_frees_it(repo, monkeypatch):
    new_feature(repo)
    at.main(["lease", "tiny", "release"])
    monkeypatch.setenv("AGENT_TEAM_HOST", "box-b")
    assert at.main(["lease", "tiny", "acquire"]) == 0


def test_tasks_batch_by_tier(repo, capsys):
    new_feature(repo, capsys=capsys)
    at.main(["tasks", "tiny"])
    assert capsys.readouterr().out.split("\n")[:3] == ["fast T2,T3", "standard T4", "fast T5"]


def test_idea_lookup_and_set(repo, capsys):
    at.main(["idea", "tiny"])
    assert capsys.readouterr().out.strip() == "status=proposed effort=S"
    at.main(["idea", "big"])
    assert "status=shipped" in capsys.readouterr().out
    at.main(["idea", "tiny", "--set", "rejected"])
    text = (repo / ".agent-team" / "ideas.md").read_text()
    assert "### tiny — Tiny thing\n- **Status:** rejected\n" in text
    assert at.main(["idea", "nope"]) == 1


def tier(capsys, *args):
    capsys.readouterr()
    at.main(["tier", *args])
    return dict(kv.split("=", 1) for kv in capsys.readouterr().out.strip().split(" ", 3))


def test_tier_rules(repo, capsys):
    wt, fd = new_feature(repo)
    assert tier(capsys, "pm-spec", "tiny")["tier"] == "standard"          # idea effort S
    assert tier(capsys, "tech-lead", "tiny")["tier"] == "standard"        # S and 2 ACs
    assert tier(capsys, "developer", "tiny", "--task", "T4")["tier"] == "standard"
    dev = tier(capsys, "developer", "tiny", "--task", "T2")
    assert dev["tier"] == "fast" and dev["model"] == "haiku" and dev["effort"] == "low"
    assert tier(capsys, "qa", "tiny")["tier"] == "fast"
    assert tier(capsys, "reviewer", "tiny")["tier"] == "standard"
    assert tier(capsys, "marketing", "tiny")["tier"] == "standard"
    codex = tier(capsys, "pm-ideate", "--tool", "codex")
    assert codex["tier"] == "deep" and codex["model"] == "gpt-5.5"
    assert "fallback" in tier(capsys, "qa", "tiny", "--tool", "other")["reason"]


def test_tier_escalations(repo, capsys):
    wt, fd = new_feature(repo)
    (fd / "plan.md").write_text(PLAN.replace("qa-ui: no", "qa-ui: yes").replace(
        "## Security touchpoints\nnone", "## Security touchpoints\n- login token"))
    assert tier(capsys, "qa", "tiny")["tier"] == "standard"
    assert tier(capsys, "reviewer", "tiny")["tier"] == "deep"
    (wt / "big.txt").write_text("x\n" * 450)
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-q", "-m", "big", cwd=wt)
    (fd / "plan.md").write_text(PLAN)
    assert "large diff" in tier(capsys, "reviewer", "tiny")["reason"]


def test_override_and_clamp(repo, capsys):
    new_feature(repo)
    (repo / ".agent-team" / "project.md").write_text(PROJECT.format(test="true", overrides="- developer: deep"))
    r = tier(capsys, "developer", "tiny", "--task", "T2")
    assert r["tier"] == "standard" and "not allowed" in r["reason"]


def test_override_example_in_comment_is_ignored(repo):
    assert at.overrides(at.project_md()) == {}


def test_diff_excludes_noise(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (wt / "code.dart").write_text("a\nb\n")
    (wt / "code.g.dart").write_text("gen\n" * 50)
    (wt / "pubspec.lock").write_text("lock\n" * 50)
    (wt / "vendor").mkdir(); (wt / "vendor" / "x.js").write_text("v\n" * 50)
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-q", "-m", "c", cwd=wt)
    assert at.diffstat("tiny") == (2, 1)
    at.main(["diff", "tiny", "--stat"])
    out = capsys.readouterr().out
    assert "code.dart" in out and "code.g.dart" not in out and "status.md" not in out


def test_test_cache_survives_status_commits(repo, capsys):
    wt, fd = new_feature(repo)
    assert at.main(["test", "tiny"]) == 0
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-q", "-m", "status", cwd=wt)
    capsys.readouterr()
    assert at.main(["test", "tiny"]) == 0
    assert "cached" in capsys.readouterr().out
    (wt / "app.txt").write_text("changed\n")
    assert at.main(["test", "tiny"]) == 0
    assert "cached" not in capsys.readouterr().out   # dirty code: no cache


def test_failing_tests_recorded(repo, capsys):
    (repo / ".agent-team" / "project.md").write_text(PROJECT.format(test="echo boom; exit 3", overrides="none"))
    wt, fd = new_feature(repo)
    assert at.main(["test", "tiny"]) == 1
    assert "boom" in capsys.readouterr().out
    assert at.read_status(fd / "status.md")["tests"].endswith("fail(test)")


def test_sync_merges_and_reports_conflicts(repo, capsys):
    wt, fd = new_feature(repo)
    (repo / "other.txt").write_text("main side\n")
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-q", "-m", "m1", cwd=repo); sh("git", "push", "-q", cwd=repo)
    assert at.main(["sync", "tiny"]) == 0 and (wt / "other.txt").exists()
    (repo / "app.txt").write_text("main\n")
    sh("git", "commit", "-qam", "m2", cwd=repo); sh("git", "push", "-q", cwd=repo)
    (wt / "app.txt").write_text("feature\n")
    sh("git", "commit", "-qam", "f", cwd=wt)
    assert at.main(["sync", "tiny"]) == 2
    assert "app.txt" in capsys.readouterr().err
    assert not (wt / ".git").is_dir() and "MERGE_HEAD" not in sh("git", "status", cwd=wt)


def test_push_rejection_explained(repo, tmp_path, monkeypatch, capsys):
    wt, fd = new_feature(repo)
    assert at.main(["push", "tiny"]) == 0
    other = tmp_path / "other"
    sh("git", "clone", "-q", "-b", "feature/tiny", str(tmp_path / "remote.git"), str(other), cwd=tmp_path)
    sh("git", "config", "user.email", "o@o", cwd=other); sh("git", "config", "user.name", "o", cwd=other)
    (other / "x.txt").write_text("x\n"); sh("git", "add", "-A", cwd=other)
    sh("git", "commit", "-q", "-m", "other", cwd=other); sh("git", "push", "-q", cwd=other)
    (wt / "y.txt").write_text("y\n"); sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-q", "-m", "me", cwd=wt)
    assert at.main(["push", "tiny"]) == 3
    assert "Never force-push" in capsys.readouterr().err


def test_pr_body_links_artifacts(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (fd / "review-1.md").write_text("x"); (fd / "qa-1.md").write_text("x")
    at.main(["log", "tiny", "spec", "pm", "--tier", "deep", "--model", "opus"])
    at.main(["pr-body", "tiny", "--summary", "Adds tiny.", "--stopped", "3 review rounds"])
    out = capsys.readouterr().out
    assert out.startswith("> **Stopped")
    for n in ("spec.md", "plan.md", "review-1.md", "qa-1.md", "tier=deep"):
        assert n in out


def test_summary_lists_features(repo, capsys):
    wt, fd = new_feature(repo)
    at.main(["log", "tiny", "spec", "pm", "--tier", "deep", "--model", "opus", "--tokens", "100", "--cost", "0.5"])
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-q", "-m", "s", cwd=wt)
    at.main(["push", "tiny"])
    capsys.readouterr()
    at.main(["summary"])
    out = capsys.readouterr().out
    assert "| tiny | spec |" in out and "$0.50" in out and "| 100 |" in out


def test_cleanup_removes_worktree_and_branch(repo):
    wt, fd = new_feature(repo)
    assert at.main(["push", "tiny"]) == 0
    sh("git", "merge", "-q", "--no-edit", "origin/feature/tiny", cwd=repo); sh("git", "push", "-q", cwd=repo)
    assert at.main(["cleanup", "tiny", "--remote"]) == 0
    assert not wt.exists()
    assert "feature/tiny" not in sh("git", "branch", "-a", cwd=repo)


V1_PROJECT = """# Demo — project context

## Product
A demo.

## Build & test
- Install: `npm ci`
- Build: `npm run build`
- Test: `npm test`

## Channels
X

## Model overrides
- developer: standard
"""


def test_upgrade_v1_repo(repo, capsys):
    import json
    (repo / ".agent-team" / "project.md").write_text(V1_PROJECT)
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text(json.dumps(
        {"model": "mine", "permissions": {"allow": ["Edit", "Bash(npm test:*)"], "deny": ["Bash(rm:*)"]}}))
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "v1 setup", cwd=repo)   # as team-init v0.1 left it
    assert at.main(["upgrade"]) == 0
    text = (repo / ".agent-team" / "project.md").read_text()
    heads = [h for h in text.splitlines() if h.startswith("## ")]
    assert heads.index("## Owner") < heads.index("## Product")
    assert heads.index("## Diff excludes") < heads.index("## Model overrides")
    assert "- developer: standard" in text and "A demo." in text          # existing content kept
    assert "## Positioning & voice\nunknown — owner to fill" in text and "## Conventions" in text
    data = json.loads((repo / ".claude" / "settings.json").read_text())
    allow = data["permissions"]["allow"]
    assert data["model"] == "mine" and data["permissions"]["deny"] == ["Bash(rm:*)"]
    assert "Bash(agent-team:*)" in allow and "Bash(npm run build:*)" in allow
    assert allow.count("Bash(npm test:*)") == 1 and "{{TEST_COMMANDS}}" not in allow
    assert (repo / ".codex" / "config.toml").exists()
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "upgrade", cwd=repo)   # docs-commit's job
    capsys.readouterr()
    assert at.main(["upgrade"]) == 0                                       # idempotent
    assert "nothing — already up to date" in capsys.readouterr().out


def test_intake_tier(repo, capsys):
    r = tier(capsys, "pm-intake")
    assert r["tier"] == "standard" and r["model"] == "sonnet"


def test_grill_stage_and_round_accepted(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["status", "tiny", "--set", "stage=grill", "grill_round=2", "stopped_at=grill"]) == 0
    capsys.readouterr()
    at.main(["status", "tiny", "grill_round"])
    assert capsys.readouterr().out.strip() == "2"


def test_pr_body_lists_assumed_decisions_and_rulings(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (fd / "grill.md").write_text("x")
    (fd / "spec.md").write_text(SPEC + "\n## Decisions\n- G1 (answered): lists sort by date — spec AC2\n"
                                 "- G2 (assumed): empty list shows a hint — PM: matches other screens\n"
                                 "- G3 (owner): free tier keeps it — Adi\n")
    (fd / "plan.md").write_text(PLAN + "\n## Rulings\n- T3: Ruling: used existing cache — signature in plan was wrong — "
                                "stale reads if wrong\n")
    at.main(["pr-body", "tiny", "--summary", "Adds tiny."])
    out = capsys.readouterr().out
    assert "grill.md" in out
    assert "## Decisions to check" in out
    assert "G2 (assumed): empty list shows a hint" in out
    assert "G1 (answered)" not in out and "G3 (owner)" not in out
    assert "T3: Ruling: used existing cache" in out


def test_pr_body_without_decisions_has_no_section(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    at.main(["pr-body", "tiny", "--summary", "Adds tiny."])
    assert "## Decisions to check" not in capsys.readouterr().out


def test_marketing_topic_tier_needs_no_slug(repo, capsys):
    r = tier(capsys, "marketing-topic")
    assert r["tier"] == "standard" and r["model"] == "sonnet"


def test_tier_audit(repo, capsys):
    deep = tier(capsys, "tech-lead-audit")
    assert deep["tier"] == "deep" and deep["model"] == "opus" and "audit" in deep["reason"]
    quick = tier(capsys, "tech-lead-audit-quick", "--tool", "codex")
    assert quick["tier"] == "standard" and quick["model"] == "gpt-5.4"
