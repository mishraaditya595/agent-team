#!/usr/bin/env python3
"""agent-team helper: the deterministic parts of the team-* workflows, so the model doesn't re-derive them.

Stdlib only (uses PyYAML when present). Run from anywhere inside the product repo or one of its worktrees.
On PATH as `agent-team` after scripts/install.sh; otherwise `python3 <team-build skill>/scripts/agent_team.py`.
Exit codes: 0 ok, 1 failure (message on stderr), 2 merge conflict (sync), 3 push rejected (push).
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent                      # skills/team-build
SKILLS = SKILL_DIR.parent                    # skills/
MODELS = SKILL_DIR / "references" / "models.yaml"
STATUS_TEMPLATE = SKILL_DIR / "references" / "status-template.md"
INIT_REFS = SKILLS / "team-init" / "references"
WORKTREES_IGNORE = ".agent-team/worktrees/"
META = "agent-team/meta"            # docs branch used when the default branch is protected
REJECTED = re.compile(r"\[rejected\]|non-fast-forward|fetch first|stale info|\[remote rejected\]", re.I)
PROTECTED = re.compile(r"protected branch|GH006|GH013|repository rule|required status|review is required", re.I)
POLL_SECONDS = 15

TIERS = ("deep", "standard", "fast")
STAGES = ("spec", "plan", "implement", "review", "qa", "pr", "ci", "pr-open", "merged", "marketed", "stopped")
STATUS_KEYS = ("stage", "branch", "pr", "owner", "worktree", "review_round", "qa_round", "ci_round",
               "last_reviewed_commit", "tests", "stop_reason", "stopped_at", "retro")
IDEA_STATUSES = ("proposed", "shipped", "rejected")   # in progress = a feature/<slug> branch exists
LEASE_TTL_HOURS = 6   # a lease older than this (no log/commit since) counts as abandoned
BIG_DIFF_LINES, BIG_DIFF_FILES = 400, 15
LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "pubspec.lock", "Podfile.lock",
             "poetry.lock", "uv.lock", "Pipfile.lock", "Cargo.lock", "Gemfile.lock", "composer.lock", "go.sum")
GENERATED = ("*.g.dart", "*.freezed.dart", "*.mocks.dart", "*.gr.dart", "*.pb.go", "*_pb2.py", "*.min.js",
             "*.min.css", "*.map")
CHECKBOX = re.compile(r"^\s*- \[( |x|X)\]")
TASK_LINE = re.compile(r"^\s*- \[( |x|X)\] (T\d+)\b(?:\s+\[([^\]]*)\])?", re.I)
ROLE_SKILL = {"pm-spec": "pm", "pm-ideate": "pm", "pm-intake": "pm"}
ROLES = ("pm-ideate", "pm-intake", "pm-spec", "tech-lead", "developer", "reviewer", "qa", "marketing")


class Fail(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


# ---------- small helpers ----------

def run(cmd, cwd=None, check=True, shell=False):
    try:
        r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, shell=shell)
    except FileNotFoundError:
        if check:
            raise Fail(f"command not found: {cmd[0]}")
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]}: not found")
    if check and r.returncode:
        raise Fail((r.stderr or r.stdout).strip() or f"{cmd} failed")
    return r


def _last_line(r):
    lines = (r.stderr or r.stdout or "").strip().splitlines()
    return lines[-1].strip() if lines else "?"


def git(*args, cwd=None, check=True):
    return run(["git", *args], cwd=cwd, check=check).stdout.strip()


def _scalar(v):
    v = v.strip()
    if v.startswith("{") and v.endswith("}"):
        pairs = (p.split(":", 1) for p in v[1:-1].split(",") if p.strip())
        return {k.strip(): _scalar(x) for k, x in pairs}
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    return v.strip("'\"")


def mini_yaml(text):
    """Enough YAML for models.yaml and skill frontmatter: nested maps, flow maps/lists, scalars, comments."""
    root, stack = {}, [(-1, {})]
    stack[0] = (-1, root)
    for raw in text.splitlines():
        if raw.lstrip().startswith("#") or not raw.strip():
            continue
        line = re.sub(r"\s+#.*$", "", raw).rstrip()
        indent = len(line) - len(line.lstrip())
        key, _, val = line.strip().partition(":")
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        if val.strip():
            parent[key.strip()] = _scalar(val)
        else:
            parent[key.strip()] = {}
            stack.append((indent, parent[key.strip()]))
    return root


def load_yaml(text):
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        return mini_yaml(text)


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return load_yaml(m.group(1)) if m else {}


def section(text, heading):
    """Body of a '## heading' section (heading matched case-insensitively), or ''."""
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    return re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S).strip() if m else ""


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def me():
    return os.environ.get("AGENT_TEAM_HOST") or socket.gethostname()


# ---------- repo layout ----------

def repo_root():
    return Path(git("rev-parse", "--path-format=absolute", "--git-common-dir")).parent


def worktree(slug):
    return repo_root() / ".agent-team" / "worktrees" / slug


def feature_dir(base, slug):
    return Path(base) / ".agent-team" / "features" / slug


def status_path(slug):
    wt = worktree(slug)
    p = feature_dir(wt, slug) / "status.md"
    return p if wt.exists() else feature_dir(repo_root(), slug) / "status.md"


def work_dir(slug):
    wt = worktree(slug)
    return wt if wt.exists() else repo_root()


def default_branch(root=None):
    root = root or repo_root()
    ref = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", cwd=root, check=False)
    if ref:
        return ref.split("/", 1)[1]
    r = run(["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"], cwd=root, check=False)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    for b in ("main", "master"):
        if git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{b}", cwd=root, check=False):
            return b
    raise Fail("can't find the default branch; run `git remote set-head origin --auto`")


def show(ref, rel, cwd=None):
    r = run(["git", "show", f"{ref}:{rel}"], cwd=cwd or repo_root(), check=False)
    return r.stdout if r.returncode == 0 else None


def meta_pr_open(root):
    """True/False when gh can tell whether agent-team/meta has an open PR; None when it can't."""
    r = run(["gh", "pr", "list", "--head", META, "--state", "open", "--json", "number", "-q", "length"],
            cwd=root, check=False)
    if r.returncode != 0:
        return None
    return r.stdout.strip() not in ("", "0")


def _is_ancestor(a, b, root):
    return run(["git", "merge-base", "--is-ancestor", a, b], cwd=root, check=False).returncode == 0


