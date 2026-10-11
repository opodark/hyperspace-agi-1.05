# SPDX-License-Identifier: Apache-2.0
"""La superficie locale del grafo del repository (`scripts/graphify_surface.py`).

Quattro cose si rompono in silenzio, e questo test le tiene ferme:

  - la superficie smette di essere di sola lettura o scivola fuori da loopback;
  - una community senza nome torna a chiamarsi "Community 12" e la pagina lo
    nasconde invece di derivare un'etichetta dal grafo;
  - la porta del modulo e quella annunciata in `/surfaces` si separano, e la
    card della dashboard apre un URL muto;
  - un `?dir=` qualunque diventa un percorso arbitrario sul filesystem.

Il grafo vero non serve: si costruisce un grafo minimo in una radice temporanea.
"""
import ast
import json
import tempfile
import unittest
from pathlib import Path

from tests import cp_source

from scripts import graphify_surface as gs

ROOT = Path(__file__).resolve().parents[1]
SORGENTE = (ROOT / "scripts" / "graphify_surface.py").read_text(encoding="utf-8")


def grafo_finto() -> dict:
    """Due community: una senza nome (segnaposto), una con un nome dichiarato."""
    return {
        "built_at_commit": "abc1234def",
        "nodes": [
            {"id": "a", "label": "push_log", "community": 0, "community_name": "Community 0",
             "source_file": "control-plane/cp/log.py", "source_location": "L10", "file_type": "code"},
            {"id": "b", "label": "rota", "community": 0, "community_name": "Community 0",
             "source_file": "control-plane/cp/log.py", "source_location": "L40"},
            {"id": "c", "label": "ricerca", "community": 1, "community_name": "Documenti e ricerca",
             "source_file": "docs/graphify.md", "source_location": "L1"},
            {"id": "d", "label": "hs", "community": 1, "community_name": "Community 1",
             "source_file": "scripts/hs.py", "source_location": "L1"},
        ],
        "links": [
            {"source": "a", "target": "b", "relation": "calls", "source_file": "control-plane/cp/log.py"},
            {"source": "a", "target": "c", "relation": "calls", "source_file": "control-plane/cp/log.py"},
            {"source": "b", "target": "c", "relation": "calls"},
            {"source": "d", "target": "c", "relation": "imports_from"},
        ],
    }


def radice_finta(destinazione: str, grafo: dict | None = None, con_report: bool = True) -> Path:
    radice = Path(destinazione)
    cartella = radice / "graphify-out"
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "graph.json").write_text(json.dumps(grafo if grafo is not None else grafo_finto()),
                                        encoding="utf-8")
    if con_report:
        (cartella / "GRAPH_REPORT.md").write_text("# Report\n\n- 4 nodi\n", encoding="utf-8")
    return radice


class EtichetteDerivateTests(unittest.TestCase):
    """Il buco delle community senza nome, chiuso dal grafo stesso."""

    def setUp(self):
        self.etichette = gs.community_labels(grafo_finto())

    def test_il_segnaposto_diventa_un_etichetta_leggibile(self):
        c0 = self.etichette["communities"]["0"]
        self.assertTrue(c0["derived"], "un nome 'Community N' non e' un nome: va derivato")
        self.assertNotIn("Community", c0["name"])
        self.assertEqual(c0["name"], "push_log · control-plane")
        self.assertEqual(c0["hub"], "push_log")          # il nodo piu' connesso
        self.assertEqual(c0["dir"], "control-plane")     # la directory dominante
        self.assertEqual(c0["size"], 2)

    def test_il_nome_dichiarato_non_si_sovrascrive(self):
        c1 = self.etichette["communities"]["1"]
        self.assertFalse(c1["derived"])
        self.assertEqual(c1["name"], "Documenti e ricerca")
        self.assertEqual(self.etichette["names"],
                         {"derived": 1, "declared": 1, "total": 2})

    def test_gradi_e_vicinanze_per_ispettore(self):
        self.assertEqual(self.etichette["degree"], {"a": 2, "b": 2, "c": 3, "d": 1})
        uscenti = [v["id"] for v in self.etichette["neighbours"]["a"] if v["dir"] == "out"]
        self.assertEqual(sorted(uscenti), ["b", "c"])
        entranti = [v["id"] for v in self.etichette["neighbours"]["c"] if v["dir"] == "in"]
        self.assertEqual(sorted(entranti), ["a", "b", "d"])


