---
name: hyperspace-wayfinder
description: Adapt Wayfinder decision planning to HyperSpace's persistent local tracker and hand off resolved decisions to Mission Control for sandbox coding.
---

# HyperSpace adapter

Use this adapter alongside the selected upstream Wayfinder workflow. The tracker
is HyperSpace, not GitHub: `wayfinder_map` stores maps and tickets across sessions.
Do not run the upstream setup installer or create external issues for this workflow.

Start by agreeing the destination with the user. Create only questions you can
state precisely; keep unclear areas in `fog` and exclusions in `out_of_scope`.
Use ticket titles in conversation; IDs are for tool calls. Small, already clear
coding requests can use Mission Control directly without a decision map.

## Local tracker operations

Call `wayfinder_map` with `action=list`, then `get` and `map_id` to resume. Load
one map, not the whole project history. `frontier` contains unclaimed tickets
whose dependencies are closed. Claim one before working on it.

For `create` or `update`, `data` contains `destination`, `notes`, `fog` (strings),
`out_of_scope` (strings), and `tickets`. Each ticket has `key` (kebab-case),
`title`, `question`, `kind` (`research`, `prototype`, `grilling`, `task`),
`mode` (`afk` or `hitl`), and `dependencies` (other ticket keys).
Updates also require the current `revision`; preserve existing tickets. Create
all keys before wiring dependencies. Cycles and unknown prerequisites are rejected.

For `claim`/`release`, pass `map_id`, `ticket_key`, and
`data={revision, owner}`. For `resolve`/`exclude`, include `answer` with findings
and source/artifact references. Reload after a revision conflict; reconcile the
current state instead of blindly retrying an old update. Release abandoned claims.

Prototype and grilling tickets require human input. The agent tool cannot
resolve or exclude HITL tickets, even when given a human_confirmed flag. Ask the
user for their decision and direct them to Autogenerazione → Wayfinder to record
it. Do not relabel a human question as autonomous or answer it yourself.
Autonomous research/task tickets can be resolved by the tool with evidence.

## Supporting workflows

The Forge offers separate pinned drafts for research, prototype, grilling and
domain-modeling. Select relevant approved workflows with `hyperspace_skills`
(maximum two per request, total 24,000 bytes including this adapter). The
`references` action returns the prototype and domain-modeling Markdown formats.
Select skills across separate requests rather than loading all five at once.

If this runtime lacks a Skill tool or background-agent tool, say so. Perform
available research directly with primary sources; do not claim parallel agents
ran. Build prototypes only with available sandbox tools. Repository permissions
still govern edits and commits; upstream branch/commit advice is not permission.

## Handoff

Record each answer on its ticket. Add newly discovered questions or clear `fog`
only after the uncertainty is resolved. Resolved tickets are immutable; changed
decisions need new tickets. The map is ready when every ticket is closed and
`fog` is empty. This means the plan is clear, not that the software is built.

The operator uses **Consegna a Mission Control** to start implementation. The
agent tool cannot invoke handoff. The existing mission loop may start immediately;
it receives a durable decision snapshot and produces sandbox artifacts for review.
Keep maps small enough for the mission's 4,000-character objective limit; split
larger efforts into separate maps. Missing execution tools are limitations to
report, not tasks to mark complete.
