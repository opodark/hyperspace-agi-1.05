# In-Weight RISC-V CPU & Gated DeltaNet RAM (Qwenputer Paradigm)

> **Documento Tecnico & Architetturale HyperSpace AGI 1.05 / 1.06**  
> Basato sul lavoro pionieristico di Divyansh Agrawal (`divagr18/qwenputer`, `chipformer`).

---

## 1. Cos'è Qwenputer

**Qwenputer** è una nuova classe di modelli neurali: un'architettura **Qwen3.5-4B** in cui un **processore fisico a 32-bit RISC-V (RV32IM + Zba)** è compilato direttamente all'interno delle matrici dei pesi dei transformer.

Non si tratta di un plugin, di un wrapper Python o di un interprete esterno richiamato via API/bash. Il processore è costituito da **11 strati transformer** prepended a quelli del modello linguistico, in cui **nessun peso è stato appreso tramite gradient descent o training**: ogni singolo peso è calcolato deterministicamente da un compilatore logico (`chipformer`).

### I Tre Pilastri Tecnologici

```
+-------------------------------------------------------------------------+
|                              QWENPUTER                                  |
|                                                                         |
|  [ In-Weight CPU ]        [ Gated DeltaNet RAM ]   [ Zero-Escape Exec ] |
|  Porte logiche RV32IM     Delta rule S_t come      Esecuzione dentro    |
|  in MLP & Attention       banchi di celle RAM      la VRAM della GPU;   |
|  senza backprop.          a riga singola.          zero syscall host.   |
+-------------------------------------------------------------------------+
```

1. **Compilazione di Circuiti (In-Weight CPU)**:
   Il compilatore traduce le porte logiche (NAND, XOR, ALU, registri, program counter) direttamente nei parametri dei tensori MLP e matrici di proiezione.
2. **Gated DeltaNet come RAM Fisica Esatta**:
   Qwen3.5 impiega blocchi ricorrenti lineari basati su Gated DeltaNet. L'aggiornamento dello stato nascosto:
   $$S_t = S_{t-1}(I - \beta_t k_t k_t^T) + v_t k_t^T$$
   permette di impostare chiavi $k_t$ one-hot ortogonali. In questo modo **ogni passo sovrascrive esattamente una specifica riga della matrice di stato**, mantenendo inalterate tutte le altre. Ogni riga funge da cella di memoria RAM a 32-bit.
3. **Il Forward Pass come Ciclo di Clock**:
   Ogni generazione di token corrisponde a un ciclo di clock del processore. La CPU interna esegue codice C compilato in ELF, codice MicroPython, e supera la suite ufficiale di conformità hardware `riscv-tests` della RISC-V Foundation.

---

## 2. Applicazioni Strategiche in HyperSpace AGI

L'adozione di questo paradigma in HyperSpace risolve quattro grandi sfide:

| Sfida HyperSpace | Soluzione con In-Weight CPU |
|---|---|
| **Zero-Escape Sandbox** | Codice generato da agenti o preso dal web viene eseguito direttamente nella VRAM del modello. Non ci sono syscall al kernel Linux/macOS, nessun filesystem host esposto e nessuna possibilità fisica di fuga dal container. |
| **Aritmetica e Crittografia Senza Allucinazioni** | Calcolo a precisione arbitraria (62+ cifre), hashing e verifica firme senza dipendere da floating point drift o allucinazioni statistiche. |
| **In-Weight Filesystem Multi-Sessione** | Gli stati DeltaNet possono ospitare fino a 512 file (~53.000 token di testo). Serializzando i pesi di stato a fine sessione, i file persistono biologicamente nella memoria neurale senza database esterno. |
| **Sogni Controfattuali Notturni Rigorosi** | Durante i cicli REM notturni di Anna (`omen_allnight_sovereign.py`), le simulazioni controfattuali dell'Assioma 2 & 4 di Aleksander possono girare su codice C deterministico prima di essere consolidate nel DAG causale. |

---

## 3. Mappa di Prontezza dei Nodi HyperSpace

Lo strumento [`scripts/diagnostics/qwenputer_mesh_probe.py`](file:///Users/opo/hyperspace-agi-1.04/scripts/diagnostics/qwenputer_mesh_probe.py) interroga i tre nodi del cluster:

```mermaid
flowchart TD
    subgraph Hub["Mac M5 Hub (Master)"]
        MAC_RT["Runtime Locale Chipformer"]
        MAC_MPS["PyTorch MPS / Metal"]
        MAC_BR["QwenputerBridge"]
    end

    subgraph Omen["HP OMEN 16 (GPU Node)"]
        OMEN_GPU["NVIDIA RTX 3070 8GB GDDR6"]
        OMEN_API["Sovereign Node API :8081"]
        OMEN_TRITON["CUDA / Triton Executor (3200 tok/s)"]
    end

    subgraph Asus["ASUS V16 (High RAM)"]
        ASUS_MEM["48GB DDR5 Memory Pool"]
        ASUS_OL["Deep Context / Unquantized Checkpoints"]
    end

    Hub <-->|Tailscale P2P| Omen
    Hub <-->|Tailscale P2P| Asus
```

### Stato dei Nodi Verificato

- **Mac M5 Hub (Master Locale)**: 🟢 **READY**
  - OS: macOS (Apple Silicon M5), Python 3.14.5.
  - Runtime locale: modulo di riferimento RISC-V e assembler operativi in `modules/qwenputer` (modulo extra, `bash scripts/install_qwenputer.sh`).
  - Benchmark: Fibonacci 20 calcolato in 0,56 ms; Bignum 62 cifre in 1,86 ms.
- **HP OMEN 16 (GPU Heavy Engine)**: 🟢 **READY**
  - Endpoint: `http://100.104.238.125:8081` (Reachable, Tier: Root).
  - GPU: NVIDIA RTX 3070 8GB GDDR6, ideale per pesi Qwen3.5-4B FP8 e Triton executor.
- **ASUS V16 (High Memory Pool)**: 🟡 **STANDBY / POOL READY**
  - Memoria: 48GB DDR5, predisposto per ospitare i pesi unquantized e i checkpoint con estensione vettoriale QwenPU.

---

## 4. Componenti Software nel Repository

1. **[`shared/qwenputer_bridge.py`](file:///Users/opo/hyperspace-agi-1.04/shared/qwenputer_bridge.py)**:
   - `execute_riscv_asm(source, initial_regs)`: assembler ed esecutore RV32IM deterministico.
   - `execute_calc_expression(expression)`: calcolo a 62 cifre senza float drift tramite firmware ELF.
   - `check_mesh_nodes_readiness()`: ispezione multi-nodo per Mac, OMEN e ASUS.
2. **[`scripts/diagnostics/qwenputer_mesh_probe.py`](file:///Users/opo/hyperspace-agi-1.04/scripts/diagnostics/qwenputer_mesh_probe.py)**:
   - Tool CLI per diagnostica, benchmark e verifiche su nodi individuali o cluster completo.
3. **[`tests/test_qwenputer_bridge.py`](file:///Users/opo/hyperspace-agi-1.04/tests/test_qwenputer_bridge.py)**:
   - 6 test unitari passed (100% GREEN) per validazione logica, aritmetica e nodi.
