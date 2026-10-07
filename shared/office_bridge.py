# SPDX-License-Identifier: Apache-2.0
"""Bridge ONLYOFFICE — Fase C (endpoint `/office/*`). Logica pura, senza rete.

Il bridge traduce un evento del documento (ONLYOFFICE) in un task per il
modello e normalizza la risposta nel formato che il writer ONLYOFFICE
reinserisce. Qui vivono SOLO le decisioni deterministiche e testabili senza un
modello: la tassonomia degli eventi, la validazione dell'envelope, la
costruzione dei prompt e la normalizzazione dell'output. La chiamata al modello
e il gate di accesso restano nel control-plane (control-plane/main.py), come per
web_search: il modulo non importa Flask né parla di rete.

Envelope (docs/onlyoffice-bridge.md):

    richiesta: {
        "event": "document.summary_requested",
        "document": {"id": "...", "type": "text", "title": "..."},
        "selection": {"text": "...", "range": null},
        "context": {"user": "...", "workspace": null},
        "options": {}
    }
    risposta:  {"status": "ok|error", "agent": "...",
                "output": {"text": "...", "format": "plain|markdown|comment"},
                "error": null}
"""
from __future__ import annotations

# Tipi di documento accettati. La Fase C (MVP) copre il testo; foglio, slide e
# pdf restano eventi futuri (fuori perimetro, vedi docs/onlyoffice-bridge.md).
DOCUMENT_TYPES = ("text", "spreadsheet", "presentation", "pdf")

# Evento ONLYOFFICE -> agente HyperSpace. La chiave e' l'identita' stabile
# dell'evento: gli endpoint sono solo una delle sue superfici.
EVENTS = {
    "document.summary_requested":      "summarizer",
    "document.rewrite_requested":      "rewriter",
    "document.action_items_requested": "planner",
    "document.selection_analyzed":     "classifier",
}

PLAIN = "plain"
MARKDOWN = "markdown"

# Oltre questo limite la selezione non e' piu' un "frammento": e' il documento,
# e va riassunto a monte invece di spedirlo intero al modello.
MAX_DOCUMENT_CHARS = 20000
# Tetto della tassonomia di `classify`: una lista di etichette lunga cosi' non
# e' una classificazione, e' un prompt travestito da opzione.
MAX_OPTION_ITEMS = 32

_SUMMARY_LENGTHS = ("short", "medium", "long")
_REWRITE_STYLES = ("formal", "plain", "concise")


def is_supported(event) -> bool:
    return event in EVENTS


def agent_for(event) -> str | None:
    return EVENTS.get(event)


def validate_request(payload) -> tuple[dict | None, str | None]:
    """Valida e normalizza l'envelope. Ritorna `(envelope, errore)`.

    Non lancia: l'errore e' testo pronto per la risposta 400. Un envelope
    corretto ma con `options` incoerenti viene rifiutato con la ragione, non
    corretto in silenzio.
    """
    if not isinstance(payload, dict):
        return None, "envelope non valido: atteso un oggetto JSON"

    event = payload.get("event")
    if not isinstance(event, str) or not event.strip():
        return None, "campo 'event' mancante"
    event = event.strip()
    if event not in EVENTS:
        return None, f"evento non supportato: {event}"

    document = payload.get("document") or {}
    if not isinstance(document, dict):
        return None, "campo 'document' non valido: atteso un oggetto"
    doc_type = str(document.get("type") or "text").strip().lower()
    if doc_type not in DOCUMENT_TYPES:
        return None, f"tipo documento non valido: {doc_type}"

    selection = payload.get("selection")
    if not isinstance(selection, dict):
        return None, "campo 'selection' mancante"
    text = selection.get("text")
    if not isinstance(text, str) or not text.strip():
        return None, "campo 'selection.text' vuoto"
    text = text.strip()
    if len(text) > MAX_DOCUMENT_CHARS:
        return None, (f"selection troppo lunga: {len(text)} caratteri "
                      f"(max {MAX_DOCUMENT_CHARS})")

    context = payload.get("context") or {}
    if not isinstance(context, dict):
        return None, "campo 'context' non valido: atteso un oggetto"

    options = payload.get("options")
    if options is None:
        options = {}
    if not isinstance(options, dict):
        return None, "campo 'options' non valido: atteso un oggetto"
    normalized_options, error = _validate_options(event, options)
    if error:
        return None, error

    return {
        "event": event,
        "agent": EVENTS[event],
        "document": {
            "id": str(document.get("id") or "").strip(),
            "type": doc_type,
            "title": str(document.get("title") or "").strip(),
        },
        "selection": {
            "text": text,
            "range": selection.get("range"),
        },
        "context": {
            "user": str(context.get("user") or "").strip(),
            "workspace": context.get("workspace"),
        },
        "options": normalized_options,
    }, None


