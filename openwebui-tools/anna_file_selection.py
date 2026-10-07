# SPDX-License-Identifier: Apache-2.0
"""
title: HyperSpace Anna — selezione file
description: Elenca le immagini di Anna e copia una selezione in sottocartelle verificabili.
required_open_webui_version: 0.4.0
version: 0.1.0
"""

from pathlib import Path
from typing import List
import filecmp
import shutil


ROOT = Path("/app/anna-images")
FOLDERS = {"selezionate": "Anna_selezionate", "da_rivedere": "Anna_da_rivedere"}
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class Tools:
    def elenco_immagini_anna(self) -> str:
        """Elenca i nomi delle immagini nella cartella condivisa di Anna."""
        if not ROOT.is_dir():
            return f"Cartella non accessibile: {ROOT}. Controlla il volume Docker."
        names = sorted(p.name for p in ROOT.iterdir()
                       if p.is_file() and not p.is_symlink() and p.suffix.lower() in EXTENSIONS)
        return f"Trovate {len(names)} immagini in {ROOT}:\n" + "\n".join(names)

    def copia_immagini_anna(self, filenames: List[str], destinazione: str) -> str:
        """Copia immagini già esaminate in Anna_selezionate o Anna_da_rivedere.

        Non usare questa funzione per decidere la qualità visiva: prima occorre
        esaminare realmente le immagini. I file originali restano nella cartella.
        :param filenames: nomi esatti dei file nella cartella HyperSpace
        :param destinazione: selezionate oppure da_rivedere
        """
        if destinazione not in FOLDERS:
            return "Destinazione non valida: usa 'selezionate' o 'da_rivedere'."
        if not ROOT.is_dir():
            return f"Cartella non accessibile: {ROOT}. Controlla il volume Docker."
        if not isinstance(filenames, list) or not filenames:
            return "Indica almeno un nome file."
        if len(filenames) > 100:
            return "Massimo 100 file per chiamata."
        sources = []
        for name in filenames:
            if not isinstance(name, str) or name != Path(name).name or name in (".", ".."):
                return f"Nome file non valido: {name!r}."
            source = ROOT / name
            if source.suffix.lower() not in EXTENSIONS or not source.is_file() or source.is_symlink():
                return f"Immagine non trovata nella cartella condivisa: {name}."
            sources.append(source)
        target_dir = ROOT / FOLDERS[destinazione]
        target_dir.mkdir(exist_ok=True)
        copied = []
        for source in sources:
            target = target_dir / source.name
            if target.exists():
                if target.is_symlink() or not target.is_file() or not filecmp.cmp(source, target, shallow=False):
                    return f"Conflitto: {target.name} esiste già con contenuto diverso. Copiati prima del conflitto: {copied}."
            else:
                shutil.copy2(source, target)
            copied.append(source.name)
        verified = sum((target_dir / name).is_file() for name in copied)
        return f"Copiate e verificate {verified}/{len(copied)} immagini in {target_dir}: " + ", ".join(copied)
