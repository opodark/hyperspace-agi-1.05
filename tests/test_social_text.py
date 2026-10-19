# SPDX-License-Identifier: Apache-2.0
"""Composizione delle didascalie: disclosure IA e adattamento per X."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.social_text import (adatta_per_x, compose_caption,  # noqa: E402
                                link_profilo_ig)


def test_compose_caption_sogno_porta_il_marcatore_ia():
    caption = compose_caption("sogno", "anna", "ho sognato il mare")
    assert "#AIDreams" in caption
    assert "Anna" in caption
    assert "ho sognato il mare" in caption


def test_compose_caption_poesia_e_dialogo_portano_il_loro_marcatore():
    assert "#AIPoetry" in compose_caption("poesia", "aurora", "versi")
    assert "#AIDialogo" in compose_caption("dialogo", "anna", "a", testo_b="b")


def test_adatta_per_x_resta_sotto_280_e_conserva_il_link():
    caption = compose_caption("sogno", "anna", "ho sognato il mare " * 20)
    out = adatta_per_x(caption, profilo_ig="https://instagram.com/aurora.anna")
    assert len(out) <= 280
    assert out.endswith("https://instagram.com/aurora.anna")
    assert "#AIDreams" in out


def test_link_profilo_ig():
    assert link_profilo_ig("@aurora.anna") == "https://instagram.com/aurora.anna"
    assert link_profilo_ig("") == ""
