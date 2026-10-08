# Missioni su più macchine: dove spostare il lavoro

Questo documento nasce da un dato misurato: la prova del
[2026-10-08](mission-bonsai2-trial-2026-10-08.md) ha prodotto un PDF vero con un
modello da 27B, ma **la macchina da 16 GB non lo sostiene**. Il modello giusto
c'è; la macchina no. Quindi il lavoro va diviso.

Non è un piano per introdurre un orchestratore nuovo — quello c'è già (Mission
Control). È un piano per far **attraversare la rete** a ciò che oggi è incollato
alla macchina del control plane.

## Il problema, in numeri

| Fatto misurato | Valore |
| --- | --- |
| Pesi del 27B | 5,5 GiB |
| Tetto pratico di contesto su 16 GB | ~12k token |
| Finestra utile di una sessione | ~30 min, poi Metal OOM |
| Decode | 5,5–7 tok/s |
| Durata di una missione **minima** (un coder, un PDF) | 872 s |
| Concorrenza reale | 1 (un solo modello grande caricato) |
| Hop cross-macchina già misurato (CP-Mac → Tailscale → nodo Windows → GPU) | **1,79 s** andata e ritorno |

L'ultima riga è la più importante: **la rete non è il problema**. Un giro
completo verso un nodo con GPU su un'altra macchina costa meno di due secondi,
mentre una singola generazione del 27B ne costa decine. Il nodo Windows ha
servito un modello che il Mac non aveva e il control plane del Mac non se n'è
accorto. La distribuzione dell'**inferenza** funziona già: è tutto il resto
— dichiarazioni, prenotazioni, ripresa, sandbox — che è rimasto locale.

`docs/mission-control.md` lo dice da un'altra angolazione: in missione «la
risorsa scarsa è l'inferenza, non lo scheduler». Questo documento prende quella
frase sul serio e ne trae le conseguenze.

## Cosa esiste già, e va riusato invece che riscritto

| Pezzo | Dove | Cosa offre già | Cosa gli manca per il nostro caso |
| --- | --- | --- | --- |
| Registro nodi | `registry/`, `GET /nodes/active` | `node_id`, `status`, `tier`, `vram_gb`, `endpoint`, `capabilities`, `capacity`, `active_requests`, `last_seen`, `routing_score` | dice *quanto è grande* un nodo, non *cosa sa servire* |
| Routing | `cp/mesh.py` (`_rank_candidate_nodes`, `_best_endpoint`, `_record_routing_pick`) | scelta del nodo per modello, con le richieste in volo | punteggio basato su `tier`/`vram_gb`/latenza: cieco su contesto, supporto tool, modello caricato |
| Esecuzione su nodo | `node/main.py` (`/status`, `/metrics`, `/execute`) | `/execute` firmato; `_AdaptiveLoadLimiter` con `acquire`/`acquire_idle`/`release` per modello | nessuna **prenotazione** per un job lungo; nessun resume |
| Misure per modello | `node/backend_metrics.py` | per modello: `loaded`, `vram_gb`, `tokens_per_sec_ewma`, `latency_ms_ewma`, `requests_seen`, `data_age_s`, `sample_source`, con `schema_version` | non dichiara il contesto del server né le proprietà del modello |
| Capacità dei modelli, lato CP | `cp/model_caps.py`, `GET /models/capabilities` | dice **se e perché** un modello riceverà i tool | è locale al CP: non interroga i nodi |
| Federazione fra CP | `federation-gateway/main.py` (`ALLOWED_ROUTES`), `cp/federazione.py` (`/federate/execute`, `/federate/view`) | firma ECDSA, allowlist, pubkey, scadenza; whitelist esplicita che **esclude** le rotte amministrative (`/missions*`, `/logs`, `/nodes/active`), con un test che la blocca | è un contratto fra control plane, non un contratto di lavoro per nodi |
| Sandbox | `shared/code_sandbox.py` | due backend: **coda su file** (`SANDBOX_EXCHANGE_DIR`, heartbeat) e **HTTP con token** verso `hostctl` (`HOSTCTL_URL`, `Authorization: Bearer`) | la coda su file richiede lo **stesso** host Docker del CP; il backend HTTP ha già la forma giusta ma punta a `host.docker.internal` |
| Host agent | `hostctl/agent.py` | `GET /status`, `POST /action`, azioni fra cui `sbx_sandbox`; argv e mai shell; token ≥32 caratteri | è legato alla macchina locale per costruzione |
| Deviazione dell'inferenza | `MISSION_INFERENCE_URL` (`_mission_inference_base`) | la missione usa un backend OpenAI-compatibile diverso da Ollama, senza toccare chat e canali | è una **URL singola**: non sa scegliere fra più macchine né rispettare chi è occupato |

