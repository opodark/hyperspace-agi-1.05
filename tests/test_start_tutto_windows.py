# SPDX-License-Identifier: Apache-2.0
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "scripts" / "start-tutto.ps1"


def _powershell() -> str | None:
    return shutil.which("powershell.exe") or shutil.which("powershell")


class StartTuttoWindowsTests(unittest.TestCase):
    def test_powershell_syntax(self):
        ps = _powershell()
        if not ps:
            self.skipTest("powershell non disponibile su questo host")
        # Il parser AST di PowerShell valida la sintassi senza eseguire nulla.
        script = (
            "$tokens=$null; $errors=$null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{START}', "
            "[ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors) { $errors | ForEach-Object { Write-Host $_.Message }; exit 1 }"
        )
        result = subprocess.run(
            [ps, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_start_copre_i_componenti_richiesti(self):
        text = START.read_text(encoding="utf-8")
        for marker in ("start.ps1", "start-surfaces.ps1",
                       "start_hermes_memory_bridge.ps1", "rea_surface.py",
                       "8098", "7872", "docker"):
            self.assertIn(marker, text)

    def test_stop_e_simmetrico(self):
        text = START.read_text(encoding="utf-8")
        # -Stop ferma le superfici e lo stack, come stop-all-macos.sh sul Mac.
        self.assertIn("-Stop", text)
        self.assertIn("start-surfaces.ps1", text)
        self.assertIn("start.ps1", text)
        self.assertLess(text.index("Stop-tutto"), text.index("Start-tutto"))


if __name__ == "__main__":
    unittest.main()
