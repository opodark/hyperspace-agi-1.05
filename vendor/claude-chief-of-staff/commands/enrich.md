# /enrich — Contact Enrichment

## Description
Build and maintain your personal CRM. Scan communications for contact mentions,
update interaction history, and surface relationships that need attention.

## Arguments
- `all` — Scan channels and update all contact files with new interactions
- `stale` — Show contacts that haven't been engaged recently (based on tier cadence)
- `<contact-name>` — Enrich a specific contact's file with latest information

## Contact Files
Location: `~/.claude/contacts/`
Index: `~/.claude/contact-index.yaml` (optional, for quick lookups)

## Instructions

### /enrich all

Scan connected channels for recent interactions and update contact files.

1. **Scan channels** for the last 24 hours (or since last enrichment):
   - Email: Recent sent/received with known contacts
   - Slack: DMs and mentions involving known contacts
   - WhatsApp/iMessage: Recent messages with known contacts
   - Calendar: Meetings that occurred with known contacts

2. **For each interaction found:**
   - Look up the contact file in `~/.claude/contacts/`
   - If the file exists: Update "Last Interaction" and add to "Interaction History"
   - If no file exists and the person seems important: Suggest creating one
   - Add any new context learned (mentioned a project, changed roles, etc.)

3. **Present a summary:**
   ```
   ENRICHMENT COMPLETE

   Updated:
   - Jane Smith — email exchange about platform migration (today)
   - Alex Chen — Slack DM re: hiring pipeline (today)

   New contacts detected (no file yet):
   - Pat Rivera (pat@example.com) — 3 emails this week, discussed partnership
     → Want me to create a contact file?

   No updates needed:
   - [List of contacts with no new interactions]
   ```

### /enrich stale

Check which contacts are overdue for engagement based on their tier.

1. **Read all contact files** in `~/.claude/contacts/`
2. **Compare last interaction date** against tier cadence:
   - Tier 1: Flag if no contact in 14+ days
   - Tier 2: Flag if no contact in 30+ days
   - Tier 3: Flag if no contact in 60+ days

3. **Present stale contacts:**
   ```
   RELATIONSHIP HEALTH CHECK

   NEEDS ATTENTION (overdue)
   - Jane Smith (Tier 2) — Last contact: 45 days ago (email)
     Suggestion: "Quick note to ask about the platform migration progress"

   - Alex Chen (Tier 1) — Last contact: 18 days ago (coffee)
     Suggestion: "Share that article on engineering leadership you bookmarked"

   APPROACHING
   - Pat Rivera (Tier 2) — Last contact: 25 days ago
     Suggestion: "Follow up on partnership discussion"

   HEALTHY
   - [X] contacts are within their cadence

   Want me to draft any of these touchpoint messages?
   ```

### /enrich <contact-name>

Deep enrichment of a specific contact.

1. **Find the contact file** in `~/.claude/contacts/`
2. **Scan all channels** for recent mentions/interactions with this person
3. **Update the file** with:
   - Latest interaction details
   - Any new context from conversations
   - Updated talking points for next interaction
4. **Check for meeting prep needs:**
   - Is there a meeting with this person coming up?
   - If so, prepare a brief prep note

5. **Present what was updated:**
   ```
   ENRICHED: Jane Smith

   Updated:
   - Last interaction: Jan 15 (was Dec 3)
   - Added interaction: Coffee meeting, discussed platform migration
   - New note: She's considering AI tooling for her team (added 2026-01-15)
   - Updated talking points: Ask about migration progress

   Upcoming:
   - Meeting with Jane on Feb 3 at 2pm (1:1 sync)
     → Want me to prep for this meeting?
   ```

### Creating New Contact Files

When a new contact is suggested, create using this template:

```markdown
# Contact: [Full Name]

## Quick Reference

| Field | Value |
|-------|-------|
| **Name** | [Full Name] |
| **Role** | [Role at Company] |
| **Tier** | [1/2/3] |
| **Email** | [email] |
| **Phone** | [if known] |
| **Location** | [if known] |
| **Met through** | [how you connected] |

## Relationship Context

[Brief context on the relationship]

## Communication Style

[Observations on how they prefer to communicate]

## Personal Notes

[Any personal details learned from conversations]

## Interaction History

| Date | Type | Summary |
|------|------|---------|
| [date] | [type] | [what happened] |

## Talking Points for Next Interaction

- [topics to bring up]

## Last Interaction

- **Date:** [date]
- **Channel:** [channel]
- **Follow-up needed:** [if any]
```

### Guidelines

- Always include dates when adding notes (e.g., "Enjoys hiking (added 2026-01-18)")
- Don't over-enrich. Only add genuinely useful context, not filler.
- When scanning channels, respect privacy — don't surface private/sensitive content in contact notes.
- Tier assignments should reflect actual relationship importance, not aspirational importance.
- Stale contact alerts are suggestions, not demands. Some relationships naturally ebb and flow.
- Focus enrichment on contacts that are actually useful for the user's goals.
