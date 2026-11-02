# SPDX-License-Identifier: Apache-2.0
# Guida Operativa di Onboarding Nodi V2 — HyperSpace Mesh 1.05

Guida per **Cips** e per chiunque debba ricostruire, configurare o estendere i nodi della mesh HyperSpace. Sostituisce il vecchio wizard monolitico di luglio 2026 (`onboarding/server.py`) introducendo un'architettura **modulare a profili**.

---

## 1. Perché l'Onboarding V2

Nel luglio 2026 HyperSpace configurava soltanto 6 variabili d'ambiente per Ollama. Oggi HyperSpace 1.05 integra:
- **Harness Agenti & UI**: OpenWork (desktop visuale), OpenCode (sidecar coding), OpenClaw/Strix (terminal agent), CLI-Anything & CLI-Hub (100+ tool professionali).
- **Memoria & Epistemica**: Native Hermes Memory Bridge (`:8098`, SQLite FTS5, livelli di evidenza E0–E4, Garbage Collector allucinazioni, Multi-cloud Vault).
- **Knowledge Graph**: Graphify AST (`:7871`, visualizzazione interattiva web).
- **Inference & Fine-Tuning**: Ollama (CUDA/Vulkan), Unsloth (LoRA fine-tuning su GPU), Flint 40B.
- **Creative & Media**: ComfyUI (SD1.5, custom nodes avatar), Voicebox/Kokoro TTS (sintesi vocale clonata), Reel Forge / MoneyPrinterTurbo (video reel).
- **Canali & Chatbot**: Bot Telegram aziendale (Vittoria PMI con vocali Whisper e fatturazione PDF), Open WebUI (`:3000`), SearXNG privacy search (`:8080`).

> [!IMPORTANT]
> **Regola d'Oro**: Nessun nodo deve tentare di eseguire tutto. Un nodo GPU deve concentrare VRAM e cicli su inferenza, training e rendering; una workstation Mac deve ospitare OpenWork, OpenCode e la memoria Hermes; un server cloud o hub deve governare il Control Plane, il Registry e i bot Telegram.

---

