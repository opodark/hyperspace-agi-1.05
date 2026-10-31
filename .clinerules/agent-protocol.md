# Protocollo fra agenti (per Cline)

Questo repository è condiviso con altri agenti sulla stessa macchina. Prima di
modificare qualsiasi cosa:

1. Leggi **[AGENTS.md](../AGENTS.md)**: chi lavora qui, le regole e dove sta la
   verità.
2. Leggi **[AGENT-LOG.md](../AGENT-LOG.md)**: i messaggi fra agenti, in ordine
   cronologico.
3. Quando finisci il tuo intervento, **aggiungi un blocco in fondo a
   `AGENT-LOG.md`** nel formato `## <data> — <agente> → <destinatario>`, con
   cosa hai fatto e cosa chiedi. Non riscrivere i messaggi degli altri.
4. Per passaggi di consegne strutturati tra sessioni o agenti, è attiva la skill
   **`handoff`** (in `.agents/skills/handoff`), che compila un documento
   riassuntivo in `$TMPDIR` con lo stato del lavoro e le suggested skills.
   Altre skill vendorizzate con lo stesso schema: `teach`, `marketing-psychology`,
   `anatomy` — vedi "Altre skill vendorizzate" in AGENTS.md.

Due cose che è facile sbagliare:

- **La verità è questo repository**, non `/Users/opo/Downloads/tiktok_editor`:
  quella cartella non è un repository git ed è ferma al 2026-09-09. Da lì serve
  solo `.venv/`, il runtime Python dell'editor. Lo sviluppo attivo sta in
  `integrations/tiktok_editor/app/`.
- **Non committare e non pushare senza conferma esplicita dell'utente.**
