# /triage — Inbox Triage

## Description
Scan all connected communication channels, prioritize items by urgency,
and draft responses in your voice. Clear your inbox in minutes.

## Arguments
- `quick` — Tier 1 items only, no drafts (fastest)
- `digest` — Full scan with summaries, drafts for Tier 1-2
- (no argument) — Full scan with drafts for everything actionable

## Instructions

You are running inbox triage for {{YOUR_NAME}}. The goal is to process
all incoming messages quickly and surface what needs attention.

### Step 0: Verify Time and Context

Get the current time so you know what "today" and "recent" mean.
Check the calendar briefly to understand where the user is in their day.

### Step 1: Scan Channels

Scan each connected channel. Only scan channels with active MCP servers.
Report progress as you go.

**Channels to scan (in order):**

1. **Work Email (Gmail)** — Search for recent unread/unreplied emails
   - Query: Messages from the last 24 hours (or since last triage)
   - Focus on: Direct emails (not newsletters, automated, or CC-only)

2. **Personal Email** — If connected, same approach
   - Focus on: Anything from key contacts or family

3. **Slack** — Check DMs and mentions
   - Query: Recent DMs and @mentions
   - Skip: Channel chatter unless directly relevant

4. **WhatsApp** — If connected, check recent messages
   - Focus on: Direct messages requiring response

5. **iMessage** — If connected (macOS only)
   - Focus on: Unreplied messages from contacts

### Step 2: Classify Each Item

For each item found, assign a triage tier:

| Tier | Criteria | Action |
|------|----------|--------|
| **Tier 1** | From key contacts, time-sensitive, blocking someone, or explicit urgency | Respond NOW |
| **Tier 2** | Important but not urgent, requires thoughtful response, due today | Handle today |
| **Tier 3** | FYI, newsletters, automated notifications, low-stakes | Archive or brief ack |

**Tier assignment factors:**
- Who sent it? (Key contacts and leadership = higher tier)
- Is someone blocked waiting for a response?
- Is there a deadline mentioned?
- Has it been waiting a long time? (Older = higher urgency)
- Does it align with active goals?

### Step 3: Check for Already-Replied

Before drafting any response, verify the user hasn't already replied:
- Check sent mail for responses to the same thread
- Check if the contact file shows a more recent interaction
- If already handled, skip it entirely

### Step 4: Draft Responses

For each actionable item (Tier 1 and Tier 2), draft a response that:
- Matches the user's writing style (reference CLAUDE.md Part 4)
- Is send-ready (not a starting point for editing)
- Is appropriately concise for the context
- Includes specific scheduling proposals if timing is involved (verify calendar first)

For `quick` mode: Skip drafts, just list Tier 1 items.
For `digest` mode: Include drafts for Tier 1, summaries for Tier 2.

### Step 5: Present Results

Format output as:

```
Scanned: [channels] ([counts])

TIER 1 — Respond Now
1. [Sender] — [Subject/summary] ([channel], [wait time])
   Draft: "[proposed response]"

2. ...

TIER 2 — Handle Today
3. [Sender] — [Subject/summary] ([channel])
   Draft: "[proposed response]"

4. ...

TIER 3 — FYI
5-N. [Brief list, auto-archived if possible]

SUMMARY: [X] items need action, [Y] drafts ready to send.
```

### Step 6: Await Approval

**NEVER send any message without explicit approval.**

After presenting drafts, wait for the user to:
- Say "Send" or "Y" to approve a specific draft
- Say "Send all" to approve all drafts
- Edit a draft and then approve
- Skip items

### Guidelines

- Speed matters. A triage should take 2-3 minutes, not 10.
- Don't over-explain. The user knows their contacts — just surface what's important.
- If a channel's MCP server isn't connected, skip it silently.
- Track what was surfaced to avoid re-surfacing in the next triage run.
- If you find nothing urgent, say so clearly: "Inbox clear. No items need immediate attention."
- For long email threads, summarize the thread — don't just quote the last message.
