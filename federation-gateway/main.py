# SPDX-License-Identifier: Apache-2.0
# federation-gateway/main.py
# HyperSpace AGI v1.03 — Federation Gateway
#
# Unico componente pensato per essere esposto pubblicamente (via Caddy o tunnel)
# nello scenario di CP confederati. Non contiene NESSUNA logica di verifica
# firma o allowlist: quella vive nel control-plane (/federate/execute),
# perché deve restare un'unica fonte di verità condivisa con la dashboard.
#
# Il gateway fa una cosa sola: inoltra sulla rete Docker interna SOLO le
# rotte esplicitamente whitelisted. Qualsiasi altro path (dashboard, config,
# task manuali, log, gestione peer) riceve 404 senza mai toccare il CP.
# Anche in caso di bug nella verifica firma del CP, chi attacca da qui fuori
# non ha comunque modo di raggiungere endpoint sensibili: non fanno parte
# della superficie che questo componente sa inoltrare.
#
# BOTTLES: /bottles/publish e /bottles/list sono l'unico bootstrap pubblico
# indipendente del progetto (vedi docs/network-panel.md) — un nodo isolato,
# senza ancora accesso alla rete privata Tailscale, deve poterle raggiungere
# da qui. /bottles/announce resta FUORI dalla whitelist di proposito: è
# un'azione admin (richiede NETWORK_ADMIN_TOKEN lato CP) pensata per la
# dashboard interna, non per chiamanti pubblici anonimi.
#
# Rispetto alle route bottle "nude", questo gateway aggiunge due cose:
#   1. un rate-limit di soglia (oltre al proof-of-work e al rate-limit
#      per-IP già nel CP — vedi shared/bottle.py: difesa in profondità, non
#      l'unica barriera);
#   2. la propagazione AUTENTICATA dell'IP pubblico reale del chiamante:
#      senza, il CP vedrebbe solo l'IP Docker interno DI QUESTO GATEWAY per
#      ogni richiesta pubblica, collassando il suo rate-limit per-IP su un
#      unico contatore condiviso da tutto il traffico esterno.
# La firma (sign_client_ip) vive in shared/network_security.py insieme a
# verify_client_ip, usata solo dal CP: stessa primitiva, stessa disciplina
# del resto del progetto — il gateway sa solo firmare, mai validare.

import hashlib
import json
import os
import threading
import time

from flask import Flask, request, Response
import requests

from shared.network_security import sign_client_ip

app = Flask(__name__)
app.logger.setLevel("INFO")

CP_URL = os.getenv("CP_URL", "http://control-plane:8085").rstrip("/")
CHAT_UPSTREAM_TIMEOUT_S = max(130, int(os.getenv("GATEWAY_CHAT_TIMEOUT_S", "600")))
GATEWAY_CHAT_MAX_TOKENS = int(os.getenv("GATEWAY_CHAT_MAX_TOKENS", "2048"))
GATEWAY_CHAT_AUTH_MAX_TOKENS = int(os.getenv("GATEWAY_CHAT_AUTH_MAX_TOKENS", "4096"))
GATEWAY_CHAT_MAX_CTX = 4096
GATEWAY_CHAT_AUTH_MAX_CTX = int(os.getenv("GATEWAY_CHAT_AUTH_MAX_CTX", "16384"))
GATEWAY_CHAT_AUTH_MAX_PER_MINUTE = int(os.getenv("GATEWAY_CHAT_AUTH_MAX_PER_MINUTE", "60"))

