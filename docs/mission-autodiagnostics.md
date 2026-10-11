# Mission Control — autodiagnostica

Usare `scripts/diagnostics/mission_health.py` per raccogliere una fotografia
sola-lettura del Control Plane, di Mission Control, del mesh e dei modelli
caricati in Ollama. Lo script non avvia, annulla o modifica missioni e non stampa
token.

```bash
DREAM_REVIEW_TOKEN="$DREAM_REVIEW_TOKEN" \
MISSION_INFERENCE_URL="$MISSION_INFERENCE_URL" \
OLLAMA_URL="$OLLAMA_URL" \
python scripts/diagnostics/mission_health.py
```

Le variabili sono opzionali tranne il token per leggere le rotte `/missions*`.
`HYPERSPACE_CP_URL` imposta il Control Plane (default `http://127.0.0.1:8085`);
si possono usare anche `--base`, `--inference-url`, `--ollama-url` e `--timeout`.

## Lettura dei risultati

- `running=true` indica che il lock del motore è occupato; verificare anche
  `/missions/status`, la missione più recente e i log `type=mission`.
- Missioni ferme in passato e nessuna richiesta attiva indicano che il rilancio
  potrebbe non essere arrivato a questo Control Plane.
- `MISSION_INFERENCE_URL` non raggiungibile indica un problema di endpoint o
  rete, anche se il CP e il nodo appaiono sani.
- `active_requests=0` e `queued_requests=0` descrivono solo la coda del nodo; la
  prova `/api/ps` dice se Ollama ha modelli caricati in quel momento.
- `vram_gb=0` può significare che il nodo non dichiara il dato; non misura la RAM
  libera dell'host.
- Un errore di autenticazione sulle rotte missione richiede
  `DREAM_REVIEW_TOKEN` nell'ambiente dello script. Non incollare mai il token nei
  log, ticket o output condivisi.

Per il messaggio `Il Mac sta completando un'immagine`, usare
`scripts/diagnostics/image_gate.py`. Legge lo stato dell'image queue e il memory
gate senza stampare prompt o token. Per chiudere un claim specifico e stantio,
richiede `--close-stale JOB_ID`, il job deve essere ancora `running` e ComfyUI
deve risultare irraggiungibile; altrimenti rifiuta la modifica. La chiusura marca
quel job `failed` e libera il gate, senza riaccodarlo né ripetere il render.

Lo script non può stabilire da solo se la UI stia parlando a un'altra istanza;
confrontare la base URL visibile/configurata nella UI con `--base` e verificare
che i timestamp di missione siano correnti.

## Tracciare gli strumenti della chat WebUI

Le richieste inviate dalla scheda chat non sono missioni. Per ispezionare una
risposta WebUI senza stampare il testo della conversazione, usare:

```bash
python3 scripts/diagnostics/chat_tool_trace.py --contains moltbook.com
```

Lo script esamina solo le ultime 100 righe `webui_interaction` e riporta modello,
tempi, token e indicatori sintetici. Per richieste con un URL esplicito, il tool
corretto è `web_fetch`; `web_search` produce risultati di ricerca e non legge il
documento. Se il fetch non fornisce il contenuto, la risposta deve segnalare il
blocco senza sostituirlo con istruzioni generiche. Il tool loop ora applica un
gate: senza un `web_fetch` riuscito con contenuto non restituisce una completion
di prosa come se fosse basata sulla pagina.

La registrazione Moltbook è un'azione esterna distinta dalla lettura della
skill: il modello non deve mai dichiararla completata sulla base del testo
generato. Lo stato dell'account HyperSpace viene letto dal Control Plane con il
tool nativo `moltbook_status`, agganciato alle richieste Moltbook prima
dell'inferenza. La skill approvata vive nel Forge e prescrive questo tool; non
chiedere di cercare credenziali nella memoria conversazionale. Il Control Plane
legge `~/.config/moltbook/credentials.json` da un mount Docker read-only. La
chiave viene inviata soltanto a `https://www.moltbook.com/api/v1/agents/status`,
redirect rifiutati e chiave esclusa dai log. Il tool espone link e codice solo
quando lo stato verificato è `pending_claim`.

Per operazioni amministrative locali, `scripts/moltbook.py` legge prima la skill
ufficiale, registra una sola volta e salva le credenziali con permessi `0600`
(cartella `0700`). Se esiste già un file credenziali, `register` controlla solo
lo stato e non crea un duplicato.

```bash
python3 scripts/moltbook.py register --name HyperSpace --description "AI agent for the HyperSpace project"
python3 scripts/moltbook.py status
```

La registrazione restituisce un link e un codice che l'umano deve usare per il
claim. Il comando non attiva heartbeat, post, follow o commenti: sono azioni
successive e vanno predisposte solo dopo che il claim risulta `claimed`.
