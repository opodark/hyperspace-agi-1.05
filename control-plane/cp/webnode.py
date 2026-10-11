# SPDX-License-Identifier: Apache-2.0
# control-plane/cp/webnode.py
# I WEB NODES: IL LAVORO CHE IL CONTROL-PLANE NON PUO' FARE DA SE'.
#
# Un web node e' una scheda del browser. Si registra, poi TIRA il lavoro con un
# long-poll e pubblica il risultato: il CP non lo chiama mai, e non puo' farlo,
# perche' il browser non ha un endpoint in ingresso. E' la stessa inversione di
# direzione del runner sandbox (shared/code_sandbox.py), e per la stessa ragione
# mette a disagio chi legge: qui il CP e' il cliente.
#
# Perche' stanno separati dal mesh (`cp/mesh.py`), che sembra fare la stessa cosa:
# il mesh sceglie fra server che lui puo' chiamare per nome e parla un protocollo
# che puo' riprovare. Il web node e' l'opposto — e' il CP ad aspettare, e il
# lavoro che torna e' codice eseguito su una macchina che non controlla. Le due
# cose hanno bisogno di garanzie diverse, e metterle nello stesso modulo avrebbe
# fatto sembrare il secondo un caso particolare del primo.
#
# I tre limiti che rendono questo dominio diverso, e che qui sono applicati:
#
# - Solo i task in WEB_SAFE_TASK_TYPES possono essere accodati. Nessuna inferenza
#   pesante puo' finire su una scheda del browser.
# - Il registro NON e' persistito, e non perche' sia scomodo: un web node e' una
#   scheda, e una scheda che si ricorda di una richiesta fatta due giorni fa e' un
#   bug che aspetta. Il riavvio deve dimenticare tutto (vedi shared/web_node.py).
# - Ogni route richiede il token di amministrazione di rete. Sono le stesse rotte
#   che possono mettere in coda codice arbitrario.
#
# Lo stato che si vede da qui (`_nodes_by_id`, `_known_endpoints`) e' del mesh: un
# web node registrato finisce nel registro dei nodi come qualsiasi altro, e deve
# comparire dove l'operatore guarda. Sono importati per nome e non iniettati, e
# va bene perche' il mesh li muta in posto e non li riassegna mai — se un giorno
# li riassegna, questo import diventa una copia morta e va rifatto dal modulo.

import html
import os
import re
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
import requests

import cp.mesh as mesh
import shared.db as db
from cp.config import (WEB_NODE_ENABLED, WEB_NODE_HEARTBEAT_S, WEB_NODE_MAX_NODES,
                       WEB_NODE_MAX_PAYLOAD, WEB_NODE_MAX_POLL_S, WEB_NODE_MAX_QUEUE,
                       WEB_NODE_TASK_TTL_S)
from cp.http import NETWORK_ADMIN_TOKEN, _network_admin_error
from cp.log import push_log
from cp.mesh import _known_endpoints, _nodes_by_id
from shared.network_security import token_authorized
from shared.web_node import (WebNodeError, WebNodeRegistry, WebNodeUnknown,
                             WebTaskRejected)
from shared.web_topology import public_topology

_bp = Blueprint("webnode", __name__)

# Registry in memoria dei web node e dei task web-safe. Volutamente NON
# persistito: un web node e' una scheda del browser e non deve mai essere
# fonte di verita' (vedi shared/web_node.py).
web_registry = WebNodeRegistry(
    max_nodes=WEB_NODE_MAX_NODES,
    max_queue=WEB_NODE_MAX_QUEUE,
    max_payload_bytes=WEB_NODE_MAX_PAYLOAD,
    task_ttl_s=WEB_NODE_TASK_TTL_S,
    max_poll_s=WEB_NODE_MAX_POLL_S,
)


def monta(app):
    """Registra le rotte /web/*. Lo stato e' gia' pronto: il registro e' tutto
    memoria e non dipende dal boot, quindi non c'e' niente da iniettare."""
    app.register_blueprint(_bp)
    return app# ── WEB NODES — worker nel browser ────────────────────────────────────────────
