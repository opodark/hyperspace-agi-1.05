# Valutazione di quattro repository esterni per lo sviluppo autonomo

Data: 2026-10-09. Scopo: decidere se integrare, modificare o solo prendere spunto da quattro
repository proposti, in vista di uno sviluppo autonomo o semi-autonomo. Stato: **valutazione
documentale** — nessuno dei quattro è stato installato o eseguito, nessuna modifica al runtime,
nessun commit. La direzione di prodotto resta quella di [VISION.md](../VISION.md) e
[openwork-hyperspace.md](openwork-hyperspace.md).

Macchina misurata oggi: MacBook Air M5, 16 GB di memoria unificata, ~23 GB liberi su
`/System/Volumes/Data`, Docker 29.8.1 (Docker Desktop), 9 modelli in Ollama. OpenWork.app
**0.18.57** installata con sidecar `opencode` **1.18.30**.

## Metodo e limiti

- Fonti primarie consultate il 2026-10-09: API GitHub (licenza, stelle, date di creazione/push,
  issue aperte), README e LICENSE dei quattro repository, model card Hugging Face per i pesi di
  laya, `openworklabs.com/docs`. Il dettaglio è in [Fonti](#fonti).
- **Non** provato: nessuno dei quattro eseguito, nessun benchmark, nessuna misura di memoria o
  latenza delle loro dipendenze. I numeri di prestazione di laya sono quelli **dichiarati dalla sua
  model card**, non nostre misure.
- Il pilot OpenWork esistente (`data/openwork-apple-pilot/`, nota in AGENT-LOG del 2026-10-09) è
  citato come contesto, non come prova di questi repository.

## Tabella comparativa (2026-10-09)

| | layra (liweiphys) | laya (NandhaKishorM) | OpenWork (different-ai) | OpenDots (CopilotKit) |
|---|---|---|---|---|
| Cos'è | visual RAG + orchestrazione workflow | motore di decisione "System 1" non autoregressivo | workspace/coworker desktop su opencode | template di "AI coworker" always-on |
| Licenza | Apache-2.0 | Apache-2.0 (pesi `apache-2.0` + commercial-use) | core MIT + `ee/` EE (GitHub: `NOASSERTION`) | MIT |
| Creato | 2025-04-06 | 2026-09-18 | 2026-01-14 | 2026-09-29 |
| Ultimo push | **2025-10-14** | 2026-10-08 | **2026-10-09** | 2026-09-29 (53 commit) |
| Stelle / issue | 897 / 7 | 31.876 / 96 | 23.975 / 634 | 4,6k / 25 |
| Stack | FastAPI + TS, Docker, Kafka/Postgres/MinIO | Python/PyTorch, extra serve/mcp/langchain/onnx/fast | Electron + TS monorepo, server, sidecar opencode | TS/React, Docker per-Dot, AG-UI |
| Requisiti reali | GPU NVIDIA, ~15 GB pesi | 0,4B params, CPU ok (~1,7 s/4k token su Apple GPU) | macOS ok (929 MB già installati) | servizi connessi (Slack, Parallel) |
| Verdetto | **No** | **Spike condizionato** | **Sì — direzione già dichiarata** | **No come base, sì come pattern** |

## Reperti interni che cambiano il giudizio

Tre cose già nel repository rendono meno utile "adottare" questi repo e più utile "collegare" ciò
che c'è:

1. **Passthrough dei tool del client già implementato e testato.** `control-plane/cp/chat.py:571-575`
   unisce i tool inviati dal client a quelli nativi; `:656-749` riconosce i tool del client e li
   **restituisce senza eseguirli** (`_risposta_solo_tool_del_client`, definita a `:321`); il ramo
   streaming li riporta via `_chunk_finale`. Coperto da `tests/test_tool_passthrough.py` (passthrough,
   risposta mista, chunk streaming, dedup delle chiamate identiche fallite, allowlist). Questo è il
   contratto di inferenza che un coding agent esterno (opencode) richiede.
2. **Superficie MCP pronta e autenticata.** `control-plane/cp/tool.py:651` espone `/mcp` (JSON-RPC:
   `initialize`, `tools/list`, `tools/call`); `shared/mcp_auth.py` applica `MCP_CLIENTS` +
   `MCP_CLIENT_TOOLS` (allowlist per cliente, `tools/list` filtrato); esiste
   `scripts/verify_mcp_auth_e2e.py`. I tool nativi pubblicabili includono `web_search`, `omega_query`,
   `omega_store`, `get_mesh_status`, `code_sandbox` e i tool d'identità (che `shared/persona.py`
   non offre su superfici che non li vogliono).