def build_messages(event: str, envelope: dict) -> list[dict]:
    """Costruisce i messaggi per il modello (system + user) per l'evento."""
    selection = envelope["selection"]["text"]

    if event == "document.summary_requested":
        lunghezze = {"short": "2-3 frasi", "medium": "un paragrafo",
                     "long": "3-5 paragrafi"}
        lunghezza = lunghezze.get(envelope["options"].get("length", "medium"),
                                  "un paragrafo")
        system = (
            "Sei il summarizer documentale di HyperSpace. Riassumi il testo "
            "fornito senza aggiungere informazioni che non contiene e senza "
            "introdurre opinioni. Non commentare il compito: produci soltanto il "
            "riassunto.")
        user = f"Riassumi in {lunghezza}.\n\n--- TESTO ---\n{selection}"
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    if event == "document.rewrite_requested":
        stili = {"formal": "formale e professionale", "plain": "semplice e chiaro",
                 "concise": "conciso, eliminando il superfluo"}
        stile = stili.get(envelope["options"].get("style", "plain"),
                          "semplice e chiaro")
        target = envelope["options"].get("target_language", "")
        target_nota = f" Traduci in {target}." if target else ""
        system = (
            "Sei il rewriter documentale di HyperSpace. Riscrivi il testo "
            "preservandone integralmente il significato, senza aggiungere fatti "
            "nuovi. Produci soltanto il testo riscritto, senza premesse né "
            "spiegazioni.")
        user = (f"Riscrivi in stile {stile}.{target_nota}\n\n"
                f"--- TESTO ---\n{selection}")
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    if event == "document.action_items_requested":
        assignees = envelope["options"].get("assignees_hint", False)
        assignees_nota = (" Se il testo nomina esplicitamente un responsabile, "
                          "indicalo dopo l'azione; non inventarne." if assignees else "")
        system = (
            "Sei il planner documentale di HyperSpace. Estrai dal testo i "
            "compiti/azioni concrete. Rispondi SOLO con una checklist in "
            "markdown, una voce per riga nel formato `- [ ] azione`. Non "
            "inventare azioni non presenti nel testo e non aggiungere commenti.")
        user = f"Estrai gli action item.{assignees_nota}\n\n--- TESTO ---\n{selection}"
        return [{"role": "system", "content": system},
                {"role": "user", "content": user}]

    if event == "document.selection_analyzed":
        etichette = ", ".join(envelope["options"]["taxonomy"])
        system = (
            "Sei il classifier documentale di HyperSpace. Assegna al testo una o "
            "più etichette scelte SOLO da questa lista: " + etichette + ". "
            "Rispondi SOLO con le etichette, una per riga, senza spiegazioni e "
            "senza inventare etichette nuove.")
        return [{"role": "system", "content": system},
                {"role": "user", "content": f"--- TESTO ---\n{selection}"}]

    raise ValueError(f"evento non supportato: {event}")


def normalize_output(event: str, text, options: dict) -> dict:
    """Normalizza la risposta del modello nell'`output` dell'envelope.

    Ritorna `{"text": str, "format": "plain|markdown"}`. Nessun fallback
    silenzioso: se la risposta e' vuota resta vuota (il chiamante decide se e'
    un errore), e per `classify` si tengono solo le etichette della taxonomy.
    """
    text = str(text or "").strip()
    if event == "document.action_items_requested":
        return {"text": _as_checklist(text), "format": MARKDOWN}
    if event == "document.selection_analyzed":
        labels = _keep_taxonomy_labels(text, options.get("taxonomy") or [])
        return {"text": "\n".join(labels) if labels else text, "format": PLAIN}
    return {"text": text, "format": PLAIN}