## 2. I 4 Profili di Nodo

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           I 4 PROFILI DI NODO HYPERSPACE                         │
├────────────────────┬─────────────────────────────────────────────────────────────┤
│ Profilo COMPUTE    │ Worker GPU: Ollama CUDA, Unsloth LoRA, ComfyUI, TTS, Video │
│ Profilo DEV        │ Workstation: OpenWork UI, OpenCode, OpenClaw, Hermes, Graph │
│ Profilo HUB        │ Gateway Mesh: Control Plane, Registry, Telegram Bot, WebUI  │
│ Profilo EDGE       │ Mobile/Watchdog: S24 Ultra Termux Vulkan, Web Node P2P      │
└────────────────────┴─────────────────────────────────────────────────────────────┘
```

### Profilo A: `compute` — Worker GPU & Media Rendering
- **Hardware tipico**: Laptop/Desktop con GPU discreta NVIDIA (es. HP OMEN RTX 3060/4080/4090, 8–24 GB VRAM) o server Linux GPU.
- **Ruolo Mesh**: `leaf` o `hub` di calcolo pesante.
- **Componenti Attivi**:
  1. **Ollama con accelerazione CUDA** (`docker compose --profile compute up -d ollama-nvidia` o host nativo).
  2. **Dichiarazione VRAM corretta** (`VRAM_GB=8` o superiore nel `.env`): impedisce al Control Plane di trattare il nodo come CPU-only (il routing assegna il 75% del punteggio a VRAM e GPU).
  3. **Unsloth Fine-Tuning**: script di addestramento LoRA in `scripts/unsloth/` su dataset sintetici CoT.
  4. **ComfyUI**: generazione immagini SD1.5 con modelli e LoRA (Anna, Aurora, Vittoria) su porta `:8188`.
  5. **Kokoro / Voicebox TTS**: motore vocale accelerato per sintesi audio.
  6. **Reel Forge / MoneyPrinterTurbo**: pipeline di montaggio video automatica su loopback `:7860`.
  7. **Node Container** (`node-1`): worker P2P con patch watcher su host.

### Profilo B: `dev` — Workstation & Agent Harness
- **Hardware tipico**: MacBook Air/Pro (Apple Silicon M-Series) o Linux PC di sviluppo.
- **Ruolo Mesh**: Postazione interattiva operatore / pair-programming.
- **Componenti Attivi**:
  1. **OpenWork Desktop UI** (`different-ai/openwork`): coworker desktop visivo collegato al Control Plane tramite token MCP (`MCP_TOKEN`).
  2. **OpenCode sidecar**: coding agent configurato via `opencode.jsonc` che interroga i modelli della mesh ed esegue tool di codice.
  3. **OpenClaw / Strix**: console e runner agentico multipiattaforma in terminale.
  4. **Hermes Memory Bridge** (`:8098`): processo host Python con SQLite FTS5 nativo, livelli di evidenza E0–E4 e Garbage Collector periodico.
  5. **Graphify Surface** (`:7871`): visualizzatore interattivo AST del codebase.
  6. **CLI-Anything & CLI-Hub**: meta-skill agentica per Blender, GIMP, FreeCAD, LibreOffice.

### Profilo C: `hub` — Gateway Mesh & Chatbot Produttivi
- **Hardware tipico**: Server Linux Cloud/VPS (Aruba, Hetzner, AWS) o Mini-PC always-on.
- **Ruolo Mesh**: `root` o `authority`.
- **Componenti Attivi**:
  1. **Control Plane** (`:8085`): orchestratore delle missioni, routing pesato, DAG e memory sync.
  2. **Registry** (`:8086`): heartbeat e auto-discovery dei peer P2P via LAN o Tailscale.
  3. **Telegram Business Bot**: bot aziendale PMI (persona Vittoria, ricezione note vocali Whisper, estrazione entità, preventivi e fatture PDF).
  4. **Open WebUI** (`:3000`): interfaccia chat web multi-modello per utenti aziendali.
  5. **SearXNG** (`:8080`): motore di ricerca privato per gli agenti della mesh.
  6. **Multi-Cloud Vault**: gestione snapshot cifrati e backup distribuito.

### Profilo D: `edge` — Mobile & Light Watchdog
- **Hardware tipico**: Smartphone Android (Samsung S24 Ultra con Termux), Web Node browser, o Raspberry Pi.
- **Ruolo Mesh**: `edge` / failover monitor.
- **Componenti Attivi**:
  1. **Llama.cpp / Ollama Vulkan**: inferenza locale ultra-leggera per task di guardia.
  2. **Watchdog Heartbeat**: monitoraggio della salute dei nodi primari e segnalazione allarmi via Telegram.

---

## 3. Matrice delle Porte di Rete

Per evitare collisioni durante il setup contemporaneo dei componenti:

| Servizio | Porta Default | Protocollo | Profilo Tipico | Nota di Rete |
|---|---|---|---|---|
| **Control Plane** | `8085` | HTTP / SSE | `hub` | Esposto ai peer mesh o via Tailscale |
| **Registry** | `8086` | HTTP | `hub` | Auto-discovery e battiti nodi |
| **Node Worker** | `8084` (o `8081`) | HTTP | `compute` / `dev` | Endpoint P2P del nodo locale |
| **Hermes Memory Bridge** | `8098` | HTTP Bearer | `dev` / `hub` | Host nativo, SQLite FTS5 |
| **Graphify Knowledge Graph** | `7871` | HTTP | `dev` | Superficie AST codice |
| **Ollama Inference** | `11434` | HTTP / OpenAI | `compute` / `dev` | API locale modelli |
| **Open WebUI** | `3000` | HTTP | `hub` | Portale chat browser |
| **SearXNG** | `8080` | HTTP | `hub` | Metamotore search privato |
| **ComfyUI** | `8188` | HTTP / WS | `compute` | Backend generazione immagini |
| **TikTok Editor / Reel Forge** | `7860` | HTTP Gradio | `compute` | Montaggio video loopback |
| **Cockpit Diagnostica** | `8090` | HTTP | `hub` / `dev` | Monitor di stato e telemetry |

---

## 4. Integrazione dei Sottosistemi Richiesti da Cips

### A. OpenWork & OpenCode Sidecar
- **OpenWork** è una desktop app Electron (`different-ai/openwork`) che comunica con HyperSpace via MCP (*Model Context Protocol*).
- **Configurazione**:
  1. Assicurarsi che nel `.env` del Control Plane sia definito un token MCP valido:
     ```bash
     MCP_CLIENTS=openwork=hyperspace_openwork_local_client_token_32chars
     MCP_CLIENT_TOOLS=openwork=code_sandbox,omega_query,web_search
     ```
  2. In OpenWork / OpenCode, inserire la configurazione in `opencode.jsonc`:
     ```json
     {
       "mcp": {
         "hyperspace-mesh": {
           "type": "local",
           "command": [
             "/path/to/hyperspace-agi-1.04/.venv/bin/python",
             "/path/to/hyperspace-agi-1.04/scripts/mcp_stdio_bridge.py"
           ],
           "enabled": true
         }
       }
     }
     ```
  3. Lo script [`scripts/mcp_stdio_bridge.py`](../scripts/mcp_stdio_bridge.py) effettua il bridge tra stdio e l'endpoint HTTP `/mcp` del Control Plane (`:8085/mcp`).

### B. OpenClaw & Strix
- Per usare **OpenClaw** o **Strix** come harness agentico a riga di comando:
  1. Installare la skill o registrare la compatibilità in `AGENTS.md`:
     ```bash
     graphify openclaw install
     ```
  2. I comandi generati vengono inoltrati a `code-sandbox` per esecuzione isolata senza sporcare l'host.

### C. Unsloth Fine-Tuning
- Riservato al profilo `compute` con GPU NVIDIA:
  1. Cartella dedicata: `data/unsloth/`.
  2. Gli script in `scripts/unsloth/` leggono i dataset sintetici CoT (`data/synthetic_cot_dataset.jsonl`) generati durante i sogni notturni.
  3. Esecuzione tramite script dedicato PowerShell o Bash (`run_omen_wsl2_training.ps1`).

### D. Native Hermes Memory Bridge
- Il backend di memoria nativo `scripts/hermes_memory_bridge.py` gira sull'host per possedere `MEMORY.md` e `USER.md` senza dipendenze Docker.
- Avvio come servizio di background:
  ```bash
  .venv/bin/python scripts/hermes_memory_bridge.py
  ```
- Supporta azioni `quarantine`, `restore`, `revoke`, `refute`, `critique` e `downgrade`.

### E. Bot Telegram & Canali Utente
- Sul profilo `hub`, avviare il daemon aziendale:
  ```bash
  .venv/bin/python scripts/telegram_business_bot.py
  ```
- Gestisce la persona Vittoria PMI: riconosce la voce con Whisper, effettua ricerche web su SearXNG ed emette preventivi/fatture PDF conformi.

---

## 5. Procedura di Onboarding Automatizzata (`scripts/node_onboarding.py`)

Per evitare errori manuali di configurazione, è disponibile lo strumento ufficiale di onboarding:

### Esecuzione Interattiva
```bash
python scripts/node_onboarding.py
```
Lo script:
1. Analizza l'hardware locale (OS, CPU, RAM totale/libera, GPU discreta/unificata, VRAM).
2. Mostra il profilo consigliato in base all'hardware rilevato.
3. Permette a Cips di personalizzare i moduli (OpenWork, Unsloth, ComfyUI, Hermes, Telegram, ecc.).
4. Genera o riconcilia il file `.env` applicando i valori corretti (`VRAM_GB`, `NODE_TIER`, `MEMORY_BACKEND`, ecc.).
5. Stampa la lista esatta dei comandi Docker e dei servizi host da avviare.

### Esecuzione Non-Interattiva (per Script di Provisioning)
```bash
# Esempio su OMEN (profilo compute GPU)
python scripts/node_onboarding.py --profile compute --apply

