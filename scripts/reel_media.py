#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage explicitly chosen Anna/Aurora media for the local reel editor."""

import argparse
import filecmp
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v"}


def anna_approved(first_state: Path, second_state: Path) -> set[str]:
    results = {}
    for state_path in (first_state, second_state):
        if not state_path.is_file():
            continue
        state = json.loads(state_path.read_text(encoding="utf-8"))
        # The second pass can review images missing from the first state, and
        # may also re-evaluate them. Prefer its decision; a later "da_rivedere"
        # must revoke an older approval.
        results.update(state.get("results", {}))
    return {name for name, result in results.items() if result.get("esito") == "ok"}


def stage_media(persona: str, source_dir: Path, output_root: Path, names: list[str],
                approved: set[str] | None = None) -> Path:
    if persona not in ("Anna", "Aurora"):
        raise ValueError("Persona ammessa: Anna o Aurora")
    if not names:
        raise ValueError("Scegli almeno un file")
    source_dir = source_dir.resolve(strict=True)
    sources = []
    for name in names:
        if Path(name).name != name or name in (".", ".."):
            raise ValueError(f"Nome file non valido: {name}")
        if approved is not None and name not in approved:
            raise ValueError(f"Immagine Anna non promossa dalla selezione: {name}")
        source = source_dir / name
        if source.is_symlink() or not source.is_file() or source.suffix.lower() not in MEDIA_EXT:
            raise ValueError(f"Media non valido: {name}")
        sources.append(source)

    output_root.mkdir(parents=True, exist_ok=True)
    folder = output_root / (persona.lower() + "-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                            + "-" + uuid.uuid4().hex[:6])
    media_dir = folder / "media"
    media_dir.mkdir(parents=True, exist_ok=False)
    for source in sources:
        target = media_dir / source.name
        shutil.copy2(source, target)
        if not filecmp.cmp(source, target, shallow=False):
            raise OSError(f"Copia non verificata: {source.name}")
    (folder / "manifest.json").write_text(json.dumps({
        "persona": persona, "media_dir": str(media_dir), "filenames": names,
        "source_dir": str(source_dir), "created_at": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return folder


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prepara foto e clip per il Reel Editor")
    parser.add_argument("persona", choices=("anna", "aurora"))
    parser.add_argument("--names", nargs="*", help="Nomi esatti dei file da usare")
    parser.add_argument("--limit", type=int, default=30, help="Solo Anna: massimo di promosse se --names manca")
    parser.add_argument("--source-dir", type=Path, help="Cartella sorgente (necessaria per Aurora)")
    parser.add_argument("--output-root", type=Path, default=REPO / "data" / "reel-projects")
    parser.add_argument("--first-state", type=Path, default=REPO / "data/control-plane/anna-selection.json")
    parser.add_argument("--second-state", type=Path, default=REPO / "data/control-plane/anna-second-pass.json")
    args = parser.parse_args(argv)
    if args.limit < 1 or args.limit > 100:
        parser.error("--limit deve essere fra 1 e 100")
    if args.persona == "anna":
        approved = anna_approved(args.first_state, args.second_state)
        names = args.names or sorted(approved)[:args.limit]
        source_dir = args.source_dir or Path(os.getenv("COMFY_OUTPUT_DIR", "/Users/opo/ComfyUI-Shared/output")) / "HyperSpace"
    else:
        if not args.source_dir or not args.names:
            parser.error("Aurora richiede --source-dir e --names: non esiste ancora una selezione verificata")
        approved = None
        names = args.names
        source_dir = args.source_dir
    try:
        folder = stage_media(args.persona.title(), source_dir, args.output_root,
                             names, approved)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Errore: {exc}\n")
    print(f"Preparati {len(names)} media in {folder / 'media'}")
    print("Apri il Reel Editor, carica questi file e scegli una musica autorizzata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
