#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""hard_bench.py — problemi procedurali a difficolta' regolabile, verificati da codice.

Perche' esiste: i benchmark pubblici si saturano (i modelli di frontiera sono al 95%+)
e finiscono nei dati di addestramento. Qui i problemi si GENERANO da un seed, con
cinque livelli di difficolta', e la risposta la controlla una funzione, non un modello
e non una persona. Il risultato e' una curva accuratezza-contro-difficolta' per ogni
modello: si vede DOVE ciascuno smette di farcela, invece di un solo numero.

Regole di onesta':
  - I generatori e i seed sono fissati PRIMA di misurare e pubblicati; nessuno sceglie i
    problemi dopo aver visto chi li sbaglia (altrimenti si pesa il confronto contro chi
    li ha scelti). Il livello 5 puo' essere fuori portata per tutti: e' un tetto, non un
    difetto.
  - Si misura senza strumenti (niente codice, niente calcolatrice): e' un test di
    ragionamento del modello, e va dichiarato. Con strumenti, quasi tutto qui diventa banale.
  - Gli elementi si salvano in JSONL con la risposta attesa o i dati del verificatore, cosi'
    un terzo controlla senza rigenerare.

Famiglie: arith (moltiplicazione esatta), trace (output di un programma), perm (stato dopo
molti scambi), coloring (colorazione di grafo con soluzione piantata, qualunque soluzione
valida e' accettata), chain (ricerca a piu' salti fra molte righe distrattive).

Uso:
    python3 scripts/hard_bench.py gen --out benchmarks/public/hard/items.jsonl --per-level 10
    python3 scripts/hard_bench.py run --items ... --name hs --api openai \
        --base-url http://100.104.238.125:8085/v1/chat/completions --model flint:latest \
        --header X-Hyperspace-Tools:off --extra '{"surface":"workbench"}' --out runs/hs.jsonl
    python3 scripts/hard_bench.py run ... --api anthropic --model claude-sonnet-5-5 --key-env ANTHROPIC_API_KEY
    python3 scripts/hard_bench.py report --runs runs/hs.jsonl runs/claude.jsonl

Solo libreria standard. Le chiavi si leggono da variabili d'ambiente (--key-env), mai salvate.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

LEVELS = (1, 2, 3, 4, 5)
FAMILIES = ("arith", "trace", "perm", "coloring", "chain")
SUFFIX = "\n\nYou may reason step by step. Finish with one last line of the form `ANSWER: <answer>`."


# ---------------------------------------------------------------------------
# Generatori: (rng, livello) -> (prompt, dati_verifica)
# ---------------------------------------------------------------------------

def gen_arith(rng: random.Random, level: int) -> Tuple[str, Dict[str, Any]]:
    digits = {1: 3, 2: 6, 3: 10, 4: 16, 5: 24}[level]
    a = rng.randrange(10 ** (digits - 1), 10 ** digits)
    b = rng.randrange(10 ** (digits - 1), 10 ** digits)
    return (f"Compute {a} * {b} exactly (an integer, no rounding, no separators)." + SUFFIX,
            {"expected": str(a * b)})


def gen_trace(rng: random.Random, level: int) -> Tuple[str, Dict[str, Any]]:
    steps = {1: 4, 2: 8, 3: 16, 4: 32, 5: 64}[level]
    state = {"a": rng.randrange(1, 100), "b": rng.randrange(1, 100), "c": rng.randrange(1, 100)}
    lines = [f"a, b, c = {state['a']}, {state['b']}, {state['c']}"]
    names = "abc"
    for _ in range(steps):
        x, y = rng.sample(names, 2)
        k, m = rng.randrange(2, 9), rng.choice([97, 101, 211, 997])
        kind = rng.randrange(3)
        if kind == 0:
            lines.append(f"{x} = ({x} * {k} + {y}) % {m}")
        elif kind == 1:
            lines.append(f"if {y} % 2 == 0:\n    {x} = ({x} + {k}) % {m}\nelse:\n    {x} = ({x} * {k}) % {m}")
        else:
            n = rng.randrange(2, 5)
            lines.append(f"for i in range({n}):\n    {x} = ({x} + i * {y}) % {m}")
    code = "\n".join(lines)
    scope: Dict[str, Any] = {}
    exec(code, {}, scope)  # codice generato da noi, mai input esterno
    expected = f"{scope['a']} {scope['b']} {scope['c']}"
    return ("What does this Python program print when it finishes with `print(a, b, c)`? "
            "Answer with the three integers separated by single spaces.\n\n```python\n"
            + code + "\n```" + SUFFIX, {"expected": expected})


