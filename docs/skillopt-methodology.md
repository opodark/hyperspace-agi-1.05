# Metodologia SkillOpt per HyperSpace AGI
<!-- SPDX-License-Identifier: Apache-2.0 -->

## 1. Visione e motivazione

HyperSpace AGI adotta un'architettura modulare in cui il Control Plane e i worker
di Mission Control delegano la guida procedurale a **skill in formato Markdown**
(`docs/tool-skill-forge.md`, `docs/skill-hooks.md`).

Nel report condiviso del 2026-10-07 (`AGENTS.md`), l'analisi comparativa di
LangGraph, CrewAI, AutoGen e n8n ha evidenziato una regola fondamentale per la
stabilità del sistema: **non aggiungere ulteriori orchestratori o dipendenze
pesanti a runtime**, bensì rendere affidabili, deterministici e verificabili i
flussi già esistenti.

Il framework **SkillOpt** (sviluppato da Microsoft Research) introduce un paradigma
complementare perfettamente allineato con questo principio: l'**ottimizzazione
nello spazio del testo** (*text-space optimization*) per agenti basati su modelli
congelati (*frozen LLMs*).

### Il principio di base
Invece di modificare i pesi del modello (fine-tuning costoso e non portabile) o di
affidarsi a prompt engineering artigianale a tentativi, SkillOpt tratta il documento
delle istruzioni di una skill (`SKILL.md`) come un **parametro addestrabile**.

```text
[Frozen Model Execution]  --->  [Trajectory Log (Tools/Errors)]
          ^                                    |
          |                                    v
  [Validation Gate]       <---    [Optimizer Reflection & Edit]
(Accetta solo se supera
 il benchmark held-out)
```

L'ottimizzazione avviene **offline** tramite gradienti testuali guidati da un gate
deterministico. Il risultato a runtime è un semplice file Markdown statico:
- **Zero overhead a runtime**: Nessun orchestratore intermedio, nessun proxy, zero latenza aggiuntiva.
- **Portabilità completa**: Il Markdown ottimizzato funziona sia su modelli frontier remoti che su modelli open-source locali (Ollama, vLLM, sandbox offline).
- **Trasparenza**: Ogni modifica è un diff testuale ispezionabile da un umano.

---

## 2. Il Ciclo SkillOpt adattato a HyperSpace Forge

L'integrazione di SkillOpt nel ciclo di vita delle skill di HyperSpace rispetta il
contratto del Tool & Skill Forge:

```
[Dataset Missioni/Task]
          │
          ▼
┌──────────────────┐
│  Rollout Sandbox │ (Esecuzione worker su compiti di benchmark)
└─────────┬────────┘
          │ (Traiettorie, chiamate tool, codici d'uscita, errori)
          ▼
┌──────────────────┐
│ Reflection Model │ (Analisi fallimenti: path errati, tool non disponibili, ecc.)
└─────────┬────────┘
          │ (Proposta di edit testuale mirato su SKILL.md)
          ▼
┌──────────────────┐
│ Validation Gate  │ ── Rifiuta ──> [Contrastive Buffer / Scarto]
└─────────┬────────┘
          │ Accetta solo se supera metricamente la baseline
          ▼
┌──────────────────┐
│ Forge Draft      │ (Artefatto inerte con SHA-256 e limite 24.000 byte)
└─────────┬────────┘
          │ (Revisione operatore con FORGE_ADMIN_TOKEN)
          ▼
┌──────────────────┐
│ Approved Skill   │ (Iniezione deterministica via hyperspace_skills / before_context)
└──────────────────┘
```

### Fasi operative

1. **Rollout (Esecuzione controllata)**:
   Il modello target (es. il modello locale coder/worker) esegue un set di task
   riproducibili all'interno della sandbox isolata (`code_sandbox`).
2. **Reflect (Riflessione strutturata)**:
   Un modello analizzatore esamina i log di esecuzione. Identifica i pattern
   sistematici di errore:
   - Uso di percorsi assoluti non consentiti (es. `/seed/...` anziché file relativi).
   - Tentativi di usare tool non assegnati al ruolo.
   - Allucinazioni di completamento senza verifica dell'effettiva creazione degli artefatti.
   - Superamento del budget di iterazioni per loop di lettura ridondanti.
3. **Edit (Gradiente testuale delimitato)**:
   L'ottimizzatore genera una modifica circoscritta al testo della skill:
   - Aggiunta di vincoli espliciti di pre-condizione.
   - Formule di invocazione tool con parametri corretti.
   - Checklist di auto-verifica deterministica che il worker deve eseguire prima di terminare.
