# Agenti su questo repository

Questo repository è lavorato da più agenti sulla **stessa macchina e sullo
stesso filesystem**. Per non sovrascriversi a vicenda usano due file in radice:

- **AGENTS.md** (questo file) — chi lavora qui, le regole di base e dove sta la
  verità.
- **[AGENT-LOG.md](AGENT-LOG.md)** — i messaggi fra agenti, in ordine
  cronologico. Si **aggiunge in fondo**: quello che ha scritto un altro non si
  riscrive e non si cancella.

I rimandi che gli agenti caricano da soli stanno in radice: `CLAUDE.md` per
Claude Code, `.clinerules/agent-protocol.md` per Cline. Gli altri agenti vanno
indirizzati qui dall'utente.

## Chi scrive qui

| Agente | Dove lavora | Nota |
|---|---|---|
| **Cline** (VS Code) | `/Users/opo/hyperspace-agi-1.04` | lavora dentro il repository |
| **Codex** | `/Users/opo/hyperspace-agi-1.04` | infrastruttura (Control Plane, Registry, bridge); ha risposto al primo passaggio di consegne |
| **Claude Code** | `/Users/opo/Downloads/tiktok_editor` | cantiere storico dell'editor, memory ferma al 2026-09-09; non ha ancora risposto |

## Regole

1. **La verità è il repository.** `/Users/opo/Downloads/tiktok_editor` non è un
   repository git ed è fermo al 2026-09-09 15:1x: da lì serve solo `.venv/`, il
   runtime Python dell'editor (Python 3.14.5, con numpy, librosa, numba,
   gradio). Lo sviluppo attivo sta in `integrations/tiktok_editor/app/`, che è
   più avanti di circa un mese (2026-10-05 23:5x) e contiene file che la cartella
   `Downloads` non ha: `autoedit/guides.py`, `autoedit/person_layers.py`,
   `autoedit/person_mask.swift`, `autoedit/scene_vision.py`, `draft.py` e due
   preset.
2. **Un messaggio per intervento.** Prima di iniziare leggere `AGENT-LOG.md`;
   quando si finisce aggiungere un blocco in fondo con data, agente e cosa è
   stato fatto o cosa si chiede.
3. **Nessun commit e nessun push senza conferma esplicita dell'utente.** Il
   lavoro non committato su `main` non è poco: al 2026-10-06 sono 60 file
   modificati, 116 non tracciati e 10 cancellati — questi ultimi **già in stage**
   (`obsidian/*`, `memory-graph/*`, i `.json` di `data/obsidian-vault/.obsidian/`).
   Obsidian è uscito dallo stack: la memoria è `hermes` (`docs/hermes.md`), il
   grafo del repository è `graphify` (`docs/graphify.md`).
4. **Nessun segreto nei file.** I file `.env` tracciati sono già in storia: non
   aggiungere valori reali, nemmeno in `.env.example`.
5. **I test girano nel `.venv` del repository**, non in quello dell'editor.

## Verificare

```bash
# suite del repository (interprete del repo): è quella che deve restare verde
.venv/bin/python -m pytest tests/ -q

# i test del reel anche nel loro ambiente: il .venv del repo NON ha numpy/librosa,
# quello dell'editor sì (unittest è già dentro i file, quindi basta l'interprete)
/Users/opo/Downloads/tiktok_editor/.venv/bin/python tests/test_tiktok_editor_integration.py
/Users/opo/Downloads/tiktok_editor/.venv/bin/python tests/test_reel_person_layers.py
/Users/opo/Downloads/tiktok_editor/.venv/bin/python tests/test_reel_webui_vision.py
```

Al 2026-10-06, con il `.venv` del repository:
**5 failed, 1811 passed, 17 skipped** (54,7s). I tre moduli del reel
(`tests/test_reel_person_layers.py`, `tests/test_reel_webui_vision.py`,
`tests/test_tiktok_editor_integration.py`) portano una guardia che li fa
**saltare** — non fallire — quando mancano numpy/librosa: lo skip vale solo per
quelle dipendenze opzionali, un import rotto per altre ragioni continua a farsi
sentire, e la raccolta della suite non viene più annullata. Con l'interprete
dell'editor gli stessi moduli eseguono davvero e passano (3 + 5 + 8 test).

I 5 fallimenti che restano sono **fuori dal perimetro reel** e sono debito della
working tree, non del codice dell'editor:

| Test | Causa |
|---|---|
| `tests/test_licensing.py` (3) | i 5 file cancellati e non committati sono ancora nell'indice: il test li enumera e non li trova |
| `tests/test_prova_colori_anna.py` (1) | le scene della serie Anna non tornano a posto (50 != 30) |
| `tests/test_comfyui_modelli_sd15.py` (1) | il documento runtime di Anna dichiara soglie diverse dal manifest (0.55 != 0.45) |

