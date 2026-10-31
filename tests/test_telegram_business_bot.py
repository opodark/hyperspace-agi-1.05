# SPDX-License-Identifier: Apache-2.0
"""Test suite per il Bot Telegram Aziendale di Vittoria."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.telegram_business_bot import TelegramBusinessBot


class TelegramBusinessBotTests(unittest.TestCase):
    def setUp(self):
        self.bot = TelegramBusinessBot(
            token="test-token-12345",
            cp_url="http://mock-cp:8085",
            allowed_users={"mario_rossi", "123456"}
        )

    def test_is_user_allowed_fail_closed_if_empty(self):
        empty_bot = TelegramBusinessBot(token="token", allowed_users=set())
        self.assertFalse(empty_bot.is_user_allowed({"username": "mario_rossi"}))

    def test_is_user_allowed_by_username_and_id(self):
        self.assertTrue(self.bot.is_user_allowed({"username": "mario_rossi", "id": 999}))
        self.assertTrue(self.bot.is_user_allowed({"username": "altrouser", "id": "123456"}))
        self.assertFalse(self.bot.is_user_allowed({"username": "sconosciuto", "id": 888}))

    @patch.object(TelegramBusinessBot, "send_message")
    def test_handle_unauthorized_user(self, mock_send):
        msg = {
            "chat": {"id": 100},
            "from": {"username": "hacker", "id": 777},
            "text": "Dammi i bilanci aziendali"
        }
        self.bot.handle_message(msg)
        mock_send.assert_called_once()
        self.assertIn("non autorizzato", mock_send.call_args[0][1])

    @patch.object(TelegramBusinessBot, "send_message")
    def test_handle_start_command(self, mock_send):
        msg = {
            "chat": {"id": 100},
            "from": {"username": "mario_rossi", "id": 123456},
            "text": "/start"
        }
        self.bot.handle_message(msg)
        mock_send.assert_called_once()
        self.assertIn("Vittoria", mock_send.call_args[0][1])
        self.assertIn("preventivi", mock_send.call_args[0][1])

    @patch.object(TelegramBusinessBot, "handle_voice_message")
    @patch.object(TelegramBusinessBot, "send_message")
    def test_handle_voice_message_routing(self, mock_send, mock_handle_voice):
        mock_handle_voice.return_value = "Fai un preventivo per Studio Rossi"
        msg = {
            "chat": {"id": 100},
            "from": {"username": "mario_rossi", "id": 123456},
            "voice": {"file_id": "voice_123"}
        }
        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Preventivo creato"}}]
            }
            mock_post.return_value = mock_resp
            self.bot.handle_message(msg)

        mock_handle_voice.assert_called_once_with(100, {"file_id": "voice_123"})
        mock_send.assert_called_with(100, "Preventivo creato")

    @patch("requests.post")
    @patch.object(TelegramBusinessBot, "send_document")
    @patch.object(TelegramBusinessBot, "send_message")
    @patch.object(TelegramBusinessBot, "send_typing")
    def test_handle_message_with_pdf_generation(self, mock_typing, mock_send_msg, mock_send_doc, mock_post):
        # Mock risposta CP con riferimento a un file PDF esistente
        test_pdf = Path("data/documents/preventivo_PREV-2026-001.pdf")
        test_pdf.parent.mkdir(parents=True, exist_ok=True)
        if not test_pdf.exists():
            test_pdf.write_bytes(b"%PDF-1.4 dummy")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": f"Ho preparato il preventivo. Ecco il file generato: /repo/data/documents/{test_pdf.name}"
                }
            }]
        }
        mock_post.return_value = mock_resp

        msg = {
            "chat": {"id": 100},
            "from": {"username": "mario_rossi", "id": 123456},
            "text": "Preparami il preventivo per Studio Bianchi"
        }
        self.bot.handle_message(msg)

        # Deve aver inviato il messaggio testuale
        mock_send_msg.assert_called_once()
        self.assertIn("preventivo", mock_send_msg.call_args[0][1])

        # Deve aver inviato il PDF via sendDocument
        mock_send_doc.assert_called_once()
        self.assertEqual(mock_send_doc.call_args[0][0], 100)
        self.assertIn("PREV-2026-001.pdf", mock_send_doc.call_args[0][1])


if __name__ == "__main__":
    unittest.main()
