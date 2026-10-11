# Superficie REA — analisi statica di un artefatto (strumento da banco)

`scripts/rea_surface.py` è una pagina **locale** (Flask su `127.0.0.1:7872`) che
toglie di mezzo il copia-incolla attorno a REA (`rea-agents`, MIT): si indica un
eseguibile, una libreria, una cartella o un `.asar`, si sceglie **una** delle
operazioni esposte e si legge un report ridotto. Il target non viene eseguito e
niente viene installato da qui.

Perché esiste: la prova del 5 ottobre 2026 (`docs/rea-pilot.md`) si è fatta a
mano — comando al terminale, fixture da copiare, JSON da aprire. Il risultato era
utile (un inventario con provenienza) ma il percorso era tutto manuale. Questa
superficie è la versione ripetibile di quel flusso.

## Come si usa

```bash
# cosa trova, senza avviare niente
.venv/bin/python scripts/rea_surface.py --check

# la pagina: http://127.0.0.1:7872
.venv/bin/python scripts/rea_surface.py
```

`--check` stampa il workspace, le operazioni che esporrebbe e dove sta `rea`, e
**esce con codice 1 se `rea` non c'è**, elencando i comandi di installazione. È
quello che usa `scripts/start-all-macos.sh`: la superficie parte solo se il check
passa, quindi senza REA installato resta spenta (e la dashboard la mostra fra le
superfici opzionali, in «Servizi» come le altre). Con `rea` nel PATH il check
esce 0, stampa la versione trovata e lo start script la avvia insieme al resto
(dal 9 ottobre 2026 su questa macchina: `rea` 6.1.0 in `~/.npm-global/bin`).

Se REA non è nel PATH la pagina si apre lo stesso e mostra i comandi —
`npm install --global rea-agents`, `npx -y rea-agents@latest …` oppure la prova
isolata in `/private/tmp/rea-pilot` — ma nessun lavoro parte: la pagina non
installa niente e non lancia `rea setup`.

## Cosa espone (13 operazioni)

| id | comando REA | target | argomento | provider |
|---|---|---|---|---|
| `doctor` | `doctor` | — | — | facoltativo |
| `providers` | `providers` | — | — | non serve |
| `capabilities` | `capabilities` | — | — | non serve |
| `analyze` | `analyze` | file/dir | — | facoltativo |
| `inspect` | `inspect` | file/dir | — | facoltativo |
| `analyze-js` | `analyze-javascript-application` | dir o `.asar` | — | non serve |
| `inspect-artifact` | `inspect-artifact` | contenitore | — | non serve |
| `function` | `function` | file | nome funzione | obbligatorio |
| `decompile` | `decompile` | file | indirizzo `0x…` | obbligatorio |
| `xrefs` | `xrefs` | file | indirizzo `0x…` | obbligatorio |
| `instructions` | `instructions` | file | indirizzo `0x…` | obbligatorio |
| `search` | `search` | file | testo | obbligatorio |
| `trace` | `trace` | file | testo | obbligatorio |

Il provider sta in una whitelist (`hopper`, `ghidra`, `ida`). Sulle operazioni
che aprono un motore nativo è **obbligatorio** sceglierlo: l'auto-selezione di
REA può avviare Hopper da sola (finestra e licenza) e quel percorso non è mai
stato provato.

## Cosa non espone, per scelta

- `setup`, `update`, `uninstall` — cambiano la configurazione degli agenti e
  possono proporre l'installazione di Hopper;
- `import-reference-source` — legge alberi di sorgenti arbitrari;
- `capture-process`, browser/Electron via CDP, riconciliazione runtime — sono
  esecuzione, non analisi statica: è la decisione presa in `docs/rea-pilot.md`.

## Le regole della superficie

- **solo `127.0.0.1`**: nessuna esposizione, nessun host diverso da loopback;
- **whitelist**: l'unico argv che parte è quello costruito dalla tabella qui
  sopra. Niente shell, nessun flag libero, `--json` sempre in coda;