3. **OpenWork già installato ma puntato su Ollama.** `~/.config/openwork/runtime-opencode-config.json`
   ha `provider.ollama.baseURL = http://localhost:11434/v1` e **`mcp: {}`**: il pilot attuale aggira
   il control plane. Riportarlo sul CP (`http://127.0.0.1:8085/v1`, senza auth, loopback-only) e
   dargli `code_sandbox`/`omega_query`/`web_search` via MCP è configurazione, non codice nuovo.

## Verdetto per repository

### layra — non integrarlo, non modificarlo

- Fermo da un anno (`pushed_at` 2025-10-14), 7 issue aperte, dichiara K8s come "futuro".
- Gira solo via `docker compose` (Kafka + Postgres + MinIO + model-server) con GPU NVIDIA e ~15 GB
  di pesi (ColQwen2.5/ColPali). Su M5/16 GB/23 GB liberi non è un'opzione.
- Duplica capacità già presenti: `converti_documento_markdown` (AnyDoc), `unlimited-ocr`, memoria
  Hermes, DAG di Mission Control con policy/verifica (che layra non ha).
- **Cosa lo riaprirebbe:** un nodo Linux+NVIDIA (ROADMAP "Linux Primary Brain") e un requisito di
  prodotto su documenti scansionati/moduli dove il testo non basta. In quel caso, come *servizio* su
  quel nodo, mai sul Mac. Un fork di un progetto fermo è debito puro.

### laya — spike misurato, dietro flag, mai autoritativo

È l'unico che porta una capacità nuova: decisioni tipizzate (choice/score/sì-no) in un singolo
forward pass, con probabilità e latenza dichiarate, e superfici di integrazione pulite
(`laya[mcp]`, `laya[langchain]`, `laya[onnx]`, `laya[serve]`). Pesi Apache-2.0 + commercial-use:
nessun problema legale.

La **sua stessa model card** è la ragione per non fidarsene fuori scatola:

- i checkpoint base sono **vicini al caso** su typed-decisions zero-shot (0,362 vs majority 0,461):
  «Laya is a fast base to specialise, not a zero-shot decision engine»;
