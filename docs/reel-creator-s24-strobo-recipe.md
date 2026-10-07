# Reel Creator — ricetta S24, karaoke e finale stroboscopico

**Ricetta:** `pole-s24-heartbeat-strobe-v1`  
**Data della prova:** 4 ottobre 2026  
**Stato:** anteprima funzionante; specifica pronta per ricavare tool modificabili.

## Risultato cercato

Un videoclip verticale di 60 secondi costruito solo dal video originale della
ballerina. Nei primi 50 secondi il montaggio segue la marcia del brano, alterna
rallentamenti, brevi fermi e accelerazioni, e mostra la traduzione italiana
come karaoke luminoso. Al secondo 50 le parole sono finite: una croce di luce
esplode dietro la ballerina, illumina l'intera scena e continua a pulsare sui
battiti. Nell'ultimo blocco anche la rotazione del corpo è stroboscopica:
microfermi e scatti tra fotogrammi sorgente più distanti. Non usare foto,
cartoon, fulmini disegnati, sfocatura del girato, oscuramento aggiunto o zoom.

## Input e output della prova

| Ruolo | File locale della prova | Nel tool futuro |
|---|---|---|
| Video originale | `/Users/opo/Documents/20261002_213630.mp4` | File scelto dall'utente; non fissare il percorso nel codice |
| Brano | `/Users/opo/Downloads/BATTISTA - BATTISTA  (Video Ufficiale) - (320 Kbps).mp3` | File scelto dall'utente |
| Testo | Le 16 frasi italiane nella sezione seguente | Campo testo modificabile o file UTF-8 |
| Output finale verificato | `data/reel-preview/s24-karaoke-motion-cross-strobe-1080p60.mp4` | Destinazione scelta dall'utente |

Il video S24 contiene circa 66,68 secondi, frame rate nominale 60 fps e
rotazione verticale nei metadati, mentre i pixel memorizzati sono 2560×1440.
Il brano inizia al secondo **73,7** dell'MP3. Il render è H.264/AAC,
1080×1920, 60 fps, 3.600 fotogrammi e 60,000 secondi.

## Testo italiano della prova

Conservare ordine e punteggiatura. Le frasi sono il testo fornito dall'utente,
non una trascrizione automatica dell'audio.

1. All’epoca i medici erano così, frettolosi: era il 1998.
2. Ma Dio dice: “La verità viene rivelata agli umili e viene nascosta a chi è colto.”
3. “Noi pregheremo il Signore affinché lo guarisca.”
4. Il dottore li guardava perplesso.
5. “In Lui troviamo conforto e solo Lui decide sulla vita e sulla morte.”
6. “Ma, anche se Dio non volesse guarirlo, sia fatta la sua volontà.”
7. Uscirono di corsa dallo studio medico e poi andarono subito in chiesa a pregare.
8. Lì si sfogarono con Mimmo, l’anziano, un membro speciale della comunità.
9. Mimmo, con una mano alzata e l’altra sulla pancia, pregava con autorità.
10. E il Signore ascoltò quelle preghiere e disse a Marianna:
11. “Figlia mia, non preoccuparti.”
12. Passarono soltanto sei mesi, il bambino nacque, era sano e per questo oggi sono qui.
13. E non solo, fratello: sono nato sano, ma sono anche il più forte di tutti quanti in questa scena.
14. Da Milano a Napoli adesso devono farsela sotto tutti quanti, se non vogliono problemi.
15. Si vede che ho uno scopo importante, per questo il Signore veglia su di me.
16. Perché, se avessero seguito la sapienza umana, a quest’ora BATTISTA non esisterebbe.

## Parametri del preset attuale

