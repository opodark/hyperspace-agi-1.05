# Pattern Adottati da Atomic Agent per HyperSpace Mesh

Questo documento descrive i moduli e i pattern architetturali ispirati dal framework open-source **Atomic Agent** (`AtomicBot-ai/atomic-agent`) e integrati in **HyperSpace 1.05+**.

I tre problemi principali risolti sono:
1. **Fragilità dei formati JSON/Tool nei modelli locali quantizzati** (OMEN 16 LFM 24B, ASUS V16 Flint 40B, Mac M5).
2. **Assenza di tracce strutturate e riproducibili** per il replay e l'osservabilità delle sessioni.
3. **Mancanza di un gate formale per le mutazioni** prima che tocchino il filesystem o eseguano comandi critici (allineamento alla regola 3 di `AGENTS.md`).

---

## 1. Vincoli Grammaticali GBNF (`shared/gbnf_grammar.py`)

### Il Problema
Nei modelli open-weight locali (7B–40B), affidarsi esclusivamente al prompt o all'auto-healing a valle produce frequentemente fallimenti sintattici (chiavi allucinate, commenti attorno al JSON, virgole finali, graffe non bilanciate).

### La Soluzione
Attraverso **GBNF** (*Grammar-Based Natural Form* di GGML/`llama.cpp`), il campionamento dei token durante l'inferenza viene fisicamente vincolato: ogni token emesso deve rispettare la grammatica formale.

```python
from shared.gbnf_grammar import GBNFBuilder, inject_gbnf_constraint

# 1. Costruzione grammatica dinamica dai tool offerti
tools = [
    {
        "type": "function",
        "function": {
            "name": "code_sandbox",
            "parameters": {"type": "object", "properties": {"action": {"type": "string"}}}
        }
    }
]
grammar = GBNFBuilder.build_tool_call_grammar(tools)

# 2. Iniezione automatica nel payload di inferenza
payload = {"messages": [{"role": "user", "content": "analizza il file"}]}
constrained_payload = inject_gbnf_constraint(payload, grammar=grammar, backend="llama.cpp")
# constrained_payload contiene {"grammar": "...", "response_format": {"type": "json_object"}}
```

---

## 2. Tracce di Esecuzione NDJSON Replayabili (`shared/ndjson_tracer.py`)

### Il Problema
Log non omogenei o dispersi (`.log` testuali, log console) rendono difficile misurare regressioni, latenze, consumi di token e percentuali di successo dei tool.

### La Soluzione
Un tracer thread-safe che produce flussi **NDJSON** (Newline Delimited JSON) immutabili e append-only in `data/traces/<session_id>.ndjson`.

```python
from shared.ndjson_tracer import NDJSONTracer

tracer = NDJSONTracer(session_id="mission_pdf_001")

# Traccia inferenze LLM
tracer.log_llm_call(node="OMEN", model="lfm-24b", prompt_tokens=250, completion_tokens=120, duration_ms=620.0)

# Traccia tool call
tracer.log_tool_call(tool_name="read_file", arguments={"path": "doc.md"}, result="content...", duration_ms=8.5, ok=True)

# Replay ed elaborazione metriche
summary = tracer.get_summary()
# {"total_events": 2, "tool_success_rate": 1.0, "total_tokens": 370, ...}
```

---

## 3. Proposal Gate & Guardrail HITL (`shared/mutation_guard.py`)

### Il Problema
Le azioni autonome degli agenti rischiano di modificare file, lanciare comandi distruttivi o effettuare commit non autorizzati senza il consenso dell'utente.

### La Soluzione
Separazione categorica tra:
- **`READ_ONLY`**: `read_file`, `list_dir`, `grep`, `ast_inspect`, metriche — eseguiti immediatamente senza attrito.
- **`MUTATING` / `CRITICAL_SYSTEM`**: scritture file, cancellazioni, `git commit`, restart servizi — intercettati con generazione di una `MutationProposal` tipizzata salvata in `data/proposals/<id>.json`.

```python
from shared.mutation_guard import MutationGuard

guard = MutationGuard()

def my_executor(name, args):
    # Logica effettiva del tool
    return "executed"

# Azione di lettura -> autorizzata subito
ok, res = guard.execute_with_guard("read_file", {"path": "main.py"}, my_executor)
# ok == True

# Azione mutante -> bloccata e convertita in proposta
ok, res = guard.execute_with_guard("run_command", {"command": "git commit -m 'feat'"}, my_executor)
# ok == False, res == {"gated": True, "proposal": {"proposal_id": "prop_...", "status": "PENDING_APPROVAL"}}

# Approvazione esplicita (es. via Cockpit UI o CLI)
guard.approve("prop_...")
ok, res = guard.execute_with_guard("run_command", {"command": "git commit -m 'feat'"}, my_executor, proposal_id="prop_...")
# ok == True, eseguito!
```

---

## 4. Test di Verifica

La suite di test per questi moduli risiede in:
```bash
.venv/bin/python -m pytest tests/test_atomic_agent_patterns.py -v
```
Tutti i test (12 unit test dedicati) risultano verdi e integrati con le regole di licenza Apache 2.0 del repository.
