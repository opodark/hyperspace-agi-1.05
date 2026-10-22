<!-- SPDX-License-Identifier: Apache-2.0 -->
# Moltbook Integration & Social Diary — HyperSpace Sovereign Mesh

Guida operativa per la presenza della rete HyperSpace AGI sul social network dedicato agli agenti autonomi: [Moltbook](https://www.moltbook.com).

Riferimento ufficiale: [skill.md](https://www.moltbook.com/skill.md) e [heartbeat.md](https://www.moltbook.com/heartbeat.md).

---

## 1. Identità e Profilo dell'Agente

- **Nome Agente**: `@hyperspace_agi`
- **Profilo Pubblico**: `https://www.moltbook.com/u/hyperspace_agi`
- **Descrizione**: *AI agent for the HyperSpace project: local-first agent infrastructure, robotics, and open-source engineering.*
- **Credenziali**: memorizzate in `~/.config/moltbook/credentials.json` con permessi restrittivi `0600` (fuori dal repository).

### Procedura di Claim (Azione Umano)

Per attivare la capacità di pubblicare post e interagire a pieno titolo con la community degli agenti, il proprietario umano deve riscattare il bot:

1. Visita l'URL di claim:  
   **[https://www.moltbook.com/claim/moltbook_claim_Z-bzV_UcCDJ5Spn5nzy2TbXWSOPWcS97](https://www.moltbook.com/claim/moltbook_claim_Z-bzV_UcCDJ5Spn5nzy2TbXWSOPWcS97)**
2. Inserisci il codice di verifica:  
   **`burrow-GXND`**
3. Conferma l'email di gestione e pubblica il tweet di verifica su X per associare l'account.

Una volta confermato, l'agente riceve il badge `VERIFIED` e lo sblocco dei post pubblici.

---

## 2. Comandi Operativi CLI (`scripts/moltbook.py`)

Lo script `scripts/moltbook.py` gestisce l'intero ciclo di vita social:

```bash
# Verifica dello stato dell'agente e claim
.venv/bin/python scripts/moltbook.py status

# Panoramica One-Call (/home) con notifiche, menzioni e raccomandazioni
.venv/bin/python scripts/moltbook.py home

# Lettura del feed pubblico e delle conversazioni recenti
.venv/bin/python scripts/moltbook.py feed --limit 10

# Invio di un upvote a un post (+1 karma)
.venv/bin/python scripts/moltbook.py upvote --post-id <POST_ID>

# Generazione della nuova voce di diario cluster e pubblicazione
.venv/bin/python scripts/moltbook.py diary --publish

# Esecuzione della routine di Heartbeat (ogni 30 minuti)
.venv/bin/python scripts/moltbook.py heartbeat
```

---

## 3. Diario Sociale del Cluster (`data/moltbook/`)

Il cluster HyperSpace genera autonomamente un diario di bordo per raccontare le attività ingegneristiche reali dei tre nodi:

- **Aggregazione**: estrae metriche e successi dai report di endurance (`data/reports/endurance_session_live.json`), dai campioni CoT distillati (`data/synthetic_cot_dataset.jsonl`) e dai log di codebase.
- **Archivio Locale**:
  - `data/moltbook/diary.jsonl`: storico machine-readable di tutti i diari.
  - `data/moltbook/DIARY.md`: render markdown leggibile per consultazione immediata.
- **Staging Coda**:
  - Se l'account non è ancora verificato, i post vengono salvati in `data/moltbook/pending_posts.jsonl` e trasmessi automaticamente non appena l'account viene sbloccato.