| Parametro | Valore usato | Comportamento |
|---|---:|---|
| Durata / finale | 60 s / ultimi 10 s | Lyrics solo nei primi 50 s; luce e movimento strobo dal secondo 50 |
| Output | 1080×1920, 60 fps | Rotazione applicata, ridimensionamento Lanczos; nessuna sfocatura o zoom del video |
| Audio start | 73,7 s | Taglio del brano per i 60 s di output; dissolvenza audio di 0,25 s ai bordi |
| Beat | 78 intervalli | 56 nel crescendo, 22 nel finale; `timeline.json` conserva gli istanti effettivi |
| Master, primi 50 s | circa 0,21× / 1,46× | Alternanza ai battiti, stop di 8 frame su battiti alterni |
| Master, ultimi 10 s intermedi | 0,25× / 5× | Usati per il master pulito; il finale consegnato li sostituisce col movimento strobo |
| Movimento finale consegnato | 5 cicli fermo/scatto per battito | 4 cicli nell'ultimo battito corto, circa 220 cambi di fase in 10 s |
| Microfermo | 2 frame per ciclo, di solito 3 tra cicli | 217 coppie consecutive di frame sorgente ripetuto nel finale |
| Scatto | fino a 6 frame sorgente tra frame di output | Avanza sempre nella sorgente: niente inversione o ripetizione di pose da foto |
| Lyrics | 52 cartelli su 2 righe | Riga attiva e successiva; parola corrente luminosa, avanzamento stimato sui beat |
| Croce | impulso di 0,19 s su ogni beat finale | Bagliore composto sullo sfondo con maschera approssimata della ballerina |
| Esplosione | bianco 0,88 di opacità per circa 0,105 s al secondo 50 | Illumina tutto il frame, ballerina inclusa |
| Lampi successivi | 0,52 di opacità per circa 0,075 s | Uno per battito dopo il primo; negli ultimi 3 s lampi intermedi 0,42 / 0,055 s |

I 217 frame ripetuti e i salti successivi sono registrati in
`data/reel-preview/s24-motion-strobe-assets/source-frame-map.json`. Il finale
percorre in avanti i secondi sorgente **41,278–66,503**. La croce usa una
maschera ricavata dai fotogrammi del finale a 360×640 e 12 fps, poi ampliata
per la composizione 1080×1920. I lampi bianchi coprono intenzionalmente anche
il soggetto; la maschera vale solo per collocare la croce dietro la sagoma.

## Pipeline riproducibile

Eseguire dalla radice del repository. Servono `ffmpeg`, `ffprobe`, Python,
Pillow, NumPy, SciPy e le dipendenze di `autoedit.beats` nell'ambiente editor.
La prova usa l'interprete indicato qui; i tool dovranno usare il proprio
ambiente e ricevere i percorsi come input.

```bash
REEL_PYTHON=/Users/opo/Downloads/tiktok_editor/.venv/bin/python
REEL_VIDEO=/Users/opo/Documents/20261002_213630.mp4
REEL_AUDIO='/Users/opo/Downloads/BATTISTA - BATTISTA  (Video Ufficiale) - (320 Kbps).mp3'
REEL_OUT=data/reel-preview

"$REEL_PYTHON" scripts/reel_s24_clean_speedramp.py \
  --video "$REEL_VIDEO" --audio "$REEL_AUDIO" \
  --out "$REEL_OUT/s24-clean-speedramp-1080p60.mp4"
```

Questo crea il master pulito, la sorgente verticale normalizzata
`s24-clean-speedramp-assets/portrait-1080x1920-60fps.mp4` e la timeline dei
battiti `s24-clean-speedramp-assets/timeline.json`.

La versione attuale di `reel_lyrics_light.py` genera la grafica a 360×640.
Per riprodurre **esattamente l'anteprima esistente**, generare un proxy del
master, poi ampliare solo il livello trasparente delle scritte nel compositing
1080p. Il video della ballerina resta alla risoluzione piena:

```bash
ffmpeg -y -v error -i "$REEL_OUT/s24-clean-speedramp-1080p60.mp4" \
  -vf scale=360:640 -c:v libx264 -preset veryfast -crf 18 \
  -c:a copy "$REEL_OUT/s24-lyrics-proxy.mp4"

"$REEL_PYTHON" scripts/reel_lyrics_light.py \
  --video "$REEL_OUT/s24-lyrics-proxy.mp4" --audio "$REEL_AUDIO" \
  --out "$REEL_OUT/s24-lyrics-proxy-render.mp4"

ffmpeg -y -v error -i "$REEL_OUT/s24-clean-speedramp-1080p60.mp4" \
  -i "$REEL_OUT/lyrics-light-assets/lyrics-alpha.mov" \
  -filter_complex '[1:v]scale=1080:1920:flags=lanczos[lyrics];[0:v][lyrics]overlay=0:0:eof_action=pass[v]' \
  -map '[v]' -map 0:a -c:v libx264 -preset veryfast -crf 16 \
  -pix_fmt yuv420p -c:a copy -t 60 \
  "$REEL_OUT/s24-clean-speedramp-karaoke-1080p60.mp4"
```

