#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test unitari per shared/mailer.py."""
import email.utils
import unittest
from unittest.mock import MagicMock, patch

import shared.mailer as mailer


class MailerTests(unittest.TestCase):
    def test_clean_val_rimuove_apici_e_spazi(self):
        self.assertEqual(mailer._clean_val('  "smtps.aruba.it"  '), "smtps.aruba.it")
        self.assertEqual(mailer._clean_val("'info@zerozerocomputer.it'"), "info@zerozerocomputer.it")
        self.assertEqual(mailer._clean_val("465"), "465")
        self.assertEqual(mailer._clean_val(""), "")

    def test_render_key_email_contiene_chiave_e_istruzioni(self):
        text, html = mailer.render_key_email(name="Mario Rossi", auth_key="hs-mesh-mario-1234")
        self.assertIn("Mario Rossi", text)
        self.assertIn("hs-mesh-mario-1234", text)
        self.assertIn("https://oszerozero.onrender.com/", text)

        self.assertIn("Mario Rossi", html)
        self.assertIn("hs-mesh-mario-1234", html)
        self.assertIn("Chiave di Accesso Mesh", html)

    def test_parse_from_addr_separa_nome_e_indirizzo_pulito(self):
        from_str = 'HyperSpace Mesh <info@zerozerocomputer.it>'
        disp, email_clean = email.utils.parseaddr(from_str)
        self.assertEqual(disp, "HyperSpace Mesh")
        self.assertEqual(email_clean, "info@zerozerocomputer.it")

    @patch("shared.mailer.get_smtp_config")
    @patch("smtplib.SMTP_SSL")
    def test_send_key_email_usa_envelope_pulito_su_ssl(self, mock_smtp_ssl, mock_get_cfg):
        mock_get_cfg.return_value = {
            "host": "smtps.aruba.it",
            "port": 465,
            "user": "info@zerozerocomputer.it",
            "password": "secret_password",
            "from_addr": "HyperSpace Mesh <info@zerozerocomputer.it>",
            "use_ssl": True,
        }
        mock_server = MagicMock()
        mock_smtp_ssl.return_value.__enter__.return_value = mock_server

        success, msg = mailer.send_key_email(
            to_email="destinatario@test.com",
            name="Test User",
            auth_key="hs-mesh-test-key"
        )

        self.assertTrue(success)
        self.assertIn("destinatario@test.com", msg)
        mock_server.login.assert_called_once_with("info@zerozerocomputer.it", "secret_password")

        # Verifica che il mittente dell'envelope (MAIL FROM) sia solo l'email pulita, senza display name
        args, kwargs = mock_server.send_message.call_args
        self.assertEqual(kwargs.get("from_addr"), "info@zerozerocomputer.it")
        sent_msg = args[0]
        self.assertEqual(sent_msg["To"], "destinatario@test.com")
        self.assertIn("HyperSpace Mesh", sent_msg["From"])

    @patch("shared.mailer.get_smtp_config")
    def test_send_key_email_rifiuta_se_smtp_non_configurato(self, mock_get_cfg):
        mock_get_cfg.return_value = {
            "host": "",
            "port": 587,
            "user": "",
            "password": "",
            "from_addr": "",
            "use_ssl": False,
        }
        success, msg = mailer.send_key_email("test@example.com", "Test", "key")
        self.assertFalse(success)
        self.assertIn("non configurato", msg.lower())


if __name__ == "__main__":
    unittest.main()
