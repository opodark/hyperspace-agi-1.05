# AG-UI — protocollo client↔agente: la decisione (P0) e lo spike (P1)

AG-UI (*Agent-User Interaction Protocol*) è un protocollo aperto che descrive
come un agente racconta a un frontend quello che sta facendo: un flusso di
eventi su SSE con un formato di evento fissato. Nasce per il problema opposto
al nostro — portare agenti dentro una UI React — ma il suo **formato di filo**
risolve un problema che abbiamo già in casa: la dashboard oggi scopre cosa
succede *chiedendolo*, con `fetch('/logs?per_page=200')` in polling.

Questo documento è la decisione presa (**P0**), non un piano di adozione. Lo
spike che ne discende (**P1**) tocca **un solo** flusso, dietro un flag spento
di default, e non cambia nessun contratto esistente.

Al momento in cui si scrive, `git grep` non trova nessuna occorrenza di `ag-ui`
fra i file tracciati: questo documento è la prima menzione nel repo.

> `P0` e `P1` qui sono i due passi di questo filone di lavoro: prima la
> decisione, poi la prova. Non hanno niente a che vedere con la colonna
> *priorità* del [ROADMAP](../ROADMAP.md).

## 1. Cos'è oggi: protocollo maturato, SDK giovani

Verificato il 2026-10-04 sulle fonti primarie (PyPI, docs.ag-ui.com, API GitHub):

| Cosa | Stato |
|---|---|
| Specifica | **1.0**: lo schema `/spec/1.0/schema` è l'unica fonte di verità, e i tipi di **ogni** SDK sono generati da esso |
| SDK Python (`ag-ui-protocol` su PyPI) | **1.0.0**, licenza **MIT**, `requires_python >=3.9`, wheel `py3-none-any` da 36,8 kB |
| Dipendenze dell'SDK Python | **una sola**: `pydantic>=2.11.2` — obbligatoria, non un extra (`requires_dist` = `['pydantic>=2.11.2']`) |
| Trasporto | JSON su SSE (invariato in 1.0); esiste anche un binding protobuf |
| Repo del protocollo (`ag-ui-protocol/ag-ui`) | TypeScript-first, ~16.300★, MIT |
| Client di riferimento | `CopilotKit/OpenBot` e `CopilotKit/OpenDots`: TypeScript/React, MIT, creati fra agosto e settembre 2026 (§2) |

La 1.0 è, nelle parole della guida *Migrating to 1.0*, **«the first release with
a specification behind it»**: prima il comportamento *era* quello degli SDK,
adesso esiste un documento normativo che lo fissa e gli SDK ne derivano. Per chi
vuole solo emettere il formato, è il dettaglio che cambia tutto.

Due cose contano più delle altre.

**Il formato è fissato e verificabile.** `EventEncoder.encode()` produce
esattamente questo, e nient'altro:

```
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg_123","delta":"Hello from Python!"}\n\n
```

In 1.0 è **normativo** che i campi opzionali senza valore si **omittano**
invece di scriverli `null` («Omit whole optional null fields»), perché è ciò
che mette sul filo un produttore TypeScript. Ogni evento porta `type` e può
portare `timestamp`, `rawEvent` e `metadata`; `metadata` è un oggetto aperto
per chiave, e la documentazione ne nomina esplicitamente gli usi: *token usage,
un trace id, un finish reason*. Le chiavi sul filo sono camelCase
(`messageId`, non `message_id`); le classi dell'SDK sono snake_case.

**L'SDK Python costa una dipendenza che oggi non abbiamo.** Il pacchetto è
minuscolo (36,8 kB; nelle 0.1.x era ~6 kB), ma installarlo tira dentro
`pydantic>=2.11.2` — e `control-plane/requirements.txt` oggi non ha pydantic,
mentre la CI installa soltanto `flask flask-cors requests cryptography httpx
pytest bandit ruff`. Non è una condanna: è il motivo per cui il *formato* si
può emettere a mano e l'*SDK* entra solo come dipendenza **di test** opzionale.

## 2. Perché non partire da un'applicazione esistente

La tentazione è prendere uno dei progetti di riferimento — gli «AI coworkers»
(`CopilotKit/OpenBot`, `CopilotKit/OpenDots`) — come base e adattarlo. I numeri
dicono perché no:

| Repo | Creato | Commit | ★ | Fork | Issue aperte | Linguaggio |
|---|---|---|---|---|---|---|
| `CopilotKit/OpenBot` | 2026-08-17 | 498 | 5.984 | 802 | 20 | TypeScript |
| `CopilotKit/OpenDots` | 2026-09-29 | 18 | 2.768 | 346 | **51** | TypeScript |
| `CopilotKit/CopilotKit` | — | — | 37.730 | — | — | TypeScript/React |

Tre ragioni, in ordine di peso.

1. **Inversione di stack.** Sono applicazioni TypeScript/React (con Node). Il
   control plane è Flask puro con SSE scritto a mano
   (`control-plane/main.py:2396`) e una `dashboard.html` statica in JS vanilla.
   Adottarne una come base significa introdurre una catena di build Node/React,
   un secondo server e una seconda superficie di autenticazione in un repo che
   ha già 19 servizi Compose. Non è una feature in più: è una biforcazione
   dello stack.
2. **Maturità.** Un repo di 5 giorni, 18 commit e 51 issue aperte non può essere
   una base; anche `OpenBot` (7 settimane) è un bersaglio mobile. Adotteremmo
   l'alpha di qualcun altro proprio mentre la Fase 3.5 ha bisogno di un
   inventario **congelato**.
3. **Il valore è la specifica, non l'applicazione.** Il formato è pubblico e
   genera i tipi di ogni SDK: si può emettere senza adottare l'app di nessuno.
   La licenza MIT non è l'ostacolo — lo sono pure i due client: l'ostacolo è
   che riusare quel *codice* significa ereditare quello *stack*.

## 3. Cosa prendiamo: quattro cose

**a) Il formato di filo.** Emesso a mano in `shared/ag_ui.py`: una tabella
`EventType` locale e `encode(event) -> bytes` che produce `data: {...}\n\n`,
camelCase, con omissione dei campi opzionali non valorizzati. Puro, senza
dipendenze, quindi verificabile byte per byte.

**b) Il vocabolario delle capability.** `AgentCapabilities` organizza le
capacità in categorie (`identity`, `transport`, `tools`, `output`, `state`,
`multiAgent`, `reasoning`, `multimodal`, `execution`, `humanInTheLoop`,
`custom`), rette da due principi: *discovery only*, l'agente dichiara e non si
negozia nulla, e *absent = unknown*, cioè si dichiara solo ciò che si supporta.
È il vocabolario che il capability manifest di S4 adotta invece di inventarne
uno: così `/ag-ui/status` risponde a una `getCapabilities()` senza traduzione.

**c) Il modello di interruzione (human-in-the-loop).** La catena del Forge
`code_proposal` / `code_review` / `code_verdict` (`control-plane/main.py:2427`,
con `trace_id` condiviso, `:2422-2423`) *è* già un'interruzione: proposta →
review umana → verdetto. AG-UI le dà una forma standard:

- esito: `RUN_FINISHED.outcome = {"type":"interrupt","interrupts":[...]}`,
  oppure `{"type":"success"}`;
