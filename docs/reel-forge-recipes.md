# Reel Creator: ricette convalidate per Auto Forge

Questa scheda conserva gli script usati nelle prove del 4 ottobre 2026. L'utente
ha convalidato il percorso di anteprima durante le iterazioni. I file sorgente
restano nel repository; gli MP4 e i media privati restano locali. Per creare
tool riutilizzabili, Auto Forge deve leggere gli script indicati qui e costruire
interfacce con input espliciti per i file, senza fissare i percorsi dell'utente.

## Script e capacità

| Script | Capacità verificata | Input principali |
|---|---|---|
| `scripts/reel_media.py` | Prepara un progetto copiando media scelti per Anna o Aurora, con manifest e verifica delle copie | persona, nomi, cartella sorgente |
| `scripts/reel_person_layer_smoke.py` | Anteprima di 5 secondi con maschere persona/sfondo, grade separati e croce luminosa sui beat | foto, video, audio, output |
| `scripts/reel_dark_intro_preview.py` | Apertura di 30 secondi molto scura con foto e clip brevi | cartella foto, video, audio, output |
| `scripts/reel_pole_preview_60.py` | Anteprima verticale di 60 secondi: 10 foto verticali dopo correzione EXIF e 9 clip video; esclude foto orizzontali e pose sdraiate dalla selezione corrente | cartella foto, video, audio, output |

La logica condivisa si trova in `integrations/tiktok_editor/app/autoedit/`:
`person_layers.py` prepara le maschere con macOS Vision tramite
`person_mask.swift`; `render.py` monta scene e applica i livelli;
`overlays.py` disegna la croce luminosa; `media.py` corregge l'orientamento
EXIF. `integrations/tiktok_editor/app/gui.py` espone gli stessi controlli nella
UI e `draft.py` salva automaticamente il lavoro. La modalità crescendo di 120
secondi usa 110 secondi di preparazione e 10 di finale con tagli e strobo.

## Riproduzione della prova da 60 secondi

```bash
/Users/opo/Downloads/tiktok_editor/.venv/bin/python scripts/reel_pole_preview_60.py \
  --photo-dir '/Users/opo/Pictures/2013/2013-10-22' \
  --video '/Users/opo/Downloads/WhatsApp Video 2026-10-04 at 12.29.24.mp4' \
  --audio '/Users/opo/Downloads/BATTISTA - BATTISTA  (Video Ufficiale) - (320 Kbps).mp3' \
  --out data/reel-preview/pole-verticale-60s.mp4
```

Il preset usa `--audio-start 13.7`, output 360×640 a 24 fps, sfondo molto
scuro e persona appena visibile. Il risultato locale è
`data/reel-preview/pole-verticale-60s.mp4`; sono state prodotte anche le prove
di 5 e 30 secondi in quella cartella. Servono `ffmpeg`, `ffprobe`, Pillow e
l'ambiente Python dell'editor. La segmentazione Vision richiede macOS e può
richiedere il primo download dei modelli di sistema.

## Evidenze e limiti

- L'MP4 di 60 secondi è stato verificato con `ffprobe` (H.264/AAC, 360×640,
  durata 60 secondi). Sono passati 12 test per bozza UI, integrazione editor e
  livelli persona/sfondo.
- La convalida dell'utente riguarda le anteprime e l'utilità degli script come
  base per Auto Forge. Non equivale a un test di ogni combinazione di input.
- La segmentazione distingue persona e sfondo, ma il palo può finire nello
  sfondo. La ricostruzione 3D dei contorni non è implementata.
- I percorsi dei media sopra servono solo a riprodurre questa prova locale.
  I nuovi tool devono riceverli come argomenti e non leggere cartelle private
  senza una scelta esplicita dell'utente.
- Prima di pubblicare un tool generato, rivedere sorgente, permessi e uso dei
  media/audio. L'artefatto Forge collegato è una bozza inattiva.

## Nuova prova in attesa di valutazione

`scripts/reel_pole_preview_60_fx.py` produce una variante di 60 secondi con
15 foto verticali e 7 clip nei primi 50 secondi, poi 16 pose acrobatiche dal
video negli ultimi 10. Usa transizioni casuali riproducibili dal catalogo
`chaos`, lampi e archi elettrici intorno alla maschera della persona, più la
croce luminosa sui beat finali. Parte dall'audio al secondo 73,7. Il file
`data/reel-preview/pole-verticale-60s-fx.mp4` è stato verificato con `ffprobe`
a 60 secondi, H.264/AAC, 360×640. Questa variante resta sperimentale finché
l'utente non ne valuta l'anteprima.