Il quadro che ne esce: esistono già un registro, un routing, un'esecuzione
remota firmata e un confine pubblico con whitelist. **Non manca
l'infrastruttura di rete; manca il contratto di lavoro.**

## I quattro pezzi che mancano

### 1. Un nodo non dichiara la propria inferenza

Il payload di registrazione del nodo porta `capabilities` (`node/main.py`) e
`/metrics` porta le misure per modello. Nessuno dice le tre cose che il
2026-10-08 hanno fatto fallire tre volte la stessa missione:

- **se il modello riceve i tool nativamente** → il loop li tolse in silenzio
  (`tool_loop: model=bonsai2-27b tools=False`) e l'agente fece una completion
  semplice;
- **se il server onora la temperatura** → il planner girò a temp 1.0, rispose
  senza JSON, `invalid plan`;
- **quanto contesto ha il server** → il contesto del worker (9.206 token) non
  entrava in `-c 8192`: `request exceeds the available context size`.

Tre fallimenti, tre metadati mancanti. Nessuno dei tre riguardava la capacità di
calcolo.

Proposta: un blocco `inference` **versionato** nel payload del nodo — per ogni
modello servito: nome, contesto del server, contesto libero, `tool_native`,
`json_native`, controllo del thinking, quantizzazione, tipo di KV — esposto anche
come `GET /inference/capabilities` sul nodo, sullo stampo di ciò che il CP fa già
con `/models/capabilities`. Il routing sceglie su **modello + contesto + tool**,
non su `tier`.

Accettazione: un modello nuovo servito da un nodo diventa utilizzabile da una
missione **senza toccare `.env`**; se il contesto richiesto non c'è, il task è
rifiutato con un motivo specifico invece di fallire a metà.

### 2. Prenotare la capacità, non sperarci

`_AdaptiveLoadLimiter` e `active_requests`/`capacity` esistono e impediscono la
sovrapposizione nel secondo. Ma una missione dura **15–30 minuti**: serve una
**lease con TTL** che il CP prenota per il modello che gli serve, con dentro la
scadenza della missione. Senza, due missioni su due macchine si scoprono occupate
a metà lavoro — il caso peggiore, perché i token sono già spesi.

### 3. Un envelope idempotente per la consegna

`/execute` oggi accetta un `int` firmato. Attorno a quel `int` servono `task_id`,
`attempt`, `deadline`, `idempotency_key`: è la proposta già presente in
`AGENTS.md` (confronto con AutoGen). Serve perché **il retry dopo un nodo caduto è
la norma, non l'eccezione**: senza chiave di idempotenza un retry dopo un timeout
può produrre due volte lo stesso artifact.

La firma va preservata: i campi nuovi viaggiano accanto al payload firmato, non
dentro.

### 4. Il tool loop deve poter girare dove stanno i dati

Questo è il punto vero, ed è quello che la giornata dell'8 ottobre ha mostrato
per metà. Oggi la geografia è questa:

