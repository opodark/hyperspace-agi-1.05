# Calendario ed Evoluzione Autonoma della Codebase (HyperSpace AGI)

> Questo documento viene aggiornato automaticamente dagli agenti e dagli strumenti di HyperSpace.
> Consulta questo storico prima di avviare refactor o modifiche architetturali.

## 📅 Calendario delle Modifiche Recenti

### 2026-10-21 (2 eventi)
- **✨ [Antigravity]**: Report tecnico architettura distillazione CoT & estensione tool-use nei chat hook per Cips
  - **File:** `docs/reports/HyperSpace_CoT_Distillation_Architecture.md`, `docs/reports/HyperSpace_CoT_Distillation_Architecture.docx`, `docs/reports/HyperSpace_CoT_Distillation_Architecture.pdf`
  - **💡 Lezione Appresa:** Per modelli compatti (SLM 8B), la traccia di pensiero CoT deve includere step espliciti di intent detection e validazione argomenti per prevenire allucinazioni di tool call.
  - **Verifica Test:** `37 passed`
- **✨ [Antigravity-Mesh]**: Esecuzione missione distribuita di autosviluppo e distillazione CoT su tutti i 3 nodi (OMEN, ASUS, MAC)
  - **File:** `scripts/diagnostics/run_mesh_autodev_mission.py`, `data/synthetic_cot_dataset.jsonl`, `data/missions.jsonl`
  - **💡 Lezione Appresa:** Su nodi eterogenei (Apple Silicon vs RTX 3070 vs RTX Mobile), imporre al prompt un limite di concisione al CoT (max 150 parole) per non esaurire il budget dei token di output prima del blocco di codice.
  - **Verifica Test:** `100% AST valid pass`

### 2026-10-20 (2 eventi)
- **✨ [Antigravity]** `[9047ce8]`: Implementazione Hermes Shadow Memory autonoma (SQLite FTS5) per nodi Windows senza hermes-agent
  - **File:** `scripts/hermes_memory_bridge.py`, `scripts/start_hermes_memory_bridge.ps1`, `tests/test_hermes_memory.py`
  - **💡 Lezione Appresa:** I nodi edge e worker Windows necessitano di fallback autonomo SQLite FTS5 su porta 8098 per non degradare a memoria legacy.
  - **Verifica Test:** `50/50 hermes passed`
- **✨ [Antigravity]** `[ee16dd6]`: Setup HP OMEN 16 operatività continua 24/7, watchdog termico e orchestratore notturno
  - **File:** `scripts/setup-omen-247.ps1`, `scripts/diagnostics/omen_watchdog_247.py`, `scripts/nightly_omen_orchestrator.py`
  - **💡 Lezione Appresa:** Sui laptop da gaming AC 24/7 limitare la carica della batteria all 80% nel BIOS ed elevare il telaio di 3cm per abbattere le temperature di 10°C.
  - **Verifica Test:** `2497 passed`

---
## 🧠 Indice delle Regole e Lezioni Critiche

- **Mount Docker Read-Only**: sui container dei nodi (`node-1`), `/repo` è in sola lettura. Ogni patch/file deve passare dal watcher host o da Git commit.
- **Gestione VRAM & Context Window**: su GPU con 8 GB VRAM (RTX 3070 OMEN / Asus V16), compattare i prompt e gli output tool per non provocare OOM.
- **Hermes Shadow Memory**: su nodi Windows privi di runtime nativo `hermes-agent`, il bridge `hermes_memory_bridge.py` deve girare in modalità Shadow (porta 8098 con SQLite FTS5).
- **Salvaguardia Batteria Laptop**: su nodi AC operativi 24/7, mantenere abilitato il limite di carica all'80% nel BIOS/OMEN Hub e sollevare il telaio di 3-5 cm.
