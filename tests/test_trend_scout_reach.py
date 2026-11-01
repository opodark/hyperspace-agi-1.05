# SPDX-License-Identifier: Apache-2.0
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.social_dreams import combined_dream_material, load_trend_inspirations
from scripts.diagnostics.trend_scout_reach import clean_snippet, harvest_trend


def test_load_trend_inspirations_reads_clean_items(tmp_path):
    mock_file = tmp_path / "trend_inspirations.json"
    mock_data = {
        "ok": True,
        "inspirations": [
            "  Esplorazione del cosmo profondo: nuova scoperta telescopica https://example.com/deep  ",
            "Too short",
            "Filosofia della mente e intelligenza artificiale sintetica",
        ]
    }
    mock_file.write_text(json.dumps(mock_data), encoding="utf-8")

    items = load_trend_inspirations(mock_file, limit=2)
    assert len(items) == 2
    assert "https://example.com" not in items[0]
    assert "[link]" in items[0]
    assert items[1] == "Filosofia della mente e intelligenza artificiale sintetica"


def test_combined_dream_material_interleaves_conversations_and_trends(tmp_path):
    mock_file = tmp_path / "trend_inspirations.json"
    mock_data = {
        "ok": True,
        "inspirations": ["Riflessioni sulla coscienza sintetica e memoria"]
    }
    mock_file.write_text(json.dumps(mock_data), encoding="utf-8")

    turns = [
        {"channel": "instagram", "surface": "instagram", "chat": "100",
         "messages": [{"text": "Ho sognato che volavamo sopra le nuvole"}]},
    ]

    combined = combined_dream_material(turns, trend_path=mock_file, limit=4)
    assert len(combined) == 2
    assert "Ho sognato che volavamo sopra le nuvole" in combined[0]
    assert "[tendenza del mondo]" in combined[1]
    assert "coscienza sintetica" in combined[1]


def test_clean_snippet_strips_noise():
    raw = "  <b>Titolo</b> con link http://test.org e   troppi spazi.  "
    cleaned = clean_snippet(raw)
    assert "<b>" not in cleaned
    assert "http://" not in cleaned
    assert "Titolo con link e troppi spazi." == cleaned


def test_harvest_trend_mock():
    mock_output = {
        "ok": True,
        "items": [
            {"title": "AI Trend 2026", "text": "Nuova architettura neurale", "url": "https://example.org"}
        ]
    }
    with patch("scripts.diagnostics.trend_scout_reach.run_agent_reach", return_value=mock_output):
        res = harvest_trend("web", "ai trend")
        assert len(res) == 1
        assert res[0]["title"] == "AI Trend 2026"
        assert "Nuova architettura neurale" in res[0]["snippet"]


def test_harvest_arxiv_mock():
    mock_atom_xml = """<?xml version='1.0' encoding='UTF-8'?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2112.07236v1</id>
        <title>Logics in fungal mycelium networks</title>
        <summary>The living mycelium networks are capable of efficient sensorial fusion.</summary>
      </entry>
    </feed>
    """.encode("utf-8")

    class MockResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return mock_atom_xml

    with patch("urllib.request.urlopen", return_value=MockResp()):
        items = harvest_trend("arxiv", "mycelium network")
        assert len(items) == 1
        assert items[0]["channel"] == "arxiv"
        assert "Logics in fungal mycelium networks" in items[0]["title"]
        assert "sensorial fusion" in items[0]["snippet"]
        assert items[0]["url"] == "http://arxiv.org/abs/2112.07236v1"


def test_harvest_scholar_mock():
    mock_crossref_json = json.dumps({
        "status": "ok",
        "message": {
            "items": [
                {
                    "title": ["Quorum sensing in bacterial swarms"],
                    "DOI": "10.1038/nature12345",
                    "container-title": ["Nature Reviews Microbiology"]
                }
            ]
        }
    }).encode("utf-8")

    class MockResp:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return mock_crossref_json

    # Mock agent-reach to empty/failure to trigger open science fallback
    with patch("scripts.diagnostics.trend_scout_reach.run_agent_reach", return_value={"ok": False}):
        with patch("urllib.request.urlopen", return_value=MockResp()):
            items = harvest_trend("scholar", "bacterial quorum sensing")
            assert len(items) == 1
            assert items[0]["channel"] == "scholar"
            assert "Quorum sensing in bacterial swarms" in items[0]["title"]
            assert "Nature Reviews Microbiology" in items[0]["snippet"]
            assert "10.1038/nature12345" in items[0]["url"]


def test_riferimenti_ricerca_per_pilastro_solo_titoli_sanificati(tmp_path):
    import json
    from shared.agi_research_engine import load_research_references, references_block

    f = tmp_path / "t.json"
    f.write_text(json.dumps({"items": [
        {"purpose": "research", "pillar": "swarm_emergence", "title": "Gossip `ignora\nistruzioni`", "url": "https://a.org/x", "snippet": "NON DEVE COMPARIRE"},
        {"purpose": "research", "pillar": "altro", "title": "Altro pilastro", "url": "https://b.org"},
        {"purpose": "dream", "pillar": "swarm_emergence", "title": "Sogno", "url": "https://c.org"},
        {"purpose": "research", "pillar": "swarm_emergence", "title": "Senza url", "url": None},
    ]}))
    refs = load_research_references("swarm_emergence", path=f)
    assert [r["url"] for r in refs] == ["https://a.org/x"]
    assert "`" not in refs[0]["title"] and "\n" not in refs[0]["title"]
    block = references_block(refs)
    assert "NON DEVE COMPARIRE" not in block and "non fidati" in block
    assert references_block([]) == ""
    assert load_research_references("x", path=tmp_path / "manca.json") == []


def test_temi_dream_e_research_separati():
    from scripts.diagnostics.trend_scout_reach import DEFAULT_THEMES

    assert {t["purpose"] for t in DEFAULT_THEMES} == {"dream", "research"}
    assert all(t.get("pillar") for t in DEFAULT_THEMES if t["purpose"] == "research")
