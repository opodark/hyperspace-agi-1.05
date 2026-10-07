# SPDX-License-Identifier: Apache-2.0
"""Le quattro prove di colore: un vestito, un fondo e una posa diversi in ognuna.

Il caso che questi test difendono (2026-10-02): la serie notturna è uscita slavata perché
l'adattatore del volto portava dentro il **fondo verde** del riferimento su *tutti* i
passi. Le prove servono a misurare dove finisce il colore, e valgono solo se ognuna chiede
**due** tinte su lati opposti della ruota — un abito e un fondo — con la luce **neutra**,
così le uniche sorgenti di colore sono quelle due. Una prova con le stesse parole di
un'altra è una prova sola pagata due volte: il test guarda le scene una per una, come
`test_serie_anna.py` fa con le trenta della notte.

L'altro patto è il motore: le prove girano su `scripts/serie_anna.py`, e chi importa le
prove non deve trovarsi le trenta scene cambiate sotto.
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

SCRIPT = ROOT / "scripts" / "prova_colori_anna.py"
ANNA = ROOT / "data" / "persona-anna.json"

# I due colori di ogni prova: uno addosso e uno alle spalle. Sono le parole che il test
# conta — caldo contro freddo, e la 34 senza fondo colorato (il grigio è il neutro).
VESTITI = ("crimson", "violet", "teal", "magenta")
SFONDI = ("indigo", "ochre", "terracotta", "grey")
POSE = ("standing", "seated", "walking", "lying")


def _carica():
    specifica = importlib.util.spec_from_file_location("prova_colori_sotto_test", SCRIPT)
    modulo = importlib.util.module_from_spec(specifica)
    specifica.loader.exec_module(modulo)
    return modulo


class ProvaColoriTests(unittest.TestCase):
    """Le quattro prove: numerate, distinte, e tutte dentro il confine del documento."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _carica()
        cls.documento = json.loads(ANNA.read_text(encoding="utf-8"))
        cls.vetrina = vetrina_dal_documento(cls.documento)

    def test_sono_quattro_numerate_e_distinte(self):
        """I numeri continuano la serie (31–34): sono un seguito, non un'altra serie."""
        prove = self.mod.PROVE
        self.assertEqual(len(prove), 4)
        self.assertEqual([nome.split("-")[0] for nome, _s, _p in prove], ["31", "32", "33", "34"])
        self.assertEqual(len({nome for nome, _s, _p in prove}), 4)
        self.assertEqual(len({scena for _n, scena, _p in prove}), 4,
                         "due prove identiche sono una prova sola pagata due volte")

    def test_ogni_prova_ha_un_vestito_e_un_fondo_diversi(self):
        """Un colore ripetuto non dice niente di nuovo: le due tinte cambiano sempre."""
        vestiti, sfondi = [], []
        for nome, scena, _posa in self.mod.PROVE:
            testo = scena.lower()
            addosso = [colore for colore in VESTITI if colore in testo]
            dietro = [colore for colore in SFONDI if colore in testo]
            self.assertEqual(len(addosso), 1, f"{nome}: vestito dichiarato {addosso}")
            self.assertEqual(len(dietro), 1, f"{nome}: fondo dichiarato {dietro}")
            vestiti.append(addosso[0])
            sfondi.append(dietro[0])
        self.assertEqual(sorted(vestiti), sorted(VESTITI), f"vestiti ripetuti: {vestiti}")
        self.assertEqual(sorted(sfondi), sorted(SFONDI), f"fondi ripetuti: {sfondi}")

    def test_la_luce_resta_neutra(self):
        """Se la luce portasse colore, la prova non direbbe chi ha deciso la tinta."""
        for nome, scena, _posa in self.mod.PROVE:
            self.assertIn("neutral", scena.lower(),
                          f"{nome}: senza una luce neutra non si sa chi ha deciso il colore")

    def test_ogni_prova_ha_una_posa_diversa(self):
        """Quattro pose, una per famiglia: la posa è il terzo pezzo della prova."""
        pose = [posa for _n, _s, posa in self.mod.PROVE]
        self.assertEqual(sorted(pose), sorted(POSE), f"pose usate: {pose}")
        for posa in pose:
            self.assertIn(posa, POSE_PRESET)

    def test_ogni_prova_passa_il_confine_di_anna(self):
        """Nessuna eccezione: una prova rifiutata è una prova che manca."""
        rifiutate = []
        for nome, scena, posa in self.mod.PROVE:
            variante = {**self.vetrina, "scena": scena,
                        "pose_preset": self.mod.serie_anna.posa_da_mandare(self.vetrina, posa)}
            problemi = verifica_vetrina(variante, self.documento)
            if problemi:
                rifiutate.append(f"{nome}: {problemi}")
        self.assertEqual(rifiutate, [], "prove che il documento di Anna non permette")

    def test_nessuna_prova_contiene_una_parola_vietata(self):
        """Si usa `conflitti`, la stessa funzione del confine vero, non un elenco ricopiato."""
        for nome, scena, _posa in self.mod.PROVE:
            self.assertEqual(conflitti(scena, VIETATI_ASSOLUTI), [],
                             f"{nome}: parola vietata nella scena")

    def test_il_motore_e_quello_della_serie_e_le_scene_tornano_a_posto(self):
        """`main` scambia le scene e le rimette a posto: chi importa dopo non se ne accorge.

        La coda finta è quella di `test_serie_anna.py`: se `--prova` chiamasse il canale,
        questo test fallirebbe col messaggio di `vietato`, non con un timeout di rete.
        """
        def vietato(*args, **kwargs):
            raise AssertionError("--prova ha chiamato la coda")

        cli = self.mod.serie_anna.cli
        originali = cli.token_canale, cli.chiama, cli.accoda_ritratto
        cli.token_canale, cli.chiama, cli.accoda_ritratto = vietato, vietato, vietato
        try:
            uscita = io.StringIO()
            with redirect_stdout(uscita):
                codice = self.mod.main(["--persona", str(ANNA), "--prova"])
        finally:
            cli.token_canale, cli.chiama, cli.accoda_ritratto = originali
        self.assertEqual(codice, 0, uscita.getvalue())
        testo = uscita.getvalue()
        for nome, _s, _p in self.mod.PROVE:
            self.assertIn(nome, testo)
        self.assertNotIn("01-volto-aurora", testo, "ha girato la serie al posto delle prove")
        self.assertNotIn("RIFIUTATA", testo)
        self.assertEqual(len(self.mod.serie_anna.SCENE), 30,
                         "le trenta scene della serie sono rimaste cambiate")


if __name__ == "__main__":
    unittest.main()

