#!/usr/bin/env python3
"""agent-team helper: the deterministic parts of the team-* workflows, so the model doesn't re-derive them.

Stdlib only (uses PyYAML when present). Run from anywhere inside the product repo or one of its worktrees.
On PATH as `agent-team` after scripts/install.sh; otherwise `python3 <team-build skill>/scripts/agent_team.py`.
Exit codes: 0 ok, 1 failure (message on stderr), 2 merge conflict (sync), 3 push rejected (push).
"""
import argparse
import datetime as dt
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent                      # skills/team-build
SKILLS = SKILL_DIR.parent                    # skills/
MODELS = SKILL_DIR / "references" / "models.yaml"
STATUS_TEMPLATE = SKILL_DIR / "references" / "status-template.md"

TIERS = ("deep", "standard", "fast")
STAGES = ("spec", "plan", "implement", "review", "qa", "pr", "ci", "pr-open", "merged", "marketed", "stopped")
STATUS_KEYS = ("stage", "branch", "pr", "owner", "worktree", "review_round", "qa_round", "ci_round",
               "last_reviewed_commit", "tests", "stop_reason", "stopped_at", "retro")
IDEA_STATUSES = ("proposed", "shipped", "rejected")   # in progress = a feature/<slug> branch exists
LEASE_TTL_HOURS = 2
BIG_DIFF_LINES, BIG_DIFF_FILES = 400, 15
LOCKFILES = ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "pubspec.lock", "Podfile.lock",
             "poetry.lock", "uv.lock", "Pipfile.lock", "Cargo.lock", "Gemfile.lock", "composer.lock", "go.sum")
GENERATED = ("*.g.dart", "*.freezed.dart", "*.mocks.dart", "*.gr.dart", "*.pb.go", "*_pb2.py", "*.min.js",
             "*.min.css", "*.map")
TASK_LINE = re.compile(r"^\s*- \[( |x)\] (T\d+) \[(fast|standard)\]")
ROLE_SKILL = {"pm-spec": "pm", "pm-ideate": "pm"}
ROLES = ("pm-ideate", "pm-spec", "tech-lead", "developer", "reviewer", "qa", "marketing")


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


def project_md():
    p = repo_root() / ".agent-team" / "project.md"
    if not p.exists():
        raise Fail(".agent-team/project.md not found — run team-init first")
    return p.read_text()


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


def rule_tier(role, slug, task=None, escalate=False):
    """The tier rules from the team-build skill. Returns (tier, reason)."""
    base = work_dir(slug) if slug else repo_root()
    fd = feature_dir(base, slug) if slug else None
    read = lambda name: (fd / name).read_text() if fd and (fd / name).exists() else ""
    if role == "pm-ideate":
        return "deep", "ideation"
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
        for line in read("plan.md").splitlines():
            m = TASK_LINE.match(line)
            if m and m.group(2) == task:
                return m.group(3), f"task tag {task}"
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
    m = re.search(rf"^###\s+{re.escape(slug)}\b.*?(?=^###?\s|\Z)", text, re.M | re.S)
    return m.group(0) if m else None


def idea_sources():
    root = repo_root()
    local = root / ".agent-team" / "ideas.md"
    if local.exists():
        yield local.read_text()
    try:
        d = default_branch(root)
    except Fail:
        d = None
    for ref in ([f"origin/{d}"] if d else []) + ["origin/agent-team/meta"]:
        r = run(["git", "show", f"{ref}:.agent-team/ideas.md"], cwd=root, check=False)
        if r.returncode == 0:
            yield r.stdout


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
    pats += re.findall(r"^\s*-\s*`?([^`\s]+)`?", section(project_text, "Diff excludes"), re.M)
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
    parts = [now_utc().strftime("%Y-%m-%d %H:%MZ"), a.stage, a.role]
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


def cmd_lease(a):
    wt = worktree(a.slug)
    branch = f"feature/{a.slug}"
    if a.action == "acquire" and wt.exists():
        if git("ls-remote", "--heads", "origin", branch, cwd=wt, check=False):
            git("fetch", "-q", "origin", branch, cwd=wt)
            r = run(["git", "merge", "--ff-only", f"origin/{branch}"], cwd=wt, check=False)
            if r.returncode:
                raise Fail(f"local {branch} has diverged from origin; resolve by hand before resuming")
    p = status_path(a.slug)
    if a.action == "release":
        write_status(p, {"owner": "none"})
        return
    owner = read_status(p).get("owner", "none")
    host, _, when = owner.partition(" ")
    if owner and owner != "none" and host != me() and not a.takeover:
        try:
            fresh = now_utc() - dt.datetime.fromisoformat(when) < dt.timedelta(hours=LEASE_TTL_HOURS)
        except ValueError:
            fresh = False
        if fresh:
            raise Fail(f"{a.slug} is running on {host} (last update {when}). "
                       f"Wait, or rerun with --takeover if that run is dead.")
    write_status(p, {"owner": f"{me()} {now_utc().isoformat(timespec='minutes')}"})
    print(f"lease: {me()}")