# Esempio su Mac Workstation (profilo dev)
python scripts/node_onboarding.py --profile dev --apply

# Esempio su Server Cloud (profilo hub)
python scripts/node_onboarding.py --profile hub --apply
```

### Moduli extra (facoltativi, su qualunque profilo)

Il profilo dice cosa *è* il nodo; i moduli extra aggiungono cosa ci *fai*. Si scelgono per
pacchetto, nel menu interattivo o con `--package` / `--with`:

```bash
python scripts/node_onboarding.py --profile dev --package agenti --package verifica
python scripts/node_onboarding.py --profile compute --with qwenputer
```

| Pacchetto | Scegli se… | Moduli |
|---|---|---|
| `agenti` | più agenti lavorano in parallelo sullo stesso repo | `orca`, `openwork` |
| `documenti` | il nodo lavora su Word/Excel/PDF per clienti o PMI | `onlyoffice`, `anydoc`, `unlimited_ocr` |
| `verifica` | analizzi binari senza eseguirli o ti serve calcolo deterministico | `rea`, `qwenputer` |

Per ogni modulo il piano stampa **stato** (verificato / sperimentale / non provato), requisiti
e comando d'installazione per il sistema operativo. Il registro è `EXTRA_MODULES` in
`scripts/node_onboarding.py`. Laya non è un extra: va su ogni nodo.

---

## 6. Le 4 Trappole Note da Evitare

1. **La trappola della VRAM a 0 su Windows**:
   - `setup.ps1` non sovrascrive `.env` se già esistente. Se `.env` non contiene `VRAM_GB=8` (o la VRAM della scheda), il nodo si registra con `vram_gb=0.0` e il Control Plane lo penalizza nel 75% dei punteggi di routing.
2. **Il flag `--build` è obbligatorio**:
   - I container Docker (`control-plane`, `node-1`) hanno il codice integrato nell'immagine. Eseguire sempre `docker compose up -d --build` dopo un `git pull`.
3. **BOM in PowerShell**:
   - Su Windows non usare `Set-Content -Encoding UTF8` perché PowerShell 5.1 inserisce il BOM e rende il `.env` illeggibile a Docker Compose. Lo script `sync_env_windows.ps1` e il nuovo `node_onboarding.py` gestiscono UTF-8 senza BOM.
4. **Token MCP minimo 32 caratteri**:
   - Qualsiasi client esterno (OpenWork, Claude Desktop) che si connette a `/mcp` deve usare un token lungo almeno 32 caratteri, altrimenti `shared/mcp_auth.py` rifiuta la richiesta.
