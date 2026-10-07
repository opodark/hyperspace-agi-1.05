# SPDX-License-Identifier: Apache-2.0
import unittest

from shared.intimate_diary import (IntimateDiary, build_intimate_prompt,
                                   destinatario_redatto, filtra_intimo, pagina)


class IntimateDiaryTests(unittest.TestCase):
    def test_prompt_creatore_parte_intimo_e_ruota_i_tre_toni(self):
        prompt = build_intimate_prompt("Ti chiami Anna", livello="creatore")
        self.assertIn("diario intimo e privato", prompt)
        self.assertIn("adulta", prompt)
        self.assertIn("lingerie", prompt)
        self.assertIn("DIDASCALIA", prompt)
        self.assertIn("IMMAGINE", prompt)

        artistico = build_intimate_prompt(
            "Ti chiami Anna", livello="creatore",
            recenti=[{"stato": "delivered", "testo": "prima"}])
        self.assertIn("nudo artistico", artistico)
        self.assertIn("non esplicito", artistico)

        spinto = build_intimate_prompt(
            "Ti chiami Anna", livello="creatore",
            recenti=[{"stato": "delivered", "testo": "prima"},
                     {"stato": "delivered", "testo": "seconda"}])
        self.assertIn("erotica esplicita", spinto)
        self.assertIn("non fermarti", spinto)

    def test_un_fallimento_non_fa_saltare_la_tappa(self):
        prompt = build_intimate_prompt(
            "Ti chiami Anna", livello="creatore",
            recenti=[{"stato": "failed", "testo": "non consegnata"}])
        self.assertIn("intima e sensuale", prompt)

    def test_filtro_richiede_testo_e_immagine_e_blocca_minori(self):
        self.assertFalse(filtra_intimo({"caption": "ciao", "image_prompt": ""})[0])
        self.assertFalse(filtra_intimo(
            {"caption": "ciao", "image_prompt": "schoolgirl"})[0])
        self.assertTrue(filtra_intimo(
            {"caption": "ciao", "image_prompt": "adult virtual woman"})[0])

    def test_store_collega_job_e_consegna(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "intimo.json"
            store = IntimateDiary()
            store.add(pagina(id="intimo-1", author="anna", livello="creatore", testo="x",
                             prompt="y", destinatario="instagram:…1234", job_id="job-1"))
            self.assertEqual(store.by_job("job-1")["stato"], "queued")
            store.conclude_job("job-1", file="HyperSpace/x.jpg", delivered=True)
            store.save(str(path))
            loaded = IntimateDiary.load(str(path))
            self.assertEqual(loaded.by_job("job-1")["stato"], "delivered")
            self.assertEqual(loaded.by_job("job-1")["file"], "HyperSpace/x.jpg")

    def test_destinatario_viene_redatto(self):
        self.assertEqual(destinatario_redatto("123456789"), "instagram:…6789")


if __name__ == "__main__":
    unittest.main()
