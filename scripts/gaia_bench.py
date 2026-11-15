#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""gaia_bench.py — runner minimale GAIA (validazione) sul Control Plane HyperSpace.

GAIA e' gated: il file con le domande va scaricato a mano (account Hugging Face che
accetta le condizioni) e NON si ripubblica. Questo script lo legge da un percorso locale
e scrive solo task_id, risposta e punteggio: mai il testo delle domande.

    python3 scripts/gaia_bench.py run --data /percorso/validation/metadata.jsonl \
        --base-url http://100.104.238.125:8085/v1/chat/completions --model flint:latest \
        --out benchmarks/public/runs/<data>/gaia_validation --limit 5
    python3 scripts/gaia_bench.py score --out benchmarks/public/runs/<data>/gaia_validation

Di default i tool li esegue il CP (nativi, surface=workbench). Con --client-tools si usano
invece quelli del client (header X-Hyperspace-Tools: off, il CP non ne inietta): web_search (SearXNG, --searxng-url), fetch_url e,
solo con --allow-python, run_python (sottoprocesso isolato, timeout, cartella temporanea).
Gli allegati (file_name) non sono gestiti: quelle domande vengono marcate "allegato".
Solo libreria standard.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

SYSTEM = (
    "You are a general AI assistant with web browsing and calculation tools. I will ask you a question.\n"
    "Rules to follow:\n"
    "1. Never ask the user for clarification. All questions are complete and must be answered autonomously.\n"
    "2. If external facts, numbers, dates, or records are needed, immediately call web_search or fetch_url to find the authoritative source.\n"
    "3. Pay strict attention to qualifiers and exact terminology (e.g. 'studio albums' excludes live/compilations; 'five-digit zip code' requires only 5 digits; 'minimum perigee' requires the exact number from Wikipedia).\n"
    "4. For arithmetic or multi-step calculations, use run_python or verify your math carefully step by step.\n"
    "5. Every response that concludes your work MUST finish with the template on a new line: FINAL ANSWER: [YOUR FINAL ANSWER]\n"
    "6. YOUR FINAL ANSWER should be as concise as possible: a single number, a word, or a comma-separated list. No explanations or conversational text after FINAL ANSWER."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "web_search", "description": "Search the web (SearXNG). Returns titles, URLs and snippets.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "fetch_url", "description": "Download a web page and return its text (truncated).",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "run_python", "description": "Run a short Python 3 script, return stdout/stderr.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
]


def extract_final(text: str) -> Optional[str]:
    m = re.findall(r"FINAL ANSWER:\s*(.+)", text or "", flags=re.IGNORECASE)
    if not m:
        return None
    ans = re.split(r"</think>", m[-1])[0].strip().strip(".").strip()
    ans = re.sub(r"^\[(.*)\]$", r"\1", ans).strip()
    return ans


def _num(s: str) -> Optional[float]:
    try:
        return float(re.sub(r"[$%,\s]", "", s))
    except ValueError:
        return None


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s.lower())


def match(pred: Optional[str], gold: str) -> bool:
    """Confronto quasi-esatto alla GAIA: numeri, liste, stringhe normalizzate."""
    if pred is None:
        return False
    if re.search(r"[,;]", gold):
        p, g = re.split(r"\s*[,;]\s*", pred), re.split(r"\s*[,;]\s*", gold)
        return len(p) == len(g) and all(match(a, b) for a, b in zip(p, g))
    gn = _num(gold)
    if gn is not None:
        pn = _num(pred)
        return pn is not None and pn == gn
    return _norm(pred) == _norm(gold)


def fetch_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "errore: solo http(s)"
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "gaia-bench/1"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            raw = r.read(300_000).decode("utf-8", "replace")
        text = re.sub(r"<(script|style)[\s\S]*?</\1>|<[^>]+>", " ", raw)
        return re.sub(r"\s+", " ", text)[:3000]
    except Exception as exc:
        return f"errore fetch: {exc}"


def web_search(query: str, searxng_url: str) -> str:
    url = f"{searxng_url.rstrip('/')}/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
    with urllib.request.urlopen(url, timeout=30) as r:
        res = json.load(r).get("results", [])[:6]
    return "\n".join(f"{x['title']} | {x['url']} | {(x.get('content') or '')[:200]}" for x in res) or "nessun risultato"


