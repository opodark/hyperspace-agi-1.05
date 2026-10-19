# SPDX-License-Identifier: Apache-2.0
# control-plane/cp/budget.py
# BUDGET DI TEMPO DI UNA RICHIESTA — timeout e deadline della catena di fallback.
#
# Perche' esiste: con un budget fisso, deepseek-r1:8b con 600 token di risposta
# non concludeva entro i 180s (Read timed out, verificato lato server), e un
# 200 con corpo d'errore faceva sembrare riuscito un fallimento.
#
# Vive qui perche' e' logica, non rotte: i test la estragono e la eseguono da
# sola (tests/test_request_budget.py) senza bisogno di Flask, DB o rete. Il resto
# del budget che NON e' puro resta in main.py: `_deadline_exceeded` scrive sul DB
# e chiama push_log, quindi dipende dal runtime.
#
# `jsonify` viene da flask, non da main.py: e' quello che permette a questo
# modulo di restare indipendente senza import circolari.

import os
import threading
import time
from datetime import datetime, timezone

from flask import jsonify, request
from shared.network_security import token_authorized

DREAM_REVIEW_TOKEN = os.getenv("DREAM_REVIEW_TOKEN", "")

def _dream_review_auth_error():
    token = os.getenv("DREAM_REVIEW_TOKEN", DREAM_REVIEW_TOKEN)
    if len(token) < 32:
        return jsonify({"error": "DREAM_REVIEW_TOKEN assente o troppo corto — revisione disabilitata"}), 503
    provided = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token_authorized(provided, token):
        return jsonify({"error": "Token revisione sogni non valido"}), 401
    return None


INFERENCE_TIMEOUT_S           = int(os.getenv("INFERENCE_TIMEOUT_S", "180"))
# Il default reasoning e' stato alzato da 600 a 1200: un modello 8B lento
# (~6-7 t/s) che genera uno script intero in una tool call (es. reportlab per
# il PDF della missione) superava i 600 s e il task moriva su "Read timed out"
# (misurato il 2026-10-08: 3120 token generati e ancora incompleti a 600 s).
INFERENCE_TIMEOUT_REASONING_S = int(os.getenv("INFERENCE_TIMEOUT_REASONING_S", "1200"))
FALLBACK_MIN_ATTEMPT_S        = int(os.getenv("FALLBACK_MIN_ATTEMPT_S", "60"))
# Il budget TOTALE deve poter contenere almeno un tentativo lungo piu' un
# ripiego, altrimenti il primo tentativo lo sfora e il messaggio di errore
# diventa incoerente ("budget di 300s esaurito dopo 600s", osservato in test).
# Il controllo della deadline avviene FRA gli stadi, non dentro un tentativo:
# un default piu' corto del timeout reasoning non e' un budget piu' severo, e'
# solo un budget che non puo' essere rispettato.
REQUEST_DEADLINE_S = max(
    int(os.getenv("REQUEST_DEADLINE_S", "0") or 0),
    INFERENCE_TIMEOUT_REASONING_S + FALLBACK_MIN_ATTEMPT_S,
)

# Modelli che ragionano: il testo puo' arrivare dopo molti token di thinking.
# Override da env REASONING_MODELS (lista separata da virgole, "*" = tutti):
# stessa semantica di TOOL_CAPABLE_MODELS, cosi' un modello nuovo non richiede
# una patch. deepseek-v4/glm-5/qwen3.8 sono gli alias che usa ds4.
_REASONING_OVERRIDE = os.getenv("REASONING_MODELS", "")
_REASONING_PATTERNS = ["qwen3", "deepseek-r1", "deepseek-v4", "deepseek-r1-pro",
                       "magistral", "glm-5", "qwen3.8"]

def _is_reasoning_model(model_name: str) -> bool:
    override = _REASONING_OVERRIDE.strip()
    if override == "*":
        return True
    if override:
        return any(p.strip().lower() and p.strip().lower() in str(model_name).lower()
                   for p in override.split(","))
    m = str(model_name or "").lower().split(":")[0]
    return any(p in m for p in _REASONING_PATTERNS)

def _inference_timeout(model_name: str) -> int:
    """Secondi concessi a UN tentativo di inferenza, in base al modello."""
    seconds = INFERENCE_TIMEOUT_REASONING_S if _is_reasoning_model(model_name) \
        else INFERENCE_TIMEOUT_S
    return max(10, int(seconds))