def gen_perm(rng: random.Random, level: int) -> Tuple[str, Dict[str, Any]]:
    n, swaps = {1: (5, 6), 2: (8, 15), 3: (10, 30), 4: (12, 60), 5: (15, 120)}[level]
    items = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:n])
    state = items[:]
    ops = []
    for _ in range(swaps):
        i, j = rng.sample(range(n), 2)
        state[i], state[j] = state[j], state[i]
        ops.append(f"swap positions {i + 1} and {j + 1}")
    return (f"A row of {n} letters starts as: {' '.join(items)} (positions are numbered from 1). "
            "Apply these operations in order:\n" + "\n".join(f"{k + 1}. {o}" for k, o in enumerate(ops))
            + "\n\nGive the final row as letters separated by single spaces." + SUFFIX,
            {"expected": " ".join(state)})


def gen_coloring(rng: random.Random, level: int) -> Tuple[str, Dict[str, Any]]:
    n = {1: 8, 2: 14, 3: 22, 4: 32, 5: 45}[level]
    planted = [rng.randrange(3) for _ in range(n)]
    edges = set()
    possible = sum(1 for u in range(n) for v in range(u + 1, n) if planted[u] != planted[v])
    target = min(int(2.4 * n), possible)  # con colori sbilanciati gli archi possibili sono pochi
    while len(edges) < target:
        u, v = rng.sample(range(n), 2)
        if planted[u] != planted[v]:
            edges.add((min(u, v), max(u, v)))
    edges_l = sorted(edges)
    text = ", ".join(f"{u}-{v}" for u, v in edges_l)
    return (f"A graph has nodes 0..{n - 1} and these edges: {text}.\n"
            f"Color every node with R, G or B so that no edge joins two nodes of the same color. "
            f"Any valid coloring is accepted. Give {n} letters separated by single spaces, "
            "for node 0 first." + SUFFIX, {"n": n, "edges": edges_l})


def gen_chain(rng: random.Random, level: int) -> Tuple[str, Dict[str, Any]]:
    total, hops = {1: (20, 3), 2: (60, 5), 3: (150, 8), 4: (300, 12), 5: (600, 16)}[level]
    names = [f"v{i}" for i in range(total + hops + 1)]
    rng.shuffle(names)
    chain, rest = names[:hops + 1], names[hops + 1:]
    value = rng.randrange(1000, 10000)
    lines = [f"{chain[-1]} = {value}"] + [f"{chain[k]} = {chain[k + 1]}" for k in range(hops)]
    for nm in rest[:total - len(lines)]:  # distrattori: puntano a variabili con altri valori
        lines.append(f"{nm} = {rng.choice(rest)}" if rng.random() < 0.5 else f"{nm} = {rng.randrange(1000, 10000)}")
    rng.shuffle(lines)
    return ("Each line below assigns either a number or another variable. "
            f"What number does {chain[0]} end up equal to?\n\n" + "\n".join(lines) + SUFFIX,
            {"expected": str(value)})


GENERATORS: Dict[str, Callable[[random.Random, int], Tuple[str, Dict[str, Any]]]] = {
    "arith": gen_arith, "trace": gen_trace, "perm": gen_perm, "coloring": gen_coloring, "chain": gen_chain,
}


def make_items(per_level: int, seed: int, families=FAMILIES) -> List[Dict[str, Any]]:
    items = []
    for fam in families:
        for level in LEVELS:
            for k in range(per_level):
                rng = random.Random(f"{seed}:{fam}:{level}:{k}")
                prompt, data = GENERATORS[fam](rng, level)
                items.append({"id": f"{fam}-L{level}-{k:02d}", "family": fam, "level": level,
                              "prompt": prompt, "data": data})
    return items


# ---------------------------------------------------------------------------
# Verifica
# ---------------------------------------------------------------------------

def extract_answer(text: str) -> Optional[str]:
    """Ultima riga `ANSWER: ...` (maiuscole/minuscole indifferenti). Niente risposta = errore."""
    found = re.findall(r"(?im)^\W*answer\s*:\s*(.+?)\s*$", text or "")
    if not found:
        return None
    return found[-1].strip().strip("`*").strip()


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[,\s]+", " ", s.replace(".", " ").replace("−", "-")).split()) \
        if not re.fullmatch(r"-?\d+", s.strip()) else s.strip()


def check(item: Dict[str, Any], response: str) -> bool:
    ans = extract_answer(response)
    if ans is None:
        return False
    fam, data = item["family"], item["data"]
    if fam == "coloring":
        colors = re.findall(r"[RGB]", ans.upper().replace("RED", "R").replace("GREEN", "G").replace("BLUE", "B"))
        if len(colors) != data["n"]:
            return False
        return all(colors[u] != colors[v] for u, v in data["edges"])
    if fam in ("arith", "chain"):
        return re.sub(r"[,\s]", "", ans) == data["expected"]
    return _norm(ans) == _norm(data["expected"])


# ---------------------------------------------------------------------------
# Esecuzione contro un endpoint
# ---------------------------------------------------------------------------

