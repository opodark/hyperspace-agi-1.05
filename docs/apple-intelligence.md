# Apple Intelligence sul nodo Mac

Il nodo verificato il 2026-10-09 ha Apple M5, 16 GiB di memoria, macOS 27.0.1,
SDK macOS 27 e Swift 6.4. La sonda nativa
`SystemLanguageModel.default.availability` restituisce `available`: Apple
Intelligence è già abilitata e il modello locale è disponibile.

Su richiesta dell'utente viene aggiunta una capability Apple esplicita per
compiti testuali. Il modello Apple conserva i propri guardrail: questa è
un'eccezione circoscritta alla preferenza generale di VISION.md per modelli
non censurati, non una sostituzione dei modelli o dei fallback HyperSpace.

## Esecuzione locale

Il worker Swift usa esclusivamente `SystemLanguageModel.default` tramite
Foundation Models. Riceve testo via stdin, crea una sessione nuova e restituisce
JSON. Non accede a file indicati dal modello, non esegue shell e non usa il
modello Private Cloud Compute. Il bridge Python offre CLI e MCP via stdio;
non apre porte di rete. È un componente host macOS, non eseguibile nel container
Linux del control plane.

```bash
.venv/bin/python scripts/apple_intelligence.py --build
.venv/bin/python scripts/apple_intelligence.py --check
.venv/bin/python scripts/apple_intelligence.py --prompt 'Riassumi in una frase: HyperSpace coordina modelli locali e strumenti per creare documenti verificabili.'
```

La compilazione richiede SDK/Command Line Tools con Foundation Models. Binario
e cache sono in `data/apple-intelligence/`, esclusi da git. Ricompilare dopo una
modifica al worker Swift. Il controllo di disponibilità non genera testo e non
cambia le impostazioni di macOS. Le funzioni di sistema restano gestibili nelle
Impostazioni di Sistema; le loro opzioni variano con la versione di macOS.
[Guida Apple per macOS 27](https://support.apple.com/guide/mac-help/get-started-with-apple-intelligence-mchl46361784/27/mac/27).

## Collegamento OpenWork / OpenCode

Su questo Mac è stato preparato il workspace
`data/openwork-apple-pilot/`, con `opencode.json` e istruzioni di prova.
Aprirlo come cartella di lavoro in OpenWork: i percorsi assoluti sono già
configurati, quindi in questo workspace non serve `HYPERSPACE_ROOT`.
Il workspace è escluso da git. Per altri workspace seguire la procedura sotto.

Unire il contenuto di
[`opencode.fragment.json`](../integrations/apple-intelligence/opencode.fragment.json)
al file `opencode.jsonc` del workspace di prova. Conservare le altre voci.
In OpenWork impostare `HYPERSPACE_ROOT` al percorso assoluto del repository,
qui `/Users/opo/hyperspace-agi-1.04`, e ricaricare la configurazione OpenCode.

Il bridge pubblica:

| Tool | Risultato |
|---|---|
| `apple_intelligence_status` | Disponibilità reale del modello sul Mac |
| `apple_intelligence_text` | Testo generato localmente da prompt, istruzioni opzionali e limite output |

Prima prova: chiedere di controllare lo stato, poi riassumere un paragrafo
tramite `apple_intelligence_text`. Il modello che coordina OpenWork continua
a essere quello scelto per gli agenti; può delegare compiti brevi al modello
Apple. Il collegamento nella UI OpenWork deve essere verificato dopo aver
caricato il frammento: l'esistenza dei file non equivale a una connessione attiva.

La configurazione di MCP locali e la sostituzione di variabili sono documentate
da [OpenCode MCP](https://opencode.ai/docs/mcp-servers/) e
[OpenCode config](https://opencode.ai/docs/config/).

## Limiti del primo adapter

- Testo singolo per chiamata, nessuna cronologia persistente. Riassunti,
  riscrittura ed estrazione sono casi da valutare, non benchmark già superati.
- Input massimo 64 KiB; non è una promessa di capienza del contesto del modello.
  Il framework può rifiutare prima per limite di contesto.
- Da 1 a 1024 token massimi richiesti in output, default 256; timeout 90 secondi.
- Un'inferenza alla volta per processo MCP; più client possono avviare processi
  distinti. Non c'è ancora uno scheduler globale della memoria del Mac.
- Errori, indisponibilità e guardrail restano visibili; nessun retry o fallback
  cloud automatico. Nessuna garanzia che un output testuale sia JSON valido.
- Nessuna registrazione automatica nella mesh, nessuna API `/v1` e nessun
  controllo di Siri o Image Playground tramite questo adapter.

La disponibilità del modello non prova che ogni funzione Apple Intelligence
sia configurata: lingua, regione e impostazioni delle singole app restano
separate. [Framework Apple](https://developer.apple.com/documentation/foundationmodels).

## Verifica e rimozione

```bash
.venv/bin/python -m pytest tests/test_apple_intelligence.py -q
```

I test non richiedono Apple Silicon: verificano protocollo, input, limiti,
timeout e propagazione degli errori con worker simulato. Compilazione e
inferenza sul Mac sono prove aggiuntive da riportare in AGENT-LOG.md.
Il 2026-10-09: 19 test passati, worker compilato, stato `available`, inferenza
italiana riuscita fuori dalla sandbox di sviluppo. Nella sandbox l'inferenza
restituiva un errore ModelManagerServices 1008; la disponibilità da sola non
garantisce quindi il permesso di generare dal processo chiamante.
Per scollegarlo disabilitare `hyperspace-apple` nel workspace; nessun servizio
di sistema o avvio automatico viene installato da questi comandi.
