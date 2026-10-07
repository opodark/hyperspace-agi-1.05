# SPDX-License-Identifier: Apache-2.0
"""OpenAPI tools for the two explicitly shared Open WebUI directories."""

import filecmp
import hashlib
import hmac
import os
import shutil
import time
from pathlib import Path

from flask import Blueprint, jsonify, request, Response
from shared.anna_vision_selection import AnnaVisionSelection, AnnaSecondPass
from shared.image_jobs import POSE_PRESET
from shared.webui_tool_registry import execute as execute_custom_tool, load_tools


tools_api = Blueprint("webui_tools", __name__, url_prefix="/webui-tools")
SHARE = Path(os.getenv("WEBUI_SHARE_DIR", "/app/hyperspace_share"))
IMAGES = Path(os.getenv("WEBUI_ANNA_IMAGES_DIR", "/app/anna-images"))
TOKEN = os.getenv("WEBUI_TOOLS_TOKEN", "")
REVIEW = None
SECOND_PASS = None
ACTIVITY = None
BATCH = None
MAX_TEXT = 200_000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DESTINATIONS = {"selezionate": "Anna_selezionate", "da_rivedere": "Anna_da_rivedere"}


def _error(message, status=400):
    return jsonify({"error": message}), status


@tools_api.before_request
def _authorize():
    if request.endpoint in ("webui_tools.openapi", "webui_tools.activity_view",
                            "webui_tools.activity_live"):
        return None
    bearer = request.headers.get("Authorization", "")
    provided = bearer[7:] if bearer.startswith("Bearer ") else ""
    if len(TOKEN) < 32 or not hmac.compare_digest(provided, TOKEN):
        return _error("Tool token non valido o assente", 401)
    return None


def _within(root: Path, relative: str, *, must_exist=False) -> Path:
    if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
        raise ValueError("Usa un percorso relativo non vuoto")
    base = root.resolve(strict=True)
    target = (base / relative).resolve(strict=must_exist)
    if not target.is_relative_to(base):
        raise ValueError("Percorso esterno alla cartella condivisa")
    return target


def _payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Invia un oggetto JSON")
    return data


def configure_review(ask_vision):
    global REVIEW
    REVIEW = AnnaVisionSelection(
        IMAGES,
        os.getenv("ANNA_REVIEW_STATE_FILE", "/app/data/anna-selection.json"),
        os.getenv("ANNA_REVIEW_MODEL", "qwen3-vl:4b-instruct"),
        ask_vision,
    )


def configure_second_pass(ask_vision):
    global SECOND_PASS
    first_state = os.getenv("ANNA_REVIEW_STATE_FILE", "/app/data/anna-selection.json")
    SECOND_PASS = AnnaSecondPass(
        IMAGES, first_state,
        os.getenv("ANNA_SECOND_PASS_STATE_FILE", "/app/data/anna-second-pass.json"),
        os.getenv("ANNA_REVIEW_MODEL", "qwen3-vl:4b-instruct"), ask_vision,
    )


def configure_activity(get_activity):
    global ACTIVITY
    ACTIVITY = get_activity


def configure_batch(run_batch):
    global BATCH
    BATCH = run_batch


def _monitor_signature(expires):
    return hmac.new(TOKEN.encode(), f"activity:{expires}".encode(), hashlib.sha256).hexdigest()


def _monitor_authorized():
    expires = request.args.get("expires", "")
    signature = request.args.get("signature", "")
    return (len(TOKEN) >= 32 and expires.isdecimal() and int(expires) >= time.time()
            and int(expires) <= time.time() + 12 * 3600
            and hmac.compare_digest(signature, _monitor_signature(expires)))


