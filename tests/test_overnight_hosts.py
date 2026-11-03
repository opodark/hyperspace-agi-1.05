# SPDX-License-Identifier: Apache-2.0
"""tests/test_overnight_hosts.py.

Il quadro Mac + OMEN del cockpit: buchi di sleep nel log dello scheduler e conteggio dei cicli
Dev Loop letti sull'OMEN (qui col runner finto, e lo script remoto eseguito davvero in locale).
"""
from __future__ import annotations

import base64
import datetime
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from shared import overnight_hosts as oh


class TestMacSleepGaps(unittest.TestCase):
    def _log(self, lines):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "sched.log"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_regular_ticks_have_no_gap(self):
        p = self._log([f"[scheduler] 2026-11-02T21:{m:02d}:09.1 modo=notte" for m in (3, 8, 13, 18)])
        self.assertEqual(oh.mac_sleep_gaps(p), [])

    def test_overnight_sleep_is_reported_with_hours(self):
        p = self._log([
            "[scheduler] 2026-11-02T21:23:09.273402 modo=notte",
            "[scheduler] 2026-11-02T21:28:09.281086 modo=notte",
            "[scheduler] 2026-11-03T01:54:13.467780 modo=notte",
            "[scheduler] 2026-11-03T06:24:26.376653 modo=notte",
            "[scheduler] avviato, finestra notte 14:00-10:00, controllo ogni 300s",
        ])
        gaps = oh.mac_sleep_gaps(p)
        self.assertEqual([g["hours"] for g in gaps], [4.43, 4.5])
        self.assertEqual(gaps[0]["from"], "2026-11-02T21:28:09")

    def test_missing_log_gives_no_gaps(self):
        self.assertEqual(oh.mac_sleep_gaps(Path("/nonexistent/sched.log")), [])

    def test_since_filters_old_gaps(self):
        p = self._log(["[scheduler] 2026-11-01T01:00:00 modo=notte", "[scheduler] 2026-11-01T05:00:00 modo=notte"])
        self.assertEqual(len(oh.mac_sleep_gaps(p)), 1)
        self.assertEqual(oh.mac_sleep_gaps(p, since=datetime.datetime(2026, 11, 2)), [])


class TestOmenSummary(unittest.TestCase):
    def test_remote_script_counts_cycles_per_hour(self):
        """Lo script che gira sull'OMEN, eseguito davvero su un repo finto."""
        now = datetime.datetime.now(datetime.timezone.utc)
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "data" / "nightly").mkdir(parents=True)
            rows = [now - datetime.timedelta(minutes=m) for m in (5, 10, 15)] + [now - datetime.timedelta(hours=30)]
            (repo / "data" / "omen_dev_loop.jsonl").write_text(
                "\n".join(json.dumps({"timestamp": t.isoformat()}) for t in rows) + "\nnot json\n", encoding="utf-8")
            (repo / "data" / "nightly" / "omen_audit.jsonl").write_text(
                json.dumps({"timestamp": rows[0].isoformat()}) + "\n", encoding="utf-8")
            out = subprocess.run([sys.executable, "-c", oh._REMOTE_SCRIPT, str(repo), "12"],
                                 capture_output=True, text=True, check=True).stdout
        data = json.loads(out)
        self.assertEqual(sum(data["dev_loop_per_hour"].values()), 3)  # il ciclo di 30 h fa e la riga rotta restano fuori
        self.assertEqual(data["sovereign_last_audit"], rows[0].isoformat())

    def test_summary_uses_runner_and_sums_cycles(self):
        seen = {}

        def runner(endpoint, cmd, timeout=30.0):
            seen.update(endpoint=endpoint, cmd=cmd)
            return {"exit_code": 0, "stdout": json.dumps({
                "dev_loop_per_hour": {"2026-11-03T01": 12, "2026-11-03T02": 12},
                "dev_loop_last": "x", "sovereign_last_audit": None}) + "\n"}

        res = oh.omen_overnight_summary(6, runner=runner, endpoint="http://omen:8081")
        self.assertTrue(res["ok"])
        self.assertEqual(res["dev_loop_cycles"], 24)
        self.assertEqual(seen["endpoint"], "http://omen:8081")
        payload = seen["cmd"].split()[1]
        self.assertEqual(base64.b64decode(payload).decode(), oh._REMOTE_SCRIPT)
        self.assertTrue(seen["cmd"].endswith(" /repo 6"))

    def test_unreachable_omen_is_reported_not_raised(self):
        res = oh.omen_overnight_summary(runner=lambda *a, **k: {"error": "timed out", "exit_code": -1}, endpoint="x")
        self.assertEqual(res, {"ok": False, "error": "timed out"})

    def test_non_json_answer_is_an_error(self):
        res = oh.omen_overnight_summary(runner=lambda *a, **k: {"exit_code": 0, "stdout": "boh"}, endpoint="x")
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
