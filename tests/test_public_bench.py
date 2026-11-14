# SPDX-License-Identifier: Apache-2.0
"""Test per scripts/public_bench.py (confronto pubblico verificabile)."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts import public_bench as pb

TARGET = {
    "name": "t", "kind": "frontier", "model_type": "local-chat-completions",
    "key_env": "MY_KEY", "model_args": {"model": "m", "base_url": "http://x/v1/chat/completions"},
    "gen_kwargs": {"max_gen_toks": 100},
}


class CommandTests(unittest.TestCase):
    def test_comando_deterministico_e_con_campioni(self):
        a = pb.build_command(TARGET, ["ifeval"], Path("out"), None, 7)
        b = pb.build_command(TARGET, ["ifeval"], Path("out"), None, 7)
        self.assertEqual(a, b)
        self.assertIn("--log_samples", a)
        self.assertIn("--apply_chat_template", a)
        self.assertIn("temperature=0,until=</s>,max_gen_toks=100", a)
        self.assertNotIn("--limit", a)
        self.assertIn("--limit", pb.build_command(TARGET, ["ifeval"], Path("out"), 5, 7))

    def test_manifesto_senza_segreti(self):
        cmd = pb.build_command(TARGET, ["ifeval"], Path("out"))
        m = pb.build_manifest(TARGET, ["ifeval"], cmd, None, 1)
        blob = json.dumps(m)
        self.assertEqual(m["key_env"], "MY_KEY")
        self.assertTrue(m["full_run"])
        env = {"MY_KEY": "segretissimo"}
        self.assertNotIn("segretissimo", blob)
        self.assertEqual(pb.target_env(TARGET, env)["OPENAI_API_KEY"], "segretissimo")

    def test_chiave_mancante_ferma_il_giro(self):
        with self.assertRaises(RuntimeError):
            pb.target_env(TARGET, {})

    def test_placeholder_bloccano(self):
        t = {**TARGET, "model_args": {"model": "FILL_ME"}}
        self.assertEqual(pb.placeholders_left(t), ["model_args.model"])
        self.assertEqual(pb.placeholders_left(TARGET), [])


class ScoringTests(unittest.TestCase):
    def test_metrica_attesa_e_ripiego_dichiarato(self):
        res = {"results": {"ifeval": {"prompt_level_strict_acc,none": 0.75},
                           "gsm8k": {"exact_match,other": 0.5, "exact_match_stderr,other": 0.01}}}
        self.assertEqual(pb.extract_metric(res, "ifeval"), (75.0, "prompt_level_strict_acc,none"))
        pct, name = pb.extract_metric(res, "gsm8k")
        self.assertEqual(pct, 50.0)
        self.assertIn("ripiego", name)
        self.assertIsNone(pb.extract_metric(res, "assente"))

    def test_verdetto_a_margine_fisso(self):
        self.assertEqual(pb.verdict(80, 82), "pareggio")
        self.assertEqual(pb.verdict(70, 82), "sconfitta")
        self.assertEqual(pb.verdict(90, 82), "vittoria")
        self.assertEqual(pb.verdict(79, 82, 3.0), "pareggio")  # bordo incluso
        self.assertEqual(pb.verdict(78.9, 82, 3.0), "sconfitta")


class ReportTests(unittest.TestCase):
    def _run(self, root, name, kind, score, full=True):
        d = Path(root) / name
        d.mkdir()
        man = {"target": name, "kind": kind, "tasks": ["gsm8k"], "declared_reasoning": "x",
               "full_run": full, "lm_eval_version": "v", "repo_commit": "abcdef0123456",
               "seed": 1, "gen_kwargs": {"temperature": 0}}
        (d / "manifest.json").write_text(json.dumps(man))
        (d / "results_1.json").write_text(json.dumps(
            {"results": {"gsm8k": {"exact_match,strict-match": score}}}))

    def test_report_con_previsioni_e_giro_parziale(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, "sys", "system", 0.90)
            self._run(tmp, "fr", "frontier", 0.95, full=False)
            runs = pb.load_run(Path(tmp))
            preds = {"margin_points": 3.0, "predictions": {"gsm8k": {"utente": "non-sconfitta", "claude": "sconfitta"}}}
            text = pb.render_report(runs, preds)
        self.assertIn("NON e' un risultato", text)
        self.assertIn("sconfitta", text)
        self.assertIn("Previsioni di **utente** centrate: 0/1", text)
        self.assertIn("Previsioni di **claude** centrate: 1/1", text)



class ProxyTests(unittest.TestCase):
    def test_toglie_solo_il_seed(self):
        from scripts import public_bench_proxy as px
        body = {"model": "m", "seed": 1, "temperature": 0, "messages": [{"role": "user", "content": "x"}]}
        out = px.clean_payload(body)
        self.assertNotIn("seed", out)
        self.assertEqual(out["messages"], body["messages"])
        self.assertEqual(out["temperature"], 0)
        self.assertIn("seed", body)  # l'originale non e' modificato


if __name__ == "__main__":
    unittest.main()
