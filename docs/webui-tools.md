# Tool HyperSpace in Open WebUI

## Creare un nuovo tool

Da questa repository:

```bash
python scripts/webui_tool.py new nome_tool
```

Il comando crea `shared/webui_custom_tools/nome_tool.py`. Modifica **quel solo
file**: scrivi una descrizione nella docstring e implementa la funzione. Sono
supportati argomenti `str`, `int`, `float`, `bool` e `list[...]`; il risultato
deve essere JSON serializzabile. Il nome della funzione diventa il nome del tool.

```bash
python scripts/webui_tool.py publish
```

`publish` rifiuta i template ancora da completare, valida gli schemi, ricostruisce
il control plane e riavvia WebUI per aggiornare la cache OpenAPI. Non serve
modificare a mano le route, il JSON OpenAPI o la configurazione di WebUI. Per
validare senza pubblicare: `python scripts/webui_tool.py check`.

Le funzioni Python dei tool sono codice fidato eseguito nel control plane:
conserva i file in questa repository e non caricare codice ricevuto da terzi
senza revisione.

## Connessione già installata

La connessione OpenAPI `HyperSpace Files` è registrata automaticamente all'avvio
di Open WebUI da `webui-tools-register`. Il server è il control plane su
`http://control-plane:8085/webui-tools/openapi.json`. La registrazione conserva
le altre connessioni configurate in WebUI e aggiorna solo `hyperspace-files`.

`WEBUI_TOOLS_TOKEN` in `.env` è una credenziale dedicata: il control plane
rifiuta le chiamate ai tool senza il suo Bearer token. Il token compare anche
nella connessione persistente di WebUI; non serve incollarlo nella chat.

Operazioni disponibili:

- elencare, leggere e creare file UTF-8 in `/Users/opo/hyperspace_share`;
- elencare i nomi delle immagini in `ComfyUI-Shared/output/HyperSpace`;
- copiare immagini già esaminate in `Anna_selezionate` o `Anna_da_rivedere`.
- avviare la selezione visiva automatica di tutte le immagini di Anna e leggerne
  l'avanzamento tramite `start_anna_visual_selection` e
  `anna_visual_selection_progress`.
- avviare `start_anna_second_pass` per ricontrollare più rapidamente, con un
  solo esame visivo a 768 px, i file `da_rivedere` o in errore del primo passaggio.
  Il progresso è in `anna_second_pass_progress`; le sole promosse sono copiate
  in `Anna_secondo_passaggio_selezionate`, senza modificare le cartelle precedenti.
- accodare scene Anna con `generate_anna_batch`, senza importare un tool Python
  né configurare Valves. Usa l'operatore in `CHANNEL_OPERATOR`; se ce n'è più
  di uno, imposta `WEBUI_ANNA_BATCH_AUTHOR`.

Per richieste lunghe scegli invece il modello **Anna Batch diretto** nel menu
dei modelli di WebUI e incolla un elenco con una scena per riga (`1. ...`,
`2. ...`, fino a 50). Questo percorso non aspetta che un LLM interpreti il
testo: invia le scene al medesimo endpoint batch, con gli stessi controlli, e
restituisce ID accettati ed eventuali rifiuti. Righe non numerate non sono
inviate; oltre 50 righe l'intero invio viene respinto. Non ritentare un invio
scaduto prima di aver controllato il monitor attività, per evitare duplicati.

Anna Batch riconosce alcune pose del corpo nel testo della scena (in piedi,
seduta, inginocchiata, sdraiata, in cammino, in danza, braccia aperte) e le
passa al ControlNet OpenPose del modello SD 1.5. Le pose precise di mani e dita
non hanno un preset: per vincolarle si può usare una foto di posa dedicata.
Caricala una volta nella cartella input di ComfyUI e usa il nome stampato dal ponte:

```bash
python integrations/comfyui/comfy_bridge.py --stage-posa ./mia-posa.jpg --nome-posa posa-anna-01.jpg
```

In **Anna Batch diretto**, la posa si dichiara sulla riga interessata:

```text
1. [pose=posa-anna-01.jpg] [strength=0.9] Anna seduta, figura intera
2. Anna in piedi, figura intera
```

La seconda riga continua a usare il preset dedotto dal testo. Il tool OpenAPI
`generate_anna_batch` accetta anche un oggetto per scena, per esempio
`{"scene":"Anna seduta","pose_image":"posa-anna-01.jpg","pose_strength":0.9}`.
Nel vecchio tool Python importabile la stessa lista si passa a
`genera_anna_batch_con_pose`.
L'esito mostra `pose_mode`: `image` se la foto entra in DWPose (mani incluse),
`preset` per uno dei sette scheletri semplici, `text` quando la posa resta solo
nel prompt. La foto deve mostrare chiaramente una sola persona e le mani; DWPose
non può ricostruire dita fuori inquadratura o nascoste. Non basta aumentare il
numero di passi o usare il fix 2× per correggere arti già generati male.
- aprire `show_hyperspace_activity` per una console di sola lettura nella chat:
  selezione Anna, secondo passaggio e coda immagini si aggiornano ogni tre secondi. Il monitor
  scade dopo 12 ore; richiamare il tool per aprirne uno nuovo. Nessun comando
  shell è disponibile. Il browser deve raggiungere la porta 8085 del Mac; se
  WebUI usa un proxy diverso, imposta `WEBUI_MONITOR_PUBLIC_URL` all'URL
  pubblico del control plane.