`lyrics-light-assets/lyrics-cues.json` conserva inizio, fine e testo di ogni
cartello. La luce avanza parola per parola in base alla lunghezza del testo e
alla griglia dei beat: i tempi delle singole parole non sono ancora verificati
contro la voce. La riga finale svanisce prima del secondo 50.

```bash
"$REEL_PYTHON" scripts/reel_s24_motion_strobe.py \
  --source "$REEL_OUT/s24-clean-speedramp-assets/portrait-1080x1920-60fps.mp4" \
  --video "$REEL_OUT/s24-clean-speedramp-karaoke-1080p60.mp4" \
  --timeline "$REEL_OUT/s24-clean-speedramp-assets/timeline.json" \
  --out "$REEL_OUT/s24-karaoke-motion-strobe-1080p60.mp4"

"$REEL_PYTHON" scripts/reel_s24_cross_strobe.py \
  --video "$REEL_OUT/s24-karaoke-motion-strobe-1080p60.mp4" \
  --timeline "$REEL_OUT/s24-clean-speedramp-assets/timeline.json" \
  --out "$REEL_OUT/s24-karaoke-motion-cross-strobe-1080p60.mp4"
```

Il primo script sostituisce solo i frame dal secondo 50 al 60; conserva i
primi 50 s con karaoke e riusa l'audio. Il secondo crea la croce, la maschera
della sagoma, il lampo iniziale e gli impulsi successivi. È possibile confrontare
il risultato con il master pulito e con il finale senza lampi.

## Tool da ricavare

1. **Analizza media e battiti.** Riceve video, audio, inizio audio e durata.
   Verifica esistenza, orientamento, dimensioni, frame rate e durata; produce
   timeline e manifest del progetto. Non assume nomi o cartelle privati.
2. **Monta master pulito.** Riceve manifest e parametri di speed ramp, stop e
   risoluzione. Produce master H.264/AAC e timeline modificabile. Usa il video
   originale; non applica sfocatura, zoom, oscuramento o grade per default.
3. **Aggiungi karaoke.** Riceve testo e cue modificabili. Mostra due righe,
   evidenzia la parola corrente e forza la fine entro l'inizio del finale.
   Rendere il testo direttamente alla risoluzione di output è un miglioramento
   da implementare nel tool: l'anteprima usa il livello 360×640 ampliato.
4. **Crea finale strobo.** Riceve sorgente originale, timeline e montaggio con
   lyrics. Espone cicli fermo/scatto per beat, intensità/durata della croce,
   lampo iniziale e lampi successivi. Produce anche la mappa dei frame e una
   variante senza flash per confrontare il solo movimento.

Una schermata Reel Creator può orchestrare questi quattro passaggi. Deve
salvare automaticamente media scelti, testo, cue, parametri, timeline e percorsi
di output in una bozza riapribile, così lo spegnimento dello schermo non perde
il lavoro. Il render non deve riavviarsi se input e parametri di uno stadio non
sono cambiati; gli artefatti intermedi vanno associati alla bozza, non a un
percorso globale condiviso tra progetti.

## Controlli prima di considerare un render riuscito

- `ffprobe`: durata 60,000 s, 1080×1920, 60 fps, 3.600 frame video, H.264/AAC.
- Ascolto e visione: il primo beat luminoso è al secondo 50, dopo l'ultima
  scritta; i microfermi e gli scatti della ballerina sono visibili tra i lampi.
- Verifica mappa: 600 frame nel finale, indici sorgente non decrescenti, inizio
  e fine all'interno del video originale. La prova attuale ha 217 transizioni
  con frame sorgente ripetuto.
