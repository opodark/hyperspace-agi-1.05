# SPDX-License-Identifier: Apache-2.0
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


    def test_start_passa_a_rea_il_motore_nativo_solo_se_ce(self):
        text = START.read_text(encoding="utf-8")
        for marker in ("GHIDRA_INSTALL_DIR", "JAVA_HOME", "ghidra_dir", "java_home"):
            self.assertIn(marker, text)
        # i due percorsi entrano nell'ambiente solo se esistono davvero
        self.assertIn('[[ -d "$ghidra_dir" && -x "$java_home/bin/java" ]]', text)
        # e l'esportazione precede l'avvio della superficie, che li eredita
        self.assertLess(text.index('export GHIDRA_INSTALL_DIR'),
                        text.index('scripts/rea_surface.py'))


if __name__ == "__main__":
    unittest.main()
