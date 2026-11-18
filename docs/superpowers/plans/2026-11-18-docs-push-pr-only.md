# docs-push: pr-only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `- docs-push: pr-only` line in `project.md` `## Conventions` makes `agent-team docs-commit` always push to `agent-team/meta` + PR, never to the default branch.

**Architecture:** `cmd_docs_commit` already has a meta path (`_docs_attempt(..., to_meta=True)` + `_meta_pr`). The setting just forces that path from the first attempt. `_docs_attempt` is the only code that pushes to a default branch, so nothing else changes.

**Tech Stack:** Python 3 stdlib, git, pytest.

**Spec:** `docs/superpowers/specs/2026-11-18-multi-repo-workspaces-design.md` (Part 1 only; Parts 2 and 3 get their own plans).

## Global Constraints

- `agent_team.py` stays stdlib-only, single file.
- No `model:` or other tool-specific frontmatter in `skills/**/SKILL.md`.
- Absent setting, or any value other than `pr-only` → behaviour byte-identical to today.
- `python3 -m pytest -q` and `python3 scripts/validate.py .` pass before each commit.

## Review Focus

1. Setting committed only on an open `agent-team/meta` PR (not yet on `main`) still applies — `read_doc` returns the newest copy; test in Task 1.
2. Setting written with different spacing/case (`- Docs-push:  PR-only`) still applies; test in Task 1.
3. `project.md` missing entirely (first `team-init` commit) → `docs-commit` must not crash on the lookup; default behaviour. Test in Task 1.
4. The template's commented example must not turn the setting on (HTML comment lines are not matched); test in Task 1.
5. Protected-branch fallback still works unchanged without the setting — covered by the existing `test_review_fixes.py` / `test_review2_fixes.py` suites.

---

### Task 1: `docs_pr_only()` and its use in `cmd_docs_commit`

**Files:**
- Modify: `skills/team-build/scripts/agent_team.py` (add helper next to `project_command`, ~line 296; use it in `cmd_docs_commit`, ~line 1120)
- Test: `tests/test_docs_pr_only.py` (new)

**Interfaces:**
- Produces: `docs_pr_only(text: str | None) -> bool` — `True` iff `## Conventions` of `text` (`None` → `False`) has a non-comment line matching `^\W*docs[-_ ]?push\W*pr[-_ ]?only\b`, case-insensitive. Caller passes `read_doc(".agent-team/project.md")` and `show("origin/<d>", …)`. (As built; see review fixes.)

- [ ] **Step 1: Write the failing tests** in `tests/test_docs_pr_only.py`, importing `at, repo, sh` from `test_agent_team` (main stays unprotected throughout):

```python
def set_conventions(repo, line):
    p = repo / ".agent-team" / "project.md"
    p.write_text(p.read_text() + f"\n## Conventions\n{line}\n")
    sh("git", "commit", "-qam", "conventions", cwd=repo); sh("git", "push", "-q", cwd=repo)

def add_idea(repo):
    i = repo / ".agent-team" / "ideas.md"
    i.write_text(i.read_text() + "\n### new — New\n- **Status:** proposed\n")

def test_pr_only_goes_to_meta_even_when_unprotected(repo, capsys):
    set_conventions(repo, "- docs-push: pr-only")
    main_before = sh("git", "rev-parse", "origin/main", cwd=repo)
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", ".agent-team/ideas.md"]) == 0
    assert "pushed to agent-team/meta" in capsys.readouterr().out
    sh("git", "fetch", "-q", "origin", cwd=repo)
    assert sh("git", "rev-parse", "origin/main", cwd=repo) == main_before

def test_without_setting_pushes_to_main(repo, capsys):
    set_conventions(repo, "- Commits: conventional")
    add_idea(repo)
    assert at.main(["docs-commit", "-m", "ideas", ".agent-team/ideas.md"]) == 0
    assert "pushed to main" in capsys.readouterr().out

def test_docs_pr_only_parsing():
    base = "# x\n\n## Conventions\n{}\n\n## Channels\nnone\n"
    assert at.docs_pr_only(base.format("- Docs-push:  PR-only"))
    assert not at.docs_pr_only(base.format("<!-- - docs-push: pr-only -->"))
    assert not at.docs_pr_only(base.format("- docs-push: direct"))
    assert not at.docs_pr_only("# x\n\n## Channels\n- docs-push: pr-only\n")   # wrong section
    assert not at.docs_pr_only(None)
```

Dropped at execution: `test_pr_only_set_on_meta_applies` passes without the change (meta with newer docs already routes to meta), so it can't test this feature. Originally: push `project.md` with the setting to `agent-team/meta` only (temp clone, `git push origin HEAD:agent-team/meta`), fetch in `repo`, then `docs-commit` an idea → output contains `pushed to agent-team/meta`.

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest -q tests/test_docs_pr_only.py`
Expected: FAIL — `AttributeError: module 'agent_team' has no attribute 'docs_pr_only'`, and the first test prints `pushed to main`.

- [ ] **Step 3: Implement `docs_pr_only` and use it.** Strip `<!-- … -->` comments from the `section(text, "Conventions")` body before matching (same reason `overrides()` ignores examples). In `cmd_docs_commit`, after `git fetch`, change `meta_open = meta_active(root, d)` to `to_meta = docs_pr_only() or meta_active(root, d)` and pass it to the first `_docs_attempt`. Update the docstring's first line to mention pr-only. Change the meta-path message to say why: `({d} is protected, has an open docs PR, or docs-push is pr-only)`.

- [ ] **Step 4: Run to verify they pass, plus the full suite**

Run: `python3 -m pytest -q`
Expected: all pass (existing docs-commit tests in `test_review_fixes.py`, `test_review2_fixes.py` unchanged).

- [ ] **Step 5: Commit**

```bash
git add skills/team-build/scripts/agent_team.py tests/test_docs_pr_only.py
git commit -m "feat: docs-push: pr-only sends every docs push via agent-team/meta (#8)"
```

### Task 2: Document the setting

**Files:**
- Modify: `skills/team-init/references/project-template.md` (`## Conventions`)
- Modify: `skills/team-init/SKILL.md` (step 5 sentence on where docs-commit pushes)
- Modify: `docs/reference.md:33` and the `docs-commit` row at `:52`
- Modify: `skills/team-build/scripts/agent_team.py` `docs-commit` parser help (~line 1325)

**Interfaces:**
- Consumes: the exact line form `- docs-push: pr-only` from Task 1.

- [ ] **Step 1: Template.** Under `## Conventions`, after the placeholder line, add a comment: `<!-- Optional: `- docs-push: pr-only` sends every agent-team docs push through an agent-team/meta PR, even if the default branch isn't protected. -->`. Comment form, so `upgrade` and new projects stay off by default.

- [ ] **Step 2: Wording.** Everywhere the docs say "if `$D` is protected or an `agent-team/meta` PR is still open", add "or `project.md` sets `docs-push: pr-only`". Same in the argparse help.

- [ ] **Step 3: Verify**

Run: `python3 -m pytest -q && python3 scripts/validate.py .`
Expected: all pass; validate prints no errors. (`test_docs_pr_only_parsing` already proves the template comment doesn't enable it.)

- [ ] **Step 4: Commit**

```bash
git add skills/team-init docs/reference.md skills/team-build/scripts/agent_team.py
git commit -m "docs: document docs-push: pr-only (#8)"
```