Per vedere **Anna Batch senza configurare un Terminale** c'è anche il monitor
sempre disponibile in `http://127.0.0.1:8085/activity`. Il Desktop HyperSpace
ha un riquadro **Attività Anna Batch** e la schermata iniziale di Open WebUI
mostra un banner con il link diretto. La pagina aggiorna coda e ultimi job ogni
tre secondi e mostra un terminale di eventi di stato. I pulsanti Start/Stop
controllano separatamente la coda immagini, la selezione Anna e il secondo
passaggio: richiedono `WEBUI_TOOLS_TOKEN` nel campo della pagina (tenuto solo in
memoria nel browser). Stop mette in pausa i nuovi job; un render o un'analisi
già avviati terminano prima della pausa. Start riprende i job rimasti. Lo stato
della pausa sopravvive al riavvio del control plane. La vista pubblica non espone
prompt, percorsi dei file o credenziali.
- preparare con `prepare_reel_project` un progetto per il Reel Editor: da nomi
  esatti di immagini Anna già approvate (`source="anna"`) oppure da file nella
  radice di `hyperspace_share` (`source="share"`). Il tool copia massimo 30
  media in `hyperspace_share/reel-projects/`; non genera né pubblica il video.
  Il progetto è selezionabile nell'editor locale.
- convertire in Markdown un documento d'ufficio già in `hyperspace_share` con
  `converti_documento_markdown`: Word, PowerPoint, Excel, OpenDocument, RTF,
  EPUB, CSV e PDF. Il tool scrive il `.md` accanto al documento (rifiuta di
  sovrascrivere senza `sovrascrivi=true`) e restituisce un'anteprima limitata a
  `anteprima_caratteri` caratteri, senza inviare il file altrove. Richiede il
  pacchetto `firecrawl-anydoc` nell'immagine del control plane, già in
  `control-plane/requirements.txt`; se manca, il tool risponde con un errore che
  dice cosa installare. La skill testuale equivalente è importabile dal Forge
  (`docs/tool-skill-forge.md`).
- classificare un PDF già in `hyperspace_share` con `classifica_pdf`: dice se è
  testo nativo, scansione, immagini o misto, con una confidenza e l'elenco
  (numeri di pagina 1-based) delle pagine senza testo estraibile, così si manda
  all'OCR solo ciò che serve invece di ogni PDF. Legge il file in locale con la
  libreria `pdf-inspector` (Firecrawl): non esegue OCR, non scarica modelli e non
  tocca la rete. Con `estrai_markdown=true` restituisce anche un'anteprima
  limitata a `anteprima_caratteri` caratteri. Richiede il pacchetto
  `pdf-inspector` nell'immagine del control plane, già in
  `control-plane/requirements.txt`; se manca, il tool risponde con un errore che
  dice cosa installare. Il catalogo testuale Firecrawl è importabile dal Forge
  (`docs/tool-skill-forge.md`).

- leggere scansioni con `leggi_documento_ocr`: PDF o PNG/JPEG/WebP inviati
  all'endpoint Unlimited-OCR/vLLM configurato dall'operatore. Selezione di
  massimo 16 pagine, anteprima limitata e output `.ocr.md` senza sovrascrittura.
  Configurazione e limiti in [unlimited-ocr.md](unlimited-ocr.md).

La lista dei nomi non è un'analisi visiva. Il tool di selezione invece manda
ogni immagine al modello visivo locale, copia quelle senza difetti visibili in
`Anna_selezionate` e mette immagini dubbie o difettose in `Anna_da_rivedere`.
La chiamata avvia un lavoro in background: solo lo stato `completed` indica che
ha esaminato tutti i file. `completed_with_errors` segnala file non classificati,
che restano nella cartella originale; richiamare il tool ritenta gli errori.
Gli originali non vengono spostati né eliminati. Il dettaglio per file è salvato
in `data/control-plane/anna-selection.json`.
Il modello locale configurato con `ANNA_REVIEW_MODEL` deve avere la capability
`vision`; su questo Mac è `qwen3-vl:4b-instruct`. Un secondo controllo esamina
le immagini che il primo passaggio vorrebbe promuovere. La selezione resta una
valutazione automatica: i casi dubbi vanno rivisti manualmente.

Le operazioni si aggiornano nel server del repository: non serve più importare
singoli file Python in Workspace → Tools. Il filtro `anna_tool_filter` già
installato aggiunge automaticamente `server:hyperspace-files` alle chat Gemma
previste dal filtro. Negli altri modelli, attiva il server dalla chat in
Integrations → Tools. Il servizio di registrazione aggiorna il
filtro solo se è la versione gestita dal repository, preservando eventuali
personalizzazioni manuali. I vecchi tool Python restano disponibili finché
non vengono rimossi dalla WebUI.