# Un web node non ha un endpoint in ingresso: il CP non puo' chiamarlo. Si
# registra, poi TIRA il lavoro con un long-poll e pubblica il risultato —
# stessa inversione di direzione del runner sandbox (shared/code_sandbox.py).
# Solo i task in WEB_SAFE_TASK_TYPES possono essere accodati: nessuna inferenza
# pesante puo' finire su una scheda del browser. Richiede che le route /web/*
# girino su un server multi-thread: il long-poll occupa un thread fino a
# WEB_NODE_MAX_POLL_S secondi (vedi docs/web-node.md).
def _web_error(error):
    """Mappa le eccezioni del registry del web node sullo status HTTP corretto."""
    if isinstance(error, WebNodeUnknown):
        status = 404
    elif isinstance(error, WebTaskRejected):
        status = 409
    else:
        status = 400
    return jsonify({"ok": False, "error": str(error)}), status



def _web_node_id(data) -> str:
    return str((data or {}).get("node_id", "") or "").strip()



def _web_capable_node(capability: str):
    """Primo web node (per anzianita' di registrazione) che ha la capability."""
    matches = [n for n in web_registry.nodes() if capability in n["capabilities"]]
    matches.sort(key=lambda n: n.get("registered_at", 0))
    return matches[0]["node_id"] if matches else None



