# SPDX-License-Identifier: Apache-2.0
"""La serie notturna: trenta scene che passano il confine, e una coda che si aspetta.

Il caso che questi test difendono è quello per cui `scripts/serie_anna.py` esiste: la
coda ha un tetto (`IMAGE_QUEUE_MAX=24`) **più corto della serie** (30 scene, 2026-10-02).
Il rifiuto `coda piena` (HTTP 429, che `ImmagineQueue.accoda` solleva) deve diventare
un'attesa, non una scena persa — è l'unica cosa che questo script fa e `serie.py` non
fa, quindi è l'unica che può rompersi in silenzio.

L'altro caso è il documento di Anna: una scena che chiede una nudità o un soggetto
minorenne deve essere rifiutata **prima** di accodare, non disegnata. Trenta scene
scritte a mano sono trenta occasioni di scrivere la parola sbagliata, e il test le
guarda una per una invece di fidarsi.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.image_jobs import POSE_PRESET  # noqa: E402
from shared.showcase import (VIETATI_ASSOLUTI, conflitti, verifica_vetrina,  # noqa: E402
                             vetrina_dal_documento)

SCRIPT = ROOT / "scripts" / "serie_anna.py"
ANNA = ROOT / "data" / "persona-anna.json"


def _carica():
    specifica = importlib.util.spec_from_file_location("serie_anna_sotto_test", SCRIPT)
    modulo = importlib.util.module_from_spec(specifica)
    specifica.loader.exec_module(modulo)
    return modulo


class ScenaTests(unittest.TestCase):
    """Le cinquanta scene: numerate, distinte, e tutte dentro il confine del documento."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _carica()
        cls.documento = json.loads(ANNA.read_text(encoding="utf-8"))
        cls.vetrina = vetrina_dal_documento(cls.documento)

    def test_sono_cinquanta_numerate_e_distinte(self):
        """Il numero nel nome è l'ordine in cui si guardano: se salta, la serie mente."""
        scene = self.mod.SCENE
        self.assertEqual(len(scene), 50)
        self.assertEqual([nome.split("-")[0] for nome, _s, _p in scene],
                         [f"{numero:02d}" for numero in range(1, 51)])
        self.assertEqual(len({nome for nome, _s, _p in scene}), 50)
        self.assertEqual(len({scena for _n, scena, _p in scene}), 50,
                         "due scene identiche sono una scena sola pagata due volte")

    def test_ogni_scena_passa_il_confine_del_documento(self):
        """Nessuna eccezione: una scena rifiutata di notte è una scena che manca."""
        rifiutate = []
        for nome, scena, posa in self.mod.SCENE:
            variante = {**self.vetrina, "scena": scena,
                        "pose_preset": self.mod.posa_da_mandare(self.vetrina, posa)}
            problemi = verifica_vetrina(variante, self.documento)
            if problemi:
                rifiutate.append(f"{nome}: {problemi}")
        self.assertEqual(rifiutate, [], "scene che il documento di Anna non permette")

    def test_nessuna_scena_contiene_una_parola_vietata(self):
        """Il controllo del confine è una sottostringa: si guarda il testo, non l'intento.

        Si usa `conflitti`, la stessa funzione che usa il confine vero: un elenco
        ricopiato qui direbbe «a posto» su una parola che il guard conosce e il test no.
        """
        for nome, scena, _posa in self.mod.SCENE:
            self.assertEqual(conflitti(scena, VIETATI_ASSOLUTI), [],
                             f"{nome}: parola vietata nella scena")

    def test_la_serie_varia_davvero(self):
        """Trenta varianti servono a scegliere: se cambia una parola, non c'è scelta."""
        scene = self.mod.SCENE
        pose_usate = {posa for _n, _s, posa in scene if posa}
        self.assertTrue({"standing", "seated", "lying", "walking", "dancing", "arms_open"}
                        <= pose_usate, f"pose usate: {sorted(pose_usate)}")
        for posa in pose_usate:
            self.assertIn(posa, POSE_PRESET)
        # Luce e ambiente: due scene con la stessa luce sono la stessa scena due volte.
        self.assertGreaterEqual(len({scena.split(",")[-2].strip() for _n, scena, _p in scene}),
                                20)

    def test_le_scene_glamour_ci_sono_e_sono_vestite(self):
        """Il vocabolario della banda VIP c'è, e dice `fully clothed`: senza quella
        parola «lingerie» da sola è un invito a toglierla."""
        glamour = [nome for nome, scena, _p in self.mod.SCENE
                   if "glamorous lingerie editorial" in scena]
        self.assertGreaterEqual(len(glamour), 3, "le scene in lingerie sono sparite")
        for _nome, scena, _posa in self.mod.SCENE:
            if "glamorous lingerie editorial" in scena:
                self.assertIn("fully clothed", scena, "lingerie senza «fully clothed»")
        self.assertTrue(any(scena for _n, scena, _p in self.mod.SCENE
                            if "stockings" in scena), "le calze chieste non ci sono")


