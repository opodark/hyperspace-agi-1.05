# Reel Editor locale per Anna e Aurora

HyperSpace include il codice dell'editor in `integrations/tiktok_editor/app/`:
monta foto e video in 9:16, taglia sul beat e produce un MP4. L'ambiente Python
esistente in `/Users/opo/Downloads/tiktok_editor/.venv` fornisce le dipendenze.
Non pubblica
automaticamente su TikTok o Instagram.

Il Desktop HyperSpace (`http://127.0.0.1:8085/`) contiene il riquadro
**Reel Editor**, che apre `http://127.0.0.1:7860`. Il servizio gira **solo sul
Mac, su loopback**: non è esposto alla rete e non viene avviato nel container.
`scripts/start-all-macos.sh` lo avvia insieme agli altri componenti;
`scripts/stop-all-macos.sh` lo ferma. Per avviarlo da solo:

```bash
launchctl bootstrap "gui/$(id -u)" integrations/tiktok_editor/com.hyperspace.tiktok-editor.plist
```

Se è già registrato ma spento, usa `launchctl kickstart -k
"gui/$(id -u)/com.hyperspace.tiktok-editor"`. Prima verifica
`/Users/opo/Downloads/tiktok_editor/.venv/bin/python scripts/tiktok_editor_service.py --check`.
Servono anche `ffmpeg` e `ffprobe` nel PATH. I log sono in
`data/tiktok-editor.log` e `data/tiktok-editor.err.log`.

Per i reel di sola grafica in motion design (avanzamenti R&D, niente foto o
musica di partenza) c'è un generatore a parte: [Motion Reels](motion-reels.md).

## Preparare un reel

Per Anna, il preparatore legge i **manifest di selezione**, non il contenuto
grezzo di `Anna_selezionate`: lì sono rimaste alcune vecchie copie non più
promosse. Copia un massimo di 30 immagini approvate dal primo o dal secondo
passaggio in una nuova cartella sotto `data/reel-projects/`:

```bash
python3 scripts/reel_media.py anna --limit 30
```

Per scegliere scatti precisi: `python3 scripts/reel_media.py anna --names
anna_00001_.jpg bridge_00020_.jpg` (solo se entrambi risultano promossi).

Per Aurora non c'è ancora un manifest visivo equivalente: scegli esplicitamente
file che hai esaminato tu, senza mescolarli per somiglianza del nome con quelli
di Anna:

```bash
python3 scripts/reel_media.py aurora \
  --source-dir /Users/opo/ComfyUI-Shared/output/HyperSpace \
  --names nome_esatto_1.png nome_esatto_2.png
```

Apri il Reel Editor, carica i file dalla cartella `media` appena stampata,
aggiungi una musica che hai diritto di usare, scegli stile e durata, poi genera
e scarica l'MP4. Il montaggio non cambia gli originali. Per i reel pubblici,
mantieni la dichiarazione che Anna e Aurora sono personaggi virtuali illustrati
nella didascalia o nel video.

L'opzione **Autocut** produce un MP4 di **30, 60 o 120 secondi esatti**: i tagli interni
restano sul ritmo e il bordo finale viene fissato alla durata scelta. Serve un
brano lungo almeno quanto la durata scelta a partire da «Inizio canzone».
«Libero/manuale» usa invece l'eventuale durata massima. La durata del file
non garantisce che una specifica traccia sia utilizzabile su TikTok: verifica
catalogo, disponibilità del frammento e diritti per il tipo di account.

## Disegnare il reel con un prompt

Dopo aver analizzato i media, scegli il profilo **Anna**, **Aurora** o **Altro
progetto**, descrivi in una sola casella il risultato desiderato e premi
**Prepara le impostazioni con HyperSpace**. Il profilo è un'etichetta di
montaggio: il modello non deve inventare biografie, scene o lyrics. Il brief
compila solo i controlli effettivamente supportati; rileggi la selezione e poi
premi **Genera**. La bozza conserva profilo e prompt anche se la pagina viene
riaperta.

L'editor cerca automaticamente un modello testuale locale dal control-plane
HyperSpace (`127.0.0.1:8085/v1/models`). Provider, modello e URL sono nelle
impostazioni avanzate; «Trova automaticamente HyperSpace» ripete la ricerca.
Si può impostare manualmente un altro provider. La configurazione salvata e i
preset personali sono in `data/tiktok-editor/`.

## Progetti da WebUI e analisi visiva

In chat HyperSpace e in WebUI il tool `reel_prepare_project` / `prepare_reel_project`
prepara fino a 30 file scelti per nome e può precompilare creator, brief e audio:
`source="anna"` accetta solo immagini promosse dalla selezione visiva;
`source="share"` legge i file presenti nella radice di `hyperspace_share`.
Il tool crea `hyperspace_share/reel-projects/<id>/media` e un manifest, senza
generare o pubblicare video. Metti prima foto/clip e musica in `hyperspace_share`;
indica i nomi esatti dei media e il nome audio (`audio_filename`) nella richiesta.
La musica viene copiata nel progetto, così resta disponibile al worker locale.
Anche `source="anna"` può indicare un `audio_filename` nell'area condivisa:
le immagini restano soggette alla verifica di approvazione.
Nell'editor apri **Progetti preparati in WebUI**,
premi **Aggiorna elenco**, scegli il progetto e premi **Apri progetto**. Poi
il creator e il brief vengono già caricati; usa **Analizza** per la prova manuale.

