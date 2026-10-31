# Nodo mobile Android (Termux)

Un telefono Android entra nella mesh come nodo con `NODE_TIER=mobile`. Di giorno
resta in heartbeat ed è una console; di notte, in carica, lavora come worker.
Primo dispositivo di riferimento: Samsung S24 Ultra, 12 GB di RAM.

## Cosa serve sul telefono

Dalla **stessa fonte** (F-Droid oppure GitHub, non il Play Store):

- **Termux**
- **Termux:API**: batteria e temperatura (`termux-battery-status`)
- **Termux:Boot** (facoltativo): avvio all'accensione, va aperto una volta
- **Tailscale** (app Android): il telefono diventa raggiungibile dagli hub

Nelle impostazioni Android: Termux su *Batteria → Senza restrizioni*.
Consigliata la protezione batteria di Samsung (carica ferma all'80%) per le notti
in carica: il gate la riconosce come "in presa".

## Installazione

Dentro Termux, con la VPN Tailscale attiva:

```bash
bash join-mesh-android.sh
```

Lo script chiede l'URL del control-plane (l'IP Tailscale del Mac), la finestra
di lavoro, le soglie e il modello. Scrive solo in `~/.00mesh`,
`~/.termux/boot/00mesh` e `$PREFIX/bin/00mesh`. Scarica dal repository solo
`node/`, `shared/` e `scripts/android/` (sparse checkout).

Al primo giro FastAPI può richiedere la compilazione di `pydantic-core` (Rust):
10-20 minuti, una volta sola.

Per provare un branch diverso da `main`:

```bash
REPO_BRANCH=nome-branch bash join-mesh-android.sh
```

## Uso

```bash
00mesh status         # nodo, batteria, gate, peer
00mesh bench          # token/s e temperatura del modello configurato
00mesh bench qwen3:8b # prova un altro modello
00mesh pull <modello>
00mesh logs [node|proxy|ollama]
00mesh config         # modifica ~/.00mesh/node.env, poi 00mesh restart
00mesh watch          # watchdog unico: telefono, mesh, telemetria, ricerca, sogni
00mesh watch --every 60 | --once | --no-notify
00mesh stop | start | restart | update
```

## Il gate di lavoro

`shared/mobile_gate.py`. Il nodo accetta lavoro solo se valgono **tutte**:

| Variabile | Default | Regola |
|---|---|---|
| `MOBILE_REQUIRE_CHARGER` | `true` | collegato al caricatore |
| `MOBILE_MIN_BATTERY_PCT` | `40` | batteria sopra la soglia |
| `MOBILE_MAX_TEMP_C` | `41` | ferma il lavoro a questa temperatura della batteria |
| `MOBILE_RESUME_TEMP_C` | `38` | riparte solo sotto questa (isteresi) |
| `MOBILE_WORK_WINDOW` | vuota | es. `23:00-07:00`; vuota = sempre |

### Ruolo: monitor e watchdog 24/7, non worker (`MOBILE_ROLE=failover`)

Il telefono è acceso sempre, ma non per fare inferenza per gli altri: con
`MOBILE_ROLE=failover` il gate resta **sempre chiuso** (motivo `failover_only`),
qualunque siano caricatore, batteria, temperatura e `MOBILE_WORK_WINDOW`. Il CP
non gli manda lavoro e i sogni non girano sul telefono. Lavora invece come:

- **watchdog 24/7** (`watchd`, parte con `00mesh start`): controlla Mac, mesh,
  sogni, missioni e il telefono stesso, notifica gli allarmi (Termux:API) e il
  rientro, scrive lo stato in `~/.00mesh/run/watch.json` e apertura/chiusura degli
  allarmi in `~/.00mesh/logs/watchdog.ndjson`. Si spegne con
  `WATCHDOG_ENABLED=false`. `watch.json` (campo `schema: 1`) è l'interfaccia per
  la futura app companion Android;