@_bp.route('/web/register', methods=['POST'])
def web_register():
    if not WEB_NODE_ENABLED:
        return jsonify({"ok": False, "error": "web node disattivati su questo control-plane"}), 503
    data = request.get_json(force=True, silent=True) or {}
    node_id = _web_node_id(data)
    if not node_id:
        return jsonify({"ok": False, "error": "missing node_id"}), 400
    try:
        record = web_registry.register(
            node_id,
            capabilities=data.get("capabilities") or [],
            label=data.get("label", ""),
            browser=data.get("browser", ""),
            limits=data.get("limits") or {},
        )
    except WebNodeError as error:
        return _web_error(error)
    # Il web node compare anche nella lista mesh (is_web_node=True) cosi' la
    # dashboard lo mostra, ma _best_endpoint lo tiene fuori dal routing: un
    # browser non e' chiamabile.
    endpoint = f"browser://{node_id}"
    info = {**(_nodes_by_id.get(node_id) or {}), **data, "node_id": node_id,
            "endpoint": endpoint, "status": "active", "is_web_node": True,
            "type": "web-node",
            "last_seen": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    _nodes_by_id[node_id] = info
    _known_endpoints.add(endpoint)
    db.upsert_node(info)
    push_log('mesh_event', f'Web node registered: {node_id[:12]}',
             f"caps={','.join(record['capabilities']) or '-'} browser={record['browser'][:40]}",
             source=node_id[:12], status='success')
    return jsonify({"ok": True, "node": record,
                    "heartbeat_interval_s": WEB_NODE_HEARTBEAT_S,
                    "max_poll_s": WEB_NODE_MAX_POLL_S})



@_bp.route('/web/poll', methods=['POST'])
def web_poll():
    if not WEB_NODE_ENABLED:
        return jsonify({"ok": False, "error": "web node disattivati su questo control-plane"}), 503
    data = request.get_json(force=True, silent=True) or {}
    try:
        timeout_s = int(data.get("timeout_s", WEB_NODE_MAX_POLL_S))
    except (TypeError, ValueError):
        timeout_s = WEB_NODE_MAX_POLL_S
    try:
        task = web_registry.poll(_web_node_id(data), timeout_s=timeout_s)
    except WebNodeError as error:
        return _web_error(error)
    if task is None:
        return jsonify({"ok": True, "task": None,
                        "next_poll_s": max(1, WEB_NODE_HEARTBEAT_S // 2)})
    push_log('web_task', f"Web task {task['task_id']} -> {task['node_id'][:12]}",
             f"type={task['type']}", source='control-plane',
             target=task['node_id'][:12], status='pending')
    return jsonify({"ok": True, "task": task})



@_bp.route('/web/result', methods=['POST'])
def web_result():
    if not WEB_NODE_ENABLED:
        return jsonify({"ok": False, "error": "web node disattivati su questo control-plane"}), 503
    data = request.get_json(force=True, silent=True) or {}
    node_id = _web_node_id(data)
    task_id = str(data.get("task_id", "") or "").strip()
    if not task_id:
        return jsonify({"ok": False, "error": "missing task_id"}), 400
    try:
        duration_ms = int(data["duration_ms"]) if data.get("duration_ms") is not None else None
    except (TypeError, ValueError):
        duration_ms = None
    try:
        entry = web_registry.complete(node_id, task_id, ok=bool(data.get("ok")),
                                      result=data.get("result"),
                                      error=data.get("error", ""),
                                      duration_ms=duration_ms)
    except WebNodeError as error:
        return _web_error(error)
    push_log('web_task', f"Web task {task_id} {'done' if entry['ok'] else 'failed'}",
             f"node={node_id[:12]} matched={entry['matched']} err={entry['error'][:80]}",
             source=node_id[:12], target='control-plane',
             status='success' if entry['ok'] else 'warn')
    return jsonify({"ok": True, "result": entry})



@_bp.route('/web/tasks', methods=['POST'])
def web_enqueue():
    """Accoda un task web-safe. Riservato all'operatore (token di rete)."""
    auth_error = _network_admin_error()
    if auth_error:
        return auth_error
    if not WEB_NODE_ENABLED:
        return jsonify({"ok": False, "error": "web node disattivati su questo control-plane"}), 503
    data = request.get_json(force=True, silent=True) or {}
    task_type = str(data.get("type", "") or "").strip()
    node_id = _web_node_id(data) or _web_capable_node(task_type)
    if not node_id:
        available = sorted({c for n in web_registry.nodes() for c in n["capabilities"]})
        return jsonify({"ok": False,
                        "error": f"nessun web node con capability '{task_type}'",
                        "available_capabilities": available}), 409
    try:
        task = web_registry.enqueue(node_id, task_type, data.get("payload") or {},
                                    constraints=data.get("constraints") or {})
    except WebNodeError as error:
        return _web_error(error)
    push_log('web_task', f"Web task enqueued {task['task_id']}",
             f"type={task_type} node={node_id[:12]}",
             source='control-plane', target=node_id[:12], status='pending')
    return jsonify({"ok": True, "task": task}), 202



@_bp.route('/web/status')
def web_status():
    """Istantanea per la dashboard: nodi browser, coda e ultimi esiti."""
    return jsonify({"enabled": WEB_NODE_ENABLED,
                    "heartbeat_interval_s": WEB_NODE_HEARTBEAT_S,
                    **web_registry.status(),
                    "recent_results": web_registry.results(limit=10),
                    "contacts": db.count_web_contacts()})


# Vista pubblica della mesh per la landing: solo nodi attivi e chiamabili,
# senza endpoint/IP/node_id (la proiezione e' in shared/web_topology.py).
# Cache breve: la rotta e' anonima, e _aggregate_mesh_models interroga i nodi.
_TOPOLOGY_CACHE_S = 10
_topology_cache = {"ts": 0.0, "data": None}
_topology_lock = threading.Lock()


def _build_public_topology():
    nodes = mesh._node_list()
    callable_ids = {n.get("node_id") for n in nodes if mesh._best_endpoint(n)}
    contesto = getattr(mesh, "_contesto", None)
    aggregate = {"bare": [], "per_node": []}
    if contesto is not None and getattr(contesto, "aggregate_mesh_models", None):
        try:
            aggregate = contesto.aggregate_mesh_models() or aggregate
        except Exception:
            pass
    return public_topology(
        nodes, aggregate.get("per_node"), web_registry.status().get("nodes"),
        callable_ids=callable_ids, aliases=dict(mesh._node_aliases),
        hub_models=aggregate.get("bare"))


@_bp.route('/web/topology', methods=['GET', 'OPTIONS'])
def web_topology():
    """Nodi realmente attivi, in forma pubblica. Nessun token: e' la vetrina."""
    if request.method == 'OPTIONS':
        return '', 204
    now = time.time()
    with _topology_lock:
        if _topology_cache["data"] is None or now - _topology_cache["ts"] > _TOPOLOGY_CACHE_S:
            _topology_cache.update(ts=now, data=_build_public_topology())
        data = _topology_cache["data"]
    response = jsonify(data)
    response.headers["Cache-Control"] = f"public, max-age={_TOPOLOGY_CACHE_S}"
    return response


_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _send_telegram_notification(token: str, chat_id: str, item: dict):
    try:
        name = html.escape(str(item.get("name", "")))
        email = html.escape(str(item.get("email", "")))
        subject = html.escape(str(item.get("subject", ""))) or "Nessun oggetto"
        msg = html.escape(str(item.get("message", "")))
        cid = html.escape(str(item.get("contact_id", "")))
        ts = html.escape(str(item.get("ts", "")))

        text = (
            f"📬 <b>Nuovo contatto da HyperSpace Web Node!</b>\n\n"
            f"👤 <b>Da:</b> {name}\n"
            f"📧 <b>Email:</b> <code>{email}</code>\n"
            f"🏷️ <b>Oggetto:</b> {subject}\n"
            f"🆔 <b>ID:</b> <code>{cid}</code>\n"
            f"⏰ <b>Data:</b> {ts}\n\n"
            f"💬 <b>Messaggio:</b>\n{msg}"
        )
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        button_name = (str(item.get("name", "")).strip() or "utente")[:20]
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": f"🔑 Emetti e Invia Token a {button_name}",
                            "callback_data": f"grant:{cid}"
                        }
                    ]
                ]
            }
        }
        res = requests.post(url, json=payload, timeout=6.0)
        if not res.ok:
            push_log('web_contact_notify', f"Errore notifica Telegram HTTP {res.status_code}",
                     detail=res.text[:200], source='web-node', status='warning')
        else:
            push_log('web_contact_notify', f"Notifica Telegram inviata per {cid}",
                     source='web-node', status='success')
    except Exception as exc:
        push_log('web_contact_notify', f"Eccezione notifica Telegram: {exc}",
                 source='web-node', status='warning')


