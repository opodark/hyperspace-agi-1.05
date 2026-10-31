# SPDX-License-Identifier: Apache-2.0
"""Regressione: /metrics/summary mostrava `avg_tokens_per_sec` implausibili
(es. 39228 tok/s per gemma4:e4b, 8245 tok/s globale — vedi AGENT-LOG.md
2026-10-31). Causa: la media era quella delle velocità per-richiesta, non
pesata; un campione con pochi token e durata vicina a zero (arrotondamento,
cache) genera un tps enorme e fisicamente valido ma che da solo sposta la
media aritmetica su pochi campioni. Ora si pesa per token/tempo totali, e i
campioni sotto 50ms di durata non contribuiscono (troppo rumorosi).

Stesso schema di estrazione via AST + exec di test_image_generate_route.py.
"""
import ast

from tests import cp_source


def _riga(model, tok_out, duration_ms, tok_in=10):
    detail = {"model": model, "tokens_in": tok_in, "tokens_out": tok_out,
              "duration_ms": duration_ms}
    return {"detail": __import__("json").dumps(detail)}


def chiama(rows, limit=300):
    import json as _json
    fn = cp_source.funzioni()['metrics_summary']
    fn.decorator_list = []
    scope = {
        "json": _json,
        "request": type("R", (), {"args": {"limit": str(limit)}})(),
        "db": type("DB", (), {"query_logs": staticmethod(lambda **kw: rows)})(),
        "jsonify": lambda x: x,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'cp', 'exec'), scope)
    return scope['metrics_summary']()


def test_near_zero_duration_outlier_does_not_blow_up_the_average():
    rows = [
        _riga("gemma4:e4b", tok_out=1, duration_ms=0),   # campione degenere: scartato
        _riga("gemma4:e4b", tok_out=100, duration_ms=5000),  # 20 tok/s reali
        _riga("gemma4:e4b", tok_out=100, duration_ms=5000),  # 20 tok/s reali
    ]
    result = chiama(rows)
    assert result["avg_tokens_per_sec"] == 20.0
    assert result["models"][0]["avg_tokens_per_sec"] == 20.0


def test_no_valid_samples_yields_none_not_zero_division():
    rows = [_riga("m", tok_out=1, duration_ms=0)]
    result = chiama(rows)
    assert result["avg_tokens_per_sec"] is None


def test_requests_and_token_totals_still_count_discarded_samples():
    rows = [
        _riga("m", tok_out=1, duration_ms=0),
        _riga("m", tok_out=50, duration_ms=2000),
    ]
    result = chiama(rows)
    assert result["requests"] == 2
    assert result["tokens_out"] == 51
