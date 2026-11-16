"""Regression tests for the PR #2 review findings."""
import subprocess

import pytest

from test_agent_team import IDEAS, PLAN, at, new_feature, repo, sh  # noqa: F401  (fixture)


def test_cleanup_refuses_unpushed_commit(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (wt / "work.txt").write_text("precious\n")
    sh("git", "add", "-A", cwd=wt); sh("git", "commit", "-q", "-m", "unpushed", cwd=wt)
    assert at.main(["cleanup", "tiny"]) == 1
    assert "not on the remote" in capsys.readouterr().err
    assert wt.exists() and "feature/tiny" in sh("git", "branch", cwd=repo)


def test_cleanup_refuses_dirty_worktree(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    (wt / "app.txt").write_text("edited\n")
    assert at.main(["cleanup", "tiny"]) == 1
    assert "uncommitted" in capsys.readouterr().err and wt.exists()


def test_idea_prefix_slug_not_confused(repo, capsys):
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(IDEAS + "\n### auth-v2 — Two\n- **Value:** L · **Effort:** M\n\n### auth — One\n- **Value:** H · **Effort:** S\n")
    at.main(["idea", "auth", "--set", "shipped"])
    text = ideas.read_text()
    assert "### auth-v2 — Two\n- **Value:**" in text
    assert "### auth — One\n- **Status:** shipped" in text


@pytest.mark.parametrize("line", ["- [ ] T6 untagged — files: x", "- [ ] T6 [Turbo] odd — files: x"])
def test_tasks_reject_missing_or_unknown_tag(repo, capsys, line):
    wt, fd = new_feature(repo, capsys=capsys)
    plan = fd / "plan.md"
    plan.write_text(PLAN.replace("- [ ] T2", "- [x] T2").replace("- [ ] T3", "- [x] T3")
                    .replace("- [ ] T4", "- [x] T4").replace("- [ ] T5", "- [x] T5") + line + "\n")
    assert at.main(["tasks", "tiny"]) == 1
    assert "T6" in capsys.readouterr().err


def test_tasks_tag_case_insensitive(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (fd / "plan.md").write_text(PLAN.replace("[standard]", "[Standard]"))
    at.main(["tasks", "tiny"])
    assert "standard T4" in capsys.readouterr().out


def test_lease_is_pushed_so_second_machine_is_blocked(repo, tmp_path, monkeypatch, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    at.main(["lease", "tiny", "release"])
    # machine B: its own clone + worktree of the same feature
    b = tmp_path / "b"
    sh("git", "clone", "-q", str(tmp_path / "remote.git"), str(b), cwd=tmp_path)
    sh("git", "config", "user.email", "b@b", cwd=b); sh("git", "config", "user.name", "b", cwd=b)
    sh("git", "remote", "set-head", "origin", "main", cwd=b)
    bwt = b / ".agent-team" / "worktrees" / "tiny"
    sh("git", "worktree", "add", "-q", "-b", "feature/tiny", str(bwt), "origin/feature/tiny", cwd=b)
    # A takes the lease (and pushes it)
    assert at.main(["lease", "tiny", "acquire"]) == 0
    # B tries: must see A's lease
    monkeypatch.chdir(b); monkeypatch.setenv("AGENT_TEAM_HOST", "box-b")
    capsys.readouterr()
    assert at.main(["lease", "tiny", "acquire"]) == 1
    assert "running on box-a" in capsys.readouterr().err


def test_lease_race_loser_backs_out(repo, tmp_path, monkeypatch, capsys):
    """Both read 'free' before either pushed: the second push is rejected and that machine doesn't hold it."""
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    assert at.main(["lease", "tiny", "release"]) == 0
    b = tmp_path / "b"
    sh("git", "clone", "-q", str(tmp_path / "remote.git"), str(b), cwd=tmp_path)
    sh("git", "config", "user.email", "b@b", cwd=b); sh("git", "config", "user.name", "b", cwd=b)
    sh("git", "remote", "set-head", "origin", "main", cwd=b)
    bwt = b / ".agent-team" / "worktrees" / "tiny"
    sh("git", "worktree", "add", "-q", "-b", "feature/tiny", str(bwt), "origin/feature/tiny", cwd=b)
    # B takes the lease first; A must see it after fetching and not take it.
    monkeypatch.chdir(b); monkeypatch.setenv("AGENT_TEAM_HOST", "box-b")
    assert at.main(["lease", "tiny", "acquire"]) == 0
    monkeypatch.chdir(repo); monkeypatch.setenv("AGENT_TEAM_HOST", "box-a")
    capsys.readouterr()
    assert at.main(["lease", "tiny", "acquire"]) == 1
    assert "box-b" in capsys.readouterr().err
    assert at.read_status(fd / "status.md")["owner"].startswith("box-b")


def test_review_numbering_continues_after_stop(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (fd / "review-1.md").write_text("x"); (fd / "review-2.md").write_text("x"); (fd / "qa-1.md").write_text("x")
    at.write_status(fd / "status.md", {"review_round": "0"})        # counter reset after a stop
    at.main(["next", "tiny", "review"])
    assert capsys.readouterr().out.strip() == "n=3 file=review-3.md prev=review-2.md"
    at.main(["next", "tiny", "qa"])
    assert capsys.readouterr().out.strip() == "n=2 file=qa-2.md prev=qa-1.md"


def test_sync_with_uncommitted_code_is_not_a_conflict(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (repo / "app.txt").write_text("main\n")
    sh("git", "commit", "-qam", "m", cwd=repo); sh("git", "push", "-q", cwd=repo)
    (wt / "app.txt").write_text("uncommitted\n")
    rc = at.main(["sync", "tiny"])
    err = capsys.readouterr().err
    assert rc == 1 and "uncommitted" in err and "merge conflict with" not in err


def test_sync_ignores_own_status_edits(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    (repo / "other.txt").write_text("x\n")
    sh("git", "add", "-A", cwd=repo); sh("git", "commit", "-qm", "m", cwd=repo); sh("git", "push", "-q", cwd=repo)
    at.write_status(fd / "status.md", {"stage": "review"})          # uncommitted status change
    assert at.main(["sync", "tiny"]) == 0


def test_bad_arguments_give_clear_errors(repo, capsys):
    new_feature(repo, capsys=capsys)
    assert at.main(["status", "tiny", "--set", "stage"]) == 1
    assert "KEY=VALUE" in capsys.readouterr().err
    assert at.main(["tier", "reviewer"]) == 1
    assert "slug" in capsys.readouterr().err


def test_project_excludes_without_slash_match_anywhere(repo):
    (repo / ".agent-team" / "project.md").write_text(
        (repo / ".agent-team" / "project.md").read_text().replace("- `vendor/**`", "- `*.gen.ts`"))
    specs = at.exclude_specs(at.project_md())
    assert ":(exclude,glob)**/*.gen.ts" in specs


@pytest.mark.parametrize("existing", ["/.agent-team/worktrees/", ".agent-team/worktrees", ".agent-team/worktrees/"])
def test_upgrade_no_duplicate_gitignore(repo, existing):
    (repo / ".gitignore").write_text(existing + "\n")
    at.main(["upgrade"])
    assert (repo / ".gitignore").read_text().count("worktrees") == 1


def test_lease_push_rejected_backs_out(repo, tmp_path, monkeypatch, capsys):
    """True race: B pushes its lease after A fetched. A's push is rejected; A must not keep a local lease commit."""
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    assert at.main(["lease", "tiny", "release"]) == 0
    head_before = sh("git", "rev-parse", "HEAD", cwd=wt)
    real_catch_up = at._catch_up
    def b_wins_after_fetch(wt_, branch):
        real_catch_up(wt_, branch)
        b = tmp_path / "b"
        if not b.exists():
            sh("git", "clone", "-q", "-b", branch, str(tmp_path / "remote.git"), str(b), cwd=tmp_path)
            sh("git", "config", "user.email", "b@b", cwd=b); sh("git", "config", "user.name", "b", cwd=b)
            st = b / ".agent-team" / "features" / "tiny" / "status.md"
            at.write_status(st, {"owner": "box-b 2099-01-01T00:00+00:00"})
            sh("git", "commit", "-qam", "b lease", cwd=b); sh("git", "push", "-q", cwd=b)
    monkeypatch.setattr(at, "_catch_up", b_wins_after_fetch)
    assert at.main(["lease", "tiny", "acquire"]) == 3
    err = capsys.readouterr().err
    assert "another machine pushed first" in err and "box-b" in err
    assert sh("git", "rev-parse", "HEAD", cwd=wt) != head_before          # caught up to B's commit
    assert at.read_status(fd / "status.md")["owner"].startswith("box-b")
    assert sh("git", "status", "--porcelain", cwd=wt) == ""


def test_lease_release_refuses_other_owner(repo, monkeypatch, capsys):
    new_feature(repo, capsys=capsys)
    assert at.main(["push", "tiny"]) == 0
    monkeypatch.setenv("AGENT_TEAM_HOST", "box-b")
    assert at.main(["lease", "tiny", "release"]) == 1
    assert "belongs to box-a" in capsys.readouterr().err


def test_cleanup_force_overrides(repo, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    assert at.main(["cleanup", "tiny", "--force"]) == 0
    assert not wt.exists()


# ---------- docs-commit (finding 6) ----------

def protect_main(tmp_path):
    hook = tmp_path / "remote.git" / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do\n'
                    '  if [ "$ref" = "refs/heads/main" ] && [ ! -f "$GIT_DIR/allow-main" ]; then\n'
                    '    echo "remote: error: GH006: Protected branch update failed for refs/heads/main." >&2; exit 1\n'
                    '  fi\ndone\n')
    hook.chmod(0o755)
    return tmp_path / "remote.git" / "allow-main"


def test_docs_commit_unprotected_keeps_local_main_clean(repo, capsys):
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### new-one — New\n- **Status:** proposed\n")
    assert at.main(["docs-commit", "-m", "docs: ideas", ".agent-team/ideas.md"]) == 0
    assert "pushed to main" in capsys.readouterr().out
    assert sh("git", "rev-parse", "HEAD", cwd=repo) == sh("git", "rev-parse", "origin/main", cwd=repo)
    assert "new-one" in sh("git", "show", "origin/main:.agent-team/ideas.md", cwd=repo)
    assert sh("git", "status", "--porcelain", cwd=repo) == ""


def test_docs_commit_protected_goes_to_meta_and_pull_still_works(repo, tmp_path, capsys):
    allow = protect_main(tmp_path)
    head = sh("git", "rev-parse", "HEAD", cwd=repo)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### first — First\n- **Status:** proposed\n")
    (repo / ".claude").mkdir(); (repo / ".claude" / "settings.json").write_text("{}\n")
    assert at.main(["docs-commit", "-m", "docs: a", ".agent-team/ideas.md", ".claude/settings.json"]) == 0
    out = capsys.readouterr().out
    assert "pushed to agent-team/meta" in out and "may ask for permissions" in out
    assert sh("git", "rev-parse", "HEAD", cwd=repo) == head                 # no local commit on main
    assert not (repo / ".claude" / "settings.json").exists()                # reset: pulls must fast-forward
    assert "first" in at.read_doc(".agent-team/ideas.md")                   # meta wins while open
    assert at.main(["idea", "first"]) == 0
    # a second docs change while the meta PR is open lands on meta too, keeping the first
    at.main(["idea", "first", "--set", "rejected"])
    assert at.main(["docs-commit", "-m", "docs: b", ".agent-team/ideas.md"]) == 0
    meta = sh("git", "show", "origin/agent-team/meta:.agent-team/ideas.md", cwd=repo)
    assert "### first — First\n- **Status:** rejected" in meta
    # owner squash-merges the meta PR on GitHub
    allow.write_text("")
    other = tmp_path / "squash"
    sh("git", "clone", "-q", str(tmp_path / "remote.git"), str(other), cwd=tmp_path)
    sh("git", "config", "user.email", "o@o", cwd=other); sh("git", "config", "user.name", "o", cwd=other)
    sh("git", "merge", "-q", "--squash", "origin/agent-team/meta", cwd=other)
    sh("git", "commit", "-qm", "squash docs", cwd=other); sh("git", "push", "-q", cwd=other)
    sh("git", "pull", "-q", "--ff-only", cwd=repo)                          # finding 6: this used to fail
    assert "rejected" in ideas.read_text() and (repo / ".claude" / "settings.json").exists()


def test_docs_pull_seeds_checkout_from_open_meta(repo, tmp_path, capsys):
    protect_main(tmp_path)
    ideas = repo / ".agent-team" / "ideas.md"
    ideas.write_text(ideas.read_text() + "\n### first — First\n- **Status:** proposed\n")
    at.main(["docs-commit", "-m", "a", ".agent-team/ideas.md"])
    assert "first" not in ideas.read_text()                                 # reset after pushing to meta
    capsys.readouterr()
    at.main(["docs-pull"])
    assert ".agent-team/ideas.md" in capsys.readouterr().out and "first" in ideas.read_text()
    # PM appends another idea to the seeded copy; the commit merges cleanly onto meta
    ideas.write_text(ideas.read_text() + "\n### second — Second\n- **Status:** proposed\n")
    assert at.main(["docs-commit", "-m", "b", ".agent-team/ideas.md"]) == 0
    meta = sh("git", "show", "origin/agent-team/meta:.agent-team/ideas.md", cwd=repo)
    assert "### first" in meta and "### second" in meta
    capsys.readouterr()
    at.main(["idea", "second", "--show"])
    assert capsys.readouterr().out.startswith("### second — Second")


# ---------- ci grace (finding 7) ----------

def fake_gh(tmp_path, monkeypatch, responses):
    """gh stub: each call to `gh pr checks` pops the next (exit, output) from a file."""
    import json
    bin_ = tmp_path / "fakebin"; bin_.mkdir(exist_ok=True)
    state = tmp_path / "gh-state.json"; state.write_text(json.dumps(responses))
    (bin_ / "gh").write_text(f'''#!/usr/bin/env python3
import json, sys
p = "{state}"
r = json.load(open(p))
code, out = r.pop(0) if len(r) > 1 else r[0]
json.dump(r, open(p, "w"))
print(out, file=sys.stderr if code else sys.stdout)
sys.exit(code)
''')
    (bin_ / "gh").chmod(0o755)
    import os
    monkeypatch.setenv("PATH", f"{bin_}:{os.environ['PATH']}")
    monkeypatch.setattr(at, "POLL_SECONDS", 0)


def test_ci_waits_for_checks_to_appear(repo, tmp_path, monkeypatch, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    at.write_status(fd / "status.md", {"pr": "7"})
    no = [1, "no checks reported on the 'feature/tiny' branch"]
    fake_gh(tmp_path, monkeypatch, [no, no, [1, "build\tfail\t1m\turl"]])
    assert at.main(["ci", "tiny", "--grace", "5"]) == 1
    assert "ci: fail" in capsys.readouterr().out


def test_ci_none_only_after_grace(repo, tmp_path, monkeypatch, capsys):
    wt, fd = new_feature(repo, capsys=capsys)
    at.write_status(fd / "status.md", {"pr": "7"})
    fake_gh(tmp_path, monkeypatch, [[1, "no checks reported on the 'feature/tiny' branch"]])
    assert at.main(["ci", "tiny", "--grace", "0"]) == 0
    assert "ci: none (no checks appeared within 0s)" in capsys.readouterr().out
