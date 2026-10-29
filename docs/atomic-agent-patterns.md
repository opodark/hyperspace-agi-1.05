# Pattern Adottati da Atomic Agent per HyperSpace Mesh

Questo documento descrive i moduli e i pattern architetturali ispirati dal framework open-source **Atomic Agent** (`AtomicBot-ai/atomic-agent`) e integrati in **HyperSpace 1.05+**.

I tre problemi principali affrontati sono:
1. **Fragilità dei formati JSON/Tool nei modelli locali quantizzati** (OMEN 16 LFM 24B, ASUS V16 Flint 40B, Mac M5).
2. **Assenza di tracce strutturate e riproducibili** per il replay e l'osservabilità delle sessioni.
3. **Mancanza di un gate formale per le mutazioni** prima che tocchino il filesystem o eseguano comandi critici (allineamento alla regola 3 di `AGENTS.md`).

---

## 1. Vincoli di Schema & GBNF (`shared/gbnf_grammar.py`)

### Differenziazione per Backend
Per garantire output strutturati rigorosi ed evitare allucinazioni sintattiche, è fondamentale distinguere i backend di inferenza:
* **`llama.cpp` / `llama-server` nativo:** Supporta direttamente le grammatiche formali **GBNF** (*Grammar-Based Natural Form*) tramite il parametro `grammar`. L'output del modello viene vincolato token per token.
* **Ollama (>= 0.5):** Ollama standard non interpreta stringhe GBNF nel dizionario options. Per forzare schemi rigidi su Ollama si impiega l'API Structured Outputs nativa, passando direttamente un dizionario **JSON Schema** nel parametro `format` (`format: {"type": "object", "properties": {...}}`).

```python
from shared.gbnf_grammar import GBNFBuilder, inject_gbnf_constraint

# 1. Costruzione grammatica dinamica GBNF (per llama.cpp)
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

# 2. Costruzione JSON Schema (per Ollama e OpenAI)
schema = GBNFBuilder.build_json_schema({
    "verdict": "string",
    "score": "number",
    "summary": "string"
})

# Iniezione in base al backend effettivo:
payload = {"messages": [{"role": "user", "content": "analizza"}]}
# Per Ollama: inietta format: schema
ollama_payload = inject_gbnf_constraint(payload, json_schema=schema, backend="ollama")
# Per llama.cpp: inietta grammar: grammar
llamacpp_payload = inject_gbnf_constraint(payload, grammar=grammar, backend="llama.cpp")
```

---

## 2. Tracce di Esecuzione NDJSON Replayabili (`shared/ndjson_tracer.py`)

Un tracer thread-safe che produce flussi **NDJSON** (Newline Delimited JSON) immutabili e append-only in `data/traces/<session_id>.ndjson`.
Ogni evento memorizza timestamp ISO, sequenza, token computati, latenze in millisecondi ed esiti.

```python
from shared.ndjson_tracer import NDJSONTracer

tracer = NDJSONTracer(session_id="mission_pdf_001")

# Traccia inferenze LLM
tracer.log_llm_call(node="OMEN", model="lfm-24b", prompt_tokens=250, completion_tokens=120, duration_ms=620.0)

# Traccia tool call
tracer.log_tool_call(tool_name="read_file", arguments={"path": "doc.md"}, result="content...", duration_ms=8.5, ok=True)

# Replay ed elaborazione metriche aggregate
summary = tracer.get_summary()
```

---

## 3. Proposal Gate & Distinzione HITL vs Pipeline Autonoma (`shared/mutation_guard.py`)

Separazione categorica tra:
- **`READ_ONLY`**: `read_file`, `list_dir`, `grep`, `ast_inspect`, metriche — eseguiti immediatamente senza attrito.
- **`MUTATING` / `CRITICAL_SYSTEM`**: scritture file, cancellazioni, `git commit`, restart servizi — intercettati con generazione di una `MutationProposal` salvata in `data/proposals/<id>.json`.

### Trasparenza della Governance
Il guardiano distingue chiaramente chi approva la proposta:
- **HITL Reale (`approver="human_operator"`):** La proposta rimane in stato `PENDING_APPROVAL` finché un operatore umano non invia un comando esplicito di approvazione (`--approve <id>` o via Cockpit).
- **Pipeline Autonoma (`approver="autonomous_pipeline"`):** Lo script dichiara esplicitamente la modalità autonoma. La proposta viene contrassegnata come `APPROVED_AUTOMATIC`, senza simulare una falsa revisione umana.

```python
from shared.mutation_guard import MutationGuard

guard = MutationGuard()

# 1. Azione di sola lettura: bypass immediato
ok, res = guard.execute_with_guard("read_file", {"path": "main.py"}, my_executor)

# 2. Azione mutante: genera proposta tipizzata
ok, res = guard.execute_with_guard("write_file", {"path": "shared/mod.py", "content": "..."}, my_executor)
# res['gated'] == True, proposal_id == "prop_..."

# 3. Approvazione esplicita umana:
guard.approve("prop_...", approver="human_operator")
ok, res = guard.execute_with_guard("write_file", {"path": "shared/mod.py"}, my_executor, proposal_id="prop_...")
```

---

## 4. Test di Verifica

La suite di test per questi moduli risiede in:
```bash
.venv/bin/python -m pytest tests/test_atomic_agent_patterns.py tests/test_promoted_atomic_sprint_modules.py tests/test_licensing.py -v
```
Tutti i test (22 unit test dedicati) risultano verdi e integrati con le regole di licenza Apache 2.0 del repository.