- è **sovra-confidente**: il refit di temperatura porta la ECE da 0,466 a 0,081 — da fare sui propri dati;
- `action.act_probability` non porta segnale (AUROC 0,30): usare la confidenza;
- `noul` può seguire le proprie etichette invece del testo (#156); `score` è la primitiva più debole (SST-5 0,372);
- repository di 3 settimane, 96 issue aperte → da fissare a commit.

Slot candidati con baseline esplicita:

| Slot | Baseline già nel repo | Deve battere |
|---|---|---|
| Scelta famiglia di skill | `shared/skill_hooks.py` (trigger a parole intere) | le regole deterministiche su dataset congelato (la "selezione semantica" è già lavoro aperto) |
| Classificazione intento/ruolo per il routing | `cp/model_caps.py` (pattern sul nome modello) | idem, senza toccare il percorso caldo |
| Pre-check messaggi dei canali (rifiuto/off-topic) | oggi assente | serve dataset etichettato a mano; solo annotazione |

Vincoli: mai veto, mai autorità — solo annotazione/routing con decisione loggata (motivo +
confidenza), flag spento di default, nessuna dipendenza nel control plane (raggiunto via MCP o HTTP
locale), script nostro `scripts/laya_probe.py`, zero modifiche all'upstream. **Gate di promozione:**
se sul dataset congelato non batte il baseline deterministico, il filo si chiude e resta un
esperimento documentato. Costo: ~1-2 GB di disco, RAM da misurare con Ollama caricato.

### openwork — sì, ed è già la direzione dichiarata

`VISION.md` ("Workspace centrale — direzione OpenWork") e `openwork-hyperspace.md` lo dicono già.
La domanda non è *se*, ma *come chiudere il confine*. Con i reperti sopra, la parte "modalità di
inferenza per runtime esterno" è in gran parte costruita. Restano:

1. Riportare OpenWork sul CP: `provider` → `http://127.0.0.1:8085/v1` (nessuna auth su `/v1`,
   loopback-only: coerente col threat model single-tenant, da annotare come debito).
2. MCP: oggi `mcp: {}` → cliente `openwork` in `MCP_CLIENTS` (token ≥32 char) +
   `MCP_CLIENT_TOOLS=openwork=code_sandbox,omega_query,web_search`; da verificare lo schema MCP remoto
   con header nella versione fissata di opencode (1.18.30).
3. Il confine di scrittura: opencode scrive file direttamente → **worktree/clone isolato** come
   workspace, mai il checkout operativo (che oggi è pieno di lavoro non committato).
4. `permission: {}` nel runtime config: da popolare deliberatamente, non lasciare ai default di
   un'app che si auto-aggiorna (release giornaliere, ultima `v0.18.57`, `releaseType: release`).
5. Licenza: su GitHub è `NOASSERTION`; il `LICENSE` su `dev` distingue core MIT da `ee/` sotto
   OpenWork EE. Adottare solo il core locale; **fissare il commit** e registrarne le attribuzioni
   prima di distribuire. Nessuna funzione Den/`ee/`.

Criteri di accettazione misurabili (i primi tre verificabili oggi, il quarto no):

- una richiesta di opencode: log `CP decision: model=… tools=N` + `tool del client: …`, e nessun
  tool di opencode eseguito dal CP;
- `tools/list` via MCP mostra solo l'allowlist; una chiamata fuori allowlist è rifiutata e loggata;
- un turno streaming porta comunque la tool_call del client (`_chunk_finale`);
- "fai X e verifica" → diff in workspace sandbox + `check/verify` → bozza Forge `applied:false`,
  nessuna applicazione;
- riavvio del CP a metà missione senza doppia esecuzione (questo è il pezzo che manca e decide
  l'autonomia; P1 in AGENTS.md).

### OpenDots — no come base, sì come quattro pattern

Già deciso in `ag-ui.md` §2 (inversione di stack, immaturità, il valore è la specifica non
l'applicazione), e oggi ancor più vero (10 giorni di vita, 53 commit, 25 issue). Pattern da
raccogliere, ognuno su un componente che esiste:

| Pattern OpenDots | Destinazione HyperSpace | Delta reale |
|---|---|---|
| schedule = istruzioni ricorrenti, non motore di obiettivi (lo dichiarano loro) | `MISSION_LOOP_ENABLED` + finestra del nightly | semantica di ricorrenza, pausa/cancel, receipt per run |
| coworker = identità + spazio + "computer" + canali | `code-sandbox` per workspace + `SBX_*` | "coworker" come configurazione (`multiAgent.subagents`, già prenotato in `ag-ui.md` §4) |
| skill con review+publicazione, versione fissata per conversazione | Forge (hash del sorgente) + `attach_skills` | la conversazione resta sulla versione di skill con cui è iniziata |
| handoff testo↔voce↔canali con identità e receipt | `channel.md`, Discord, Instagram DM, web-node-voice | "receipt + approvazione dentro il canale" |

## Cosa manca davvero all'autonomia

Nessuno dei quattro è un motore di autonomia. L'autonomia è il **rapporto fra ciò che il sistema
sa verificare e ciò che sa fare**. I mancanti, per come li elenca lo stesso repository, sono:

1. **Gate di completamento indipendente dal modello**, per tipo di artefatto (PDF = file+firma+pagine+
   testo; codice = diff+test; sito = asset presenti). (AGENTS.md P0; il 2026-10-08 la catena è
   riuscita ma il verdetto di missione era sbagliato per un prompt difettoso.)
2. **Contratto di run + idempotenza**: nessuna azione esterna duplicata dopo riavvio/HITL. (AGENTS.md P1)
3. **Dataset di regressione e metriche**: completamento con artefatto verificato, costo, latenza,
   retry, interventi umani. (AGENTS.md P1 — ed è il presupposto per giudicare laya.)
4. **Il tetto hardware**: 12k di contesto, ~30 min, un solo modello grande per volta
   (`mission-bonsai2-trial-2026-10-08.md`). Con questo non esiste autonomia *lunga*: esiste autonomia
   a missioni corte, oppure si collega il nodo Asus/Win11 (`distributed-inference.md`).

## Ordine di lavoro proposto (agganciato all'ordine 1.05 già concordato)

- **P0 — OpenWork sul CP in worktree isolato** (nessuna dipendenza nuova): workspace dedicato come il
  pilot Apple, `provider` → CP, cliente MCP con allowlist, verifica dei criteri di cui sopra,
  documentare in `openwork-hyperspace.md`. Accettazione: primo turno reale di opencode contro il CP
  registrato nei log.
- **P0bis — i due gate dell'autonomia** (AGENTS.md): gate di completamento per tipo di artefatto +
  test di crash/restart/HITL con idempotenza.
- **P1 — missione PDF ×3 dalla conversazione OpenWork** (criterio già in `openwork-hyperspace.md`)
  e dataset di eval dalle run reali. Accettazione: tre run con PDF apribile e fonti consultabili, e
  una run che fallisce dicendo quale passo e perché.
- **P2 — spike laya** (solo se dopo P0/P1 lo si vuole ancora): `scripts/laya_probe.py` loopback +
  `data/eval/decision-cases.jsonl` congelato + `docs/laya-decision-spike.md`; servizio esterno al CP;
  guardia di skip nei test come per i moduli del reel; gate = battere il baseline deterministico.
- **P3 — pattern OpenDots** su schedule/receipt/coworker/skill-version, quando servono.
- **Parcheggiato — layra**: rivalutazione solo su nodo Linux+NVIDIA con requisito visual-RAG.

Non fare: nessun fork; nessun secondo orchestratore; nessuna seconda autenticazione; nessun
classificatore con potere di veto; nessun tool nuovo nel catalogo prima dei gate P0bis.

## Decisioni aperte (dell'operatore)

1. **Confine di scrittura di OpenWork**: worktree isolato (raccomandato, coerente con VISION) o
   checkout operativo.
2. **Disco/RAM**: 23 GB liberi e 16 GB di RAM sono il tetto. Pulizie proposte: `~/Downloads/ghidra-dist`
   (~570 MB), `/tmp/ghidra-decomp-build`, `docker system prune`, workspace sandbox orfani.
3. **Modello dell'autonomia**: missioni corte con il tetto attuale, o collegare il nodo Asus
   (`distributed-inference.md`).
4. **Priorità a laya**: filo di ricerca con gate onesto, ma non è ciò che sblocca l'autonomia.

## Non-obiettivi / cosa questo documento NON dichiara

- Nessuna adozione, nessun fork, nessun codice importato da questi repository.
- Licenze citate solo dalle fonti elencate; OpenWork va **rifissato al commit scelto** (i riferimenti
  `dev` sono mobili). Importando codice in futuro: aggiornare `THIRD-PARTY-NOTICES.md` e
  `docs/licensing.md` (vincolato da `tests/test_licensing.py`).
- OpenWork non è ancora collegato al control plane; il passthrough è testato con modelli simulati,
  non end-to-end con opencode reale.
- laya non è misurato su dati nostri; layra non è provato; nessuna garanzia di autonomia.

## Fonti (consultate il 2026-10-09)

- liweiphys/layra — https://github.com/liweiphys/layra · API: https://api.github.com/repos/liweiphys/layra
- NandhaKishorM/laya — https://github.com/NandhaKishorM/laya · API: https://api.github.com/repos/NandhaKishorM/laya · model card: https://huggingface.co/convaiinnovations/laya
- different-ai/openwork — https://github.com/different-ai/openwork · API: https://api.github.com/repos/different-ai/openwork · release v0.18.57: https://github.com/different-ai/openwork/releases/tag/v0.18.57
- CopilotKit/OpenDots — https://github.com/CopilotKit/OpenDots
- Interni: VISION.md, ROADMAP.md, docs/ag-ui.md (§2), docs/openwork-hyperspace.md, docs/mission-control.md, docs/mission-bonsai2-trial-2026-10-08.md, docs/skill-hooks.md, docs/code-sandbox.md, docs/nightly-development-dream.md, docs/code-conversation.md, control-plane/cp/chat.py, control-plane/cp/tool.py, shared/mcp_auth.py, tests/test_tool_passthrough.py.



