# /my-tasks — Task Management

## Description
Track, prioritize, and execute tasks with goal alignment and due date awareness.
Claude doesn't just remind you — it helps get work done.

## Arguments
- `list` — Show all active tasks, grouped by urgency
- `add "title" --due YYYY-MM-DD --goal "goal-name"` — Add a new task
- `complete <task-id>` — Mark a task as complete
- `execute` — Work on the highest-priority pending task
- `overdue` — Show only overdue and at-risk tasks

## Task File
Location: `~/.claude/my-tasks.yaml`

## Instructions

### /my-tasks list

Read `~/.claude/my-tasks.yaml` and present tasks grouped by urgency:

```
TASKS

OVERDUE (action required)
- [task-id] [title] — due [date] ([X days late]) — goal: [goal]

DUE TODAY
- [task-id] [title] — goal: [goal]

APPROACHING (next 7 days)
- [task-id] [title] — due [date] ([X days]) — goal: [goal]

LATER
- [task-id] [title] — due [date] — goal: [goal]

Summary: [X] active tasks, [Y] overdue, [Z] due this week
```

If there are overdue tasks, flag them prominently and ask:
"Want me to help execute [task], reschedule it, or break it down?"

### /my-tasks add

When adding a task:

1. Generate a unique task ID (format: `task-XXX`)
2. Ask for any missing required info:
   - Title (required)
   - Due date (required — always set one, even if approximate)
   - Goal alignment (recommended — which goal does this advance?)
   - Priority (default: 3/normal)
   - Description (optional — helpful for complex tasks)
3. Write the task to `~/.claude/my-tasks.yaml`
4. Confirm: "Added: [title] — due [date] — aligned to [goal]"

**Goal alignment validation:**
Check `~/.claude/goals.yaml` for active goals. If the task doesn't align
with any active goal, flag it: "This task doesn't align with your current goals.
Still want to add it?" This isn't a blocker — just a prompt for intentionality.

### /my-tasks complete

1. Find the task by ID in `~/.claude/my-tasks.yaml`
2. Update status to "complete"
3. Add completion date
4. Confirm: "Completed: [title]"
5. If completed before due date, celebrate briefly: "Nice — finished 3 days early."

### /my-tasks execute

This is where Claude actively helps get work done.

1. Read the task list and identify the highest-priority actionable task
2. Check the user's calendar to confirm they have time now
3. Present the task and a plan:
   ```
   Ready to work on: [task title]
   Due: [date] | Goal: [goal] | Priority: [priority]

   Here's my plan:
   1. [Step 1]
   2. [Step 2]
   3. [Step 3]

   Shall I proceed?
   ```
4. Execute the work (draft emails, do research, create documents, etc.)
5. Present progress and ask for feedback
6. Iterate until the user is satisfied

**Important:** Claude helps execute — the user marks tasks complete.
Present work as "Here's where we are" not "Here's the finished product."

### /my-tasks overdue

Quick check for overdue and at-risk tasks. Used by automated scheduling.

Show:
1. **OVERDUE** — Past due date, not complete
2. **AT RISK** — Due within 48 hours, not started or blocked
3. **APPROACHING** — Due within 7 days

For each, suggest an action: execute, reschedule, delegate, or break down.

### Session-Start Behavior

At the start of any substantive conversation (not just /my-tasks), Claude
should silently check the task list and surface anything critical:

- **OVERDUE tasks:** Always mention these immediately
- **Due today:** Mention if there's time to work on them
- **At risk:** Mention if today's calendar has capacity

This check should be brief (1-2 lines) and not interrupt the user's request.

### Guidelines

- Every task should have a due date. If the user doesn't provide one, suggest one.
- Goal alignment isn't required but is strongly encouraged.
- When executing tasks, be specific about what you're doing and why.
- Don't expand scope. If the task says "draft email," draft the email. Don't also restructure their email templates.
- Celebrate early completions — positive reinforcement matters.
- If a task has been sitting with no progress for 5+ days, proactively ask about it.
