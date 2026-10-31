# SPDX-License-Identifier: Apache-2.0
# tests/test_mobile_gate.py
"""Nodo mobile (Android/Termux): lettura batteria e gate di lavoro."""

import sys
import unittest
from datetime import time as dtime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import power_sense
from shared.mobile_gate import (
    REASON_BATTERY_LOW,
    REASON_FAILOVER_ONLY,
    REASON_NOT_PLUGGED,
    REASON_OUTSIDE_WINDOW,
    REASON_TOO_HOT,
    MobileGate,
    MobileGateConfig,
    evaluate_mobile_gate,
    in_window,
    parse_window,
)

PLUGGED_COOL = {"ac_line": True, "battery_pct": 80.0, "temperature_c": 33.0}


class TestTermuxBattery(unittest.TestCase):
    def test_plugged_and_charging(self):
        res = power_sense._map_termux_battery({
            "health": "GOOD", "percentage": 64, "plugged": "PLUGGED_AC",
            "status": "CHARGING", "temperature": 31.4,
        })
        self.assertTrue(res["ac_line"])
        self.assertTrue(res["charging"])
        self.assertFalse(res["discharging"])
        self.assertEqual(res["battery_pct"], 64.0)
        self.assertEqual(res["temperature_c"], 31.4)
        self.assertEqual(res["source"], "termux_api")

    def test_samsung_protect_battery_counts_as_plugged(self):
        """Carica ferma all'80%: collegato ma NOT_CHARGING, non sta scaricando."""
        res = power_sense._map_termux_battery({
            "percentage": 80, "plugged": "PLUGGED_USB", "status": "NOT_CHARGING",
        })
        self.assertTrue(res["ac_line"])
        self.assertFalse(res["charging"])
        self.assertFalse(res["discharging"])

    def test_unplugged(self):
        res = power_sense._map_termux_battery({
            "percentage": 55, "plugged": "UNPLUGGED", "status": "DISCHARGING",
        })
        self.assertFalse(res["ac_line"])
        self.assertTrue(res["discharging"])

    def test_garbage_is_ignored(self):
        self.assertIsNone(power_sense._map_termux_battery({}))
        self.assertIsNone(power_sense._map_termux_battery("x"))

    def test_android_unknown_power_is_never_ac(self):
        """Su Android senza Termux:API il nodo non deve credersi alla presa."""
        with mock.patch.object(power_sense, "is_android", return_value=True), \
             mock.patch.object(power_sense, "_parse_termux_battery", return_value=None), \
             mock.patch.object(power_sense, "_parse_linux_sysfs", return_value=None), \
             mock.patch.object(power_sense, "_read_host_power_file", return_value=None):
            res = power_sense.detect_host_power()
        self.assertFalse(res["ac_line"])
        self.assertEqual(res["source"], "android_unknown")

    def test_android_uses_termux_first(self):
        fake = {"ac_line": True, "battery_pct": 90.0, "source": "termux_api"}
        with mock.patch.object(power_sense, "is_android", return_value=True), \
             mock.patch.object(power_sense, "_parse_termux_battery", return_value=fake), \
             mock.patch.object(power_sense, "_read_host_power_file", return_value=None):
            self.assertEqual(power_sense.detect_host_power()["source"], "termux_api")


class TestWindow(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_window("23:00-07:00"), (dtime(23, 0), dtime(7, 0)))
        self.assertIsNone(parse_window(""))
        self.assertIsNone(parse_window("notte"))
        self.assertIsNone(parse_window("08:00-08:00"))

    def test_overnight_window(self):
        w = parse_window("23:00-07:00")
        self.assertTrue(in_window(dtime(23, 30), w))
        self.assertTrue(in_window(dtime(3, 0), w))
        self.assertFalse(in_window(dtime(7, 0), w))
        self.assertFalse(in_window(dtime(13, 0), w))

    def test_daytime_window(self):
        w = parse_window("09:00-18:00")
        self.assertTrue(in_window(dtime(9, 0), w))
        self.assertFalse(in_window(dtime(18, 0), w))

    def test_no_window_is_always(self):
        self.assertTrue(in_window(dtime(13, 0), None))


