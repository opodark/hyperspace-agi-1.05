# Laya Decision Engine (System 1) in HyperSpace

HyperSpace adotta **Laya** (`NandhaKishorM/laya`) come motore decisionale **System 1 non-autoregressivo**.

---

## 1. Motivazione Architetturale: System 1 vs System 2

Prima di questa integrazione, HyperSpace gestiva le decisioni in due modalità estreme:
1. **Euristiche rigide basate su regex o dizionari esatti**:
   - `shared/skill_hooks.py` (`RULES` con keyword statiche in italiano/inglese);
   - `shared/channel.py` (`SPAM_RULES`);
   - `shared/instagram_language.py` (dizionario slang e tetto a 3 parole);
   - `shared/instagram_intimacy.py` (consenso basato su liste fisse di parole).
   Se l'utente usava perifrasi o lingue differenti (es. spagnolo, tedesco, hindi, ecc.), le regole fallivano.
2. **LLM generativi lenti e pesanti per decisioni categoriche (System 2)**:
   - In `control-plane/cp/mission.py`, il verifier invocava modelli autoregressivi da 8B-27B via Ollama o cloud per farsi restituire un JSON con una singola scelta (`pass`, `retry`, `replan`, `fail`).
   - Latenza elevata (3–10 secondi a step), rischio di allucinazioni di schema JSON e consumo di budget token.

### Il ruolo di Laya
Laya introduce un livello decisionale **System 1**:
- **Singola forward pass (30–35 ms su GPU, ~120 ms su Apple Silicon MPS)**: non genera token progressivi, quindi non allucina formati né produce risposte incomplete.
- **Decisioni tipizzate**:
  - `choice`: classificazione categorica tra N opzioni con distribuzione di probabilità e confidenza calibrata.
  - `noul`: valutazione booleana Sì/No con probabilità \(P(\text{true}) \in [0.0, 1.0]\).
  - `score`: livelli ordinali (urgenza, gravità, priorità).
- **Supporto multilingua nativo (100+ lingue)** con router di script e lingua a costo trascurabile (<0.5 ms).
- **Confidenza calibrata e astensione**: se la confidenza è inferiore alla soglia (`min_confidence`), il sistema sa di non essere certo e rimette la decisione al System 2 (il modello generativo con reasoning CoT).

---

## 2. Strategia di Ripartizione Hardware & ComfyUI Offloading

Poiché i workflow di generazione immagini pesanti (**ComfyUI**, Stable Diffusion 1.5, Flux) vengono progressivamente delocalizzati su un **nodo dedicato ad alta VRAM/RAM** (es. workstation con GPU NVIDIA o Windows RTX nella mesh Tailscale), la macchina locale (Mac Apple Silicon) ottiene headroom immediato di memoria.

Questo permette a HyperSpace di mantenere in locale:
- Il **Control Plane** e Registry;
- Il motore **Laya su Apple Silicon (Metal Performance Shaders - MPS)**, che risiede stabilmente in RAM/VRAM con un'impronta ridotta (**~650 MB – 1.2 GB** totali);
- I nodi decisionali veloci, lasciando i calcoli grafici intensivi al worker remoto.

---

## 3. Punti di Integrazione in HyperSpace

### A. Mission Control — Fast-Gate del Verifier
In [`control-plane/cp/mission.py`](file:///Users/opo/hyperspace-agi-1.04/control-plane/cp/mission.py), la funzione `_mission_verify` include il gate Laya System 1:
- Prima di invocare il modello generativo autoregressivo `_mission_llm`, Laya valuta istantaneamente l'output del worker e l'evidenza dei tool contro l'istruzione del task.
- Se la confidenza è elevata ($\ge 0.85$), il verdetto (`pass`, `retry`, `replan`, `fail`) viene acquisito in sub-50ms senza token spesi (`system: "laya-1"`).
- Se Laya è incerto o offline, il runtime scala in modo trasparente e automatico su `_mission_llm`.
- I gate oggettivi indipendenti dal modello (es. `_mission_pdf_gate`) restano vincolanti ed ereditano la priorità finale.

### B. Client Interoperabile e Fail-Safe (`shared/laya_client.py`)
Il modulo [`shared/laya_client.py`](file:///Users/opo/hyperspace-agi-1.04/shared/laya_client.py) fornisce metodi tipizzati senza alcuna dipendenza da PyTorch o NumPy nel `.venv` del repository:
```python
from shared.laya_client import decide_choice, decide_noul, decide_score

# 1. Scelta categorica
res = decide_choice(
    text_or_state="I file brief.pdf e il codice sono stati creati con successo.",
    choices={"pass": "Task completato", "retry": "Incompleto o fallito"},
    instructions="Giudica se il task è completato",
    min_confidence=0.85
)
# res -> {"choice": "pass", "confidence": 0.94, "probabilities": {...}, "abstention": False}

# 2. Domanda Booleana (noul)
res_noul = decide_noul(
    text_or_state="Voglio disdire il servizio immediatamente.",
    instructions="L'utente richiede la cancellazione del piano?",
    min_confidence=0.8
)
# res_noul -> {"noul": 0.96, "is_yes": True, "confidence": 0.92, ...}
```

---

## 4. Modalità Operative ed Esecuzione

### A. Esecuzione Locale nativa su Mac (MPS)
Il runner dedicato in `scripts/laya_service.py` avvia il server FastAPI esponendo le API compatibili Laya:
```bash
python scripts/laya_service.py --port 8098 --device mps
```

### B. Profilo Docker Compose (`decision`)
In `docker-compose.yml`, Laya è registrato come servizio opzionale con il profilo `decision`:
```bash
docker compose --profile decision up -d laya
```

### C. Strumento di Diagnostica
Conforme alla Regola 6 di `AGENTS.md`, HyperSpace include lo script read-only di monitoraggio e health check:
```bash
python scripts/diagnostics/laya_health.py
# Opzioni: --url http://127.0.0.1:8098 --timeout 2.0
```
Lo script testa la raggiungibilità del servizio, misura la latenza reale in millisecondi ed esegue due probe tipizzati (`choice` e `noul` multilingua).

---

## 5. Variabili d'Ambiente

| Variabile | Default | Descrizione |
|---|---|---|
| `LAYA_URL` | `http://127.0.0.1:8098` | Endpoint base del microservizio Laya |
| `LAYA_ENABLED` | `true` | Flag globale per abilitare/disabilitare chiamate a Laya |
| `LAYA_TIMEOUT_S` | `2.0` | Timeout massimo delle chiamate HTTP (le inferenze richiedono ~35–120ms) |
| `MISSION_LAYA_VERIFY_ENABLED` | `true` | Abilita il Fast-Gate Laya in Mission Control |
| `MISSION_LAYA_VERIFY_MIN_CONF` | `0.85` | Soglia minima di confidenza calibrata per accettare il verdetto senza escalation a System 2 |
