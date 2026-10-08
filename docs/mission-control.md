# Mission Control

Mission Control trasforma un obiettivo in un **DAG di task** e lo esegue in modo
limitato e verificabile: pianifica, distribuisce, verifica e — se serve —
ripianifica. È distinto dal [Nightly Development Dream](nightly-development-dream.md):
quello produce una proposta di codice dopo inattività, questo esegue una missione
richiesta da un operatore, con più ruoli e una verifica per task.

Nessuna rotta applica mai un artifact: il codice vive in una sandbox
usa-e-getta, ogni artifact porta `applied: false` e la revisione umana registra
la decisione, non la esegue.

## Sequenza e gate

1. L'operatore crea la missione (obiettivo + criteri di accettazione) e sceglie
   se avviarla subito o lasciarla `planned`. Può restringere i ruoli con
   `allowed_roles`, per esempio `["coder"]` per un artefatto locale: il server
   conserva l'allowlist e corregge una role fuori lista proposta dal planner.
2. Il **planner** decompone l'obiettivo in task. Ruoli fuori allowlist, chiavi
   duplicate e dipendenze verso task inesistenti vengono filtrati; il DAG viene
   poi validato dallo store. Un piano malformato fa fallire la missione con un
   errore leggibile, non la corrompe.
3. Il **dispatch** procede a ondate: solo i task `ready` (dipendenze `done`),
   fino a `max_concurrency`, in un `ThreadPoolExecutor`.
4. Il **worker** esegue un singolo task con i soli tool del suo manifest e
   riceve in prompt gli output dei task a monte.
5. Il **verifier** giudica il task: `pass`, `retry`, `replan` o `fail`. Un
   verdetto `replan` fa produrre nuove task al planner (mai le stesse chiavi).
6. Quando ogni task è terminale il verifier si pronuncia sulla missione:
   `pass` → `done`, `replan` → nuove task (fino a `max_replans`), altrimenti
   `failed` con il motivo.
7. Il codice prodotto resta nella sandbox: l'artifact (workspace, file cambiati,
   diff) attende la revisione umana. Il solo tool che scrive altrove è
   `create_website` del coder — un sito statico in `WEBSITE_DIR` — catturato
   come artifact `website-project` (`applied: false`) con la sua preview.

## Ruoli e manifest

Il manifest è l'unica fonte di verità su cosa un ruolo può vedere, e il control
plane gli passa solo l'**intersezione** con il proprio catalogo nativo: un ruolo
non può chiamare un tool che non possiede, anche se il modello lo inventa.

| Ruolo | Tool | Iterazioni | Classe modello | Review |
| --- | --- | --- | --- | --- |
| `planner` | — | 1 | reasoning | no |
| `repo-analyst` | `web_search`, `omega_query`, `get_mesh_status` | 8 | general | no |
| `coder` | `code_sandbox`, `create_website` | 16 | code | sì |
| `verifier` | `code_sandbox`, `get_mesh_status`, `website_status` | 8 | code | no |
| `memory-agent` | `omega_query` | 4 | general | no |
| `ops-agent` | — (spento: `shell_run`, `get_mesh_status` solo con `MISSION_OPS_AGENT_ENABLED=true`) | 4 | code | sì |
| `worker` | `web_search`, `omega_query`, `get_mesh_status` | 6 | general | no |

Un ruolo sconosciuto — per esempio per un refuso nel piano — ricade sul manifest
`worker` (`DEFAULT_ROLE`), non su quello più potente. Gli strumenti di identità
non entrano in nessun manifest.

## Budget

I limiti vivono in `shared/mission_policy.py` e valgono per l'intera missione.
`POST /missions` accetta un oggetto `budget` che li abbassa ulteriormente; i
valori restano comunque dentro i minimi e i massimi del codice (per esempio
`max_concurrency` non supera il tetto di 8: la risorsa scarsa è l'inferenza,
non lo scheduler).

| Chiave (`budget`) | Env | Default |
| --- | --- | --- |
| `max_steps` | `MISSION_MAX_STEPS` | 40 |
| `max_wall_seconds` | `MISSION_MAX_WALL_SECONDS` | 3600 |
| `max_tokens_per_task` | `MISSION_MAX_TOKENS_PER_TASK` | 4096 |
| `max_concurrency` | `MISSION_MAX_CONCURRENCY` | 2 |
| `max_replans` | `MISSION_MAX_REPLANS` | 3 |
| `max_task_attempts` | `MISSION_MAX_TASK_ATTEMPTS` | 2 |

