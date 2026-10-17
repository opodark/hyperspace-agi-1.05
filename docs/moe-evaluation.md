# SPDX-License-Identifier: Apache-2.0
# docs/moe-evaluation.md
# HyperSpace AGI 1.05 — Valutazione Architetturale Modelli MoE (Mixture of Experts)

Questo documento analizza e formalizza la strategia di adozione dei modelli **Mixture of Experts (MoE)** per la flotta distribuita di nodi portatili HyperSpace AGI (MacBook Pro, ASUS V16, HP Omen 16 con GPU NVIDIA RTX da 8 GB di VRAM).

---

## 1. Il Problema Empirico dei Modelli Densi (Dense Models) su 8 GB VRAM

Durante i test sul nodo **HP Omen 16** (NVIDIA RTX, 8 GB VRAM), il confronto empirico su task di generazione codice ha evidenziato una soglia hardware invalicabile per i modelli densi tradizionali:

| Famiglia / Modello | Parametri | Impronta Pesi | Spazio VRAM Libero per KV Cache | Esito Inferenza | Throughput Reale |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`qwen3.5:4b`** | 4B (Denso) | ~2.5 GB | ~5.5 GB (Ampio) | **Successo** | ~45.0 tok/s |
| **`qwen3-8b-abliterated`** | 8B (Denso) | ~5.0 GB | ~3.0 GB (Ottimale) | **Successo** | **67.2 tok/s** |
| **`granite3.3:8b`** | 8B (Denso) | ~5.1 GB | ~2.9 GB (Ottimale) | **Successo** | **28.6 tok/s** |
| **`qwen3.5-abliterated:9b`** | 9B (Denso) | ~5.8 GB | ~2.2 GB (Ristretto) | **Successo (lento)** | 4.6 tok/s |
| **`gemma-4-abliterated:12b`**| 12B (Denso) | **7.54 GB** | **< 460 MB (Critico)** | **TIMEOUT (>120s)** | ~1.5 tok/s (swapping PCIe) |

### Diagnosi del Bottleneck VRAM:
Nei modelli densi, **tutti i parametri vengono calcolati per ogni singolo token**. A partire da ~9B-12B parametri, i pesi statici occupano quasi interamente gli 8 GB fisici di memoria video. Non appena vengono allocate la **KV Cache** di contesto e le matrici intermedie di attenzione:
1. La VRAM fisica viene esaurita.
2. Il runtime WDDM (Windows/WSL2) o Linux inizia a riversare le pagine di memoria video nella **RAM di sistema condivisa attraverso il bus PCIe**.
3. La banda di memoria crolla da **~300-400 GB/s (GDDR6 interna)** a **~30-50 GB/s (PCIe)**, provocando una caduta verticale del throughput sotto i 2 token/secondo e superando il timeout del worker di HyperSpace.

---

## 2. Perché i Modelli MoE Risolvono il Problema

Un'architettura **Mixture of Experts (MoE)** separa la **capacità cognitiva totale** del modello dal **costo computazionale per singolo token**:

```
                       Input Token
                            │
                     ┌──────▼──────┐
                     │ Gating Router│
                     └──────┬──────┘
             ┌──────────────┼──────────────┐
             ▼ (Top-1)      ▼ (Top-2)      ▽ (Inerte)
       ┌───────────┐  ┌───────────┐  ┌───────────┐
       │ Esperto 1 │  │ Esperto 2 │  │ Esperto N │
       └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
             └──────────────┼──────────────┘
                            ▼
                      Output Token
```

1. **Parametri Attivi Ridotti**: Un modello MoE da 16B parametri totali può avere solo **2.4B - 3B parametri attivi** per token (calcolo equivalente a un modello leggerissimo).
2. **Throughput Elevatissimo**: Poiché il calcolo FLOPs per token coinvolge solo 2 esperti su N, la velocità di inferenza resta compresa tra **30 e 50 token/s**.
3. **Qualità da Modello Superiore**: La conoscenza accumulata in 8 o 16 esperti specializzati (codice, logica, refactoring, documentazione) supera quella di un modello denso equivalente a parità di memoria attiva.

---

## 3. I Migliori Candidati MoE per i Nodi HyperSpace (8 GB VRAM)

### 🥇 1. `DeepSeek-Coder-V2-Lite-Instruct`
- **Architettura**: MoE con 16B parametri totali, **2.4B attivi per token** (Top-2 esperti attivati per strato).
- **Contesto**: Finestra fino a 32k/128k token nativi (Yarn).
- **Impronta Memoria**:
  - `Q4_K_M`: ~8.9 GB (richiede CPU offload parziale).
  - `Q3_K_M` / `IQ3_M`: **~6.8 GB** (entra interamente nella VRAM da 8 GB).
- **Idoneità HyperSpace**: Modello di riferimento per programmazione Python, shell script, YAML Compose e frontend web.

### 🥈 2. `Qwen2.5-Coder-MoE` / `Qwen1.5-MoE-A2.7B`
- **Architettura**: 14.3B parametri totali, **2.7B attivi per token**.
- **Impronta Memoria**: ~7.0 GB a 4-bit.
- **Idoneità HyperSpace**: Allineato al dialetto di Qwen (con cui i prompt di sistema di HyperSpace sono già rodati). Elevata precisione nelle chiamate di funzione JSON.

### 🥉 3. `MiniCPM-MoE-8x2B`
- **Architettura**: 8 esperti da 2B ciascuno (totale ~16B), **4B attivi per token**.
- **Impronta Memoria**: **~5.2 GB** a 4-bit.
- **Idoneità HyperSpace**: Si adatta con margine di sicurezza ampio nella VRAM da 8 GB, lasciando oltre 2.8 GB liberi per KV Cache ad alta concorrenza e task paralleli.

---

## 4. Matrice di Assegnazione Ruoli nella Mesh HyperSpace 1.05

In base ai risultati dei test odierni e alla policy energetica ([`docs/power-policy.md`](power-policy.md)):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CLASSIFICAZIONE DEL CARICO                       │
├────────────────────────┬──────────────────────────┬────────────────────┤
│ Categoria Task         │ Modello Consigliato      │ Vincolo Energetico │
├────────────────────────┼──────────────────────────┼────────────────────┤
│ Triage sub-50ms        │ Laya System 1            │ Qualsiasi (anche <20%)
│ Chat rapida / status   │ qwen3.5:4b (45 tok/s)    │ AC o Batteria >20% │
│ Coding intensivo/diff  │ qwen3:8b (67 tok/s)      │ Priorità Presa AC  │
│ Deep Reasoning & MoE   │ DeepSeek-Coder-V2-Lite   │ Solo Presa fissa AC│
│ Vision & Diffusion     │ ComfyUI SDXL / Apple ML  │ Rigorosamente AC   │
└────────────────────────┴──────────────────────────┴────────────────────┘
```

---

## 5. Passi Operativi per il Prossimo Sprint

1. **Pull di prova del modello MoE compatto su HP Omen**:
   ```bash
   ollama pull deepseek-coder-v2:16b-lite-instruct-q3_K_M
   # oppure
   ollama pull qwen2.5-coder:7b-instruct-q4_K_M
   ```
2. **Benchmark con la suite mesh**:
   Eseguire il probe di latenza su task da 1000+ token per validare che il throughput si mantenga costantemente > 30 tok/s senza superare i 120s di timeout.
3. **Routing Automatico MoE nel Control-Plane**:
   Aggiornare [`control-plane/routing.py`](../control-plane/routing.py) con il tag capability `moe-inference` per instradare automaticamente i task di refactoring complesso verso il nodo Omen alimentato da rete elettrica.
