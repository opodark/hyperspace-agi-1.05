import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "scripts" / "start-all-macos.sh"
STOP = ROOT / "scripts" / "stop-all-macos.sh"


class StartAllMacosTests(unittest.TestCase):
    def test_shell_syntax(self):
        for script in (START, STOP):
            result = subprocess.run(["bash", "-n", str(script)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_start_copre_i_componenti_richiesti(self):
        text = START.read_text(encoding="utf-8")
        for marker in ("control-plane", "registry", "libretranslate", "Comfy Desktop",
                       "com.hyperspace.comfy-bridge", "start-telegram.sh", "serve.mjs"):
            self.assertIn(marker, text)

    def test_stop_e_simmetrico(self):
        text = STOP.read_text(encoding="utf-8")
        for marker in ("telegram_bot.py", "com.hyperspace.comfy-bridge", "serve.mjs",
                       "control-plane registry libretranslate", "Comfy Desktop"):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
