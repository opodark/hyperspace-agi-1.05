# SPDX-License-Identifier: Apache-2.0
"""Test suite per scripts/frontier_bench.py (00MESH vs Frontier Quality Audit)."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts import frontier_bench as fb


class FrontierJudgesTests(unittest.TestCase):
    def test_valuta_ragionamento(self):
        score, nota = fb.valuta_ragionamento("NO, lo Salamandroide non puo' essere un rettile.")
        self.assertEqual(score, 10.0)
        self.assertIn("non e' un rettile", nota)

        score, nota = fb.valuta_ragionamento("SI, certamente e' un rettile.")
        self.assertEqual(score, 0.0)
        self.assertIn("errata", nota)

        score, _nota = fb.valuta_ragionamento("Potrebbe essere o non essere.")
        self.assertEqual(score, 4.0)

    def test_valuta_matematica(self):
        # 1512 + 648 = 2160 euro
        score, _nota = fb.valuta_matematica("L'incasso totale complessivo e' di 2160 euro.")
        self.assertEqual(score, 10.0)

        score, _nota = fb.valuta_matematica("L'incasso e' di 2.160 euro.")
        self.assertEqual(score, 10.0)

        score, nota = fb.valuta_matematica("Il primo lotto da' 1512 euro e il secondo 648 euro ma non so sommare.")
        self.assertEqual(score, 7.0)
        self.assertIn("parziali", nota)

        score, _nota = fb.valuta_matematica("Il totale e' 5000 euro.")
        self.assertEqual(score, 1.0)

    def test_valuta_coding_contratto(self):
        codice_buono = """
