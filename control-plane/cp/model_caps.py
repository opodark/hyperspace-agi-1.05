# SPDX-License-Identifier: Apache-2.0
# control-plane/cp/model_caps.py
# CAPACITA' DEL MODELLO: chi riceve i tool, e chi li spegne per chiesto.
#
# Perche' esiste: una funzione sola, "questo modello riceve i tool?", con i
# motivi espliciti. Sono qui tre cose che stavano in tre punti diversi di
# main.py e che i test trattano insieme (tests/test_model_patterns.py le
# estrae ed esegue in un scope solo):
#
# 1. i pattern di tool-capability e di native-chat fallback;
# 2. il flag X-Hyperspace-Tools: off, che sospende i tool del CP per una
#    chiamata deterministica (un grafo ComfyUI, uno script) senza toccare
#    quelli del client;
# 3. `_use_native_chat_fallback`, che sta nella sezione "budget" di main.py
#    ma parla di modelli: e finita qui per stare con le altre due.
#
# Quarto blocco: `_warn_tools_stripped`, l'avviso che dice PERCHE' i tool sono
# stati tolti. Sta qui perche' dipende da `_tool_capability_reason`, che e' gia'
# qui: la ragione e l'avviso che la riporta non possono stare in due posti.
#
# e lancia la richiesta al modello.

import os
import time

from cp.log import push_log

# ── TOOL CAPABLE MODELS ────────────────────────────────────────────────────────
_TOOL_CAPABLE_OVERRIDE = os.getenv("TOOL_CAPABLE_MODELS", "")
_TOOL_CAPABLE_PATTERNS = [
    "qwen3", "qwen2.5", "llama3.1", "llama3.2", "llama3.3",
    "mistral-nemo", "mistral-small", "mixtral",
    "command-r", "firefunction", "functionary",
    "hermes", "nexusraven", "gorilla", "gemma4", "gemma-4", "deepseek-r1",
    "phi4", "granite", "flint",
]
# Varianti vision (es. qwen2.5vl) non supportano le tool call di Ollama anche
# quando il modello testuale base e' in _TOOL_CAPABLE_PATTERNS — "qwen2.5vl"
# altrimenti farebbe match su "qwen2.5" per substring e si vedrebbe rifiutare
# le tools da Ollama ("does not support tools").
_VISION_PATTERNS = ["vl", "vision", "llava"]

def _model_supports_tools(model_name: str) -> bool:
    override = _TOOL_CAPABLE_OVERRIDE.strip()
    if override == "*":
        return True
    if override:
        for p in override.split(","):
            p = p.strip().lower()
            # `if p` non e' cosmetico: con TOOL_CAPABLE_MODELS="qwen3," (o con
            # soli spazi) il pattern vuoto sarebbe substring di QUALSIASI nome
            # modello, abilitando le tool call su tutti i modelli per sbaglio.
            if p and p in model_name.lower():
                return True
    m = model_name.lower().split(":")[0]
    if any(p in m for p in _VISION_PATTERNS):
        return False
    return any(p in m for p in _TOOL_CAPABLE_PATTERNS)

# Modelli per cui il fallback "Ollama diretto" (nessun nodo mesh disponibile)
# usa il percorso NATIVO /api/chat invece di quello OpenAI-compatibile. Serve
# ai modelli reasoning, per i quali il CP vuole pilotare esplicitamente `think`:
# sul percorso OpenAI il campo `reasoning` resta comunque popolato.
# L'elenco NON e' cablato nel codice: i modelli reasoning distillati cambiano
# in fretta. Override da env NATIVE_CHAT_FALLBACK_MODELS (lista separata da
# virgole, "*" = tutti i modelli), modificabile da tab Setup.
_NATIVE_CHAT_FALLBACK_OVERRIDE  = os.getenv("NATIVE_CHAT_FALLBACK_MODELS", "")
_NATIVE_CHAT_FALLBACK_PATTERNS  = ["qwen3"]


# ── MODELLI CHE RAGIONANO SEMPRE ──────────────────────────────────────────────
# Alcune varianti (qwen3:4b nella build 2507 "Thinking") non hanno una modalita'
# senza ragionamento. Con think=false Ollama non separa il ragionamento e lo
# scrive dentro `content`: la risposta diventa "Okay, the user is saying..." e,
# con max_tokens bassi, non arriva mai alla frase utile (verificato sulla mesh
# pubblica il 2026-10-27). Per questi modelli il CP chiede think=true, cosi' il
# ragionamento finisce nel suo campo, e non lo ricopia in `content`.
# Ollama lo dichiara in /api/show: `thinking.values == [true]` (un modello
# ibrido come qwen3:8b dichiara [false, true]). Override da env
# THINKING_ONLY_MODELS (lista di pattern, "off" per disattivare il rilevamento).
_THINKING_ONLY_OVERRIDE = os.getenv("THINKING_ONLY_MODELS", "")
_THINKING_ONLY_CACHE: dict = {}
_THINKING_ONLY_TTL_S = 600