- Verifica contorni: la maschera della croce è una stima del movimento, non una
  ricostruzione 3D né una segmentazione Vision affidabile in ogni posa. I tool
  devono permettere l'anteprima del finale e la regolazione della maschera.

## Script e artefatti della prova

| Stadio | Script | Artefatto principale |
|---|---|---|
| Master | `scripts/reel_s24_clean_speedramp.py` | `data/reel-preview/s24-clean-speedramp-1080p60.mp4` |
| Karaoke | `scripts/reel_lyrics_light.py` + compositing FFmpeg | `data/reel-preview/s24-clean-speedramp-karaoke-1080p60.mp4` |
| Movimento finale | `scripts/reel_s24_motion_strobe.py` | `data/reel-preview/s24-karaoke-motion-strobe-1080p60.mp4` |
| Croce e lampi | `scripts/reel_s24_cross_strobe.py` | `data/reel-preview/s24-karaoke-motion-cross-strobe-1080p60.mp4` |

Questa ricetta descrive il preset realizzato e controllato con il materiale
S24 indicato sopra. Il comportamento su altri media resta da verificare mentre
si costruiscono i tool; la bozza Forge non attiva né pubblica codice da sola.

## Estensione sperimentale: movimento sulle note della cornamusa

La versione con beat e microfermi descritta sopra resta il riferimento. Due
nuove anteprime sostituiscono **solo i primi 50 secondi**: i confini musicali
derivano da variazioni nello spettro armonico del brano, mentre lyrics e ultimi
10 secondi rimangono come nel riferimento. Lo script
`scripts/reel_s24_note_motion.py` calcola una CQT armonica nell'intervallo
G3–F♯6, cerca cambi persistenti con distanza minima di 0,48 s e ne ha trovati
53 all'interno del primo blocco, producendo 54 intervalli. A ogni confine la
ballerina sosta per alcuni fotogrammi; nel corpo della nota il movimento
accelera e rallenta in modo continuo. Il mapping percorre i secondi sorgente
0–41,278 senza tornare indietro. I tempi stimati sono modificabili in
`data/reel-preview/s24-note-experiments/note-cues.json`; la mappa dei 3.000
fotogrammi è `intro-frame-map.json` nella stessa cartella.

Poiché rap, percussioni e cornamusa sono mescolati nella stessa traccia,
l'analisi segnala **cambi armonici candidati**, non l'inizio e la fine certi di
ogni singola nota di cornamusa. Per un tool di produzione servono regolazione
manuale dei cue o separazione degli strumenti prima dell'analisi.

`scripts/reel_s24_note_aura.py` aggiunge luce solo nel primo blocco, usando
come guida le strisce luminose già presenti sul costume e modulando
l'intensità ai confini delle note. Le due versioni da valutare sono:

| Variante | Effetto | Anteprima |
|---|---|---|
| Neon | Bagliori e breve scia magenta/verde sulle strisce del costume | `data/reel-preview/s24-note-motion-neon-final-beat-1080p60.mp4` |
| Avorio | Bagliore bianco caldo, più tenue, sulle stesse strisce | `data/reel-preview/s24-note-motion-ivory-final-beat-1080p60.mp4` |

Un tentativo di alone su tutta la sagoma ha generato bagliori staccati dal
corpo in alcune pose; resta escluso dalle anteprime proposte. Gli effetti sulle
strisce conservano il video originale nitido e non aggiungono fulmini o tratti
disegnati. Il finale con croce e strobo sui battiti è lo stesso nelle due
varianti.

