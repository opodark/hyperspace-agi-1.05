# Customization Guide

Your CLAUDE.md is your AI operating system. The more deeply you customize it,
the better Claude performs. This guide walks through each section with examples
and tips for making it truly yours.

---

## The 80/20 of Customization

If you only do four things, do these:

1. **Add real email examples** to the Writing Style section
2. **Define your leadership team** with communication notes
3. **Set your hard time constraints** (dinner time, no early meetings, etc.)
4. **Write your actual goals** in goals.yaml

These four changes will cover 80% of the improvement. Everything else is refinement.

---

## Part-by-Part Guide

### Part 1: Core Principles

**What to customize:**

- **Guardrails** — Add rules specific to your context. If you're a lawyer, add
  "Never draft client communications without attorney review." If you're a
  founder, add "Flag any commitment that requires board approval."

- **Confidentiality** — Define your sensitive topics. What keywords should
  trigger extra caution? What channels are safe for what topics?

**Example guardrails for different roles:**

| Role | Guardrails |
|------|-----------|
| CEO | "Flag any commitment >$50K", "Board communications require extra care" |
| VP Engineering | "Never commit to timelines without team input", "Security issues are always Tier 1" |
| Sales Leader | "Never share pricing without approval", "Competitor mentions are always flagged" |
| Product Manager | "Customer feedback is always Tier 2+", "Roadmap details are confidential externally" |

---

### Part 2: Who You Are

**What to customize:**

This section is about teaching Claude your life context. The more Claude knows,
the better it can anticipate needs and make judgment calls.

**Good entries:**
```markdown
- Partner: Alex — works at Google, usually home by 6:30
- Kids: Sam (5) and Maya (8) — school pickup is at 3:15
- EA: Jordan (jordan@company.com) — "Looping in Jordan to help coordinate"
- Hard constraint: HOME by 5:30pm — flag any conflicts
- Hard constraint: No meetings before 9am unless Tier 1
- Energy: Best deep work in the morning (9-12), meetings afternoon
```

**Why this matters:** If Claude knows you have school pickup at 3:15, it won't
propose a 3pm meeting that runs over. If it knows your EA's name, it can
draft handoff emails naturally.

---

### Part 3: Company Context

**What to customize:**

Give Claude enough context to be effective in your workplace. Focus on:

1. **What your company does** (one line)
2. **Key principles** that affect daily decisions
3. **People Claude needs to know** (your team, board, key stakeholders)

**Example:**
```markdown
- Company: Acme Corp — B2B SaaS for supply chain optimization
- Stage: Series C, 350 employees, $50M ARR
- Key principle: "Customer outcomes over feature shipping"
- E-Team: Sarah (CTO), James (VP Sales), Priya (VP Product), Marcus (CFO)
```

**For the leadership team table**, include communication style notes:
```markdown
| Sarah Chen | CTO | Prefers data-driven arguments. Direct. |
| James Park | VP Sales | Responds fast. Needs exec summary first. |
| Priya Patel | VP Product | Thorough. Appreciates when you've done homework. |
```

---

### Part 4: Writing Style

**This is the most impactful section to customize.**

Claude uses this to draft every email, Slack message, and document in your voice.
Bad writing style instructions = drafts that need heavy editing = no time saved.

**How to get this right:**

1. **Open your Sent Mail folder**
2. **Find 5-10 representative emails** across different contexts:
   - A casual reply to a colleague
   - A professional response to a client or stakeholder
   - A response to criticism or bad news
   - A cold outreach or introduction
   - A scheduling email
3. **Paste them as examples** (anonymize names if needed)
4. **Note your patterns:**
   - How do you start emails? (Name first? "Hey"? Jump right in?)
   - How do you end? ("Best," "Thanks," just your name?)
   - Sentence length? (Short and punchy? Longer and flowing?)
   - Contractions? (I'm/I'd vs I am/I would?)
   - Emoji usage? (Never? Sometimes? Frequently?)
   - Tone shifts? (When are you formal vs casual?)