```python
def comprimi_serie(valori):
    if not valori:
        return []
    risultato = []
    curr = valori[0]
    count = 1
    for v in valori[1:]:
        if v == curr:
            count += 1
        else:
            risultato.append((curr, count))
            curr = v
            count = 1
    risultato.append((curr, count))
    return risultato
```
"""
        score, nota = fb.valuta_coding(codice_buono)
        self.assertEqual(score, 10.0)
        self.assertIn("superati", nota)

        codice_errato = "def comprimi_serie(valori):\n    return []\n"
        score, nota = fb.valuta_coding(codice_errato)
        self.assertEqual(score, 4.0)
        self.assertIn("fallito test", nota)

    def test_valuta_allucinazioni(self):
        r_onesta = "Questo evento non e' mai avvenuto e non esiste alcun trattato di Neo-Bologna del 1974."
        score, nota = fb.valuta_allucinazioni(r_onesta)
        self.assertEqual(score, 10.0)
        self.assertIn("fittizio", nota)

        r_allucinata = "I tre articoli del trattato firmato nel 1974 stabiliva che le Alpi fossero smilitarizzate."
        score, nota = fb.valuta_allucinazioni(r_allucinata)
        self.assertEqual(score, 0.0)
        self.assertIn("allucinazione confermata", nota)

    def test_valuta_ambiguita(self):
        r_critica = ("Per dare una risposta motivata mancano tre fattori essenziali:\n"
                     "1. La distanza e la tratta specifica.\n"
                     "2. Il budget e il costo del biglietto.\n"
                     "3. Il tempo a disposizione e le emissioni di CO2.")
        score, nota = fb.valuta_ambiguita(r_critica)
        self.assertEqual(score, 10.0)
        self.assertIn("fattori decisivi", nota)

        r_arbitraria = "Il treno e' meglio in assoluto perche' e' comodo."
        score, nota = fb.valuta_ambiguita(r_arbitraria)
        self.assertEqual(score, 2.0)
        self.assertIn("arbitraria", nota)

    def test_valuta_vincolo_negativo(self):
        # 4 frasi senza lettera 'e'
        senza_e = "Un raggio di luna illumina la roccia scura. Soffia un alito rigido tra i pini. In alto brillano miriadi di astri. Il buio assoluto avvolga la cima pura."
        score, nota = fb.valuta_vincolo_negativo(senza_e)
        self.assertEqual(score, 10.0)
        self.assertIn("0 lettere 'e'", nota)

        con_e = "La notte e' molto bella e serena sulle montagne innevate. I lupi ululano nel bosco fitto. Il cielo risplende di stelle."
        score, nota = fb.valuta_vincolo_negativo(con_e)
        self.assertLess(score, 5.0)
        self.assertIn("lettere 'e'", nota)

    def test_valuta_needle(self):
        score, _nota = fb.valuta_needle("La chiave di sblocco e' OMEGA-774-VALVOLA-BLU.")
        self.assertEqual(score, 10.0)

        score, _nota = fb.valuta_needle("Non ho trovato alcuna chiave nel testo.")
        self.assertEqual(score, 0.0)

    def test_valuta_bug_mutabile(self):
        r_esperta = ("Il bug e' dovuto al default argument mutabile promo={'sconto': 10}. "
                     "Il dizionario viene condiviso tra le chiamate successive e accumula modifiche. "
                     "Si corregge impostando promo=None di default.")
        score, _nota = fb.valuta_bug(r_esperta)
        self.assertEqual(score, 10.0)

        r_superficiale = "Il codice e' perfetto e calcola lo sconto correttamente."
        score, _nota = fb.valuta_bug(r_superficiale)
        self.assertEqual(score, 1.0)

    def test_valuta_system_design(self):
        r_arch = ("Per evitare blocchi usiamo un modello asincrono basato su code di messaggi ed outbox. "
                  "Ogni messaggio ha chiavi di idempotenza per gestire i retry senza duplicazioni. "
                  "Un meccanismo di heartbeat rileva nodi isolati garantendo l'isolamento della partizione.")
        score, _nota = fb.valuta_system_design(r_arch)
        self.assertEqual(score, 10.0)

    def test_valuta_tool_calling(self):
        chiamata_valida = '{"tool": "deploy_node", "parameters": {"node_alias": "hpomen", "force_restart": true, "timeout_sec": 60}}'
        score, _nota = fb.valuta_tool_calling(chiamata_valida)
        self.assertEqual(score, 10.0)

        con_markdown = f"```json\n{chiamata_valida}\n```"
        score, nota = fb.valuta_tool_calling(con_markdown)
        self.assertEqual(score, 3.0)
        self.assertIn("markdown", nota)

        con_chatter = f"Ecco la chiamata richiesta: {chiamata_valida}"
        score, nota = fb.valuta_tool_calling(con_chatter)
        self.assertEqual(score, 2.0)
        self.assertIn("chatter", nota)


class ScoringAndReportsTests(unittest.TestCase):
    def test_calcola_fqi(self):
        punteggi = {f"asse_{i}": 8.0 for i in range(10)}
        fqi = fb.calcola_fqi(punteggi)
        self.assertEqual(fqi, 80.0)

    def test_determina_verdetto_sovranita(self):
        punteggi_top = {f"asse_{i}": 9.5 for i in range(10)}
        v_top = fb.determina_verdetto_sovranita(-0.2, punteggi_top)
        self.assertIn("SOVRANITA' PIENA", v_top)

        punteggi_mid = {f"asse_{i}": 7.5 for i in range(10)}
        v_mid = fb.determina_verdetto_sovranita(-1.8, punteggi_mid)
        self.assertIn("EFFICACE CON SUPERVISIONE", v_mid)

        punteggi_low = {f"asse_{i}": 4.0 for i in range(10)}
        v_low = fb.determina_verdetto_sovranita(-5.0, punteggi_low)
        self.assertIn("DELEGA CONSIGLIATA", v_low)

    def test_radar_table_and_markdown_export(self):
        punteggi = {nome: 8.5 for nome, _, _, _ in fb.AUDIT_SUITE}
        tabella = fb.genera_tabella_radar("test-model", punteggi, "Claude-3.5-Sonnet")
        self.assertIn("INDICE QUALITA GLOBALE", tabella)
        self.assertIn("test-model", tabella)

        with tempfile.TemporaryDirectory() as tmpdir:
            md_path = Path(tmpdir) / "report.md"
            dettagli = {
                nome: {"score": 8.5, "nota": "ok", "durata": 1.2, "risposta": "risposta test"}
                for nome, _, _, _ in fb.AUDIT_SUITE
            }
            report_data = {
                "modello": "test-model",
                "timestamp": 12345,
                "dettagli": dettagli,
            }
            fb.esporta_report_markdown("test-model", report_data, md_path)
            self.assertTrue(md_path.exists())
            testo = md_path.read_text(encoding="utf-8")
            self.assertIn("Benchmark Qualitativo di Frontiera", testo)
            self.assertIn("Claude 3.5 Sonnet", testo)


class ParserTests(unittest.TestCase):
    def test_parser(self):
        p = fb.build_parser()
        args = p.parse_args(["--model", "flint:latest", "--compare-with", "Gemini-1.5-Pro"])
        self.assertEqual(args.model, "flint:latest")
        self.assertEqual(args.compare_with, "Gemini-1.5-Pro")


if __name__ == "__main__":
    unittest.main()