- **nessuna esecuzione del target**;
- **l'argomento è validato** (una riga, ≤ 200 caratteri, niente `-` iniziale;
  indirizzo esadecimale o nome di funzione secondo il tipo) e passa come argv
  separato, mai concatenato;
- **il target è sempre la copia nella workspace** del job: nessun percorso
  scelto dal client arriva a REA;
- **un lavoro alla volta**, timeout al processo (default 900 s) e tetto di byte
  su stdout/stderr; upload massimo 256 MB, workspace 2 GB, 20 lavori in coda.

## Il report, in tre corsie

La pagina non promuove niente a vulnerabilità. Ogni lavoro mostra:

1. **osservato qui** — quello che misuriamo noi sulla copia del file: byte,
   `sha256`, codice di uscita, durata, troncamento;
2. **riferito da REA** — la riduzione del documento: chiavi, conteggi, digest,
   il **verdetto** del comando quando ne porta uno (`doctor` dichiara `healthy`
   e `environment_healthy`) e l'envelope d'errore tradotto (`invalid_input`,
   `unsupported_provider`, `timeout`, `unavailable`, …). Un codice di uscita
   diverso da zero **senza** envelope d'errore non viene chiamato errore: la
   corsia lo scrive e rimanda al documento (con `rea` 6.1.0 è il caso di
   `doctor`, che esce 1 quando manca il motore nativo);
3. **progresso dichiarato da REA** — la timeline dei passi `rea_progress` che
   REA scrive su `stderr` (fase, file, messaggio), nell'ordine in cui li ha
   emessi.

Sotto, i limiti fissi: nessuna vulnerabilità è confermata qui, il target non è
stato eseguito, le etichette del provider possono non descrivere il runtime
(`docs/rea-pilot.md`). Il **documento grezzo** resta scaricabile
(`report.json`, `job.json`, `stdout.json`, `stderr.log`): la riduzione sceglie
cosa mostrare, non interpreta al posto dell'operatore.

## Dove finiscono i file

Tutto sotto `data/rea/` (fuori da git, override con `REA_SURFACE_WORKSPACE`):

```
data/rea/jobs/<id>/target/      la copia dell'artefatto che REA legge
data/rea/jobs/<id>/report.json  il documento grezzo di REA
data/rea/jobs/<id>/job.json     il record del lavoro (comando, esiti, digest)
data/rea/jobs/<id>/stdout.json  la raccolta di stdout, con il flag di troncamento
data/rea/jobs/<id>/stderr.log   stderr, come raccolto
```

## Endpoint

| rotta | cosa fa |
|---|---|
| `GET /` | la pagina (HTML e JS inline, nessuna CDN) |
| `GET /health` | `{ok: true, rea: …}` per lo start script e la dashboard |
| `GET /api/status` | workspace, `rea`, operazioni, provider, limiti, comandi di installazione |
| `GET /api/operations` | la tabella delle operazioni |
| `GET /api/jobs` | l'elenco dei lavori |
| `POST /api/jobs` | accoda un lavoro (`op`, `provider`, `argomento`, `file`) |
| `GET /api/jobs/<id>` | job + report ridotto |
| `GET /api/jobs/<id>/artifact/<nome>` | uno dei quattro artefatti |

Variabili d'ambiente: `REA_SURFACE_PORT`, `REA_SURFACE_WORKSPACE`,
`REA_SURFACE_MAX_UPLOAD_MB`, `REA_SURFACE_MAX_OUTPUT_MB`,
`REA_SURFACE_MAX_WORKSPACE_MB`, `REA_SURFACE_TIMEOUT_S`, `REA_BIN`.

Due variabili non sono della superficie ma le **eredita** all'avvio, per il motore
nativo: `GHIDRA_INSTALL_DIR` e `JAVA_HOME` (sezione «Il motore nativo»).

## Il motore nativo (Ghidra 12.1.4, dal 9 ottobre 2026)

Le sei operazioni con provider obbligatorio hanno bisogno di un motore installato.
Su questa macchina ora c'è **Ghidra 12.1.4**, con quattro pezzi:

1. **La release ufficiale**, non un pacchetto di terzi: `ghidra_12.1.4_PUBLIC_20260921.zip`
   (569 649 598 byte), con lo sha256 controllato contro quello pubblicato
   (`ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db`), scompattata in
   `~/ghidra_12.1.4_PUBLIC`. REA verifica la linea `12.1.x` (build di riferimento
   12.1.4) leggendo `application.version`, e ricava i limiti del JDK da
   `Ghidra/application.properties`: `application.java.min=21`, `application.java.max`
   vuoto — cioè un JDK **21 o più recente**.
2. **Un JDK completo** (con `javac`, non solo il runtime): OpenJDK 21 da Homebrew,
   keg-only, in `/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home`.
   REA usa `JAVA_HOME` e aggiunge lui `$JAVA_HOME/bin` al `PATH`; senza quella
   variabile cerca un `java` nel `PATH` e lo considera runtime parziale. Prima
   dell'installazione sul sistema c'erano solo gli stub di Apple
   (`/usr/bin/java -version` risponde «Unable to locate a Java Runtime») e
   `/Library/Java/JavaVirtualMachines` era vuota: il pacchetto Homebrew è
   keg-only, quindi `JAVA_HOME` non è un vezzo ma la via per farlo vedere a REA.
3. **Il decompiler nativo compilato dai sorgenti**: la release ufficiale contiene
   binari di decompilazione **solo** per `linux_x86_64` e `win_x86_64` (si vede
   elencando lo zip), mentre REA pretende
   `Ghidra/Features/Decompiler/os/mac_arm_64/decompile`. I sorgenti C++ sono nel
   pacchetto e la macchina ha già gli Xcode Command Line Tools, quindi il binario
   si costruisce in un minuto:

   ```bash
   cp -R ~/ghidra_12.1.4_PUBLIC/Ghidra/Features/Decompiler/src/decompile /tmp/ghidra-decomp-build
   cd /tmp/ghidra-decomp-build/decompile/cpp && mkdir -p ghi_opt
   make -j"$(sysctl -n hw.ncpu)" ghidra_opt ARCH_TYPE= ADDITIONAL_FLAGS=-w OSDIR=mac_arm_64
   install -m 755 ghidra_opt \
     ~/ghidra_12.1.4_PUBLIC/Ghidra/Features/Decompiler/os/mac_arm_64/decompile
   ```

   `ghidra_opt` è il target che la build ufficiale installa come
   `os/<OSDIR>/decompile`; il Makefile della release è scritto per macOS x86_64,
   quindi `ARCH_TYPE=` (niente `-arch x86_64`) e `OSDIR=mac_arm_64` vanno forzati a
   mano. I parser generati (`grammar.cc`, `xml.cc`, `sleighparse.cc`…) sono già nel
   sorgente: non serve bison. Il risultato è un Mach-O arm64 di 3,2 MB.
4. **Due variabili d'ambiente**, che la superficie **eredita** e non possiede:
   `GHIDRA_INSTALL_DIR` (la radice scompattata) e `JAVA_HOME` (il JDK). Le esporta
   `scripts/start-all-macos.sh` solo se i percorsi esistono; cambiandole va
   riavviata la superficie, perché le legge all'avvio.

Verifica del motore, senza avviare analisi:

```bash
GHIDRA_INSTALL_DIR=~/ghidra_12.1.4_PUBLIC \
JAVA_HOME=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  rea doctor --json
```

Con l'installazione a posto il provider `ghidra` risulta disponibile con **otto
controlli su otto** (`configuration`, `platform`, `architecture`, `installation`,
`version`, `headless`, `native_decompiler`, `java`) e versione `12.1.4`.

### Le sei operazioni native, provate davvero

Su un Mach-O arm64 di prova (33 792 byte, compilato con `clang -O1 -g`, con
`_parse_input` e `_main`), attraverso questa superficie, il 9 ottobre 2026:

| op | argomento | esito | durata | cosa è tornato |
|---|---|---|---|---|
| `function` | `_parse_input` | completato | 5,8 s | procedura a `0x100000460`, corpo 48 byte, provenienza `ghidra-function-manager` |
| `decompile` | `0x100000460` | completato | 5,0 s | pseudocodice di `_parse_input` |
| `xrefs` | `0x100000460` | completato | 4,8 s | `["0x1000080a0"]` |
| `instructions` | `0x100000460` | completato | 4,8 s | corpo della procedura (48 byte) |
| `search` | `ciao` | completato | 4,8 s | la stringa a `0x100000504` |
| `trace` | `ciao` | completato | 4,7 s | workflow composto da REA (`provider.id` = `rea-workflow`), `raw_result` nullo |

Due cose da sapere quando si legge il risultato:

- su Mach-O **i nomi delle procedure in Ghidra portano l'underscore del simbolo**:
  la funzione si chiama `_parse_input`, non `parse_input`. Con il nome sbagliato REA
  risponde `invalid_request` e il motivo puntuale sta in
  `details.issues[].reason = invalid_value` del documento grezzo, non nella
  spiegazione generica della superficie (che resta «percorso, formato o
  argomento»). Vale la pena guardare `stdout.json` prima di ritentare;
- `trace` non è un'operazione del motore: REA la compone e il provider dichiarato
  non è Ghidra. Il verdetto sui dati resta quello dell'operazione singola.

## Limiti dichiarati

- **REA non è incluso**: senza `rea` nel PATH non si analizza niente. Servono
  Node 22.19+ / 24.11+ / 26 (o un runtime equivalente) e, per le operazioni
  native, **Hopper o Ghidra** già installati e configurati;
- **una sola analisi per volta**: la coda è un thread singolo, la UI fa polling
  ogni 1,2 s;
- **cosa è stato provato**: il 9 ottobre 2026 `rea` 6.1.0 (Node 24.15.0) e le
  operazioni **statiche** (`doctor`, `capabilities`,
  `analyze-javascript-application` su un `.asar`, `analyze` su uno zip,
  `inspect-artifact`) sono passate end-to-end attraverso questa superficie; poi le
  sei operazioni **native** con **Ghidra 12.1.4** (tabella sopra). Sono prove su
  quegli artefatti, non una garanzia sul prossimo;
- **un solo motore nativo è provato**: **Hopper** (commerciale, macOS) e **IDA**
  (con il suo server MCP) restano dichiarati e non provati — la superficie non
  lancia mai `rea setup`, quindi non installa niente e non apre licenze;
- **il decompiler nativo su macOS va compilato**: il pacchetto ufficiale di Ghidra
  12.1.4 porta i binari di decompilazione solo per Linux e Windows. Su un'altra
  macchina Apple Silicon servono i passi della sezione precedente, altrimenti REA
  risponde `provider_unavailable` sul controllo `native_decompiler`;
- **il report è una riduzione**: conteggi, digest e progresso vengono dal
  documento, ma la lettura completa resta nei JSON scaricabili. Non è un
  verdetto di sicurezza.

## Verificare

```bash
.venv/bin/python -m pytest tests/test_rea_surface.py -q
node --test tests/rea_surface.test.cjs
```

I test Python fissano il perimetro (whitelist, rotte, validazioni, coda,
artefatti) e il contratto con lo stack (`/surfaces`, dashboard, start script);
il test Node estrae lo `<script>` della pagina dal sorgente Python e lo esegue
con un DOM finto, per controllare cosa la pagina dice — incluso il caso di REA
assente e la resa delle tre corsie.

Le operazioni native, quando c'è un motore, si riprovano dalla pagina oppure con
una richiesta sola — il file si **carica**, il client non passa mai un percorso:

```bash
curl -fsS -F op=decompile -F provider=ghidra -F argomento=0x100000460 \
  -F file=@prova_nativa http://127.0.0.1:7872/api/jobs
```

I lavori restano in `data/rea/jobs/`: al 9 ottobre 2026 gli ultimi sei sono
proprio le sei operazioni native con Ghidra.

Fonte: [REA README](https://github.com/morluto/rea), prova e decisione in
[docs/rea-pilot.md](rea-pilot.md), quadro generale in
[docs/development-security-tools.md](development-security-tools.md).