def call_model(api: str, base_url: str, model: str, prompt: str, key: Optional[str],
               headers: Dict[str, str], extra: Dict[str, Any], max_tokens: int, timeout: int) -> str:
    if api == "anthropic":
        url = base_url or "https://api.anthropic.com/v1/messages"
        body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}], **extra}
        hdr = {"x-api-key": key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}
    else:
        url = base_url
        body = {"model": model, "max_tokens": max_tokens, "temperature": 0,
                "messages": [{"role": "user", "content": prompt}], **extra}
        hdr = {"content-type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}
    hdr.update(headers)
    req = urllib.request.Request(url, json.dumps(body).encode(), hdr, method="POST")
    last: Exception = RuntimeError("nessun tentativo")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                j = json.load(r)
            if api == "anthropic":
                return "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
            return (j["choices"][0]["message"].get("content") or "")
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in (429, 500, 502, 503, 529):
                break
        except Exception as exc:
            last = exc
        time.sleep(min(60, 2 ** attempt * 3))
    raise RuntimeError(f"{type(last).__name__}: {str(last)[:120]}")


def cmd_gen(a: argparse.Namespace) -> int:
    items = make_items(a.per_level, a.seed)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} problemi in {a.out} (seed {a.seed}, {a.per_level} per famiglia e livello)")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    items = [json.loads(l) for l in open(a.items, encoding="utf-8")]
    if a.max_level:
        items = [i for i in items if i["level"] <= a.max_level]
    if a.limit:
        items = items[: a.limit]
    key = os.environ.get(a.key_env) if a.key_env else None
    if a.key_env and not key:
        print(f"variabile {a.key_env} non impostata", file=sys.stderr)
        return 1
    headers = dict(h.split(":", 1) for h in a.header)
    extra = json.loads(a.extra) if a.extra else {}

    def one(it: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        try:
            resp, err = call_model(a.api, a.base_url, a.model, it["prompt"], key, headers, extra,
                                   a.max_tokens, a.timeout), None
        except Exception as exc:
            resp, err = "", str(exc)
        return {"id": it["id"], "family": it["family"], "level": it["level"], "model": a.name,
                "correct": check(it, resp) if not err else False, "error": err,
                "response": resp, "seconds": round(time.time() - t0, 1)}

    with ThreadPoolExecutor(max_workers=a.workers) as pool, open(a.out, "w", encoding="utf-8") as fh:
        for r in pool.map(one, items):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
    print(f"{len(items)} risposte in {a.out}")
    return 0


def render_report(runs: Dict[str, List[Dict[str, Any]]]) -> str:
    L = ["# Curve accuratezza-contro-difficolta'", "",
         "Percentuale di risposte verificate corrette. Errori di rete/API contati a parte, "
         "non come risposte sbagliate.", ""]
    for fam in FAMILIES:
        L += [f"## {fam}", "", "| Modello | " + " | ".join(f"L{l}" for l in LEVELS) + " |",
              "|---|" + "---|" * len(LEVELS)]
        for name, rows in runs.items():
            cells = []
            for l in LEVELS:
                sel = [r for r in rows if r["family"] == fam and r["level"] == l]
                ok = [r for r in sel if not r.get("error")]
                err = len(sel) - len(ok)
                if not sel:
                    cells.append("-")
                else:
                    pct = 100 * sum(r["correct"] for r in ok) / len(ok) if ok else 0
                    cells.append(f"{pct:.0f}% ({len(ok)})" + (f" +{err} err" if err else ""))
            L.append(f"| {name} | " + " | ".join(cells) + " |")
        L.append("")
    return "\n".join(L)


def cmd_report(a: argparse.Namespace) -> int:
    runs: Dict[str, List[Dict[str, Any]]] = {}
    for path in a.runs:
        rows = [json.loads(l) for l in open(path, encoding="utf-8")]
        if rows:
            runs[rows[0]["model"]] = rows
    print(render_report(runs))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--out", required=True)
    g.add_argument("--per-level", type=int, default=10)
    g.add_argument("--seed", type=int, default=20261103)
    r = sub.add_parser("run")
    r.add_argument("--items", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--api", choices=("openai", "anthropic"), default="openai")
    r.add_argument("--base-url", default="")
    r.add_argument("--model", required=True)
    r.add_argument("--key-env", default="")
    r.add_argument("--header", action="append", default=[], help="Nome:valore (ripetibile)")
    r.add_argument("--extra", default="", help="JSON da aggiungere al corpo")
    r.add_argument("--max-tokens", type=int, default=4096)
    r.add_argument("--timeout", type=int, default=600)
    r.add_argument("--workers", type=int, default=1)
    r.add_argument("--max-level", type=int, default=0)
    r.add_argument("--limit", type=int, default=0)
    p = sub.add_parser("report")
    p.add_argument("--runs", nargs="+", required=True)
    a = ap.parse_args(argv)
    return {"gen": cmd_gen, "run": cmd_run, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