Esaurito il budget la missione passa a `failed` con il motivo nei log
(`budget exhausted: steps=… replans=… elapsed=…s`), invece di girare a vuoto.

## Stato e persistenza

- `missions.jsonl` in `MISSION_DATA_DIR` (default `/app/data`, nei compose
  `/repo/data`): riscrittura atomica, rilettura a ogni chiamata.
- Stati di missione: `planned`, `running`, `blocked`, `done`, `failed`,
  `cancelled`. Stati di task: `pending`, `ready`, `running`, `done`, `failed`,
  `skipped`.
- **Una missione per volta**: il lock è non bloccante, una seconda partenza
  viene rifiutata con 409 invece di accodarsi.
- Ripresa dopo un riavvio: i task rimasti `running` senza più un thread tornano
  `pending` (`reclaim_orphans`).
- Il **loop** che riprende da solo le missioni aperte è spento di default
  (`MISSION_LOOP_ENABLED=false`). Quando è acceso controlla ogni
  `MISSION_TICK_SECONDS` (minimo 5) e tace se c'è attività in primo piano da
  meno di `MISSION_FOREGROUND_PAUSE_S`. Una missione con revisioni in sospeso non
  riparte: aspettare l'umano è il punto della guardia.

## Rotte

Tutte richiedono lo stesso token operatore delle dream review
(`DREAM_REVIEW_TOKEN`, almeno 32 caratteri) inviato come
`Authorization: Bearer …`. Un obiettivo interno non è materiale da endpoint
pubblico: senza token la risposta è 503 (token assente o troppo corto) oppure
401.

| Rotta | Metodo | Cosa fa |
| --- | --- | --- |
| `/missions/status` | GET | Motore: `running`, `last_mission`, concorrenza, budget, conteggi e `loop` |
| `/missions` | GET | Inbox (`?status=…&limit=…`) con i payload delle missioni |
| `/missions` | POST | Crea la missione (`objective`, `criteria`, `budget`, `allowed_roles`, `start`) |
| `/missions/<id>` | GET | Dettaglio: task, verifica, plan log, revisioni, budget |
| `/missions/<id>/run` | POST | Avvia (202) o 409 se un'altra missione è in corso |
| `/missions/<id>/cancel` | POST | Chiede l'annullamento (`reason`); la ondata in corso si ferma al checkpoint |
| `/missions/<id>/review` | POST | Registra `approve`/`reject`/`defer`/`reopen` con `rationale` obbligatoria |

```bash
TOKEN="$DREAM_REVIEW_TOKEN"
BASE="http://localhost:8085"

curl -s -H "Authorization: Bearer $TOKEN" "$BASE/missions/status"

curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"objective":"ridurre i timeout di rete","criteria":["i test passano"],"start":true}' \
  "$BASE/missions"

# La review registra solo la decisione: la risposta porta sempre applied: false.
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"action":"approve","reviewer":"operator","rationale":"diff verificato a mano"}' \
  "$BASE/missions/<id>/review"
```

## Dashboard

Nel pannello **Autogenerazione** la card *Mission Control* offre filtro per stato,
obiettivo, criteri (uno per riga), `Pianifica` e `Pianifica e avvia`; mostra lo
stato del motore (loop, budget, conteggi), per ogni missione budget e contatori,
l'ultima decisione di review, l'elenco dei task con ruolo, stato, tentativi,
dipendenze, verdetto e numero di artifact, e le azioni `Avvia`, `Annulla`,
`Approva`, `Rifiuta`, `Rimanda`. Il token è quello del campo *Token revisione*
condiviso con la Dream Review Inbox. L'inbox si aggiorna da sola ogni 10 secondi
solo se il pannello è visibile **e** l'ultimo caricamento è andato a buon fine.

## Prerequisiti sandbox

