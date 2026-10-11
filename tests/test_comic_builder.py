# SPDX-License-Identifier: Apache-2.0
import tempfile
import unittest

from shared.comic_builder import (ComicStore, add_character, add_episode,
                                  episode_html, new_project, panel_prompt)


class ComicBuilderTests(unittest.TestCase):
    def test_project_episode_and_continuity_prompt(self):
        project = new_project("Luce nera", "Anna e Aurora cercano un ricordo perduto")
        add_character(project, name="Anna", role="protagonista", visual="capelli neri con punte viola")
        project["continuity"] = {"abito": "cappotto nero", "ora": "notte"}
        episode = add_episode(project, title="La porta", synopsis="Una soglia appare", panels=[
            {"scene": "Anna davanti a una porta luminosa", "dialogue": "La apriamo?"},
            {"scene": "Aurora posa la mano sulla serratura", "caption": "Il metallo ricorda."},
        ])
        prompt = panel_prompt(project, episode, episode["panels"][0])
        self.assertIn("capelli neri", prompt)
        self.assertIn("cappotto nero", prompt)
        self.assertIn("foreground must visibly include Anna", prompt)
        self.assertIn("no speech bubbles", prompt)

    def test_scene_override_non_riscrive_i_tag_tecnici(self):
        project = new_project("Titolo", "Premessa", style="ink graphic novel")
        episode = add_episode(project, title="Episodio", synopsis="x",
                              panels=[{"scene": "una porta"}])
        prompt = panel_prompt(project, episode, episode["panels"][0],
                              scene="a glowing door")
        self.assertTrue(prompt.startswith("a glowing door."))
        self.assertIn("single comic panel", prompt)
        self.assertIn("source_anime", prompt)
        self.assertIn("cel shading", prompt)

    def test_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            store = ComicStore(root)
            project = new_project("Titolo", "Premessa")
            store.save(project)
            self.assertEqual(store.load(project["id"])["premise"], "Premessa")
            self.assertEqual(len(store.list()), 1)

    def test_tavola_tiene_dialogo_fuori_dall_immagine(self):
        project = new_project("Titolo", "Premessa")
        episode = add_episode(project, title="Ep", synopsis="Sinossi", panels=[
            {"scene": "Anna entra", "dialogue": "Eccomi", "caption": "Notte"}])
        episode["panels"][0]["image_file"] = "HyperSpace/a.jpg"
        page = episode_html(project, episode, image_url=lambda x: "/img/" + x)
        self.assertIn('/img/HyperSpace/a.jpg', page)
        self.assertIn("Eccomi", page)
        self.assertIn('class="balloon"', page)
        self.assertIn('class="caption"', page)
        self.assertIn("@media", page)


if __name__ == "__main__":
    unittest.main()
