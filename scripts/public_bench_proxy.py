#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""public_bench_proxy.py — adattatore minimo per l'endpoint OpenAI-compatibile di Gemini.

Perche' esiste: lm-evaluation-harness manda sempre il campo `seed` nel corpo della
richiesta, e l'endpoint compatibile di Google lo rifiuta (400 "Unknown name seed",
verificato 2026-11-03, anche con seed nullo). Questo proxy toglie SOLO i campi in
STRIP_FIELDS e inoltra tutto il resto invariato: stessi messaggi, stessa temperatura,
stessi token. Non modifica il contenuto delle domande ne' delle risposte.

E' parte della prova e va dichiarato: chi rifa' il giro lo avvia con lo stesso comando.
Non registra intestazioni ne' corpi, e la chiave arriva dal client (Authorization) senza
essere scritta da nessuna parte.

    python3 scripts/public_bench_proxy.py --port 8791 \
        --upstream https://generativelanguage.googleapis.com
    # poi nel target: base_url=http://127.0.0.1:8791/v1beta/openai/chat/completions
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

STRIP_FIELDS = ("seed",)


def clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Copia del corpo senza i campi che l'upstream non conosce."""
    return {k: v for k, v in payload.items() if k not in STRIP_FIELDS}


def make_handler(upstream: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # niente log: potrebbero contenere dati o chiavi
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = clean_payload(json.loads(self.rfile.read(length) or b"{}"))
            except json.JSONDecodeError:
                self.send_error(400, "JSON non valido")
                return
            req = urllib.request.Request(
                upstream.rstrip("/") + self.path,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": self.headers.get("Authorization", "")},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=600) as resp:
                    status, data = resp.status, resp.read()
            except urllib.error.HTTPError as exc:
                status, data = exc.code, exc.read()
            except Exception as exc:  # rete: lm_eval ritenta
                status, data = 502, json.dumps({"error": {"message": str(exc)[:200]}}).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--upstream", default="https://generativelanguage.googleapis.com")
    args = ap.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.upstream))
    print(f"proxy su 127.0.0.1:{args.port} -> {args.upstream} (tolti: {', '.join(STRIP_FIELDS)})",
          file=sys.stderr)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
