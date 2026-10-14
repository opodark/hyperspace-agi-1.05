# Resilienza e Decentralizzazione Cloud della Memoria Hermes

La memoria di **Hermes Agent** rappresenta l'unica fonte di verità cognitiva di HyperSpace
(`MEMORY.md`, `USER.md`, `state.db` con FTS5, `skills/` e il mirror locale `memory.json.gz`).
Se il nodo che ospita Hermes subisce un guasto hardware, perdita disco o disconnessione prolungata,
è fondamentale garantire un meccanismo di disaster recovery e resilienza distribuita.

Il sottosistema **Hermes Multi-Cloud Resilience Vault** implementa una strategia di replica
multi-provider e decentralizzata, basata su crittografia client-side **Zero-Knowledge** e supporto
a opzioni cloud sia gratuite (con ampi free tier) sia proprietarie o decentralizzate P2P.

---

## 1. Architettura di Sicurezza Zero-Knowledge

La memoria cognitiva contiene conversazioni, riflessioni e preferenze confidenziali dell'utente.
I provider cloud di terze parti **non devono mai avere accesso al contenuto in chiaro**.

```text
                  [ Hermes Host / Node ]
    MEMORY.md, USER.md, state.db, skills, memory.json.gz
                             │
                             ▼
                 [ Tar.Gz Memory Bundle ]
                             │
       PBKDF2-HMAC-SHA256 (100.000 iterazioni, salt 16B)
                             │
                             ▼
               AES-256-GCM (Nonce 12B casuale)
          Header JSON AAD autenticato (HSMV v1.0)
                             │
                             ▼
              [ .vault Pacchetto Cifrato ]
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
   Cloudflare R2         Nextcloud           GitHub Gist /
  Backblaze B2 (S3)       (WebDAV)            IPFS (P2P)
   (10 GB gratuiti)     (Autohosted)        (Decentralizzato)
```

### Specifiche dell'Envelope Vault (`hyperspace.hermes.vault.v1`)
Ogni snapshot viene generato come file `.vault` auto-consistente:
- **Magic Byte**: `HSMV` (4 byte)
- **Header Length**: Intero unsigned a 32-bit (big-endian)
- **Header JSON (Autenticato come AAD)**:
  - `snapshot_id`: Identificativo univoco temporale con precisione al microsecondo (`hermes-snap-YYYYMMDD-HHMMSS-micros-hex`)
  - `algorithm`: `AES-256-GCM`
  - `kdf`: `PBKDF2-HMAC-SHA256` (100.000 iterazioni)
  - `salt_b64`: Salt crittografico a 16 byte
  - `nonce_b64`: Nonce monouso a 12 byte
  - `unencrypted_sha256`: Hash di integrità del payload chiaro
  - `metadata`: Conteggio voci, manifest file inclusi, tag
- **Ciphertext**: Dati cifrati con tag di autenticazione GCM a 16 byte in coda.
Qualsiasi manomissione dei dati o dell'header provoca il fallimento immediato della decifratura (`InvalidTag`).

---

## 2. Opzioni di Archiviazione Supportate (Gratuite e a Pagamento)

Il sistema supporta la configurazione simultanea di molteplici backend, applicando la regola di backup **3-2-1** (almeno 3 copie, su 2 supporti diversi, di cui 1 off-site):

| Provider / Protocollo | Tipo | Costo / Free Tier | Note Operative |
|---|---|---|---|
| **Cloudflare R2** | S3-compatible | **10 GB gratuiti per sempre**, 0 egress fees | Eccellente: zero costi di download/restore |
| **Backblaze B2** | S3-compatible | **10 GB gratuiti**, API S3 nativa | Molto economico oltre il free tier |
| **AWS S3 / Wasabi / MinIO** | S3-compatible | A consumo / Self-hosted | Pieno supporto SigV4 senza dipendenze pesanti |
| **Nextcloud / pCloud / Koofr** | WebDAV | Gratuito (self-hosted o tier free) | Standard aperto, zero lock-in |
| **GitHub Gist (Secret)** | Git API | **Gratuito** | Storico versionato distribuito nativo |
| **IPFS / Pinata** | Web3 P2P | Gratuito (Pinata 1 GB free / nodo locale) | Content-addressable decentralizzato |
| **Filesystem / rclone** | Locale / Mount | Gratuito | Per mount point Google Drive, Dropbox, NAS, USB |

---

## 3. Configurazione (`.env`)

Tutte le credenziali sono lette dalle variabili d'ambiente e non vengono mai stampate nei log o negli output diagnostici:

```dotenv
# Passphrase master per la cifratura AES-256-GCM (obbligatoria per i backup)
HERMES_VAULT_PASSPHRASE="la-tua-chiave-segreta-robusta"
# Oppure percorso file contenente la chiave:
# HERMES_VAULT_KEY_FILE=/app/data/hermes-vault.key

# Quanti snapshot storici conservare sui remoti (default: 7)
HERMES_VAULT_RETENTION_COUNT=7

# Directory per snapshot locali o mount point rclone/NAS
HERMES_VAULT_LOCAL_DIR="data/vault_backups"

# --- Provider S3 / Cloudflare R2 / Backblaze B2 ---
HERMES_VAULT_S3_ENDPOINT="https://<account_id>.r2.cloudflarestorage.com"
HERMES_VAULT_S3_BUCKET="hyperspace-hermes-memory"
HERMES_VAULT_S3_KEY="<access_key_id>"
HERMES_VAULT_S3_SECRET="<secret_access_key>"
HERMES_VAULT_S3_REGION="auto"
HERMES_VAULT_S3_PREFIX="hermes-vault/"

# --- Provider WebDAV (Nextcloud, ownCloud, pCloud) ---
# HERMES_VAULT_WEBDAV_URL="https://nextcloud.tuodominio.com/remote.php/dav/files/utente"
# HERMES_VAULT_WEBDAV_USER="utente"
# HERMES_VAULT_WEBDAV_PASS="app-password-dedicata"

# --- Provider GitHub Gist (Privato) ---
# HERMES_VAULT_GITHUB_TOKEN="ghp_token..."
# HERMES_VAULT_GITHUB_GIST_ID="<opzionale_creato_in_automatico>"

# --- Provider IPFS / Pinata ---
# HERMES_VAULT_IPFS_API="http://127.0.0.1:5001"
# HERMES_VAULT_PINATA_JWT="eyJ..."
```

---

## 4. Strumenti Operativi e CLI

### 4.1 CLI di Gestione (`scripts/hermes_resilience.py`)

Lo script CLI permette il controllo completo di snapshot, verifica e ripristino:

```bash
# Mostra lo stato di salute dei provider e della crittografia
python scripts/hermes_resilience.py --status

# Crea uno snapshot cifrato e lo propaga a tutti i cloud configurati
python scripts/hermes_resilience.py --snapshot --tag "pre_aggiornamento"

# Elenca tutti gli snapshot disponibili nei vault remoti
python scripts/hermes_resilience.py --list

# Esegue un test di verifica di connettività e integrità dell'ultimo vault
python scripts/hermes_resilience.py --verify

# Ripristina uno snapshot in una directory per disaster recovery
python scripts/hermes_resilience.py --restore --target-dir ./hermes_ripristinato

# Pota gli snapshot più vecchi oltre la soglia di retention (es. 5)
python scripts/hermes_resilience.py --prune --keep 5
```

### 4.2 Sonda Diagnostica HyperSpace (`scripts/diagnostics/hermes_resilience_probe.py`)

Sonda conforme alla **Regola 6 di AGENTS.md**, sicura e read-only (nessun segreto emesso):

```bash
python scripts/diagnostics/hermes_resilience_probe.py
python scripts/diagnostics/hermes_resilience_probe.py --json
```

---

## 5. API Control Plane (`/memory/resilience/*`)

Il Control Plane pubblica quattro endpoint dedicati alla gestione della resilienza:

- **`GET /memory/resilience/status`**: Restituisce lo stato dei backend, la presenza della chiave di cifratura e i dettagli dell'ultimo check.
- **`GET /memory/resilience/snapshots`**: Elenca gli snapshot disponibili deduplicati su tutti i cloud.
- **`POST /memory/resilience/snapshot`**: Crea uno snapshot su richiesta e lo invia a tutti i backend attivi. Payload opzionale: `{"tag": "manual_backup"}`.
- **`POST /memory/resilience/verify`**: Esegue la verifica di connettività e integrità crittografica dell'ultimo vault.

---

## 6. Procedura di Disaster Recovery (Ripristino)

In caso di guasto totale del nodo principale:

1. **Configurare la chiave su nuova macchina**:
   ```bash
   export HERMES_VAULT_PASSPHRASE="la-tua-chiave-segreta"
   # Configurare i puntatori S3/WebDAV al bucket esistente
   ```
2. **Scaricare e decifrare l'ultimo snapshot valido**:
   ```bash
   python scripts/hermes_resilience.py --restore --target-dir ./recovery_hermes
   ```
3. **Verificare i file estratti**:
   La directory `./recovery_hermes` conterrà:
   - `hermes/MEMORY.md` e `hermes/USER.md`
   - `hermes/state.sql` (dump consistente SQLite FTS5)
   - `hermes/skills/`
   - `hyperspace/memory.json.gz` (mirror delle voci HyperSpace)
   - `manifest.json`
4. **Re-integrazione**:
   - I file Markdown e SQLite possono essere posizionati in `$HERMES_HOME`.
   - Se il bridge Hermes è già avviato, `scripts/memory_migrate.py` o il restore automatico re-inietta le voci attraverso `import_entries()` con dedup idempotente garantita.