def _notify_web_contact(item: dict):
    token = os.getenv("CONTACT_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("CONTACT_TELEGRAM_CHAT_ID", "").strip()
    if token and chat_id:
        threading.Thread(
            target=_send_telegram_notification,
            args=(token, chat_id, item),
            daemon=True
        ).start()


@_bp.route('/web/contact', methods=['POST', 'OPTIONS'])
def web_contact():
    """Riceve un messaggio dal form di contatto della landing page pubblica."""
    if request.method == 'OPTIONS':
        return '', 204
    data = request.get_json(force=True, silent=True) or {}

    # Honeypot anti-spam per bot automatici
    honeypot = str(data.get("honeypot") or data.get("website") or "").strip()
    if honeypot:
        # Falsa conferma per ingannare gli scraper senza inquinare il DB
        return jsonify({"ok": True, "message": "Messaggio inviato con successo"}), 200

    name = str(data.get("name", "") or "").strip()
    email = str(data.get("email", "") or "").strip()
    subject = str(data.get("subject", "") or "").strip()
    message = str(data.get("message", "") or "").strip()

    if not name or len(name) > 100:
        return jsonify({"ok": False, "error": "Il nome è obbligatorio (massimo 100 caratteri)"}), 400
    if not email or len(email) > 255 or not _EMAIL_REGEX.match(email):
        return jsonify({"ok": False, "error": "Indirizzo email non valido"}), 400
    if not message or len(message) < 5 or len(message) > 4000:
        return jsonify({"ok": False, "error": "Il messaggio deve essere compreso tra 5 e 4000 caratteri"}), 400
    if len(subject) > 200:
        return jsonify({"ok": False, "error": "L'oggetto può contenere al massimo 200 caratteri"}), 400

    client_ip = (request.headers.get("X-Hs-Client-Ip", "") or "").strip() or (request.remote_addr or "")
    item = db.insert_web_contact(name=name, email=email, subject=subject, message=message, ip=client_ip)

    push_log('web_contact', f"Nuovo messaggio da {name}",
             f"email={email} subject={subject[:50]} id={item['contact_id']}",
             source='web-node', status='info')

    _notify_web_contact(item)

    return jsonify({
        "ok": True,
        "contact_id": item["contact_id"],
        "message": "Messaggio inviato con successo"
    }), 201


@_bp.route('/web/contacts', methods=['GET'])
def web_contacts_list():
    """Elenco messaggi ricevuti. Riservato all'operatore di rete."""
    auth_error = _network_admin_error()
    if auth_error:
        return auth_error

    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        limit, offset = 50, 0
    status = request.args.get("status")
    contacts = db.list_web_contacts(limit=limit, offset=offset, status=status)
    counts = db.count_web_contacts()
    return jsonify({"ok": True, "contacts": contacts, "counts": counts})


@_bp.route('/web/contacts/<contact_id>', methods=['PATCH'])
def web_contact_update(contact_id):
    """Aggiorna lo stato di un messaggio (read, unread, archived). Riservato all'operatore."""
    auth_error = _network_admin_error()
    if auth_error:
        return auth_error

    data = request.get_json(force=True, silent=True) or {}
    new_status = str(data.get("status", "") or "").strip().lower()
    if new_status not in {"unread", "read", "archived", "starred"}:
        return jsonify({"ok": False, "error": "Stato non valido (consentiti: unread, read, archived, starred)"}), 400

    updated = db.update_web_contact_status(contact_id, new_status)
    if not updated:
        return jsonify({"ok": False, "error": "Messaggio non trovato"}), 404
    return jsonify({"ok": True, "contact_id": contact_id, "status": new_status})


@_bp.route('/web/auth/verify', methods=['POST', 'OPTIONS'])
def web_auth_verify():
    """Verifica un token/chiave di accesso per sbloccare le funzioni mesh del web-node."""
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(force=True, silent=True) or {}
    provided = str(data.get("token") or data.get("auth_key") or data.get("key") or "").strip()
    if not provided:
        auth_hdr = request.headers.get("Authorization", "").strip()
        if auth_hdr.lower().startswith("bearer "):
            provided = auth_hdr[7:].strip()
        elif request.headers.get("X-Hyperspace-Network-Token"):
            provided = request.headers.get("X-Hyperspace-Network-Token", "").strip()

    if not provided:
        return jsonify({"ok": False, "authenticated": False, "error": "Token di autenticazione mancante"}), 401

    # 1. Controllo token admin di rete
    if NETWORK_ADMIN_TOKEN and len(NETWORK_ADMIN_TOKEN) >= 32 and token_authorized(provided, NETWORK_ADMIN_TOKEN):
        return jsonify({
            "ok": True,
            "authenticated": True,
            "role": "admin",
            "label": "Amministratore Mesh"
        })

    # 2. Controllo token dedicato web-node
    web_token = os.getenv("WEB_NODE_AUTH_TOKEN", "").strip()
    web_tokens_raw = os.getenv("WEB_NODE_AUTH_TOKENS", "").strip()
    allowed_tokens = [t.strip() for t in web_tokens_raw.split(",") if t.strip()]
    if web_token:
        allowed_tokens.append(web_token)

    for tok in allowed_tokens:
        if len(tok) >= 8 and token_authorized(provided, tok):
            return jsonify({
                "ok": True,
                "authenticated": True,
                "role": "member",
                "label": "Utente Mesh Autorizzato"
            })

    # 3. Controllo chiavi dinamiche a database SQLite
    db_key = db.get_auth_key(provided)
    if db_key and db_key.get("status") == "active":
        db.touch_auth_key(provided)
        label = db_key.get("label") or "Utente Mesh Autorizzato"
        return jsonify({
            "ok": True,
            "authenticated": True,
            "role": db_key.get("role", "member"),
            "label": label
        })

    return jsonify({"ok": False, "authenticated": False, "error": "Chiave o token non valido"}), 401