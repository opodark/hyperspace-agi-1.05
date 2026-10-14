---
name: hermes-resilience-operator
description: Guida operativa per agenti e operatori per la gestione della resilienza, snapshot cifrati e disaster recovery della memoria Hermes su cloud decentralizzati.
---

# Procedura Operativa: Gestione Resilienza e Vault Memoria Hermes
<!-- SPDX-License-Identifier: Apache-2.0 -->

Questa skill guida l'agente o l'operatore nelle procedure di salvaguardia, replica
cloud decentralizzata e disaster recovery della memoria cognitiva Hermes (`hyperspace.hermes.vault.v1`).

## 1. Principi e Vincoli di Sicurezza

1. **Zero-Knowledge Rigido**:
   - Non trasmettere o salvare mai file di memoria non cifrati su server remoti.
   - La cifratura client-side (AES-256-GCM + PBKDF2-HMAC-SHA256) è obbligatoria.
2. **Nessun Segreto nei Log o Output**:
   - `HERMES_VAULT_PASSPHRASE` e i token/chiavi di accesso cloud (S3, WebDAV, GitHub, IPFS)
     devono risiedere esclusivamente nell'ambiente o in file protetti (`HERMES_VAULT_KEY_FILE`).
   - Non stampare mai le chiavi né includerle negli output delle risposte o nei commit.
3. **Percorsi Relativi e Budget di Esecuzione**:
   - Usare sempre percorsi relativi (es. `./data/vault_backups`, `./recovery_staging`) per
     evitare violazioni di sandbox o path assoluti host.
   - Rispettare un budget massimo di 3 tentativi consecutivi per le operazioni di rete;
     in caso di timeout o fallimento ripetuto, interrompere con errore diagnostico esplicito.
4. **Snapshot Prima di Interventi Critici**:
   - Prima di eseguire migrazioni di schema, reset di container, aggiornamenti di modello
     o pulizie di memoria, creare sempre uno snapshot preventivo con tag esplicito.

## 2. Flusso di Lavoro Operativo

### Fase 1: Verifica di Connettività e Salute (Non-Mutante)
Eseguire la sonda diagnostica per accertare che i provider e la crittografia siano operativi:
```bash
python scripts/diagnostics/hermes_resilience_probe.py --json
```
- Se `encryption.configured` è `false`: informare l'operatore di impostare `HERMES_VAULT_PASSPHRASE`.
- Se nessun provider è `healthy`: verificare le credenziali S3/R2/WebDAV in `.env`.

### Fase 2: Creazione Snapshot di Sicurezza
Prima di qualsiasi operazione rischiosa, creare un vault cifrato:
```bash
python scripts/hermes_resilience.py --snapshot --tag "pre_modifica_memoria"
```
Verificare che l'output indichi:
- Esito positivo su almeno una destinazione remota (`targets_succeeded`).
- Numero di voci archiviate congruente con il database (`entries_count > 0`).

### Fase 3: Verifica Integrità Round-Trip Remota
Accertare che l'ultimo snapshot remoto sia integro e decifrabile senza alterare lo stato locale:
```bash
python scripts/hermes_resilience.py --verify
```
Confermare che l'esito riporti `[OK] Decifratura AES-256-GCM riuscita. SHA256 verificato.`

### Fase 4: Disaster Recovery (Ripristino)
In caso di corruzione del database o perdita del nodo:
1. Scaricare ed estrarre il vault in una cartella di staging isolata:
   ```bash
   python scripts/hermes_resilience.py --restore --target-dir ./recovery_staging
   ```
2. Ispezionare i file ripristinati (`hermes/MEMORY.md`, `hermes/state.sql`, `manifest.json`).
3. Re-integrare i dati nel runtime Hermes o tramite re-import idempotente:
   ```bash
   python scripts/memory_migrate.py ./recovery_staging/hyperspace/memory.json.gz
   ```

## 3. Gestione Retention e Pruning
Per evitare di superare le quote dei tier gratuiti (es. 10 GB Cloudflare R2 o Backblaze B2),
mantenere la retention a non più di 7 snapshot recenti:
```bash
python scripts/hermes_resilience.py --prune --keep 7
```