def meta_newer(root, d, rel):
    """Is agent-team/meta's copy of rel newer than the default branch's? Only if meta's last change to it
    was built on top of the default branch's last change to it. After a squash merge (branch kept, as
    GitHub does by default) that's never true, so a stale meta can't shadow later edits."""
    if not git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{META}", cwd=root, check=False):
        return False
    ma = git("log", "-1", "--format=%H", f"origin/{META}", "--", rel, cwd=root, check=False)
    da = git("log", "-1", "--format=%H", f"origin/{d}", "--", rel, cwd=root, check=False)
    if not ma or ma == da:
        return False
    if not da or _is_ancestor(da, ma, root):
        return True
    if _is_ancestor(ma, da, root):
        return False
    t = lambda c: int(git("log", "-1", "--format=%ct", c, cwd=root, check=False) or 0)
    return t(ma) > t(da)


def meta_active(root, d, rel=None, pr_open="ask"):
    """Should agent-team/meta's copy count (for one doc, or for any .agent-team file)?"""
    if not git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{META}", cwd=root, check=False):
        return False
    if (meta_pr_open(root) if pr_open == "ask" else pr_open) is False:
        return False                       # gh says its PR is merged/closed: the default branch is current
    rels = [rel] if rel else git("diff", "--name-only", f"origin/{d}", f"origin/{META}", "--", ".agent-team",
                                 cwd=root, check=False).splitlines()
    return any(meta_newer(root, d, r) for r in rels)


def read_doc(rel):
    """An agent-team doc (project.md, ideas.md, lessons.md): agent-team/meta's copy while it's live
    (open PR, newer than the default branch), else the local checkout, else origin/<default>."""
    root = repo_root()
    try:
        d = default_branch(root)
        main_v = show(f"origin/{d}", rel, root)
    except Fail:
        d, main_v = None, None
    meta_v = show(f"origin/{META}", rel, root) if d and meta_active(root, d, rel) else None
    if meta_v is not None and meta_v != main_v:
        return meta_v
    local = root / rel
    if local.exists():
        return local.read_text()
    return main_v if main_v is not None else meta_v


DOCS = (".agent-team/project.md", ".agent-team/ideas.md", ".agent-team/lessons.md")


def _seed_record(root, rel):
    return Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=root)) / "agent-team-seed" / rel


def seed_doc(rel):
    """Make the checkout's copy the newest one (read_doc), remembering what it was seeded from, so a
    later docs-commit merges against that and not against HEAD."""
    root = repo_root()
    text = read_doc(rel)
    local = root / rel
    if text is None or (local.exists() and local.read_text() == text):
        return False
    if local.exists() and local.read_text() != (show("HEAD", rel, root) or ""):
        raise Fail(f"{rel} has uncommitted edits; commit them with `agent-team docs-commit` first")
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(text)
    rec = _seed_record(root, rel)
    rec.parent.mkdir(parents=True, exist_ok=True)
    rec.write_text(text)
    return True


def project_md():
    text = read_doc(".agent-team/project.md")
    if text is None:
        raise Fail(".agent-team/project.md not found — run team-init first")
    return text


def project_command(name, text=None):
    """`- Test: `cmd`` from project.md ## Build & test; None when missing or 'none'."""
    body = section(text if text is not None else project_md(), "Build & test")
    m = re.search(rf"^\s*-\s*{name}:\s*`([^`]+)`", body, re.M | re.I)
    if not m or m.group(1).strip().lower().startswith("none"):
        return None
    return m.group(1).strip()


# ---------- status.md ----------

LINE = re.compile(r"^([a-z_]+):(\s*)(.*?)(\s+#.*)?$")


def read_status_text(text):
    head = text.split("\n## Log", 1)[0]
    vals = {}
    for line in head.splitlines():
        m = LINE.match(line)
        if m:
            vals[m.group(1)] = m.group(3).strip()
    return vals


def read_status(path):
    if not path.exists():
        raise Fail(f"{path} is missing")
    return read_status_text(path.read_text())


def check_status_values(updates):
    for k, v in updates.items():
        if k not in STATUS_KEYS:
            raise Fail(f"unknown status key '{k}' (known: {', '.join(STATUS_KEYS)})")
        if k in ("stage", "stopped_at") and v not in STAGES and not (k == "stopped_at" and v == "none"):
            raise Fail(f"unknown stage '{v}' (known: {', '.join(STAGES)})")
        if k.endswith("_round") and not v.isdigit():
            raise Fail(f"{k} must be a number")


def write_status(path, updates):
    check_status_values(updates)
    out, done, in_head = [], set(), True
    for line in path.read_text().splitlines():
        if in_head and line.startswith("## Log"):
            out += [f"{k}: {v}" for k, v in updates.items() if k not in done]
            done.update(updates)
            in_head = False
        m = LINE.match(line) if in_head else None
        if m and m.group(1) in updates:
            line = f"{m.group(1)}: {updates[m.group(1)]}{m.group(4) or ''}"
            done.add(m.group(1))
        out.append(line)
    out += [f"{k}: {v}" for k, v in updates.items() if k not in done]
    path.write_text("\n".join(out) + "\n")


def append_log(path, line):
    text = path.read_text()
    if "## Log" not in text:
        text += "\n## Log\n"
    path.write_text(text.rstrip("\n") + "\n" + line + "\n")


# ---------- models / tiers ----------

def models():
    data = load_yaml(MODELS.read_text())
    return data.get("tools") or {}, data.get("effort") or {}


def role_meta(skill):
    p = SKILLS / skill / "SKILL.md"
    if not p.exists():
        raise Fail(f"unknown role skill '{skill}'")
    meta = frontmatter(p.read_text()).get("metadata") or {}
    return meta.get("tier"), list(meta.get("allowed-tiers") or [meta.get("tier")])


def overrides(text):
    out = {}
    for m in re.finditer(r"^\s*-\s*([\w-]+):\s*(deep|standard|fast)\b", section(text, "Model overrides"), re.M):
        out[m.group(1)] = m.group(2)
    return out


def clamp(tier, allowed):
    if tier in allowed:
        return tier
    i = TIERS.index(tier)
    return min(allowed, key=lambda t: abs(TIERS.index(t) - i))


def spec_effort(spec):
    m = re.search(r"effort:\s*([SML])\b", spec)
    return m.group(1) if m else None


def ac_count(spec):
    return len(re.findall(r"^\s*-\s*AC\d+\b", spec, re.M))


def plan_flag(plan, key):
    m = re.search(rf"{key}:\s*(yes|no)\b", plan, re.I)
    return bool(m and m.group(1).lower() == "yes")


def security_touchpoints(plan):
    body = section(plan, "Security touchpoints").strip().lower()
    return bool(body) and not re.fullmatch(r"[-*\s]*none\.?", body)