# Whitelist esplicita (metodo, path). Aggiungere qui SOLO endpoint pensati
# per essere pubblici by design — non aggiungere mai /config/*, /task/*,
# /logs/*, /federation/peers* (gestione allowlist, solo dashboard interna),
# né /bottles/announce (azione admin, vedi commento in cima al file).
ALLOWED_ROUTES = {
    ("POST", "/federate/execute"),
    # /federate/view e' l'unica rotta federata in LETTURA: restituisce a un peer
    # ACCOPPIATO un'istantanea di nodi, modelli, task e log di questo CP
    # (docs/control-plane-sync.md). Sta in whitelist perche' il CP la verifica da
    # solo con firma ECDSA + allowlist, esattamente come /federate/execute: il
    # gateway non aggiunge fiducia, toglie superficie. Nota: condivide solo se
    # FEDERATION_VIEW_ENABLED=true sul CP, che di default e' false — quindi la
    # rotta e' raggiungibile ma risponde 403 finche' l'operatore non lo decide.
    # /federation/views NON e' qui, ed e' deliberato: quella e' la vista
    # aggregata per la dashboard interna, e da fuori diventeremmo una sonda
    # verso i peer federati per chiunque.
    ("GET",  "/federate/view"),
    ("GET",  "/federation/identity"),
    ("POST", "/bottles/publish"),
    ("GET",  "/bottles/list"),
    # Ingresso pubblico dei browser node. Non espone chat, modelli, dashboard o
    # task amministrativi: il browser si registra, tira un task web-safe e ne
    # restituisce l'esito. OPTIONS serve al preflight CORS della pagina HTTPS.
    ("POST", "/web/register"),
    ("POST", "/web/poll"),
    ("POST", "/web/result"),
    ("OPTIONS", "/web/register"),
    ("OPTIONS", "/web/poll"),
    ("OPTIONS", "/web/result"),
    ("POST", "/web/contact"),
    ("OPTIONS", "/web/contact"),
    ("POST", "/web/auth/verify"),
    ("OPTIONS", "/web/auth/verify"),
    ("POST", "/web/search"),
    ("OPTIONS", "/web/search"),
    ("POST", "/web/sandbox/run"),
    ("OPTIONS", "/web/sandbox/run"),
    ("POST", "/web/image/generate"),
    ("OPTIONS", "/web/image/generate"),
    ("GET", "/web/image/status"),
    ("OPTIONS", "/web/image/status"),
    ("GET", "/web/image/file"),
    ("OPTIONS", "/web/image/file"),
    # Tokenomics per Nodi Web ($00MESH)
    ("POST", "/web/node/wallet"),
    ("OPTIONS", "/web/node/wallet"),
    ("GET", "/web/node/balance"),
    ("OPTIONS", "/web/node/balance"),
    ("GET", "/web/tokenomics/status"),
    ("OPTIONS", "/web/tokenomics/status"),
    ("GET", "/tokenomics/leaderboard"),
    ("OPTIONS", "/tokenomics/leaderboard"),
    ("GET", "/web/tokenomics/leaderboard"),
    ("OPTIONS", "/web/tokenomics/leaderboard"),
    # Vista pubblica della topologia: solo conteggi, etichette pubbliche e
    # modelli (gli stessi di /v1/models). Il CP non vi mette endpoint ne' IP.
    ("GET", "/web/topology"),
    ("OPTIONS", "/web/topology"),
    ("GET", "/web/ping"),
    ("OPTIONS", "/web/ping"),
    # Esperienza pubblica della mesh: catalogo e chat OpenAI-compatible.
    # Restano escluse dashboard, log, task manuali e configurazione. Il rate
    # limit qui sotto protegge il CP da uso anonimo eccessivo.
    ("GET", "/v1/models"),
    ("OPTIONS", "/v1/models"),
    ("POST", "/v1/chat/completions"),
    ("OPTIONS", "/v1/chat/completions"),
}

_EXCLUDED_RESPONSE_HEADERS = {"content-encoding", "content-length", "transfer-encoding", "connection"}

# Header con cui questo gateway attesta al CP l'IP pubblico reale del
# chiamante. Riservati: un client esterno non deve MAI poterli impostare lui
# stesso (altrimenti potrebbe far credere al CP di chiamare da un IP
# arbitrario e aggirare il suo rate-limit per-IP) — vengono sempre rimossi
# da quanto arriva dal client prima di inoltrare, su OGNI rotta, non solo
# quelle bottle.
_CLIENT_IP_HEADERS = ("X-Hs-Client-Ip", "X-Hs-Client-Ts", "X-Hs-Client-Sig")
_RESERVED_HEADER_NAMES = {h.lower() for h in _CLIENT_IP_HEADERS} | {"host"}

