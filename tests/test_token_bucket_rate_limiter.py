#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test suite per TokenBucketRateLimiter."""

import asyncio
import time
import unittest
from shared.token_bucket_rate_limiter import TokenBucketRateLimiter


class TestTokenBucketRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = TokenBucketRateLimiter(
            capacity=100,
            refill_rate=200.0,  # 200 token al secondo
            name="test-gpu",
        )

    def test_initial_state(self):
        self.assertEqual(self.limiter.available(), 100)
        st = self.limiter.status()
        self.assertEqual(st["name"], "test-gpu")
        self.assertEqual(st["available_tokens"], 100)
        self.assertEqual(st["capacity"], 100)

    def test_acquire_and_exhaust(self):
        self.assertTrue(self.limiter.acquire(60))
        self.assertLessEqual(self.limiter.available(), 40)
        self.assertTrue(self.limiter.acquire(30))
        # Non ce ne sono 50 disponibili
        self.assertFalse(self.limiter.acquire(50))

    def test_refill_over_time(self):
        self.assertTrue(self.limiter.acquire(100))
        self.assertEqual(self.limiter.available(), 0)

        # Attendi 0.1s: con refill_rate=200, dovrebbero rientrare ~20 token
        time.sleep(0.1)
        self.assertGreaterEqual(self.limiter.available(), 15)
        self.assertTrue(self.limiter.acquire(15))

    def test_wait_and_acquire(self):
        self.limiter.acquire(100)  # svuota
        # Attende che rientrino 10 token (dovrebbe richiedere ~0.05s)
        self.assertTrue(self.limiter.wait_and_acquire(10, timeout=1.0))

    def test_release(self):
        self.limiter.acquire(80)
        self.assertLessEqual(self.limiter.available(), 25)
        self.limiter.release(50)
        self.assertGreaterEqual(self.limiter.available(), 70)

    def test_async_acquire(self):
        async def run_async():
            self.limiter.acquire(100)
            res = await self.limiter.acquire_async(20, timeout=1.0)
            self.assertTrue(res)

        asyncio.run(run_async())

    def test_device_registry(self):
        lim1 = TokenBucketRateLimiter.for_device("omen-rtx3070")
        lim2 = TokenBucketRateLimiter.for_device("omen-rtx3070")
        self.assertIs(lim1, lim2)
        self.assertEqual(lim1.name, "omen-rtx3070")


if __name__ == "__main__":
    unittest.main()