def plan_tasks(plan):
    """[(done, id, tier)] for every checkbox line in plan.md's ## Tasks. Fails on a missing or unknown tag."""
    body = section(plan, "Tasks")
    if not body:
        raise Fail("plan.md has no '## Tasks' section")
    out = []
    for line in body.splitlines():
        if not CHECKBOX.match(line):
            continue
        m = TASK_LINE.match(line)
        tag = (m.group(3) or "").strip().lower() if m else ""
        if not m or tag not in ("fast", "standard"):
            raise Fail(f"plan.md task needs an id and a [fast] or [standard] tag: {line.strip()}")
        out.append((m.group(1).lower() == "x", m.group(2).upper(), tag))
    return out


def rule_tier(role, slug, task=None, escalate=False):
    """The tier rules from the team-build skill. Returns (tier, reason)."""
    base = work_dir(slug) if slug else repo_root()
    fd = feature_dir(base, slug) if slug else None
    read = lambda name: (fd / name).read_text() if fd and (fd / name).exists() else ""
    if role == "pm-ideate":
        return "deep", "ideation"
    if role == "pm-intake":
        return "standard", "shaping the owner's idea"
    if role == "pm-spec":
        eff = idea_info(slug).get("effort")
        return ("standard", "idea effort S") if eff == "S" else ("deep", f"idea effort {eff or '?'}")
    if role == "tech-lead":
        spec = read("spec.md")
        if spec_effort(spec) == "S" and 0 < ac_count(spec) <= 2:
            return "standard", "effort S and <= 2 ACs"
        return "deep", "default"
    if role == "developer":
        if escalate:
            return "standard", "escalated after 2 failures"
        if not task:
            raise Fail("developer needs --task T<n>")
        for _, tid, tag in plan_tasks(read("plan.md")):
            if tid == task.upper():
                return tag, f"task tag {tid}"
        raise Fail(f"task {task} not found in plan.md")
    if role == "reviewer":
        lines, files = diffstat(slug)
        if lines > BIG_DIFF_LINES or files > BIG_DIFF_FILES:
            return "deep", f"large diff ({lines} lines, {files} files)"
        if security_touchpoints(read("plan.md")):
            return "deep", "security touchpoints in plan"
        return "standard", f"diff {lines} lines, {files} files"
    if role == "qa":
        return ("standard", "plan says qa-ui: yes") if plan_flag(read("plan.md"), "qa-ui") else ("fast", "no UI checks")
    if role == "marketing":
        return ("deep", "launch: true") if re.search(r"launch:\s*true", read("spec.md")) else ("standard", "default")
    raise Fail(f"unknown role '{role}' (known: {', '.join(ROLES)})")


def pick(role, slug, tool, task=None, escalate=False):
    skill = ROLE_SKILL.get(role, role)
    _, allowed = role_meta(skill)
    ov = overrides(project_md())
    forced = ov.get(role) or ov.get(skill)
    tier, reason = (forced, "project override") if forced else rule_tier(role, slug, task, escalate)
    picked = clamp(tier, allowed)
    if picked != tier:
        reason += f"; {tier} not allowed for {skill}"
    tools, effort = models()
    model = (tools.get(tool) or {}).get(picked)
    return {"tier": picked, "model": model or "session", "effort": effort.get(picked, "-"),
            "reason": reason + ("" if model else f"; no {tool} model in models.yaml -> fallback")}


# ---------- ideas ----------

def idea_block(text, slug):
    m = re.search(rf"^###[ \t]+{re.escape(slug)}(?=[ \t]|$).*?(?=^###?\s|\Z)", text, re.M | re.S)
    return m.group(0) if m else None


def idea_sources():
    text = read_doc(".agent-team/ideas.md")
    if text is not None:
        yield text


def idea_info(slug):
    for text in idea_sources():
        block = idea_block(text, slug)
        if block:
            st = re.search(r"\*\*Status:\*\*\s*(\w+)", block)
            eff = re.search(r"\*\*Effort:\*\*\s*([SML])", block)
            return {"status": st.group(1) if st else "proposed", "effort": eff.group(1) if eff else None}
    raise Fail(f"unknown slug '{slug}': not in .agent-team/ideas.md")


def set_idea_status(path, slug, status):
    if status not in IDEA_STATUSES:
        raise Fail(f"idea status must be one of {', '.join(IDEA_STATUSES)}")
    text = path.read_text()
    block = idea_block(text, slug)
    if not block:
        raise Fail(f"'{slug}' not in {path}")
    if re.search(r"\*\*Status:\*\*", block):
        new = re.sub(r"(\*\*Status:\*\*\s*)\w+", rf"\g<1>{status}", block, count=1)
    else:
        head, _, rest = block.partition("\n")
        new = f"{head}\n- **Status:** {status}\n{rest}"
    path.write_text(text.replace(block, new, 1))


# ---------- diff ----------

def exclude_specs(project_text=""):
    pats = [f"**/{p}" for p in LOCKFILES + GENERATED]
    for p in re.findall(r"^\s*-\s*`?([^`\s]+)`?", section(project_text, "Diff excludes"), re.M):
        p = p.lstrip("/") if p.startswith("/") else (p if "/" in p else f"**/{p}")
        pats.append(p)
    return [":(exclude).agent-team"] + [f":(exclude,glob){p}" for p in pats if p.lower() != "none"]


def diff_args(slug, since=None):
    rng = f"{since}..HEAD" if since else f"origin/{default_branch()}...HEAD"
    return [rng, "--", ".", *exclude_specs(project_md())]


def diffstat(slug, since=None):
    out = git("diff", "--shortstat", *diff_args(slug, since), cwd=work_dir(slug))
    files = re.search(r"(\d+) files? changed", out)
    ins = re.search(r"(\d+) insertions?", out)
    dels = re.search(r"(\d+) deletions?", out)
    n = lambda m: int(m.group(1)) if m else 0
    return n(ins) + n(dels), n(files)


def code_key(wt):
    """Last commit touching code (not .agent-team/), or None if code has uncommitted changes."""
    dirty = git("status", "--porcelain", "--", ".", ":(exclude).agent-team", cwd=wt)
    if dirty:
        return None
    return git("log", "-1", "--format=%h", "--", ".", ":(exclude).agent-team", cwd=wt) or None


# ---------- commands ----------

def cmd_default_branch(a):
    print(default_branch())


def cmd_init_status(a):
    wt = worktree(a.slug)
    if not wt.exists():
        raise Fail(f"no worktree at {wt}")
    p = feature_dir(wt, a.slug) / "status.md"
    if p.exists():
        raise Fail(f"{p} already exists")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(STATUS_TEMPLATE.read_text().replace("<slug>", a.slug))
    write_status(p, {"owner": f"{me()} {now_utc().isoformat(timespec='minutes')}"})
    print(p)


