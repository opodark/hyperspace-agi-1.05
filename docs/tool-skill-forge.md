# Tool & Skill Forge

The Forge is the controlled authoring area exposed by the Control Plane dashboard.
Generated code is always stored as an inert draft under the persistent Control Plane
data directory; it is never imported or executed automatically.

Within the [unified development tooling architecture](development-tooling-architecture.md),
the Forge is the review and artifact layer shared by the offline Dev Sandbox and
future benchmark, browser, dependency-audit, and Security Lab workers. It does
not absorb their execution privileges.

## Workflow

1. Describe a tool or skill in the **Forge** dashboard tab, or export a unified
   diff from **Dev Sandbox**.
2. Generate with the configured coder model, or enter source manually.
3. Inspect static validation warnings and open the source in the browser IDE.
4. Move the artifact to `review`.
5. Approve it explicitly with `FORGE_ADMIN_TOKEN`, or disable it.

Approval records intent but does not install the artifact into Open WebUI. Export and
publication adapters for Open WebUI, MCP, and OpenAPI are deliberately separate future
steps so generated source cannot silently become executable server code.

Approved Markdown skills can now be selected explicitly for a chat request with
`hyperspace_skills: ["artifact-id"]`. The Control Plane verifies the approval's
source hash and adds the reference text to that request only. This does not
execute code, activate hooks, or grant tool permissions. Updating an artifact
resets approval. Older approvals without a source hash need renewed approval.

## Selected ECC workflows

In the Forge dashboard, enter the existing admin token and choose **Importa
skill ECC come draft**. This imports the bundled `security-review` and
`verification-loop` files from a pinned upstream commit, checking their SHA-256
hashes and preserving their MIT license and provenance. Repeating the import
leaves existing artifacts, including local edits, unchanged. Review and approve
the desired drafts, then use their displayed IDs in a request:

```json
{
  "model": "your-local-model",
  "messages": [{"role": "user", "content": "Review this task's code changes"}],
  "hyperspace_skills": ["ecc-security-review-9ac593b55cba"]
}
```

The extension is consumed by `/v1/chat/completions` before routing, so both
streaming and non-streaming paths receive the same context. At most two skills
and 24,000 UTF-8 bytes of injected context are allowed; oversized selections
are rejected rather than truncated. This is a byte budget, not a tokenizer or
model context-window guarantee. Skills are sent to the backend selected for
that request, like other messages. The Hyperspace adaptation asks the model to
use available sandbox presets and report unavailable checks as not run.

## Selected document workflow (anydoc)