def cmd_tier(a):
    tool = a.tool or os.environ.get("AGENT_TEAM_TOOL", "claude")
    r = pick(a.role, a.slug, tool, a.task, a.escalate)
    print(f"tier={r['tier']} model={r['model']} effort={r['effort']} reason={r['reason']}")


def cmd_tasks(a):
    plan = feature_dir(work_dir(a.slug), a.slug) / "plan.md"
    batches = []
    for line in plan.read_text().splitlines():
        m = TASK_LINE.match(line)
        if not m:
            continue
        if m.group(1) == "x":
            if batches and batches[-1][0] != "done":
                batches.append(("done", []))
            continue
        if batches and batches[-1][0] == m.group(3):
            batches[-1][1].append(m.group(2))
        else:
            batches.append((m.group(3), [m.group(2)]))
    todo = [(t, ids) for t, ids in batches if t != "done"]
    if not todo:
        print("all tasks done")
    for tier, ids in todo:
        print(f"{tier} {','.join(ids)}")


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
    git("fetch", "-q", "origin", d, cwd=wt)
    if run(["git", "merge-base", "--is-ancestor", f"origin/{d}", "HEAD"], cwd=wt, check=False).returncode == 0:
        print(f"up to date with origin/{d}")
        return 0
    r = run(["git", "merge", "--no-edit", f"origin/{d}"], cwd=wt, check=False)
    if r.returncode:
        files = git("diff", "--name-only", "--diff-filter=U", cwd=wt, check=False)
        run(["git", "merge", "--abort"], cwd=wt, check=False)
        raise Fail(f"merge conflict with origin/{d} in: {', '.join(files.split()) or '?'}", code=2)
    print(f"merged origin/{d}")
    return 0


def cmd_push(a):
    wt = worktree(a.slug)
    branch = f"feature/{a.slug}"
    r = run(["git", "push", "-u", "origin", branch], cwd=wt, check=False)
    if r.returncode == 0:
        print(f"pushed {branch}")
        return 0
    git("fetch", "-q", "origin", branch, cwd=wt, check=False)
    rs = run(["git", "show", f"origin/{branch}:.agent-team/features/{a.slug}/status.md"], cwd=wt, check=False)
    owner = read_status_text(rs.stdout).get("owner", "unknown") if rs.returncode == 0 else "unknown"
    raise Fail(f"push rejected ({(r.stderr or '').strip().splitlines()[-1:] or ['?']}). Remote owner: {owner}. "
               f"Never force-push; stop and tell the owner.", code=3)


def cmd_idea(a):
    if a.set:
        p = repo_root() / ".agent-team" / "ideas.md"
        set_idea_status(p, a.slug, a.set)
        print(f"{a.slug}: {a.set}")
        return
    info = idea_info(a.slug)
    print(f"status={info['status']} effort={info['effort'] or '?'}")


def cmd_ci(a):
    pr = read_status(status_path(a.slug)).get("pr", "none")
    if pr in ("", "none"):
        raise Fail("no pr in status.md")
    cmd = ["gh", "pr", "checks", pr] + (["--watch", "--interval", "30"] if a.watch else [])
    r = run(cmd, cwd=work_dir(a.slug), check=False)
    out = (r.stdout + r.stderr).strip()
    if "no checks reported" in out.lower():
        print("ci: none")
        return 0
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
    for p in sorted((root / ".agent-team" / "features").glob("*/status.md")):
        sources.append((p.parent.name, p.read_text()))
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


def cmd_cleanup(a):
    root = repo_root()
    wt = worktree(a.slug)
    branch = f"feature/{a.slug}"
    if wt.exists():
        git("worktree", "remove", "--force", str(wt), cwd=root)
        print(f"removed worktree {wt}")
    if git("rev-parse", "--verify", "-q", f"refs/heads/{branch}", cwd=root, check=False):
        git("branch", "-D", branch, cwd=root)
        print(f"deleted local {branch}")
    if a.remote and git("ls-remote", "--heads", "origin", branch, cwd=root, check=False):
        git("push", "origin", "--delete", branch, cwd=root)
        print(f"deleted origin/{branch}")


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
    s.add_argument("slug"); s.add_argument("--set", choices=IDEA_STATUSES); s.set_defaults(fn=cmd_idea)
    s = sub.add_parser("ci", help="PR check result: pass, fail, none or pending")
    s.add_argument("slug"); s.add_argument("--watch", action="store_true"); s.set_defaults(fn=cmd_ci)
    s = sub.add_parser("pr-body", help="print the PR body")
    s.add_argument("slug"); s.add_argument("--summary"); s.add_argument("--stopped", metavar="REASON")
    s.set_defaults(fn=cmd_pr_body)
    s = sub.add_parser("summary", help="all features: stage, rounds, tokens, cost")
    s.set_defaults(fn=cmd_summary)
    s = sub.add_parser("cleanup", help="remove a merged feature's worktree and branches")
    s.add_argument("slug"); s.add_argument("--remote", action="store_true"); s.set_defaults(fn=cmd_cleanup)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except Fail as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