# Le route anonime pubbliche hanno un rate-limit dedicato qui. Le bottle hanno
# anche proof-of-work e limiti nel CP; i web node hanno limiti di registro,
# payload e coda nel CP. path -> (richieste, secondi).
_RATE_LIMITS = {
    "/bottles/publish": (int(os.getenv("GATEWAY_BOTTLE_PUBLISH_MAX_PER_HOUR", "20")), 3600),
    "/bottles/list":    (int(os.getenv("GATEWAY_BOTTLE_LIST_MAX_PER_MINUTE", "30")), 60),
    "/web/register":    (int(os.getenv("GATEWAY_WEB_REGISTER_MAX_PER_MINUTE", "12")), 60),
    "/web/poll":        (int(os.getenv("GATEWAY_WEB_POLL_MAX_PER_MINUTE", "30")), 60),
    "/web/result":      (int(os.getenv("GATEWAY_WEB_RESULT_MAX_PER_MINUTE", "30")), 60),
    "/web/contact":     (int(os.getenv("GATEWAY_WEB_CONTACT_MAX_PER_HOUR", "10")), 3600),
    "/web/auth/verify": (int(os.getenv("GATEWAY_WEB_AUTH_MAX_PER_MINUTE", "20")), 60),
    "/web/search":      (int(os.getenv("GATEWAY_WEB_SEARCH_MAX_PER_MINUTE", "20")), 60),
    "/web/sandbox/run": (int(os.getenv("GATEWAY_WEB_SANDBOX_MAX_PER_MINUTE", "15")), 60),
    "/web/image/generate": (int(os.getenv("GATEWAY_IMAGE_GENERATE_MAX_PER_MINUTE", "12")), 60),
    "/web/image/status":   (int(os.getenv("GATEWAY_IMAGE_STATUS_MAX_PER_MINUTE", "60")), 60),
    "/web/image/file":     (int(os.getenv("GATEWAY_IMAGE_FILE_MAX_PER_MINUTE", "60")), 60),
    "/web/node/wallet":    (int(os.getenv("GATEWAY_NODE_WALLET_MAX_PER_MINUTE", "15")), 60),
    "/web/node/balance":   (int(os.getenv("GATEWAY_NODE_BALANCE_MAX_PER_MINUTE", "60")), 60),
    "/web/tokenomics/status": (int(os.getenv("GATEWAY_TOKENOMICS_STATUS_MAX_PER_MINUTE", "30")), 60),
    "/web/topology":    (int(os.getenv("GATEWAY_WEB_TOPOLOGY_MAX_PER_MINUTE", "20")), 60),
    "/v1/models":       (int(os.getenv("GATEWAY_MODELS_MAX_PER_MINUTE", "30")), 60),
    "/v1/chat/completions": (int(os.getenv("GATEWAY_CHAT_MAX_PER_MINUTE", "12")), 60),
}
_RATE_MAX_TRACKED_KEYS = int(os.getenv("GATEWAY_BOTTLE_RATE_MAX_IPS", "4096"))

_rate_lock = threading.Lock()
_rate_hits: dict[tuple[str, str], list[float]] = {}


def _client_ip() -> str:
    """IP del chiamante da usare per il rate-limit e da attestare al CP.

    Con TRUST_PROXY_HEADERS=true (gateway dietro UN SOLO reverse proxy
    fidato davanti, es. Caddy con `reverse_proxy` di default) legge il primo
    hop di X-Forwarded-For, che quel proxy imposta lui stesso. ATTENZIONE:
    è un'assunzione a un solo hop — con più di un proxy in catena (o dietro
    un tunnel che non normalizza l'header) un client potrebbe falsificare
    gli hop successivi al primo; non abilitare finché la topologia reale
    non è esattamente "un Caddy davanti a questo gateway, niente altro in
    mezzo". Di default (false) usa la connessione TCP diretta, corretta
    quando il gateway è già il primo punto pubblico (es. dietro un tunnel L4
    che non riscrive gli header)."""
    if os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true":
        xff = request.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.remote_addr or "?"


def _rate_check(path: str, ip: str) -> bool:
    limit = _RATE_LIMITS.get(path)
    if not limit:
        return True
    max_hits, window_s = limit
    key = (path, ip)
    now = time.time()
    with _rate_lock:
        for old_key in list(_rate_hits):
            old_path, _ = old_key
            old_window_s = _RATE_LIMITS.get(old_path, (0, window_s))[1]
            kept = [t for t in _rate_hits[old_key] if now - t < old_window_s]
            if kept:
                _rate_hits[old_key] = kept
            else:
                _rate_hits.pop(old_key, None)
        if key not in _rate_hits and len(_rate_hits) >= _RATE_MAX_TRACKED_KEYS:
            return False
        recent = _rate_hits.get(key, [])
        if len(recent) >= max_hits:
            return False
        recent.append(now)
        _rate_hits[key] = recent
        return True


