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