class RequestDeadline:
    """Budget totale condiviso da tutta la catena di fallback di una richiesta.

    Il clock e' iniettabile perche' la logica sia testabile senza attese reali.
    """

    def __init__(self, total_s: int = None, clock=time.time):
        self.clock = clock
        self.total_s = max(10, int(REQUEST_DEADLINE_S if total_s is None else total_s))
        self.started_at = clock()
        self.deadline = self.started_at + self.total_s

    def remaining(self) -> float:
        return self.deadline - self.clock()

    def allows(self, min_s: int = None) -> bool:
        """True se resta abbastanza budget perche' un altro tentativo abbia
        senso: sotto la soglia si fallisce subito, invece di sprecare il tempo
        residuo in un tentativo che non potra' completare."""
        threshold = FALLBACK_MIN_ATTEMPT_S if min_s is None else min_s
        return self.remaining() >= max(1, int(threshold))

    def elapsed(self) -> float:
        return self.clock() - self.started_at

def _is_error_payload(payload) -> bool:
    """True se la risposta e' un errore travestito da risposta.

    `_run_tool_loop` e i fallback restituiscono `{"error": {...}}` invece di
    sollevare un'eccezione: senza questo controllo il task veniva marcato `done`
    e il client riceveva HTTP 200 con un corpo d'errore — un fallimento
    indistinguibile da un successo se non leggendo il corpo (osservato in
    sessione di test: due timeout da 180s chiusi come "done").
    """
    return isinstance(payload, dict) and bool(payload.get("error"))

def _respond_result(result_json, status_error: int = 502):
    """Risposta HTTP coerente col payload: un errore non esce come 200."""
    if _is_error_payload(result_json):
        return jsonify(result_json), status_error
    return jsonify(result_json)


# ── SMART ECONOMIC FALLBACK ("Mesh-First, API-Second" + tetto giornaliero) ────
# Regola di sostenibilita' economica:
# 1. Priorita' assoluta ai nodi GPU della Mesh (Mac/PC locali, nodi Bridge Chrome,
#    federazione) a costo zero (€0.00).
# 2. Se tutti i nodi Mesh sono occupati o offline, il fallback verso provider API
#    esterni low-cost (OmniRoute / OpenRouter / DeepSeek / Qwen) e' protetto da un
#    tetto giornaliero rigido in Euro e in numero di chiamate, cosi' l'operatore
#    non riceve mai sorprese in fattura.

EXTERNAL_FALLBACK_DAILY_EUR_CAP          = float(os.getenv("EXTERNAL_FALLBACK_DAILY_EUR_CAP", "0.50"))
EXTERNAL_FALLBACK_DAILY_CALLS_CAP        = int(os.getenv("EXTERNAL_FALLBACK_DAILY_CALLS_CAP", "500"))
EXTERNAL_FALLBACK_COST_PER_1M_INPUT_EUR  = float(os.getenv("EXTERNAL_FALLBACK_COST_PER_1M_INPUT_EUR", "0.14"))
EXTERNAL_FALLBACK_COST_PER_1M_OUTPUT_EUR = float(os.getenv("EXTERNAL_FALLBACK_COST_PER_1M_OUTPUT_EUR", "0.28"))


