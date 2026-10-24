# SPDX-License-Identifier: Apache-2.0
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-plane"))

from connectors.scout import ScoutConnector
from connectors.seo import SeoConnector
from scripts.diagnostics.site_seo_optimizer import save_report


def test_scout_connector_tools_and_execution():
    conn = ScoutConnector()
    tools = conn.get_tools()
    assert len(tools) == 3
    tool_names = [t["function"]["name"] for t in tools]
    assert "scout_web_read" in tool_names
    assert "scout_get_trends" in tool_names
    assert "scout_harvest_trends" in tool_names

    # Test scout_get_trends with fallback
    res_raw = conn.execute("scout_get_trends", {"limit": 2})
    res = json.loads(res_raw)
    assert res["ok"] is True
    assert "inspirations" in res


def test_seo_connector_tools_and_execution(tmp_path):
    conn = SeoConnector()
    tools = conn.get_tools()
    assert len(tools) == 4
    tool_names = [t["function"]["name"] for t in tools]
    assert "seo_audit_site" in tool_names
    assert "seo_get_latest_report" in tool_names
    assert "seo_inspect_llms" in tool_names
    assert "seo_generate_schema_jsonld" in tool_names

    # Test schema generation
    schema_res_raw = conn.execute("seo_generate_schema_jsonld", {"name": "TestCorp", "url": "https://test.corp"})
    schema_res = json.loads(schema_res_raw)
    assert schema_res["ok"] is True
    assert "Organization" in schema_res["schema_json"]
    assert "SoftwareApplication" in schema_res["schema_json"]


def test_site_seo_optimizer_save_report(tmp_path):
    mock_report = tmp_path / "report.json"
    mock_hist = tmp_path / "history.json"
    with patch("scripts.diagnostics.site_seo_optimizer.REPORT_FILE", mock_report), \
         patch("scripts.diagnostics.site_seo_optimizer.HISTORY_FILE", mock_hist):
        ok = save_report({"url": "https://test.local", "geo_score": 75})
        assert ok is True
        assert mock_report.is_file()
        assert mock_hist.is_file()
