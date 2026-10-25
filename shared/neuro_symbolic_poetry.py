#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
shared/neuro_symbolic_poetry.py
Modulo promosso in produzione da HyperSpace R&D Sovereign Lab.
Prototipo sorgente: proto_algorithmic_poetry_aesthetics_1792874380.py
Topic: Algorithmic Aesthetics & Intelligent Poetry Generation (Teknokultura 2023, ScienceDirect 2025)

Combina la sintesi tematica di memorie episodiche (Anna / Aurora) con
motore neuro-simbolico per la generazione poetica metrica e l'estrazione
di prompt visivi ottimizzati per ComfyUI.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional


class NeuroSymbolicPoetryEngine:
    """
    Motore neuro-simbolico per la composizione poetica metrica e
    la derivazione coerente di prompt visivi per la pipeline ComfyUI.
    """

    DEFAULT_MEMORY: Dict[str, str] = {
        "location": "giardino cibernetico",
        "weather": "alba radiosa",
        "emotion": "serenità contemplativa",
        "sky": "orizzonte indaco",
        "focus": "luce tra i rami quantici",
    }

    STYLE_PRESETS: Dict[str, Dict[str, Any]] = {
        "watercolor": {
            "style_prompt": "delicate watercolor painting, soft pigment bleeding, paper texture, subtle pastels",
            "negative": "photorealistic, 3d render, plastic, noisy, oversaturated",
        },
        "cinematic": {
            "style_prompt": "cinematic 35mm photograph, shallow depth of field, anamorphic golden hour glow, 8k",
            "negative": "blurry, low quality, cartoon, deformed, glitch",
        },
        "cyberpunk_dream": {
            "style_prompt": "ethereal cyberpunk aesthetic, neon bokeh, misty atmospheric reflections, anime chicmix",
            "negative": "drab, monochrome, lowres, text, watermark",
        },
    }

    def __init__(self, day_memory: Optional[Dict[str, Any]] = None):
        self.day_memory = dict(self.DEFAULT_MEMORY)
        if day_memory:
            self.day_memory.update(day_memory)

    def generate_poem(
        self,
        emotion: Optional[str] = None,
        location: Optional[str] = None,
        scheme: str = "ABAB",
    ) -> str:
        """
        Genera una quartina poetica armonizzata sui temi della giornata.
        Supporta schemi metrici ABAB e AABB con cadenza prosodica italiana.
        """
        loc = location or self.day_memory.get("location", "orizzonte")
        emo = emotion or self.day_memory.get("emotion", "pace")
        weather = self.day_memory.get("weather", "luce chiara")
        sky = self.day_memory.get("sky", "cielo sereno")

        stanzas_abab = [
            f"Nel {loc} ove il tempo tace e brilla,",
            f"risveglia l'alba una {emo} antica,",
            f"mentre tra i rami la rugiada stilla,",
            f"e il cuore trova la sua voce amica.",
        ]

        stanzas_aabb = [
            f"Sotto il chiarore di questo {sky},",
            f"dove i pensieri sciolgono ogni guai,",
            f"con passo lieve Anna cammina attenta,",
            f"e la memoria in armonia s'ammanta.",
        ]

        lines = stanzas_aabb if scheme.upper() == "AABB" else stanzas_abab
        return "\n".join(lines)

    def extract_visual_prompt(
        self,
        keywords: Optional[List[str]] = None,
        style: str = "watercolor",
    ) -> Dict[str, Any]:
        """
        Estrae un descrittore visuale compatibile con ComfyUI e SD1.5 / SDXL,
        garantendo corrispondenza estetica con i temi del sonetto/quartina.
        """
        kw = list(keywords) if keywords else [
            self.day_memory.get("location", "garden"),
            self.day_memory.get("weather", "morning dawn"),
            self.day_memory.get("emotion", "serene contemplation"),
        ]

        preset = self.STYLE_PRESETS.get(style, self.STYLE_PRESETS["watercolor"])
        positive_elements = [
            "Masterpiece",
            "Anna portrait",
            f"atmosphere of {kw[0]}",
            preset["style_prompt"],
            "hyperdetailed eyes, soft smile, artistic composition",
        ]
        if len(kw) > 1:
            positive_elements.append(f"ambient theme: {', '.join(kw[1:])}")

        return {
            "theme": kw[0] if kw else "serene reflection",
            "style": style,
            "positive_prompt": ", ".join(positive_elements),
            "negative_prompt": preset["negative"],
            "elements": kw,
            "created_at": time.time(),
        }


if __name__ == "__main__":
    engine = NeuroSymbolicPoetryEngine()
    print("--- POESIA GENERATA ---")
    print(engine.generate_poem())
    print("\n--- PROMPT VISUALE COMFYUI ---")
    print(engine.extract_visual_prompt(["giardino quantico", "alba dorata", "contemplazione"]))
