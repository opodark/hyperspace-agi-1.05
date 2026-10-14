# SPDX-License-Identifier: Apache-2.0
"""Client interoperabile e fail-safe per il motore decisionale Laya (System 1).

Fornisce decisioni tipizzate non-autoregressive (choice, score, noul) in singola
forward pass (sub-50ms), con confidenza calibrata e supporto a oltre 100 lingue.
Se il servizio Laya non è raggiungibile o è disabilitato, tutti i metodi
restituiscono None o valori di fallback deterministici senza sollevare eccezioni,
permettendo a HyperSpace di scalare fluidamente su System 2 (LLM autoregressivo).
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("hyperspace.laya")

LAYA_DEFAULT_URL = "http://127.0.0.1:8097"
LAYA_URL = os.getenv("LAYA_URL", LAYA_DEFAULT_URL).rstrip("/")
LAYA_ENABLED = os.getenv("LAYA_ENABLED", "true").lower() in ("true", "1", "yes", "on")
LAYA_TIMEOUT_S = float(os.getenv("LAYA_TIMEOUT_S", "2.0"))


def is_available(url: Optional[str] = None, timeout: Optional[float] = None) -> bool:
    """Verifica se il servizio Laya è attivo e risponde sull'endpoint di salute."""
    if not LAYA_ENABLED:
        return False
    base_url = (url or LAYA_URL).rstrip("/")
    timeout_s = timeout or min(1.0, LAYA_TIMEOUT_S)
    req = urllib.request.Request(f"{base_url}/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.status == 200
    except Exception:
        # Molti server FastAPI espongono /models o / docs anziché /health
        try:
            req_models = urllib.request.Request(f"{base_url}/models", method="GET")
            with urllib.request.urlopen(req_models, timeout=timeout_s) as resp:
                return resp.status == 200
        except Exception:
            return False


def predict(
    state: Union[str, Dict[str, Any], List[Any]],
    questions: Dict[str, Any],
    *,
    model: Optional[str] = None,
    lang: Optional[str] = None,
    lang_guess: Optional[str] = None,
    min_confidence: Optional[float] = None,
    max_len: Optional[int] = None,
    head_max_len: Optional[int] = None,
    url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Invia una richiesta decisionale a Laya (/predict) in singola forward pass.

    :param state: Testo grezzo, dizionario di stato o documento JSON
    :param questions: Mappa di domande tipizzate ('choice', 'score', 'noul')
    :return: Risultato strutturato con answers e routing, oppure None se offline
    """
    if not LAYA_ENABLED:
        return None

    base_url = (url or LAYA_URL).rstrip("/")
    timeout_s = timeout or LAYA_TIMEOUT_S

    payload: Dict[str, Any] = {
        "state": {"body": state} if isinstance(state, str) else state,
        "questions": questions,
    }
    if model:
        payload["model"] = model
    if lang:
        payload["lang"] = lang
    if lang_guess:
        payload["lang_guess"] = lang_guess
    if min_confidence is not None:
        payload["min_confidence"] = float(min_confidence)
    if max_len is not None:
        payload["max_len"] = int(max_len)
    if head_max_len is not None:
        payload["head_max_len"] = int(head_max_len)

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for endpoint in ("/v1/systemone", "/predict"):
        req = urllib.request.Request(
            f"{base_url}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
        except urllib.error.HTTPError as http_err:
            if http_err.code == 404 and endpoint == "/v1/systemone":
                continue
            logger.debug("Laya predict HTTP error (%s%s): %s", base_url, endpoint, http_err)
            return None
        except Exception as exc:
            logger.debug("Laya predict unreachable or failed (%s): %s", base_url, exc)
            return None
    return None


def predict_batch(
    requests_batch: List[Dict[str, Any]],
    *,
    batch_size: Optional[int] = None,
    sort_by_length: bool = True,
    url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Invia un batch eterogeneo a Laya (/v1/systemone/batch o /predict/batch)."""
    if not LAYA_ENABLED or not requests_batch:
        return None

    base_url = (url or LAYA_URL).rstrip("/")
    timeout_s = timeout or (LAYA_TIMEOUT_S * max(2, len(requests_batch) // 4))

    payload: Dict[str, Any] = {
        "requests": requests_batch,
        "sort_by_length": sort_by_length,
    }
    if batch_size:
        payload["batch_size"] = batch_size

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for endpoint in ("/v1/systemone/batch", "/predict/batch"):
        req = urllib.request.Request(
            f"{base_url}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
        except urllib.error.HTTPError as http_err:
            if http_err.code == 404 and endpoint == "/v1/systemone/batch":
                continue
            logger.debug("Laya predict_batch HTTP error (%s%s): %s", base_url, endpoint, http_err)
            return None
        except Exception as exc:
            logger.debug("Laya predict_batch failed: %s", exc)
            return None
    return None


def decide_choice(
    text_or_state: Union[str, Dict[str, Any]],
    choices: Dict[str, str],
    instructions: str,
    *,
    min_confidence: float = 0.5,
    model: Optional[str] = None,
    question_id: str = "decision",
) -> Optional[Dict[str, Any]]:
    """Valuta una scelta categorica (choice) con criteri semantici per opzione.

    Ritorna un dizionario con:
      - choice: l'etichetta selezionata (es. 'pass', 'coder', 'security')
      - confidence: confidenza calibrata [0.0, 1.0]
      - probabilities: distribuzione di probabilità su tutte le opzioni
      - abstention: True se la confidenza è sotto min_confidence
      - model_used: checkpoint usato da Laya (es. 'english', 'multilingual')
    """
    questions = {
        question_id: {
            "type": "choice",
            "instructions": instructions,
            "criteria": choices,
        }
    }
    res = predict(text_or_state, questions, model=model, min_confidence=min_confidence)
    if not res or "answers" not in res:
        return None

    ans = res["answers"].get(question_id, {})
    return {
        "choice": ans.get("choice"),
        "confidence": float(ans.get("confidence") or ans.get("x_jev_confidence") or 0.0),
        "probabilities": ans.get("probabilities", {}),
        "abstention": bool(ans.get("abstention", False)),
        "model_used": res.get("routing", {}).get("model", ""),
        "raw": ans,
    }


def decide_noul(
    text_or_state: Union[str, Dict[str, Any]],
    instructions: str,
    *,
    min_confidence: float = 0.5,
    model: Optional[str] = None,
    question_id: str = "is_true",
) -> Optional[Dict[str, Any]]:
    """Valuta un'affermazione booleana Sì/No (noul) con probabilità P(true) calibrata.

    Ritorna un dizionario con:
      - noul: float P(true) da 0.0 a 1.0
      - is_yes: booleano (P(true) >= 0.5)
      - confidence: livello di certezza rispetto a 0.5 (|noul - 0.5| * 2)
      - abstention: True se sotto soglia di astensione
      - model_used: checkpoint usato da Laya
    """
    questions = {
        question_id: {
            "type": "noul",
            "instructions": instructions,
        }
    }
    res = predict(text_or_state, questions, model=model, min_confidence=min_confidence)
    if not res or "answers" not in res:
        return None

    ans = res["answers"].get(question_id, {})
    p_true = float(ans.get("noul") if ans.get("noul") is not None else 0.5)
    conf = float(ans.get("confidence") or abs(p_true - 0.5) * 2.0)
    return {
        "noul": p_true,
        "is_yes": p_true >= 0.5,
        "confidence": conf,
        "abstention": bool(ans.get("abstention", False)),
        "model_used": res.get("routing", {}).get("model", ""),
        "raw": ans,
    }


def decide_score(
    text_or_state: Union[str, Dict[str, Any]],
    criteria: List[str],
    instructions: str,
    *,
    model: Optional[str] = None,
    question_id: str = "level",
) -> Optional[Dict[str, Any]]:
    """Valuta una scala ordinale (score) tra livelli ordinati (es. urgenza, rischio).

    Ritorna un dizionario con:
      - score: valore ordinale continuo stimato
      - level_index: indice intero arrotondato al livello più vicino
      - level_label: etichetta corrispondente
      - confidence: confidenza dell'ordinamento
    """
    questions = {
        question_id: {
            "type": "score",
            "instructions": instructions,
            "criteria": criteria,
        }
    }
    res = predict(text_or_state, questions, model=model)
    if not res or "answers" not in res:
        return None

    ans = res["answers"].get(question_id, {})
    score_val = float(ans.get("score") if ans.get("score") is not None else 0.0)
    idx = max(0, min(len(criteria) - 1, int(round(score_val))))
    return {
        "score": score_val,
        "level_index": idx,
        "level_label": criteria[idx] if criteria else "",
        "confidence": float(ans.get("confidence") or 0.0),
        "raw": ans,
    }