def cmd_status(a):
    p = status_path(a.slug)
    if a.set:
        bad = [kv for kv in a.set if "=" not in kv]
        if bad:
            raise Fail(f"--set takes KEY=VALUE pairs; got: {' '.join(bad)}")
        updates = dict(kv.split("=", 1) for kv in a.set)
        write_status(p, updates)
        return
    vals = read_status(p)
    if a.key:
        print(vals.get(a.key, ""))
    else:
        print("\n".join(f"{k}: {v}" for k, v in vals.items()))


def cmd_log(a):
    p = status_path(a.slug)
    parts = [now_utc().strftime("%Y-%m-%dT%H:%MZ"), a.stage, a.role]
    parts += [f"tier={a.tier}", f"model={a.model}"]
    if a.tokens:
        parts.append(f"tokens={a.tokens}")
    if a.cost:
        parts.append(f"cost={a.cost}")
    if a.note:
        parts.append(" ".join(a.note))
    append_log(p, " ".join(parts))
    owner = read_status(p).get("owner", "none")
    if owner.split(" ")[0] == me():
        write_status(p, {"owner": f"{me()} {now_utc().isoformat(timespec='minutes')}"})


def _status_rel(slug):
    return f".agent-team/features/{slug}/status.md"


def _commit_status(wt, slug, msg):
    """Commit only status.md; returns True if there was something to commit."""
    rel = _status_rel(slug)
    git("add", "--", rel, cwd=wt)
    if run(["git", "diff", "--cached", "--quiet", "--", rel], cwd=wt, check=False).returncode == 0:
        return False
    git("commit", "-q", "-m", msg, "--", rel, cwd=wt)
    return True


def _catch_up(wt, branch):
    """Fast-forward the worktree to origin/<branch> if it exists; fail if they diverged."""
    if not git("ls-remote", "--heads", "origin", branch, cwd=wt, check=False):
        return False
    git("fetch", "-q", "origin", branch, cwd=wt)
    if run(["git", "merge", "--ff-only", f"origin/{branch}"], cwd=wt, check=False).returncode:
        raise Fail(f"local {branch} has diverged from origin/{branch}; resolve by hand before resuming")
    return True


def cmd_lease(a):
    """The lease lives in status.md on the pushed branch: taking it is a commit + push, so a second machine
    either sees it after fetching, or (if both raced) gets its push rejected and backs out."""
    wt = worktree(a.slug)
    branch = f"feature/{a.slug}"
    if not wt.exists():
        raise Fail(f"no worktree at {wt}")
    _catch_up(wt, branch)
    p = feature_dir(wt, a.slug) / "status.md"
    owner = read_status(p).get("owner", "none")
    host, _, when = owner.partition(" ")
    if a.action == "acquire" and owner not in ("", "none") and host != me() and not a.takeover:
        try:
            fresh = now_utc() - dt.datetime.fromisoformat(when) < dt.timedelta(hours=LEASE_TTL_HOURS)
        except ValueError:
            fresh = False
        if fresh:
            raise Fail(f"{a.slug} is running on {host} (last update {when}). "
                       f"Wait, or rerun with --takeover if that run is dead.")
    if a.action == "release" and owner not in ("", "none") and host != me() and not a.takeover:
        raise Fail(f"the lease belongs to {host}, not {me()}; not releasing it")
    new = "none" if a.action == "release" else f"{me()} {now_utc().isoformat(timespec='minutes')}"
    write_status(p, {"owner": new})
    committed = _commit_status(wt, a.slug, f"chore({a.slug}): lease {a.action} by {me()} [skip ci]")
    r = run(["git", "push", "-u", "origin", branch], cwd=wt, check=False)
    if r.returncode:
        if committed:
            run(["git", "reset", "-q", "--keep", "HEAD~1"], cwd=wt, check=False)
        if not REJECTED.search(r.stderr or ""):
            raise Fail(f"lease {a.action}: push failed (network, sign-in or permissions?): {_last_line(r)}")
        try:
            _catch_up(wt, branch)
        except Fail:
            pass
        other = read_status(p).get("owner", "unknown")
        raise Fail(f"lease {a.action} not recorded: another machine pushed first (owner now: {other}). "
                   f"Don't touch the PR or status; tell the owner.", code=3)
    print(f"lease: {'released' if a.action == 'release' else me()}")


def cmd_tier(a):
    tool = a.tool or os.environ.get("AGENT_TEAM_TOOL", "claude")
    if not a.slug and a.role not in ("pm-ideate", "pm-intake"):
        raise Fail(f"tier {a.role} needs the feature slug: agent-team tier {a.role} <slug>")
    r = pick(a.role, a.slug, tool, a.task, a.escalate)
    print(f"tier={r['tier']} model={r['model']} effort={r['effort']} reason={r['reason']}")


def cmd_tasks(a):
    plan = feature_dir(work_dir(a.slug), a.slug) / "plan.md"
    if not plan.exists():
        raise Fail(f"{plan} is missing")
    batches = []
    for done, tid, tag in plan_tasks(plan.read_text()):
        if done:
            if batches and batches[-1][0] != "done":
                batches.append(("done", []))
            continue
        if batches and batches[-1][0] == tag:
            batches[-1][1].append(tid)
        else:
            batches.append((tag, [tid]))
    todo = [(t, ids) for t, ids in batches if t != "done"]
    if not todo:
        print("all tasks done")
    for tier, ids in todo:
        print(f"{tier} {','.join(ids)}")


def cmd_next(a):
    fd = feature_dir(work_dir(a.slug), a.slug)
    nums = sorted(int(m.group(1)) for p in fd.glob(f"{a.kind}-*.md")
                  if (m := re.fullmatch(rf"{a.kind}-(\d+)\.md", p.name)))
    n = (nums[-1] if nums else 0) + 1
    print(f"n={n} file={a.kind}-{n}.md prev={f'{a.kind}-{nums[-1]}.md' if nums else 'none'}")


def cmd_diff(a):
    wt = work_dir(a.slug)
    if a.shortstat:
        lines, files = diffstat(a.slug, a.since)
        print(f"{lines} lines, {files} files")
        return
    args = ["diff"] + (["--stat"] if a.stat else ["--unified=3"]) + diff_args(a.slug, a.since)
    sys.stdout.write(git(*args, cwd=wt) + "\n")


