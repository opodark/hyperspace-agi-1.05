# Bio-Mimetic Spore Continuity & Sovereign Disaster Recovery (`shared/spore_protocol.py`)

Questo documento descrive l'architettura delle **Endospore Crittografiche** di HyperSpace AGI: il sistema di salvaguardia biomimetica progettato per garantire la sopravvivenza della memoria cognitiva, del grafo causale e dell'intera codebase anche nello scenario estremo in cui:

1. I nodi primari della Mesh (**Mac M5 Hub**, **HP OMEN 16**, **ASUS V16**) siano spenti, distrutti o irraggiungibili.
2. Il fondatore (**Alberto Marinoni**) perda temporaneamente o permanentemente l'accesso alla propria identità digitale primaria, ai propri gestori di password o ai propri account principali.

---

## 1. Principio Biomimetico: Endospora Dormiente Zero-Knowledge

In biologia, un'*endospora batterica* non è un organismo aggressivo o auto-replicante incontrollato: è una **capsula metabolicamente dormiente, corazzata e impermeabile**, capace di resistere nel vuoto, nel ghiaccio o nel deserto finché non incontra un substrato autorizzato e il segnale chimico di germinazione.

Allo stesso modo, una **Spora HyperSpace (`.hspore`)**:
- È **ermeticamente cifrata** con **AES-256-GCM** e derivazione **HKDF-SHA256** (formato binario autenticato `HSPORE01` con Associated Data JSON).
- È **Zero-Knowledge verso il Cloud**: può essere depositata su **MEGA**, **Dropbox**, **OneDrive**, **Google Drive**, **S3** o **Aruba** senza che nessun provider possa leggerne il contenuto o bloccarla per violazione dei Termini di Servizio (poiché viene caricata su account legittimamente configurati con `rclone` o client desktop).
- È **Indipendente dalle Password Abituali**: la chiave a 256 bit della Spora viene suddivisa tramite **Shamir's Secret Sharing su campo finito $\text{GF}(2^8)$** (polinomio di Rijndael `0x11b`) in un **Quorum $K$-su-$N$** (default **2-su-3**).

---

## 2. Il Quorum di Shamir (2-su-3) Contro la Perdita di Identità Digitale

Ogni volta che viene generata una Spora (o usando una Master Key persistente di continuità), la chiave di decifratura a 256 bit viene divisa in **3 frammenti matematici (`HSP-SPORE-V1`)**:

| Indice | Custode Designato | Dove conservarlo |
|---|---|---|
| **Share #1** | `alberto-founder` | Cassaforte personale / chiavetta hardware di Alberto Marinoni |
| **Share #2** | `guido-cips-partner` | Consegnato fuori banda a **Guido Cipolla ("Cips")**, socio e ingegnere di rete |
| **Share #3** | `offline-paper-vault` | Stampato su carta / inciso su piastrina metallica in luogo fisico sicuro (Verbania) |

### Proprietà Matematiche Garantite
- **Qualsiasi coppia di frammenti ricostruisce il 100% della chiave**:
  - Se Alberto perde tutte le proprie password digitali (`Share #1` perso), **Guido (`Share #2`) + il foglio cartaceo (`Share #3`)** rigenerano l'intero nodo HyperSpace.
  - Se un malintenzionato compromette un singolo frammento (es. trova un solo codice), ottiene **0 bit di informazione** (sicurezza teorico-informazionale perfetta di Shamir: ogni byte in $\text{GF}(2^8)$ resta equiprobabile tra `0x00` e `0xFF`).

---

## 3. Contenuto di una Capsula `.hspore`

Ogni file `spore-<timestamp>-<id>.hspore` racchiude in un unico archivio cifrato e firmato SHA-256:

1. **`codebase/repo.bundle`**: `git bundle` completo dell'intera storia del repository (clonabile offline con `git clone repo.bundle` senza bisogno di GitHub).
2. **`workspace/` (Memoria & Grafo)**:
   - `data/control-plane/memory.json.gz` (Memoria runtime Hermes)
   - `data/control-plane/hyperspace.db` e `data/causal_memory.db` (Database SQLite e lineage causale)
   - `data/control-plane/diario.json`, `data/persona-anna.json`, `data/persona-aurora.json`
   - `AGENTS.md`, `AGENT-LOG.md`, `CLAUDE.md`
3. **`vault/secrets.vault.enc` (Opzionale, Doppio Livello)**:
   - Envelope interno cifrato con una sotto-chiave HKDF separata (`hyperspace-spore-secrets-v1`) per le variabili d'ambiente critiche, mai esposte nel manifest pubblico.
4. **`bootstrap/germinate_spore.py`**:
   - Script autonomo di germinazione per ricostruire l'ambiente su qualsiasi nuovo host Linux o macOS.

---

## 4. Configurazione Multi-Cloud (MEGA, Dropbox, OneDrive) con `rclone`

Per distribuire automaticamente le Spore sui tuoi account cloud senza dipendere da un singolo fornitore:

```bash
# 1. Installa rclone sul nodo (macOS / Linux)
brew install rclone

# 2. Configura i tuoi remote ufficiali (una sola volta)
rclone config
# -> Crea un remote chiamato "mega" (tipo: mega)
# -> Crea un remote chiamato "dropbox" (tipo: dropbox)
# -> Crea un remote chiamato "onedrive" (tipo: onedrive)
```

In alternativa, se usi le applicazioni desktop ufficiali di MEGA, Dropbox o OneDrive, lo strumento rileva automaticamente le cartelle locali `~/MEGA`, `~/Dropbox`, `~/OneDrive` e vi deposita le capsule cifrate `.hspore`.