class StatoEFreschezzaTests(unittest.TestCase):
    """Un grafo vecchio deve dirlo: e' la ragione per cui la superficie esiste."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.radice = radice_finta(self.tmp.name)
        self.cartella = self.radice / "graphify-out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_conteggi_e_commit(self):
        stato = gs.graph_status(self.cartella, self.radice, head="abc1234")
        self.assertEqual((stato["nodes"], stato["edges"], stato["communities"]), (4, 4, 2))
        self.assertEqual(stato["built_at_commit"], "abc1234def")
        self.assertFalse(stato["stale"], "stesso commit: non e' stantio")
        self.assertTrue(stato["report"])
        self.assertFalse(stato["html"], "senza graph.html la superficie lo dice, non lo inventa")
        self.assertIsNotNone(stato["age_hours"])

    def test_head_diverso_significa_stantio(self):
        stato = gs.graph_status(self.cartella, self.radice, head="9999999")
        self.assertTrue(stato["stale"])

    def test_senza_commit_non_si_finge_fresco(self):
        grafo = grafo_finto()
        grafo.pop("built_at_commit")
        radice = radice_finta(str(Path(self.tmp.name) / "senza-commit"), grafo)
        stato = gs.graph_status(radice / "graphify-out", radice, head="abc1234")
        self.assertIsNone(stato["stale"], "non sapere non e' 'fresco'")

    def test_ogni_stato_porta_i_comandi_che_lo_rimettono_a_posto(self):
        stato = gs.graph_status(self.cartella, self.radice, head="abc1234")
        self.assertEqual(stato["commands"]["update"], "./scripts/graphify.sh update .")
        self.assertIn("graphify_surface.py", stato["commands"]["service"])


class RotteTests(unittest.TestCase):
    """Le rotte servono dati veri e rifiutano i percorsi che non sono grafi."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.radice = radice_finta(self.tmp.name)
        self.client = gs.build_app(self.radice).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_health_dichiara_lettura_sola_e_i_grafi(self):
        corpo = self.client.get("/health").get_json()
        self.assertTrue(corpo["ok"])
        self.assertTrue(corpo["read_only"])
        self.assertEqual(corpo["graphs"], ["graphify-out"])

    def test_la_pagina_si_serve_e_ha_gli_agganci(self):
        risposta = self.client.get("/")
        self.assertEqual(risposta.status_code, 200)
        pagina = risposta.get_data(as_text=True)
        for aggancio in ('id="net"', 'id="comList"', 'id="inspect"', 'id="dirSel"',
                         "/api/graph", "/api/status"):
            with self.subTest(aggancio=aggancio):
                self.assertIn(aggancio, pagina)

    def test_api_graph_allega_community_e_vicinanze(self):
        corpo = self.client.get("/api/graph").get_json()
        self.assertEqual(sorted(corpo["communities"]), ["0", "1"])
        self.assertEqual(corpo["communities"]["0"]["name"], "push_log · control-plane")
        self.assertEqual(corpo["names"], {"derived": 1, "declared": 1, "total": 2})
        self.assertIn("a", corpo["neighbours"])
        self.assertEqual(len(corpo["nodes"]), 4)
        for nodo in corpo["nodes"]:
            self.assertTrue(set(nodo) <= set(gs._CAMPI_NODO),
                            f"campo non dichiarato servito al browser: {sorted(set(nodo) - set(gs._CAMPI_NODO))}")

    def test_api_status_e_report(self):
        stato = self.client.get("/api/status").get_json()
        self.assertEqual(stato["nodes"], 4)
        self.assertEqual(stato["dir"], "graphify-out")
        report = self.client.get("/api/report")
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.get_data(as_text=True).startswith("# Report"))

    def test_report_assente_lo_dice_con_il_comando(self):
        radice = radice_finta(str(Path(self.tmp.name) / "senza-report"), con_report=False)
        client = gs.build_app(radice).test_client()
        risposta = client.get("/api/report")
        self.assertEqual(risposta.status_code, 404)
        self.assertIn("cluster-only", risposta.get_json()["detail"])

    def test_i_percorsi_che_non_sono_grafi_restano_fuori(self):
        for cattivo in ("../../etc", "/etc", "..", "graphify-out/../graphify-out",
                        "graphify-out/graph.json", "graphify-out-docs"):
            with self.subTest(dir=cattivo):
                self.assertEqual(self.client.get("/api/status?dir=" + cattivo).status_code, 404)
                self.assertEqual(self.client.get("/api/graph?dir=" + cattivo).status_code, 404)

    def test_radice_senza_grafi_non_e_un_crash(self):
        vuota = Path(self.tmp.name) / "vuota"
        vuota.mkdir()
        client = gs.build_app(vuota).test_client()
        self.assertEqual(client.get("/health").get_json()["graphs"], [])
        manca = client.get("/api/status")
        self.assertEqual(manca.status_code, 404)
        self.assertIn("graphify", manca.get_json()["commands"]["primo_giro"])
        self.assertEqual(client.get("/").status_code, 200)


