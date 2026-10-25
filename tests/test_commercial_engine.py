# tests/test_commercial_engine.py
# SPDX-License-Identifier: Apache-2.0
"""
Test suite per HyperSpace Commercial Engine (R&D Commerciale & Monetizzazione).
Verifica calcolo break-even, pilastri commerciali, ranking arcade e generatori di pitch.
"""

import json
import tempfile
from pathlib import Path
from shared.commercial_engine import (
    CommercialEngine,
    COMMERCIAL_PILLARS,
    DEFAULT_PACKAGES,
    TARGET_TIERS
)


def test_commercial_engine_init_and_financials():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CommercialEngine(base_dir=Path(tmpdir))
        status = engine.get_financial_status()

        assert "costs_breakdown_eur" in status
        assert status["total_monthly_burn_rate_eur"] > 0
        assert status["break_even_target_eur"] == 668.0
        assert "break_even_percentage" in status
        assert "active_clients" in status
        assert "target_tiers" in status
        assert len(status["target_tiers"]) == 3


def test_commercial_pillars_and_packages():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CommercialEngine(base_dir=Path(tmpdir))
        pillars = engine.get_commercial_pillars()
        assert len(pillars) == 5
        pillar_ids = [p["id"] for p in pillars]
        assert "b2b_sovereign_appliance" in pillar_ids
        assert "neural_arcade_gamification" in pillar_ids
        assert "autonomous_outreach_swarm" in pillar_ids

        packages = engine.get_packages()
        assert len(packages) >= 4
        pkg_ids = [pkg["id"] for pkg in packages]
        assert "pkg_starter_sponsor" in pkg_ids
        assert "pkg_sovereign_studio_box" in pkg_ids


def test_arcade_scores_and_gamification():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CommercialEngine(base_dir=Path(tmpdir))
        initial_scores = engine.get_arcade_scores()
        assert len(initial_scores) >= 3

        # Registra nuovo punteggio
        res = engine.record_arcade_score("TestChampion", 5200, "neural_invaders")
        assert res["status"] == "recorded"
        assert res["entry"]["player"] == "TestChampion"
        assert res["entry"]["score"] == 5200
        assert res["entry"]["tokens_won"] > 100
        assert res["rank"] == 1  # Dovrebbe essere primo con 5200

        # Verifica persistenza
        updated_scores = engine.get_arcade_scores()
        assert updated_scores[0]["player"] == "TestChampion"


def test_generate_pitch_sectors():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CommercialEngine(base_dir=Path(tmpdir))
        
        # Test Studio Legale / GDPR
        pitch_legal = engine.generate_pitch("Studio Legale e Tributario", company_name="LexConsult Saronno")
        assert "Zero Data Leak" in pitch_legal["subject"]
        assert "GDPR" in pitch_legal["value_prop"]
        assert "LexConsult Saronno" in pitch_legal["linkedin_pitch"]

        # Test Software House
        pitch_dev = engine.generate_pitch("Software House / Web Agency", company_name="CodeDev Milan")
        assert "Cluster Mesh" in pitch_dev["subject"]
        assert "Code Sandbox" in pitch_dev["value_prop"]

        # Test MSP / IT Support
        pitch_msp = engine.generate_pitch("Managed Service Provider IT Helpdesk", company_name="FastIT Varese")
        assert "Agenti Diagnostici" in pitch_msp["subject"]


def test_custom_quote_calculator():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = CommercialEngine(base_dir=Path(tmpdir))
        quote = engine.calculate_custom_quote(
            target_sector="Studi Legali",
            workstations_count=6,
            on_premise_hardware=True,
            autonomous_agents_count=2,
            tokens_monthly_millions=3.0
        )
        assert "comparison" in quote
        comp = quote["comparison"]
        assert comp["cloud_monopoly_annual_eur"] > 0
        assert comp["hyperspace_year1_total_eur"] > 0
        assert "net_savings_year1_eur" in comp
        assert comp["net_savings_year2_eur"] > comp["net_savings_year1_eur"]
