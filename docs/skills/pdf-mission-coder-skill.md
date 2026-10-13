---
name: hyperspace-pdf-mission-coder
description: Guida operativa per coder worker in Code Sandbox per l'estrazione dati e generazione autonoma e verificata di presentazioni PDF riproducibili.
---

# Procedura Operativa: Generazione PDF in Code Sandbox
<!-- SPDX-License-Identifier: Apache-2.0 -->

Questa skill guida il worker con ruolo `coder` e tool `code_sandbox` nella
creazione deterministica di documenti e presentazioni PDF, evitando i tipici
blocchi di esecuzione e le chiamate tool rifiutate.

## 1. Regole e Vincoli di Esecuzione

1. **Percorsi Tassativamente Relativi**:
   - Tutte le chiamate `read`, `write` e `run` devono usare percorsi relativi alla
     radice del proprio workspace (es. `README.md`, `docs/mission-control.md`, `generate.py`).
   - Non usare MAI percorsi assoluti come `/seed/...` o `/Users/...`: verranno
     rifiutati dalla policy di sicurezza del sandbox con errore `path_denied`.
2. **Budget Esplorativo Rigido**:
   - Limita la lettura preliminare a massimo **3 file mirati** (es. `README.md`,
     `VISION.md` e il documento di riferimento).
   - Non eseguire letture speculative ad anello o listature ricorsive: consumano
     rapidamente il budget di iterazioni del controller.
3. **Generazione Tramite Script Python Riproducibile**:
   - Non tentare di scrivere binari PDF direttamente.
   - Scrivi sempre uno script Python (`build_presentation.py`) che utilizza
     le librerie grafiche disponibili nell'immagine sandbox (es. `reportlab`, `fpdf2`
     o script di composizione SVG/Canvas con esportazione PDF).
   - Includi sempre gestione degli errori e output di log sintetici.
4. **Verifica Deterministica dell'Artefatto (Gate Obbligatorio)**:
   Prima di dichiarare il task completato, esegui un comando di verifica formale
   nello sandbox:
   ```bash
   python -c "import os; p='presentation.pdf'; assert os.path.exists(p) and os.path.getsize(p) > 1024; f=open(p,'rb'); assert f.read(5)==b'%PDF-'; print('GATE_VERIFIED_OK')"
   ```
   - Se lo script fallisce o l'output non contiene `GATE_VERIFIED_OK`, il task
     è **fallito**: correggi l'errore o documenta il blocco specifico. Non dichiarare
     mai completato un task senza aver ottenuto `GATE_VERIFIED_OK`.

## 2. Sequenza Operativa a 4 Passi

### Passo 1: Ispezione e Contesto (max 2-3 chiamate)
- Esegui `list` per confermare i file disponibili nella radice dello workspace.
- Esegui `read` su non più di 2 documenti chiave per estrarre titoli, statistiche
  e struttura dei capitoli.

### Passo 2: Creazione dello Script di Build
- Usa `write` per creare `build_presentation.py`.
- Struttura raccomandata con ReportLab:
  ```python
  from reportlab.lib.pagesizes import letter, landscape
  from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
  from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
  from reportlab.lib import colors

  doc = SimpleDocTemplate("presentation.pdf", pagesize=landscape(letter),
                          leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
  styles = getSampleStyleSheet()
  # Definizione slide e contenuti...
  story = []
  story.append(Paragraph("HyperSpace AGI", styles['Title']))
  story.append(Spacer(1, 20))
  story.append(Paragraph("Presentazione di Sistema", styles['Heading2']))
  doc.build(story)
  print("BUILD_COMPLETE")
  ```

### Passo 3: Esecuzione in Sandbox
- Esegui `run` con comando `python build_presentation.py`.
- Controlla l'exit code. Se l'exit code è diverso da 0, analizza l'errore in stderr
  (es. modulo mancante, sintassi) ed effettua un solo edit correttivo.

### Passo 4: Validazione e Rilascio
- Esegui il comando di verifica gate sopra descritto.
- Confermato `GATE_VERIFIED_OK`, elenca nel verdetto finale:
  - Nome del file PDF prodotto.
  - Dimensione in byte.
  - Script riproducibile associato.