- l'interruzione: `{id, reason, message?, toolCallId?, responseSchema?,
  expiresAt?, metadata?}`, con `reason` categorico (`tool_call`,
  `input_required`, ...);
- la ripresa: una **nuova** run con
  `RunAgentInput.resume[] = [{interruptId, status, payload}]`, dove `status` è
  `resolved` o `cancelled`; con `approveWithEdits` dichiarato, `payload` porta
  anche `editedArgs`.

Il punto che ci riguarda davvero è che **l'audit trail è il protocollo
stesso**: `TOOL_CALL_ARGS` (la proposta) → `resume[].payload.editedArgs` (le
modifiche umane) → `TOOL_CALL_RESULT` (l'esito). Abbiamo già quelle righe nel
log; AG-UI dà loro una busta interoperabile invece di un formato nostro.

**d) `metadata.traceId`.** Il `trace_id` attraversa già `push_log`
(`control-plane/main.py:2438`, che ne genera uno nuovo solo se non gliene passi
uno) e la catena del Forge. AG-UI indica *un trace id* come uso previsto di
`metadata`: la mappatura è diretta, non inventata.

## 4. Le due ricadute su Fase 3.5

La decisione non è isolata: due voci entrano nell'inventario della
[Fase 3.5](../ROADMAP.md) (§«Consolidamento e separazione Ufficio/Multimedia»)
e vanno raccolte lì, senza ri-derivarle.

1. **`code-sandbox` è una risorsa opzionale, non core.** Il container dello
   sviluppo agentico (`docker-compose.yml`) serve al profilo che fa coding: nel
   capability manifest è una risorsa di capability, non un servizio che ogni
   deployment deve avviare.
2. **La catena del Forge è una policy di approvazione.** `code_proposal` /
   `code_review` / `code_verdict` non è un tipo di log fra gli altri: è il
   punto in cui un umano autorizza un'azione. Nel manifest è una
   *approval policy*, cioè esattamente il posto in cui §3c atterra.

E una prenotazione per S4: il manifest riserva i campi già nella forma di
AG-UI, così il passaggio da `<<CAP>>_ENABLED` a «il coworker è
configurazione» è **additivo** e non una riscrittura. In concreto: `tools`,
`humanInTheLoop.interrupts`, `humanInTheLoop.approveWithEdits`,
`multiAgent.subagents`, `transport`, `state`. Il concetto di prodotto
«coworker» corrisponde a `multiAgent.subagents`: non serve inventare un nome
nuovo per una cosa che il protocollo già nomina.

## 5. P1 — lo spike: un flusso, dietro un flag

**Il bersaglio è il feed di log/audit, non `/v1/chat/completions`.** Tre
ragioni:

- il feed di log **è già** la traccia di audit di quello che facciamo: i tipi
  `office`, `intimate`, `mcp` e la catena del Forge sono in `LOG_TYPES`
  (`control-plane/main.py:2418-2436`);
- oggi è **interrogato in polling** — `GET /logs` (`:6769`) risponde con
  `db.query_logs(...)` (`:6777`, `shared/db.py:130`) e la dashboard fa
  `fetch('/logs?...')`. Nessun consumatore interpreta un *framing*: cambiare
  il modo di leggere il log ha un raggio d'azione quasi nullo;
- un solo adattatore copre Forge, MCP, ufficio e diario.

Lo stream di chat resta **fuori** da P1: è una linea vitale per webui, ComfyUI
e i nodi, e porta i commenti più delicati del repo sui header hop-by-hop
(`control-plane/main.py:2399-2405`: impostarli a mano produce header duplicati
e stream troncati). Diventa l'estensione P1-b, quando `shared/ag_ui.py` esiste
già e l'emettitore è collaudato.

I file toccati:

| File | Cosa |
|---|---|
| `shared/ag_ui.py` | nuovo, puro, **zero dipendenze**: tabella `EventType`, `encode(event) -> bytes`, `project_log_row(row) -> event \| None` |
| `control-plane/main.py` | additivo: `AG_UI_ENABLED` fail-closed, `GET /ag-ui/events` (SSE), `GET /ag-ui/status` |
| `.env.example` | la voce in fondo al blocco, con il default e la nota che `false` = nessun endpoint |
| `tests/test_ag_ui.py` | nuovo |

Le guardie da copiare esistono già in casa, e sono queste:

- **flag fail-closed a livello di modulo**, esattamente come
  `OFFICE_BRIDGE_ENABLED` (`control-plane/main.py:175`);
- **guardia di route con 503 e motivo esplicito**, come
  `control-plane/main.py:3205-3207`;
- **endpoint di stato che espone `enabled`**, come `:3318`, sul modello di
  `/office/status` (`:3313`), `/sandbox/status` (`:5606`), `/mcp/status`
  (`:6759`);
- **la risposta SSE** è `Response(stream_with_context(gen),
  headers=_sse_headers())`, come le due che esistono già (`:6439`, `:7417`),
  con i header da `_sse_headers()` (`:2396`).

**Un vincolo concreto trovato leggendo il DB.** `shared/db.py:130`
`query_logs()` non ha un parametro `after_id` e ordina `ORDER BY id DESC LIMIT
? OFFSET ?`: per *seguire* il log serve un cursore monotòno. `insert_log`
(`shared/db.py:120`) garantisce un `id` crescente, quindi P1 aggiunge un
parametro additivo `after_id: int = 0` — con default 0 il comportamento di
oggi non cambia — oppure una query dedicata.

I test, in quattro gruppi:

1. **mappatura pura**: fixture di righe di log → eventi attesi;
2. **encoding esatto**: i byte prodotti, con l'omissione dei campi opzionali
   non valorizzati;
3. **non-regressione a flag spento**: gli stream esistenti restano
   **byte-identici**, e il test di accettazione `sys.modules` di S4 resta verde;
4. **conformità opzionale**: se `ag_ui.core` c'è, gli eventi emessi si
   validano contro i suoi tipi; se non c'è, il test si salta
   (`skipTest`) invece di fallire.

Si eseguono come tutto il resto:
`PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py'` — è
`PYTHONPATH=.` che rende importabile `shared.*`.

