# 🤝 agent-team

**A small AI product team that lives in your repo.** It dreams up features, plans them, builds them, reviews its own work, tests it and opens a pull request. You only say *"yes, build that"* and *"yes, merge it"*.

## 😩 The problem

You've already built your product. Now every new feature means the same slog: decide what to build, plan it, code it, review it, test it, write the launch post. Doing that with an AI assistant still means babysitting every step, and it burns expensive tokens on work a cheaper model could do.

## ✨ What agent-team does

Six specialists, each running on the **cheapest model that can do the job**:

| | Role | Job |
|---|---|---|
| 💡 | **PM** | Suggests features and writes the spec |
| 🧭 | **Tech Lead** | Grills the PM on the spec, then plans how to build it, test-first |
| 🛠️ | **Developer** | Writes the code test-first, and fixes bugs at the root cause |
| 🔍 | **Reviewer** | Checks the code against the spec and plan |
| ✅ | **QA** | Verifies every acceptance criterion |
| 📣 | **Marketing** | Drafts Instagram, blog, LinkedIn and Reddit posts (nothing is posted for you) |

```mermaid
flowchart LR
    A["💡 PM suggests ideas"] --> B{{"👤 You pick one"}}
    B --> C0["🧭 Grill the spec"] --> C["🧭 Plan"] --> D["🛠️ Build"] --> E["🔍 Review"] --> F["✅ QA"] --> G["Pull request"]
    G --> H{{"👤 You merge"}}
    H --> I["📣 Launch drafts"]
```

The two 👤 steps are the only ones that need you. The one exception: if grilling the spec turns up a question that changes scope or what users see, the run stops and asks you in a **draft PR**. Smaller calls the agents make for you are listed in the PR. If something gets stuck, you get a draft PR explaining why, not a question in the middle of a run.

## 🚀 Get started

**1. Install once per machine**

In Claude Code:

```
/plugin install agent-team --marketplace mishraaditya595/agent-team
```

For Codex, Gemini CLI or other tools:

```bash
git clone https://github.com/mishraaditya595/agent-team ~/agent-team
pip install pyyaml   # needed for Codex profiles
~/agent-team/scripts/install.sh
```

**2. Set up your product repo**, then ask for ideas

```
team-init       # learns your project
team-ideate     # PM suggests up to 5 features
```

Got your own idea? `team-ideate add "keep drafts on the device when offline"`

**3. Build it**

```
team-build <idea-name>
```

Review the pull request it opens and merge it. Done. 🎉

## 🧰 Commands

| Command | What it does |
|---|---|
| `team-init` | One-time setup for a product repo |
| `team-ideate` | Get feature ideas, or add/reject your own |
| `team-audit [quick\|deep]` | Tech Lead audits the code (bugs, security, tests, debt, direction) and adds the best fixes as ideas |
| `team-build <name>` | Spec → grill → plan → code → review → QA → PR |
| `team-status` | See every feature's stage and cost |
| `team-wrap <name>` | After merging: close it out and save lessons |
| `team-market <name>` | Draft launch posts and release notes |
| `team-market --topic "…"` | Draft Instagram, blog, LinkedIn and Reddit posts for any idea, plan or topic |

Works with **Claude Code**, **Codex**, **Gemini CLI** and any tool that supports Agent Skills.

## 📚 Learn more

Helper CLI, model tiers and cost rules, adding your own role, and development setup are in **[docs/reference.md](docs/reference.md)**.

Credits: see [NOTICE](NOTICE) · License: MIT
