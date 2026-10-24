# SPDX-License-Identifier: Apache-2.0
"""
Tests for HyperSpace Comprehensive SEO & GEO Enhancements.
Verifies:
1. XML Sitemap generation & standard conformity.
2. robots.txt Sitemap directive.
3. AI discovery endpoints (.well-known/ai.txt, ai/summary.json, ai/faq.json, ai/service.json).
4. Canonical tags, OpenGraph and Twitter Cards on all web-node pages.
5. Schema.org JSON-LD structured data on index.html.
6. Local SEO audit API returns near-perfect health scores (>= 98/100).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import urllib.request
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_NODE_DIR = REPO_ROOT / "web-node"


def test_sitemap_xml_exists_and_valid():
    sitemap = WEB_NODE_DIR / "sitemap.xml"
    assert sitemap.exists(), "sitemap.xml must exist in web-node"
    content = sitemap.read_text(encoding="utf-8")
    assert '<?xml version="1.0" encoding="UTF-8"?>' in content
    assert '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' in content
    assert "https://www.zerozerocomputer.it/" in content
    assert "https://www.zerozerocomputer.it/progetto.html" in content
    assert "https://www.zerozerocomputer.it/chat.html" in content


def test_robots_txt_sitemap_directive():
    robots = WEB_NODE_DIR / "robots.txt"
    assert robots.exists(), "robots.txt must exist"
    content = robots.read_text(encoding="utf-8")
    assert "Sitemap: https://www.zerozerocomputer.it/sitemap.xml" in content


def test_ai_discovery_endpoints_exist():
    ai_txt = WEB_NODE_DIR / ".well-known" / "ai.txt"
    assert ai_txt.exists(), ".well-known/ai.txt must exist"
    assert "User-Agent: *" in ai_txt.read_text(encoding="utf-8")

    ai_dir = WEB_NODE_DIR / "ai"
    for jfile in ["summary.json", "faq.json", "service.json"]:
        p = ai_dir / jfile
        assert p.exists(), f"ai/{jfile} must exist"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert len(data) > 0


def test_html_pages_have_canonical_og_and_schema():
    html_files = sorted(WEB_NODE_DIR.glob("*.html"))
    assert len(html_files) >= 12, "Must have at least 12 HTML pages"

    for f in html_files:
        content = f.read_text(encoding="utf-8")
        assert 'rel="canonical"' in content or "rel='canonical'" in content, f"{f.name} missing canonical link"
        assert 'property="og:title"' in content or "property='og:title'" in content, f"{f.name} missing og:title"
        assert 'name="twitter:card"' in content or "name='twitter:card'" in content, f"{f.name} missing twitter:card"
        assert 'application/ld+json' in content, f"{f.name} missing Schema.org JSON-LD"


def test_index_html_has_rich_schemas():
    index_file = WEB_NODE_DIR / "index.html"
    content = index_file.read_text(encoding="utf-8")
    assert '"@type": "Organization"' in content
    assert '"@type": "WebSite"' in content
    assert '"@type": "SoftwareApplication"' in content
    assert '"@type": "FAQPage"' in content


def test_cockpit_seo_audit_scores():
    try:
        req = urllib.request.Request("http://localhost:8090/api/seo-audit")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            pages = data.get("pages", [])
            assert len(pages) >= 12
            avg_score = sum(p["score"] for p in pages) / len(pages)
            assert avg_score >= 98.0, f"Average SEO score {avg_score} must be >= 98.0"
    except urllib.error.URLError:
        pytest.skip("Cockpit service not reachable on :8090 for live test")
