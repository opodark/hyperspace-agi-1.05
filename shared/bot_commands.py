# SPDX-License-Identifier: Apache-2.0
"""Comandi conversazionali comuni a Telegram e Instagram."""
from __future__ import annotations


HELP_COMMANDS = ("!help", "!aiuto", "/help")


def help_requested(text: str) -> bool:
    """Vero solo per il comando intero, con eventuali spazi."""
    normalized = " ".join(str(text or "").strip().lower().split())
    return normalized in HELP_COMMANDS


def help_text(*, creator: bool = False) -> str:
    """Guida breve e fattuale; i comandi privati non trapelano al pubblico."""
    lines = [
        "Comandi disponibili:",
        "!help — mostra questa guida",
        "!presentati — dice chi sono e cosa posso fare",
        "!anna <scena> — crea una mia immagine con volto e ricetta di Anna",
        "!immagine <descrizione> — crea un'immagine; !foto è un alias",
    ]
    if creator:
        lines.extend([
            "!render <prompt> — generazione neutrale senza identità di Anna (solo creatore)",
            "Suggerimento: specifica soggetto, stile, inquadratura e luce.",
        ])
    return "\n".join(lines)


def command_help(text: str, *, creator: bool = False) -> str | None:
    return help_text(creator=creator) if help_requested(text) else None
