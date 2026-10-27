# Ponte R&D 1: Coscienza Sintetica (Assiomi di Aleksander) ↔ Causal AI (Pearl-Style)

## Panoramica

Il **Ponte 1** unifica il modello cognitivo dei **5 Assiomi di Igor Aleksander** ([`shared/synthetic_consciousness_governor.py`](../shared/synthetic_consciousness_governor.py)) con il grafo causale distribuito FTS5 WAL ([`shared/causal_memory_graph.py`](../shared/causal_memory_graph.py)).

In precedenza, il modulo di coscienza operava con generatori controfattuali sintetici (scenari pseudo-casuali) e con euristiche di pianificazione fisse. Con questo ponte, l'immaginazione e la pianificazione di Anna sono direttamente alimentate dalla memoria episodica e dalle relazioni causali reali dello swarm mesh.

---

## Architettura dei 5 Assiomi Connessi

| Assioma di Aleksander | Integrazione con Causal AI | Meccanismo Operativo |
|---|---|---|
| **1. Depiction of Self** | `persona.json` (modello d'identità) | Allineamento tra autorappresentazione interna, credenze e nodi radice dell'identità nel grafo episodico. |
| **2. Imagination** | `DreamEngine` con interventi $do(X = x')$ | Generazione di scenari controfattuali Pearl-style: `suppression` (rimozione cause di incidenti o perdita capacità), `amplification` (potenziamento link virtuosi), `inversion` (biforcazioni alternative). Calcolo dell'entropia di Shannon sulle distribuzioni d'esito $\{-1, 0, +1\}$. |
| **3. Attention** | `TaskScheduler` + salienza causale | Assegnazione di budget computazionale calibrato sul grado di centralità causale e sul decadimento semantico (`SemanticMemoryDecayController`). |
| **4. Planning** | Verifica del path causale nel DAG | Verifica empirica che le azioni pianificate abbiano legami causali dimostrati verso gli obiettivi dichiarati nella persona ($\frac{\text{azioni causali valide}}{\text{totale azioni}}$). |
| **5. Emotion & Valencing** | Valutazione retrospettiva di impatto | Modulazione della valenza affettiva in base agli incidenti o successi causali registrati recentemente in memoria episodica. |

---

## Ciclo Onirico Integrato (`dream_causal_cycle`)

Il metodo `governor.dream_causal_cycle(n_scenarios=6)` esegue il consolidamento notturno della memoria:
1. **Estrazione Episodica**: Campiona eventi causali reali archiviati in Hermes SQLite FTS5 WAL.
2. **Intervento Controfattuale**: Esegue perturbazioni $do(X)$ valutando le conseguenze a valle via forward graph.
3. **Misura dell'Entropia**: Calcola la ricchezza dell'immaginazione come entropia informativa normalizzata.
4. **Consolidamento Causale**: Registra l'insight emerso dal sogno direttamente nel `CausalMemoryGraph` come nuovo evento con causa `dream_cycle_<node_id>` ed effetto `causal_imagination_consolidation_<timestamp>`, permettendo al sistema di imparare dalle proprie simulazioni oniriche.
5. **WAL Checkpoint**: Scrive un checkpoint atomico di coscienza con lo stato dei 5 assiomi.

---

## Strumenti Diagnostici & Test

```bash
# Esecuzione verifica rapida console
python scripts/diagnostics/verify_aleksander_causal_bridge.py

# Esecuzione con simulazione del ciclo onirico completo (8 scenari)
python scripts/diagnostics/verify_aleksander_causal_bridge.py --run-dream --scenarios 8

# Output JSON per telemetria di sistema o dashboard Cockpit
python scripts/diagnostics/verify_aleksander_causal_bridge.py --json --run-dream

# Esecuzione suite di test automatica Pytest nel .venv del repository
.venv/bin/python -m pytest tests/test_aleksander_causal_bridge.py -v
```