# ── CHIAVI MESH SULLA CHAT PUBBLICA ───────────────────────────────────────────
# Una chiave hs-mesh-* (o un token web-node) da' alla chat pubblica un proprio
# rate-limit, piu' token e piu' contesto. La presenza dell'header non basta:
# prima di questa verifica chiunque mandasse "Authorization: x" otteneva il
# tetto dei membri. La verita' sulle chiavi resta nel CP (/web/auth/verify);
# qui si tiene solo l'esito, indicizzato per hash, per non chiamarlo a ogni
# richiesta. Una chiave non valida non e' un errore: si resta nel livello
# anonimo, come succede ai client OpenAI che mandano una api_key qualsiasi.
_KEY_CACHE_TTL_S = 60
_KEY_CACHE_MAX = 4096
_key_cache_lock = threading.Lock()
_key_cache: dict[str, tuple[bool, float]] = {}


def _provided_mesh_key() -> str:
    auth_hdr = request.headers.get("Authorization", "").strip()
    if auth_hdr.lower().startswith("bearer "):
        return auth_hdr[7:].strip()
    return (request.headers.get("X-Hyperspace-Auth-Key")
            or request.headers.get("X-Hyperspace-Network-Token") or "").strip()


def _mesh_key_valid(key: str) -> bool:
    if not key or len(key) > 512:
        return False
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    now = time.time()
    with _key_cache_lock:
        cached = _key_cache.get(digest)
        if cached and now - cached[1] < _KEY_CACHE_TTL_S:
            return cached[0]
    # Ogni chiave nuova (anche inventata) costa una chiamata al CP: la paga il
    # rate-limit per IP della verifica, non quello della chat.
    if not _rate_check("/web/auth/verify", _client_ip()):
        return False
    try:
        r = requests.post(f"{CP_URL}/web/auth/verify", json={"token": key}, timeout=5)
        valid = r.status_code == 200 and bool((r.json() or {}).get("authenticated"))
    except Exception:
        # CP irraggiungibile: niente privilegi, e niente cache dell'esito.
        return False
    with _key_cache_lock:
        if len(_key_cache) >= _KEY_CACHE_MAX:
            _key_cache.clear()
        _key_cache[digest] = (valid, now)
    return valid