In the Forge dashboard, enter the existing admin token and choose **Importa
skill anydoc come draft**. This imports the pinned `convert-documents-to-markdown`
Agent Skill from [firecrawl/anydoc](https://github.com/firecrawl/anydoc) as an
inert draft, checking the SHA-256 of the skill and its MIT license and preserving
provenance. The skill teaches a model to turn Word, PowerPoint, Excel,
OpenDocument, RTF, EPUB, CSV and PDF into GitHub-Flavored Markdown with the
`anydoc` CLI. The Control Plane also ships an executable tool,
`converti_documento_markdown`, which converts such a document from the shared
folder locally (see [webui-tools.md](webui-tools.md)); the imported skill is
reference text only and does not run code or install anything by itself.

## Selected Agency Agents profiles

The dashboard button **Importa profili Agency Agents come draft** (or
`POST /forge/import/agency-agents` with `X-Hyperspace-Forge-Token`) imports three
short HyperSpace adaptations: `multi-agent-architect`, `code-reviewer`, and
`technical-writer`. They come from the MIT-licensed
[Agency Agents](https://github.com/msitarzewski/agency-agents) repository at
commit `f99f6aa910a442b0197b768ce0ea7751e35e2060`. The bundle contains the
three original Markdown files, their SHA-256 hashes, the local adaptations and
the license; the loader checks all of them before creating any draft. Reimport
leaves existing drafts and local edits intact.

The upstream multi-agent profile is too long for HyperSpace's 24,000-byte
selected-skill context limit, so the Forge injects the short local adaptation,
not the original file. The original is retained for provenance and review.
These profiles are reference text: they do not create workers, grant tools,
run checks, approve code, or publish documents. After explicit review and
approval, select at most two IDs using `hyperspace_skills` in a chat request.
For the PDF mission, the technical-writer profile suggests an evidence-backed
outline and an artifact check; it does not imply that Mission Control has
successfully produced or verified a PDF.

## Browser IDE

The optional IDE is code-server and is bound to localhost only. Start it with:

```powershell
docker compose -f docker-compose.windows.yml --profile ide up -d hyperspace-ide
```

Use **Apri IDE** in the Forge dashboard, or open `http://127.0.0.1:<CODE_SERVER_PORT>`,
and use `CODE_SERVER_PASSWORD` from the local `.env`. Artifact sources are available
inside the IDE under `/home/coder/forge` as `.py`, `.md`, or `.diff` files. The repository and
the Forge directory are mounted read/write, but the Docker socket is not mounted. Do not
expose this port publicly; use a trusted authenticated tunnel if remote access is needed.

The artifact JSON managed by the dashboard is the authoritative record. Source sidecars
are provided for inspection in the IDE; edits made only to a sidecar are not imported
back into the registry and can be replaced by a later dashboard save.

## API

- `GET /forge/artifacts` — list artifacts.
- `GET /forge/config` — return the local IDE URL and artifact directory.
- `POST /forge/artifacts` — create an inert manual draft.
- `POST /forge/import/ecc` — import the bundled workflows as inert drafts;
  requires `X-Hyperspace-Forge-Token`. No network fetch or installer runs.
- `POST /forge/import/anydoc` — import the pinned anydoc skill as an inert draft;
  requires `X-Hyperspace-Forge-Token`. No network fetch or installer runs.
- `POST /forge/import/agency-agents` — import three pinned, locally adapted
  Agency Agents profiles as inert drafts; requires `X-Hyperspace-Forge-Token`.
  No network fetch or installer runs.
- `POST /forge/import/firecrawl-skills` — import the pinned Firecrawl skill
  catalogue entries (`firecrawl-search`, `firecrawl-scrape`,
  `firecrawl-research-index`, `firecrawl-developer-index`) as inert drafts;
  requires `X-Hyperspace-Forge-Token`. No network fetch or installer runs.
- `PUT /forge/artifacts/<id>` — update a draft and increment its version.
- `POST /forge/generate` — generate and persist a draft through local Ollama.
- `POST /forge/artifacts/<id>/status` — change lifecycle state; approval requires
  the `X-Hyperspace-Forge-Token` header.

The accepted artifact types are `tool`, `skill`, and `patch`. Patch validation
requires unified text diff headers and at least one hunk, and rejects binary
change placeholders. `/forge/generate` remains limited to tools and skills;
patches come from a reviewed sandbox diff or manual input.

## Wayfinder decision planning

**Importa Wayfinder e skill di supporto come draft** imports five pinned MIT
workflows via `POST /forge/import/wayfinder`, protected by the Forge token.
The [Wayfinder integration](wayfinder.md) supplies a persistent local tracker,
an agent tool and an explicit handoff to Mission Control. Selecting a Wayfinder
skill injects the local adapter alongside the unchanged approved upstream source.
Planning maps are available under **Autogenerazione → Wayfinder**.

## Selected research/scraping method (firecrawl/skills)

**Importa skill Firecrawl come draft** imports four pinned reference-only
workflows via `POST /forge/import/firecrawl-skills`, protected by the Forge
token: `firecrawl-search`, `firecrawl-scrape`, `firecrawl-research-index` and
`firecrawl-developer-index`, from
[firecrawl/skills](https://github.com/firecrawl/skills) under the ISC license.
The Markdown is bundled verbatim with its SHA-256 and provenance, and imported
as inert drafts. Hyperspace runs no Firecrawl runtime, uses no `FIRECRAWL_API_KEY`
and makes no network call for these skills: they only teach the method. Local
execution stays in the shipped tools — `classifica_pdf` and
`converti_documento_markdown` (see [webui-tools.md](webui-tools.md)) — or in a
service configured separately by the operator.

### Selezione automatica nel tool loop

L'hook `before_context` seleziona fino a due skill già approvate quando i trigger
locali corrispondono al compito e i tool necessari sono offerti al ruolo. La
selezione esplicita prevale; il registro `type=skill` espone le motivazioni.
Regole, provenienza e limiti in [skill-hooks.md](skill-hooks.md).

Per leggere un URL specifico non usare `web_search` come se fosse un browser:
il Control Plane espone `web_fetch`, un lettore HTTP(S) in sola lettura. Rifiuta
host locali e indirizzi non pubblici, non segue redirect e limita la risposta a
80 KB prima dell'estrazione del testo HTML. I ruoli di ricerca di Mission Control
lo ricevono automaticamente; la skill Firecrawl scrape è solo una guida
facoltativa selezionata dal hook se è stata approvata, non installa un runtime.

Una skill selezionata è guida e non forza la scelta di un tool. Per URL espliciti
il tool loop applica una regola deterministica: usa `web_fetch` e toglie
`web_search` dai tool disponibili per quel turno. Se la pagina non si può
leggere, deve dichiarare il blocco senza inventare contenuti o passaggi.

### Moltbook — stato account HyperSpace

La skill approvata `hyperspace-moltbook-account-20261010` si aggancia alle
richieste Moltbook in chat. Per richieste su stato, claim o credenziali, il tool
loop chiama anche `moltbook_status` prima dell'inferenza: la risposta viene
quindi basata sullo stato API appena letto e non sulla memoria del modello. Il
tool legge `MOLTBOOK_CREDENTIALS_FILE` (mount read-only in Compose), invia la
chiave soltanto a `https://www.moltbook.com/api/v1/agents/status`, rifiuta i
redirect e non registra mai la chiave nei log. Se `pending_claim`, espone claim
URL e codice all'utente; non attiva heartbeat né pubblica contenuti. Per il
runtime Mac il Compose monta `~/.config/moltbook/credentials.json`; dopo aver
aggiunto il mount o aggiornato il CP, ricreare il solo servizio
`control-plane`.
