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
REJECTED = re.compile(r"\[rejected\]|non-fast-forward|fetch first|stale info", re.I)       # someone pushed first
REFUSED = re.compile(r"\[remote rejected\]|hook declined|GH006|GH013|protected branch|repository rule", re.I)
PROTECTED = re.compile(r"protected branch|GH006|GH013|repository rule|required status|review is required", re.I)
POLL_SECONDS = 15

TIERS = ("deep", "standard", "fast")
STAGES = ("spec", "grill", "plan", "implement", "review", "qa", "pr", "ci", "pr-open", "merged", "marketed", "stopped")
STATUS_KEYS = ("stage", "branch", "pr", "owner", "worktree", "grill_round", "review_round", "qa_round", "ci_round",
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
ROLE_SKILL = {"pm-spec": "pm", "pm-ideate": "pm", "pm-intake": "pm", "marketing-topic": "marketing",
              "tech-lead-audit": "tech-lead", "tech-lead-audit-quick": "tech-lead"}
ROLES = ("pm-ideate", "pm-intake", "pm-spec", "tech-lead", "tech-lead-audit", "tech-lead-audit-quick",
         "developer", "reviewer", "qa", "marketing", "marketing-topic")


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


def _refusal(r):
    lines = [l.strip() for l in (r.stderr or "").splitlines() if REFUSED.search(l)]
    return lines[0] if lines else _last_line(r)


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


_GH_CACHE = None   # dict while a command runs: one `gh pr list` per command, not per doc read


def meta_pr_open(root):
    """True/False when gh can tell whether agent-team/meta has an open PR; None when it can't."""
    if _GH_CACHE is not None and str(root) in _GH_CACHE:
        return _GH_CACHE[str(root)]
    ans = _meta_pr_open(root)
    if _GH_CACHE is not None:
        _GH_CACHE[str(root)] = ans
    return ans


def _meta_pr_open(root):
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


def _is_seeded(root, rel):
    """True if the checkout's copy is exactly what docs-pull wrote (not an edit of the owner's)."""
    rec, local = _seed_record(root, rel), root / rel
    return rec.exists() and local.exists() and rec.read_text() == local.read_text()


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


def block_command(block, name):
    """`- Test: `cmd`` from a block of project.md text; None when missing or 'none'."""
    m = re.search(rf"^\s*-\s*{name}:\s*`([^`]+)`", block, re.M | re.I)
    if not m or m.group(1).strip().lower().startswith("none"):
        return None
    return m.group(1).strip()


def project_command(name, text=None):
    """`- Test: `cmd`` from project.md ## Build & test; None when missing or 'none'."""
    return block_command(section(text if text is not None else project_md(), "Build & test"), name)


def repos(text=None):
    """Workspace mode: the product repos under project.md ## Repos (one `### <path>` block each), ordered by
    ## Cross-repo rules `Order:` then listing order. [] in a single-repo project."""
    text = text if text is not None else project_md()
    out = []
    for m in re.finditer(r"^###\s+(\S+)[^\n]*\n?(.*?)(?=^###\s|\Z)", section(text, "Repos"), re.M | re.S):
        block = m.group(2)
        field = lambda k: (re.search(rf"^\s*-\s*{k}:\s*`?([^`\n]*?)`?\s*$", block, re.M | re.I) or [None, None])[1]
        out.append({"path": m.group(1).strip("`/"), "role": field("Role") or "", "branch": field("Branch") or None,
                    "block": block})
    om = re.search(r"^\W*Order:\s*(.+)$", section(text, "Cross-repo rules"), re.M | re.I)
    order = [p.strip(" `/") for p in om.group(1).split(",")] if om else []
    rank = lambda r: order.index(r["path"]) if r["path"] in order else len(order)
    return sorted(out, key=rank)    # stable: unlisted repos keep their listing order


def repo_branch(r):
    return r["branch"] or default_branch(repo_root() / r["path"])


def repo_dir(path):
    """The workspace's clone of a product repo; Fail unless it's a git repo's top level."""
    d = repo_root() / path
    top = git("rev-parse", "--show-toplevel", cwd=d, check=False) if d.is_dir() else ""
    if not top or Path(top).resolve() != d.resolve():
        raise Fail(f"{path} (## Repos in project.md) isn't a git repo at {d}")
    return d


def docs_pr_only(text):
    """project.md ## Conventions has `- docs-push: pr-only`: docs never go straight to the default branch.
    text None (no project.md yet) → False."""
    # Lenient on purpose (any bullet, backticks, bold, `pr_only`): a mistyped line must not silently stay off.
    pat = r"^\W*docs[-_ ]?push\W*pr[-_ ]?only\b"
    return bool(text) and bool(re.search(pat, section(text, "Conventions"), re.M | re.I))


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


def planned_at(plan):
    m = re.search(r"planned-at:\s*`?([0-9a-f]{7,40})\b", plan)
    return m.group(1) if m else None


def plan_files(plan):
    """Every backticked path on the bullet ('-' or '*') lines of plan.md's ## Files; globs are skipped."""
    out = []
    for line in section(plan, "Files").splitlines():
        if not re.match(r"\s*[-*]\s", line):
            continue
        for p in re.findall(r"`([^`]+)`", line.split(" — ", 1)[0]):
            p = re.sub(r":\d+(-\d+)?$", "", p.strip())
            if p and "*" not in p and p not in out:
                out.append(p)
    return out


def rule_tier(role, slug, task=None, escalate=False):
    """The tier rules from the team-build skill. Returns (tier, reason)."""
    base = work_dir(slug) if slug else repo_root()
    fd = feature_dir(base, slug) if slug else None
    read = lambda name: (fd / name).read_text() if fd and (fd / name).exists() else ""
    if role == "tech-lead-audit":
        return "deep", "audit"
    if role == "tech-lead-audit-quick":
        return "standard", "quick audit"
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
    if role == "marketing-topic":
        return "standard", "owner's topic"
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
            rp = re.search(r"\*\*Repos:\*\*\s*(.+)$", block, re.M)
            return {"status": st.group(1) if st else "proposed", "effort": eff.group(1) if eff else None,
                    "repos": [p.strip(" `/") for p in rp.group(1).split(",") if p.strip(" `/")] if rp else []}
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


# ---------- agent rules (the repo's own AGENTS.md / CLAUDE.md) ----------

RULES_FILES = ("AGENTS.md", "CLAUDE.md")


def rules_root():
    """Nearest folder at or above the cwd holding .agent-team/ (a feature worktree or the main checkout)."""
    for d in (Path.cwd(), *Path.cwd().parents):
        if (d / ".agent-team").is_dir():
            return d
    return repo_root()


def _include_only(f, listed):
    """A CLAUDE.md whose every line is `@<file>` naming a file already listed adds nothing."""
    lines = [l.strip() for l in f.read_text(errors="replace").splitlines() if l.strip()]
    return bool(lines) and all(l.startswith("@") and os.path.realpath(f.parent / l[1:]) in listed for l in lines)


def rule_files(root, paths, fallback=None):
    """Rules files governing paths: each AGENTS.md/CLAUDE.md from the path's folder up to root, root-most first.
    A folder missing under root (product worktree not created yet) is read from fallback instead."""
    root = Path(root).resolve()
    folders = set()
    for p in paths:
        if Path(p).is_absolute() or ".." in Path(os.path.normpath(p)).parts:
            raise Fail(f"{p} is outside the repo root {root}")
        rel = Path(os.path.normpath(p))
        d = rel if (root / rel).is_dir() or (fallback and (Path(fallback) / rel).is_dir()) else rel.parent
        folders.update([d, *d.parents])
    out, real = [], set()
    for d in sorted(folders, key=lambda d: (len(d.parts), d.as_posix())):
        base = root if (root / d).is_dir() or not fallback else Path(fallback)
        for name in RULES_FILES:
            f = base / d / name
            if not f.is_file():
                continue
            rp = os.path.realpath(f)
            if rp in real or (name == "CLAUDE.md" and _include_only(f, real)):
                continue
            real.add(rp)
            out.append((d / name).as_posix())
    return out


def feature_paths(slug):
    """Files the feature touches: its diff plus the plan's ## Files (which may not exist yet)."""
    paths = git("diff", "--name-only", *diff_args(slug), cwd=work_dir(slug)).splitlines()
    plan = feature_dir(work_dir(slug), slug) / "plan.md"
    return list(dict.fromkeys(paths + (plan_files(plan.read_text()) if plan.exists() else [])))


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
        if REFUSED.search(r.stderr or ""):
            raise Fail(f"lease {a.action}: push refused by the server (branch protection or a hook on "
                       f"{branch}): {_refusal(r)}")
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
    if not a.slug and a.role not in ("pm-ideate", "pm-intake", "marketing-topic", "tech-lead-audit", "tech-lead-audit-quick"):
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


def cmd_drift(a):
    wt = work_dir(a.slug)
    plan = feature_dir(wt, a.slug) / "plan.md"
    if not plan.exists():
        raise Fail(f"{plan} is missing")
    text = plan.read_text()
    sha = planned_at(text)
    if not sha:
        print("drift: unchecked (no planned-at line in plan.md; written before drift checks)")
        return 0
    files = plan_files(text)
    if not files:
        print("drift: unchecked (no paths in ## Files to watch)")
        return 0
    d = default_branch()
    git("fetch", "-q", "origin", d, cwd=wt)
    if run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=wt, check=False).returncode:
        print(f"drift: unchecked (planned-at {sha} isn't in this clone — shallow clone or rewritten history)")
        return 0
    changed = git("diff", "--name-only", sha, f"origin/{d}", "--", *files, cwd=wt).split()
    print(f"drift: {', '.join(changed) if changed else 'none'}")
    return 0


