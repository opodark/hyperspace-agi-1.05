#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test suite per InferenceLatencyPIDController."""

import unittest
from shared.inference_latency_pid import InferenceLatencyPIDController


class TestInferenceLatencyPIDController(unittest.TestCase):
    def setUp(self):
        self.pid = InferenceLatencyPIDController(
            target_latency_s=30.0,
            kp=0.5,
            ki=0.05,
            kd=0.1,
            min_output=0.2,
            max_output=2.0,
        )

    def test_nominal_latency_keeps_factor_near_one(self):
        # Misurazione esattamente pari al target
        factor = self.pid.compute(30.0, current_time=1.0)
        self.assertAlmostEqual(factor, 1.0, places=2)

    def test_high_latency_reduces_factor(self):
        # Latenza molto alta (60s invece di 30s) -> errore negativo
        factor = self.pid.compute(60.0, current_time=1.0)
        self.assertLess(factor, 1.0)
        self.assertGreaterEqual(factor, 0.2)

        # Token limit scalato verso il basso
        adjusted = self.pid.adjust_token_limit(1000, 60.0, current_time=2.0)
        self.assertLess(adjusted, 1000)

    def test_low_latency_increases_factor(self):
        # Latenza molto bassa (10s invece di 30s) -> errore positivo, possiamo espandere
        factor = self.pid.compute(10.0, current_time=1.0)
        self.assertGreater(factor, 1.0)
        self.assertLessEqual(factor, 2.0)

        adjusted = self.pid.adjust_token_limit(1000, 10.0, current_time=2.0)
        self.assertGreater(adjusted, 1000)

    def test_clamping_limits(self):
        # Caso estremo di ritardo (300s)
        factor = self.pid.compute(300.0, current_time=1.0)
        self.assertEqual(factor, 0.2)

        # Caso estremo di velocità (0.1s)
        factor_fast = self.pid.compute(0.1, current_time=2.0)
        self.assertLessEqual(factor_fast, 2.0)

    def test_reset(self):
        self.pid.compute(100.0, current_time=1.0)
        self.assertNotEqual(self.pid.integral, 0.0)
        self.pid.reset()
        self.assertEqual(self.pid.integral, 0.0)
        self.assertEqual(self.pid.last_error, 0.0)


if __name__ == "__main__":
    unittest.main()
