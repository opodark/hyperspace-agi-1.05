# SPDX-License-Identifier: Apache-2.0
"""Test suite per PocketHubGuard (shared/pocket_hub_guard.py)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.pocket_hub_guard import PocketHubGuard, PocketHubState


class TestPocketHubGuard(unittest.TestCase):
    def test_pocket_hub_init_default(self):
        guard = PocketHubGuard(primary_cp_url="http://100.81.234.102:8085")
        self.assertFalse(guard.enabled)
        self.assertFalse(guard.is_active_hub())
        self.assertEqual(guard.state, PocketHubState.STANDBY)
        snap = guard.snapshot()
        self.assertEqual(snap["state"], "standby")
        self.assertFalse(snap["is_active_hub"])
        self.assertEqual(snap["promotions_total"], 0)

    def test_pocket_hub_disabled_tick(self):
        guard = PocketHubGuard(primary_cp_url="http://100.81.234.102:8085", enabled=False)
        state = guard.tick(force_probe_result=False)
        self.assertEqual(state, PocketHubState.STANDBY)
        self.assertFalse(guard.is_active_hub())

    def test_pocket_hub_forced_active(self):
        guard = PocketHubGuard(primary_cp_url="http://100.81.234.102:8085", enabled=False)
        self.assertFalse(guard.is_active_hub())
        guard.set_forced_active(True)
        self.assertTrue(guard.is_active_hub())
        snap = guard.snapshot()
        self.assertTrue(snap["forced_active"])
        self.assertTrue(snap["is_active_hub"])
        guard.set_forced_active(False)
        self.assertFalse(guard.is_active_hub())

    def test_pocket_hub_failover_and_recovery_transitions(self):
        transitions = []

        def on_change(old_s, new_s):
            transitions.append((old_s, new_s))

        guard = PocketHubGuard(
            primary_cp_url="http://100.81.234.102:8085",
            enabled=True,
            failover_threshold_misses=3,
            recovery_threshold_hits=2,
            on_state_change=on_change,
        )

        # 1. Primary is healthy -> remains in STANDBY
        self.assertEqual(guard.tick(force_probe_result=True), PocketHubState.STANDBY)
        self.assertFalse(guard.is_active_hub())

        # 2. Miss 1
        self.assertEqual(guard.tick(force_probe_result=False), PocketHubState.STANDBY)
        self.assertFalse(guard.is_active_hub())

        # 3. Miss 2
        self.assertEqual(guard.tick(force_probe_result=False), PocketHubState.STANDBY)
        self.assertFalse(guard.is_active_hub())

        # 4. Miss 3 -> Threshold reached! Promoted to ACTIVE_FAILOVER
        self.assertEqual(guard.tick(force_probe_result=False), PocketHubState.ACTIVE_FAILOVER)
        self.assertTrue(guard.is_active_hub())
        self.assertEqual(guard.snapshot()["promotions_total"], 1)
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[-1], (PocketHubState.STANDBY, PocketHubState.ACTIVE_FAILOVER))

        # 5. Continuous failure maintains ACTIVE_FAILOVER
        self.assertEqual(guard.tick(force_probe_result=False), PocketHubState.ACTIVE_FAILOVER)
        self.assertTrue(guard.is_active_hub())

        # 6. Recovery probe hit 1 (not enough yet)
        self.assertEqual(guard.tick(force_probe_result=True), PocketHubState.ACTIVE_FAILOVER)
        self.assertTrue(guard.is_active_hub())

        # 7. Recovery probe hit 2 -> Transitions to RECOVERING
        self.assertEqual(guard.tick(force_probe_result=True), PocketHubState.RECOVERING)
        self.assertEqual(transitions[-1], (PocketHubState.ACTIVE_FAILOVER, PocketHubState.RECOVERING))

        # 8. Next tick completes recovery -> Transitions back to STANDBY
        self.assertEqual(guard.tick(force_probe_result=True), PocketHubState.STANDBY)
        self.assertFalse(guard.is_active_hub())
        self.assertEqual(guard.snapshot()["demotions_total"], 1)
        self.assertEqual(transitions[-1], (PocketHubState.RECOVERING, PocketHubState.STANDBY))

    def test_pocket_hub_probe_primary_mock(self):
        guard = PocketHubGuard(primary_cp_url="http://127.0.0.1:8085", enabled=True)

        with patch("shared.pocket_hub_guard.http.client.HTTPConnection") as mock_conn_cls:
            mock_conn = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_conn.getresponse.return_value = mock_resp
            mock_conn_cls.return_value = mock_conn

            ok, latency = guard.probe_primary(timeout=0.1)
            self.assertTrue(ok)
            self.assertGreaterEqual(latency, 0.0)

            mock_conn.getresponse.side_effect = Exception("Connection refused")
            ok, latency = guard.probe_primary(timeout=0.1)
            self.assertFalse(ok)

    def test_pocket_hub_watchdog_lifecycle(self):
        guard = PocketHubGuard(
            primary_cp_url="http://mock-primary:8085",
            enabled=True,
            check_interval_s=0.05,
        )
        guard.probe_primary = lambda timeout=3.0: (True, 1.0)
        guard.start_watchdog()
        self.assertIsNotNone(guard._watchdog_thread)
        self.assertTrue(guard._watchdog_thread.is_alive())

        t1 = guard._watchdog_thread
        guard.start_watchdog()
        self.assertIs(guard._watchdog_thread, t1)

        guard.stop_watchdog(timeout=1.0)
        self.assertIsNone(guard._watchdog_thread)


if __name__ == "__main__":
    unittest.main()
