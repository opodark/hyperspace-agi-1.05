# Motion Reels

I Motion Reel sono video verticali di 30 secondi in motion design, disegnati in
JavaScript su un canvas 1080×1920 e registrati fotogramma per fotogramma in MP4.
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

Le scene illustrano, non misurano: grafici e simulazioni (curve PID, livello
VRAM, code del rate limiter) sono animazioni dimostrative. I numeri scritti a
schermo, come i conteggi dei test, vanno presi dai risultati reali.

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

Il test compone ogni reel, controlla segnaposto, font, ordine dei tagli e che
ogni scena elencata esista; se `node` c'è, verifica anche la sintassi dello
script assemblato.