| Cosa | Dove gira oggi |
| --- | --- |
| loop dei tool (`_run_tool_loop`, `cp/chat.py`) | sulla macchina del control plane |
| inferenza della missione | ovunque dica `MISSION_INFERENCE_URL` (**già remota**) |
| sandbox (`code_sandbox`) | sulla macchina del CP: coda su file nel volume Docker locale, oppure HTTP+token verso `hostctl` su `host.docker.internal` |
| artifact e revisione | sulla macchina del CP |

Quindi la missione ha già l'inferenza staccata dalla macchina, ma **il contesto
lo costruisce, i file li legge e le decisioni le prende il CP**. Su una macchina
senza memoria come questa, questo sposta il problema invece di risolverlo: il PDF
è stato prodotto, ma il prompt «due documenti» non ci stava comunque, perché a
comporlo è il CP, non il nodo.

Due passi, in quest'ordine:

- **Passo 1 — già fatto.** L'inferenza va su un nodo con la GPU
  (`MISSION_INFERENCE_URL`); la sandbox resta locale al CP. Basso rischio, utile
  subito, ma il CP resta il collo di bottiglia.
- **Passo 2 — il passo che serve davvero.** Il **loop intero** diventa un job su
  un nodo: il CP manda prompt, manifest dei tool e riferimenti al workspace; il
  nodo esegue le iterazioni con **la sua** GPU e **la sua** sandbox e restituisce
  `messages`, evidenze e artifact; il CP verifica e registra. Le premesse
  esistono: `node/` ha già `/execute` firmato, e la sandbox ha già un client HTTP
  con token (`SbxSandboxClient`), solo che punta alla macchina locale.

Requisito non negoziabile del passo 2: **il checkpoint del loop**. Oggi
`reclaim_orphans` rimette i task `running` a `pending` — è il livello *task*. Un
nodo che muore a metà fa ripartire il task da zero e **ripaga i token**: il
2026-10-08 una sola generazione ne ha bruciati 3.953. Serve la persistenza dello
stato del loop (messaggi + consumo) a ogni iterazione, e una ripresa che
continui invece di ricominciare.

## Topologia consigliata

Tre ruoli distinti, e **non tutti i nodi uguali**: è esattamente il punto in cui
il routing attuale sbaglia (`tier` alto non significa «sa servire un 27B con
20k di contesto»).

| Ruolo | Macchina | Cosa ci gira |
| --- | --- | --- |
| **Orchestratore** | quella di oggi, anche modesta | control plane, registro, dashboard, `planner`/`verifier` con modelli 8B, sandbox per artifact piccoli. Non deve avere il modello grande per coordinare. |
| **Nodo di lavoro grande** | 24 GB di VRAM dedicata, o 32–64 GB di memoria unificata | `coder` con il modello grande, tool loop completo, sandbox propria, artifact locali. È il nodo che oggi manca. |
| **Nodi piccoli** | nodi Windows/Linux già in mesh, web node nel browser | task brevi senza loop di tool: classificazione, traduzione, embeddings, summarization. Il web node **tira** (pull/long-poll) perché il browser non accetta HTTP in ingresso: non cambia con questo piano. |

Regola di indirizzamento: la scelta del nodo si fa per **modello + contesto
richiesto + supporto ai tool**, con la latenza come criterio secondario (l'hop
costa 1,79 s, una generazione decine di secondi: la rete non decide).

## Dimensionamento pratico

La formula che i numeri dell'8 ottobre suggeriscono, per un modello denso:

```
pesi + KV(ctx) + ~20% di headroom + il sistema operativo e l'IDE
```

Con un 27B ternario i pesi sono 5,5 GiB, ma è il **KV** a decidere il tetto: con
16 GB il limite pratico è ~12k di contesto e la sessione dura ~30 minuti. Il
contesto da riservare è `prompt del loop + output`, non il massimo che il server
sa fare: prendere `-c` grande «per sicurezza» è la ricetta dell'OOM. Ridurre il
KV a 4 bit **non** è la scorciatoia: su questo fork/M5 il prefill è crollato da
~90 a ~12 tok/s.