def _as_checklist(text: str) -> str:
    """Rende il testo una checklist markdown `- [ ] ...`, una voce per riga."""
    righe = []
    for grezza in text.splitlines():
        riga = grezza.strip()
        if not riga:
            continue
        if riga[0] in "-*•":
            corpo = riga[1:].strip()
        else:
            corpo = _strip_enumerazione(riga)
        if not corpo:
            continue
        basso = corpo.lower()
        if basso.startswith("[ ]") or basso.startswith("[x]"):
            righe.append(f"- {corpo}")
        else:
            righe.append(f"- [ ] {corpo}")
    return "\n".join(righe) if righe else text


def _strip_enumerazione(riga: str) -> str:
    """Toglie un'eventuale numerazione iniziale (`1.`, `1)`)."""
    i = 0
    while i < len(riga) and riga[i].isdigit():
        i += 1
    if i > 0 and i < len(riga) and riga[i] in ".)":
        return riga[i + 1:].strip()
    return riga


def _keep_taxonomy_labels(text: str, taxonomy: list) -> list:
    """Le etichette della risposta che appartengono alla taxonomy, nell'ordine
    in cui compaiono e senza duplicati. Ritorna `[]` se nessuna combacia: cosi'
    il chiamante sa che il modello ha risposto fuori lista."""
    per_chiave = {str(label).strip().lower(): str(label).strip()
                  for label in taxonomy if str(label).strip()}
    trovate = []
    for pezzo in text.replace(",", "\n").splitlines():
        voce = pezzo.strip().lstrip("-*•#0123456789.) ").strip()
        etichetta = per_chiave.get(voce.lower())
        if etichetta and etichetta not in trovate:
            trovate.append(etichetta)
    return trovate


def describe() -> dict:
    """Parte statica della diagnostica per `GET /office/status` (nessun segreto)."""
    return {
        "supported_events": dict(EVENTS),
        "document_types": list(DOCUMENT_TYPES),
        "max_document_chars": MAX_DOCUMENT_CHARS,
        "max_taxonomy_labels": MAX_OPTION_ITEMS,
    }

def _validate_options(event: str, options: dict) -> tuple[dict, str | None]:
    """Normalizza le opzioni evento-specifiche, con i default del design doc."""
    if event == "document.summary_requested":
        length = str(options.get("length") or "medium").strip().lower()
        if length not in _SUMMARY_LENGTHS:
            return {}, f"opzione 'length' non valida: {length}"
        return {"length": length}, None

    if event == "document.rewrite_requested":
        style = str(options.get("style") or "plain").strip().lower()
        if style not in _REWRITE_STYLES:
            return {}, f"opzione 'style' non valida: {style}"
        target = options.get("target_language")
        return {"style": style,
                "target_language": str(target).strip() if target else ""}, None

    if event == "document.action_items_requested":
        raw = options.get("assignees_hint", False)
        if isinstance(raw, str):
            raw = raw.strip().lower() in ("1", "true", "yes", "on")
        return {"assignees_hint": bool(raw)}, None

    if event == "document.selection_analyzed":
        taxonomy = options.get("taxonomy")
        if not isinstance(taxonomy, list) or not taxonomy:
            return {}, "opzione 'taxonomy' mancante: serve una lista di etichette"
        labels = []
        for entry in taxonomy:
            label = str(entry).strip()
            if label and label.lower() not in {esistente.lower() for esistente in labels}:
                labels.append(label)
        if not labels:
            return {}, "opzione 'taxonomy' vuota: nessuna etichetta utilizzabile"
        if len(labels) > MAX_OPTION_ITEMS:
            return {}, (f"opzione 'taxonomy' troppo lunga: {len(labels)} etichette "
                        f"(max {MAX_OPTION_ITEMS})")
        return {"taxonomy": labels}, None

    # Inarrivabile finche' EVENTS e' allineato con i rami sopra: se un evento
    # viene aggiunto senza le sue opzioni, e' meglio un errore esplicito che un
    # task senza vincoli.
    return {}, f"evento senza opzioni definite: {event}"

