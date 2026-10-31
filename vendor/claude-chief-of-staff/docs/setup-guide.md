# Setup Guide

Get your AI Chief of Staff running in 15 minutes.

---

## Prerequisites

### 1. Claude Code CLI

Install Claude Code from Anthropic:

```bash
# Install via npm
npm install -g @anthropic-ai/claude-code

# Authenticate
claude auth
```

See [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code) for detailed installation instructions.

### 2. MCP Servers

You need at least Gmail and Google Calendar MCP servers for the core experience. See [mcp-servers.md](mcp-servers.md) for detailed installation instructions for each server.

---

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/claude-chief-of-staff.git
cd claude-chief-of-staff
```

### Step 2: Run the Installer

```bash
chmod +x install.sh
./install.sh
```

The installer will:
- Ask for your name, role, company, and preferences
- Create the `~/.claude/` directory structure
- Copy and customize all template files
- Replace placeholders in CLAUDE.md with your information

### Step 3: Connect MCP Servers

At minimum, connect Gmail and Google Calendar. See [mcp-servers.md](mcp-servers.md) for instructions.

After connecting MCP servers, verify they work:

```bash
claude
# In the Claude Code session:
> Search my email for messages from today
> What's on my calendar today?
```

If both work, your core setup is complete.

### Step 4: Customize CLAUDE.md

The installer fills in basic placeholders, but the real power comes from deep customization. Open `~/.claude/CLAUDE.md` and work through each section:

**High-impact customizations (do these now):**

1. **Writing Style (Part 4)** — Paste 2-3 example emails you've sent. This is the single biggest improvement to draft quality.

2. **Leadership Team (Part 3)** — List the people Claude needs to know about. Include their communication style if you know it.

3. **Hard Constraints (Part 2)** — Define your non-negotiable time boundaries. ("Home by 6pm", "No meetings before 9am", etc.)

4. **Confidentiality Rules (Part 1)** — Define what topics require extra caution in your context.

**Medium-impact customizations (do this week):**

5. **Triage Tier definitions** — Who is Tier 1 for you? What makes something urgent?

6. **Operating mode preferences** — Do you want Claude to default to "push hard" or "supportive"?

7. **Personal themes** — What's guiding your year?

See [customization.md](customization.md) for a comprehensive guide to each section.

### Step 5: Set Your Goals

Open `~/.claude/goals.yaml` and replace the example objectives with your real ones.

Tips:
- Keep it to 3-5 objectives (fewer is better)
- Each objective should be specific and time-bound
- Include measurable key results
- Set initial progress to 0.0

### Step 6: Try Your First Commands

```bash
claude
```

Then try these commands:

```
/gm                    # Morning briefing
/triage                # Inbox triage
/my-tasks list         # See your tasks
/my-tasks add "Review quarterly metrics" --due 2026-02-15
/enrich stale          # Check relationship health
```

---

## Directory Structure

After installation, your `~/.claude/` directory looks like this:

```
~/.claude/
├── CLAUDE.md                # Your AI operating system config
├── goals.yaml               # Quarterly objectives
├── my-tasks.yaml            # Active tasks
├── schedules.yaml           # Automation schedules
├── contacts/                # Contact files (one per person)
│   └── example-contact.md   # Template contact
├── commands/                # Skill definitions
│   ├── gm.md                # Morning briefing
│   ├── triage.md            # Inbox triage
│   ├── my-tasks.md          # Task management
│   └── enrich.md            # Contact enrichment
├── objectives/              # Detailed objective files (optional)
└── task-outputs/            # Work product from task execution
```

---

## How It Works

### CLAUDE.md

This is the core of the system. It's a markdown file that Claude reads at the start of every session. It tells Claude:

- Who you are and what you care about
- How you write so drafts sound like you
- What your goals are so Claude knows what matters
- Your time constraints so Claude protects your calendar
- Your relationships so Claude can help maintain them

The better your CLAUDE.md, the better Claude performs. Treat it like onboarding a new chief of staff — the more context you provide upfront, the less you have to correct later.

### Commands (Skills)

Commands are markdown files in `~/.claude/commands/` that define multi-step workflows. When you type `/gm`, Claude reads `commands/gm.md` and follows the instructions.

You can:
- Modify existing commands to fit your workflow
- Create new commands for your specific needs
- Share commands with your team

### Contact Files

Each contact gets a markdown file in `~/.claude/contacts/`. These files accumulate context over time — interaction history, personal notes, communication preferences, talking points.

The more you use the system, the richer these files become. After a few months, Claude will know your network better than any CRM.

### Goals

Goals in `goals.yaml` aren't passive — Claude actively references them when:
- Triaging your inbox (does this email advance a goal?)
- Proposing meetings (does this meeting advance a goal?)
- Prioritizing tasks (which task moves the needle most?)
- Challenging your time allocation (are you spending time on what matters?)

---

## Automation (Optional)

For users who want Claude to run automatically on a schedule:

### macOS (cron)

```bash
# Edit crontab
crontab -e

# Add morning briefing at 7am
0 7 * * * cd ~ && claude --command "/gm" >> ~/.claude/logs/gm.log 2>&1

# Add midday triage at noon
0 12 * * * cd ~ && claude --command "/triage digest" >> ~/.claude/logs/triage.log 2>&1
```

### Manual (Recommended for Getting Started)

Most users start by manually running commands and add automation later.
The commands work just as well when typed manually:

```
/gm              # Run when you start your day
/triage          # Run when you want to clear your inbox
/my-tasks list   # Run when you're planning your day
```

---

## Troubleshooting

### "MCP server not connected"

Make sure the MCP server is installed and configured. See [mcp-servers.md](mcp-servers.md).

### "Permission denied" on install.sh

```bash
chmod +x install.sh
```

### Drafts don't sound like me

This is the most common issue. Fix it by:
1. Adding more writing style examples to CLAUDE.md (Part 4)
2. Pasting 5-10 real emails you've sent
3. Being specific about tone, sentence length, greetings, sign-offs

### Claude doesn't know my team

Add your leadership team to CLAUDE.md (Part 3). Include:
- Names and roles
- Communication style notes
- Any relevant context

### Tasks aren't being tracked

Make sure `~/.claude/my-tasks.yaml` exists and is writable. The installer should have created it.

---

## Getting Help

- **Customization guide:** [customization.md](customization.md)
- **MCP server setup:** [mcp-servers.md](mcp-servers.md)
- **Claude Code docs:** [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code)

---

## What's Next

Once you're comfortable with the basics:

1. **Create contact files** for your 10-20 most important relationships
2. **Write detailed objective files** in `~/.claude/objectives/` for each goal
3. **Build custom commands** for workflows specific to your role
4. **Set up automation** to run triage and briefings on schedule
5. **Iterate on CLAUDE.md** — every correction is a chance to improve the system