La valutazione successiva dell'utente ha confermato che il montaggio comincia
a seguire il battito, ma ha respinto gli archi elettrici disegnati. Quegli
effetti non devono diventare un tool o un preset riutilizzabile.

`scripts/reel_pole_preview_60_heartbeat.py` è la prova successiva: 78 scene
tagliate sui battiti rilevati del brano (56 nel crescendo, 22 nel finale),
17 foto verticali diverse distribuite in 28 apparizioni, 28 brevi clip video
e 22 pose finali estratte dal girato. Non usa archi elettrici disegnati: la
luce sul corpo segue la maschera della persona. La croce rimane sui beat negli
ultimi 10 secondi. Il risultato `data/reel-preview/pole-verticale-60s-heartbeat.mp4`
è stato verificato a 60 secondi e 1440 fotogrammi, con pose diverse anche a
50 e 58 secondi. Resta in attesa della valutazione dell'utente.

`scripts/reel_whatsapp_heartbeat_60.py` applica la stessa griglia ai download
WhatsApp del 4 ottobre 2026: tutte le 18 foto delle 11:44 (ritagliate in
verticale intorno al soggetto) e il video delle 14:10, lungo circa 67 secondi.
Le foto sono alternate a 28 clip brevi; il finale prende 22 pose dalla seconda
metà del nuovo video. Mantiene la luce aderente alla maschera, il blu originale
e la croce sui battiti finali, senza fulmini disegnati. L'anteprima locale è
`data/reel-preview/whatsapp-heartbeat-60s.mp4`, verificata a 60 secondi e
1440 fotogrammi. Anche questa variante attende la valutazione dell'utente.

`scripts/reel_whatsapp_speedramp_finale.py` riusa i primi 50 secondi di quella
anteprima e sostituisce le 22 foto finali con 22 frammenti consecutivi del
video verticale WhatsApp: velocità alternate 0,8× e 3× a ogni battito. I
frammenti percorrono senza salti i secondi 47,50–66,50 della sorgente; la
segmentazione persona e la croce sui beat restano attive. Il file
`data/reel-preview/whatsapp-heartbeat-speedramp-60s.mp4` è stato verificato a
60 secondi, 1440 fotogrammi, H.264/AAC. Prova in attesa di valutazione.

`scripts/reel_whatsapp_video_only_60.py` elimina tutte le foto. Usa solo il
video verticale WhatsApp dall'inizio fino a 0,18 secondi dalla fine, senza
saltare intervalli. Nei primi 50 secondi alterna circa 0,61× e 1,37×; negli
ultimi 10 alterna 0,8× e 3×. Su un battito sì e uno no trattiene due
fotogrammi iniziali per un effetto start/stop. Mantiene grade separato per
persona/sfondo, audio BATTISTA dal secondo 73,7 e croce finale sui beat.
`data/reel-preview/whatsapp-video-only-start-stop-60s.mp4` è stato verificato
a 60 secondi, 1440 fotogrammi, H.264/AAC. Prova da valutare con l'utente.

`scripts/reel_lyrics_light.py` aggiunge al reel solo-video il testo italiano
fornito dall'utente. La prima prova aveva 38 frasi; dopo la richiesta di un
ritmo più rapido la ricetta mostra 52 frasi, con due righe visibili nei primi
50 secondi: le parole della riga attuale si accendono una alla volta con
bagliore e sottolineatura, mentre quelle già passate restano illuminate e la
riga successiva attende in azzurro. L'ultima riga svanisce prima che inizi la
croce luminosa del finale. I tempi sono distribuiti e agganciati ai beat;
l'avanzamento delle parole è stimato dalla lunghezza del testo, quindi non è
ancora un allineamento preciso alla voce. Il file
`data/reel-preview/lyrics-light-assets/lyrics-cues.json` conserva gli intervalli
per rifinirli dopo l'ascolto. L'anteprima
`data/reel-preview/whatsapp-video-only-karaoke-words-60s.mp4` è stata verificata
a 60 secondi e 1440 fotogrammi, H.264/AAC. Attende la valutazione dell'utente.