Conseguenza operativa: un nodo di lavoro grande serve **solo** a quello. Se ci
gira anche l'IDE, la finestra si chiude prima.

## Confine di sicurezza (invarianti da non rompere)

- **Le rotte di missione non si federano.** `/missions*` non è in
  `ALLOWED_ROUTES` del `federation-gateway` ed è deliberato, con un test che lo
  blocca (`tests/test_mission_routes.py`). Un nodo che esegue task di missione
  deve essere **un nodo della mesh** (`/execute`, firmato, con identità ECDSA),
  non un'esposizione dell'API amministrativa.
- **Nessun artifact si applica da solo.** `applied` resta `false` anche dopo una
  review `approve`; spostare l'esecuzione su un'altra macchina non cambia questa
  regola, la rende solo più importante (i file stanno su un'altra macchina).
- **La sandbox resta senza rete** (`network_mode: none`) e usa-e-getta: il nodo
  di lavoro non deve avere un percorso verso l'interno della rete locale.
- **Il `.env` non viaggia.** Lezione di `windows-node-handoff.md`: `.env` è in
  `.gitignore`, nessuna variabile si aggiorna da sola, e un fix nel repo non
  arriva al processo già avviato finché non si riconcilia il file. Vale doppio
  quando le macchine sono più di una: serve una verifica di versione/contratto
  all'avvio, non la fiducia che «tanto è lo stesso repo».

## Cosa misurare

Metriche per missione, non solo il verdetto del verifier:

- tasso di completamento **con artifact verificato** da un gate indipendente;
- token consumati e costo, tempo totale, numero di retry;
- **quale nodo ha servito** e con quale contesto;
- motivo del fallimento, con un codice distinguibile (`context_too_small`,
  `model_no_tools`, `node_unavailable`, `sandbox_limit`, …) invece di un errore
  generico.

Su un dataset versionato di missioni campione — dentro c'è anche la
presentazione PDF — così una modifica si confronta con un baseline
riproducibile.

## Ordine di lavoro

1. **P0a — capability di inferenza nel registro.** Blocco `inference` +
   `GET /inference/capabilities` sul nodo; routing che rifiuta un task quando il
   contesto non basta. Piccolo, testabile, e copre da solo tre dei fallimenti
   dell'8 ottobre.
2. **P0b — lease + ripresa del loop.** Prenotazione con TTL e checkpoint dello
   stato del loop. È il prerequisito perché una missione lunga su una macchina
   remota sia affidabile.
3. **P1 — il loop come job sul nodo.** Passo 2 sopra: prompt + manifest in
   ingresso, `messages` + evidenze + artifact in uscita.
4. **P2 — envelope versionato e deduplica.** `task_id`/`attempt`/`deadline`/
   `idempotency_key`, nodo offline, risultato tardivo, consegna duplicata.

L'ordine conta: P0a e P0b si possono fare **senza** spostare nulla, e senza di
essi il passo 3 produce solo nuovi modi di perdere token.

## Cosa non fare adesso

- **Non importare LangGraph, CrewAI, AutoGen o n8n.** Resta la conclusione del
  report in `AGENTS.md`: si prendono i pattern, non i runtime.
- **Non introdurre Redis o un secondo orchestratore** prima che una missione sia
  affidabile su una macchina sola.
- **Non passare a gRPC «per principio»**: i browser node non accettano HTTP in
  ingresso, il pull/long-poll resta il trasporto giusto per loro. Prima un
  envelope interoperabile, poi il trasporto per tipo di nodo.
- **Non alzare `MISSION_MAX_CONCURRENCY`** per compensare: la risorsa scarsa è
  l'inferenza, e su un nodo grande la concorrenza reale è 1.
