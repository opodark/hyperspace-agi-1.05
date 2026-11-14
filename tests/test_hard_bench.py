# SPDX-License-Identifier: Apache-2.0
"""Test per scripts/hard_bench.py (problemi procedurali verificati da codice)."""

import unittest

from scripts import hard_bench as hb


class GenerationTests(unittest.TestCase):
    def test_deterministico_dal_seed(self):
        a = hb.make_items(2, 7)
        b = hb.make_items(2, 7)
        self.assertEqual(a, b)
        self.assertNotEqual(a, hb.make_items(2, 8))
        self.assertEqual(len(a), 2 * len(hb.FAMILIES) * len(hb.LEVELS))

    def test_la_risposta_attesa_passa_il_verificatore(self):
        for it in hb.make_items(2, 3):
            if it["family"] == "coloring":
                continue
            self.assertTrue(hb.check(it, f"ragiono...\nANSWER: {it['data']['expected']}"), it["id"])
            self.assertFalse(hb.check(it, "ANSWER: 0 0 0 zzz"), it["id"])
            self.assertFalse(hb.check(it, "nessuna riga finale"), it["id"])

    def test_coloring_accetta_qualunque_soluzione_valida(self):
        it = next(i for i in hb.make_items(1, 5) if i["family"] == "coloring" and i["level"] == 1)
        n, edges = it["data"]["n"], it["data"]["edges"]
        # colora a forza bruta una soluzione valida (backtracking) e verifica che passi
        col = [None] * n

        def solve(k):
            if k == n:
                return True
            for c in "RGB":
                if all(col[u] != c for u, v in edges if v == k and col[u] is not None) and \
                   all(col[v] != c for u, v in edges if u == k and col[v] is not None):
                    col[k] = c
                    if solve(k + 1):
                        return True
                    col[k] = None
            return False

        self.assertTrue(solve(0))
        self.assertTrue(hb.check(it, "ANSWER: " + " ".join(col)))
        bad = col[:]
        u, v = edges[0]
        bad[u] = bad[v]
        self.assertFalse(hb.check(it, "ANSWER: " + " ".join(bad)))
        self.assertFalse(hb.check(it, "ANSWER: R G"))  # lunghezza sbagliata

    def test_estrazione_prende_l_ultima_riga(self):
        self.assertEqual(hb.extract_answer("ANSWER: 1\nbla\nanswer: **42**"), "42")
        self.assertIsNone(hb.extract_answer("il risultato e' 42"))


class ReportTests(unittest.TestCase):
    def test_errori_di_rete_non_contano_come_sbagliate(self):
        rows = [
            {"model": "m", "family": "arith", "level": 1, "correct": True, "error": None},
            {"model": "m", "family": "arith", "level": 1, "correct": False, "error": "503"},
        ]
        text = hb.render_report({"m": rows})
        self.assertIn("100% (1) +1 err", text)


if __name__ == "__main__":
    unittest.main()
