# SPDX-License-Identifier: Apache-2.0
"""Test per shared/crypto_intel.py: comandi crypto, CA, pump.fun e DexScreener."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from shared.crypto_intel import (
    CA_ADDRESS,
    PUMPFUN_URL,
    DEXSCREENER_URL,
    format_ca,
    format_price,
    format_mesh_stats,
    format_pouw_guide,
    format_anna_sim,
    format_help,
    handle_crypto_command,
    get_market_metrics,
)


class TestCryptoIntel(unittest.TestCase):
    def test_ca_formatting(self):
        msg = format_ca()
        self.assertIn(CA_ADDRESS, msg)
        self.assertIn("pump.fun", msg)
        self.assertIn("DexScreener", msg)

    def test_price_formatting_mocked(self):
        mock_data = {
            "price_usd": "0.000000025",
            "market_cap": 25.0,
            "volume_24h": 745.0,
            "price_change_24h": 12.5,
            "price_change_6h": 5.0,
            "buys_24h": 100,
            "sells_24h": 50,
            "dex": "pumpfun",
            "live": True,
        }
        with patch("shared.crypto_intel.get_market_metrics", return_value=mock_data):
            msg = format_price()
            self.assertIn("0.000000025", msg)
            self.assertIn("25.00", msg)
            self.assertIn("+12.5%", msg)
            self.assertIn(CA_ADDRESS, msg)

    def test_handle_crypto_command_variants(self):
        # CA commands
        self.assertIsNotNone(handle_crypto_command("/ca"))
        self.assertIsNotNone(handle_crypto_command("!ca"))
        self.assertIsNotNone(handle_crypto_command("/ca@Pimpachatbot"))
        self.assertIn(CA_ADDRESS, handle_crypto_command("/ca"))

        # Price commands
        self.assertIsNotNone(handle_crypto_command("/price"))
        self.assertIsNotNone(handle_crypto_command("/prezzo"))
        self.assertIsNotNone(handle_crypto_command("!price@Pimpachatbot"))

        # Chart commands
        self.assertIsNotNone(handle_crypto_command("/chart"))
        self.assertIn("DexScreener", handle_crypto_command("/chart"))

        # Bonding / Tokenomics / Quiz commands
        self.assertIsNotNone(handle_crypto_command("/bonding"))
        self.assertIsNotNone(handle_crypto_command("/tokenomics"))
        self.assertIsNotNone(handle_crypto_command("/quiz"))

        # Mesh / Nodes commands
        self.assertIsNotNone(handle_crypto_command("/mesh"))
        self.assertIsNotNone(handle_crypto_command("/nodes"))

        # PoUW / Mining commands
        self.assertIsNotNone(handle_crypto_command("/pouw"))
        self.assertIsNotNone(handle_crypto_command("/mining"))

        # Anna Dating Sim
        self.assertIsNotNone(handle_crypto_command("/anna"))
        self.assertIn("anna.html", handle_crypto_command("/anna"))

        # Help
        self.assertIsNotNone(handle_crypto_command("/help"))

        # Non-crypto text should return None (pass through to LLM)
        self.assertIsNone(handle_crypto_command("Ciao Anna come stai?"))
        self.assertIsNone(handle_crypto_command("Parlami della coscienza"))


if __name__ == "__main__":
    unittest.main()