class TestGate(unittest.TestCase):
    def setUp(self):
        self.cfg = MobileGateConfig()

    def test_open_when_plugged_and_cool(self):
        res = evaluate_mobile_gate(PLUGGED_COOL, self.cfg, now=dtime(2, 0))
        self.assertTrue(res["open"])
        self.assertEqual(res["reasons"], [])

    def test_closed_on_battery(self):
        res = evaluate_mobile_gate({**PLUGGED_COOL, "ac_line": False}, self.cfg, now=dtime(2, 0))
        self.assertFalse(res["open"])
        self.assertIn(REASON_NOT_PLUGGED, res["reasons"])

    def test_charger_optional(self):
        cfg = MobileGateConfig(require_charger=False)
        res = evaluate_mobile_gate({**PLUGGED_COOL, "ac_line": False}, cfg, now=dtime(2, 0))
        self.assertTrue(res["open"])

    def test_closed_when_battery_low_even_plugged(self):
        res = evaluate_mobile_gate({**PLUGGED_COOL, "battery_pct": 25.0}, self.cfg, now=dtime(2, 0))
        self.assertIn(REASON_BATTERY_LOW, res["reasons"])

    def test_missing_power_closes_gate(self):
        res = evaluate_mobile_gate(None, self.cfg, now=dtime(2, 0))
        self.assertFalse(res["open"])

    def test_thermal_hysteresis(self):
        hot = evaluate_mobile_gate({**PLUGGED_COOL, "temperature_c": 41.5}, self.cfg, now=dtime(2, 0))
        self.assertIn(REASON_TOO_HOT, hot["reasons"])
        # 39.5 °C: sotto la soglia di stop ma sopra quella di ripartenza
        still = evaluate_mobile_gate({**PLUGGED_COOL, "temperature_c": 39.5}, self.cfg,
                                     now=dtime(2, 0), was_hot=True)
        self.assertFalse(still["open"])
        cooled = evaluate_mobile_gate({**PLUGGED_COOL, "temperature_c": 37.5}, self.cfg,
                                      now=dtime(2, 0), was_hot=True)
        self.assertTrue(cooled["open"])
        # senza storia di surriscaldamento 39.5 °C va bene
        fresh = evaluate_mobile_gate({**PLUGGED_COOL, "temperature_c": 39.5}, self.cfg, now=dtime(2, 0))
        self.assertTrue(fresh["open"])

    def test_outside_window(self):
        cfg = MobileGateConfig(window=parse_window("23:00-07:00"), window_spec="23:00-07:00")
        res = evaluate_mobile_gate(PLUGGED_COOL, cfg, now=dtime(14, 0))
        self.assertEqual(res["reasons"], [REASON_OUTSIDE_WINDOW])

    def test_from_env(self):
        env = {"MOBILE_WORK_WINDOW": "23:00-07:00", "MOBILE_MIN_BATTERY_PCT": "60",
               "MOBILE_REQUIRE_CHARGER": "off", "MOBILE_MAX_TEMP_C": "40",
               "MOBILE_RESUME_TEMP_C": "45"}
        with mock.patch.dict("os.environ", env):
            cfg = MobileGateConfig.from_env()
        self.assertEqual(cfg.window_spec, "23:00-07:00")
        self.assertEqual(cfg.min_battery_pct, 60.0)
        self.assertFalse(cfg.require_charger)
        self.assertEqual(cfg.resume_temp_c, 40.0)  # mai sopra la soglia di stop


class TestMobileGateRuntime(unittest.TestCase):
    def test_hysteresis_kept_between_refreshes(self):
        readings = iter([
            {**PLUGGED_COOL, "temperature_c": 42.0},
            {**PLUGGED_COOL, "temperature_c": 39.0},
            {**PLUGGED_COOL, "temperature_c": 37.0},
        ])
        gate = MobileGate(MobileGateConfig(), lambda: next(readings), clock=lambda: dtime(2, 0))
        self.assertFalse(gate.refresh()["open"])
        self.assertFalse(gate.refresh()["open"])
        self.assertTrue(gate.refresh()["open"])

    def test_disabled_gate_always_open(self):
        gate = MobileGate(MobileGateConfig(), lambda: {"ac_line": False}, enabled=False)
        self.assertTrue(gate.allows_work())

    def test_power_errors_close_the_gate(self):
        def boom():
            raise RuntimeError("termux-api assente")
        gate = MobileGate(MobileGateConfig(), boom, clock=lambda: dtime(2, 0))
        self.assertFalse(gate.allows_work())


class TestNodeWiring(unittest.TestCase):
    """node/main.py non si importa senza fastapi: si controlla il sorgente."""

    def setUp(self):
        self.src = (ROOT / "node" / "main.py").read_text(encoding="utf-8")

    def test_every_work_entry_checks_the_gate(self):
        import re
        calls = re.findall(r"(.*)\n.*\n\s*if not await _try_acquire_slot\(model\):", self.src)
        self.assertEqual(len(calls), 3)
        for line in calls:
            self.assertIn("if _gate_closed():", line)

    def test_degraded_is_reported_with_the_gate(self):
        self.assertNotIn('"degraded":         _qos_monitor.degraded', self.src)
        self.assertIn('"true" if _node_degraded() else "false"', self.src)

    def test_mobile_tier_can_be_forced(self):
        self.assertIn('("hub", "root", "leaf", MOBILE_TIER)', self.src)

class TestFailoverRole(unittest.TestCase):
    def test_failover_role_keeps_gate_closed_in_ideal_conditions(self):
        cfg = MobileGateConfig(failover_only=True)  # niente finestra: per un worker vorrebbe dire "sempre"
        res = evaluate_mobile_gate(PLUGGED_COOL, cfg, now=dtime(3, 0))
        self.assertFalse(res["open"])
        self.assertEqual(res["reasons"], [REASON_FAILOVER_ONLY])
        self.assertEqual(res["role"], "failover")

    def test_failover_role_ignores_window(self):
        cfg = MobileGateConfig(failover_only=True, window=parse_window("01:00-05:00"), window_spec="01:00-05:00")
        self.assertFalse(evaluate_mobile_gate(PLUGGED_COOL, cfg, now=dtime(3, 0))["open"])

    def test_role_from_env(self):
        with mock.patch.dict("os.environ", {"MOBILE_ROLE": "failover"}):
            self.assertTrue(MobileGateConfig.from_env().failover_only)
        with mock.patch.dict("os.environ", {"MOBILE_ROLE": "worker"}):
            self.assertFalse(MobileGateConfig.from_env().failover_only)
        with mock.patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("MOBILE_ROLE", None)
            self.assertFalse(MobileGateConfig.from_env().failover_only)  # default: comportamento invariato


if __name__ == "__main__":
    unittest.main()