class InvariantiTests(unittest.TestCase):
    """Il perimetro: loopback, sola lettura, un solo sottoprocesso e di sola lettura."""

    def test_solo_loopback(self):
        self.assertEqual(gs.HOST, "127.0.0.1")
        # assertTrue e non assertNotIn: se fallisce, il messaggio di assertNotIn
        # stamperebbe l'intero sorgente del modulo.
        self.assertTrue("0.0.0.0" not in SORGENTE,
                        "nessuna stringa di questo file puo' bindare il wildcard")

    def test_nessuna_scrittura_nel_repository(self):
        for vietato in ("write_text", "shutil", "shell=True", "os.remove", "unlink"):
            with self.subTest(vietato=vietato):
                self.assertNotIn(vietato, SORGENTE)

    def test_un_solo_sottoprocesso_e_legge_solo_head(self):
        chiamate = [n for n in ast.walk(ast.parse(SORGENTE))
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and getattr(n.func.value, "id", "") == "subprocess"]
        self.assertEqual([c.func.attr for c in chiamate], ["run"])
        self.assertEqual(gs.GIT_HEAD_ARGV, ["git", "rev-parse", "--short", "HEAD"])

    def test_la_pagina_non_promette_nomi_che_non_ha(self):
        for aggancio in ("etichetta derivata", "stantio", "./scripts/graphify.sh cluster-only ."):
            with self.subTest(aggancio=aggancio):
                self.assertIn(aggancio, gs._PAGE)


class ContrattoConLoStackTests(unittest.TestCase):
    """La superficie e' annunciata dove gli altri la cercano, con la stessa porta."""

    def setUp(self):
        self.catalogo = ast.literal_eval(cp_source.assegnazioni()["SURFACES"])

    def test_il_catalogo_annuncia_la_stessa_porta(self):
        voci = [s for s in self.catalogo if s["id"] == "graphify"]
        self.assertEqual(len(voci), 1, "una superficie sola, con un id stabile")
        voce = voci[0]
        self.assertEqual(voce["port"], gs.PORT)
        self.assertEqual(voce["path"], "/")
        self.assertEqual(voce["category"], "dev")
        self.assertTrue(voce.get("optional"), "il grafo e' un extra: senza grafo il servizio non parte")

    def test_la_dashboard_apre_la_superficie_dal_catalogo(self):
        dashboard = (ROOT / "control-plane" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("openSurface('graphify')", dashboard)
        self.assertIn("async function openSurface(id)", dashboard)
        self.assertIn(f":{gs.PORT}<", dashboard, "la card dice su quale porta guardare")

    def test_start_tutto_la_avvia(self):
        script = (ROOT / "scripts" / "start-all-macos.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/graphify_surface.py", script)
        self.assertIn(str(gs.PORT), script)
        self.assertIn("--check", script, "senza grafo il servizio non si avvia (check prima)")

    def test_la_documentazione_la_descrive(self):
        doc = (ROOT / "docs" / "graphify.md").read_text(encoding="utf-8")
        self.assertIn("graphify_surface.py", doc)
        self.assertIn(str(gs.PORT), doc)


if __name__ == "__main__":
    unittest.main()
