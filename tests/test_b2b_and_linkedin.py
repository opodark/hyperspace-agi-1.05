"""
Tests for B2B target research and LinkedIn bulletin generator.
Ensures both scripts handle data formatting, filtering, and reporting properly.
"""

import os
import json
import pytest
from pathlib import Path
from scripts.publish_linkedin_bulletins import generate_bulletin_posts, BULLETINS, get_next_daily_post
from scripts.diagnostics.b2b_target_research import TARGET_QUERIES, DISALLOWED_DOMAINS

def test_linkedin_bulletin_generator():
    res = generate_bulletin_posts()
    assert res is not None
    assert res["total_posts"] >= 3
    assert len(res["posts"]) >= 3
    
    # Verify presence of Target 1, 3, and 4
    targets_str = " ".join([p["target"] for p in res["posts"]])
    assert "Target 1" in targets_str
    assert "Target 3" in targets_str
    assert "Target 4" in targets_str
    
    # Target 2 (Reel Editor) MUST NOT be present
    assert "Target 2" not in targets_str
    assert "Reel Editor" not in targets_str

    # Test get_next_daily_post
    next_post = get_next_daily_post()
    assert next_post is not None
    assert "text" in next_post
    assert "https://www.zerozerocomputer.it" in next_post["text"]

def test_b2b_target_config():
    assert len(TARGET_QUERIES) == 3
    target_ids = [t["target_id"] for t in TARGET_QUERIES]
    assert "target_3_software_agencies" in target_ids
    assert "target_4_msp_helpdesk" in target_ids
    assert "target_1_studi_professionali_gdpr" in target_ids
    
    # Check disallowed domains
    assert "wikipedia.org" in DISALLOWED_DOMAINS
    assert "paginegialle.it" in DISALLOWED_DOMAINS
