#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Generatore PDF ad alta leggibilità per i Report Tecnici di HyperSpace AGI.
Converte il documento Markdown di architettura CoT e Distillazione Neurale
in un PDF formattato professionalmente con ReportLab.
"""

from pathlib import Path
import sys
import re

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs" / "reports"
MD_FILE = DOCS_DIR / "HyperSpace_CoT_Distillation_Architecture.md"
PDF_FILE = DOCS_DIR / "HyperSpace_CoT_Distillation_Architecture.pdf"


class NumberedCanvas(canvas.Canvas):
    """Canvas personalizzato per aggiungere piè di pagina con numerazione 'Pagina X di Y' e intestazione."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Intestazione superiore (da pagina 2 in poi)
        if self._pageNumber > 1:
            self.drawString(54, 800, "HyperSpace AGI — Report Tecnico: Distillazione CoT & Fine-Tuning Modelli Locali")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 792, 540, 792)

        # Piè di pagina inferiore
        page_str = f"Pagina {self._pageNumber} di {page_count}"
        self.drawRightString(540, 36, page_str)
        self.drawString(54, 36, "Confidenziale / Uso Interno — HyperSpace Sovereign Mesh Ecosystem")
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 540, 48)

        self.restoreState()


def build_pdf():
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(PDF_FILE),
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Definizione stili tipografici curati
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0369a1"),
        spaceAfter=14
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=18
    )

    h1_style = ParagraphStyle(
        'DocH1',
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'DocH2',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=8
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        leftIndent=15,
        spaceAfter=4
    )

    code_title_style = ParagraphStyle(
        'CodeTitle',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    code_style = ParagraphStyle(
        'CodeContent',
        fontName='Courier',
        fontSize=7.8,
        leading=10.2,
        textColor=colors.HexColor("#0f172a")
    )

    think_style = ParagraphStyle(
        'ThinkContent',
        fontName='Courier',
        fontSize=7.8,
        leading=10.2,
        textColor=colors.HexColor("#1e1b4b")
    )

    story = []

    # 1. Copertina / Titolo
    story.append(Paragraph("HyperSpace AGI — Architettura di Distillazione Neurale CoT e Fine-Tuning dei Modelli Locali", title_style))
    story.append(Paragraph("Estensione Operativa delle Capacità di Chat Hook, Invocazione Skill e Strumenti Sovrani", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=10))

    meta_text = """
    <b>Autore:</b> Antigravity (HP OMEN 16 / Mesh Node) &bull; 
    <b>Destinatari:</b> Cips, Alberto, Team HyperSpace<br/>
    <b>Data:</b> 21 Ottobre 2026 &bull; <b>Ambiente:</b> HyperSpace v1.05 Mesh Cluster
    """
    story.append(Paragraph(meta_text, meta_style))
    story.append(Spacer(1, 10))

    # 2. Premessa
    story.append(Paragraph("1. Premessa e Visione Strategica", h1_style))
    p1 = """
    In questi mesi l'infrastruttura di HyperSpace si è arricchita di componenti sovrani di altissimo livello:
    il ponte neurale ComfyUI (SDXL Turbo, Pony, SD1.5, ControlNet), la memoria sovrana Hermes (SQLite WAL + FTS5),
    l'infrastruttura crittografica e di routing Mesh P2P (ECDSA inter-nodo), il Reel Editor automatico e il DAG orchestrator di Mission Control.
    <br/><br/>
    Tuttavia, è emerso un limite fondamentale: <b>i modelli linguistici compatti locali (SLM da 4B a 8B come Liquid AI LFM2.5 o Granite 3.3) sanno "tanto", ma nei chat hook operativi non sanno ancora "usare" concretamente questi strumenti</b>. Quando un utente richiede un'operazione via chat, il modello tende a rispondere con spiegazioni teoriche o ad allucinare invocazioni e parametri errati, mancando di un addestramento specifico sull'uso attivo delle nostre API.
    <br/><br/>
    Questo report definisce l'architettura della <b>Distillazione Neurale mediata da Tracce di Pensiero (Chain of Thought - CoT)</b> e il piano operativo per trasformare i nostri modelli in <b>agenti operativi capaci di attivare e orchestrare l'intero set di skill e tool di HyperSpace</b>.
    """
    story.append(Paragraph(p1, body_style))

    # 3. Cuore Tecnologico
    story.append(Paragraph("2. Il Cuore Tecnologico: La Traccia di Pensiero (&lt;think&gt;)", h1_style))
    p2 = """
    Nei modelli compatti locali (4B–8B Q4_K_M residenti su schede consumer come la RTX 3070 8GB), l'inferenza diretta ("zero-shot") fallisce sistematicamente su compiti complessi per tre ragioni principali:
    """
    story.append(Paragraph(p2, body_style))
    story.append(Paragraph("&bull; <b>Allucinazione di API e Parametri:</b> il modello inventa metodi non esistenti o omette campi obbligatori.", bullet_style))
    story.append(Paragraph("&bull; <b>Errori Sintattici e Refusi:</b> blocchi tronchi, mancata gestione di divisioni per zero o puntatori nulli.", bullet_style))
    story.append(Paragraph("&bull; <b>Mancanza di Decomposizione:</b> incapacità di valutare sequenze causali prima di agire.", bullet_style))

    p3 = """
    L'introduzione della <b>Traccia di Pensiero (&lt;think&gt;...&lt;/think&gt;)</b> sdoppia l'inferenza in due fasi distinte:
    <br/>
    1. <b>Fase di Ragionamento Privato (&lt;think&gt;):</b> uno spazio interiore in cui il modello analizza l'intento, mappa le dipendenze, controlla i vincoli di sistema (AGENTS.md) e pianifica il codice.
    <br/>
    2. <b>Fase di Esecuzione Pubblica:</b> l'emissione rigorosa dell'output finale (codice Python verificabile, JSON schema strict o tool call normalizzata).
    <br/><br/>
    L'<code>UniversalModelParser</code> separa deterministicamente la traccia di pensiero dal payload finale, consentendo alle interfacce operative di consumare solo il risultato pulito.
    """
    story.append(Paragraph(p3, body_style))

    # 4. Esempio Reale
    story.append(Paragraph("3. Esempio Concreto dal Dataset Reale (HP OMEN 16)", h1_style))
    p_ex = """
    Durante il turno notturno continuo, il worker autonomo <code>omen_dev_loop_247.py</code> ha distillato e validato 
    <b>oltre 90 campioni sintetici completi</b> in <code>data/synthetic_cot_dataset.jsonl</code>. Di seguito è riportata una tupla reale generata da Liquid AI LFM2.5:
    """
    story.append(Paragraph(p_ex, body_style))

    # Box Prompt
    story.append(Paragraph("A. Prompt di Input (Compresso via Caveman Engine)", code_title_style))
    prompt_txt = "Crea una funzione Python `route_task_by_vram(task_requirements, nodes_list)` che calcola lo score di idoneità in base alla VRAM libera e all'alimentazione AC/Batteria. Mostra prima il ragionamento CoT in <think>, poi restituisci il codice completo con type hinting."
    prompt_p = Paragraph(prompt_txt, ParagraphStyle('PromptInner', fontName='Helvetica-Oblique', fontSize=8.5, leading=12, textColor=colors.HexColor("#0369a1")))
    t_prompt = Table([[prompt_p]], colWidths=[486])
    t_prompt.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0f9ff")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#bae6fd")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_prompt)
    story.append(Spacer(1, 8))

    # Box CoT
    story.append(Paragraph("B. Traccia di Pensiero Reale Registrata (&lt;think&gt;)", code_title_style))
    cot_raw = """The user wants a Python function `route_task_by_vram(task_requirements, nodes_list)` 
that calculates a suitability score based on free VRAM and AC/Battery feeding.

1. Decomposizione dei requisiti:
   - task_requirements conterrà VRAM minima, eventuale soglia AC e batteria.
   - nodes_list è una lista di nodi mesh con attributi vram_available, ac_available, battery_available.
   - Punteggio finale normalizzato tra 0.0 e 1.0.

2. Risoluzione delle criticità ed edge cases:
   - Rischio ZeroDivisionError se req == 0: guardia `(avail / req) if req > 0 else 0.0`.
   - L'alimentazione AC è più stabile della batteria: pesi (VRAM 50%, AC 30%, Batteria 20%).
   - Se le risorse disponibili superano di molto il requisito, clamp: `max(0.0, min(1.0, score))`.

3. Pianificazione contratti e sintassi:
   - Importare Dict, List, Any da typing.
   - Docstring completa ed esecuzione autonoma."""

    cot_p = Preformatted(cot_raw, think_style)
    t_cot = Table([[cot_p]], colWidths=[486])
    t_cot.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f5f3ff")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#ddd6fe")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_cot)
    story.append(Spacer(1, 8))

    # Box Codice
    story.append(Paragraph("C. Output Finale Validato via AST Python (ast_valid: true)", code_title_style))
    code_raw = """from typing import Dict, List, Any

def route_task_by_vram(task_requirements: Dict[str, Any], nodes_list: List[Dict[str, Any]]) -> float:
    \"\"\"Calcola lo score di idoneità (0.0-1.0) per VRAM e alimentazione.\"\"\"
    required_vram = task_requirements.get("vram_needed", 0)
    required_ac = task_requirements.get("ac_needed", float('inf'))
    required_battery = task_requirements.get("battery_needed", float('inf'))

    vram_avail = [node.get("vram_available", 0) for node in nodes_list]
    ac_avail = [node.get("ac_available", 0.0) for node in nodes_list]
    battery_avail = [node.get("battery_available", 0.0) for node in nodes_list]

    # Prevenzione divisione per zero pianificata nel <think>
    vram_norm = [v / required_vram if required_vram > 0 else 0.0 for v in vram_avail]
    ac_norm = [a / required_ac if required_ac > 0 else 0.0 for a in ac_avail]
    battery_norm = [b / required_battery if required_battery > 0 else 0.0 for b in battery_avail]

    weights = {"vram": 0.5, "ac": 0.3, "battery": 0.2}
    score = (weights["vram"] * sum(vram_norm) +
             weights["ac"] * sum(ac_norm) +
             weights["battery"] * sum(battery_norm))

    return max(0.0, min(1.0, score))  # Clamp rigoroso definito nel reasoning"""

    code_p = Preformatted(code_raw, code_style)
    t_code = Table([[code_p]], colWidths=[486])
    t_code.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_code)

    # 5. Applicazione Architetturale
    story.append(Paragraph("4. Applicazione Architetturale nei Componenti di HyperSpace", h1_style))
    p_arch = """
    Questa metodologia è integrata in modo trasversale attraverso l'architettura di HyperSpace:
    """
    story.append(Paragraph(p_arch, body_style))
    story.append(Paragraph("1. <b>Distillazione & Fine-Tuning a Costo Zero:</b> il worker notturno genera centinaia di tuple convalidate da usare come dataset supervisionato per training QLoRA locale su PyTorch.", bullet_style))
    story.append(Paragraph("2. <b>Pianificazione DAG in Mission Control:</b> il planner decompone con <code>think=True</code> in passaggi discreti, mentre i worker eseguono senza latenza aggiuntiva con <code>/no_think</code>.", bullet_style))
    story.append(Paragraph("3. <b>Pipeline Pre/Post-Inference (Universal Parser):</b> il <code>CavemanEngine</code> comprime i prompt del 20-40% preservando contratti e tag, mentre il parser ripara JSON parziali da troncamento token.", bullet_style))
    story.append(Paragraph("4. <b>Self-Healing Loop:</b> se un test fallisce, il messaggio del compilatore viene re-iniettato nel prompt per l'auto-riparazione immediata guidata da CoT.", bullet_style))
    story.append(Paragraph("5. <b>Memoria Sovrana Hermes:</b> le lezioni apprese dai blocchi CoT vengono salvate nel database SQLite FTS5 per orientare le sessioni future.", bullet_style))

    # 6. Dal Sapere al Saper Fare
    story.append(Paragraph("5. La Nuova Frontiera: Dal Sapere al Saper Fare (Tool-Use nei Chat Hook)", h1_style))
    p_future = """
    La priorità strategica evidenziata è <b>insegnare ai modelli a usare attivamente tools e skill nei chat hook</b>. 
    Attualmente i modelli compatti tendono a produrre risposte discorsive invece di invocare le azioni reali.
    <br/><br/>
    <b>Il Nuovo Schema di Ragionamento CoT per Tool-Calling:</b>
    <br/>
    Nei chat hook (Telegram, Discord, WebUI Cockpit), il modello viene addestrato a compiere una sequenza deterministica a 4 stadi:
    """
    story.append(Paragraph(p_future, body_style))
    story.append(Paragraph("&bull; <b>Rilevamento Intento:</b> discernere se l'utente desidera una conversazione o un'azione operativa sul cluster.", bullet_style))
    story.append(Paragraph("&bull; <b>Selezione del Tool:</b> individuare il tool registrato idoneo (es. <code>hermes_memory_store</code>, <code>comfy_generate</code>, <code>reel_render</code>).", bullet_style))
    story.append(Paragraph("&bull; <b>Validazione Parametri & Sicurezza:</b> verificare tipi, percorsi e assenza di credenziali esposte (policy AGENTS.md).", bullet_style))
    story.append(Paragraph("&bull; <b>Emissione Strutturata:</b> emettere rigorosamente il payload <code>&lt;tool_call&gt;{...}&lt;/tool_call&gt;</code> senza testo superfluo.", bullet_style))

    story.append(Spacer(1, 6))

    # Box Esempio Tool Call
    story.append(Paragraph("Esempio di Traccia CoT & Chiamata Tool Strutturata per Chat Hook", code_title_style))
    tool_raw = """PROMPT: "Registra nella memoria che su Windows i file SQLite richiedono conn.close() prima del cleanup."

<think>
1. Intento: Salvataggio permanente di una lezione appresa sul repository.
2. Tool: Hermes Memory Bridge (hermes_memory_store).
3. Parametri: text esplicito con WinError 32, category "lesson_learned", tags ["windows", "sqlite", "resilience"].
4. Output: emetto solo il payload tool_call conforme allo schema.
</think>

<tool_call>
{
  "tool": "hermes_memory_store",
  "arguments": {
    "text": "Su host Windows, le connessioni SQLite devono essere chiuse esplicitamente prima della cancellazione della cartella temporanea per prevenire WinError 32.",
    "category": "lesson_learned",
    "tags": ["windows", "sqlite", "resilience"]
  }
}
</tool_call>"""

    tool_p = Preformatted(tool_raw, code_style)
    t_tool = Table([[tool_p]], colWidths=[486])
    t_tool.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94a3b8")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_tool)

    # 7. Piano Operativo
    story.append(Paragraph("6. Piano Operativo e Prossimi Passi Condivisi", h1_style))
    p_plan = """
    1. <b>Espansione DEV_TOPICS:</b> estendere il generatore <code>omen_dev_loop_247.py</code> introducendo i 4 domini di tool-use (ComfyUI, Hermes Memory, Reel Editor, Mesh Telemetry).<br/>
    2. <b>Validatore di Schema Tool Call:</b> aggiungere un quality gate che validi la conformità JSON dei parametri contro i manifest di HyperSpace prima di ammettere il campione nel dataset.<br/>
    3. <b>Fine-Tuning QLoRA:</b> al raggiungimento di 500 campioni convalidati, avviare il training notturno su GPU RTX 3070 ed esportare gli adapter per Ollama.<br/>
    4. <b>Attivazione Chat Hook:</b> agganciare il modello sintonizzato sui bot Telegram/Discord con esecuzione automatica e trasparente delle skill.
    """
    story.append(Paragraph(p_plan, body_style))

    # Costruzione del PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESSO] PDF generato: {PDF_FILE}")


if __name__ == "__main__":
    build_pdf()
