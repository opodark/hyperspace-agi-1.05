# Missione PDF con Bonsai 2 27B (prova del 2026-10-08)

Data: 2026-10-08. Obiettivo: ripetere la prova del
[7 ottobre](mission-pdf-trial-2026-10-07.md) — Mission Control legge la
documentazione del repository e ne fa un PDF — sostituendo i modelli 8B con
**Bonsai 2 27B** servito *fuori* da Ollama. Questo documento registra anche i
passi e i workaround che sono serviti a farla girare su una macchina da 16 GB:
quelli sono il risultato più riutilizzabile della giornata.

Hardware della prova: MacBook Air M5, **16 GB** di memoria unificata, macOS.
Modello: `Ternary-Bonsai-2-27B-PTQ1_0` (fork `llama-server` di PrismML, endpoint
OpenAI-compatibile su `127.0.0.1:8080`).

## Esito

**Un PDF vero è stato prodotto e il collo di bottiglia non è più la qualità del
modello.** Missione `mission-831a8cb16a064ebe` (avvio 11:02Z, **872 s**):
`artifacts/docs-briefing.pdf` + `make_briefing.py` (137 righe, reportlab) nello
stesso workspace della sandbox.

| Verifica | Esito |
| --- | --- |
| task `coder` | `pass` |
| task `verifier` | `pass` (azione sandbox `inspect`: `magic_ok`, pagine, testo) |
| gate indipendente dal modello | `%PDF-1.3`, **1 pagina, 549 caratteri** estraibili con `pypdf`, 2.107 byte |
| verdetto di **missione** | **`fail`** — difetto del prompt del verifier, poi corretto (difetto 2) |

Il verdetto di missione sbagliato non era un difetto del modello: il verifier di
missione riceveva un digest **senza artifact** e ha risposto «no PDF file was
generated» su un PDF che esisteva. Con il digest corretto la catena task →
artifact → verifica → verdetto è continua.

Restano due cautele da non dimenticare: il piano era ristretto a un coder e il
PDF è un briefing di **una pagina**; questa prova dimostra la catena, non
l'autonomia del planner.

### Il workspace è stato perso (lezione operativa)

Il volume `hyperspace-agi-104_sandbox_workspaces` è stato svuotato con un
`clear_ws` alle 12:17. Il PDF è sopravvissuto **solo** perché le copie erano
state estratte prima, in `/tmp/docs-briefing.pdf` e
`~/Downloads/docs-briefing.pdf` (MD5 `687c6a1816644731c851acd63a1d6cc9`).
Da qui una regola: prima di qualunque pulizia dei workspace, copiare fuori gli
artifact che si vogliono conservare. Il volume è un runtime usa-e-getta, non un
archivio.

## Il backend: ricetta riproducibile

Lo script di avvio è `/tmp/start_bonsai.sh`; i pesi ufficiali stanno in
`/Users/opo/models/bonsai2-27b-gguf/`. La configurazione che ha prodotto il PDF:

```bash
llama-server \
  -m ~/models/bonsai2-27b-gguf/Ternary-Bonsai-2-27B-PTQ1_0.gguf \
  --host 127.0.0.1 --port 8080 \
  -c 16384 -ub 512 \
  --reasoning-budget 0 --reasoning-format none \
  --chat-template-kwargs '{"enable_thinking": false}'
  # nessun proiettore vision (mmproj): non serve alla missione e costa memoria
```

Ogni pezzo ha una ragione misurata, non una preferenza:

| Opzione | Perché |
| --- | --- |
| `-c 16384` (o 12288) | È la variabile da scegliere contro la memoria **libera in quel momento**: vedi la tabella qui sotto. Il contesto che serve è *prompt del loop + output*, non il massimo del server. |
| `-ub 512` | Riduce il batch di prefill: picchi di memoria più bassi. È il flag che ha reso sostenibile `-c 12288` su 16 GB. |
| `--reasoning-budget 0 --reasoning-format none --chat-template-kwargs '{"enable_thinking": false}'` | Il modello **ignora `/no_think`**. Se il thinking non viene spento all'avvio, ogni passo del tool loop rigira i token di ragionamento e gonfia il contesto fino a far saltare la richiesta. |
| nessun `--mmproj` | Il proiettore vision non entra in nessun manifest di missione: è memoria spesa per niente. |

### Le configurazioni provate (16 GB, misure del 2026-10-08)

| ctx | `-ub` | KV | Esito osservato |
| --- | --- | --- | --- |
| 16384 | 512 | f16 | OOM su un prompt da ~9,7k token con tool (due documenti nel contesto) |
| 8192 | 512 | f16 | Il server regge, ma il contesto del worker (9.206 token) non ci sta: `request exceeds the available context size` |
| 12288 | 512 | f16 | **Ha prodotto il PDF**; OOM dopo ~30 min di sessione |
| 12288 | 512 | 4 bit (`BONSAI_KV4=1`) | **Non è la risposta**: sul prefill si crolla da ~90 a ~12 tok/s e il decode scende a 0,05 tok/s |

Altri numeri utili: pesi **5,5 GiB**; decode reale **5,5–7 tok/s**; una tool call
corta ~28 token, uno script 1,5–4k token. L'OOM Metal arriva come
`Insufficient Memory (kIOGPUCommandBufferCallbackErrorOutOfMemory)` e poi il
server resta in `Compute error` finché non lo si riavvia.

**Due trappole di processo, non di modello:**