def cmd_test(a):
    wt = worktree(a.slug)
    if not wt.exists():
        raise Fail(f"no worktree at {wt}")
    text = project_md()
    p = feature_dir(wt, a.slug) / "status.md"
    key = code_key(wt)
    cmds = (project_command("Build", text) or "") + "\n" + (project_command("Test", text) or "")
    if key:
        key += "+" + hashlib.sha1(cmds.encode()).hexdigest()[:6]
    cached = read_status(p).get("tests", "none")
    if key and not a.force and not a.build and cached.split(" ")[0] == key:
        print(f"tests (cached for {key}): {cached.split(' ', 1)[1]}")
        return 0 if cached.endswith("pass") else 1
    steps = ([("Build", project_command("Build", text))] if a.build else []) + [("Test", project_command("Test", text))]
    for name, cmd in steps:
        if not cmd:
            print(f"{name}: none configured in project.md")
            continue
        print(f"$ {cmd}")
        r = run(cmd, cwd=wt, check=False, shell=True)
        out = (r.stdout + r.stderr).strip().splitlines()
        if r.returncode:
            print("\n".join(out[-40:]))
            if key:
                write_status(p, {"tests": f"{key} fail({name.lower()})"})
            print(f"{name}: FAILED (exit {r.returncode})")
            return 1
        print("\n".join(out[-3:]))
    if key:
        write_status(p, {"tests": f"{key} pass"})
    print("tests: pass")
    return 0


def cmd_sync(a):
    wt = worktree(a.slug)
    d = default_branch()
    dirty = git("status", "--porcelain", "--", ".", f":(exclude).agent-team/features/{a.slug}", cwd=wt)
    if dirty:
        raise Fail("uncommitted changes in the worktree (not a merge conflict); commit or discard them first:\n"
                   + dirty)
    git("fetch", "-q", "origin", d, cwd=wt)
    if run(["git", "merge-base", "--is-ancestor", f"origin/{d}", "HEAD"], cwd=wt, check=False).returncode == 0:
        print(f"up to date with origin/{d}")
        return 0
    r = run(["git", "merge", "--no-edit", f"origin/{d}"], cwd=wt, check=False)
    if r.returncode:
        files = git("diff", "--name-only", "--diff-filter=U", cwd=wt, check=False)
        run(["git", "merge", "--abort"], cwd=wt, check=False)
        if not files:
            raise Fail(f"merging origin/{d} failed (not a conflict): {(r.stderr or r.stdout).strip()}")
        raise Fail(f"merge conflict with origin/{d} in: {', '.join(files.split())}", code=2)
    print(f"merged origin/{d}")
    return 0


def cmd_push(a):
    wt = worktree(a.slug)
    branch = f"feature/{a.slug}"
    r = run(["git", "push", "-u", "origin", branch], cwd=wt, check=False)
    if r.returncode == 0:
        print(f"pushed {branch}")
        return 0
    if not REJECTED.search(r.stderr or ""):
        raise Fail(f"push failed (network, sign-in or permissions?): {_last_line(r)}")
    git("fetch", "-q", "origin", branch, cwd=wt, check=False)
    rs = run(["git", "show", f"origin/{branch}:.agent-team/features/{a.slug}/status.md"], cwd=wt, check=False)
    owner = read_status_text(rs.stdout).get("owner", "unknown") if rs.returncode == 0 else "unknown"
    raise Fail(f"push rejected: {branch} has commits from elsewhere ({_last_line(r)}). Remote owner: {owner}. "
               f"Never force-push; stop and tell the owner.", code=3)


def cmd_idea(a):
    if a.set:
        p = repo_root() / ".agent-team" / "ideas.md"
        if read_doc(".agent-team/ideas.md") is None:
            raise Fail("no .agent-team/ideas.md")
        if not p.exists() or p.read_text() == (show("HEAD", ".agent-team/ideas.md") or ""):
            seed_doc(".agent-team/ideas.md")      # start from the newest copy (e.g. agent-team/meta)
        set_idea_status(p, a.slug, a.set)
        print(f"{a.slug}: {a.set}")
        return
    if a.show:
        for text in idea_sources():
            block = idea_block(text, a.slug)
            if block:
                print(block.strip())
                return 0
        raise Fail(f"unknown slug '{a.slug}': not in .agent-team/ideas.md")
    info = idea_info(a.slug)
    print(f"status={info['status']} effort={info['effort'] or '?'}")


def cmd_ci(a):
    """Waits for checks to appear (GitHub can take a minute after a push) before deciding there is no CI."""
    pr = read_status(status_path(a.slug)).get("pr", "none")
    if pr in ("", "none"):
        raise Fail("no pr in status.md")
    wd = work_dir(a.slug)
    has_workflows = any((wd / ".github" / "workflows").glob("*.y*ml"))
    grace = a.grace if a.grace is not None else (300 if has_workflows else 60)
    deadline = time.monotonic() + grace
    while True:
        r = run(["gh", "pr", "checks", pr], cwd=wd, check=False)
        out = (r.stdout + r.stderr).strip()
        if "no checks reported" not in out.lower():
            break
        if time.monotonic() >= deadline:
            print(f"ci: none (no checks appeared within {grace}s)")
            return 0
        time.sleep(POLL_SECONDS)
    if a.watch:
        r = run(["gh", "pr", "checks", pr, "--watch", "--interval", "30"], cwd=wd, check=False)
        out = (r.stdout + r.stderr).strip()
    if r.returncode == 0:
        print("ci: pass")
        return 0
    if r.returncode == 8:
        print("ci: pending")
        return 0
    print("\n".join(l for l in out.splitlines() if re.search(r"\bfail", l, re.I)) or out[-2000:])
    print("ci: fail")
    return 1


def github_blob_base(wt, branch):
    url = git("remote", "get-url", "origin", cwd=wt, check=False)
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return f"https://github.com/{m.group(1)}/blob/{branch}/" if m else ""


def cmd_pr_body(a):
    wt = work_dir(a.slug)
    fd = feature_dir(wt, a.slug)
    rel = f".agent-team/features/{a.slug}/"
    base = github_blob_base(wt, f"feature/{a.slug}")
    link = lambda name: f"[{name}]({base}{rel}{name})" if base else f"`{rel}{name}`"
    reports = sorted(p.name for p in fd.glob("review-*.md")) + sorted(p.name for p in fd.glob("qa-*.md"))
    parts = []
    if a.stopped:
        parts.append(f"> **Stopped — needs your decision:** {a.stopped}\n")
    parts.append("## Summary\n" + (a.summary or "<!-- 3 lines -->"))
    parts.append("## Artifacts\n" + "\n".join(f"- {link(n)}" for n in ["spec.md", "plan.md", *reports]))
    st = fd / "status.md"
    log = st.read_text().split("## Log", 1)[1].strip() if st.exists() and "## Log" in st.read_text() else ""
    log = "\n".join(l for l in log.splitlines() if not l.startswith("<!--"))
    parts.append("## Tier / model log\n```\n" + (log or "(empty)") + "\n```")
    print("\n\n".join(parts))


def _sum_usage(log):
    tokens = sum(int(x) for x in re.findall(r"tokens=(\d+)", log))
    cost = sum(float(x) for x in re.findall(r"cost=\$?([\d.]+)", log))
    return tokens, cost


