import unittest

from shared.bot_commands import command_help, help_requested, help_text


class BotCommandsTests(unittest.TestCase):
    def test_help_ha_alias_italiano_e_telegram(self):
        for command in ("!help", " !AIUTO ", "/help"):
            self.assertTrue(help_requested(command))

    def test_una_frase_normale_non_e_help(self):
        self.assertFalse(help_requested("mi dai help con una foto?"))
        self.assertIsNone(command_help("ciao", creator=True))

    def test_render_compare_solo_nella_guida_del_creatore(self):
        self.assertNotIn("!render", help_text(creator=False))
        self.assertIn("!render", help_text(creator=True))

    def test_guida_pubblica_elenca_solo_comandi_reali(self):
        guida = help_text(creator=False)
        for command in ("!help", "!presentati", "!anna", "!immagine", "!foto"):
            self.assertIn(command, guida)


if __name__ == "__main__":
    unittest.main()
