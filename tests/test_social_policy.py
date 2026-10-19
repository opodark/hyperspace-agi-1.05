# SPDX-License-Identifier: Apache-2.0
"""La politica social: guardie e finestre, senza rete."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.social_policy import SocialPolicy  # noqa: E402

ROMA = ZoneInfo("Europe/Rome")


def policy(**overrides):
    return SocialPolicy(overrides)


def test_x_e_spento_di_default():
    p = SocialPolicy()
    assert p.enabled
    assert p.canale_abilitato("instagram")
    assert not p.canale_abilitato("x")


def test_publish_disabled_blocks_everything():
    p = policy(SOCIAL_PUBLISH_ENABLED="false")
    assert not p.enabled
    assert not p.canale_abilitato("instagram")
    ok, _ = p.check_voce({"tipo": "sogno", "author": "anna", "testo": "x"},
                         "instagram", datetime(2026, 10, 6, 8, 0, tzinfo=ROMA))
    assert not ok


def test_check_voce_richiede_disclosure_ia_su_instagram():
    p = policy()
    voce = {"tipo": "sogno", "author": "anna", "testo": "un sogno",
            "caption": "🌙 Sogno di Anna\n\nun sogno"}
    ok, motivo = p.check_voce(voce, "instagram", datetime(2026, 10, 6, 8, 0, tzinfo=ROMA))
    assert not ok
    assert "disclosure" in motivo


def test_check_voce_accetta_un_sogno_valido():
    p = policy()
    voce = {"tipo": "sogno", "author": "anna", "testo": "un sogno",
            "caption": "🌙 Sogno di Anna\n\nun sogno\n\n#AIDreams"}
    ok, _ = p.check_voce(voce, "instagram", datetime(2026, 10, 6, 8, 0, tzinfo=ROMA))
    assert ok


def test_check_voce_blocca_il_contenuto_esplicito():
    p = policy()
    voce = {"tipo": "sogno", "author": "anna", "testo": "un racconto nudo",
            "caption": "🌙 Sogno di Anna\n\nun racconto nudo\n\n#AIDreams"}
    ok, motivo = p.check_voce(voce, "instagram", datetime(2026, 10, 6, 8, 0, tzinfo=ROMA))
    assert not ok
    assert "esplicito" in motivo


def test_check_voce_applica_il_tetto_per_tipo():
    p = policy()
    voce = {"tipo": "sogno", "author": "anna", "testo": "s", "caption": "#AIDreams"}
    adesso = datetime(2026, 10, 6, 8, 0, tzinfo=ROMA)
    ok, _ = p.check_voce(voce, "instagram", adesso, conteggi={"sogno": 0})
    assert ok
    ok, motivo = p.check_voce(voce, "instagram", adesso, conteggi={"sogno": 1})
    assert not ok
    assert "sogno" in motivo


def test_check_voce_applica_il_tetto_del_canale():
    p = policy(SOCIAL_MAX_PER_DAY="2")
    voce = {"tipo": "poesia", "author": "anna", "testo": "versi", "caption": "#AIPoetry"}
    adesso = datetime(2026, 10, 6, 13, 0, tzinfo=ROMA)
    # la poesia non ha superato il suo tetto (0 < 1), ma il canale è pieno (2/2)
    ok, motivo = p.check_voce(voce, "instagram", adesso,
                              conteggi={"sogno": 1, "dialogo": 1})
    assert not ok
    assert "canale" in motivo


def test_check_voce_applica_il_gap_minimo():
    p = policy(SOCIAL_MIN_GAP_MINUTES="180")
    voce = {"tipo": "sogno", "author": "anna", "testo": "s", "caption": "#AIDreams"}
    adesso = datetime(2026, 10, 6, 8, 0, tzinfo=ROMA)
    ok, _ = p.check_voce(voce, "instagram", adesso, conteggi={"sogno": 0},
                         ultimo_ts=adesso.timestamp() - 181 * 60)
    assert ok
    ok, _ = p.check_voce(voce, "instagram", adesso, conteggi={"sogno": 0},
                         ultimo_ts=adesso.timestamp() - 10)
    assert not ok


def test_finestra_sogno_alle_tre_apre_alle_sette():
    p = policy()
    tre = datetime(2026, 10, 6, 3, 0, tzinfo=ROMA)
    istante, dentro = p.finestra("sogno", "instagram", tre)
    assert not dentro
    assert istante == datetime(2026, 10, 6, 7, 0, tzinfo=ROMA)


def test_finestra_sogno_dopo_mezzogiorno_apre_domani():
    p = policy()
    mezzogiorno = datetime(2026, 10, 6, 12, 0, tzinfo=ROMA)
    istante, dentro = p.finestra("sogno", "instagram", mezzogiorno)
    assert not dentro
    assert istante == datetime(2026, 10, 7, 7, 0, tzinfo=ROMA)


def test_finestra_x_sogno_e_mezzora_dopo():
    p = policy()
    tre = datetime(2026, 10, 6, 3, 0, tzinfo=ROMA)
    istante, dentro = p.finestra("sogno", "x", tre)
    assert not dentro
    assert istante == datetime(2026, 10, 6, 7, 30, tzinfo=ROMA)


def test_finestra_dentro_risponde_con_adesso():
    p = policy()
    otto = datetime(2026, 10, 6, 8, 30, tzinfo=ROMA)
    istante, dentro = p.finestra("sogno", "instagram", otto)
    assert dentro
    assert istante == otto


def test_persona_e_tipo_sconosciuti_respinti():
    p = policy()
    adesso = datetime(2026, 10, 6, 8, 0, tzinfo=ROMA)
    ok, _ = p.check_voce({"tipo": "sogno", "author": "bob", "testo": "x",
                          "caption": "#AIDreams"}, "instagram", adesso)
    assert not ok
    ok, _ = p.check_voce({"tipo": "storia", "author": "anna", "testo": "x",
                          "caption": "#AIDreams"}, "instagram", adesso)
    assert not ok