@tools_api.get("/openapi.json")
def openapi():
    text_path = {"type": "string", "description": "Percorso relativo in hyperspace_share"}
    image_name = {"type": "string", "description": "Nome esatto di un'immagine nella cartella HyperSpace"}
    def operation(operation_id, summary, description, properties, required=None):
        return {"operationId": operation_id, "summary": summary, "description": description,
                "security": [{"BearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {
                    "type": "object", "properties": properties,
                    "required": required or [], "additionalProperties": False}}}},
                "responses": {"200": {"description": "Risultato JSON; controllare i campi restituiti"}}}
    paths = {
            "/webui-tools/share/list": {"post": operation("list_shared_files", "Elenca file condivisi",
                "Elenca file e sottocartelle in hyperspace_share.", {"path": text_path}, ["path"])},
            "/webui-tools/share/read": {"post": operation("read_shared_text", "Leggi file di testo condiviso",
                "Legge fino a 200000 byte UTF-8.", {"path": text_path}, ["path"])},
            "/webui-tools/share/write": {"post": operation("create_shared_text", "Crea file di testo condiviso",
                "Crea un nuovo file UTF-8, senza sovrascrivere file esistenti.",
                {"path": text_path, "content": {"type": "string"}}, ["path", "content"])},
            "/webui-tools/anna/list": {"post": operation("list_anna_images", "Elenca immagini di Anna",
                "Restituisce i nomi dei file; questo non equivale a esaminarne il contenuto visivo.", {})},
            "/webui-tools/anna/copy": {"post": operation("copy_anna_images", "Copia immagini di Anna selezionate",
                "Copia immagini già esaminate in Anna_selezionate o Anna_da_rivedere; gli originali restano. Non dichiarare valutazioni anatomiche senza aver visto le immagini.",
                {"filenames": {"type": "array", "items": image_name, "minItems": 1, "maxItems": 100},
                 "destination": {"type": "string", "enum": list(DESTINATIONS)}},
                ["filenames", "destination"])},
            "/webui-tools/anna/select": {"post": operation("start_anna_visual_selection", "Seleziona visivamente le immagini di Anna",
                "Avvia una revisione visiva di tutte le immagini con il modello locale. "
                "Copia quelle senza difetti visibili in Anna_selezionate e le altre in Anna_da_rivedere. "
                "La procedura è asincrona: usa anna/progress per sapere quando è davvero finita.", {})},
            "/webui-tools/anna/progress": {"post": operation("anna_visual_selection_progress", "Stato selezione visiva Anna",
                "Mostra quante immagini sono state realmente esaminate, copiate e rimaste in errore.", {})},
            "/webui-tools/anna/second-pass": {"post": operation("start_anna_second_pass", "Secondo passaggio Anna",
                "Ricontrolla rapidamente i file da rivedere o rimasti in errore al primo passaggio. "
                "Avvia un job asincrono; le promosse sono copiate in una cartella separata.", {})},
            "/webui-tools/anna/second-pass/progress": {"post": operation("anna_second_pass_progress", "Stato secondo passaggio Anna",
                "Mostra il progresso e la cartella delle promosse del secondo passaggio.", {})},
            "/webui-tools/anna/batch": {"post": operation("generate_anna_batch", "Genera Anna in batch",
                "Accoda da 1 a 50 scene Anna: testo semplice oppure oggetto con scene, "
                "pose_image (nome relativo in ComfyUI/input), pose_preset e pose_strength. "
                "Restituisce gli ID accettati, il controllo di posa usato e i rifiuti; "
                "controlla poi l'attività. Non dichiarare immagini completate finché non lo sono.",
                {"scene": {"type": "array", "items": {"oneOf": [
                    {"type": "string"},
                    {"type": "object", "properties": {
                        "scene": {"type": "string"},
                        "pose_image": {"type": "string"},
                        "pose_preset": {"type": "string", "enum": list(POSE_PRESET)},
                        "pose_strength": {"type": "number", "minimum": 0, "maximum": 2}},
                     "required": ["scene"], "additionalProperties": False}]},
                    "minItems": 1, "maxItems": 50}},
                ["scene"])},
            "/webui-tools/activity": {"post": operation("show_hyperspace_activity", "Console attività HyperSpace",
                "Mostra un monitor di sola lettura, aggiornato automaticamente, per la selezione Anna "
                "e la coda immagini. Nessun comando shell.", {})},
    }
    for custom in load_tools().values():
        paths[f"/webui-tools/custom/{custom.name}"] = {"post": operation(
            custom.name, custom.name.replace("_", " ").title(), custom.description,
            custom.properties, custom.required)}
    return jsonify({
        "openapi": "3.0.3",
        "info": {"title": "HyperSpace file tools", "version": "1.0.0",
                 "description": "Operazioni sulle sole cartelle condivise HyperSpace e Anna."},
        "servers": [{"url": "http://control-plane:8085"}],
        "components": {"securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer"}}},
        "paths": paths,
    })


@tools_api.post("/custom/<name>")
def custom_tool(name):
    try:
        return jsonify({"result": execute_custom_tool(name, _payload())})
    except KeyError:
        return _error("Tool non trovato", 404)
    except (TypeError, ValueError) as exc:
        return _error(str(exc))