`scripts/reel_s24_heartbeat_60fps.py` usa il girato originale S24
`/Users/opo/Documents/20261002_213630.mp4` (60 fps con rotazione verticale nei
metadati) al posto della copia WhatsApp. Monta 60 secondi a 60 fps con stop di
quattro fotogrammi sui battiti alterni, piccoli zoom in ingresso al battito,
accelerazioni e rallentamenti più netti negli ultimi dieci secondi. La croce
appare come bagliore diffuso sullo sfondo; nel finale una maschera della sagoma
ricavata dal movimento del video mantiene la ballerina davanti alla luce.
La maschera è una stima locale, da valutare visivamente sui contorni. Le lyrics
karaoke restano nei primi 50 secondi. Anteprima:
`data/reel-preview/s24-heartbeat-karaoke-backlit-60fps.mp4`. Prova da valutare
con l'utente.

`scripts/reel_s24_clean_speedramp.py` corregge la perdita di dettaglio della
prova S24 precedente: il montaggio usa 1080×1920 a 60 fps dal file originale,
senza sfocatura, oscuramento, zoom, maschere o croce. Gli stop sul battito
durano 8 fotogrammi nel crescendo e 12 nel finale; i tratti lenti e veloci
alternano circa 0,21×/1,46× prima del finale e 0,25×/5× negli ultimi 10
secondi. La griglia e le velocità effettive sono in
`data/reel-preview/s24-clean-speedramp-assets/timeline.json`. Il master senza
grafica è `data/reel-preview/s24-clean-speedramp-1080p60.mp4`; la variante con
le lyrics karaoke precedenti è
`data/reel-preview/s24-clean-speedramp-karaoke-1080p60.mp4`.

`scripts/reel_s24_cross_strobe.py` aggiunge al master S24 con lyrics una croce
luminosa dietro alla sagoma nel finale e lampi bianchi sull'intera scena.
Il primo lampo al secondo 50 è un'esplosione di luce più forte; i successivi
seguono i battiti della timeline, con lampi intermedi negli ultimi tre secondi.
La maschera del soggetto è stimata dai fotogrammi del finale e riguarda solo la
croce; i lampi illuminano anche la ballerina. Anteprima a 1080×1920 e 60 fps:
`data/reel-preview/s24-karaoke-cross-strobe-1080p60.mp4`.

`scripts/reel_s24_motion_strobe.py` intensifica anche il movimento nell'ultimo
blocco: riprende dal girato originale S24 i secondi sorgente 41,278–66,503 e
crea cinque cicli fermo/scatto per battito (quattro nell'ultimo battito più
corto). In 10 secondi produce circa 220 cambi di fase: ripete brevemente i
fotogrammi, poi salta in avanti fino a sei fotogrammi sorgente. La mappa completa
si trova in `data/reel-preview/s24-motion-strobe-assets/source-frame-map.json`.
Il montaggio con lyrics e senza lampi è
`data/reel-preview/s24-karaoke-motion-strobe-1080p60.mp4`; riapplicando
`scripts/reel_s24_cross_strobe.py` si ottiene
`data/reel-preview/s24-karaoke-motion-cross-strobe-1080p60.mp4`.

La ricetta completa del preset S24 corrente, con tutti gli input, il testo,
i parametri, i comandi per riprodurlo e le interfacce proposte per i tool, è in
`docs/reel-creator-s24-strobo-recipe.md`. Questo indice resta la cronologia
delle prove precedenti.

L'estensione sperimentale nella ricetta completa usa
`scripts/reel_s24_note_motion.py` per stimare 54 intervalli di nota nei primi
50 secondi e `scripts/reel_s24_note_aura.py` per due luci legate alle strisce
del costume: neon magenta/verde e bianco avorio. Il finale conserva la
sincronizzazione ai beat. I file da valutare sono
`data/reel-preview/s24-note-motion-neon-final-beat-1080p60.mp4` e
`data/reel-preview/s24-note-motion-ivory-final-beat-1080p60.mp4`.

L'utente ha scelto la variante neon. La nuova prova
`scripts/reel_s24_dual_tone_neon.py` fa pulsare il viola su “no” e il verde
su “naaa” nei primi 50 secondi, lasciando invariato il finale beat-strobo.
La mappa modificabile è `data/reel-preview/s24-note-experiments/tone-cues.json`;
l'anteprima è `data/reel-preview/s24-note-motion-purple-green-final-beat-1080p60.mp4`.
La classificazione automatica dei due toni è sperimentale e va ascoltata.
La revisione staccata usa due lampi brevi per nota, pausa buia e cambio colore
netto a 60 fps: `data/reel-preview/s24-note-motion-purple-green-staccato-final-beat-1080p60.mp4`.
