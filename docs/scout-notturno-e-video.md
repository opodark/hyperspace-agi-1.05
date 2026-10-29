# Scout notturno (browser-use) e video (MoneyPrinterTurbo)

Due servizi separati dalla mesh, ognuno nel proprio container Docker.

## 1. Scout notturno isolato

Ogni notte alle 02:40 legge le segnalazioni raccolte da `trend_scout_reach`
(`data/control-plane/trend_inspirations.json`), apre fino a 6 pagine nuove e
scrive un approfondimento per ognuna.

| Cosa | Dove |
|---|---|
| Codice | `integrations/browser-scout/scout.py` |
| Avvio | `integrations/browser-scout/run-scout.sh` |
| Pianificazione | `integrations/browser-scout/com.hyperspace.browser-scout.plist` |
| Risultati dell'ultima notte | `data/scout/latest.json` |
| Storico | `data/scout/deep_dives.jsonl` |
| Log | `data/scout/scout.log` |
| Cockpit | riquadro «Scout notturno», API `GET /api/scout/deep-dives` |

### Isolamento

- **Container**: vede solo il file delle segnalazioni (sola lettura) e
  `data/scout`. File system in sola lettura, nessun privilegio, limiti di
  memoria, CPU e processi. Non vede file, portachiavi, sessioni o Docker del Mac.
- **Browser**: profilo nuovo per ogni pagina, cancellato alla fine. Nessun
  cookie, nessun account, nessuna estensione, nessun download.
- **Navigazione**: solo il sito della pagina e i suoi sottodomini. Indirizzi
  IP, `localhost` e reti interne (LAN, tailnet, `.local`, `.ts.net`) sono
  bloccati: lo scout non può raggiungere il cockpit o i nodi.
- **Azioni**: disattivate tutte quelle che scrivono o inviano: moduli, tasti,
  upload, file, JavaScript, ricerche su altri motori.
- **Siti saltati**: social con login (X, Facebook, Instagram, LinkedIn,
  TikTok, Threads), video (YouTube, Vimeo) e file come PDF, che il browser
  non legge come pagina.
- **Output**: il testo delle pagine è trattato come dato. Il risultato viene
  ripulito, troncato e marcato `"untrusted": true`. Nessuna parte della mesh
  lo esegue.

### Installazione sul Mac

```
cd ~/hyperspace-agi-1.04
docker build -t hyperspace/browser-scout:0.13.14 integrations/browser-scout
integrations/browser-scout/run-scout.sh --dry-run     # quali pagine sceglierebbe
integrations/browser-scout/run-scout.sh               # un giro completo
cp integrations/browser-scout/com.hyperspace.browser-scout.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.hyperspace.browser-scout.plist
```

Modello: per impostazione predefinita Flint su Ollama dell'ASUS
(`http://100.64.31.18:11434`). Per cambiarlo, crea
`integrations/browser-scout/scout.env`:

```
SCOUT_LLM_PROVIDER=ollama
SCOUT_LLM_URL=http://host.docker.internal:11434
SCOUT_LLM_MODEL=qwen3.8-9b-heretic-uncensored-mtplx
SCOUT_LIMIT=6
```