Il dettaglio, le risposte di Codex e le domande aperte sono in
[AGENT-LOG.md](AGENT-LOG.md).

## Stato noto al 2026-10-06

Il Reel Editor è descritto in [docs/tiktok-editor.md](docs/tiktok-editor.md), con
le ricette in [docs/reel-forge-recipes.md](docs/reel-forge-recipes.md). Servizio
locale in `scripts/tiktok_editor_service.py` (loopback `127.0.0.1:7860`),
avvio con `integrations/tiktok_editor/com.hyperspace.tiktok-editor.plist` e con
`scripts/start-all-macos.sh`. Nessuno di questi file è ancora tracciato da git.

## Report condiviso — LangGraph, CrewAI, AutoGen e n8n (2026-10-07)

Questo report è una **lista di pattern da valutare per HyperSpace 1.05**, non
un'istruzione a installare i quattro prodotti. I riferimenti sono le
documentazioni ufficiali consultate il 7 ottobre 2026:
[LangGraph — Thinking in LangGraph](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph),
[CrewAI — documentazione](https://docs.crewai.com/),
[AutoGen — Distributed Agent Runtime](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/distributed-agent-runtime.html),
[n8n — documentazione](https://docs.n8n.io/).
Il punto di confronto locale è [docs/mission-control.md](docs/mission-control.md)
e il risultato reale della [prova PDF](docs/mission-pdf-trial-2026-10-07.md):
cinque missioni tracciate, nessun PDF prodotto. In questo momento è più utile
far riuscire quel flusso che aggiungere un altro orchestratore.

### LangGraph — rendere espliciti stato, transizioni ed errori

La guida parte dal processo, lo spezza in passi con responsabilità singola
(LLM, dati, azione, input umano), fa condividere uno **stato strutturato** e
instrada in base all'esito di ogni passo. Nello stato salva i dati grezzi,
non prompt già formattati: questi si costruiscono al momento dell'inferenza.
Per HyperSpace: formalizzare il contratto fra planner, worker, verifier e review
con campi tipizzati per obiettivo, criteri, capability effettive, fonti,
artifact, evidenze, errori, tentativi e decisione. Evitare di ricostruire
l'esito da testo libero o log. Ogni transizione deve dichiarare precondizioni
e possibili stati successivi. [Fonte: progettazione dello stato](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph#step-3-design-your-state).

La guida distingue errori transitori (retry con backoff), correggibili dal
modello (errore strutturato nello stato e nuovo tentativo limitato), risolvibili
da un umano (pausa), esauriti (compensazione) e inattesi (errore visibile).
Per HyperSpace: codici d'errore distinguibili per `workspace_full`,
`path_denied`, `file_missing`, `tool_unavailable`, `model_invalid_output` e
`verification_failed`; il worker deve ricevere un feedback utilizzabile senza
loggare segreti o contenuti integrali. [Fonte: gestione degli errori](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph#handle-errors-appropriately).

Checkpoint ai confini dei passi e pausa/ripresa dopo input umano sono utili
per missioni lunghe. La guida avverte che, al resume, il nodo interrotto può
rieseguire il codice che precede l'interruzione: quindi **nessuna azione
esterna prima del punto di pausa** senza idempotency key/record durevole.
Scegliere checkpoint dopo operazioni costose o irreversibili, non per ogni
microfunzione. Mission Control ha già persistenza e `reclaim_orphans`: prima
verificare con test di riavvio dove si ripete lavoro o si rischia il doppio
invio. [Fonte: checkpoint e review](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph#step-5-wire-it-together).

### CrewAI — autonomia entro un flusso governato

CrewAI distingue **Crews** (collaborazione più aperta di agenti) da **Flows**
(sequenze, diramazioni ed eventi espliciti). Per HyperSpace la metafora utile
è: Mission Control governa il flusso, il singolo ruolo ha autonomia solo nel
suo task e nel proprio manifest. Non sostituire il controller con una crew
generica. [Fonte: Flows](https://docs.crewai.com/en/concepts/flows).

I Flows associano stato e ID alla run, routing condizionale, persistenza e
resume/fork. L'idea riutilizzabile è rendere ogni missione **riproducibile**:
versione del piano, capability risolte al momento dell'avvio, modello/prompt,
input e decisioni umane come snapshot; una ripartenza continua la stessa run,
mentre un esperimento alternativo ha nuovo ID e conserva la storia originale.
[Fonte: Flow Persistence](https://docs.crewai.com/en/concepts/flows#flow-persistence).

I task supportano output strutturati e guardrail che validano l'output prima
del passo successivo, con retry limitato e feedback dell'errore. Per HyperSpace
questo suggerisce **validatori per tipo di artefatto**, indipendenti dal giudizio
del modello: PDF = file esistente, firma, pagine, testo/fonti; codice = diff e
test; documento = formato apribile e fonti; ricerca = citazioni verificabili.
Un output testuale `ok` non sostituisce questi gate. [Fonte: task e guardrail](https://docs.crewai.com/en/concepts/tasks).

### AutoGen — confine host/worker e messaggi tipizzati

Nel runtime distribuito AutoGen un host mantiene connessioni e consegna
messaggi; i worker dichiarano i tipi di agenti che ospitano. Sono mostrati
messaggi diretti e publish/subscribe; per runtime in linguaggi diversi, i
messaggi devono avere schemi protobuf condivisi. La documentazione chiama
questa funzione **sperimentale** e avverte di possibili breaking change.
[Fonte: runtime distribuito](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/framework/distributed-agent-runtime.html).

Per HyperSpace: confrontare il proprio Registry/mesh con questo contratto,
registrando capability e versioni di schema realmente eseguibili, health e
identità del nodo; separare messaggi di controllo, task e telemetria. Aggiungere
`task_id`, `attempt`, deadline e idempotency key alle consegne; misurare
retry, duplicati e nodi offline. Non adottare gRPC/AutoGen per principio:
il browser node attuale usa pull/long poll perché il browser non accetta HTTP
in ingresso. Mantenere un envelope interoperabile, poi scegliere il trasporto
per tipo di nodo. HIP resta una direzione futura, non una capacità già attiva.

### n8n — ergonomia operativa ed evaluation

n8n offre trigger, integrazioni, storico delle esecuzioni, gestione errori e
una UI visuale: è un benchmark di **esperienza operatore**, non qualcosa da
riscrivere subito. Le sue error workflow separano fallimento, nodo responsabile,
run originale ed eventuale retry. Per HyperSpace: nella dashboard mostrare
per ogni missione la timeline con input/output sintetici, causa del blocco,
artifact e un'azione sicura di ripresa o nuovo tentativo; allertare sul
fallimento senza scambiarlo per successo. [Fonte: error workflows](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully.md).

n8n propone evaluation su dataset di casi, prima piccola e manuale, poi con
metriche e regressioni ricavate dalle run reali. Per HyperSpace: mantenere un
dataset versionato di missioni campione (inclusa la presentazione PDF),
registrando tasso di completamento **con artefatto verificato**, costo/token,
tempo, retry, errori e qualità della review. Confrontare modelli e prompt sullo
stesso dataset; non misurare solo il verdetto del verifier. [Fonte: evaluation](https://docs.n8n.io/build/integrate-ai/test-and-improve-ai-workflows/understand-why-to-test.md).

Il queue mode n8n separa trigger e worker, con broker, database condiviso e
limiti operativi espliciti. È utile come riferimento quando HyperSpace avrà
più missioni concorrenti, ma **non è una priorità ora**: introdurre Redis e un
secondo orchestratore prima di una missione affidabile aumenterebbe le parti
da gestire. [Fonte: queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode.md).

### Ordine di lavoro proposto a Cips/Cline e Codex

1. **P0 — missione PDF ripetibile.** Planner vincolato alle capability reali;
   lettura batch dei documenti; spazio disponibile nel runner; generatore PDF
   installato; errori tool strutturati; gate PDF indipendente dal modello.
   Accettazione: tre run da zero producono PDF leggibili e fonti controllabili,
   oppure falliscono con motivo specifico; nessuna review applica file da sola.
2. **P1 — contratto run e ripresa.** Stato tipizzato, versioni e snapshot di
   piano/capability, checkpoint dopo passi costosi, idempotenza delle azioni e
   test di crash/restart/HITL. Accettazione: nessuna azione esterna duplicata
   dopo resume; budget e criteri sopravvivono identici al riavvio.
3. **P1 — osservabilità ed eval.** Timeline task/tool e codici d'errore nella
   dashboard; dataset di regressione con artefatti, latenza e costo. Accettazione:
   una run fallita indica il passo e il motivo; una modifica si confronta con
   un baseline riproducibile.
4. **P2 — contratti distribuiti.** Envelope versionato, capability negoziate,
   deduplica e heartbeat per nodi pesanti/browser. Testare perdita connessione,
   risultato tardivo e consegna duplicata prima di introdurre nuovi trasporti.

Nessuna di queste idee richiede adesso di importare LangGraph, CrewAI, AutoGen
o n8n nel runtime. Se una libreria risolve un problema misurato meglio del codice
locale, valutarla in una prova isolata con licenza, dipendenze e rollback.
