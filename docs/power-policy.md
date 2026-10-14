# HyperSpace AGI 1.05 — Policy Energetica & Gestione Batteria della Mesh

Questo documento formalizza le regole operative e architetturali per la gestione dei nodi alimentati da rete elettrica fissa (**AC Line**) rispetto ai nodi operanti su batteria (**DC Battery**) nella mesh distribuita HyperSpace v1.05.

---

## 1. Principi Guida

1. **Grid-First (Privilegio della Presa Elettrica)**:
   - I carichi computazionali pesanti (generazione diffusion ComfyUI, cicli di sogno e consolidamento notturno, fine-tuning e modelli LLM >10B) vengono instradati con priorità assoluta sui nodi alimentati dalla rete elettrica continua.
2. **Battery Preservation (Salvaguardia Autonomia Portatili)**:
   - Quando un nodo (es. MacBook, laptop Windows) opera a batteria e nella mesh sono presenti nodi AC, il carico viene progressivamente deviato verso questi ultimi.
   - I task differibili (dream loop, re-indicizzazione Graphify) vengono automaticamente sospesi sul nodo a batteria.
   - Sotto il **20%** di carica residua (*Battery Critical*), il nodo entra in stato `degraded` e rifiuta qualsiasi carico eccetto il triage sub-50ms di emergenza (Laya System 1).
3. **Cooperative Survival (Resilienza a Blackout Totale)**:
   - Se l'intera flotta opera a batteria (nessun nodo AC disponibile):
     - I carichi pesanti e i cicli di riflessione profonda vengono congelati.
     - L'inferenza essenziale viene distribuita in modo proporzionale alla carica residua di ciascun nodo.

---

## 2. Profili Energetici Formali

| Profilo | Condizione | Moltiplicatore Capacità | Concorrenza Max | Task Consentiti | Stato Degraded |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **`grid_ac`** | Collegato alla presa di rete (AC) | `1.00` | 4 | Tutti (LLM, ComfyUI, Sogni, Sandbox) | No |
| **`battery_optimal`** | Batteria > 50% | `0.75` | 2 | Inferenza standard; carichi pesanti deviati se ci sono nodi AC | No |
| **`battery_eco`** | Batteria 20% – 50% | `0.40` | 1 | Solo inferenza essenziale; sogni e diffusion sospesi | No |
| **`battery_critical`**| Batteria < 20% | `0.05` | 1 | Solo triage ultra-leggero di sopravvivenza (sub-50ms) | **Sì** |

---

## 3. Classificazione dei Task e Controllo di Ammissione

I task della mesh sono classificati in 5 categorie con regole di ammissione vincolanti (`evaluate_task_admission`):

- **`light_inference`**: Laya decision engine (sub-50ms), triage intenti, health check.
  - *Ammesso sempre*, anche in `battery_critical`.
- **`standard_inference`**: Chat LLM, completamento testuale standard (es. Qwen 4B/8B).
  - Ammesso su `grid_ac` e `battery_optimal`.
  - In `battery_eco`: deviato su nodi AC se disponibili; ammesso in caso di blackout.
- **`heavy_gpu`**: Generazione immagini/video diffusion via ComfyUI Desktop.
  - *Vietato a batteria*: deviato su nodi AC o differito.
- **`dream_consolidation`**: Cicli di riflessione notturna (`shared/dream_schedule.py`).
  - *Sospeso a batteria*: riprende solo quando il nodo torna sotto alimentazione di rete fissa.
- **`code_sandbox`**: Esecuzione codice in container isolati.
  - Deviato su nodi AC se presenti.

---

## 4. Architettura di Rilevamento Dual-Path (Docker WSL2 / Host)

I container Docker su WSL2 non possono accedere direttamente all'interfaccia ACPI / sysfs della batteria dell'hardware host. Per colmare questo confine:

1. **Host-Side Sensing (`shared/power_sense.py`)**:
   - Su Windows: interrogazione nativa `GetSystemPowerStatus` via `ctypes` (`win32_api`).
   - Su macOS: parsing rapido di `pmset -g batt` (`mac_pmset`).
   - Su Linux: lettura di `/sys/class/power_supply/` (`linux_sysfs`).
2. **Dual-Path Atomic Persistence**:
   - Lo stato rilevato viene scritto atomicamente sia in `data/host_power.json` (host path) sia in `data/runtime/data/host_power.json` (montato in Docker come `/app/data/host_power.json`).
3. **Container-Side Ingestion**:
   - Il Control Plane e la telemetria di nodo leggono `/app/data/host_power.json` garantendo una visibilità in tempo reale dello stato elettrico con freschezza fino a 300 secondi.
4. **Daemon di Monitoraggio (`scripts/power_monitor.py`)**:
   - Integrato nel ciclo di vita delle superfici host (`scripts/start-surfaces.ps1`).

---

## 5. Integrazione con Doctor Mesh e Routing

- **Doctor Mesh Check 6 (`control-plane/cp/doctor_mesh.py`)**:
  - Esegue `assess_cluster_energy_status(telemetries)` e categorizza la flotta in 3 regimi:
    - `all_grid_ac`: Stabile, massima potenza.
    - `mixed_grid_preference`: Rete mista, priorità AC.
    - `blackout_cooperative`: Tutti i nodi a batteria, allerta coordinata.
- **Metric-Driven Routing (`control-plane/routing.py`)**:
  - Calcola `power_s`:
    - Nodo AC: `power_s = 1.0`
    - Nodo a batteria con nodi AC presenti: penalizzazione proporzionale `0.05..0.50`.
    - Blackout totale: assegnazione proporzionale alla carica `0.10..1.00`.
    - Batteria < 15%: depenalizzazione a `0.02` e flag `degraded = True`.
