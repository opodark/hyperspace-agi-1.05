#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the user's local TikTok editor as an optional, loopback-only service."""

import argparse
import os
import shutil
import sys
from pathlib import Path


def editor_dir() -> Path:
    bundled = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "app"
    return Path(os.getenv("TIKTOK_EDITOR_DIR", str(bundled))).expanduser()


def check_editor(path: Path) -> None:
    if not path.is_dir() or not (path / "gui.py").is_file() or not (path / "autoedit" / "pipeline.py").is_file():
        raise FileNotFoundError(f"TikTok editor non trovato in {path}; imposta TIKTOK_EDITOR_DIR")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise FileNotFoundError("Servono ffmpeg e ffprobe nel PATH")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Servizio locale TikTok editor per HyperSpace")
    parser.add_argument("--check", action="store_true", help="Verifica file e ffmpeg senza avviare il servizio")
    args = parser.parse_args(argv)
    source = editor_dir().resolve()
    try:
        check_editor(source)
        if args.check:
            print(f"Editor pronto: {source}")
            return 0
        os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
        sys.path.insert(0, str(source))
        import gui  # type: ignore  # loaded from the configured local editor

        print("TikTok editor: http://127.0.0.1:7860", flush=True)
        share_dir = Path(os.getenv("TIKTOK_EDITOR_SHARE_DIR", "/Users/opo/hyperspace_share"))
        allowed = [str(share_dir.resolve())] if share_dir.is_dir() else []
        gui.demo.launch(server_name="127.0.0.1", server_port=7860,
                        inbrowser=False, share=False, show_error=True,
                        allowed_paths=allowed)
        return 0
    except (FileNotFoundError, ImportError, OSError) as exc:
        print(f"TikTok editor non avviato: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