def cmd_summary(a):
    root = repo_root()
    git("fetch", "-q", "--prune", "origin", cwd=root, check=False)
    rows, seen = [], set()
    refs = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/feature/", cwd=root, check=False)
    sources = []
    for ref in refs.split():
        slug = ref.split("/", 2)[2]
        r = run(["git", "show", f"{ref}:.agent-team/features/{slug}/status.md"], cwd=root, check=False)
        if r.returncode == 0:
            sources.append((slug, r.stdout))
    try:
        d = default_branch(root)
        listed = git("ls-tree", "-r", "--name-only", f"origin/{d}", "--", ".agent-team/features", cwd=root, check=False)
    except Fail:
        d, listed = None, ""
    for rel in sorted(listed.splitlines()):
        m = re.fullmatch(r"\.agent-team/features/([^/]+)/status\.md", rel)
        text = show(f"origin/{d}", rel, root) if m else None
        if text is not None:
            sources.append((m.group(1), text))
    for slug, text in sources:
        if slug in seen:
            continue
        seen.add(slug)
        s = read_status_text(text)
        tokens, cost = _sum_usage(text.split("## Log", 1)[-1])
        note = s.get("stop_reason", "none")
        rows.append(f"| {slug} | {s.get('stage', '?')} | {s.get('review_round', '0')} | {s.get('qa_round', '0')} | "
                    f"{s.get('pr', 'none')} | {tokens or '-'} | {f'${cost:.2f}' if cost else '-'} | "
                    f"{'' if note == 'none' else note} |")
    if not rows:
        print("no features yet")
        return
    print("| slug | stage | review | qa | pr | tokens | cost | stop reason |\n|---|---|---|---|---|---|---|---|")
    print("\n".join(rows))


def merged_pr_head(pr, cwd):
    """Head commit of a merged PR, or None (not merged, unknown, or gh unavailable)."""
    if pr in ("", "none", None):
        return None
    r = run(["gh", "pr", "view", pr, "--json", "state,headRefOid", "-q", '.state + " " + .headRefOid'],
            cwd=cwd, check=False)
    state, _, oid = r.stdout.strip().partition(" ")
    return oid if r.returncode == 0 and state == "MERGED" and oid else None


def cmd_cleanup(a):
    """Remove a feature's worktree and branches — only when nothing would be lost (or --force)."""
    root = repo_root()
    wt = worktree(a.slug)
    branch = f"feature/{a.slug}"
    sp = status_path(a.slug)
    pr = read_status(sp).get("pr", "none") if sp.exists() else "none"
    git("fetch", "-q", "--prune", "origin", cwd=root, check=False)
    pr_head = merged_pr_head(pr, root)
    problems = []
    if wt.exists() and git("status", "--porcelain", cwd=wt):
        problems.append(f"uncommitted changes in {wt}")
    tip = git("rev-parse", "--verify", "-q", f"refs/heads/{branch}", cwd=root, check=False)
    if tip and tip != pr_head and not git("branch", "-r", "--contains", tip, cwd=root, check=False):
        n = git("rev-list", "--count", tip, "--not", "--remotes", cwd=root, check=False)
        problems.append(f"{n} commit(s) on {branch} are not on the remote and not in a merged PR")
    remote_tip = git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}", cwd=root, check=False)
    if a.remote and remote_tip:
        try:
            in_default = _is_ancestor(remote_tip, f"origin/{default_branch(root)}", root)
        except Fail:
            in_default = False
        if remote_tip != pr_head and not in_default:
            problems.append(f"origin/{branch} is not merged (no merged PR with that head, and not in the "
                            f"default branch); not deleting it")
    if problems and not a.force:
        raise Fail("not cleaning up: " + "; ".join(problems) + ". Push or discard them, or rerun with --force.")
    if wt.exists():
        git("worktree", "remove", "--force", str(wt), cwd=root)
        print(f"removed worktree {wt}")
    if tip:
        git("branch", "-D", branch, cwd=root)
        print(f"deleted local {branch}")
    if a.remote and remote_tip:
        git("push", "origin", "--delete", branch, cwd=root)
        print(f"deleted origin/{branch}")


# ---------- docs commits (never on the local default branch) ----------

def _expand_paths(root, paths):
    files = []
    for p in paths:
        out = git("ls-files", "-com", "--exclude-standard", "--", p, cwd=root, check=False)
        files += [f for f in out.splitlines() if f] or ([p] if (root / p).is_file() else [])
    return list(dict.fromkeys(files))


def _merge_into(tmp_root, root, rel):
    """3-way merge of the checkout's edits (HEAD -> working copy) into the temp worktree's copy."""
    theirs_p = root / rel
    rec = _seed_record(root, rel)
    base_v = rec.read_text() if rec.exists() else show("HEAD", rel, root)
    base = base_v or ""
    ours_p = tmp_root / rel
    ours = ours_p.read_text() if ours_p.exists() else ""
    if not theirs_p.exists():
        if base_v is None or not ours_p.exists():
            return False                   # never existed / already gone
        if ours != base:
            raise Fail(f"can't delete {rel}: it was changed on the branch being updated")
        ours_p.unlink()
        return True
    theirs = theirs_p.read_text()
    if theirs == base or theirs == ours:
        return False
    if ours == base:
        merged = theirs
    else:
        tmp = tmp_root.parent / f".merge-{os.getpid()}"
        tmp.mkdir(exist_ok=True)
        try:
            for name, text in (("ours", ours), ("base", base), ("theirs", theirs)):
                (tmp / name).write_text(text)
            r = run(["git", "merge-file", "-p", str(tmp / "ours"), str(tmp / "base"), str(tmp / "theirs")],
                    check=False)
        finally:
            for f in tmp.iterdir():
                f.unlink()
            tmp.rmdir()
        if r.returncode:
            raise Fail(f"can't merge {rel}: it changed both here and on the branch being updated; "
                       f"merge or pull that first")
        merged = r.stdout
    ours_p.parent.mkdir(parents=True, exist_ok=True)
    ours_p.write_text(merged)
    return True