Senza `CODE_SANDBOX_ENABLED=true` il tool `code_sandbox` si limita a riportare lo
stato del backend: i task girano, ma non esiste nessun diff da revisionare. Il
workspace nasce da una copia usa-e-getta del seed dell'immagine
(`sandbox/Dockerfile`, `COPY . /seed`), quindi il seed deve essere **leggibile**
dall'utente non privilegiato che esegue i job: il Dockerfile chiude con
`chmod -R a-w /seed && chmod -R a+rX /seed` (un file 0600 nel repo — per esempio
una cache `graphify-out/` — faceva fallire *ogni* `create` con "Permission
denied") e `.dockerignore` tiene fuori le cache rigenerabili. Il runner accetta
al massimo `SANDBOX_MAX_WORKSPACES` workspace (default 6) e risponde
`workspace limit reached` a limite raggiunto: prima di una missione conviene
chiudere i workspace vecchi con `discard`.

## Perché non passa dal federation-gateway

`federation-gateway/main.py` non elenca `/missions*` in `ALLOWED_ROUTES`, ed è
deliberato. Il gateway esiste per esporre verso peer accoppiati e browser node i
soli contratti che il control plane verifica da sé (firma ECDSA, allowlist,
token); le rotte di missione sono amministrative, protette da un token operatore
e pensate per la rete interna, come `/logs`, `/tasks` e `/config`. Un test
(`tests/test_mission_routes.py`) blocca la whitelist: se un giorno si volesse
federarle, la decisione deve essere esplicita e non un effetto collaterale.

## Cosa non fa

- Non applica, non committa, non pusha, non distribuisce: `applied` è sempre
  `False`, anche dopo una review `approve`.
- Non tocca l'host: nessun tool host nei manifest, e `ops-agent` è spento
  finché `MISSION_OPS_AGENT_ENABLED` non è `true`.
- Non esegue due missioni insieme e non prioritizza la coda.
- La cancellazione è cooperativa: impedisce le chiamate successive ai checkpoint,
  ma non interrompe un tool esterno o una richiesta di inferenza già in corso.
- Il verifier resta un modello: il suo giudizio non sostituisce test e review.
  Una risposta vuota o malformata non approva più nulla: richiede un nuovo
  tentativo sul task oppure fa fallire la verifica finale.
- Il conteggio riguarda i token di output, non il costo totale di input e output.
  Planner e verifier hanno un limite per chiamata; il budget cumulativo per task
  riguarda il worker, inclusi i tentativi falliti.

## Configurazione

```dotenv
DREAM_REVIEW_TOKEN=            # >= 32 caratteri: abilita anche la review umana
MISSION_LOOP_ENABLED=false     # il loop che riprende da solo le missioni aperte
MISSION_MODEL=                 # vuoto = NIGHTLY_DEV_MODEL
MISSION_PLANNER_MODEL=         # vuoto = MISSION_MODEL
MISSION_INFERENCE_URL=         # vuoto = l'Ollama del control-plane; altrimenti planner/worker/verifier vanno su questo backend OpenAI-compatibile
MISSION_MAX_CONCURRENCY=2      # tetto nel codice: 8
MISSION_MAX_REPLANS=3
MISSION_FOREGROUND_PAUSE_S=120
MISSION_TICK_SECONDS=15
```

Le missioni persistono in `missions.jsonl` sotto `MISSION_DATA_DIR` e
sopravvivono ai riavvii; l'orchestrazione finisce nel feed dei log con
`type=mission` (`/logs?type=mission`).


## Hook di esecuzione (2026-10-07)

`shared/tool_runtime.py` contiene il contesto `Invocation`, costruito dal server.
Prima dell'inferenza limita la generazione e controlla cancellazione/scadenza;
prima del dispatch controlla che il tool sia stato offerto in quella invocazione
e che gli argomenti siano un oggetto JSON valido. Il verifier può usare soltanto
le azioni sandbox `status`, `catalog`, `list`, `read`, `diff`, `check`, `verify`.
Dopo il tool registra evidenze strutturate: un errore non viene più loggato come
successo. I log generici del loop non copiano argomenti e risultati integrali.

Il budget effettivo è il minimo fra richiesta e tetto globale. Anche le ondate
parallele rispettano i passi rimasti; il tempo già speso viene conservato alla
ripresa. I token dichiarati dal backend vengono accumulati; se il backend non
riporta il consumo, o il trasporto fallisce, viene addebitato conservativamente
il massimo richiesto e `usage_known` diventa falso. Questo può fermare prima un
task su backend privi di metriche, ma non considera gratuito un consumo ignoto.

Planner, worker e verifier ricevono i criteri persistiti in `success_criteria`.
Un coder senza artifact né evidenza strutturata di verifica completata e passata
non supera la verifica soltanto perché dichiara di aver finito.

Una review `approve` copre l'impronta dei metadati degli artifact e dell'output
dei task presenti al momento della decisione. Non è un hash dei byte su disco.
Artifact successivi o metadati/output cambiati richiedono una nuova review;
`defer`, `reopen` e `reject` non equivalgono ad approvazione. Le vecchie review
senza impronta richiedono una nuova approvazione.

Questi hook non selezionano automaticamente le skill e non ne eseguono il testo.
Il collegamento comune fra skill approvate, capacità e missioni resta lavoro
successivo, insieme al benchmark con/senza skill.