### Generazione giornaliera in coda revisione

I tool `reel_schedule_daily`, `reel_daily_status`, `reel_render_now` e
`reel_cancel_daily` gestiscono una singola schedulazione. La pianificazione
predefinita è ogni giorno alle 09:00 (`Europe/Rome`), con video da 30 secondi;
si può scegliere 30 o 60 secondi e specificare ora/fuso. Il Mac esegue il worker
LaunchAgent `com.hyperspace.reel-daily` una volta al minuto. I file completati e
verificati vanno in `hyperspace_share/reel-review/`; lo stato è in
`hyperspace_share/reel-schedules/status.json`. `reel_render_now` accoda una
singola prova immediata, mentre `reel_cancel_daily` ferma i render futuri.
La prova immediata conta come Reel del giorno; annullare o sostituire la
schedulazione elimina anche richieste immediate ancora in attesa. Il worker
prenota il giorno prima del render: in caso di errore si può riprovare con
`reel_render_now`, evitando tentativi automatici ripetuti. La cancellazione non
interrompe un render già partito.

Il Mac deve essere acceso e la sessione utente disponibile. Al risveglio il
worker recupera il render del giorno corrente se l'orario è già passato;
non genera l'arretrato dei giorni precedenti. I file del progetto sono un
insieme fisso: cambia il seed giornaliero per variare ordine, movimenti ed
effetti, senza generare nuove immagini. Il brief resta disponibile nella UI;
lo scheduler applica la ricetta `psychedelic_outline` descritta qui.

Il preset giornaliero usa il ritmo veloce psichedelico documentato sopra,
segmentazione persona/sfondo Vision su Mac e bordo luminoso ciano derivato dalla
maschera. Se il worker non riesce a segmentare/renderizzare o la durata non
corrisponde, registra `failed` e scarta il file parziale. Nessun Reel viene
pubblicato: ogni MP4 richiede revisione manuale. Se è già attiva un'altra
schedulazione, occorre passare `replace_existing=true` per sostituirla.

Collaudo sul Mac del 6 ottobre 2026: progetto `reel-0975a71f2283`, sette immagini
Anna già usate e `LEENALCHI_-_Bird_(mp3.pm).mp3`; render reale verificato di
30,0 s, 1080×1920, con video e audio. Schedulazione attivata alle 09:00
Europe/Rome. Anteprima:
`/Users/opo/hyperspace_share/reel-review/2026-10-06-anna-682294b893d7.mp4`.

### Prova di zoom e lampi sul soggetto da WebUI

Il tool `reel_subject_fx_preview` accetta il nome di un MP4 verticale 1080×1920
e di una traccia audio presenti nella radice di `hyperspace_share`. Può ricevere
anche `karaoke_filename`, un livello MOV trasparente già preparato, per mantenere
i sottotitoli sopra gli effetti. Accoda un render locale; `reel_subject_fx_status`
restituisce l'esito tramite `job_id`. I video completati finiscono in
`hyperspace_share/reel-review/` e richiedono revisione manuale.

Il worker usa Apple Vision per trovare il soggetto in primo piano ai colpi forti,
ingrandisce brevemente la sagoma e aggiunge luce ciano e piccoli archi elettrici
vicini al contorno. Le maschere vuote o troppo estese sono escluse: in quelle
scene il video originale resta visibile. La precisione varia con l'illustrazione.
Il tool è disponibile sia tra i tool WebUI sia tra i tool nativi del Control
Plane; il worker gira sul Mac insieme al Reel giornaliero, senza modificarne la
schedulazione.

La sezione **Analisi visiva delle scene** trova un modello VL locale dal
catalogo del control-plane e analizza le scene selezionate (massimo 20 per
volta). Mostra soggetto e sfondo rilevati e suggerisce colore, movimento e un
effetto breve sui beat forti per ogni clip. I suggerimenti vengono usati solo
se attivi la casella **Applica colori, movimenti e impatti**. La chiamata usa l'API
nativa Ollama sul Mac perché il proxy OpenAI-compatibile del control-plane
attualmente restituisce una risposta vuota per questo modello VL. Se il backend
è occupato da un altro modello, l'editor chiede di riprovare più tardi: non
scarica il modello in uso. Questo passaggio descrive la scena e non genera
maschere pixel.

