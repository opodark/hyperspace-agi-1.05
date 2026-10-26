# Manuale Operativo HyperSpace AGI — Comandi, R&D e Cluster Tri-Nodo

> **Versione**: 1.05.0 Sovereign Mesh  
> **Data di Riferimento**: Ottobre 2026  
> **Ambiente**: Mac M5 Hub (Control & Orchestrator), HP OMEN 16 (GPU Worker), ASUS V16 (Inference Node)

---

## 1. Topologia e Indirizzamento dei 3 Nodi

HyperSpace AGI opera come una mesh decentralizzata e sovrana distribuita su tre macchine fisiche interconnesse via rete locale e overlay crittografico Tailscale:

| Nodo | Indirizzo di Rete | Ruolo Primario | Servizi & Porte Attive |
|---|---|---|---|
| **Mac M5 Hub** | `localhost` / `127.0.0.1` | Authority, Control Plane, Orchestratore R&D | • **Operations Cockpit & HyperDev Studio**: `:8090`<br>• **Control Plane API & Registry**: `:8085`<br>• **Ollama Decision Engine (tev1 System 1)**: `:11434`<br>• **ComfyUI Local**: `:8188` |
| **HP OMEN 16** | `100.104.238.125` | GPU Worker Pesante (NVIDIA RTX 3070 8GB VRAM) | • **Node API ECDSA**: `http://100.104.238.125:8081`<br>• **ComfyUI GPU Rendering**: `:8188`<br>• **Worker Inferenza Pesante**: Liquid AI LFM 2.5 24B / 8B |
| **ASUS V16** | `100.64.31.18` | High-VRAM Inference Worker | • **Ollama Cluster Node**: `http://100.64.31.18:11434`<br>• **Node API**: `http://100.64.31.18:8081`<br>• **Modelli**: Flint 40B, LFM2.5 24B, Granite 3.3 8B, Gemma-4 12B |

---

## 2. Cruscotti Web e Interfacce di Controllo

Tutte le interfacce grafiche sono servite direttamente dal Cockpit locale su porta `8090`:

* **Cockpit Generale Operations**: [http://localhost:8090/](http://localhost:8090/)  
  *Stato in tempo reale dei nodi, telemetria della mesh, heartbeat e radar dei servizi.*
* **Sovereign R&D Lab & AST Gate**: [http://localhost:8090/research.html](http://localhost:8090/research.html)  
  *Albero genealogico della ricerca, ispezione AST dei 64 prototipi, diff unificato e deploy in produzione.*
* **HyperDev Studio (IDE Web Sovrano)**: [http://localhost:8090/devstudio.html](http://localhost:8090/devstudio.html)  
  *Editor di file, visualizzatore git diff, terminale web protetto e assistente AI pair programmer.*
* **Control Plane Ufficiale**: [http://localhost:8085/](http://localhost:8085/)  
  *Gestione canali, registri degli agenti, task DAG e dashboard di sistema.*
* **Missions & Mesh Scouting**: [http://localhost:8090/missions.html](http://localhost:8090/missions.html)  
  *Monitoraggio dei flussi missionari autonomi RFC-0043.*

---

## 3. Comandi di Ricerca & Sviluppo (R&D) e Promozione Prototipi

I comandi essenziali per governare il ciclo di vita del codice generato dall'IA da `data/research/prototypes/` a `shared/`:

### A. Validazione Sistematica dei Prototipi
Scansiona tutti i file generati, esegue l'AST Gate ed esegue i test funzionali sui 6 piloni scientifici (Aleksander, Causal, Swarm, Modular, Poetry, BioMesh).

```bash
# Esecuzione standard con tabella riassuntiva:
python scripts/diagnostics/validate_research_prototypes.py

# Output dettagliato per singolo prototipo:
python scripts/diagnostics/validate_research_prototypes.py --verbose

# Output JSON per automazioni o telemetria:
python scripts/diagnostics/validate_research_prototypes.py --json
```

### B. Promozione Automatizzata in Produzione
Promuove un prototipo validato nella cartella `shared/`, generando il backup `.bak`, verificando la compilazione ed eseguendo la suite Pytest con **rollback automatico istantaneo** se un test fallisce.

```bash
# 1. Elenco dei prototipi candidati alla promozione con tag raccomandati:
./scripts/promote_research_prototype.py --list

# 2. Promozione automatica batch dei candidati raccomandati (100% verificata):
./scripts/promote_research_prototype.py --auto-recommended

# 3. Promozione manuale di un singolo prototipo specifico:
./scripts/promote_research_prototype.py --prototype proto_aleksander_axioms_1792931402.py --target synthetic_consciousness_governor.py
```

### C. Ciclo Continuo di Ricerca Autonoma Tri-Nodo
Attiva il ciclo notturno o continuo su OMEN e ASUS per generare nuovi approfondimenti e prototipi:

```bash
# Turno continuo autonomo (Research + CoT + AST generation + WAL Checkpoint):
python scripts/omen_allnight_sovereign.py --single-pass

# Ciclo di sprint R&D di 1 ora a energia solare / battery budget:
python scripts/sun_power_swarm_rd_1h.py
```

---

## 4. Diagnostica, Health Check e Manutenzione

### A. Diagnostica Gate Immagini & ComfyUI
Controlla lo stato della coda di generazione e verifica che non ci siano job bloccati o lock di memoria orfani:

```bash
# Verifica coda locale ComfyUI e Memory Gate:
python scripts/diagnostics/image_gate.py --comfy http://127.0.0.1:8188

# Sblocco forzato di un job obsoleto (solo se ComfyUI non risponde):
python scripts/diagnostics/image_gate.py --comfy http://127.0.0.1:8188 --close-stale <JOB_ID>
```

### B. Probing Decision Engine (Laya System 1)
Misura la latenza di risposta su singola passata (sub-15ms) del modello decisionale `tev1` su Mac:

```bash
python scripts/diagnostics/laya_health.py
```

### C. Monitoraggio Generale della Mesh
Verifica connettività, latenza round-trip e stato termico/VRAM tra i 3 nodi:

```bash
python scripts/mesh_health.py
```

### D. Riavvio e Gestione del Cockpit Service (:8090)
Se il cockpit necessita di riavvio o ricaricamento del codice:

```bash
# Individuazione PID:
lsof -i :8090

# Riavvio in background con logging su data/cockpit_service.log:
kill $(lsof -t -i :8090) && nohup .venv/bin/python scripts/cockpit_service.py > data/cockpit_service.log 2>&1 &
```

---

## 5. Esecuzione Suite di Test (Pytest)

> [!IMPORTANT]
> **Regola Fondamentale (AGENTS.md)**: I test girano sempre nell'interprete `.venv` del repository, mai in interpreti globali.

```bash
# Esecuzione completa suite del repository:
.venv/bin/python -m pytest tests/ -q

# Verifica specifica dei prototipi di ricerca validati:
.venv/bin/python -m pytest tests/test_research_prototypes_validation.py -v

# Verifica dei moduli promossi in produzione (shared/):
.venv/bin/python -m pytest tests/test_promoted_rd_modules.py -v

# Verifica dell'albero genealogico e dell'AST Lab:
.venv/bin/python -m pytest tests/test_research_tree_and_lab.py -v

# Verifica del grafo di causalità tra agenti:
.venv/bin/python -m pytest tests/test_causal_memory_graph.py -v
```

---

## 6. Regole di Ingaggio fra Agenti e Sicurezza

1. **La Verità è il Repository**: Il codice attivo risiede nel repository locale; nessuna dipendenza da cartelle esterne non versionate.
2. **Un Messaggio per Intervento**: Ogni modifica o diagnosi completata va registrata in calce a [`AGENT-LOG.md`](file:///Users/opo/hyperspace-agi-1.04/AGENT-LOG.md).
3. **Nessun Commit e Nessun Push Senza Conferma Esplicita dell'Utente**.
4. **Nessun Segreto nei File o nei Log**: Non stampare mai token, credenziali o dump integrali di environment.
5. **Fail-Closed e Rollback Automatico**: Qualsiasi promozione di codice deve superare l'ispezione AST e la suite Pytest prima di consolidarsi.
