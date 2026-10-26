# tests/test_arcade_games_and_cockpit.py
# SPDX-License-Identifier: Apache-2.0
"""
Test suite per la Sala Giochi Neurale Arcade & integrazione Cockpit / Commercial Engine.
Verifica integrità file HTML (3 giochi Canvas), sintesi Web Audio, rotte Cockpit e tokenomics.
"""

import json
from pathlib import Path
import tempfile
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
from shared.commercial_engine import CommercialEngine
from scripts.diagnostics.orchestrate_arcade_gameplay import (
    check_html_integrity,
    run_full_diagnostic,
    ARCADE_HTML
)


def test_arcade_html_file_exists_and_structure():
    """Verifica che arcade.html esista e contenga tutti i 3 giochi retro."""
    assert ARCADE_HTML.exists(), f"arcade.html non trovato in {ARCADE_HTML}"
    content = ARCADE_HTML.read_text(encoding="utf-8")

    # Verifica Canvas CRT
    assert "<canvas id=\"gameCanvas\"" in content
    assert "class=\"arcade-crt" in content

    # Verifica i 3 giochi
    assert "Neural Invaders" in content
    assert "Pong vs AGI" in content
    assert "Vector Matrix" in content
    assert "updateInvaders" in content
    assert "updatePong" in content
    assert "updateMatrix" in content

    # Verifica boss fight in invaders
    assert "MONOLITHIC CLOUD BOSS" in content

    # Verifica sintetizzatore chiptune Web Audio
    assert "ArcadeAudio" in content
    assert "AudioContext" in content

    # Verifica controlli e leaderboard
    assert "ctrlBtn1" in content
    assert "ctrlBtn2" in content
    assert "ctrlAction" in content
    assert "arcadeLeaderboard" in content


def test_arcade_html_integrity_diagnostic():
    """Verifica che la funzione diagnostica confermi tutti i check su arcade.html."""
    res = check_html_integrity()
    assert res["ok"] is True
    checks = res["checks"]
    assert checks["canvas_crt"] is True
    assert checks["chiptune_audio"] is True
    assert checks["game_invaders"] is True
    assert checks["game_pong"] is True
    assert checks["game_matrix"] is True
    assert checks["leaderboard_hook"] is True
    assert checks["controls_onscreen"] is True


def test_commercial_engine_arcade_gamification():
    """Verifica il calcolo dei token premio per ciascuno dei 3 giochi."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CommercialEngine(base_dir=Path(tmpdir))
        # Initial scores include 4820, 3950, 2740

        # Partita record a Neural Invaders (> 4820)
        res1 = engine.record_arcade_score("PilotOne", 5200, "invaders")
        assert res1["status"] == "recorded"
        assert res1["entry"]["tokens_won"] == 130  # 5200 / 40
        assert res1["rank"] == 1

        # Partita a Pong vs AGI (> 5200)
        res2 = engine.record_arcade_score("AgiHunter", 6000, "pong")
        assert res2["entry"]["tokens_won"] == 150  # 6000 / 40
        assert res2["rank"] == 1  # 6000 > 5200

        # Partita a Vector Matrix
        res3 = engine.record_arcade_score("MatrixRacer", 3000, "matrix")
        assert res3["entry"]["tokens_won"] == 75  # 3000 / 40
        assert res3["rank"] >= 2

        scores = engine.get_arcade_scores()
        top_players = [s["player"] for s in scores[:2]]
        assert "AgiHunter" in top_players
        assert "PilotOne" in top_players


def test_run_full_diagnostic_dry_run():
    """Verifica che il diagnostic runner non sollevi eccezioni e restituisca un report strutturato."""
    report = run_full_diagnostic(simulate=False)
    assert "status" in report
    assert "html_integrity" in report
    assert report["html_integrity"]["ok"] is True
    assert "cockpit_routes" in report
    assert "nodes_telemetry" in report