@tools_api.post("/share/list")
def share_list():
    try:
        path = _within(SHARE, _payload().get("path", "."), must_exist=True)
        if not path.is_dir():
            return _error("Cartella non trovata", 404)
        items = [{"name": p.name, "type": "directory" if p.is_dir() else "file"}
                 for p in sorted(path.iterdir(), key=lambda p: p.name.lower())]
        return jsonify({"path": str(path.relative_to(SHARE.resolve())), "items": items, "count": len(items)})
    except (OSError, ValueError) as exc:
        return _error(str(exc))


@tools_api.post("/share/read")
def share_read():
    try:
        path = _within(SHARE, _payload().get("path"), must_exist=True)
        if not path.is_file():
            return _error("File non trovato", 404)
        if path.stat().st_size > MAX_TEXT:
            return _error(f"File oltre il limite di {MAX_TEXT} byte", 413)
        return jsonify({"path": str(path.relative_to(SHARE.resolve())),
                        "content": path.read_text(encoding="utf-8")})
    except (OSError, UnicodeError, ValueError) as exc:
        return _error(str(exc))


@tools_api.post("/share/write")
def share_write():
    try:
        data = _payload()
        content = data.get("content")
        if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_TEXT:
            return _error(f"Il contenuto deve essere testo UTF-8 entro {MAX_TEXT} byte")
        path = _within(SHARE, data.get("path"))
        if path == SHARE.resolve():
            return _error("Indica un nome file")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
        return jsonify({"created": str(path.relative_to(SHARE.resolve())), "bytes": path.stat().st_size})
    except FileExistsError:
        return _error("File già esistente; nessuna sovrascrittura", 409)
    except (OSError, ValueError) as exc:
        return _error(str(exc))


@tools_api.post("/anna/list")
def anna_list():
    try:
        names = sorted(p.name for p in IMAGES.iterdir()
                       if p.is_file() and not p.is_symlink() and p.suffix.lower() in IMAGE_EXTENSIONS)
        return jsonify({"count": len(names), "filenames": names})
    except OSError as exc:
        return _error(str(exc), 503)


@tools_api.post("/anna/select")
def anna_select():
    if REVIEW is None:
        return _error("Selezione visiva non configurata", 503)
    try:
        _payload()
        return jsonify(REVIEW.start())
    except (OSError, ValueError) as exc:
        return _error(str(exc), 503)


@tools_api.post("/anna/progress")
def anna_progress():
    if REVIEW is None:
        return _error("Selezione visiva non configurata", 503)
    return jsonify(REVIEW.status())


@tools_api.post("/anna/second-pass")
def anna_second_pass():
    if SECOND_PASS is None:
        return _error("Secondo passaggio non configurato", 503)
    try:
        _payload()
        return jsonify(SECOND_PASS.start())
    except (OSError, ValueError) as exc:
        return _error(str(exc), 503)


@tools_api.post("/anna/second-pass/progress")
def anna_second_pass_progress():
    if SECOND_PASS is None:
        return _error("Secondo passaggio non configurato", 503)
    return jsonify(SECOND_PASS.status())


@tools_api.post("/anna/batch")
def anna_batch():
    if BATCH is None:
        return _error("Anna Batch non configurato", 503)
    try:
        scene = _payload().get("scene")
        result, status = BATCH(scene)
        return jsonify(result), status
    except (OSError, ValueError) as exc:
        return _error(str(exc))


@tools_api.post("/activity")
def activity():
    if ACTIVITY is None:
        return _error("Monitor non configurato", 503)
    expires = str(int(time.time()) + 12 * 3600)
    signature = _monitor_signature(expires)
    path = f"/webui-tools/activity/view?expires={expires}&signature={signature}"
    # The outer iframe is sandboxed by Open WebUI. The inner page is served by
    # the control plane and polls its own origin, so no bearer token reaches JS.
    html = """<!doctype html><html lang=it><meta charset=utf-8><body style='margin:0;background:#111827;color:#e5e7eb;font:14px system-ui'>
<iframe id=monitor title='Attività HyperSpace' style='width:100%;height:420px;border:0'></iframe>
<script>const path=PATH;const configured=PUBLIC_URL;
let base=configured;
if(!base){try{const u=new URL(document.referrer);base=u.protocol+'//'+u.hostname+':8085'}catch{base='http://localhost:8085'}}
document.getElementById('monitor').src=base+path;
parent.postMessage({type:'iframe:height',height:430},'*');</script></body></html>"""
    import json
    html = html.replace("PATH", json.dumps(path)).replace(
        "PUBLIC_URL", json.dumps(os.getenv("WEBUI_MONITOR_PUBLIC_URL", "").rstrip("/")))
    return Response(html, content_type="text/html; charset=utf-8",
                    headers={"Content-Disposition": "inline", "Cache-Control": "no-store"})


