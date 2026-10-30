# SPDX-License-Identifier: Apache-2.0
"""Estensioni del motore dei reel per il video YouTube: immagini incorporate, 16:9 nativo, mix audio a capitoli."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

MOTION = Path(__file__).resolve().parents[1] / "integrations" / "tiktok_editor" / "motion"
sys.path.insert(0, str(MOTION))
import build  # noqa: E402
import mix_youtube  # noqa: E402

REEL = "youtube-presentazione-2026-10-30"


def _assets_present():
    meta = build.read_meta((build.REELS / f"{REEL}.js").read_text(encoding="utf-8"), REEL)
    return all((build.REPO / p).is_file() for p in meta["assets"].values())


needs_assets = pytest.mark.skipif(not _assets_present(), reason="ritagli delle schermate assenti (data/ è ignorata da git)")


@needs_assets
def test_assets_are_inlined_as_data_uris_and_page_is_16x9():
    page, meta = build.build_page(REEL, "16:9")
    assert meta["size"] == (1920, 1080) and meta["formats"] == ["16:9"]
    m = re.search(r"const ASSETS = (\{.*\});", page)
    assets = json.loads(m.group(1))
    assert set(assets) == set(meta["assets"]) and all(u.startswith("data:image/png;base64,") for u in assets.values())
    assert "native: true" in page and "{{" not in page


def test_reel_without_assets_gets_empty_assets_object():
    page, _ = build.build_page("voglio-te-2026-10-29")
    assert "const ASSETS = {};" in page


def test_asset_outside_repo_is_refused(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG")
    with pytest.raises(SystemExit):
        build.asset_uris({"assets": {"x": str(img)}}, "t")


def test_mix_command_delays_each_voice_and_ducks_music(tmp_path):
    meta = mix_youtube.read_meta(REEL)
    meta = {**meta, "voice": [{"file": v["file"], "at": v["at"]} for v in meta["voice"]]}
    # i file audio sono in data/ (ignorata da git): per il test basta che esistano
    f = build.REPO / "data" / "reels" / "youtube-audio"
    if not all((build.REPO / v["file"]).is_file() for v in meta["voice"]):
        pytest.skip("voci registrate assenti")
    music = tmp_path / "m.mp3"
    music.write_bytes(b"x")
    cmd = mix_youtube.build_command(tmp_path / "v.mp4", tmp_path / "o.mp4", meta, music, -20.0)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert fc.count("adelay=") == len(meta["voice"]) and "sidechaincompress" in fc and "-stream_loop" in cmd
    assert "adelay=1000|1000" in fc and f"{int(meta['voice'][-1]['at'] * 1000)}" in fc


def test_music_without_license_is_refused_unless_draft(tmp_path):
    mp3 = tmp_path / "b.mp3"
    mp3.write_bytes(b"x")
    vid = tmp_path / "v.mp4"
    vid.write_bytes(b"x")
    r = subprocess.run([sys.executable, str(MOTION / "mix_youtube.py"), REEL, "--video", str(vid), "--music", str(mp3)],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "licenza" in (r.stderr + r.stdout)