- **console di debug estrema** (Pocket Hub): in caso di cataclisma, cioè con il
  Mac irraggiungibile per 3 controlli di fila, il suo modello piccolo risponde
  ad Anna via `anna chat` e il registro delle conversazioni va a Hermes al
  ritorno. Vedi [pocket-hub.md](pocket-hub.md). Sostituire il CP o i modelli degli
  altri nodi è raro per progetto.

Attenzione: **togliere la finestra di lavoro non basta** per fermare il lavoro —
una finestra vuota significa "sempre aperto", il contrario. Si cambia con
`00mesh role failover|worker` (scrive `MOBILE_ROLE` in `node.env`; poi
`00mesh restart`). Il setup nuovo parte già in failover; senza `MOBILE_ROLE` il
comportamento è quello di prima.

Con il gate chiuso il nodo risponde `503` con `type: node_power_gated` e si
dichiara `degraded` in `/status`, `/metrics` e nel registry: il control-plane
smette di sceglierlo invece di ricevere errori a ripetizione. Anche i sogni
(`DREAM_ENABLED`) rispettano il gate. `/status` espone il dettaglio in
`mobile_gate`.

Senza Termux:API la batteria è sconosciuta e il nodo si considera **a batteria**:
su Android non vale il ripiego "presa fissa" degli altri sistemi.

## Rete

Il nodo ascolta solo sull'IP Tailscale del telefono (`NODE_BIND`), non sulla
Wi-Fi locale. Ollama e ollama-proxy ascoltano solo su `127.0.0.1`. Se all'avvio
la VPN è spenta, il nodo parte in locale e `00mesh status` lo segnala:
`00mesh restart` dopo aver attivato Tailscale.

## Accelerazione Hardware GPU (Adreno 750 / Vulkan)

Per superare il vincolo CPU di Ollama e sfruttare la GPU Adreno 750 dello Snapdragon 8 Gen 3:

```bash
bash scripts/android/setup_vulkan_adreno.sh
```

Lo script compila `llama.cpp` con flag `-DGGML_VULKAN=1` linkando il loader Vulkan nativo di Android.
Una volta completato, consente di avviare il server hardware-accelerated con:

```bash
00mesh-vulkan-start
```

Con un modello come **Qwen2.5 3B Q4** o **Llama 3.2 3B Q4**, la velocità passa dai ~2 tok/s su CPU a **oltre 20-25 tok/s su GPU Adreno 750**, con temperature sotto i 37°C.

## Limiti noti

- Ollama in Termux usa la CPU: niente GPU né NPU del telefono. I numeri reali
  vanno misurati con `00mesh bench` (vedi tabella sotto, da riempire).
- Android può chiudere processi in background nonostante il wake-lock se
  l'ottimizzazione batteria resta attiva per Termux.
- Questo percorso è per il proprio telefono. Il pacchetto pubblico (Play Store)
  sarà un'app nativa separata: Termux non è distribuibile agli utenti finali.

## Misure

| Data | Telefono | Modello | Prompt tok/s | Generazione tok/s | Temp. inizio → fine |
|---|---|---|---|---|---|
| | S24 Ultra | | | | |

## Watchdog unico (`00mesh watch`)

Una schermata (la stessa logica gira in background come `watchd`) che si aggiorna ogni 30 s (`--every S` o `ANNA_WATCH_S`) con: il
telefono (batteria, temperatura, gate di lavoro, Pocket Hub e registro da
riconsegnare), la mesh (nodi attivi/degradati, heartbeat del CP), la telemetria
(richieste e token, generazioni in corso, modello più usato), la ricerca
(missioni di Mission Control in corso, task fatti, esito dell'ultima) e i sogni
(notturni e development dream). In cima il verdetto `● OK` o `▲ ATTENZIONE n` con
gli allarmi. Con Termux:API installato, un allarme **nuovo** diventa una
notifica (non quelli già noti, non al primo giro). `--once` fa una passata sola
ed esce con codice 1 se ci sono allarmi.

Se il Mac non risponde passa al Pocket Hub del telefono e lo dice. I nodi
`mobile` non generano allarme "degradato": a gate chiuso lo sono per progetto.
Sola lettura: non scrive e non riavvia nulla.