def _docs_attempt(root, d, files, msg, to_meta):
    meta_exists = bool(git("ls-remote", "--heads", "origin", META, cwd=root, check=False))
    base = f"origin/{META}" if to_meta and meta_exists else f"origin/{d}"
    tmp_root = root / ".agent-team" / "worktrees" / "_docs"
    if tmp_root.exists():
        git("worktree", "remove", "--force", str(tmp_root), cwd=root, check=False)
    git("worktree", "add", "-q", "--detach", str(tmp_root), base, cwd=root)
    try:
        if base != f"origin/{d}":
            r = run(["git", "merge", "-q", "--no-edit", f"origin/{d}"], cwd=tmp_root, check=False)
            if r.returncode:
                run(["git", "merge", "--abort"], cwd=tmp_root, check=False)
                raise Fail(f"{META} conflicts with {d}; merge its open PR (or fix it) first")
        changed = [f for f in files if _merge_into(tmp_root, root, f)]
        if not changed:
            return None, []
        git("add", "--", *changed, cwd=tmp_root)
        git("commit", "-q", "-m", msg, cwd=tmp_root)
        target = META if to_meta else d
        r = run(["git", "push", "origin", f"HEAD:refs/heads/{target}"], cwd=tmp_root, check=False)
        if r.returncode:
            err = (r.stderr or r.stdout).strip()
            if not to_meta and PROTECTED.search(err):
                return "protected", changed
            raise Fail(f"push to {target} rejected: {err.splitlines()[-1] if err else '?'} — "
                       f"pull and rerun; never force-push")
        return target, changed
    finally:
        git("worktree", "remove", "--force", str(tmp_root), cwd=root, check=False)


def _meta_pr(root, d, title):
    r = run(["gh", "pr", "list", "--head", META, "--state", "open", "--json", "url", "-q", ".[0].url"],
            cwd=root, check=False)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    r = run(["gh", "pr", "create", "--base", d, "--head", META, "--title", title,
             "--body", "agent-team docs (ideas, project context, lessons). Merge to bring them onto the default branch."],
            cwd=root, check=False)
    return r.stdout.strip().splitlines()[-1] if r.returncode == 0 and r.stdout.strip() else None


def cmd_docs_pull(a):
    git("fetch", "-q", "origin", cwd=repo_root(), check=False)
    updated = [rel for rel in DOCS if seed_doc(rel)]
    print("updated: " + (" ".join(updated) if updated else "nothing (checkout copies are current)"))


def cmd_docs_commit(a):
    """Commit agent-team docs edited in the checkout without committing on the local default branch:
    a temp worktree gets the edits, pushes to the default branch, or to agent-team/meta (+ PR) if it's
    protected or meta already has unmerged docs. The checkout's copies are then reset to match."""
    root = repo_root()
    d = default_branch(root)
    git("fetch", "-q", "origin", cwd=root)
    files = _expand_paths(root, a.paths)
    if not files:
        raise Fail("nothing to commit: none of those paths exist")
    meta_open = meta_active(root, d)
    target, changed = _docs_attempt(root, d, files, a.message, to_meta=meta_open)
    if target == "protected":
        target, changed = _docs_attempt(root, d, files, a.message, to_meta=True)
    if target is None:
        print("nothing changed")
        return 0
    # The edits are on the remote now; reset the checkout's copies so later pulls fast-forward
    # (git refuses a pull over local changes even when they're identical to what's coming in).
    for f in changed:
        _seed_record(root, f).unlink(missing_ok=True)
    for f in changed:
        if show("HEAD", f, root) is not None:
            git("checkout", "HEAD", "--", f, cwd=root)
        else:
            (root / f).unlink(missing_ok=True)
    if target == d:
        on_d = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root, check=False) == d
        r = run(["git", "merge", "-q", "--ff-only", f"origin/{d}"], cwd=root, check=False) if on_d else \
            subprocess.CompletedProcess([], 1)
        print(f"pushed to {d}" + ("" if r.returncode == 0 else f" (your checkout isn't on {d} or has local "
                                                                 f"commits: pull it yourself)"))
    else:
        url = _meta_pr(root, d, a.title or "agent-team: docs")
        print(f"pushed to {META} ({d} is protected or has an open docs PR). "
              + (f"PR: {url}" if url else f"Open a PR from {META} into {d}."))
    print("files: " + " ".join(changed))
    if target != d and any(not f.startswith(".agent-team/") for f in changed):
        print(f"note: tool settings in that PR apply here once it's merged and pulled; "
              f"until then the tools may ask for permissions")
    return 0


# ---------- upgrade (repos set up by an older agent-team) ----------

def _headings(text):
    return [m.group(1).strip() for m in re.finditer(r"^##\s+(.+?)\s*$", text, re.M)]


def owner_line(root):
    name = git("config", "user.name", cwd=root, check=False)
    r = run(["gh", "api", "user", "-q", ".login"], cwd=root, check=False)
    login = r.stdout.strip() if r.returncode == 0 else ""
    if name and login:
        return f"{name} (@{login})"
    return name or (f"@{login}" if login else "unknown — owner to fill")


def add_missing_sections(text, template, owner="unknown — owner to fill"):
    """Add template sections the project.md lacks, in template order, without touching existing ones."""
    have = {h.lower() for h in _headings(text)}
    order = _headings(template)
    added = []
    for i, h in enumerate(order):
        if h.lower() in have:
            continue
        body = owner if h.lower() == "owner" else section_raw(template, h)
        if body.startswith("<") and not body.startswith("<!--"):
            body = "unknown — owner to fill"
        block = f"## {h}\n{body}\n\n"
        nxt = next((n for n in order[i + 1:] if n.lower() in have), None)
        m = re.search(rf"^##\s+{re.escape(nxt)}\s*$", text, re.M | re.I) if nxt else None
        if m:
            text = text[:m.start()] + block + text[m.start():]
        else:
            text = text.rstrip("\n") + "\n\n" + block.rstrip("\n") + "\n"
        have.add(h.lower())
        added.append(h)
    return text, added