def cmd_rules(a):
    t = a.targets
    if len(t) == 1 and feature_dir(work_dir(t[0]), t[0]).is_dir():
        root, paths = work_dir(t[0]), feature_paths(t[0])
    else:
        root, paths = rules_root(), t or ["."]
        if not t and read_doc(".agent-team/project.md") is not None:
            paths += [r["path"] for r in repos()]       # each product repo's top-level rules too
    found = rule_files(root, paths, fallback=repo_root() if root != repo_root() else None)
    print("\n".join(found) if found else "none")


def cmd_repos(a):
    rs = repos()
    if not rs:
        print("single-repo")
        return 0
    for r in rs:
        d = repo_dir(r["path"])
        print(f"{r['path']} {repo_branch(r)} {git('log', '-1', '--format=%h %s', cwd=d, check=False)}")


def cmd_audit_path(a):
    """Next free .agent-team/audits/<date>[-n].md, checking the checkout, origin/<default> and origin/agent-team/meta,
    plus every earlier audit report as a path or a <ref>:<path> for `git show`."""
    root = repo_root()
    d = default_branch(root)
    rel_dir = ".agent-team/audits"
    taken, earlier = set(), []
    local = root / rel_dir
    for f in sorted(local.glob("*.md")) if local.is_dir() else []:
        rel = f"{rel_dir}/{f.name}"
        taken.add(rel); earlier.append(rel)
    for ref in (f"origin/{d}", f"origin/{META}"):
        if not git("rev-parse", "--verify", "-q", f"refs/remotes/{ref}", cwd=root, check=False):
            continue
        for rel in git("ls-tree", "-r", "--name-only", ref, "--", rel_dir, cwd=root, check=False).splitlines():
            if rel.endswith(".md") and rel not in taken:
                taken.add(rel); earlier.append(f"{ref}:{rel}")
    date = a.date or now_utc().strftime("%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise Fail(f"--date must be YYYY-MM-DD, got {date!r}")
    path, n = f"{rel_dir}/{date}.md", 1
    while path in taken:
        n += 1
        path = f"{rel_dir}/{date}-{n}.md"
    print(f"path: {path}")
    for e in earlier:
        print(f"earlier: {e}")
    return 0


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
    if REFUSED.search(r.stderr or ""):
        raise Fail(f"push refused by the server (branch protection or a hook on {branch}): {_refusal(r)}. "
                   f"agent-team needs to push feature/* branches; check the repo's rules.")
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
    print(f"status={info['status']} effort={info['effort'] or '?'}"
          + (f" repos={','.join(info['repos'])}" if info["repos"] else ""))


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


def _section_lines(path, heading):
    if not path.exists():
        return []
    m = re.search(rf"^## {heading}\s*$(.*?)(?=^## |\Z)", path.read_text(), re.M | re.S)
    return [l.strip() for l in m.group(1).splitlines() if l.strip().startswith("- ")] if m else []


def _decisions_to_check(fd):
    """Assumed grill answers (spec.md ## Decisions) and developer rulings (plan.md ## Rulings)."""
    assumed = [l for l in _section_lines(fd / "spec.md", "Decisions") if "(assumed)" in l]
    rulings = [l for l in _section_lines(fd / "plan.md", "Rulings") if "Ruling:" in l]
    return assumed + rulings


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
    grill = ["grill.md"] if (fd / "grill.md").exists() else []
    parts.append("## Artifacts\n" + "\n".join(f"- {link(n)}" for n in ["spec.md", *grill, "plan.md", *reports]))
    checks = _decisions_to_check(fd)
    if checks:
        parts.append("## Decisions to check\nCalls the agents made on your behalf — assumed grill answers and "
                     "the developer's rulings.\n" + "\n".join(checks))
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
        problems.append(f"uncommitted changes in {wt} — commit or discard them")
    tip = git("rev-parse", "--verify", "-q", f"refs/heads/{branch}", cwd=root, check=False)
    if tip and tip != pr_head and not git("branch", "-r", "--contains", tip, cwd=root, check=False):
        n = git("rev-list", "--count", tip, "--not", "--remotes", cwd=root, check=False)
        problems.append(f"{n} commit(s) on {branch} are not on the remote and not in a merged PR — push them")
    remote_tip = git("rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}", cwd=root, check=False)
    if a.remote and remote_tip:
        try:
            in_default = _is_ancestor(remote_tip, f"origin/{default_branch(root)}", root)
        except Fail:
            in_default = False
        if remote_tip != pr_head and not in_default:
            problems.append(f"origin/{branch} is not merged (no merged PR with that head, and not in the "
                            f"default branch) — merge its PR first, or run without --remote")
    if problems and not a.force:
        raise Fail("not cleaning up: " + "; ".join(problems) + ". Rerun with --force only if that's really "
                   "what you want.")
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
    live = to_meta and meta_exists and meta_active(root, d)
    base = f"origin/{META}" if live else f"origin/{d}"
    tmp_root = root / ".agent-team" / "worktrees" / "_docs"
    if tmp_root.exists():
        git("worktree", "remove", "--force", str(tmp_root), cwd=root, check=False)
    git("worktree", "add", "-q", "--detach", str(tmp_root), base, cwd=root)
    try:
        if live:
            r = run(["git", "merge", "-q", "--no-edit", f"origin/{d}"], cwd=tmp_root, check=False)
            if r.returncode:
                run(["git", "merge", "--abort"], cwd=tmp_root, check=False)
                raise Fail(f"{META} (open PR) conflicts with {d}; resolve that PR's conflicts first")
        elif to_meta and meta_exists:
            # Old meta whose PR was merged/closed: start from the default branch, and record the old
            # meta as a parent (keeping the default branch's content) so the push stays a fast-forward.
            git("merge", "-q", "-s", "ours", "--no-edit", "-m", f"chore: restart {META} from {d}",
                f"origin/{META}", cwd=tmp_root)
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


def cmd_pull(a):
    """`git pull --ff-only` for the default branch, safe with docs-pull's uncommitted copies: copies nobody
    edited since docs-pull wrote them are put back first (git refuses to pull over them, even when
    identical), then the newest docs are pulled in again. Copies that were edited are never discarded."""
    root = repo_root()
    d = default_branch(root)
    if git("rev-parse", "--abbrev-ref", "HEAD", cwd=root, check=False) != d:
        raise Fail(f"the checkout must be on the default branch ({d}) to pull")
    edited = []
    for rel in DOCS:
        rec = _seed_record(root, rel)
        if not rec.exists():
            continue
        if _is_seeded(root, rel):
            if show("HEAD", rel, root) is not None:
                git("checkout", "HEAD", "--", rel, cwd=root)
            else:
                (root / rel).unlink(missing_ok=True)
            rec.unlink()
        elif (root / rel).exists() and (root / rel).read_text() != (show("HEAD", rel, root) or ""):
            edited.append(rel)
        else:
            rec.unlink()                       # back to HEAD already: the record is stale
    r = run(["git", "pull", "-q", "--ff-only"], cwd=root, check=False)
    if r.returncode:
        hint = (f" These docs were edited after docs-pull wrote them and aren't committed: {', '.join(edited)} — "
                f"commit them with `agent-team docs-commit`, or discard them, then rerun.") if edited else ""
        raise Fail(f"git pull --ff-only failed: {_last_line(r)}.{hint}")
    updated = [rel for rel in DOCS if seed_doc(rel)]
    print(f"pulled {d}" + (f"; docs from {META}: {' '.join(updated)}" if updated else ""))


def cmd_docs_commit(a):
    """Commit agent-team docs edited in the checkout without committing on the local default branch:
    a temp worktree gets the edits, pushes to the default branch, or to agent-team/meta (+ PR) if it's
    protected, meta already has unmerged docs, or project.md says docs-push: pr-only. The checkout's
    copies are then reset to match."""
    root = repo_root()
    d = default_branch(root)
    git("fetch", "-q", "origin", cwd=root)
    files = _expand_paths(root, a.paths)
    if not files:
        raise Fail("nothing to commit: none of those paths exist")
    # The local copy may lag origin/<default> (another machine set it): either one turns pr-only on.
    to_meta = (docs_pr_only(read_doc(".agent-team/project.md"))
               or docs_pr_only(show(f"origin/{d}", ".agent-team/project.md", root)) or meta_active(root, d))
    target, changed = _docs_attempt(root, d, files, a.message, to_meta=to_meta)
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
        print(f"pushed to {META} ({d} is protected, has an open docs PR, or docs-push is pr-only). "
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
        if h.lower() == "intent docs":            # an older repo may well have ADRs/PRDs: ask, don't claim none
            body = re.sub(r"^none$", "unknown — owner to fill", body, flags=re.M)
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


def nested_repos(root):
    """Workspace detection: top-level folders that are their own git repo and that the workspace gitignores."""
    out = []
    for d in sorted(p for p in Path(root).iterdir() if p.is_dir() and not p.name.startswith(".")):
        top = git("rev-parse", "--show-toplevel", cwd=d, check=False)
        if top and Path(top).resolve() == d.resolve() and \
                run(["git", "check-ignore", "-q", d.name], cwd=root, check=False).returncode == 0:
            out.append(d.name)
    return out


def workspace_sections(paths):
    """## Repos and ## Cross-repo rules drafts for upgrade; commands stay `none` until filled from each repo."""
    blocks = "".join(f"### {p}\n- Role: unknown — owner to fill\n- Install: `none`\n- Build: `none`\n- Test: `none`\n"
                     for p in paths)
    return (f"## Repos\n<!-- One block per product repo; fill commands from its manifests/CI. -->\n{blocks}\n"
            f"## Cross-repo rules\n- Order: {', '.join(paths)}   <!-- merge/ship order; first = earliest -->\n"
            f"unknown — owner to fill\n")


def merged_allow(existing, project_text):
    """Template allow-list entries (with the project's and each product repo's commands) missing from existing."""
    tpl = json.loads((INIT_REFS / "claude-settings.json").read_text())["permissions"]["allow"]
    cmds = [project_command(n, project_text) for n in ("Install", "Build", "Test")]
    cmds += [block_command(r["block"], n) for r in repos(project_text) for n in ("Install", "Build", "Test")]
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
    changed_files = set(git("diff", "--name-only", "HEAD", "--", *touched, cwd=root).splitlines())
    changed_files |= set(git("ls-files", "--others", "--exclude-standard", "--", *touched, cwd=root).splitlines())
    dirty = "\n".join(sorted(f for f in changed_files if f and not _is_seeded(root, f)))
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
    nested = nested_repos(root) if not re.search(r"^##\s+Repos\s*$", text, re.M | re.I) else []
    if nested:
        text = text.rstrip("\n") + "\n\n" + workspace_sections(nested)
        added += ["Repos", "Cross-repo rules"]
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
    s = sub.add_parser("drift", help="files in plan.md changed on the default branch since planned-at")
    s.add_argument("slug"); s.set_defaults(fn=cmd_drift)
    s = sub.add_parser("rules", help="the repo's AGENTS.md/CLAUDE.md files governing a feature's or some paths' code")
    s.add_argument("targets", nargs="*", metavar="SLUG|PATH"); s.set_defaults(fn=cmd_rules)
    s = sub.add_parser("repos", help="workspace mode: the product repos in project.md ## Repos")
    s.set_defaults(fn=cmd_repos)
    s = sub.add_parser("audit-path", help="next free audit report path, and earlier audit reports")
    s.add_argument("--date", help="YYYY-MM-DD (default: today, UTC)"); s.set_defaults(fn=cmd_audit_path)
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
    s = sub.add_parser("pull", help="pull the default branch (instead of `git pull`): puts back unedited "
                                  "docs-pull copies first, then docs-pull again")
    s.set_defaults(fn=cmd_pull)
    s = sub.add_parser("docs-pull", help="refresh the checkout's agent-team docs from agent-team/meta while "
                                       "its PR is open (run before a role edits them)")
    s.set_defaults(fn=cmd_docs_pull)
    s = sub.add_parser("docs-commit", help="commit agent-team docs to the default branch (or agent-team/meta "
                                         "if protected or docs-push: pr-only) without committing on the local default branch")
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
    global _GH_CACHE
    args = build_parser().parse_args(argv)
    _GH_CACHE = {}
    try:
        return args.fn(args) or 0
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        _GH_CACHE = None


if __name__ == "__main__":
    sys.exit(main())
