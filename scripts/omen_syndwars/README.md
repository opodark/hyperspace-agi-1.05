# Prove nel gioco vero (OMEN, distro `swbuild`)

Script usati da `scripts/syndwars_bisect.py` e a mano. Percorsi (`/opt/sw`, `/mnt/c/Users/opoda/swbuild`) e
nomi di file sono quelli di OMEN: vanno adattati altrove. Non sono ancora parametrizzati.

- `evalset.sh`: compila un sottoinsieme di bozze (tar da `syndwars_patch.py`), fa girare il replay fino al turno 400
  e confronta `things`, `sthings` e mappa con il riferimento. Applica `found = 0` in `people.c`.
- `ingame_calls_gdb.py`, `ingame_calls_run.sh`, `ingame_calls_cmp.py`: chiamano ogni bozza dal gioco al turno 400
  con quattro serie di argomenti, ripristinando la memoria tra una chiamata e l'altra, e confrontano due binari.
  Servono `set scheduler-locking on` e `unwindonsignal on` (il gioco ha thread audio e timer).
- `trace_calls_gdb.py`: stato prima e dopo ogni chiamata di una funzione; `stackfill_gdb.py`: riempie lo stack sotto
  `person_move` per smascherare letture non inizializzate.
- Con `fifties_per_gameturn = 400` il replay e' deterministico; senza, i punti di arresto lo alterano.

## Asset a risoluzione doppia e schermo HD

Il codice sta nel repository del gioco. I file si aggiungono in `data/` accanto agli originali; senza di essi il gioco non cambia.

- `make_hires_pages.py`: `tex00h.dat` ... `tex03h.dat` (512x512, 8 bit). Le pagine 4 e 5 restano originali: sono scritte a runtime con passo 256.
- `make_hires_sprites.py`: `mspr-Nh.dat/.tab` per i sei colori di impermeabile. Colori dall'originale, dettaglio dall'IA, profilo con Scale2x.
- Risoluzione: in `config.ini` del gioco, per esempio `ResGameHi="1920x1080x8"` (massimo 2560x1440).
- `hires_check.sh`: costruisce e confronta stato, pixel e tempi fra master, ramo senza asset e ramo con asset.

Tutti i dati generati derivano dagli asset EA/Bullfrog: restano solo in locale.

## Bozze applicate al sorgente

- `../syndwars_apply.py`: sostituisce gli stub con le bozze verificate su una copia di lavoro.
- `evalad.sh` con `../syndwars_bisect.py --worktree ...`: bisezione su un orizzonte di turni a scelta. I riferimenti `/tmp/k_a_*` si creano con `hires_check.sh`.
- Attenzione: `evalset.sh` ripristina solo i file delle bozze con `pristine.tar`; dopo prove su `bflibrary/` o `swrendersoft/` l'albero di build resta contaminato. Prima di un riferimento si rifa' `/src` dal repository.
