#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rigenera i sottoinsiemi .woff dei font dei Motion Reels (serve fontTools).

    python3 subset_fonts.py --display /percorso/InterDisplay-{peso}.otf --mono /percorso/DejaVuSansMono{suffisso}.ttf

I file committati vengono da Inter Display 4.x (OFL-1.1) e DejaVu Sans Mono
(licenza Bitstream Vera + modifiche in pubblico dominio): vedi LICENSE-*.txt.
Per usare altri font (per esempio Unbounded e JetBrains Mono, come sulla landing)
basta produrre file con gli stessi nomi: build.py li incorpora senza altre modifiche.
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNICODES = ("U+0020-007E,U+00A0-00FF,U+0391-03C9,U+2010-205F,U+2070-209F,U+2190-21FF,"
            "U+2200-22FF,U+2580-259F,U+25A0-25FF,U+2713,U+2715,U+2733")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--display", default="/usr/share/fonts/opentype/inter/InterDisplay-{peso}.otf",
                    help="modello di percorso con {peso} = Black|SemiBold|Medium")
    ap.add_argument("--mono", default="/usr/share/fonts/truetype/dejavu/DejaVuSansMono{suffisso}.ttf",
                    help="modello di percorso con {suffisso} = ''|-Bold")
    args = ap.parse_args()
    jobs = [(args.display.format(peso="Black"), "MeshDisplay-900.woff"),
            (args.display.format(peso="SemiBold"), "MeshDisplay-600.woff"),
            (args.display.format(peso="Medium"), "MeshDisplay-500.woff"),
            (args.mono.format(suffisso=""), "MeshMono-400.woff"),
            (args.mono.format(suffisso="-Bold"), "MeshMono-700.woff")]
    for src, out in jobs:
        subprocess.run([sys.executable, "-m", "fontTools.subset", src, f"--unicodes={UNICODES}",
                        "--flavor=woff", "--layout-features=*", f"--output-file={HERE / out}"], check=True)
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