def section_raw(text, heading):
    m = re.search(rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def merged_allow(existing, project_text):
    """Template allow-list entries (with the project's commands filled in) missing from existing."""
    tpl = json.loads((INIT_REFS / "claude-settings.json").read_text())["permissions"]["allow"]
    cmds = [project_command(n, project_text) for n in ("Install", "Build", "Test")]
    entries = []
    for e in tpl:
        entries += [f"Bash({c}:*)" for c in cmds if c] if e == "{{TEST_COMMANDS}}" else [e]
    return [e for e in dict.fromkeys(entries) if e not in existing]


def cmd_upgrade(a):
    root = repo_root()
    proj = root / ".agent-team" / "project.md"
    if not proj.exists():
        raise Fail(".agent-team/project.md not found — run team-init first")
    touched = [".agent-team/project.md", ".claude/settings.json", ".codex/config.toml", ".gitignore"]
    dirty = git("status", "--porcelain", "--", *touched, cwd=root)
    if dirty:
        raise Fail("these files have uncommitted changes of your own; commit or stash them first so they "
                   "don't get swept into the upgrade commit:\n" + dirty)
    sp = root / ".claude" / "settings.json"
    try:
        data = json.loads(sp.read_text()) if sp.exists() else {}
    except ValueError as e:
        raise Fail(f".claude/settings.json isn't valid JSON ({e}); fix it first — nothing was changed")
    if not isinstance(data, dict) or not isinstance(data.get("permissions", {}), dict) \
            or not isinstance(data.get("permissions", {}).get("allow", []), list):
        raise Fail(".claude/settings.json has an unexpected shape (permissions.allow must be a list); "
                   "nothing was changed")
    changed = []
    text, added = add_missing_sections(proj.read_text(), (INIT_REFS / "project-template.md").read_text(),
                                       owner_line(root))
    if added:
        proj.write_text(text)
        changed.append(".agent-team/project.md")
        print(f"project.md: added sections {', '.join(added)}")
    allow = data.setdefault("permissions", {}).setdefault("allow", [])
    new = merged_allow(allow, text)
    if new:
        allow += new
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(data, indent=2) + "\n")
        changed.append(".claude/settings.json")
        print(f".claude/settings.json: added {len(new)} allow entries: {', '.join(new)}")
    cx = root / ".codex" / "config.toml"
    if not cx.exists():
        cx.parent.mkdir(parents=True, exist_ok=True)
        cx.write_text((INIT_REFS / "codex-project.toml").read_text())
        changed.append(".codex/config.toml")
        print(".codex/config.toml: created")
    gi = root / ".gitignore"
    lines = gi.read_text().splitlines() if gi.exists() else []
    norm = {l.strip().strip("/").rstrip("*").rstrip("/") for l in lines}
    if ".agent-team/worktrees" not in norm:
        gi.write_text("\n".join(lines + [WORKTREES_IGNORE]) + "\n")
        changed.append(".gitignore")
        print(f".gitignore: added {WORKTREES_IGNORE}")
    print("changed: " + (" ".join(changed) if changed else "nothing — already up to date"))


def build_parser():
    ap = argparse.ArgumentParser(prog="agent-team", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("default-branch", help="print the default branch")
    s.set_defaults(fn=cmd_default_branch)
    s = sub.add_parser("init-status", help="write a fresh status.md in the feature's worktree")
    s.add_argument("slug"); s.set_defaults(fn=cmd_init_status)
    s = sub.add_parser("status", help="print status, one key, or set keys")
    s.add_argument("slug"); s.add_argument("key", nargs="?")
    s.add_argument("--set", nargs="+", metavar="KEY=VALUE"); s.set_defaults(fn=cmd_status)
    s = sub.add_parser("log", help="append a log line to status.md")
    s.add_argument("slug"); s.add_argument("stage"); s.add_argument("role")
    s.add_argument("--tier", required=True); s.add_argument("--model", required=True)
    s.add_argument("--tokens"); s.add_argument("--cost"); s.add_argument("note", nargs="*")
    s.set_defaults(fn=cmd_log)
    s = sub.add_parser("lease", help="claim or release a feature run for this machine")
    s.add_argument("slug"); s.add_argument("action", choices=["acquire", "release"])
    s.add_argument("--takeover", action="store_true"); s.set_defaults(fn=cmd_lease)
    s = sub.add_parser("tier", help="pick a role's tier, model and effort")
    s.add_argument("role", choices=ROLES); s.add_argument("slug", nargs="?")
    s.add_argument("--task"); s.add_argument("--escalate", action="store_true")
    s.add_argument("--tool", choices=["claude", "codex", "gemini", "other"]); s.set_defaults(fn=cmd_tier)
    s = sub.add_parser("tasks", help="unticked plan tasks, batched by tier")
    s.add_argument("slug"); s.set_defaults(fn=cmd_tasks)
    s = sub.add_parser("next", help="next review-N.md / qa-N.md number (continues after stops) and the previous file")
    s.add_argument("slug"); s.add_argument("kind", choices=["review", "qa"]); s.set_defaults(fn=cmd_next)
    s = sub.add_parser("diff", help="feature diff without .agent-team/, lockfiles and generated code")
    s.add_argument("slug"); s.add_argument("--since", metavar="SHA")
    s.add_argument("--stat", action="store_true"); s.add_argument("--shortstat", action="store_true")
    s.set_defaults(fn=cmd_diff)
    s = sub.add_parser("test", help="run project tests in the worktree; cached per code commit")
    s.add_argument("slug"); s.add_argument("--build", action="store_true", help="run Build first")
    s.add_argument("--force", action="store_true"); s.set_defaults(fn=cmd_test)
    s = sub.add_parser("sync", help="merge the default branch into the feature branch")
    s.add_argument("slug"); s.set_defaults(fn=cmd_sync)
    s = sub.add_parser("push", help="push the feature branch; explains a rejection")
    s.add_argument("slug"); s.set_defaults(fn=cmd_push)
    s = sub.add_parser("idea", help="print or set an idea's status")
    s.add_argument("slug"); s.add_argument("--set", choices=IDEA_STATUSES)
    s.add_argument("--show", action="store_true", help="print the idea's entry (wherever it lives)")
    s.set_defaults(fn=cmd_idea)
    s = sub.add_parser("ci", help="PR check result: pass, fail, none or pending")
    s.add_argument("slug"); s.add_argument("--watch", action="store_true")
    s.add_argument("--grace", type=int, help="seconds to wait for checks to appear (default 300 with "
                                             ".github/workflows, else 60)")
    s.set_defaults(fn=cmd_ci)
    s = sub.add_parser("pr-body", help="print the PR body")
    s.add_argument("slug"); s.add_argument("--summary"); s.add_argument("--stopped", metavar="REASON")
    s.set_defaults(fn=cmd_pr_body)
    s = sub.add_parser("summary", help="all features: stage, rounds, tokens, cost")
    s.set_defaults(fn=cmd_summary)
    s = sub.add_parser("docs-pull", help="refresh the checkout's agent-team docs from agent-team/meta while "
                                       "its PR is open (run before a role edits them)")
    s.set_defaults(fn=cmd_docs_pull)
    s = sub.add_parser("docs-commit", help="commit agent-team docs to the default branch (or agent-team/meta "
                                         "if protected) without committing on the local default branch")
    s.add_argument("-m", "--message", required=True); s.add_argument("--title")
    s.add_argument("paths", nargs="+"); s.set_defaults(fn=cmd_docs_commit)
    s = sub.add_parser("upgrade", help="bring a repo set up by an older agent-team up to date (adds only)")
    s.set_defaults(fn=cmd_upgrade)
    s = sub.add_parser("cleanup", help="remove a merged feature's worktree and branches")
    s.add_argument("slug"); s.add_argument("--remote", action="store_true")
    s.add_argument("--force", action="store_true", help="also when it would lose unpushed or uncommitted work")
    s.set_defaults(fn=cmd_cleanup)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