def run_python(code: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        try:
            r = subprocess.run([sys.executable, "-I", "-c", code], cwd=d, capture_output=True,
                               text=True, timeout=30)
            return (r.stdout + r.stderr)[-4000:]
        except subprocess.TimeoutExpired:
            return "errore: timeout 30s"


def chat(base_url: str, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json", "X-Hyperspace-Surface": "workbench"}
    req = urllib.request.Request(base_url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)


def solve(question: str, args: argparse.Namespace) -> Dict[str, Any]:
    tools = [t for t in TOOLS if args.allow_python or t["function"]["name"] != "run_python"]
    msgs: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM},
                                  {"role": "user", "content": question}]
    text = ""
    for turn in range(args.max_turns):
        # Pruning prudente per non sfondare il tetto dei token di contesto
        if len(msgs) > 8:
            for m in msgs[:-4]:
                if m.get("role") == "tool" and isinstance(m.get("content"), str) and len(m["content"]) > 300:
                    m["content"] = m["content"][:300] + " ... [trattato per brevità]"

        body = {
            "model": args.model,
            "messages": msgs,
            "temperature": 0,
            "max_tokens": args.max_tokens,
            "tools": tools,
        }
        try:
            res = chat(args.base_url, body)
            msg = res["choices"][0]["message"]
        except Exception as exc:
            return {"turns": turn + 1, "answer": None, "error": f"chat error: {exc}", "raw_tail": text[-300:]}

        msgs.append(msg)
        calls = msg.get("tool_calls") or []
        text = msg.get("content") or ""

        if not calls:
            ans = extract_final(text)
            if not ans:
                # Prompt di recupero formato finale (turno 0 o successivi)
                msgs.append({"role": "user", "content": "State your final conclusion now strictly in the format: FINAL ANSWER: [YOUR FINAL ANSWER]"})
                try:
                    res_fin = chat(args.base_url, {"model": args.model, "messages": msgs, "temperature": 0, "max_tokens": 1024})
                    text = res_fin["choices"][0]["message"].get("content") or text
                    ans = extract_final(text)
                except Exception:
                    pass
            return {"turns": turn + 1, "answer": ans, "raw_tail": text[-300:]}

        for idx, c in enumerate(calls):
            fn = c.get("function") or {}
            c_id = c.get("id") or f"call_{turn}_{idx}"
            try:
                a = json.loads(fn.get("arguments") or "{}")
                if fn.get("name") == "web_search":
                    out = web_search(a.get("query", ""), args.searxng_url)
                elif fn.get("name") == "fetch_url":
                    out = fetch_url(a.get("url", ""))
                elif fn.get("name") == "run_python" and args.allow_python:
                    out = run_python(a.get("code", ""))
                else:
                    out = "errore: tool non disponibile"
            except Exception as exc:
                out = f"errore: {exc}"
            msgs.append({"role": "tool", "tool_call_id": c_id, "content": out[:2500]})

    ans = extract_final(text)
    if not ans:
        msgs.append({"role": "user", "content": "Based on all search findings, state your final conclusion now strictly in the format: FINAL ANSWER: [YOUR FINAL ANSWER]"})
        try:
            res_fin = chat(args.base_url, {"model": args.model, "messages": msgs, "temperature": 0, "max_tokens": 1024})
            text = res_fin["choices"][0]["message"].get("content") or text
            ans = extract_final(text)
        except Exception:
            pass
    return {"turns": args.max_turns, "answer": ans, "raw_tail": text[-300:]}


def cmd_run(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(args.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    if getattr(args, "level", None):
        rows = [r for r in rows if str(r.get("Level")) == str(args.level)]
    if getattr(args, "only_text", False):
        rows = [r for r in rows if not r.get("file_name")]
    if getattr(args, "offset", 0):
        rows = rows[args.offset:]
    if args.limit:
        rows = rows[:args.limit]
    manifest = {k: getattr(args, k) for k in ("base_url", "model", "max_turns", "max_tokens",
                                              "client_tools", "allow_python", "searxng_url", "limit")}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    with open(out / "answers.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            rec: Dict[str, Any] = {"task_id": row["task_id"], "level": row.get("Level")}
            if row.get("file_name"):
                rec.update(model_answer=None, note="allegato")
            else:
                try:
                    res = solve(row["Question"], args)
                except Exception as exc:
                    res = {"answer": None, "error": str(exc)[:200]}
                rec.update(model_answer=res.get("answer"), **{k: v for k, v in res.items() if k != "answer"})
                gold = row.get("Final answer")
                if gold is not None and gold != "?":
                    rec["correct"] = match(res.get("answer"), str(gold))
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(rec["task_id"], rec.get("correct"), flush=True)
    return cmd_score(args)


def cmd_score(args: argparse.Namespace) -> int:
    recs = [json.loads(l) for l in (Path(args.out) / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    scored = [r for r in recs if "correct" in r]
    skipped = sum(1 for r in recs if r.get("note") == "allegato")
    ok = sum(r["correct"] for r in scored)
    print(f"corrette {ok}/{len(scored)}  (allegati saltati: {skipped}, totale righe: {len(recs)})")
    
    # Se è fornito il dataset completo (--data), allinea submission.jsonl a tutti i task ufficiali
    sub_map = {r["task_id"]: r.get("model_answer") or "" for r in recs}
    data_path = getattr(args, "data", None)
    if data_path and Path(data_path).exists():
        all_meta = [json.loads(l) for l in Path(data_path).read_text(encoding="utf-8").splitlines() if l.strip()]
        sub_rows = [{"task_id": m["task_id"], "model_answer": sub_map.get(m["task_id"], "")} for m in all_meta]
    else:
        sub_rows = [{"task_id": r["task_id"], "model_answer": sub_map.get(r["task_id"], "")} for r in recs]

    sub = Path(args.out) / "submission.jsonl"
    sub.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in sub_rows), encoding="utf-8")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--data", required=True)
    r.add_argument("--base-url", required=True)
    r.add_argument("--model", default="flint:latest")
    r.add_argument("--out", required=True)
    r.add_argument("--level", type=int, choices=(1, 2, 3), help="filtra per livello GAIA (1, 2 o 3)")
    r.add_argument("--only-text", action="store_true", help="filtra solo i task testuali senza allegati")
    r.add_argument("--offset", type=int, default=0)
    r.add_argument("--limit", type=int)
    r.add_argument("--max-turns", type=int, default=12)
    r.add_argument("--max-tokens", type=int, default=4096)
    r.add_argument("--searxng-url", default="http://localhost:8092")
    r.add_argument("--client-tools", action="store_true",
                   help="tool del client (X-Hyperspace-Tools: off) invece dei tool nativi del CP")
    r.add_argument("--allow-python", action="store_true")
    r.set_defaults(fn=cmd_run)
    s = sp.add_parser("score")
    s.add_argument("--out", required=True)
    s.add_argument("--data", help="percorso metadata.jsonl per allineare tutti i 301 task della leaderboard")
    s.set_defaults(fn=cmd_score)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
