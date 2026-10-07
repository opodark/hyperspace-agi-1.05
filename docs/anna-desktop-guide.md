# Anna Desktop Guide

## Obiettivo

Anna Desktop Guide è un companion locale che comprende l'interfaccia davanti
all'utente e offre indicazioni contestuali tramite un piccolo avatar. Deve
funzionare sopra applicazioni desktop e siti web senza dipendere da integrazioni
specifiche per ogni prodotto.

Non è un sistema di sorveglianza e, nella prima versione, non controlla il
computer: legge la struttura accessibile della finestra attiva, spiega ciò che
vede e suggerisce il prossimo passo. Ogni futura azione su mouse o tastiera dovrà
essere proposta e confermata separatamente.

## Architettura

```text
Finestra attiva
   │
   ├─ Accessibility API (macOS)
   ├─ UI Automation (Windows)
   └─ Browser extension / DOM
             │
       Screen Context normalizzato
             │
       HyperSpace Office Agent
             │
       Overlay + avatar di Anna
```

Quando una superficie non espone informazioni accessibili, screenshot e OCR/VLM
locale costituiscono un fallback esplicito, non il percorso predefinito.

## MVP

1. Companion desktop con icona/avatar sempre in primo piano ma spostabile.
2. Rilevamento di applicazione, titolo e finestra attiva.
3. Lettura, su richiesta, di testo selezionato e albero accessibile visibile.
4. Comandi: «cosa sto guardando?», «come faccio a…?» e «qual è il prossimo passo?».
5. Risposta breve nell'overlay, con possibilità di aprire una spiegazione estesa.
6. Nessun click, digitazione o invio automatico.

## Privacy e sicurezza

- Elaborazione local-first; nessun contenuto dello schermo nei log operativi.
- Indicatore visibile durante ogni lettura e comando immediato di pausa.
- Esclusione predefinita di password manager, campi password e finestre private.
- Allowlist/denylist configurabile di applicazioni, domini e titoli finestra.
- Contesto effimero per default; memoria della sessione solo opt-in.
- Screenshot disabilitati per default e mai conservati senza scelta esplicita.
- In modalità aziendale, configurazione e audit per tenant senza registrare il
  contenuto letto.

## Adapter previsti

- `macos`: AXUIElement/Accessibility API e ScreenCaptureKit come fallback.
- `windows`: UI Automation e Windows Graphics Capture come fallback.
- `browser`: estensione con DOM semantico, tab attiva e selezione dell'utente.

Il core riceve sempre lo stesso oggetto `ScreenContext`, indipendentemente dalla
piattaforma. In questo modo avatar, prompt, policy e dialogo restano condivisi.

## Primo criterio di riuscita

Con una finestra supportata aperta, l'utente richiama Anna e ottiene nome
dell'applicazione, sezione attiva, controlli principali e una spiegazione utile
senza che alcuna immagine o testo lasci la macchina.
