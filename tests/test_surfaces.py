# SPDX-License-Identifier: Apache-2.0
"""Il catalogo delle superfici (`/surfaces`) e la scheda "Servizi".

Sono i modi in cui questa pagina e questo endpoint si rompono in silenzio:
  - se una superficie perde il `path`, la card punta a un URL muto;
  - se un campo viene rinominato, la card mostra vuoto senza nessun errore;
  - se nasce una categoria nuova nel catalogo senza etichetta nella dashboard,
    quel gruppo di card non viene disegnato affatto;
  - se la rotta sparisce, la scheda "Servizi" resta su "Caricamento…" per sempre.

I campi sono un contratto fra due lati: i test lo fissano.
"""
import ast
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify

ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
DASH = (ROOT / "control-plane" / "dashboard.html").read_text(encoding="utf-8")


def _surfaces_literal():
    for node in ast.parse(MAIN).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SURFACES":
            return ast.literal_eval(node.value)
    raise AssertionError("SURFACES non trovato in control-plane/main.py")


class SurfacesCatalogTests(unittest.TestCase):
    def test_la_rotta_esiste(self):
        routes = {dec.args[0].value for node in ast.parse(MAIN).body
                  if isinstance(node, ast.FunctionDef)
                  for dec in node.decorator_list
                  if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                  and dec.func.attr == "route" and dec.args}
        self.assertIn("/surfaces", routes)

    def test_ogni_superficie_dichiara_come_si_apre(self):
        for s in _surfaces_literal():
            with self.subTest(id=s.get("id")):
                self.assertTrue(s.get("id"), "ogni superficie ha un id stabile")
                self.assertTrue(s.get("label"), "ogni superficie ha un'etichetta")
                self.assertTrue(str(s.get("path", "")).startswith("/"),
                                "il path e' quello che apre il browser")
                port = s.get("port")
                self.assertTrue(port is None or (isinstance(port, int) and 0 < port < 65536),
                                f"port deve essere None o una porta valida, e' {port!r}")
                self.assertIn(s.get("category"),
                              {"control-plane", "observability", "dev", "external"})

    def test_gli_id_sono_unici(self):
        ids = [s["id"] for s in _surfaces_literal()]
        self.assertEqual(len(ids), len(set(ids)), "un id duplicato rompe le card e le chiavi di stato")

    def test_la_rotta_restituisce_il_catalogo(self):
        source = ROOT / "control-plane" / "main.py"
        function = next(node for node in ast.parse(source.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == "surfaces")
        function.decorator_list = []
        app = Flask(__name__)
        scope = {"jsonify": jsonify, "datetime": datetime, "timezone": timezone,
                 "SURFACES": _surfaces_literal()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), scope)
        app.add_url_rule("/surfaces", view_func=scope["surfaces"])
        resp = app.test_client().get("/surfaces")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["surfaces"], _surfaces_literal())
        self.assertIn("ts", body)

    def test_la_dashboard_rende_la_scheda_servizi(self):
        self.assertIn('id="panel-services"', DASH)
        self.assertIn("showPanel('services',this)", DASH)
        self.assertIn("onclick=\"loadSurfaces()\"", DASH)
        self.assertIn("if(name==='services')loadSurfaces();", DASH)

    def test_le_categorie_della_pagina_coprono_il_catalogo(self):
        blocco = re.search(r"var SURFACE_CATEGORIES = \{(.*?)\};", DASH, re.S)
        self.assertIsNotNone(blocco, "SURFACE_CATEGORIES non trovato in dashboard.html")
        coperte = set(re.findall(r"'([\w-]+)':", blocco.group(1)))
        usate = {s["category"] for s in _surfaces_literal()}
        self.assertFalse(usate - coperte,
                         f"categorie senza etichetta nella dashboard: {sorted(usate - coperte)}")


if __name__ == "__main__":
    unittest.main()
