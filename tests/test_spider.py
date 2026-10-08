# SPDX-License-Identifier: Apache-2.0
"""La ragnatela (Web Crawlers) su ogni pagina — vedi docs/spider.md.

Nessuno di questi controlli e' teorico: sono i modi in cui questa cosa si rompe
in silenzio.
  - una pagina nuova senza la riga nell'<head>: la ragnatela semplicemente non
    c'e' li', e nessuno se ne accorge finche' non la si cerca a mano;
  - il file vendorizzato che entra in git per sbaglio (`git add -f`): rompe
    tests/test_licensing.py, e ridistribuisce codice che non ha licenza;
  - SPIDER_ENABLED=false che non spegne niente: una chiave scritta e mai letta;
  - il bootstrap rinominato: la rotta serve una pagina bianca e ogni pagina fa
    una richiesta inutile, senza nessun errore visibile.

Sorgenti letti come testo/AST: importare control-plane/main.py o
infra-ui/server.py qui significherebbe tirare su Flask/FastAPI e httpx solo per
controllare delle stringhe (stessa scelta di tests/test_infra_ui_landing.py).
"""
import ast
import hashlib
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from tests import cp_source

ROOT = Path(__file__).parents[1]
MAIN = ROOT / "control-plane" / "main.py"
BRIDGE = ROOT / "infra-ui" / "server.py"
BOOTSTRAP = ROOT / "control-plane" / "spider" / "bootstrap.js"
VENDOR = ROOT / "data" / "control-plane" / "vendor" / "web-crawlers" / "spider.js"
PROVENANCE = ROOT / "data" / "control-plane" / "vendor" / "web-crawlers" / "PROVENANCE.txt"
DOC = ROOT / "docs" / "spider.md"
INCLUDE = '<script defer src="/spider/bootstrap.js"></script>'
PAGINE = (sorted((ROOT / "control-plane").glob("*.html"))
          + sorted((ROOT / "infra-ui").glob("*.html")))


def _testo(percorso: Path) -> str:
    return percorso.read_text(encoding="utf-8")


def _codice_js(percorso: Path) -> str:
    """Il sorgente JS senza i commenti.

    I commenti del bootstrap PARLANO di localStorage (`sessionStorage, non
    localStorage`) e di chrome: cercare quelle stringhe li' dentro sarebbe un
    test che passa — o fallisce — per il motivo sbagliato.
    """
    testo = re.sub(r"/\*.*?\*/", "", _testo(percorso), flags=re.S)
    return re.sub(r"^\s*//.*$", "", testo, flags=re.M)


def _nodo(percorso: Path, nome: str) -> ast.AST:
    for nodo in ast.parse(_testo(percorso)).body:
        if isinstance(nodo, ast.Assign) and any(
                getattr(t, "id", "") == nome for t in nodo.targets):
            return nodo
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and nodo.name == nome:
            return nodo
    raise AssertionError(f"{nome} non c'e' piu' in {percorso.name}")


def _funzione(percorso: Path, nome: str) -> str:
    """Il sorgente di una funzione, per eseguirla con dei finti moduli."""
    return ast.unparse(_nodo(percorso, nome))


