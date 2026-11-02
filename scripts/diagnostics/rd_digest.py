#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Digest compatto dello stato R&D (promozioni, scarti, qualità della generazione, rete).

Sola lettura: legge data/research/*, data/nightly/node_stream.jsonl e lo stato del ciclo
notturno. Pensato per essere letto da un agente (o dal cockpit) al posto dei log: poche
decine di righe e una lista "attenzione" con le sole cose che richiedono un intervento.

Uso:
  python scripts/diagnostics/rd_digest.py            # testo
  python scripts/diagnostics/rd_digest.py --json     # JSON
  python scripts/diagnostics/rd_digest.py --hours 6
"""
from __future__ import annotations

import argparse
import collections
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

LAYA_NOTE_RE = re.compile(r"\[laya noul=([\d.]+) conf=([\d.]+) ([\d.]+)ms\]")

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "data" / "research"
NIGHTLY = ROOT / "data" / "nightly"

NET_PATTERNS = {
    "503_nodo_occupato": "503",
    "timeout": "timed out",
    "401_non_autorizzato": "401",
    "asus_non_risponde": "ASUS non ha risposto",
}


def _jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _ts(value: Any) -> float:
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def build_digest(hours: float = 24.0) -> Dict[str, Any]:
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    since = now - hours * 3600

    studies = [r for r in _jsonl(RESEARCH / "agi_deep_dives.jsonl") if _ts(r.get("timestamp")) >= since]
    gens = [r.get("generation") or {} for r in studies]
    with_tests = [g for g in gens if g.get("tests_passed") is not None]
    gen = {
        "studi": len(studies),
        "con_prototipo": sum(1 for r in studies if r.get("prototype_file")),
        "varianti_medie": round(sum(g.get("variants", 0) for g in gens) / len(gens), 2) if gens else 0,
        "test_passati": sum(1 for g in with_tests if g["tests_passed"]),
        "test_falliti": sum(1 for g in with_tests if not g["tests_passed"]),
        "test_generati_dal_modello_piccolo": sum(1 for g in gens if g.get("tests_generated")),
        "riparazioni": sum(g.get("repairs", 0) for g in gens),
    }

    promos = [r for r in _jsonl(RESEARCH / "promotions.jsonl") if _ts(r.get("timestamp")) >= since]
    promoted = [
        {"modulo": r.get("target_module"), "tier": (r.get("evidence") or {}).get("tier"), "autore": r.get("author")}
        for r in promos
    ]

    try:
        state = json.loads((RESEARCH / "auto_promotion_state.json").read_text(encoding="utf-8"))
    except Exception:
        state = {}
    reasons = collections.Counter(str(v).split(":")[0].split("(")[0].strip() for v in state.get("rejected", {}).values())

    net: collections.Counter = collections.Counter()
    # Capacità per nodo fisico (OMEN vs ASUS), misurata con Laya come sensore: ogni riga DEV
    # porta già il nodo che ha risposto (routed_via) e, quando Laya ha giudicato, la sua
    # confidenza e latenza — non serve un benchmark separato, basta aggregare il log.
    per_node: Dict[str, Dict[str, Any]] = collections.defaultdict(
        lambda: {"accettati": 0, "scartati_laya": 0, "senza_cot_o_ast": 0, "errori": 0,
                 "laya_confidenze": [], "laya_latenze_ms": []}
    )
    for r in _jsonl(NIGHTLY / "node_stream.jsonl"):
        if _ts(r.get("timestamp")) < since:
            continue
        msg = str(r.get("message", ""))
        for name, needle in NET_PATTERNS.items():
            if needle in msg:
                net[name] += 1
        if r.get("tag") != "DEV":
            continue
        node = r.get("node", "OMEN-16")
        slot = per_node[node]
        if msg.startswith("✓"):
            slot["accettati"] += 1
        elif msg.startswith("✗") and "triage Laya" in msg:
            slot["scartati_laya"] += 1
        elif msg.startswith("✗"):
            slot["errori"] += 1
        elif msg.startswith("○"):
            slot["senza_cot_o_ast"] += 1
        m = LAYA_NOTE_RE.search(msg)
        if m:
            slot["laya_confidenze"].append(float(m.group(2)))
            slot["laya_latenze_ms"].append(float(m.group(3)))

    capacita_nodi = {}
    for node, slot in per_node.items():
        confs, lats = slot.pop("laya_confidenze"), slot.pop("laya_latenze_ms")
        slot["laya_conf_media"] = round(sum(confs) / len(confs), 2) if confs else None
        slot["laya_latenza_media_ms"] = round(sum(lats) / len(lats), 1) if lats else None
        tot = slot["accettati"] + slot["scartati_laya"]
        slot["tasso_accettazione_laya"] = round(slot["accettati"] / tot, 2) if tot else None
        capacita_nodi[node] = slot

    try:
        cyc = json.loads((NIGHTLY / "omen_allnight_state.json").read_text(encoding="utf-8"))
        ciclo = {"id": cyc.get("cycle_id"), "stato": cyc.get("status"), "durata_s": cyc.get("total_elapsed_s"),
                 "fasi": list((cyc.get("phases") or {}).keys())}
    except Exception:
        ciclo = {}

    protos = list((RESEARCH / "prototypes").glob("proto_*.py"))
    nuovi = sum(1 for p in protos if p.stat().st_mtime >= since)

    attenzione: List[str] = []
    rolled = [p for p in promoted if p["tier"] != "verified"]
    if rolled:
        attenzione.append(f"{len(rolled)} promozioni non verified: controllare i test")
    if len(with_tests) >= 5 and gen["test_passati"] / len(with_tests) < 0.3:
        attenzione.append("meno del 30% degli studi supera i test: rivedere prompt/contratto di output")
    if net.get("401_non_autorizzato"):
        attenzione.append(f"{net['401_non_autorizzato']} errori 401 dall'OMEN: identità/firma del nodo")
    if net.get("503_nodo_occupato", 0) > 20:
        attenzione.append("molti 503: due runner attivi o nodo saturo")
    if gen["studi"] >= 10 and not promoted:
        attenzione.append(f"{gen['studi']} studi e nessuna promozione nelle ultime {hours:g} h")
    if gen["studi"] == 0:
        attenzione.append("nessuno studio nel periodo: demone fermo?")
    top = reasons.most_common(1)
    if top and top[0][1] > 100:
        attenzione.append(f"scarto dominante: '{top[0][0]}' ({top[0][1]} prototipi)")

    return {
        "finestra_ore": hours,
        "generazione": gen,
        "promossi": promoted,
        "prototipi": {"totali": len(protos), "nuovi": nuovi},
        "scarti_principali": reasons.most_common(5),
        "rete": dict(net),
        "capacita_nodi": capacita_nodi,
        "ultimo_ciclo": ciclo,
        "attenzione": attenzione,
    }


def render(d: Dict[str, Any]) -> str:
    g = d["generazione"]
    lines = [
        f"R&D digest (ultime {d['finestra_ore']:g} h)",
        f"- studi {g['studi']} (con prototipo {g['con_prototipo']}), varianti medie {g['varianti_medie']}, "
        f"test passati {g['test_passati']} / falliti {g['test_falliti']}, test scritti dal modello piccolo "
        f"{g['test_generati_dal_modello_piccolo']}, riparazioni {g['riparazioni']}",
        f"- prototipi: {d['prototipi']['totali']} totali, {d['prototipi']['nuovi']} nuovi",
        f"- promossi: {len(d['promossi'])}" + "".join(f"\n    {p['modulo']} [{p['tier']}] da {p['autore']}" for p in d["promossi"]),
        "- scarti: " + (", ".join(f"{k} ({v})" for k, v in d["scarti_principali"]) or "nessuno"),
        "- rete: " + (", ".join(f"{k}={v}" for k, v in d["rete"].items()) or "nessun errore"),
    ]
    if d.get("capacita_nodi"):
        lines.append("- capacità per nodo (Laya come sensore):")
        for node, c in d["capacita_nodi"].items():
            lines.append(
                f"    {node}: accettati {c['accettati']}, scartati-Laya {c['scartati_laya']}, "
                f"senza CoT/AST {c['senza_cot_o_ast']}, errori {c['errori']}, "
                f"tasso accettazione {c['tasso_accettazione_laya']}, "
                f"Laya conf. media {c['laya_conf_media']}, latenza media {c['laya_latenza_media_ms']} ms"
            )
    c = d["ultimo_ciclo"]
    if c:
        lines.append(f"- ultimo ciclo {c.get('id')} {c.get('stato')} in {c.get('durata_s')} s, fasi: {', '.join(c.get('fasi', []))}")
    lines.append("ATTENZIONE:" if d["attenzione"] else "Nessuna anomalia.")
    lines += [f"  ! {a}" for a in d["attenzione"]]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=24.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = build_digest(a.hours)
    print(json.dumps(d, indent=2, ensure_ascii=False) if a.json else render(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
