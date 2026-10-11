# SPDX-License-Identifier: Apache-2.0
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IntimatePageTests(unittest.TestCase):
    def test_private_page_uses_authenticated_api_and_manual_generation(self):
        page = (ROOT / "control-plane" / "intimo.html").read_text(encoding="utf-8")
        self.assertIn("/diario/intimo/data", page)
        self.assertIn("/diario/intimo/genera", page)
        self.assertIn("X-Hyperspace-Network-Token", page)

    def test_control_plane_serves_the_private_page(self):
        source = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
        self.assertIn("@app.route('/diario/intimo')", source)
        self.assertIn("'intimo.html'", source)

    def test_image_contains_the_private_page(self):
        dockerfile = (ROOT / "control-plane" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY control-plane/intimo.html .", dockerfile)


if __name__ == "__main__":
    unittest.main()