def _rate_check_key(key: str) -> bool:
    """Rate-limit della chat per chiave valida, separato da quello per IP."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    now = time.time()
    bucket = ("/v1/chat/completions#key", digest)
    with _rate_lock:
        recent = [t for t in _rate_hits.get(bucket, []) if now - t < 60]
        if len(recent) >= GATEWAY_CHAT_AUTH_MAX_PER_MINUTE:
            _rate_hits[bucket] = recent
            return False
        recent.append(now)
        _rate_hits[bucket] = recent
        return True


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
def proxy(path):
    full_path = f"/{path}"
    check_method = "GET" if request.method == "HEAD" and ("GET", full_path) in ALLOWED_ROUTES else request.method
    route_key = (check_method, full_path)
    if route_key not in ALLOWED_ROUTES:
        return {"error": "not found"}, 404

    ip = _client_ip()
    member_chat = False
    if full_path == "/v1/chat/completions" and request.method == "POST":
        member_key = _provided_mesh_key()
        member_chat = _mesh_key_valid(member_key)
        if member_chat and not _rate_check_key(member_key):
            return {
                "error": "Limite richieste per chiave superato, riprova tra un minuto.",
                "code": "RATE_LIMIT_EXCEEDED",
            }, 429
    # Preflight e HEAD non eseguono lavoro applicativo e non consumano il rate limit
    if (request.method not in ("OPTIONS", "HEAD") and full_path in _RATE_LIMITS
            and not member_chat and not _rate_check(full_path, ip)):
        return {
            "error": "Limite richieste anonime superato. Con una chiave membro hs-mesh-* (POST /web/contact) in Authorization: Bearer il limite sale a 60 richieste al minuto.",
            "code": "RATE_LIMIT_EXCEEDED",
            "vip_upgrade": "https://www.zerozerocomputer.it/index.html#contactSection"
        }, 429

    forward_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _RESERVED_HEADER_NAMES
    }
    secret = os.getenv("BOTTLE_GATEWAY_SECRET", "")
    if full_path in _RATE_LIMITS and len(secret) >= 32:
        ts = str(time.time())
        forward_headers["X-Hs-Client-Ip"] = ip
        forward_headers["X-Hs-Client-Ts"] = ts
        forward_headers["X-Hs-Client-Sig"] = sign_client_ip(secret, ip, ts)

    # Il CP puo' restare in attesa del nodo per oltre un minuto prima di inviare
    # gli header. Funnel e alcuni browser interpretano quel silenzio come una
    # connessione morta. Apriamo subito uno stream SSE con un keepalive; se il
    # backend restituisce JSON nativo, lo trasformiamo nello stesso contratto.
    if full_path == "/v1/chat/completions" and request.method == "POST":
        origin = request.headers.get("Origin", "*") or "*"
        method = request.method
        try:
            public_payload = request.get_json(force=True) or {}
        except Exception:
            public_payload = {}
        if "model" in public_payload:
            raw_m = str(public_payload.get("model") or "").strip()
            if not raw_m or "<" in raw_m or ">" in raw_m:
                return (
                    {
                        "error": {
                            "message": f"model '{public_payload.get('model')}' not found",
                            "type": "model_not_found",
                            "param": "model",
                            "code": "model_not_found",
                        }
                    },
                    404,
                )
        client_wants_stream = bool(public_payload.get("stream", False))
        # La pagina pubblica deve avere latenza prevedibile: i tool possono
        # moltiplicare le inferenze anche per domande semplici. Il CP usa il
        # percorso nativo non-stream, che rispetta think=false e max_tokens;
        # se il client ha chiesto stream=True (es. browser SSE), la risposta JSON
        # viene riconfezionata come SSE con keepalive; altrimenti (default OpenAI
        # stream=False) viene restituita come JSON standard application/json.
        public_payload["stream"] = False
        public_payload["think"] = False
        max_allowed = GATEWAY_CHAT_AUTH_MAX_TOKENS if member_chat else GATEWAY_CHAT_MAX_TOKENS
        max_ctx = GATEWAY_CHAT_AUTH_MAX_CTX if member_chat else GATEWAY_CHAT_MAX_CTX
        requested_tokens = int(public_payload.get("max_tokens", max_allowed))
        public_payload["max_tokens"] = min(max_allowed, max(1, requested_tokens))
        options = public_payload.get("options") if isinstance(public_payload.get("options"), dict) else {}
        public_payload["options"] = {**options, "num_ctx": min(max_ctx, max(2048, int(options.get("num_ctx", 4096))))}
        body = json.dumps(public_payload, ensure_ascii=False).encode("utf-8")
        forward_headers["Content-Type"] = "application/json"
        forward_headers["X-Hyperspace-Tools"] = "off"
        query = request.args.to_dict(flat=False)

        if not client_wants_stream:
            try:
                upstream = requests.request(
                    method=method,
                    url=f"{CP_URL}{full_path}",
                    headers=forward_headers,
                    data=body,
                    params=query,
                    timeout=(10, CHAT_UPSTREAM_TIMEOUT_S),
                )
            except Exception as e:
                return {"error": {"message": f"control-plane non raggiungibile: {e}", "type": "server_error"}}, 502
            raw_content = getattr(upstream, "content", None)
            if not isinstance(raw_content, (bytes, bytearray)):
                try:
                    raw_content = json.dumps(upstream.json(), ensure_ascii=False).encode("utf-8")
                except Exception:
                    raw_content = b"{}"
            return Response(
                raw_content,
                status=upstream.status_code,
                headers={"Access-Control-Allow-Origin": origin, "Vary": "Origin"},
                content_type=upstream.headers.get("Content-Type", "application/json"),
            )

        def chat_stream():
            started = time.monotonic()
            yield b": gateway connected\n\n"
            try:
                upstream = requests.request(
                    method=method,
                    url=f"{CP_URL}{full_path}",
                    headers=forward_headers,
                    data=body,
                    params=query,
                    timeout=(10, CHAT_UPSTREAM_TIMEOUT_S),
                    stream=True,
                )
                first_byte_s = time.monotonic() - started
                app.logger.info("public chat upstream headers status=%s first_byte_s=%.2f",
                                upstream.status_code, first_byte_s)
                content_type = upstream.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    payload = upstream.json()
                    if not upstream.ok or payload.get("error"):
                        error = payload.get("error") or f"HTTP {upstream.status_code}"
                        if isinstance(error, dict):
                            error = error.get("message") or str(error)
                        yield f"data: {json.dumps({'error': str(error)})}\n\n".encode()
                        return
                    choice = ((payload.get("choices") or [{}])[0])
                    message = choice.get("message") or {}
                    content = message.get("content", "")
                    event = {"choices": [{"delta": {"role": "assistant", "content": content},
                                           "finish_reason": choice.get("finish_reason")} ]}
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
                    yield b"data: [DONE]\n\n"
                    app.logger.info("public chat complete format=json total_s=%.2f",
                                    time.monotonic() - started)
                    return
                for chunk in upstream.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
                app.logger.info("public chat complete format=sse total_s=%.2f",
                                time.monotonic() - started)
            except Exception as error:
                app.logger.warning("public chat failed after %.2fs: %s",
                                   time.monotonic() - started, error)
                yield f"data: {json.dumps({'error': str(error)})}\n\n".encode()

        return Response(
            chat_stream(),
            headers={"Access-Control-Allow-Origin": origin, "Vary": "Origin"},
            content_type="text/event-stream",
        )

    try:
        upstream = requests.request(
            method=request.method,
            url=f"{CP_URL}{full_path}",
            headers=forward_headers,
            data=request.get_data(),
            params=request.args,
            timeout=130,
        )
    except Exception as e:
        return {"error": f"control-plane non raggiungibile: {e}"}, 502

    headers = [
        (k, v) for k, v in upstream.headers.items()
        if k.lower() not in _EXCLUDED_RESPONSE_HEADERS
    ]
    return Response(
        upstream.content,
        status=upstream.status_code,
        headers=headers,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )


@app.after_request
def _add_cors_headers(response):
    origin = request.headers.get("Origin") or "*"
    if "Access-Control-Allow-Origin" not in response.headers:
        response.headers["Access-Control-Allow-Origin"] = origin
    if "Access-Control-Allow-Methods" not in response.headers:
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    if "Access-Control-Allow-Headers" not in response.headers:
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Hyperspace-Network-Token"
    return response


@app.route("/", methods=["GET", "OPTIONS", "HEAD"])
def root():
    """Root del gateway federato: reindirizza i browser al portale sovrano
    con wallet e nodi (mesh.html) e risponde con metadati di discovery per client API."""
    if request.method == "OPTIONS":
        return Response("", status=204)
    accept = request.headers.get("Accept", "")
    if "text/html" in accept:
        from flask import redirect
        return redirect("https://www.zerozerocomputer.it/mesh.html", code=302)
    return {
        "status": "online",
        "mesh": "00MESH",
        "service": "federation-gateway",
        "version": "1.05",
        "endpoints": {
            "portal_ui": "https://www.zerozerocomputer.it/mesh.html",
            "chat_ui": "https://www.zerozerocomputer.it/chat.html",
            "topology": "/web/topology",
            "ping": "/web/ping",
            "models": "/v1/models",
            "chat_completions": "/v1/chat/completions",
            "health": "/health",
        },
        "discovery": "https://www.zerozerocomputer.it/llms.txt",
    }


@app.route("/web/ping", methods=["GET", "OPTIONS", "HEAD"])
def ping():
    """Endpoint zero-cost per verificare la connettività machine-to-machine
    senza caricare modelli né consumare GPU/token."""
    if request.method == "OPTIONS":
        return Response("", status=204)
    return {
        "status": "ok",
        "mesh": "00MESH",
        "version": "1.05",
        "echo": "pong",
        "service": "federation-gateway",
        "timestamp": time.time(),
    }


@app.route("/health", methods=["GET", "OPTIONS", "HEAD"])
def health():
    """Unico endpoint informativo extra, utile per gli healthcheck Docker
    e per verificare che il gateway sia in piedi senza rivelare nulla sul CP."""
    return {"status": "ok", "service": "federation-gateway", "cp_url": CP_URL}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8095, debug=False)
