# SPDX-License-Identifier: Apache-2.0
"""
title: HyperSpace — cartella condivisa
description: Elenca, legge e scrive file di testo nella cartella hyperspace_share dell'utente opo.
required_open_webui_version: 0.4.0
version: 0.1.0
"""

from pathlib import Path
from pydantic import BaseModel, Field


ROOT = Path("/app/hyperspace_share")
MAX_READ = 200_000
MAX_WRITE = 200_000


def _resolve(relative_path: str, base: Path | None = None) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("Indica un percorso relativo alla cartella condivisa.")
    path = Path(relative_path)
    if path.is_absolute():
        raise ValueError("Usa un percorso relativo, senza / iniziale.")
    root = (base or ROOT).resolve(strict=True)
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Percorso esterno alla cartella condivisa.")
    return target


class Tools:
    class Valves(BaseModel):
        sottocartella: str = Field(
            default=".",
            description="Sottocartella di /Users/opo/hyperspace_share da usare come area di lavoro.",
        )
        max_lettura_byte: int = Field(
            default=MAX_READ, ge=1, le=1_000_000,
            description="Dimensione massima di un file di testo leggibile (byte).",
        )
        max_scrittura_byte: int = Field(
            default=MAX_WRITE, ge=1, le=1_000_000,
            description="Dimensione massima di un nuovo file di testo (byte).",
        )

    def __init__(self):
        self.valves = self.Valves()

    def _base(self) -> Path:
        base = _resolve(self.valves.sottocartella)
        if not base.is_dir():
            raise ValueError(f"Sottocartella configurata non trovata: {self.valves.sottocartella}")
        return base

    def elenco_share(self, percorso: str = ".") -> str:
        """Elenca file e sottocartelle nella cartella condivisa.
        :param percorso: sottocartella relativa, oppure . per la radice
        """
        try:
            target = _resolve(percorso, self._base())
            if not target.is_dir():
                return f"Cartella non trovata: {percorso}"
            rows = [f"{'DIR ' if p.is_dir() else 'FILE'} {p.name}"
                    for p in sorted(target.iterdir(), key=lambda p: p.name.lower())]
            return f"{len(rows)} elementi in {percorso}:\n" + "\n".join(rows)
        except (OSError, ValueError) as error:
            return f"Errore accesso cartella: {error}"

    def leggi_testo_share(self, percorso: str) -> str:
        """Legge un file di testo UTF-8 della cartella condivisa.
        :param percorso: percorso relativo del file
        """
        try:
            target = _resolve(percorso, self._base())
            if not target.is_file():
                return f"File non trovato: {percorso}"
            if target.stat().st_size > self.valves.max_lettura_byte:
                return f"File troppo grande: limite {self.valves.max_lettura_byte} byte."
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError) as error:
            return f"Errore lettura: {error}"

    def scrivi_testo_share(self, percorso: str, contenuto: str) -> str:
        """Crea un file di testo UTF-8 nella share; rifiuta file già esistenti.
        :param percorso: percorso relativo del nuovo file
        :param contenuto: testo da scrivere
        """
        try:
            if not isinstance(contenuto, str) or len(contenuto.encode("utf-8")) > self.valves.max_scrittura_byte:
                return f"Contenuto non valido o troppo grande: limite {self.valves.max_scrittura_byte} byte."
            base = self._base()
            target = _resolve(percorso, base)
            if target == base:
                return "Indica un nome file."
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as stream:
                stream.write(contenuto)
            return f"Creato e verificato: {target.relative_to(base)} ({target.stat().st_size} byte)."
        except FileExistsError:
            return f"File già esistente: {percorso}. Nessuna modifica."
        except (OSError, ValueError) as error:
            return f"Errore scrittura: {error}"