def _model_thinking_only(model_name: str) -> bool:
    name = str(model_name or "").strip()
    if not name:
        return False
    override = _THINKING_ONLY_OVERRIDE.strip().lower()
    if override in {"off", "false", "none"}:
        return False
    if override:
        patterns = [p.strip() for p in override.split(",") if p.strip()]
        if patterns:
            return any(p in name.lower() for p in patterns)
    now = time.time()
    cached = _THINKING_ONLY_CACHE.get(name)
    if cached and now - cached[1] < _THINKING_ONLY_TTL_S:
        return cached[0]
    try:
        import requests
        from cp.config import OLLAMA_URL
        r = requests.post(f"{OLLAMA_URL.rstrip('/')}/api/show", json={"model": name}, timeout=3)
        thinking = (r.json() or {}).get("thinking") if r.ok else None
        values = thinking.get("values") if isinstance(thinking, dict) else None
        result = isinstance(values, list) and bool(values) and all(v is True for v in values)
    except Exception:
        # Ollama locale irraggiungibile o modello solo remoto: nessun cambio.
        result = False
    _THINKING_ONLY_CACHE[name] = (result, now)
    return result


def _tool_capability_reason(model_name: str) -> str:
    """Perche' questo modello riceve o non riceve i tool (diagnostica).

    Serve al momento del cambio modello: un modello nuovo che supporta il
    function calling ma non compare in nessun pattern perde i tool IN SILENZIO
    (il CP li rimuove dalla richiesta), e l'unico sintomo e' "web_search non
    parte piu'". Qui la ragione diventa esplicita, e finisce nei log.
    """
    override = _TOOL_CAPABLE_OVERRIDE.strip()
    if override == "*":
        return "override: tutti i modelli"
    if override:
        for p in override.split(","):
            p = p.strip().lower()
            if p and p in model_name.lower():
                return f"override TOOL_CAPABLE_MODELS: {p}"
    m = model_name.lower().split(":")[0]
    vision = next((p for p in _VISION_PATTERNS if p in m), None)
    if vision:
        return f"escluso: variante vision ({vision})"
    matched = next((p for p in _TOOL_CAPABLE_PATTERNS if p in m), None)
    if matched:
        return f"pattern: {matched}"
    return "NESSUN pattern corrisponde"

TOOLS_OFF_VALUES = ("off", "0", "false", "no", "disabilitati")

def _tools_requested_off(valore) -> bool:
    valore = str(valore or "").strip().lower()
    return valore in TOOLS_OFF_VALUES

def _use_native_chat_fallback(model_name: str) -> bool:
    """True se il fallback Ollama-diretto deve passare dal percorso nativo
    /api/chat. Confronto per substring sul nome base del modello, come
    _model_supports_tools(): cosi' "qwen3:8b", "qwen3-16k" e i futuri
    distillati "qwen3.8-..." restano coperti senza toccare il codice."""
    override = _NATIVE_CHAT_FALLBACK_OVERRIDE.strip()
    if override.lower() in {"off", "false", "none"}:
        return False
    if override == "*":
        return True
    # Un override di soli spazi, o con solo virgole, produce una lista vuota:
    # in quel caso NON deve disabilitare in silenzio il fallback, ma tornare ai
    # pattern di default (stesso motivo del `if p` in _model_supports_tools).
    parsed = [p.strip().lower() for p in override.split(",") if p.strip()] if override else []
    patterns = parsed or _NATIVE_CHAT_FALLBACK_PATTERNS
    m = model_name.lower().split(":")[0]
    return any(p in m for p in patterns)


# ── IL WARNING DEI TOOL TOltI ────────────────────────────────────────────────
# Un modello a cui togliamo i tool deve dirlo: al cambio modello il sintomo
# sarebbe altrimenti solo "web_search non parte piu'". Rate-limit per modello,
# cosi' una chat lunga non riempie il DB di log.
#
# Sta qui e non in main.py perche' dipende da `_tool_capability_reason`, che e'
# gia' in questo modulo: la ragione del "no" e l'avviso che la riporta non
# possono stare in due posti, altrimenti un giorno ne accadono versioni diverse.
_TOOL_STRIPPED_WARN_AT: dict = {}
_TOOL_STRIPPED_WARN_EVERY_S = 300


def _warn_tools_stripped(model: str) -> None:
    now = time.time()
    if now - _TOOL_STRIPPED_WARN_AT.get(model, 0.0) < _TOOL_STRIPPED_WARN_EVERY_S:
        return
    _TOOL_STRIPPED_WARN_AT[model] = now
    push_log('system', f'{model}: tool rimossi dalla richiesta',
             f"motivo: {_tool_capability_reason(model)}. Se il modello supporta il "
             f"function calling, aggiungilo a TOOL_CAPABLE_MODELS (env, tab Setup); "
             f"elenco completo su GET /models/capabilities.",
             status='warn')