Prima di scrivere `shared/ag_ui.py` si **congela l'insieme degli eventi**
leggendolo dalla specifica: nessun tipo inventato, nessun nome ricordato a
memoria. È il passo che rende il gruppo 4 possibile.

## 6. Non-obiettivi

Sono la parte più utile del documento, perché è qui che la cosa smette di
crescere.

- **Non è un framework agentico.** Non eseguiamo tool, non aggiungiamo un
  reasoning loop, non aggiungiamo un endpoint di *run*. AG-UI qui è un
  **formato di uscita** per dati che già produciamo.
- **Nessun cambio a `/v1/chat/completions`** in P1: lo stream di chat resta
  esattamente quello di oggi.
- **Nessun container nuovo, nessuna porta nuova, nessuna dipendenza di runtime
  nuova, nessuna tabella nuova.** `ag-ui-protocol` non entra in
  `control-plane/requirements.txt`: al più è una dipendenza **di test**
  opzionale, e se entra si annota in `THIRD-PARTY-NOTICES.md`.
- **Nessuna riscrittura del frontend.** `dashboard.html` resta JS vanilla; un
  client React è fuori scope, e resta fuori anche se in futuro servisse.
- **A flag spento, nessuna differenza osservabile**: gli stream esistenti
  devono restare byte-identici, ed è un test, non una promessa.
- **Non adottiamo un'applicazione esistente come base** (§2).

Il confine è deliberato: il giorno in cui servisse *un agente che agisce*, non
sarebbe l'evoluzione di questo documento — sarebbe un'altra decisione, con un
altro documento.

## 7. Rischi e guardie

**Scope slip: da «formato di eventi» a «framework agentico».** È il rischio
principale, perché è la direzione in cui la cosa vorrebbe crescere.
*Guardia:* i non-obiettivi di §6; il tema si riapre solo con un documento
nuovo, non allargando questo.

**Deriva della specifica.** La 1.0 è la prima release con uno schema, ma i
pacchetti TypeScript e i client di riferimento sono molto più giovani.
*Guardia:* la versione della specifica è annotata qui, l'insieme degli eventi
si congela prima di scrivere il modulo, e il test di conformità (gruppo 4) si
attiva quando `ag_ui.core` c'è.

**Costo del tail su un DB in polling.** SSE servito da polling resta economico
solo se la query è limitata. *Guardia:* **misurare, non presumere** — filtro
lato server per `type_`, `per_page`, cursore su `id`, e chiusura del generatore
alla disconnessione del client.

**Emettere male un tipo noto.** Un lettore 1.0 *salta* un tipo di evento che
non conosce, ma non perdona un evento malformato. *Guardia:* i test
byte-esatti (gruppo 2); aggiungere tipi dopo è la parte economica, emetterli
storti no.

Il costo di questa decisione, oggi, è zero: nessun codice di runtime, e questo
documento è l'unico artefatto. Il costo della P1 è quello di un flag spento.

## Fonti

Le verifiche di §1 e §2 vengono da qui, e sono le stesse da rileggere quando si
congela l'insieme degli eventi (§5). Le pagine dei concetti esistono anche in
versione markdown, aggiungendo `.md` all'URL.

- **SDK Python**: `https://pypi.org/pypi/ag-ui-protocol/json` — versione,
  licenza e `requires_dist`.
- **Eventi**: `https://docs.ag-ui.com/concepts/events`.
- **Interruzioni**: `https://docs.ag-ui.com/concepts/interrupts`.
- **Capability**: `https://docs.ag-ui.com/concepts/capabilities`.
- **Migrazione a 1.0** (compatibilità e regole sui campi opzionali):
  `https://docs.ag-ui.com/migrating-to-1-0`.
- **Indice completo** della documentazione: `https://docs.ag-ui.com/llms.txt`.
- **Maturità dei client**: API GitHub su `CopilotKit/OpenBot` e
  `CopilotKit/OpenDots` — data di creazione, numero di commit, issue aperte.
