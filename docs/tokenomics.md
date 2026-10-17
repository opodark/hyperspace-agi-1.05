# Tokenomics di 00MESH ($00MESH) & Predisposizione pump.fun (Solana)

Architettura economica decentralizzata per incentivare la condivisione di risorse di calcolo (GPU consumer e chip Apple Silicon) nella mesh P2P sovereign **00MESH** (sviluppata da ZeroZero Computer).

---

## 1. Visione & Modello Proof-of-Useful-Work (PoUW)

00MESH non consuma energia in calcoli crittografici a vuoto (Proof-of-Work tradizionale). La generazione di reward computazionali per i nodi si basa su due pilastri reali e verificabili:

1. **Proof-of-Useful-Work (PoUW)**: I nodi che eseguono inferenze reali per la rete (risposte chat, embedding, elaborazione video/ComfyUI o compiti di agenti sandbox) ricevono reward proporzionali alla complessità del modello e alla potenza erogata.
2. **Proof-of-Availability**: I nodi che mantengono attivo e raggiungibile il canale crittografico E2EE (`secp256k1` + `AES-256-GCM`) ricevono reward periodici per la disponibilità oraria offerta.

---

## 2. Specifiche del Token ($00MESH)

| Parametro | Valore | Note |
|---|---|---|
| **Nome del Token** | 00MESH Network Token | Token di utilità per il settlement di calcolo distribuito |
| **Simbolo / Ticker** | **`$00MESH`** | Ticker univoco su Solana SPL (evita collisioni con token esistenti) |
| **DEX / Launchpad Target** | **pump.fun (Solana SPL)** | Scelta ottimale per fee microscopiche, liquidità trasparente e bonding curve |
| **Supply Totale Fissa** | **1.000.000.000 $00MESH** | Offerta fissa non inflazionabile standard pump.fun |
| **Bonding Curve & Fair Launch** | **700.000.000 $00MESH (70.0%)** | Fornita alla bonding curve pump.fun con migrazione a Raydium al target |
| **Mesh Community Mining Pool** | **200.000.000 $00MESH (20.0%)** | Quota riservata ai nodi e ai miner che erogano calcolo PoUW |
| **Core Dev & Ecosystem Reserve** | **100.000.000 $00MESH (10.0%)** | Riserva con vesting per sviluppo runtime, bridge hardware e audit sicurezza |
| **Decimali Solana** | **6** | Standard SPL pump.fun |

---

## 3. Formule di Calcolo dei Reward PoUW

### A. Welcome Grant (Node Join)
* **Importo**: **+50.0 $00MESH**
* **Condizione**: Accreditato una tantum al primo annuncio del nodo con chiave pubblica o associazione di un wallet Solana valido.
* **Anti-Abuso**: Il registro verifica l'idempotenza; richieste successive dallo stesso `node_id` non raddoppiano il bonus.

### B. Task di Inferenza (Calcolo Utile)
La ricompensa base è pari a **2.0 $00MESH**, scalata dal moltiplicatore del modello ospitato:

$$\text{Reward} = (\text{Base} \times \text{Moltiplicatore Modello}) + \text{Bonus Durata} + \text{Bonus Token}$$

| Categoria Modello | Esempi | Moltiplicatore | Reward Base |
|---|---|---|---|
| **Leggero ($\le 4B$)** | `qwen3.5:4b`, embeddings | **1.0x** | 2.0 $00MESH |
| **Intermedio (7B - 9B)** | `qwen3:8b`, `granite3.3:8b` | **1.5x** | 3.0 $00MESH |
| **Avanzato / MoE / Ternary ($\ge 14B$)** | `Ternary-Bonsai-2-27B`, `DeepSeek-Coder-MoE` | **3.0x** | **6.0 $00MESH** |

* **Bonus Sessione**: $+0.1 \times \text{secondi}$ (se esecuzione $>5\text{s}$, max +2.0 $00MESH$).
* **Bonus Token**: $+0.5$ per ogni 500 token generati.

### C. Uptime & Disponibilità
* **Importo**: **5.0 $00MESH per ora** di uptime verificato con canale sicuro attivo.

---

