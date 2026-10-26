# Validazione Sistematica dei Prototipi di Ricerca Sovrana HyperSpace AGI

## Panoramica

L'albero di ricerca genealogico di HyperSpace AGI (`data/research/research_tree.json`) raccoglie gli studi di frontiera, i fallimenti documentati, i pivot concettuali e i prototipi generati durante i turni notturni continui eseguiti sui nodi distribuiti della rete mesh (**Mac M5 Hub**, **HP OMEN 16**, **ASUS V16**).

Tutti i prototipi risiedono in `data/research/prototypes/` e vengono sottoposti a verifica a doppio livello:
1. **AST Gate Sintattico**: analisi formale del codice astratto (`ast.parse`) senza esecuzione arbitraria, estraendo classi, metodi, decoratori, complessità e import.
2. **Harness Funzionale dei Piloni**: collaudo isolato in memoria delle capacità cognitive, relazionali e distribuite.

---

## I 6 Piloni Scientifici Validati

### 1. Coscienza Sintetica (Assiomi di Igor Aleksander) — `aleksander_axioms`
* **Prototipi di riferimento**: `proto_aleksander_axioms_1792931402.py` e `proto_aleksander_axioms_1792931956.py`
* **Classe Principale**: `SyntheticConsciousnessGovernor`
* **Assiomi Verificati**:
  * *Depiction of Self*: Autorappresentazione persistente dell'identità tramite `persona.json` (modello ontologico a grafo con nodi persona, valori e obiettivi).
  * *Imagination*: Generazione controfattuale di scenari predittivi e futuri ipotetici (`DreamEngine`).
  * *Attention*: Allocazione mirata del budget attentivo e prioritizzazione degli stimoli (`TaskScheduler` RFC-0043).
  * *Planning*: Ordinamento temporale delle azioni e pianificazione causale.
  * *Valuation/Emotion*: Assegnazione di pesi affettivi ed emotivi alle esperienze con persistenza atomica WAL (`CheckpointManager` RFC-0044).

### 2. Causal AI & Memoria Stigmergica — `symbolic_causal_mesh`
* **Prototipo di riferimento**: `proto_symbolic_causal_mesh_1792927875.py`
* **Classe Principale**: `CausalMemoryGraph`
* **Caratteristiche**:
  * Persistenza su SQLite in memoria/disco con supporto WAL.
  * Indicizzazione episodica full-text FTS5 con tokenizzatore `porter unicode61`.
  * Risalita retrospettiva con breadth-first search (`trace_lineage`) per individuare le cause radice (root-cause analysis) delle failure o dei successi della mesh.

### 3. Swarm AI & Coscienza Collettiva — `swarm_emergence`
* **Prototipo di riferimento**: `proto_swarm_emergence_1792923871.py`
* **Classe Principale**: `StigmergicMeshSwarm`
* **Caratteristiche**:
  * Coordinamento stigmergico ispirato alle colonie di insetti sociali: deposizione di feromoni digitali in memoria condivisa con decadimento temporale esponenziale.
  * Rilevamento dei gradienti di carico e latenza (`sense_gradient`) con calcolo di media pesata e varianza.
  * Orologi logici `VectorClock` per tracciare causalità distribuita e convergenza di consenso senza master.

### 4. ModularIntellect: Memoria Tri-Modale a Grafo — `modular_intellect`
* **Prototipi di riferimento**: `proto_modular_intellect_1792920337.py` e `proto_modular_intellect_1792916524.py`
* **Classe Principale**: `SovereignModularIntellect`
* **Caratteristiche**:
  * Tipologia tri-modale: `document` (chunk part-of), `interaction` (scambi episodici), `note` (auto-riflessioni ricursive).
  * Esplorazione iterativa del contesto con navigazione a grafo (`traverse_graph_context`, BFS multi-hop).
  * `AlignmentAuditor` deontologico che intercetta e blocca azioni non consentite o manipolazioni fuori perimetro.

### 5. Estetica Algoritmica & Poesia Neuro-Simbolica — `algorithmic_poetry_aesthetics`
* **Prototipi di riferimento**: `proto_algorithmic_poetry_aesthetics_1792930830.py` e `proto_algorithmic_poetry_aesthetics_1792929535.py`
* **Classe Principale**: `NeuroSymbolicPoetryEngine`
* **Caratteristiche**:
  * Scansione sillabica fonetica per la metrica endecasillaba italiana.
  * Schemi di rima strutturati (incatenata, baciata, alternata) guidati dalle memorie emotive di Anna.
  * Generazione di prompt visivi e tipografici per nodi ComfyUI (`typography: elegant serif, pastel watercolor`).

### 6. Biomimicry Mesh Computing — `biomimetic_nature_mesh`
* **Prototipo di riferimento**: `proto_biomimetic_nature_mesh_1792916915.py`
* **Classi Principali**: `Nodo`, `Link`, `BioMeshMonitor`
* **Caratteristiche**:
  * Calcolo dell'entropia di Shannon sui carichi dei nodi per valutare il bilanciamento dell'elaborazione.
  * Potatura euristica (`pota_alta_latenza`) dei canali di comunicazione degradati.
  * Quorum sensing e *idle cycle stealing* per riallocare task da nodi saturi a nodi a riposo.

---

## Esecuzione Diagnostica & Test

```bash
# Esecuzione diagnostica rapida con report console:
python scripts/diagnostics/validate_research_prototypes.py

# Output dettagliato JSON per telemetria di sistema:
python scripts/diagnostics/validate_research_prototypes.py --json

# Esecuzione suite di test automatica Pytest nel .venv del repository:
.venv/bin/python -m pytest tests/test_research_prototypes_validation.py -v
```

---

## Integrazione con la UI Cockpit

Tutti i prototipi e i rami genealogici sono ispezionabili e gestibili graficamente all'indirizzo:
**`http://localhost:8090/research.html`**

Funzionalità operative:
* **Albero genealogico interattivo**: visualizza i nodi passati, i pivot e i tentativi falliti.
* **AST Inspector Visuale**: seleziona un prototipo per esaminarne classi, metodi, docstring e conformità sintattica.
* **Diff Engine**: visualizza il diff unificato tra il prototipo e il codice attualmente promosso in `shared/`.
* **Deploy Promozione**: promuove il prototipo in produzione in `shared/` con compilazione preventiva e backup atomico `.bak`.