**Example — well-documented writing style:**
```markdown
### Tone
Direct but warm. Professional with close colleagues, slightly more formal
with external contacts. Never stiff or corporate-sounding.

### Characteristics
- Short paragraphs (1-3 sentences max)
- Start with the person's name for important messages
- Use "Thanks" not "Thank you" — shorter, warmer
- Sign off with just first name for internal, full sig for external
- Contractions always (I'm, I'd, we'll, it's)
- Occasional "!" for enthusiasm, but not every sentence
- Never use "I hope this email finds you well" or similar filler

### Examples

Casual internal:
"Hey Sarah — quick update on the roadmap review. Moving the API
launch to March 15 to give the team more buffer. I'll update the
tracker. Let me know if that causes issues on your end. — Chris"

Professional external:
"David, appreciate the detailed proposal. The pricing model works
for us with one adjustment — we'd need the enterprise tier to include
SSO at no additional cost. If that's workable, I'm ready to move
forward. Happy to jump on a call Thursday to finalize. Chris"

Handling criticism:
"Mark, that's fair feedback and I should have caught it sooner.
I'll own the fix — expect an updated version by EOD Friday.
Can we sync for 15 min tomorrow so I can walk you through
the changes? Chris"
```

---

### Part 5: Relationships & Networks

**What to customize:**

- **Tier definitions** — Who is Tier 1 for you? This varies dramatically by role.
- **Cadence expectations** — How often should you be in touch with key contacts?
- **Contact file conventions** — What information do you want to track?

**Tier 1 examples by role:**

| Role | Tier 1 contacts |
|------|----------------|
| CEO | Board members, co-founders, top 3 customers, partner/family |
| VP Engineering | CTO, direct reports, key architects, partner/family |
| Sales Leader | CEO, top 5 customers, VP Product, partner/family |
| Solo founder | Co-founder, lead investor, top 3 customers, partner/family |

---

### Part 6: Operating Modes

**Usually fine as-is.** The defaults work for most people.

**Customization ideas:**
- Add a "Report" mode if you frequently write status updates
- Add a "Negotiate" mode if you frequently prepare for negotiations
- Rename "Explore" to whatever trigger word feels natural to you

---

### Part 7: Always-On Responsibilities

**What to customize:**

- **Task management preferences** — Do you want Claude to be aggressive about
  task completion, or more of a gentle reminder? Adjust the language.

- **Scheduling preferences** — Add your energy patterns. "Deep work mornings,
  meetings after lunch, no calls on Friday."

- **Time constraints** — Be specific. "No meetings before 9am. Lunch from
  12-1pm is protected. Leave office by 5:15pm to be home by 5:45pm."

---

## Creating Your Own Commands

Commands are just markdown files in `~/.claude/commands/`. You can create
any workflow you want.

**Template for a custom command:**

```markdown
# /command-name — One-Line Description

## Description
What this command does and when to use it.

## Arguments
- `arg1` — What it does
- `arg2` — What it does

## Instructions

### Step 1: [Name]
[What Claude should do]

### Step 2: [Name]
[What Claude should do]

### Guidelines
- [Important rules for this command]
```

**Ideas for custom commands:**

| Command | What It Does |
|---------|-------------|
| `/prep <meeting>` | Prepare for a specific meeting with attendee research and talking points |
| `/weekly` | Generate a weekly status update from calendar and completed tasks |
| `/1on1 <person>` | Prepare for a 1:1 with agenda items, recent context, and open items |
| `/board-update` | Draft a board update from goals progress and key metrics |
| `/review <doc>` | Review a document with specific feedback categories |
| `/debrief` | After a meeting, capture decisions, action items, and follow-ups |

---

## Tips for Continuous Improvement

### The Correction Loop

Every time Claude gets something wrong, that's an opportunity to improve the system.

**Pattern:**
1. Claude drafts something that doesn't sound like you
2. You correct it
3. Ask Claude: "How should I update CLAUDE.md to prevent this in the future?"
4. Claude proposes a specific edit (usually to the Writing Style section)
5. Make the edit

After 2-3 weeks of corrections, Claude will sound remarkably like you.

### Version Your CLAUDE.md

Since CLAUDE.md is just a text file, you can version it with git:

```bash
cd ~/.claude
git init
git add CLAUDE.md goals.yaml
git commit -m "Initial AI Chief of Staff setup"
```

This lets you track changes over time and revert if an edit makes things worse.

### Review Quarterly

At the start of each quarter:
1. Update `goals.yaml` with new objectives
2. Review CLAUDE.md for outdated information (team changes, priority shifts)
3. Add any new custom commands you've been wanting
4. Check contact files for accuracy

### Share What Works

If you build a command or customization that works well, consider sharing it
with the community. The best AI Chief of Staff setups are built by combining
ideas from many people.
