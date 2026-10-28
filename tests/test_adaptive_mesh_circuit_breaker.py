#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test suite per AdaptiveMeshCircuitBreaker."""

import asyncio
import time
import unittest
from shared.adaptive_mesh_circuit_breaker import (
    AdaptiveMeshCircuitBreaker,
    CircuitBreakerOpenError,
)


class TestAdaptiveMeshCircuitBreaker(unittest.TestCase):
    def setUp(self):
        self.cb = AdaptiveMeshCircuitBreaker(
            name="test-peer",
            fail_thresh=2,
            recov_timeout=0.1,  # timeout rapido per i test
        )

    def test_initial_state_closed(self):
        self.assertEqual(self.cb.state, AdaptiveMeshCircuitBreaker.CLOSED)
        self.assertEqual(self.cb.state_name, "CLOSED")
        self.assertTrue(self.cb.is_available())

    def test_success_keeps_closed(self):
        res = self.cb.call(lambda x: x * 2, 5)
        self.assertEqual(res, 10)
        self.assertEqual(self.cb.state_name, "CLOSED")
        self.assertEqual(self.cb.failures, 0)

    def test_failures_trigger_open(self):
        def failing_fn():
            raise ValueError("connection error")

        with self.assertRaises(ValueError):
            self.cb.call(failing_fn)
        self.assertEqual(self.cb.failures, 1)
        self.assertEqual(self.cb.state_name, "CLOSED")

        # Secondo fallimento -> supera fail_thresh (2) -> passa a OPEN
        with self.assertRaises(ValueError):
            self.cb.call(failing_fn)
        self.assertEqual(self.cb.failures, 2)
        self.assertEqual(self.cb.state, AdaptiveMeshCircuitBreaker.OPEN)
        self.assertEqual(self.cb.state_name, "OPEN")
        self.assertFalse(self.cb.is_available())

        # Chiamata successiva fallisce immediatamente con CircuitBreakerOpenError
        with self.assertRaises(CircuitBreakerOpenError):
            self.cb.call(lambda: "ok")

    def test_fallback_when_open(self):
        # Forza stato OPEN
        self.cb.state = AdaptiveMeshCircuitBreaker.OPEN
        self.cb.last_fail = time.time()

        res = self.cb.call(lambda: "never called", fallback=lambda: "fallback-value")
        self.assertEqual(res, "fallback-value")

    def test_half_open_recovery(self):
        self.cb.state = AdaptiveMeshCircuitBreaker.OPEN
        self.cb.last_fail = time.time() - 0.2  # tempo superiore a recov_timeout (0.1s)

        # Dovrebbe transitare a HALF_OPEN
        self.assertEqual(self.cb.state_name, "HALF_OPEN")
        self.assertTrue(self.cb.is_available())

        # Chiamata riuscita -> torna a CLOSED
        res = self.cb.call(lambda: "success")
        self.assertEqual(res, "success")
        self.assertEqual(self.cb.state_name, "CLOSED")
        self.assertEqual(self.cb.failures, 0)

    def test_async_call(self):
        async def async_test():
            async def remote_coro(val):
                return val.upper()

            res = await self.cb.async_call(remote_coro, "hello")
            self.assertEqual(res, "HELLO")

        asyncio.run(async_test())

    def test_registry_singleton(self):
        cb1 = AdaptiveMeshCircuitBreaker.for_target("asus-v16")
        cb2 = AdaptiveMeshCircuitBreaker.for_target("asus-v16")
        self.assertIs(cb1, cb2)
        self.assertEqual(cb1.name, "asus-v16")


if __name__ == "__main__":
    unittest.main()