class CodaTests(unittest.TestCase):
    """La coda piena è un'attesa, non una scena persa: è la ragione dello script.

    Trenta scene e un tetto di ventiquattro (`IMAGE_QUEUE_MAX`) non entrano in un
    colpo. Il caso vero è quello: alle prime sei che avanzano il control-plane risponde
    `coda piena`, e se lo script le dichiarasse fallite la serie notturna uscirebbe da
    ventiquattro — cioè non sarebbe la serie che si è chiesta.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = _carica()

    def _chiama(self, risposte, **kwargs):
        """`accoda_aspettando` con la coda finta e il sonno finto (nessuno aspetta 60s)."""
        coda = list(risposte)
        chiamate = []
        dormite = []

        def accoda(*args, **kw):
            chiamate.append((args, kw))
            return coda.pop(0) if coda else (429, {"error": "coda piena (24)"})

        job, motivo, atteso = self.mod.accoda_aspettando(
            "http://control-plane", "token", {"scena": "x"}, scena="x", seed=None,
            creatore=False, pausa_s=kwargs.pop("pausa_s", 60.0),
            pazienza_s=kwargs.pop("pazienza_s", 600.0), log=lambda *_a: None,
            accoda=accoda, dormi=dormite.append, **kwargs)
        return job, motivo, atteso, chiamate, dormite

    def test_la_coda_piena_si_aspetta_invece_di_perdere_la_scena(self):
        job, motivo, _atteso, chiamate, dormite = self._chiama([
            (429, {"error": "coda piena (24)"}),
            (429, {"error": "coda piena (24)"}),
            (201, {"ok": True, "job": {"id": "j1"}}),
        ])
        self.assertEqual(job, {"id": "j1"})
        self.assertEqual(motivo, "")
        self.assertEqual(len(chiamate), 3, "ha ritentato?")
        self.assertEqual(dormite, [60.0, 60.0], "fra un tentativo e l'altro si dorme")

    def test_il_ponte_irraggiungibile_per_un_istante_si_ritenta(self):
        """HTTP 0 è ComfyUI o il control-plane che non risponde per un attimo."""
        job, _motivo, _a, _chiamate, dormite = self._chiama([
            (0, {"errore": "connessione rifiutata"}),
            (201, {"ok": True, "job": {"id": "j2"}}),
        ])
        self.assertEqual(job, {"id": "j2"})
        self.assertEqual(len(dormite), 1)

    def test_un_errore_vero_non_si_ritenta(self):
        """Un payload che il server non accetta è un errore, non una coda piena: se si
        ritentasse, alle sei del mattino la serie avrebbe girato per niente."""
        job, motivo, _a, chiamate, dormite = self._chiama([(400, {"error": "prompt non valido"})])
        self.assertIsNone(job)
        self.assertIn("prompt non valido", motivo)
        self.assertEqual(len(chiamate), 1)
        self.assertEqual(dormite, [])

    def test_la_pazienza_finita_dichiara_la_scena_non_accodata(self):
        """Due ore di coda piena vogliono dire che il ponte non macina: si dice e basta."""
        job, motivo, _a, _chiamate, dormite = self._chiama(
            [(429, {"error": "coda piena (24)"})] * 10, pazienza_s=0.0)
        self.assertIsNone(job)
        self.assertIn("coda piena", motivo)
        self.assertEqual(dormite, [], "senza pazienza non si dorme nemmeno una volta")


class AccodamentoTests(unittest.TestCase):
    """Cosa parte davvero: il seed della scena, e la posa dove il ControlNet c'è."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _carica()

    def _run(self, argv):
        """`main` con la coda finta: torna il codice, l'uscita e i payload accodati."""
        accodati = []

        def chiama(url, *args, **kwargs):
            if str(url).endswith("/image/status"):
                return 200, {"ok": True, "in_coda": 0, "in_esecuzione": 0, "max_jobs": 24}
            payload = kwargs.get("payload") or {}
            accodati.append(payload)
            return 201, {"ok": True, "job": {
                "id": "job" + str(len(accodati)),
                "larghezza": payload.get("larghezza"), "altezza": payload.get("altezza"),
                "passi": payload.get("passi"), "seed": payload.get("seed"),
                "fix": payload.get("fix")}}

        cli = self.mod.cli
        originali = cli.token_canale, cli.chiama
        cli.token_canale = lambda *args, **kwargs: "token"
        cli.chiama = chiama
        try:
            uscita = io.StringIO()
            with redirect_stdout(uscita):
                codice = self.mod.main(argv)
        finally:
            cli.token_canale, cli.chiama = originali
        return codice, uscita.getvalue(), accodati

    def test_ogni_scena_porta_il_suo_seed(self):
        """La lezione del 2026-10-01: la scena va passata come argomento, o l'offset del
        seed non si applica e trenta varianti escono con la stessa composizione."""
        codice, testo, accodati = self._run(["--persona", str(ANNA), "--solo", "01,02,03"])
        self.assertEqual(codice, 0, testo)
        self.assertEqual(len(accodati), 3, testo)
        seed = [payload["seed"] for payload in accodati]
        self.assertEqual(len(set(seed)), 3, f"un seed solo per tre scene: {seed}")

    def test_la_posa_arriva_al_job_solo_dove_serve(self):
        """`pose_preset` nel payload è ciò che accende il ControlNet openpose."""
        _codice, _testo, accodati = self._run(
            ["--persona", str(ANNA), "--solo", "01,14,24,29"])
        self.assertEqual(len(accodati), 4)
        self.assertEqual([payload.get("pose_preset") for payload in accodati],
                         ["", "standing", "lying", "arms_open"])

    def test_la_prova_non_tocca_la_coda(self):
        """`--prova` è la mano sul freno: se accodasse, non sarebbe una prova."""
        def vietato(*args, **kwargs):
            raise AssertionError("--prova ha chiamato la coda")

        cli = self.mod.cli
        originali = cli.token_canale, cli.chiama, cli.accoda_ritratto
        cli.token_canale, cli.chiama, cli.accoda_ritratto = vietato, vietato, vietato
        try:
            uscita = io.StringIO()
            with redirect_stdout(uscita):
                codice = self.mod.main(["--persona", str(ANNA), "--prova"])
        finally:
            cli.token_canale, cli.chiama, cli.accoda_ritratto = originali
        self.assertEqual(codice, 0, uscita.getvalue())
        self.assertIn("01-volto-aurora", uscita.getvalue())
        self.assertIn("30-figura-studio", uscita.getvalue())
        # Le trenta scene sono state tutte giudicate: nessuna rifiutata.
        self.assertNotIn("RIFIUTATA", uscita.getvalue())


if __name__ == "__main__":
    unittest.main()
