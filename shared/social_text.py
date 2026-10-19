# SPDX-License-Identifier: Apache-2.0
"""Testi dei post social: composizione deterministica, nessun modello.

Le didascalie oggi scritte a mano in `_instagram_publish_voce` e in
`_publish_dialogue` vivono qui, così policy e test le vedono senza importare il
control-plane. Regola unica: la disclosure IA è sempre presente
(`#AIDreams`/`#AIPoetry`/`#AIDialogo`/`#AIAuthor`).
"""
from __future__ import annotations

import re

MAX_IG = 2200
MAX_X = 280

_TAG = re.compile(r"#\w+")


def _pulisci(testo) -> str:
    return " ".join(str(testo or "").split())


def compose_caption(tipo: str, persona: str, testo: str, *, testo_b: str = "") -> str:
    """La didascalia Instagram di una voce, con prefisso e disclosure IA."""
    persona = str(persona or "").strip().capitalize() or "Anna"
    corpo = _pulisci(testo)
    if tipo == "poesia":
        base = f"📜 Poesia di {persona}\n\n{corpo}"
        tag = "#AuroraAndAnna #PoesiaDigitale #AIPoetry"
    elif tipo == "dialogo":
        base = f"💬 Anna e Aurora si rispondono\n\n{corpo}"
        if _pulisci(testo_b):
            base += f"\n\n{_pulisci(testo_b)}"
        tag = "#AuroraAndAnna #DueSorelle #AIDialogo"
    elif tipo == "sogno":
        base = f"🌙 Sogno di {persona}\n\n{corpo}"
        tag = "#AuroraAndAnna #SogniDigitali #AIDreams"
    else:
        base = corpo
        tag = "#AuroraAndAnna #AIAuthor"
    return f"{base}\n\n{tag}"[:MAX_IG]


def link_profilo_ig(handle: str) -> str:
    handle = str(handle or "").strip().lstrip("@")
    return f"https://instagram.com/{handle}" if handle else ""


def adatta_per_x(caption: str, *, profilo_ig: str = "") -> str:
    """Adatta una didascalia per X: ≤280 caratteri, ≤3 hashtag, link al profilo.

    Il profilo IG va in fondo come riferimento stabile: l'immagine su X arriva
    in un secondo momento, quindi si punta al profilo e non al singolo post.
    """
    testo = _pulisci(caption)
    hashtag = _TAG.findall(testo)
    tenuti = " ".join(hashtag[:3])
    corpo = " ".join(_TAG.sub(" ", testo).split())
    footer = f"\n{_pulisci(profilo_ig)}" if _pulisci(profilo_ig) else ""
    tag_block = f"\n{tenuti}" if tenuti else ""
    # Il corpo si tronca per far posto a hashtag e link: il link non va mai perso.
    budget = MAX_X - len(footer) - len(tag_block)
    return (corpo[:budget].strip() + tag_block + footer)[:MAX_X]