Per un server compatibile OpenAI (llama-server sull'OMEN):
`SCOUT_LLM_PROVIDER=openai` e `SCOUT_LLM_URL=http://100.104.238.125:8081/v1`.

I modelli piccoli completano meno pagine dei grandi: i fallimenti restano nel
registro con il motivo, e le pagine scadute per tempo si riprovano la notte dopo.

## 2. MoneyPrinterTurbo

Da un tema a un video verticale con voce italiana, sottotitoli e video di
repertorio. Il video non viene pubblicato: finisce in `data/reels/mpt/` con un
file `.json` accanto, e `da_rivedere` resta vero.

| Cosa | Dove |
|---|---|
| Servizio | `integrations/moneyprinter/docker-compose.yml` (API su `127.0.0.1:8095`) |
| Configurazione | `integrations/moneyprinter/config.toml` (creato da `setup.sh`, fuori da git) |
| Ponte dalla mesh | `integrations/moneyprinter/mpt_bridge.py` |
| Musica | `integrations/moneyprinter/music/` + `music/licenze.json` |
| Video pronti | `data/reels/mpt/` |

- **Testi**: modello locale via Ollama (`flint:latest` sull'ASUS).
- **Voce**: Kokoro del Mac (`scripts/kokoro_tts_service.py`, porta 8880),
  voci `if_sara`, `im_nicola`, `documentarista`, `giornalista`, `poetica`,
  `teatrale`.
- **Video di repertorio**: Pexels (serve una chiave gratuita).
- **Musica**: i 29 brani inclusi in MoneyPrinterTurbo vengono da video YouTube
  senza licenza chiara, quindi sono disattivati. Si usano solo brani messi in
  `music/` e registrati in `music/licenze.json` con licenza e fonte. Senza
  brani registrati il video esce senza musica.
- **Pubblicazione automatica**: spenta.

### Installazione sul Mac

```
cd ~/hyperspace-agi-1.04
PEXELS_API_KEY=la-tua-chiave integrations/moneyprinter/setup.sh
.venv/bin/python scripts/kokoro_tts_service.py &          # se non è già attivo
docker compose -f integrations/moneyprinter/docker-compose.yml up -d
.venv/bin/python integrations/moneyprinter/mpt_bridge.py "Che cos'è una mesh di AI locali"
```

Interfaccia web (facoltativa):
`docker compose -f integrations/moneyprinter/docker-compose.yml --profile webui up -d`
e poi http://127.0.0.1:8501.

Esempio di `music/licenze.json`:

```json
{
  "brani": [
    {"file": "ambient-01.mp3", "licenza": "CC BY 4.0", "fonte": "https://…", "attribuzione": "Titolo — Autore"}
  ]
}
```

Se la licenza chiede l'attribuzione, il testo è nel `.json` accanto al video:
va riportato nella descrizione quando lo si pubblica.

## 3. Voce clonata (Voicebox) per HyperSpace e MoneyPrinterTurbo

Voicebox (app sul Mac, API su `127.0.0.1:17493`) tiene i profili di voce clonata e i motori
`qwen` (Qwen3-TTS 1.7B/0.6B), `qwen_custom_voice`, `luxtts`, `chatterbox`, `chatterbox_turbo`, `tada`, `kokoro`.
Il testo non esce dal Mac. L'app deve essere aperta.

| Cosa | Come |
|---|---|
| Elenco profili | `python scripts/diagnostics/voicebox_tts.py list` |
| Un testo con una voce | `… say "Albi ita" "Testo" --engine qwen -o prova.wav` |
| Confronto fra motori | `… compare "Albi ita" "Testo" --engines qwen,chatterbox --out-dir /tmp/confronto` |
| Da HyperSpace / Open WebUI | servizio `:8880`, `POST /v1/audio/speech` con `"voice": "voicebox:Albi ita@qwen"` |
| Da MoneyPrinterTurbo | `mpt_bridge.py "Tema" --voice "voicebox:Albi ita@qwen"` (diventa `kokoro:voicebox:…`) |

`voicebox:<profilo>[@motore]`: il profilo si cerca per nome o id; senza motore vale quello del profilo, poi `qwen`.
`GET /v1/audio/voices` elenca anche i profili Voicebox. Codice: `shared/voicebox_client.py`.

Note: la prima generazione carica il modello e può richiedere oltre un minuto (misurato 76 s con Qwen, 51 s con
Chatterbox su un testo di una frase); le successive sono più rapide. Il servizio `:8880` va riavviato dopo l'aggiornamento
(`scripts/start-all-macos.sh`). Non verificato: un video completo in MoneyPrinterTurbo con voce Voicebox
(manca `PEXELS_API_KEY`), in particolare che MPT passi intatto il nome con spazi e `@`.