4. **Validation Gate (Cancello di validazione)**:
   La versione modificata viene eseguita su un set di test di validazione separato (*held-out*).
   - **Regola di ammissione**: La nuova versione viene promossa a candidato solo se
     il tasso di successo deterministico è **strettamente superiore** alla baseline.
   - In caso di parità o regressione, la modifica viene scartata e l'errore archiviato
     in un buffer contrastivo per non ripetere lo stesso tentativo.
5. **Emissione della Bozza Forge**:
   Il file ottimizzato viene confezionato come bozza inerte conforme alle regole del Forge:
   - Dimensione strettamente inferiore a **24.000 byte UTF-8**.
   - Calcolo e verifica dell'hash SHA-256.
   - Nessun privilegio o esecuzione automatica: la bozza attende approvazione esplicita
     dell'operatore (`FORGE_ADMIN_TOKEN`).

---

## 3. Applicazione al caso studio: Risoluzione P0 Missione PDF

La prova autonoma di Mission Control del 2026-10-07 (`docs/mission-pdf-trial-2026-10-07.md`)
ha evidenziato 5 fallimenti su 5 tentativi nella generazione di una presentazione PDF.
L'analisi dei fallimenti fornisce il dataset perfetto per l'ottimizzazione SkillOpt:

| Fallimento rilevato nel trial | Causa radice (dal log traiettorie) | Correttivo testuale inserito da SkillOpt |
|---|---|---|
| Planner seleziona `repo-analyst` per leggere file locali | `repo-analyst` non dispone del tool `code_sandbox` | Vincolo di ruolo: dichiarare che per compiti sui file locali serve esclusivamente `coder` con `code_sandbox`. |
| Il worker legge path assoluti rifiutati | Invocazione di path come `/seed/README.md` rifiutata dalla policy sandbox | Direttiva sui path: usare tassativamente percorsi relativi allo workspace (`README.md`). |
| Esaurimento workspace (`SANDBOX_MAX_WORKSPACES=6`) | Ripetute chiamate `create` senza cleanup | Politica lifecycle: riutilizzare o rilasciare lo workspace assegnato senza ripartire da zero. |
| Falsa dichiarazione di successo | Il modello dichiara completato il task anche se `run` ha fallito o non è stato chiamato | Gate di auto-verifica interno: eseguire `python -c "import os; assert os.path.exists('output.pdf')"` prima del messaggio finale. |
| Zero artefatti prodotti | Il worker si perde in 14 letture consecutive esaurendo il budget | Budget procedurale: massimo 3 letture esplorative, poi obbligo di scrittura script di generazione. |

Grazie a questo approccio, la skill generata (`docs/skills/pdf-mission-coder-skill.md`)
non contiene istruzioni generiche, ma incorpora esattamente le risposte strutturate
alle deviazioni misurate empiricamente.

---

## 4. Validazione deterministica degli artefatti

SkillOpt per HyperSpace impone che il *Validation Gate* non si basi su
valutatori probabilistici o "LLM-as-a-judge", ma su verificatori deterministici:

1. **Gate Codice**:
   - Exit code del processo = 0.
   - Risultato dei test (pytest / unittest) = tutti passati, 0 errori.
   - Rispetto dei limiti di dimensione e conformità licenza SPDX.
2. **Gate Documenti / PDF**:
   - File esistente nello workspace.
   - Magic bytes validi (`%PDF-` nei primi 5 byte).
   - Dimensione minima plausibile (> 1024 byte).
   - Numero di pagine > 0 verificabile programmaticamente (es. `pypdf` o `pdfinfo`).
3. **Gate Forge Compliance**:
   - Dimensione UTF-8 ≤ 24.000 byte.
   - Frontmatter YAML valido con campi obbligatori (`name`, `description`).
   - Assenza di token, password o URL interni sensibili.
   - Nessuna istruzione che richieda strumenti o permessi non concessi al ruolo.

---

## 5. Strumenti a supporto

- **Valutatore diagnostico**: `scripts/diagnostics/skillopt_evaluator.py` per
  ispezionare, calcolare l'hash SHA-256, verificare i vincoli di dimensione Forge
  e validare deterministicamente una skill candidata prima dell'importazione.
- **Skill di riferimento per Mission Control**: `docs/skills/pdf-mission-coder-skill.md`,
  bozza inerte ottimizzata per sbloccare la generazione documentale autonoma.