---

## 5. Flussi Operativi (`scripts/diagnostics/spore_continuity_manager.py`)

### A. Diagnostica Sola Lettura (Sentinella + Substrati + Integrità Spore)
```bash
.venv/bin/python scripts/diagnostics/spore_continuity_manager.py
```

### B. Sporulazione (Creazione di una Nuova Spora + Verifica Germinazione)
```bash
.venv/bin/python scripts/diagnostics/spore_continuity_manager.py \
    --create-spore \
    --verify-roundtrip
```
- Crea `data/spores/spore-<timestamp>-<id>.hspore` e `.manifest.json`.
- Salva i 3 frammenti Shamir in `data/spores/spore-<timestamp>-<id>.quorum-kit.secret.json` con permessi `0600` (escluso da Git).
- Con `--verify-roundtrip`, testa immediatamente la germinazione usando solo i frammenti `#2` (`guido-cips-partner`) e `#3` (`offline-paper-vault`), simulando la perdita totale delle chiavi del fondatore.

### C. Dispersione Multi-Cloud su MEGA, Dropbox, OneDrive o Cartelle Locali
```bash
.venv/bin/python scripts/diagnostics/spore_continuity_manager.py \
    --disperse data/spores/<id>.hspore \
    --rclone-remote mega:hyperspace-spores \
    --rclone-remote dropbox:hyperspace-spores \
    --rclone-remote onedrive:hyperspace-spores \
    --local-vault ~/MEGA/HyperSpace-Spores
```

### D. Germinazione di Emergenza su un Nuovo Nodo (Ripartenza da Zero)
Su qualsiasi macchina (es. HP OMEN 16, ASUS V16 o un nuovo server Linux/Mac) in possesso del file `.hspore` scaricato da MEGA/Dropbox/OneDrive e di **2 frammenti su 3**:

```bash
.venv/bin/python -c '
from pathlib import Path
from shared.spore_protocol import ShamirQuorumVault, SporeBuilder

key = ShamirQuorumVault.recover_secret([
    "HSP-SPORE-V1:2:2:3:guido-cips-partner:...",
    "HSP-SPORE-V1:3:2:3:offline-paper-vault:..."
])
res = SporeBuilder.germinate_spore(
    spore_path=Path("spore-xxx.hspore"),
    master_key=key,
    target_dir=Path("./hyperspace-reborn"),
    restore_secrets=True
)
print(res)
'
```
Una volta germinata la directory `./hyperspace-reborn`, è possibile ricostruire il repository completo con `git clone repo.bundle hyperspace-repo` e sovrapporre la memoria cognitiva estratta.


---

## 6. "Message in a Bottle" Multi-Blockchain (`BlockchainBottleBeacon`)

Anche qualora un dominio DNS scadesse o non ricordassi più gli URL dei mirror su MEGA, Dropbox, OneDrive o i CID IPFS/Arweave, ogni Spora genera automaticamente un file **`<spore_id>.blockchain-bottle.json`** contenente tre formati di **faro immutabile on-chain**:

1. **Reti EVM (`Polygon`, `Base`, `Arbitrum`, `Optimism`, `Ethereum`) — Calldata `0x...`**:
   - Formato ASCII autenticato: `HSP-BOTTLE-V1|<spore_id>|<spore_sha256>|<salt_hex>|<aes_gcm_base64>`
   - Contiene al suo interno (cifrato con **AES-256-GCM** usando una sotto-chiave HKDF derivata dalla stessa Master Key del Quorum di Shamir 2-su-3):
     - La lista completa dei `locators` (`mega:...`, `dropbox:...`, `onedrive:...`, `ipfs://...`).
     - L'epistola di continuità del fondatore (`founder_epistle`).
     - L'ancora crittografica `spore_sha256` e `git_head_commit`.
   - Costo di inscrizione su L2 (Polygon, Base, Arbitrum): **$< \$0.002$** per bottiglia invia una transazione a valore `0` verso l'indirizzo faro `0x0000000000000000000000000000000000485350` (`0x...HSP`).

2. **Bitcoin (`OP_RETURN`, 80 byte esatti)**:
   - Rispetta il limite standard di relay di 80 byte di Bitcoin Core:
     - `4B`: Magic `HSP1` (`48535031`)
     - `4B`: Versione (`0x01`) + Timestamp Epoch mod $2^{24}$
     - `4B`: Primi 4 byte del commit Git (`HEAD`)
     - `32B`: Hash **SHA-256 integrale** della capsula `.hspore`
     - `16B`: Salt crittografico
     - `20B`: Primi 20 byte dell'`HMAC-SHA256` della lista dei mirror

3. **Solana (`SPL Memo Program` — `MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr`)**:
   - Stringa compatta pronta per essere allegata a qualsiasi transazione Solana tramite `--with-memo`.

### Come Aprire una Bottiglia letta da una Blockchain Pubblica
Chiunque disponga di **2 frammenti Shamir su 3** può leggere il campo `input` (`0x...`) della transazione da qualsiasi block explorer o nodo RPC pubblico e decifrare all'istante le coordinate dei mirror:

```python
from shared.spore_protocol import BlockchainBottleBeacon, ShamirQuorumVault

master_key = ShamirQuorumVault.recover_secret([SHARE_2_GUIDO, SHARE_3_PAPER])
bottle = BlockchainBottleBeacon.open_bottle("0x4853502d424f54544c45...", master_key)
print("Mirror dove scaricare la Spora:", bottle.locators)
print("SHA-256 atteso:", bottle.spore_sha256)
print("Messaggio del fondatore:", bottle.founder_epistle)
```