- `pkill` da solo **non** termina sempre `llama-server`. Due server vivi sulla
  stessa porta = OOM immediato. Serve `pkill -9`, un'attesa e una verifica con
  `pgrep` prima di rilanciare.
- Con il 27B caricato, liberare RAM chiudendo `hyperspace_open_webui` e
  `hyperspace_libretranslate` per la durata della prova è stato necessario, e i
  due container vanno **riavviati dopo** (nel 2026-10-08 è stato fatto).

## I quattro difetti trovati nel codice e corretti

Tutti e quattro sono bug del control plane, invisibili con i modelli 8B e
messi a nudo da un modello servito fuori da Ollama. Tutti hanno un test.

| # | Sintomo | Prova | Correzione |
| --- | --- | --- | --- |
| 1 | Gli agenti della missione **non potevano usare i tool**: `_run_tool_loop` li toglieva e faceva una completion semplice | feed: `tool_loop: model=bonsai2-27b tools=False` | `_model_supports_tools` (`cp/model_caps.py`) non conosceva `bonsai*`: aggiunto via `TOOL_CAPABLE_MODELS=bonsai` (l'override si **aggiunge** ai pattern di default, non li sostituisce) |
| 2 | Il **verdetto di missione giudicava senza prove** | `fail` con «no PDF file was generated or verified» su un PDF esistente | `_mission_task_digest` (`control-plane/main.py`) porta anche i `changed_files`; il prompt di missione riporta l'esito del gate PDF («checked by the runner, not by a model») |
| 3 | La **temperatura non arrivava al backend**: il planner girava col sampling del server (temp 1.0) invece di 0.2 e a volte rispondeva senza JSON → `invalid plan` | la temperatura viaggia in `options`, forma nativa Ollama, che un endpoint OpenAI-compatibile ignora | `Invocation.model_payload` (`shared/tool_runtime.py`): la temperatura va anche nel campo di primo livello |
| 4 | **Nessun modo di puntare la missione a un backend non-Ollama** | l'unico endpoint era `advanced_config["ollama"]["url"]` | `MISSION_INFERENCE_URL` + helper `_mission_inference_base`; vuota = comportamento di prima |

Il difetto 3 è quello da ricordare: **il contratto OpenAI-compatibile non è il
contratto Ollama**, e un campo che viaggia nella forma sbagliata non dà errore,
dà silenziosamente un comportamento diverso.

## I workaround adottati, in ordine di utilità

1. **`MISSION_INFERENCE_URL`** per deviare solo planner/worker/verifier, senza
   toccare chat e canali: si prova un backend nuovo senza rischiare il resto
   dello stack.
2. **`TOOL_CAPABLE_MODELS` / `REASONING_MODELS`** per dichiarare le proprietà di
   un modello che i pattern non conoscono, invece di toccare il codice.
3. **Temperature nel payload, in entrambe le forme** (`options` per Ollama,
   primo livello per OpenAI-compatibile): difesa contro il punto 3 sopra.
4. **Digest con `changed_files` + esito del gate** nel prompt del verifier di
   missione: un verifier che non vede l'artifact non verifica, indovina.
5. **`MISSION_MAX_TOKENS_PER_TASK` 4096 → 8192**: una sola generazione del 27B ha
   bruciato 3.953 token. Con il 27B il default da 8B è un vincolo che si tocca
   subito.
6. **Thinking spento all'avvio del server** (non nel prompt): è l'unico modo
   perché il tool loop non riempia il contesto di ragionamento.
7. **Ctx scelto per finestra di memoria** (16384 se libera, 12288 come piano B) e
   `-ub 512`.
8. **Prima di una missione lunga**: chiudere i container non indispensabili,
   verificare che non ci siano `llama-server` orfani, e controllare i workspace
   liberi (`SANDBOX_MAX_WORKSPACES`) e il disco.
9. **Copiare fuori gli artifact appena la missione finisce**, prima di qualunque
   pulizia del volume.

## Config lasciata accesa (`.env`, non tracciata)

```dotenv
MISSION_INFERENCE_URL=http://host.docker.internal:8080
MISSION_MODEL=MISSION_PLANNER_MODEL=bonsai2-27b
REASONING_MODELS=bonsai
TOOL_CAPABLE_MODELS=bonsai
MISSION_MAX_TOKENS_PER_TASK=8192
```

Per tornare a Ollama: svuotare `MISSION_INFERENCE_URL` e rimettere i due modelli
8B.

## Limiti della macchina — quello che con 16 GB non si ottiene

- Il tetto pratico è **ctx ~12k**: il caso «due documenti nel contesto» (un
  briefing che legge più di una fonte) **non regge**. Il PDF prodotto è un
  briefing di una pagina da `docs/mission-control.md`.
- La finestra utile è di **~30 minuti**: dopo, Metal OOM e il server va
  riavviato. Una missione da più task lunghi non entra in una finestra sola.
- **Un solo modello grande per volta**: nessuna concorrenza, quindi
  `MISSION_MAX_CONCURRENCY` resta a 1 di fatto.
- **872 s per una missione minima** a 5,5–7 tok/s: accettabile in prova, non come
  servizio.

Conclusione: il modello giusto c'è, la macchina no. Il seguito è
[distributed-inference.md](distributed-inference.md).

## Verifica

Suite del repository con il `.venv` del repo: **3 failed, 2218 passed, 17
skipped, 919 subtest**. I 3 fallimenti sono i già noti e fuori perimetro
(`licensing` per i file cancellati non committati, colori Anna, manifest SD15).
Nessuna regressione introdotta dai quattro fix.

Nessun commit e nessun push sono stati fatti.
