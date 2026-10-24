# SPDX-License-Identifier: Apache-2.0
"""Test suite per LinkedIn DevPost Generator & Liftli Heuristics."""

import json
from pathlib import Path
import pytest
from scripts.marketing.linkedin_generator import (
    LiftliPostAnalyzer,
    LinkedInDevPostGenerator,
    PostMetrics,
)


def test_liftli_analyzer_metrics():
    text = (
        "Rilasciato HyperSpace 1.05.6 con punteggio 100/100!\n\n"
        "Ecco le novità principali:\n\n"
        "• Modelli LFM 2.5 su cluster OMEN\n"
        "• Dialoghi ad agenti in fumetti\n\n"
        "Scoprilo sul repo GitHub. Cosa ne pensi?\n\n"
        "#AI #BuildInPublic #MultiAgent"
    )
    metrics = LiftliPostAnalyzer.analyze(text)

    assert isinstance(metrics, PostMetrics)
    assert metrics.total_chars == len(text)
    assert metrics.total_words > 10
    assert metrics.bullet_points_count == 2
    assert metrics.has_cta is True
    assert len(metrics.hashtags) == 3
    assert metrics.score >= 80
    assert len(metrics.mobile_hook) <= 140
    assert len(metrics.desktop_hook) <= 210


def test_liftli_analyzer_penalizes_wall_of_text():
    # Muro di testo di 6 righe consecutive senza newline vuoti
    wall = "\n".join([f"Riga di testo {i} continuata senza interruzioni per il lettore" for i in range(6)])
    metrics = LiftliPostAnalyzer.analyze(wall)

    assert metrics.max_consecutive_lines >= 5
    assert any("muro di testo" in fb.lower() for fb in metrics.feedback)


def test_generator_sprint():
    gen = LinkedInDevPostGenerator()
    post = gen.generate_from_latest_sprint()

    assert "100/100" in post
    assert "TasteSkill" in post
    metrics = LiftliPostAnalyzer.analyze(post)
    assert metrics.score >= 85
    assert metrics.has_cta is True


def test_generator_topic():
    gen = LinkedInDevPostGenerator()
    post = gen.generate_from_topic("Architettura Sovereign Mesh P2P", ["Zero-trust cryptography", "Offline first"])

    assert "Architettura Sovereign Mesh P2P" in post
    assert "Zero-trust cryptography" in post
    metrics = LiftliPostAnalyzer.analyze(post)
    assert metrics.score >= 80
