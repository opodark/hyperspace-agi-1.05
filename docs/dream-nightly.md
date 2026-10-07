# Il sogno di stanotte: ciclo, registro, monitor, scheduler

Il sogno illustrato di Anna e Aurora (`docs/growth-strategy.md` §4, *Il sogno di
stanotte*) è una pipeline, non una funzione: il testo nasce dal modello locale, lo
sketch lo disegna il Mac (ComfyUI), il post finisce su Instagram. Questa pagina
dice come si osserva e come si tiene viva — perché il suo guasto tipico non è un
errore: è un **silenzio**. Notti senza sogni con il ciclo acceso si leggono come
"tutto tranquillo" finché non si guarda.

## Il percorso di un sogno

| Passo | Chi lo fa | Dove si vede |
|---|---|---|
| 1. decide se tocca | `dream_loop` (control-plane) o un tick dello scheduler | registro, fase `saltato` + motivo |
| 2. scrive la scena | modello locale (`build_dream_prompt`) | diario `tipo=sogno`, fase `scritto` |
| 3. accoda lo sketch | `_accoda_sketch` → coda immagini | fase `sketch` + job in `image-jobs.json` |
| 4. disegna | bridge sul Mac (ComfyUI) | fase `disegnato`, `file` sulla voce |
| 5. racconta e pubblica | `_sogno_da_immagine` + `_instagram_publish_voce` | `instagram_status` `published`/`failed`, fase `pubblicato`/`fallito` |

Un sogno che non arriva in fondo **resta alla fase precedente**: è questo che il
monitor mostra, ed è l'unica risposta utile a "com'è andata stanotte?".

## I tre strumenti

**1. Registro dettagliato** — `data/control-plane/dream-log.jsonl`
(`shared/dream_log.py`): una riga JSON per ogni passo, legata dalla stessa
`voce_id`. Append-only, `fsync` a ogni riga, righe illeggibili saltate in lettura
(il registro serve a capire, non a fallire). I salti sono deduplicati: «fuori
finestra» si scrive una volta, non a ogni giro del loop (`salto_da_scrivere`).

**2. Monitor** — `python3 scripts/dream_monitor.py`
- fotografia testuale: salute del ciclo, soglie, quota del giorno, un sogno per
  riga con la sua fase, gli ultimi giri a vuoto con il motivo;
- `--json` stampa **lo stesso payload** di `GET /dreams/nightly/status`;
- `--watch 60` per tenerlo aperto; esce **1** quando il verdetto è `muto`
  (cron/launchd: un monitor che esce sempre 0 non sveglia nessuno).

Verdetti: `ok` (ha sognato oggi), `attenzione` (un giorno senza sogni: l'ultimo
avviso utile), `muto` (due o più: il ciclo è acceso ma tace), `spento`
(`DREAM_LOOP_ENABLED` non è `true`).

**3. Scheduler** — `scripts/dream_scheduler.py` + `integrations/sogni/`
`com.hyperspace.dream-nightly.plist`
Un tick ogni 30 minuti chiama `POST /dreams/nightly/tick`. Il tick applica **le
stesse guardie** del loop (`_decisione_sogno`: finestra, quota, intervallo
minimo), quindi non può produrre un secondo sogno: quando non tocca, risponde
`saltato` con il motivo. Esiste per il caso peggiore — il thread del loop che
muore in silenzio, che è già successo.

```bash
# installazione (una volta)
cp integrations/sogni/com.hyperspace.dream-nightly.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hyperspace.dream-nightly.plist
# diagnosi
python3 scripts/dream_monitor.py
tail -n 20 data/dream-nightly.log
```

## Configurazione (`.env`)

| Chiave | Default | Cosa fa |
|---|---|---|
| `DREAM_LOOP_ENABLED` | `false` | accende il ciclo (a caldo via `POST /config/env`) |
| `DREAM_NIGHT_START_HOUR` / `_END_HOUR` | `0` / `8` | finestra notturna, nel fuso sotto |
| `DREAM_TIMEZONE` | `Europe/Rome` | il fuso in cui la finestra e la quota sono "oggi" |
| `DREAM_PER_AUTHOR_PER_DAY` | `2` | tetti giornalieri per autrice |
| `DREAM_LOOP_INTERVAL_S` | `7200` | distanza minima fra due sogni |
| `DREAM_LOOP_CHECK_S` | `300` | ogni quanto il loop ricontrolla |
| `DREAM_IDLE_S` | `10800` | sognare anche fuori finestra dopo tanta inattività |
| `DREAM_LOG_FILE` | `data/dream-log.jsonl` | dove vive il registro dettagliato |
| `INSTAGRAM_DREAM_PUBLISH_ENABLED` | `false` | pubblica sogni e poesie finite |
| `CONNECTOR_READ_ONLY` / `CONNECTOR_WRITE_TOOLS` | `true` / — | la policy: senza allowlist la pubblicazione resta **muta** (vedi `docs/connectors.md`) |

## Rotte

- `GET /dreams/nightly/status` — il monitor (sola lettura, come `/logs`).
- `POST /dreams/nightly/tick` — un giro del ciclo, dietro
  `X-Hyperspace-Network-Token` (`NETWORK_ADMIN_TOKEN`).

Le rotte sono **nuove**: finché il control-plane non riparte, rispondono 404 e lo
scheduler registra l'errore in `data/dream-scheduler.json` senza fallire. Il
riavvio è dell'operatore: `docker compose restart control-plane` (i job immagine e
il diario sono su file, quindi sopravvivono).

## Perché esiste (misurato il 2026-10-06)

Tre notti senza sogni con `DREAM_LOOP_ENABLED=true` e nessuno se n'è accorto: il
sintomo era indistinguibile dalla normalità. Guardando i dati reali col monitor
sono emersi due fatti che nessun errore diceva:

- il sogno del `2026-10-06 02:58` era ancora **`sketch in coda`** (il Mac non aveva
  ancora disegnato) — cioè la pubblicazione non era "fallita", non era ancora
  iniziata;
- `sogno-ff895fd6` (01/10 02:47) era fermo in **`in attesa di sketch`**: nessun job
  accodato, nessuna traccia. Una notte morta a metà, invisibile.

## Verifica

```bash
python3 -m pytest tests/test_dream_schedule.py tests/test_dream_log.py \
                tests/test_dream_monitor.py tests/test_dream_nightly.py -q
python3 scripts/dream_monitor.py --json | head -40
```

I test coprono: quota nel fuso locale, riapertura della finestra, fasi della
pipeline, dedup dei salti, robustezza del registro (righe rotte, percorsi non
scrivibili), indipendenza dall'ordine dell'elenco, verdetto `muto`, guardiania
della rotta `tick` e — chiusura di un buco dichiarato in `docs/connectors.md` — il
fatto che `INSTAGRAM_DREAM_PUBLISH_ENABLED=true` **non** pubblichi nulla quando la
policy resta quella di default.
