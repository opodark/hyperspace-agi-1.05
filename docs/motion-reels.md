# Motion Reels

I Motion Reel sono video in motion design, di norma verticali e di 30 secondi,
disegnati in JavaScript su un canvas 1080×1920 e registrati fotogramma per
fotogramma in MP4. Un reel può durare di più e uscire anche in orizzontale
1920×1080 per YouTube (vedi [Durata, formati e reel di raccolta](#durata-formati-e-reel-di-raccolta)).
Raccontano gli avanzamenti R&D di HyperSpace e servono per i social. Sono
complementari al [Reel Editor](tiktok-editor.md), che monta foto e video sul
beat: qui non ci sono media di partenza, tutto è grafica generata dal codice.

Il codice sta in `integrations/tiktok_editor/motion/`:

| File | Ruolo |
|---|---|
| `runtime.js` | motore condiviso: easing, testo, sfondo a griglia, HUD, tagli di scena, mesh dei tre nodi, intro e chiusura |
| `reels/<id>.js` | un reel: le sue scene e la costante `REEL` (data, slogan, finestre delle scene, tagli) |
| `player.js` | riproduzione nel browser, scrubber, `window.__renderAt(t)` per il render |
| `shell.html` | pagina del player con i segnaposto che `build.py` sostituisce |
| `build.py` | compone la pagina autonoma e, a richiesta, lancia il render |
| `render.js` | Playwright + ffmpeg: un PNG per frame, H.264 `yuv420p`, `+faststart` |
| `fonts/` | sottoinsiemi `.woff` di Inter Display e DejaVu Sans Mono, con licenze |

Reel presenti:

- `rd-2026-10-27`: coscienza sintetica, endospore crittografiche, swarm stigmergico, protocolli sovrani, causal AI.
- `resilienza-2026-10-28`: circuit breaker adattivo, token bucket, PID di latenza, causal AI in Mission Control, 37/37 test.
- `pipeline-2026-10-28`: pipeline R&D, da Agent-Reach (24 ispirazioni, 6 canali) ai prototipi notturni (141), alla promozione in `shared/` (15 promozioni, 10 moduli) e alla memoria unica Hermes.
- `endurance-2026-10-28`: i quattro moduli del commit `113c769`, cioè validatore di bozze speculative, heartbeat con quorum anti split-brain, pool KV a blocchi con auto-eviction, sync di stato a 60 Hz con rollback, 8/8 test.
- `atomic-2026-10-29`: lo sprint del commit `5bb44d0`, con i tre pattern da Atomic Agent (grammatiche GBNF, traccia NDJSON replayabile con i 10 eventi veri di `data/traces/atomic_dual_sprint_20261029_091406.ndjson`, Mutation Guard con le tre proposte `prop_*`), i tre moduli promossi e 15/15 test.
- `panoramica-2026-10-29`: 60 s in 9:16 e 16:9, dieci scene prese dai cinque reel precedenti più il diario finale.
- `voglio-te-2026-10-29`: primo reel commerciale, in stile manifesto d'epoca (carta, rosso, blu notte). Un personaggio col cilindro punta il dito: «Piccola azienda! Voglio te, per i tuoi social». Seguono il problema, il turno di notte sui computer dell'ufficio, l'approvazione al mattino col tasto annulla e l'invito finale. Sostituisce sfondo, intro, HUD, chiusura e tagli con `REEL.layers`.

## Generare un reel dal Reel Editor

Apri `http://127.0.0.1:7860` e passa alla scheda **Motion Reels**: scegli il reel,
a sinistra lo vedi girare dal vivo (scrubber compreso), poi **Fotogrammi di
controllo** per i PNG agli istanti indicati e **Registra MP4** con la barra di
avanzamento. In fondo alla scheda c'è lo stato di node, ffmpeg e Playwright, e
fra i file scaricabili ci sono la pagina HTML autonoma e l'MP4. Le uscite sono le
stesse della riga di comando. La scheda è `integrations/tiktok_editor/app/motion_tab.py`.

## Generare un reel da riga di comando

```bash
python3 integrations/tiktok_editor/motion/build.py --list
python3 integrations/tiktok_editor/motion/build.py resilienza-2026-10-28            # solo HTML
python3 integrations/tiktok_editor/motion/build.py resilienza-2026-10-28 --render   # HTML + MP4
python3 integrations/tiktok_editor/motion/build.py resilienza-2026-10-28 --stills 9,18.5
```

L'uscita va in `data/reel-projects/motion/<id>/` (ignorata da git). La pagina
`<id>.html` è autonoma: si apre con un doppio clic, gira offline e si può
pubblicare così com'è. Il render dura circa due minuti e mezzo per 900 frame.

Per l'MP4 servono `ffmpeg` nel PATH, Node e Playwright con Chromium:

```bash
cd integrations/tiktok_editor/motion
npm i --no-save playwright && npx playwright install chromium
```

Il video è muto: la musica si aggiunge nell'app del social, oppure passando
l'MP4 al Reel Editor. Il render è deterministico: lo stesso istante produce
sempre lo stesso fotogramma, quindi due render dello stesso reel coincidono.

## Scrivere un reel nuovo

1. Copia un file di `reels/` con un nuovo id e aggiorna la riga `// @meta`
   (`id` uguale al nome del file, `title`, `aria` per gli screen reader).
2. Ogni scena è una funzione `scena(t)` che esce subito fuori dalla propria
   finestra e usa `header(t, a, b, numero, kicker, righe)` per titolo e numero
   in filigrana. Gli helper (`T`, `circ`, `seg`, `ring`, `pill`, `badge`,
   `arrow`, `words`, `letters`, `mesh`) e la palette `C` vengono da `runtime.js`.
3. In `REEL` elenca le scene in ordine, le loro finestre `sc` (per l'HUD) e i
   tagli `cuts` (la linea lime che attraversa lo schermo fra una scena e l'altra).
4. Controlla con `--stills` qualche istante, poi `--render`.

Per uno stile diverso da quello del log R&D, `REEL.layers` sostituisce i livelli
fissi del runtime: `bg`, `intro`, `outro`, `hud`, `cuts` (funzioni di `t`;
`() => {}` ne spegne uno) e `fade`, il colore della dissolvenza iniziale e
finale. I livelli non indicati restano quelli di sempre.

L'indirizzo nella pillola di chiusura è `REEL.cta`, di default
`os.zerozerocomputer.it`. Nei reel pubblici non va mai `mesh.zerozerocomputer.it`,
che è l'API interna dei bot.

Le scene illustrano, non misurano: grafici e simulazioni (curve PID, livello
VRAM, code del rate limiter) sono animazioni dimostrative. I numeri scritti a
schermo, come i conteggi dei test, vanno presi dai risultati reali.

## Durata, formati e reel di raccolta

La riga `// @meta` accetta tre chiavi facoltative:

| Chiave | Default | Effetto |
|---|---|---|
| `"dur": 60` | `30` | durata in secondi: player, scrubber, HUD, chiusura e render si adeguano |
| `"formats": ["9:16", "16:9"]` | `["9:16"]` | formati disponibili, il primo è il predefinito |
| `"parts": ["rd-2026-10-27", …]` | nessuna | reel di cui riusare le scene, letti da `PARTS['<id>']` |

Le scene si scrivono sempre in coordinate verticali 1080×1920. In 16:9 il
runtime le disegna su una tela verticale fuori schermo: `header()` mette kicker e
titolo nella colonna sinistra, mentre la fascia `REEL.crop` (default
`[600, 1540]`, in y verticali) finisce nella colonna destra. Il reel di raccolta
`panoramica-2026-10-29` non ridisegna nulla: prende le scene da `PARTS`, le
sposta nel tempo e le rinumera con `HNUM`.

```bash
python3 integrations/tiktok_editor/motion/build.py panoramica-2026-10-29 --render                # 9:16
python3 integrations/tiktok_editor/motion/build.py panoramica-2026-10-29 --format 16:9 --render  # 16:9
```

Il formato predefinito tiene i nomi di sempre (`<id>.mp4`), gli altri aggiungono
il suffisso (`<id>-16x9.mp4`). Nella scheda Motion Reels compare la scelta del
formato quando il reel ne ha più d'uno.

## Font

Il display è Inter Display (Black, SemiBold, Medium), il monospazio DejaVu Sans
Mono, entrambi incorporati come data URI così il video è identico su ogni
macchina. La landing usa Unbounded e JetBrains Mono: per allineare i reel basta
rigenerare i file con `fonts/subset_fonts.py` puntando a quei font (stessi nomi
di uscita), con le relative licenze in `fonts/`.

## Verifica

```bash
.venv/bin/python -m pytest tests/test_motion_reels.py -q
```

Il test compone ogni reel in ogni suo formato, controlla segnaposto, font,
dimensioni, ordine dei tagli entro la durata, che ogni scena elencata esista e
che le parti di un reel di raccolta esistano; se `node` c'è, verifica anche la
sintassi dello script assemblato.