@tools_api.get("/activity/view")
def activity_view():
    if not _monitor_authorized():
        return _error("Monitor scaduto o non autorizzato", 401)
    html = """<!doctype html><html lang=it><meta charset=utf-8>
<meta name=viewport content='width=device-width,initial-scale=1'>
<style>body{margin:0;padding:16px;background:#111827;color:#e5e7eb;font:14px system-ui}
h2{font-size:16px;margin:0 0 12px}section{background:#1f2937;border:1px solid #374151;border-radius:9px;padding:12px;margin:8px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace,SFMono-Regular,monospace;margin:7px 0 0}
.muted{color:#9ca3af}.bad{color:#fca5a5}</style>
<h2>Attività HyperSpace <span id=clock class=muted></span></h2>
<section><b>Selezione Anna</b><pre id=anna>Caricamento…</pre></section>
<section><b>Secondo passaggio</b><pre id=second>Caricamento…</pre></section>
<section><b>Coda immagini / Anna Batch</b><pre id=queue>Caricamento…</pre></section>
<script>
const url='/webui-tools/activity/live'+location.search;
async function tick(){try{const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);
const d=await r.json(),a=d.anna||{},s=d.anna_second_pass||{},q=d.images||{};
document.getElementById('anna').textContent=`${a.status||'non avviato'} · ${a.processed||0}/${a.total||0} esaminate · ${a.selected||0} selezionate · ${a.to_review||0} da rivedere · ${a.errors||0} errori`+(a.last_file?`\\nUltimo file: ${a.last_file}`:'');
document.getElementById('second').textContent=`${s.status||'non avviato'} · ${s.processed||0}/${s.total||0} esaminate · ${s.selected||0} promosse · ${s.to_review||0} ancora da rivedere · ${s.errors||0} errori`+(s.last_file?`\\nUltimo file: ${s.last_file}`:'');
document.getElementById('queue').textContent=`${q.in_coda||0} in coda · ${q.in_esecuzione||0} in esecuzione · massimo ${q.max_jobs||0}`+(q.ultimi?.length?'\\nUltimi job:\\n'+q.ultimi.map(x=>`${x.id}: ${x.stato}${x.file?' — '+x.file:''}${x.error?' — '+x.error:''}`).join('\\n'):'');
document.getElementById('clock').textContent='· aggiornato '+new Date().toLocaleTimeString('it-IT');
}catch(e){document.getElementById('clock').textContent='· connessione non disponibile: '+e.message}}
tick();setInterval(tick,3000);
</script></html>"""
    return Response(html, content_type="text/html; charset=utf-8",
                    headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@tools_api.get("/activity/live")
def activity_live():
    if not _monitor_authorized():
        return _error("Monitor scaduto o non autorizzato", 401)
    if ACTIVITY is None:
        return _error("Monitor non configurato", 503)
    response = jsonify(ACTIVITY())
    response.headers["Cache-Control"] = "no-store"
    return response


@tools_api.post("/anna/copy")
def anna_copy():
    try:
        data = _payload()
        names = data.get("filenames")
        destination = data.get("destination")
        if destination not in DESTINATIONS:
            return _error("Destinazione non valida")
        if not isinstance(names, list) or not 1 <= len(names) <= 100:
            return _error("Indica da 1 a 100 nomi file")
        sources = []
        for name in names:
            if not isinstance(name, str) or Path(name).name != name or name in (".", ".."):
                return _error("Nome file non valido")
            source = _within(IMAGES, name, must_exist=True)
            if not source.is_file() or source.is_symlink() or source.suffix.lower() not in IMAGE_EXTENSIONS:
                return _error(f"Immagine non valida: {name}")
            sources.append(source)
        target_dir = IMAGES / DESTINATIONS[destination]
        target_dir.mkdir(exist_ok=True)
        # Validate all conflicts before writing the first file.
        for source in sources:
            target = target_dir / source.name
            if target.exists() and (target.is_symlink() or not target.is_file()
                                    or not filecmp.cmp(source, target, shallow=False)):
                return _error(f"Conflitto per {source.name}; nessun file copiato", 409)
        for source in sources:
            target = target_dir / source.name
            if not target.exists():
                shutil.copy2(source, target)
        verified = [source.name for source in sources if (target_dir / source.name).is_file()]
        return jsonify({"destination": target_dir.name, "copied": verified,
                        "count": len(verified), "verified": len(verified) == len(sources)})
    except (OSError, ValueError) as exc:
        return _error(str(exc))