def _estimate_usage_tokens(data: dict = None, response: dict = None) -> tuple[int, int]:
    """Estrae (prompt_tokens, completion_tokens) dal campo `usage` OpenAI oppure
    li stima dalla lunghezza del testo (~4 caratteri per token)."""
    if isinstance(response, dict):
        usage = response.get("usage")
        if isinstance(usage, dict):
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
            if pt > 0 or ct > 0:
                return max(1, pt), max(1, ct)

    prompt_chars = 0
    if isinstance(data, dict):
        for m in (data.get("messages") or []):
            if isinstance(m, dict):
                c = m.get("content", "")
                prompt_chars += len(c) if isinstance(c, str) else len(str(c))
    elif isinstance(data, str):
        prompt_chars = len(data)

    completion_chars = 0
    if isinstance(response, dict):
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content") or ""
            completion_chars = len(str(content))
        except Exception:
            completion_chars = 120

    return max(1, prompt_chars // 4 or 64), max(1, completion_chars // 4 or 64)


class ExternalFallbackBudget:
    """Contabilita' e hard-cap giornaliero per il fallback su API esterne.

    - Si azzera automaticamente al cambio di giorno UTC (`YYYY-MM-DD`).
    - Tiene traccia sia della spesa API reale/stimata (`spent_eur_today`), sia del
      risparmio generato dai nodi gratuiti della Mesh (`saved_eur_today` e
      `mesh_served_today`).
    - Il clock e' iniettabile per test deterministici senza attese.
    """

    def __init__(
        self,
        daily_eur_cap: float = None,
        daily_calls_cap: int = None,
        cost_per_1m_input_eur: float = None,
        cost_per_1m_output_eur: float = None,
        clock=time.time,
    ):
        self._lock = threading.Lock()
        self.clock = clock
        self._explicit_eur_cap = daily_eur_cap
        self._explicit_calls_cap = daily_calls_cap
        self._explicit_in_cost = cost_per_1m_input_eur
        self._explicit_out_cost = cost_per_1m_output_eur
        self._day = self._current_day()
        self._reset_counters(self._day)

    def _current_day(self) -> str:
        return datetime.fromtimestamp(self.clock(), tz=timezone.utc).strftime("%Y-%m-%d")

    def _reset_counters(self, day: str) -> None:
        self._day = day
        self.calls_today = 0
        self.blocked_today = 0
        self.prompt_tokens_today = 0
        self.completion_tokens_today = 0
        self.spent_eur_today = 0.0
        self.mesh_served_today = 0
        self.mesh_prompt_tokens_today = 0
        self.mesh_completion_tokens_today = 0
        self.saved_eur_today = 0.0

    def _ensure_day_unlocked(self) -> None:
        today = self._current_day()
        if today != self._day:
            self._reset_counters(today)

    @property
    def daily_eur_cap(self) -> float:
        if self._explicit_eur_cap is not None:
            return max(0.0, float(self._explicit_eur_cap))
        try:
            return max(0.0, float(os.getenv("EXTERNAL_FALLBACK_DAILY_EUR_CAP", str(EXTERNAL_FALLBACK_DAILY_EUR_CAP))))
        except (TypeError, ValueError):
            return 0.50

    @property
    def daily_calls_cap(self) -> int:
        if self._explicit_calls_cap is not None:
            return max(0, int(self._explicit_calls_cap))
        try:
            return max(0, int(os.getenv("EXTERNAL_FALLBACK_DAILY_CALLS_CAP", str(EXTERNAL_FALLBACK_DAILY_CALLS_CAP))))
        except (TypeError, ValueError):
            return 500

    @property
    def cost_per_1m_input_eur(self) -> float:
        if self._explicit_in_cost is not None:
            return max(0.0, float(self._explicit_in_cost))
        try:
            return max(0.0, float(os.getenv("EXTERNAL_FALLBACK_COST_PER_1M_INPUT_EUR", str(EXTERNAL_FALLBACK_COST_PER_1M_INPUT_EUR))))
        except (TypeError, ValueError):
            return 0.14

    @property
    def cost_per_1m_output_eur(self) -> float:
        if self._explicit_out_cost is not None:
            return max(0.0, float(self._explicit_out_cost))
        try:
            return max(0.0, float(os.getenv("EXTERNAL_FALLBACK_COST_PER_1M_OUTPUT_EUR", str(EXTERNAL_FALLBACK_COST_PER_1M_OUTPUT_EUR))))
        except (TypeError, ValueError):
            return 0.28

    def calculate_cost_eur(self, prompt_tokens: int, completion_tokens: int) -> float:
        pt = max(0, int(prompt_tokens or 0))
        ct = max(0, int(completion_tokens or 0))
        return (pt / 1_000_000.0) * self.cost_per_1m_input_eur + (ct / 1_000_000.0) * self.cost_per_1m_output_eur

    def allows(self) -> tuple[bool, str]:
        """Verifica se il budget giornaliero consente una chiamata di fallback esterno."""
        with self._lock:
            self._ensure_day_unlocked()
            eur_cap = self.daily_eur_cap
            calls_cap = self.daily_calls_cap
            if eur_cap <= 0.0 or calls_cap <= 0:
                self.blocked_today += 1
                return False, "tetto giornaliero fallback esterno impostato a zero (modalita' 100% Mesh gratuita)"
            if self.calls_today >= calls_cap:
                self.blocked_today += 1
                return False, f"tetto giornaliero chiamate fallback raggiunto ({self.calls_today}/{calls_cap})"
            if self.spent_eur_today >= eur_cap:
                self.blocked_today += 1
                return False, f"tetto giornaliero budget fallback raggiunto ({self.spent_eur_today:.4f}/{eur_cap:.2f} EUR)"
            return True, "ok"

    def record_external_call(self, prompt_tokens: int = 0, completion_tokens: int = 0, cost_eur: float = None) -> dict:
        """Registra una chiamata completata dal provider API di fallback esterno."""
        with self._lock:
            self._ensure_day_unlocked()
            pt = max(0, int(prompt_tokens or 0))
            ct = max(0, int(completion_tokens or 0))
            cost = float(cost_eur) if cost_eur is not None else self.calculate_cost_eur(pt, ct)
            self.calls_today += 1
            self.prompt_tokens_today += pt
            self.completion_tokens_today += ct
            self.spent_eur_today = round(self.spent_eur_today + max(0.0, cost), 6)
            return self._status_unlocked()

    def record_mesh_call(self, prompt_tokens: int = 0, completion_tokens: int = 0) -> dict:
        """Registra una richiesta servita gratuitamente dai nodi della Mesh / GPU locale."""
        with self._lock:
            self._ensure_day_unlocked()
            pt = max(0, int(prompt_tokens or 0))
            ct = max(0, int(completion_tokens or 0))
            avoided_cost = self.calculate_cost_eur(pt, ct)
            self.mesh_served_today += 1
            self.mesh_prompt_tokens_today += pt
            self.mesh_completion_tokens_today += ct
            self.saved_eur_today = round(self.saved_eur_today + max(0.0, avoided_cost), 6)
            return self._status_unlocked()

    def _status_unlocked(self) -> dict:
        eur_cap = self.daily_eur_cap
        calls_cap = self.daily_calls_cap
        rem_eur = max(0.0, round(eur_cap - self.spent_eur_today, 6))
        rem_calls = max(0, calls_cap - self.calls_today)
        usage_pct = round(min(100.0, (self.spent_eur_today / eur_cap) * 100.0), 2) if eur_cap > 0 else 100.0
        total_served = self.mesh_served_today + self.calls_today
        mesh_offload_pct = round((self.mesh_served_today / total_served) * 100.0, 2) if total_served > 0 else 100.0
        cap_reached = (eur_cap <= 0.0 or calls_cap <= 0
                       or self.spent_eur_today >= eur_cap
                       or self.calls_today >= calls_cap)
        return {
            "day": self._day,
            "policy": "mesh_first_api_second",
            "daily_eur_cap": round(eur_cap, 4),
            "daily_calls_cap": calls_cap,
            "spent_eur_today": round(self.spent_eur_today, 6),
            "remaining_eur_today": rem_eur,
            "usage_pct": usage_pct,
            "calls_today": self.calls_today,
            "remaining_calls_today": rem_calls,
            "blocked_today": self.blocked_today,
            "prompt_tokens_today": self.prompt_tokens_today,
            "completion_tokens_today": self.completion_tokens_today,
            "mesh_served_today": self.mesh_served_today,
            "saved_eur_today": round(self.saved_eur_today, 6),
            "mesh_offload_pct": mesh_offload_pct,
            "cap_reached": cap_reached,
        }

    def status(self) -> dict:
        with self._lock:
            self._ensure_day_unlocked()
            return self._status_unlocked()


EXTERNAL_FALLBACK_BUDGET = ExternalFallbackBudget()


def check_external_fallback_budget() -> tuple[bool, str]:
    """Controlla se il tetto giornaliero permette una chiamata al fallback esterno."""
    return EXTERNAL_FALLBACK_BUDGET.allows()


def record_external_fallback_usage(data: dict = None, response: dict = None) -> dict:
    """Contabilizza i token e il costo in Euro di una risposta ottenuta dal fallback esterno."""
    pt, ct = _estimate_usage_tokens(data, response)
    return EXTERNAL_FALLBACK_BUDGET.record_external_call(pt, ct)


def record_mesh_completion(prompt_or_data=None, response: dict = None) -> dict:
    """Contabilizza una risposta servita a costo zero dalla Mesh o da Ollama locale."""
    pt, ct = _estimate_usage_tokens(prompt_or_data, response)
    return EXTERNAL_FALLBACK_BUDGET.record_mesh_call(pt, ct)