```bash
"$REEL_PYTHON" scripts/reel_s24_note_motion.py \
  --source "$REEL_OUT/s24-clean-speedramp-assets/portrait-1080x1920-60fps.mp4" \
  --audio "$REEL_AUDIO" \
  --final-video "$REEL_OUT/s24-karaoke-motion-cross-strobe-1080p60.mp4" \
  --lyrics-alpha "$REEL_OUT/lyrics-light-assets/lyrics-alpha.mov" \
  --timeline "$REEL_OUT/s24-clean-speedramp-assets/timeline.json" \
  --out "$REEL_OUT/s24-note-motion-karaoke-final-beat-1080p60.mp4"

"$REEL_PYTHON" scripts/reel_s24_note_aura.py \
  --video "$REEL_OUT/s24-note-motion-karaoke-final-beat-1080p60.mp4" \
  --notes "$REEL_OUT/s24-note-experiments/note-cues.json" \
  --style neon \
  --out "$REEL_OUT/s24-note-motion-neon-final-beat-1080p60.mp4"

"$REEL_PYTHON" scripts/reel_s24_note_aura.py \
  --video "$REEL_OUT/s24-note-motion-karaoke-final-beat-1080p60.mp4" \
  --notes "$REEL_OUT/s24-note-experiments/note-cues.json" \
  --style ivory \
  --out "$REEL_OUT/s24-note-motion-ivory-final-beat-1080p60.mp4"
```

Per i tool aggiungere al progetto `sync_intro = beat | note` e
`light_style = none | neon | ivory`, più un editor della timeline delle note.
Il preset `note` mantiene il cambio a `beat` esattamente al secondo 50. Le due
anteprime sono state verificate a 60 s, 1080×1920, 60 fps, 3.600 frame,
H.264/AAC; l'esattezza percettiva dei cue delle note attende l'ascolto
dell'utente.

## Variante scelta: viola “no” e verde “naaa”

L'utente ha scelto come base la variante neon. La prova successiva conserva
montaggio, lyrics e finale, ma fa pulsare il colore del bagliore in modo diverso
per le due tonalità percepite della cornamusa. `scripts/reel_s24_dual_tone_neon.py`
confronta l'energia armonica di due profili vicini nell'intervallo C♯4/D4 e
la durata degli intervalli: assegna **viola a “no”** e **verde a “naaa”**. Nella
prova corrente risultano 24 intervalli viola e 30 verdi. L'inizio della nota
accende il bagliore, la fine lo richiama brevemente. La prima prova sfumava
tra i colori per 0,12 s e manteneva una luce di fondo. Nella revisione staccata,
ogni nota produce due lampi brevi, uno all'attacco e uno prima della fine,
separati da una pausa buia. Il cambio viola/verde è netto, senza sfumatura;
la maschera della luce è aggiornata a 12 fps e il lampeggio a 60 fps. La luce
segue le strisce del costume. Dopo il secondo
50 si interrompe e resta il finale strobo sui beat.

La classificazione è una scelta sperimentale sul brano mixato, non una prova che
ogni nota appartenga con certezza a uno dei due strumenti o profili. Il file
`data/reel-preview/s24-note-experiments/tone-cues.json` contiene `start`, `end`,
`tone`, `score` e rapporto armonico per ogni intervallo. Si può correggere
`tone` a `no` o `naaa` e rilanciare il render senza rifare il movimento.
Il CQT salvato da `reel_s24_note_motion.py` è
`data/reel-preview/s24-note-experiments/bagpipe-cqt.npz`.

```bash
"$REEL_PYTHON" scripts/reel_s24_dual_tone_neon.py \
  --video "$REEL_OUT/s24-note-motion-karaoke-final-beat-1080p60.mp4" \
  --notes "$REEL_OUT/s24-note-experiments/note-cues.json" \
  --cqt "$REEL_OUT/s24-note-experiments/bagpipe-cqt.npz" \
  --tones "$REEL_OUT/s24-note-experiments/tone-cues.json" \
  --out "$REEL_OUT/s24-note-motion-purple-green-staccato-final-beat-1080p60.mp4"
```

Anteprima staccata da valutare:
`data/reel-preview/s24-note-motion-purple-green-staccato-final-beat-1080p60.mp4`.
La prima prova, con sfumatura, resta in
`data/reel-preview/s24-note-motion-purple-green-final-beat-1080p60.mp4`.
Verificata a 60 s, 1080×1920, 60 fps, 3.600 frame, H.264/AAC. Nel tool futuro
esporre la mappa `no`/`naaa` in un editor semplice e mostrare subito i due
colori su pochi secondi di anteprima prima del render completo.