## 4. Integrazione con pump.fun & Wallet Solana

I punti vengono inizialmente accumulati e tracciati nel ledger crittografico del Control Plane (tabelle SQLite `token_wallets` e `token_transactions`).

Per consentire ai proprietari dei nodi di convertire i punti accumulati nei token reali al momento del deploy su pump.fun:

1. **Collegamento Wallet Phantom / Solflare**:
   Ogni proprietario di nodo associa la propria chiave pubblica Solana (Base58, 32-44 caratteri) al proprio `node_id`.
   ```bash
   # Associazione da CLI
   .venv/bin/python scripts/tokenomics_cli.py link-wallet <node_id> <indirizzo_solana>
   ```
   Oppure direttamente dal browser inserendo l'indirizzo nel box "Avvia Nodo".
2. **Generazione dello Snapshot di Claim**:
   Al momento del lancio su pump.fun, 00MESH genera uno **Snapshot di Airdrop**:
   ```bash
   .venv/bin/python scripts/tokenomics_cli.py snapshot
   ```
   Ciascun nodo riceve una quota di token SPL direttamente proporzionale ai punti PoUW minati:
   $$\text{Token SPL Assegnati} = \frac{\text{Punti Nodo}}{\text{Totale Punti Minati}} \times \text{Pool Community (200.000.000)}$$

---

## 5. Console CLI `scripts/tokenomics_cli.py`

```bash
# 1. Panoramica globale della tokenomics
.venv/bin/python scripts/tokenomics_cli.py status

# 2. Classifica miner e nodi più attivi
.venv/bin/python scripts/tokenomics_cli.py leaderboard

# 3. Accreditamento manuale / test per onboarding nodo
.venv/bin/python scripts/tokenomics_cli.py reward-join node-hp-omen-16 --tier hub

# 4. Accreditamento task di inferenza
.venv/bin/python scripts/tokenomics_cli.py reward-task node-hp-omen-16 --task-id task-01 --model "Ternary-Bonsai-2-27B"

# 5. Collegamento indirizzo Solana Phantom
.venv/bin/python scripts/tokenomics_cli.py link-wallet node-hp-omen-16 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU

# 6. Esportazione snapshot pump.fun in JSON
.venv/bin/python scripts/tokenomics_cli.py snapshot --json
```

---

## 6. Endpoint REST nel Control Plane (`control-plane/cp/webnode.py` & `mesh.py`)

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/web/tokenomics/status` | Statistiche globali supply emessa, pool e nodi |
| `GET` | `/web/node/balance?node_id=<id>` | Saldo reale, task eseguiti e wallet Solana del nodo |
| `POST` | `/web/node/wallet` | Associa o aggiorna il wallet Solana per un nodo web (`{"node_id": "...", "solana_address": "..."}`) |
| `GET` | `/tokenomics/leaderboard` | Classifica nodi per token accumulati |
| `GET` | `/tokenomics/snapshot` | Esporta il payload di claim/airdrop per pump.fun |

---

## 7. Disclaimer Legale & Conformità Regolamentare (MiCA / UE 2023/1114)

> [!IMPORTANT]
> **Avviso Legale Obbligatorio:**
> 1. **Natura del Token**: `$00MESH` è un utility token sperimentale e un sistema di punti computazionali a supporto della ricerca e dello sviluppo di reti di intelligenza artificiale distribuite.
> 2. **Assenza di Rendimenti Garantiti**: L'assegnazione di punti PoUW o token non costituisce alcuna promessa di rendita passiva, dividendo, quota di partecipazione societaria o investimento finanziario ai sensi del Regolamento Europeo MiCA (UE 2023/1114) e della normativa Consob / Testo Unico della Finanza (TUF).
> 3. **Proventi dell'Infrastruttura**: Eventuali proventi da servizi terzi o sponsorizzazioni sono destinati unicamente al rimborso delle spese computazionali dei nodi e al mantenimento dell'infrastruttura open-source della rete.
> 4. **Fase Sperimentale**: Il software e la mesh sono attualmente in fase di testnet e sviluppo attivo. Prima di effettuare qualunque transazione o interazione su blockchain, consultare un professionista legale qualificato.
