# SPDX-License-Identifier: Apache-2.0
"""Vista pubblica della topologia della mesh, per la landing del web node.

La pagina pubblica vuole disegnare i nodi che sono DAVVERO accesi, non tre
orbite di repertorio. Il registro del mesh pero' contiene endpoint interni,
indirizzi Tailscale, node_id completi e le etichette scelte dai visitatori:
nessuna di queste cose deve uscire su una rotta anonima.

Qui c'e' solo la proiezione, senza Flask e senza stato, cosi' si testa con dei
dizionari: il chiamante (cp/webnode.py) le passa il registro gia' letto.

Cosa esce:
- le macchine attive e chiamabili (le stesse che il routing considera), con
  un'etichetta pubblica: l'alias dell'operatore se e' "pulito", altrimenti un
  hash corto e stabile del node_id;
- i modelli che ognuna serve davvero (gli stessi nomi gia' pubblici su
  /v1/models), il carico e la VRAM arrotondati;
- i browser collegati solo come CONTEGGIO e capability aggregate.

Cosa non esce mai: endpoint, public_endpoint, node_id, IP, user agent,
etichette dei browser.
"""
from __future__ import annotations

import calendar
import hashlib
import re
import time

_SAFE_ALIAS = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_MODELS_PER_MACHINE = 24
MAX_MODELS_TOTAL = 60


def _public_label(node_id: str, alias: str) -> str:
    alias = str(alias or "").strip()
    if alias and _SAFE_ALIAS.match(alias):
        return alias
    digest = hashlib.sha256(str(node_id).encode("utf-8")).hexdigest()[:4]
    return f"nodo-{digest}"


def _ratio(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(min(1.0, max(0.0, number)), 2)


def _vram(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number) if number > 0 else None


def _age_s(last_seen, now: float):
    """Secondi dall'ultimo contatto. Accetta epoch o ISO-8601 'Z'."""
    if last_seen in (None, ""):
        return None
    if isinstance(last_seen, (int, float)):
        return max(0, int(now - float(last_seen)))
    try:
        parsed = time.strptime(str(last_seen), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return max(0, int(now - calendar.timegm(parsed)))


def public_topology(mesh_nodes, per_node_models, browser_nodes, *,
                    callable_ids, aliases=None, hub_models=None, now=None) -> dict:
    """Proietta il registro in una vista pubblica e sanificata.

    mesh_nodes:      dict del registro del mesh (_node_list()).
    per_node_models: voci 'per_node' di _aggregate_mesh_models().
    browser_nodes:   record del WebNodeRegistry, gia' ripuliti dai nodi scaduti.
    callable_ids:    node_id che il CP puo' chiamare (_best_endpoint non vuoto).
    hub_models:      modelli serviti direttamente dal CP (inferenza diretta,
                     senza un worker del mesh dietro).
    """
    moment = time.time() if now is None else now
    aliases = aliases or {}
    callable_ids = set(callable_ids or ())

    models_by_node: dict[str, set] = {}
    for entry in per_node_models or ():
        nid = entry.get("node_id")
        base = str(entry.get("base_model") or "").strip()
        if nid and base:
            models_by_node.setdefault(nid, set()).add(base)

    machines = []
    for node in mesh_nodes or ():
        nid = str(node.get("node_id") or "")
        if not nid or node.get("status") != "active" or nid not in callable_ids:
            continue
        if node.get("is_web_node"):
            continue
        models = sorted(models_by_node.get(nid, ()))
        machines.append({
            "label": _public_label(nid, aliases.get(nid) or node.get("alias", "")),
            "tier": str(node.get("tier") or "leaf")[:16],
            "models": models[:MAX_MODELS_PER_MACHINE],
            "model_count": len(models),
            "load": _ratio(node.get("saturation")),
            "active_requests": max(0, int(node.get("active_requests") or 0)),
            "vram_gb": _vram(node.get("vram_gb")),
            "last_seen_s": _age_s(node.get("last_seen"), moment),
        })
    machines.sort(key=lambda m: (-m["model_count"], m["label"]))

    served = {m for m_obj in machines for m in m_obj["models"]}
    direct = sorted({str(m).strip() for m in (hub_models or ()) if str(m).strip()} - served)

    browsers = list(browser_nodes or ())
    capabilities = sorted({c for b in browsers for c in (b.get("capabilities") or [])})

    all_models = sorted(served | set(direct))
    return {
        "ok": True,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(moment)),
        "hub": {
            "label": "Control Plane",
            "online": True,
            "models": direct[:MAX_MODELS_PER_MACHINE],
            "model_count": len(direct),
        },
        "machines": machines,
        "browsers": {"count": len(browsers), "capabilities": capabilities},
        "models": all_models[:MAX_MODELS_TOTAL],
        "totals": {
            "machines": len(machines),
            "models": len(all_models),
            "browsers": len(browsers),
        },
    }