La sezione **Persona e sfondo separati** usa invece la segmentazione persona
di Vision su macOS. Dopo **Analizza**, premi **Mostra maschera** per controllare
una scena: bianco indica la persona, nero lo sfondo. Attiva la casella e scegli
un color grade distinto per ciascun livello; puoi anche sfocare lo sfondo.
La funzione opera su foto e video. Per i video prepara una maschera a 4 frame
al secondo e la conserva nella cartella del progetto, quindi il primo render
può richiedere tempo. Il palo e gli oggetti non vengono riconosciuti come
persona e possono restare nello sfondo. I file originali non vengono modificati.
I controlli **Oscuramento sfondo**, **Luce sulla persona** e **Oscura la persona**
permettono anche un'apertura in cui si intravede solo la sagoma. Nella modalità crescendo,
**Croce di luce stroboscopica** mostra una croce luminosa per circa 0,11 secondi
sui beat rilevati negli ultimi 10 secondi. Il preset **BATTISTA crescendo 2 minuti**
attiva questi controlli con un inizio audio a 13,7 secondi.

La lavorazione specifica S24 con lyrics karaoke, movimento 60 fps e lampi
viola/verde sulle note è ancora documentata come ricetta sperimentale e non è
selezionabile dal generatore generale. Le ricette per Auto Forge restano draft:
lo sviluppo può proporre nuovi tool o preset, mentre attivazione e uso nel render
richiedono integrazione e revisione esplicite.

### Look psichedelico con bordo aderente alla persona

Il preset `Anna psichedelico contorno` prova il look richiesto: 2 tagli per beat,
ritmo dinamico, transizioni caotiche brevi, impatti RGB/flash/shake e grading
neon; la persona riceve un grade neon e lo sfondo un grade scuro separato.
Attiva la segmentazione macOS Vision e produce un bordo ciano derivato dalla
maschera della persona, con intensità e spessore regolabili. Il bordo è un alone
colorato sul profilo segmentato; non ricostruisce capelli o dettagli fini che la
maschera non abbia catturato. I flash/RGB/shake del preset restano effetti
globali sui beat, mentre il contorno segue la persona. La maschera non include
necessariamente il palo da pole dance.

La funzione è stata collegata a CLI, GUI, preset e bozza autosalvata. Il graph
FFmpeg del bordo è stato verificato con un render sintetico: il bagliore segue
la maschera e rimane confinato al profilo. La validazione con maschere Vision
reali resta da fare sul Mac fuori dal sandbox: Vision non riesce a creare il
proprio CVPixelBufferPool nell'ambiente confinato. Il render musicale completo
è ancora bloccato dal runtime Python 3.14 descritto sopra: Librosa/Numba non
importano. Non sono quindi stati prodotti gli MP4 da 30/60 secondi. Prima di
affidare un render completo, verificare una maschera reale in anteprima e fare
un render breve sul Mac.

## Prova automatica Anna con immagini a figura intera (5 ottobre 2026)

La clip `/Users/opo/Downloads/LEENALCHI_-_Bird_(mp3.pm).mp3` è disponibile e
dura 219,3 secondi. Sono stati selezionati e controllati 125 JPG singoli,
verticali e illustrati, con Anna a figura intera o quasi; tutti appartengono
alle immagini promosse dal secondo passaggio di selezione. Il progetto locale è
`data/reel-projects/anna-20261005-234633-1d8087/`, con elenco ordinato in
`manifest.json` e copie sotto `media/`. La selezione esclude immagini non
promosse, collage, pose sdraiate e materiale non coerente col set.

Sono richieste due anteprime: 30 e 60 secondi, 9:16 a 1080×1920 e 30 fps,
stile `smooth`, grade `dream`, 0,5 tagli per beat, aggancio ai transienti,
hook di 0,8 s e seed `20261005`. I percorsi di output previsti sono
`data/reel-preview/anna-bird-30s-figura-intera.mp4` e
`data/reel-preview/anna-bird-60s-figura-intera.mp4`.

**Stato render:** bloccato dal runtime esistente, non dal progetto o dai media.
L'unico ambiente dell'editor disponibile è
`/Users/opo/Downloads/tiktok_editor/.venv`, basato su Python 3.14.5, Librosa
1.0.0 e Numba 0.67.0. L'import di Librosa fallisce con `cannot cache function
'_zc_wrapper': no locator available`; `NUMBA_DISABLE_JIT=1` non risolve il
problema, e disattivare i decoratori Numba in un launcher provoca poi un
errore di dispatcher. La `.venv` del repository non contiene Librosa/NumPy.
Non sono stati creati MP4 finali né modificate le dipendenze esterne. Per
completare i render serve un runtime Python supportato e funzionante oppure una
correzione riproducibile del packaging Numba/Librosa.

Per rifare la selezione, passare nomi approvati esatti a
`scripts/reel_media.py anna --names ...`; l'approvazione unisce i due manifest
e la decisione del secondo passaggio prevale in caso di conflitto. Il bug è
stato corretto nello script, che prima consultava soltanto il primo passaggio.
Prossimi miglioramenti UI/tool emersi: filtro «figura intera» con revisione
visiva; set sequenziale riproducibile salvato nel manifest; profilo «ritratto
calmo»; batch 30/60 s da una sola selezione di media e brano; indicatore runtime
che rilevi Librosa/Numba non importabili prima di avviare un render lungo.
