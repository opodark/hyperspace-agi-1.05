# Wayfinder in HyperSpace

Wayfinder turns a large, uncertain objective into persistent decision tickets.
Once decisions are settled, an operator hands the map to Mission Control, whose
existing planner, coder and verifier produce artifacts for review.

## Dashboard

Open `/dashboard#forge` and **Importa Wayfinder e skill di supporto come draft**
with the existing Forge token. The five drafts are Wayfinder, research, prototype,
grilling and domain-modeling. Review and approve the ones you want to select in
chat; import alone does not approve them. Original Markdown and MIT license are
pinned in `vendor/wayfinder/manifest.json`. The four supporting reference files
are bundled and hash-checked too.

Under `/dashboard#autogen`, **Wayfinder — decisioni prima del codice** uses the
same review token as Mission Control. Create a map, add questions, wire prerequisites,
and take a question in charge before recording its answer. The list shows available,
claimed and resolved tickets. Human decisions require explicit confirmation in the
operator UI; the agent tool cannot sign them off. Exclude a question with a reason
when it falls outside the destination. Release abandoned claims to let others work.

Only a map with no open tickets and no remaining fog can be handed off. The button
explicitly warns that the existing mission loop can start immediately. Repeated
handoff returns the same mission, including after a restart. The handed-off map
is immutable; the mission stores its full snapshot in `policy.wayfinder` and the
compact destination/decisions/scope in its objective. No artifact is applied by
this integration. Review still happens in Mission Control.

## Agent use

The native Control Plane tool `wayfinder_map` supports list/get/create/update,
claim/release/resolve/exclude, and references. It can resolve autonomous research
and prerequisite tasks; it cannot resolve HITL tickets or launch a mission.
It is available in the chat's native tool catalog, not added to every mission
role: execution workers receive already settled decisions through the mission.
A saved map does not itself schedule research or invoke an LLM; the selected
chat agent drives that planning work with the tools actually available.

Select approved Forge artifact IDs through `hyperspace_skills`, as for ECC/anydoc.
The Control Plane adds the [HyperSpace adapter](../integrations/wayfinder/SKILL.md)
when a Wayfinder-imported skill is selected. Upstream text stays unchanged. At
most two skills fit a request, subject to the existing total 24,000-byte limit;
load supporting workflows on demand. No automatic nested Skill/subagent runtime
is assumed. The adapter documents the actual tool schema and human handoff.

## Persistence and API

Maps live in `MISSION_DATA_DIR/wayfinder.sqlite3`. SQLite transactions protect
cross-process claims; revisions reject stale updates with HTTP 409. Runtime data
belongs in the existing persistent data mount, not Git. Tickets cannot be deleted
or silently pre-resolved by an update. Closed decisions cannot be rewritten.

Every `/wayfinder/*` route requires the same bearer token as `/missions`:

- `GET/POST /wayfinder/maps`: list or create maps.
- `GET/PUT /wayfinder/maps/<id>`: load or update with current `revision`.
- `POST /wayfinder/maps/<id>/tickets/<key>/<action>`: claim, release, resolve or
  exclude. Body: `revision`, `owner`; resolution also needs `answer`, and HITL
  resolution requires `human_confirmed: true` through this operator channel.
- `POST /wayfinder/maps/<id>/handoff`: `revision`, `confirm_execution: true`,
  optional mission `budget`. Returns the linked `mission_id`; no forced launch
  occurs, but the existing enabled mission loop picks it up.
- `GET /wayfinder/references`: verified auxiliary Markdown.

`POST /forge/import/wayfinder` instead uses `X-Hyperspace-Forge-Token`, preserving
Forge's approval boundary. Import is idempotent and never replaces local edits.

The operator channel trusts its bearer-token holder to record actual human input;
`owner` identifies a cooperative agent/session, not a separate authenticated user.
A crashed claim remains visible until explicitly released by the operator.
Handoff rejects objectives over 4,000 characters instead of silently truncating
decisions. Split large projects into smaller decision maps. Already linked maps
can retry handoff after a storage failure to recover the same reserved mission ID.

## Verification

`tests/test_wayfinder.py` exercises dependency blocking, human/agent boundaries,
concurrent claims, stale updates, restart persistence, failed-handoff recovery,
mission snapshot/idempotence, auth, import preservation and bundle tampering.