def _stringhe(percorso: Path, nome: str) -> set:
    """Le stringhe dentro un nodo: i letterali, senza dipendere dalle virgolette
    che sceglie chi li ha scritti (o dal modo in cui ast.unparse li rimette)."""
    return {n.value for n in ast.walk(_nodo(percorso, nome))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _meta() -> list:
    return ast.literal_eval(cp_source.nodo("_ENV_META").value)


class RagnatelaSuOgniPaginaTest(unittest.TestCase):
    def test_ogni_pagina_servita_ha_l_include_una_volta_sola(self):
        """La guardia che conta: 'in ogni parte' vale finche' vale per tutte."""
        self.assertGreaterEqual(len(PAGINE), 10,
                                "le pagine servite sono cambiate: aggiorna docs/spider.md")
        for pagina in PAGINE:
            with self.subTest(pagina=pagina.name):
                html = _testo(pagina)
                self.assertEqual(html.count(INCLUDE), 1,
                                 "una pagina senza la ragnatela non da' errore: manca e basta")
                self.assertLess(html.index(INCLUDE), html.index("</head>"),
                                "l'include sta nell'<head>, come gli altri <script> defer")


class RotteDelControlPlaneTest(unittest.TestCase):
    def test_le_due_rotte_esistono(self):
        testo = _testo(MAIN)
        self.assertIn("@app.route('/spider/bootstrap.js')", testo)
        self.assertIn("@app.route('/spider/spider.js')", testo)

    def test_il_bootstrap_porta_contratto_e_codice_non_cacheati(self):
        stringhe = _stringhe(MAIN, "spider_bootstrap")
        self.assertIn("window.__HSPIDER__", _testo(MAIN))
        self.assertIn("/spider/spider.js", stringhe)
        self.assertIn("Cache-Control", stringhe)
        self.assertIn("no-store", stringhe)
        self.assertIn("application/javascript", stringhe)

    def test_il_bootstrap_usa_il_kill_switch(self):
        self.assertIn("_spider_enabled", _funzione(MAIN, "spider_bootstrap"))

    def test_il_contratto_porta_anche_la_destinazione_della_ricerca(self):
        self.assertIn("_spider_search", _funzione(MAIN, "spider_bootstrap"))

    def test_la_ragnatela_mancante_non_e_un_errore_di_rete(self):
        stringhe = _stringhe(MAIN, "spider_vendored")
        self.assertIn("docs/spider.md", " ".join(stringhe))
        self.assertIn("application/javascript", stringhe)
        valori = {n.value for n in ast.walk(_nodo(MAIN, "spider_vendored"))
                  if isinstance(n, ast.Constant)}
        self.assertIn(404, valori, "404 con commento JS: la console lo dice, la pagina no")

    def test_la_ragnatela_viene_servita_da_dove_il_container_la_vede(self):
        """Il percorso si risolve nei due alberi in cui questo file gira davvero.

        Nel container BASE_DIR e' /app e i dati arrivano dal volume in /app/data
        (cioe' il data/control-plane della repo); nella repo i dati stanno in
        ../data/control-plane. Sbagliarlo non da' errore: da' 404 silenzioso.
        """
        self.assertEqual(Path(self._risolvi(str(ROOT / "control-plane"))).resolve(),
                         VENDOR.resolve(),
                         "nella repo si arriva a data/control-plane/vendor/web-crawlers")
        with tempfile.TemporaryDirectory() as tmp:
            finto = Path(tmp, "data", "vendor", "web-crawlers", "spider.js")
            finto.parent.mkdir(parents=True)
            finto.write_text("// finta ragnatela", encoding="utf-8")
            self.assertEqual(Path(self._risolvi(tmp)).resolve(), finto.resolve(),
                             "nel container /app/data e' la prima cosa che si guarda")

    def test_senza_il_file_il_ripiego_e_il_percorso_del_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(Path(self._risolvi(tmp)),
                             Path(tmp, "data", "vendor", "web-crawlers", "spider.js"))

    def test_il_bootstrap_e_dove_il_dockerfile_lo_copia(self):
        """Se la cartella sposta, il Dockerfile la copia ancora? Se no: 404 a ogni
        pagina, e nessun errore da nessuna parte."""
        ns = {"os": os, "BASE_DIR": str(ROOT / "control-plane")}
        exec(ast.unparse(_nodo(MAIN, "SPIDER_BOOTSTRAP")), ns)
        self.assertEqual(Path(ns["SPIDER_BOOTSTRAP"]).resolve(), BOOTSTRAP.resolve())
        self.assertIn("./spider", _testo(ROOT / "control-plane" / "Dockerfile"),
                      "il Dockerfile deve portarsi il bootstrap nell'immagine")

    def _risolvi(self, base_dir: str) -> str:
        ns = {"os": os, "BASE_DIR": base_dir}
        exec(_funzione(MAIN, "_spider_vendor_path"), ns)
        return ns["_spider_vendor_path"]()


class KillSwitchTest(unittest.TestCase):
    """SPIDER_ENABLED: la chiave della tab Setup. Eseguita davvero, non letta."""

    @classmethod
    def setUpClass(cls):
        ns = {"os": os}
        exec(_funzione(MAIN, "_spider_enabled"), ns)
        cls.spegne = staticmethod(ns["_spider_enabled"])

    def test_spegne(self):
        for valore in ("0", "false", "FALSE", " false ", "no", "off", " Off "):
            with self.subTest(valore=valore), mock.patch.dict(
                    os.environ, {"SPIDER_ENABLED": valore}):
                self.assertFalse(self.spegne(), f"{valore!r} deve spegnere")

    def test_lascia_acceso_il_resto(self):
        """Solo i valori espliciti spengono: un refuso non deve togliere la
        ragnatela a sorpresa."""
        for valore in ("", "true", "TRUE", "1", "yes", "on", "si", "qualsiasi cosa"):
            with self.subTest(valore=valore), mock.patch.dict(
                    os.environ, {"SPIDER_ENABLED": valore}):
                self.assertTrue(self.spegne(), f"{valore!r} non deve spegnere")

    def test_senza_la_chiave_la_ragnatela_c_e(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SPIDER_ENABLED", None)
            self.assertTrue(self.spegne())


class AssistenteRicercaTest(unittest.TestCase):
    """SPIDER_SEARCH e il contratto `search`: eseguiti davvero, non solo letti."""

    @classmethod
    def setUpClass(cls):
        ns = {"os": os}
        for nome in ("_spider_enabled", "_spider_search_enabled", "_spider_search"):
            exec(_funzione(MAIN, nome), ns)
        cls.acceso = staticmethod(ns["_spider_search_enabled"])
        cls.destinazione = staticmethod(ns["_spider_search"])

    def test_spegne(self):
        for valore in ("0", "false", "FALSE", " no ", "off", " Off "):
            with self.subTest(valore=valore), mock.patch.dict(
                    os.environ, {"SPIDER_SEARCH": valore}):
                self.assertFalse(self.acceso(), f"{valore!r} deve spegnere")

    def test_acceso_di_default(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SPIDER_SEARCH", None)
            os.environ.pop("SPIDER_ENABLED", None)
            self.assertTrue(self.acceso())

    def test_spento_non_manda_nessuna_destinazione(self):
        with mock.patch.dict(os.environ, {"SPIDER_SEARCH": "false"}):
            self.assertIsNone(self.destinazione())

    def test_senza_la_ragnatela_l_assistente_non_esiste(self):
        """Non c'e' nessuno che raccoglie la parola: il contratto non lo dichiara."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SPIDER_SEARCH", None)
            os.environ["SPIDER_ENABLED"] = "false"
            self.assertIsNone(self.destinazione())

    def test_la_destinazione_e_porta_pubblica_e_path(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SPIDER_SEARCH", None)
            os.environ.pop("SPIDER_ENABLED", None)
            os.environ.pop("SEARXNG_PORT", None)
            self.assertEqual(self.destinazione(), {"port": 8092, "path": "/search"})

    def test_la_porta_si_puo_cambiare(self):
        with mock.patch.dict(os.environ, {"SEARXNG_PORT": "9999"}, clear=False):
            os.environ.pop("SPIDER_SEARCH", None)
            os.environ.pop("SPIDER_ENABLED", None)
            self.assertEqual(self.destinazione()["port"], 9999)


class VendorTest(unittest.TestCase):
    """Il file di terzi: fuori da git, con l'impronta che dichiariamo."""

    def setUp(self):
        if not VENDOR.exists():
            self.skipTest("vendor assente (gitignorato): e' il caso di un clone pulito")

    def test_l_impronta_e_quella_dichiarata_in_provenance(self):
        impronta = hashlib.sha256(VENDOR.read_bytes()).hexdigest()
        self.assertIn(impronta, _testo(PROVENANCE),
                      "il file non e' quello di cui PROVENANCE.txt dichiara l'impronta")

    def test_git_non_lo_traccia_e_lo_ignora(self):
        """Il vincolo di licenza, scritto come test: se questo fallisce, il
        prossimo `git add -f` rompe tests/test_licensing.py."""
        relativo = str(VENDOR.relative_to(ROOT))
        ignorato = subprocess.run(["git", "check-ignore", "-q", relativo],
                                  cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(ignorato.returncode, 0,
                         f"{relativo} deve restare sotto .gitignore (**/data/)")
        tracciato = subprocess.run(["git", "ls-files", "--error-unmatch", relativo],
                                   cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(tracciato.returncode, 0,
                            "codice di terzi senza licenza non deve entrare nel repo")

    def test_la_provenienza_dice_da_dove_viene(self):
        testo = _testo(PROVENANCE)
        for atteso in ("cyohei9907", "web-crawlers", "extension/src/spider.js",
                       "gitignorato", "Apache-2.0"):
            with self.subTest(atteso=atteso):
                self.assertIn(atteso, testo)


class BridgeTest(unittest.TestCase):
    def test_la_bridge_serve_la_stessa_riga_puntando_al_cp(self):
        testo = _testo(BRIDGE)
        self.assertIn('@app.get("/spider/bootstrap.js")', testo)
        self.assertIn('@app.get("/spider/spider.js")', testo)
        self.assertIn("_spider_asset", testo)

    def test_il_proxy_inoltra_al_control_plane(self):
        sorgente = _funzione(BRIDGE, "_spider_asset")
        self.assertIn("CP_URL", sorgente, "stessa fonte unica delle altre rotte")
        self.assertIn("/spider/", sorgente)
        self.assertIn("application/javascript", _stringhe(BRIDGE, "_spider_asset"))
        self.assertIn("docs/spider.md", " ".join(_stringhe(BRIDGE, "_spider_asset")))

    def test_nessuna_copia_locale_del_file_di_terzi(self):
        """La bridge non tiene il file: lo chiede al CP. Cosi' l'immagine del
        bridge non trasporta codice senza licenza."""
        self.assertFalse((ROOT / "infra-ui" / "spider.js").exists())
        self.assertFalse((ROOT / "infra-ui" / "vendor" / "web-crawlers").exists())


class CatalogoTest(unittest.TestCase):
    def test_la_chiave_e_dichiarata_e_leggibile_dalla_tab_setup(self):
        voci = {m["key"]: m for m in _meta()}
        self.assertIn("SPIDER_ENABLED", voci)
        voce = voci["SPIDER_ENABLED"]
        self.assertEqual(voce["type"], "bool")
        self.assertEqual(voce["default"], "true")
        self.assertEqual(voce["section"], "Interfaccia (UI)")
        self.assertTrue(voce["label"] and voce["hint"], "una voce muta non si sa cosa fa")
        self.assertIn("SPIDER_ENABLED", _testo(ROOT / ".env.example"),
                      "una chiave senza riga in .env.example non si scopre")

    def test_anche_l_assistente_ha_la_sua_chiave(self):
        voci = {m["key"]: m for m in _meta()}
        self.assertIn("SPIDER_SEARCH", voci)
        voce = voci["SPIDER_SEARCH"]
        self.assertEqual(voce["type"], "bool")
        self.assertEqual(voce["default"], "true")
        self.assertEqual(voce["section"], "Interfaccia (UI)")
        self.assertTrue(voce["label"] and voce["hint"],
                        "una voce muta non si sa cosa fa")
        self.assertIn("SPIDER_SEARCH", _testo(ROOT / ".env.example"),
                      "una chiave senza riga in .env.example non si scopre")


class BootstrapTest(unittest.TestCase):
    """Il file NOSTRO: l'unico di questo intervento che porta la licenza."""

    @classmethod
    def setUpClass(cls):
        cls.src = _testo(BOOTSTRAP)
        cls.codice = _codice_js(BOOTSTRAP)

    def test_e_nostro_e_non_dell_upstream(self):
        self.assertIn("SPDX-License-Identifier: Apache-2.0", self.src)
        self.assertNotIn("chrome.", self.codice)

    def test_non_tocca_la_pagina(self):
        self.assertNotIn("document.body", self.codice)
        self.assertNotIn("innerHTML", self.codice)
        self.assertIn("appendChild", self.codice, "il solo <script> che aggiunge")

    def test_lo_stato_e_della_scheda(self):
        self.assertIn("sessionStorage", self.codice)
        self.assertNotIn("localStorage", self.codice)

    def test_e_spegnibile_dal_contratto_e_da_solo(self):
        self.assertIn("enabled === false", self.codice)
        self.assertIn("__HSPIDER__", self.codice)

    def test_i_modi_per_riprenderla_sono_nel_file(self):
        self.assertIn("prefers-reduced-motion", self.codice)
        for comando in ("Alt+Shift+S", "?spider=off", "__hspider"):
            with self.subTest(comando=comando):
                self.assertIn(comando, self.src)

    def test_l_assistente_alla_ricerca_e_nel_file(self):
        """La parola sotto il ragno non arriva dall'upstream: la ricaviamo noi,
        con la stessa API pubblica che usa lui. Se queste righe spariscono,
        l'assistente muore in silenzio: nessun chip, nessun errore."""
        self.assertIn("cfg.search", self.codice)
        for atteso in ("caretRangeFromPoint", "Segmenter", "data-hspider-chip",
                       "Alt+Shift+F", "window.open"):
            with self.subTest(atteso=atteso):
                self.assertIn(atteso, self.src)


class DocumentazioneTest(unittest.TestCase):
    def test_la_doc_racconta_provenienza_limiti_e_comandi(self):
        doc = _testo(DOC)
        for atteso in ("cyohei9907", "extension/src/spider.js", "Apache-2.0",
                       "sessionStorage", "prefers-reduced-motion", "SPIDER_ENABLED",
                       "Alt+Shift+S", "?spider=off", "PROVENANCE.txt",
                       "test_licensing.py", "data/control-plane/vendor/web-crawlers/spider.js",
                       "SPIDER_SEARCH", "Alt+Shift+F", "SearXNG", "caretRangeFromPoint"):
            with self.subTest(atteso=atteso):
                self.assertIn(atteso, doc)

    def test_la_doc_dichiara_i_due_limiti_veri(self):
        """Le altre origini non si toccano; la posizione delle zampe non e' quella
        di prima. Sono i due punti in cui la richiesta 'ovunque' non e' letterale."""
        doc = _testo(DOC)
        self.assertIn("altre origini", doc)
        self.assertIn("espone nessuna API per", doc)

    def test_la_doc_e_indicizzata_dall_indice(self):
        self.assertIn("spider.md", _testo(ROOT / "docs" / "README.md"))


if __name__ == "__main__":
    unittest.main()


