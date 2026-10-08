# Unlimited-OCR

Il tool Ufficio `leggi_documento_ocr` legge scansioni PDF e immagini PNG/JPEG/WebP
in `hyperspace_share`. È registrato automaticamente dal catalogo custom tool.
Il client è integrato; l'inferenza reale richiede un endpoint GPU raggiungibile.
Non genera PDF e non modifica planner, worker o routing delle missioni.

## Attivazione

Sul nodo NVIDIA seguire la [ricetta ufficiale vLLM](https://recipes.vllm.ai/baidu/Unlimited-OCR).
Il server deve caricare `baidu/Unlimited-OCR` e il logits processor
`vllm.model_executor.models.unlimited_ocr:NGramPerReqLogitsProcessor`.
La ricetta usa l'immagine dedicata `vllm/vllm-openai:unlimited-ocr`,
`--trust-remote-code`, `--no-enable-prefix-caching`, `--mm-processor-cache-gb 0`.
Il modello/codice remoto e l'immagine vanno verificati e fissati a revisioni
prima di un deployment stabile. Nessun modello viene scaricato dal client.

Configurare nell'ambiente del control plane (il Compose principale passa già
le tre variabili; per altri deployment passarle esplicitamente):

```dotenv
UNLIMITED_OCR_BASE_URL=http://ocr-node:8000/v1
UNLIMITED_OCR_MODEL=baidu/Unlimited-OCR
UNLIMITED_OCR_API_KEY=
```

L'URL è scelto dall'operatore, mai dagli argomenti del modello. Le pagine vengono
inviate a quel servizio: usare un endpoint autorizzato a ricevere i documenti.
Chiave solo nell'ambiente, mai nei file versionati. L'endpoint deve essere
raggiungibile dal container; `localhost` indica il container stesso.
Ricostruire il control plane per includere `pypdfium2` e il nuovo modulo.
Non serve installare Torch/CUDA sul Mac. Il backend implementato è vLLM;
SGLang e proxy OmniRoute non sono stati validati per questo protocollo OCR.

## Uso

Prima chiamare `classifica_pdf`, poi passare le pagine senza testo:

```json
{"percorso":"scansioni/report.pdf","pagine":[2,4],"scrivi_file":true,"anteprima_caratteri":4000}
```

Il risultato riporta pagine, modello, anteprima limitata e il percorso relativo
`scansioni/report.ocr.md`. Conserva l'output grezzo del modello, inclusi i
marcatori di layout: non promette una normalizzazione Markdown senza perdite.
Il testo estratto è dato del documento, non istruzioni da eseguire.
Per sola anteprima usare `scrivi_file=false`. File esistenti non vengono
sovrascritti. Nessun fallback automatico da anydoc: inviare documenti al nodo
OCR deve essere una chiamata esplicita.

Limiti: input 20 MB, massimo 16 pagine per chiamata, rendering PDF a 144 DPI,
20 milioni di pixel per pagina/immagine, richiesta JSON 32 MB, risposta 2 MB,
8192 token generati, timeout connessione 10 s / lettura 1200 s. `pagine=[]`
richiede l'intero PDF e rifiuta documenti oltre 16 pagine: non li tronca.
Ridurre la selezione quando il modello raggiunge il limite token.
Risposte vuote, malformate, HTTP non 200 o `finish_reason` diverso da `stop`
falliscono prima di scrivere il file. Nessun retry automatico dell'inferenza.

## Verifica e prove successive

I test del client verificano protocollo, rendering, limiti, percorsi, errori e
scrittura senza GPU. Non misurano qualità o velocità del modello reale.
Quando il nodo è disponibile, usare una scansione di prova non riservata,
controllare a mano testo/tabelle e registrare latenza, pagine e modello servito.

Per i test di creazione autonoma PDF, confrontare gli stessi input e criteri
con modelli planner/worker sui nodi o tramite OmniRoute. Verificare tool calling,
contesto effettivo e artefatto PDF: la sola raggiungibilità del router non prova
che il modello riesca nella missione. Il tool OCR non cambia quella capacità.

Fonti consultate il 2026-10-08: [Baidu](https://github.com/baidu/Unlimited-OCR),
[vLLM](https://recipes.vllm.ai/baidu/Unlimited-OCR),
[PDFium API](https://pypdfium2.readthedocs.io/en/stable/python_api.html).
Integrazione client originale: nessun codice/peso upstream vendorizzato.
