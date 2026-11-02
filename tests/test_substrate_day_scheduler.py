# SPDX-License-Identifier: Apache-2.0
"""tests/test_substrate_day_scheduler.py.

Verifica scripts/substrate_day_scheduler.py: finestra notte/giorno, e che tick() avvii o
fermi il demone R&D solo alla transizione (non ad ogni giro) e lanci la batteria diurna solo
al passare dell'intervallo.
"""
from __future__ import annotations

import datetime
import unittest
from unittest.mock import patch

from scripts import substrate_day_scheduler as sched


class TestNightWindow(unittest.TestCase):
    def test_window_not_crossing_midnight(self):
        self.assertTrue(sched.is_night_hour(22, start=21, end=7))
        self.assertFalse(sched.is_night_hour(10, start=0, end=6))  # 10 fuori da 0-6

    def test_window_crossing_midnight(self):
        # finestra 21:00-07:00: 23, 2, 6 sono notte; 7, 12, 20 sono giorno
        for h in (21, 23, 0, 2, 6):
            self.assertTrue(sched.is_night_hour(h, start=21, end=7), h)
        for h in (7, 12, 20):
            self.assertFalse(sched.is_night_hour(h, start=21, end=7), h)

    def test_current_mode_reads_the_clock(self):
        notte = datetime.datetime(2026, 11, 2, 23, 0)
        giorno = datetime.datetime(2026, 11, 2, 12, 0)
        with patch.object(sched, "NIGHT_START_HOUR", 21), patch.object(sched, "NIGHT_END_HOUR", 7):
            self.assertEqual(sched.current_mode(notte), "notte")
            self.assertEqual(sched.current_mode(giorno), "giorno")


class TestTickTransitions(unittest.TestCase):
    def test_entering_night_starts_daemon_once(self):
        with patch.object(sched, "current_mode", return_value="notte"), \
             patch.object(sched, "start_nightly_daemon") as mock_start, \
             patch.object(sched, "stop_nightly_daemon") as mock_stop, \
             patch.object(sched, "run_day_battery") as mock_battery:
            mode, ts = sched.tick(last_mode="giorno", last_battery_ts=0.0)
            self.assertEqual(mode, "notte")
            mock_start.assert_called_once()
            mock_stop.assert_not_called()
            mock_battery.assert_not_called()

    def test_staying_in_night_does_not_restart_daemon(self):
        with patch.object(sched, "current_mode", return_value="notte"), \
             patch.object(sched, "start_nightly_daemon") as mock_start, \
             patch.object(sched, "stop_nightly_daemon") as mock_stop:
            sched.tick(last_mode="notte", last_battery_ts=0.0)
            mock_start.assert_not_called()
            mock_stop.assert_not_called()

    def test_entering_day_stops_daemon_and_runs_battery(self):
        with patch.object(sched, "current_mode", return_value="giorno"), \
             patch.object(sched, "start_nightly_daemon") as mock_start, \
             patch.object(sched, "stop_nightly_daemon") as mock_stop, \
             patch.object(sched, "run_day_battery") as mock_battery, \
             patch("time.time", return_value=1000.0):
            mode, ts = sched.tick(last_mode="notte", last_battery_ts=0.0)
            self.assertEqual(mode, "giorno")
            mock_stop.assert_called_once()
            mock_start.assert_not_called()
            mock_battery.assert_called_once()
            self.assertEqual(ts, 1000.0)

    def test_day_battery_runs_only_after_interval_elapses(self):
        with patch.object(sched, "current_mode", return_value="giorno"), \
             patch.object(sched, "start_nightly_daemon"), \
             patch.object(sched, "stop_nightly_daemon"), \
             patch.object(sched, "run_day_battery") as mock_battery, \
             patch.object(sched, "BATTERY_INTERVAL_S", 3600), \
             patch("time.time", return_value=1800.0):
            # già in giorno da prima (last_mode="giorno"), ultima batteria 1000s fa < 3600s
            sched.tick(last_mode="giorno", last_battery_ts=1000.0)
            mock_battery.assert_not_called()

        with patch.object(sched, "current_mode", return_value="giorno"), \
             patch.object(sched, "start_nightly_daemon"), \
             patch.object(sched, "stop_nightly_daemon"), \
             patch.object(sched, "run_day_battery") as mock_battery, \
             patch.object(sched, "BATTERY_INTERVAL_S", 3600), \
             patch("time.time", return_value=5000.0):
            sched.tick(last_mode="giorno", last_battery_ts=1000.0)
            mock_battery.assert_called_once()


class TestDaemonLookup(unittest.TestCase):
    def test_find_pid_excludes_self_and_parses_pgrep_output(self):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = f"{sched.os.getpid()}\n4242\n"
            pid = sched._find_nightly_daemon_pid()
        self.assertEqual(pid, 4242)

    def test_find_pid_none_when_pgrep_missing(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(sched._find_nightly_daemon_pid())

    def test_stop_returns_false_when_not_running(self):
        with patch.object(sched, "_find_nightly_daemon_pid", return_value=None):
            self.assertFalse(sched.stop_nightly_daemon())

    def test_start_returns_false_when_already_running(self):
        with patch.object(sched, "_find_nightly_daemon_pid", return_value=123):
            self.assertFalse(sched.start_nightly_daemon())


if __name__ == "__main__":
    unittest.main()
