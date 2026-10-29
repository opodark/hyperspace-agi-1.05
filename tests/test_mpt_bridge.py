# SPDX-License-Identifier: Apache-2.0
"""Test del ponte MoneyPrinterTurbo: musica solo con licenza, richiesta corretta."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

BRIDGE = Path(__file__).resolve().parents[1] / "integrations" / "moneyprinter" / "mpt_bridge.py"
spec = importlib.util.spec_from_file_location("mpt_bridge", BRIDGE)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def _music(tmp_path, brani, files):
    (tmp_path / "licenze.json").write_text(json.dumps({"brani": brani}), encoding="utf-8")
    for f in files:
        (tmp_path / f).write_bytes(b"x")
    return tmp_path


def test_only_registered_tracks_with_license_and_file_are_usable(tmp_path):
    d = _music(tmp_path, [
        {"file": "ok.mp3", "licenza": "CC BY 4.0", "fonte": "freemusicarchive"},
        {"file": "senza-licenza.mp3", "licenza": ""},
        {"file": "manca.mp3", "licenza": "CC0"},
        {"file": "../../segreto.mp3", "licenza": "CC0"},
        {"file": "testo.txt", "licenza": "CC0"},
    ], ["ok.mp3", "senza-licenza.mp3", "non-registrato.mp3", "testo.txt"])
    assert [t["file"] for t in bridge.licensed_tracks(d)] == ["ok.mp3"]


def test_no_licenses_file_means_no_music(tmp_path):
    assert bridge.licensed_tracks(tmp_path) == []
    assert bridge.choose_music("auto", []) is None


def test_choose_music_refuses_unregistered_file():
    tracks = [{"file": "ok.mp3", "licenza": "CC0"}]
    assert bridge.choose_music("none", tracks) is None
    assert bridge.choose_music("ok.mp3", tracks)["file"] == "ok.mp3"
    with pytest.raises(SystemExit):
        bridge.choose_music("youtube-hit.mp3", tracks)


def test_payload_without_music_disables_bgm():
    args = SimpleNamespace(subject="Mesh", script_file=None, language="it-IT", aspect="9:16",
                           clip_duration=4, voice="kokoro:if_sara", paragraphs=1, source="pixabay")
    p = bridge.build_payload(args, None)
    assert p["bgm_type"] == "" and p["bgm_file"] == ""
    p = bridge.build_payload(args, {"file": "ok.mp3", "licenza": "CC0"})
    assert p["bgm_type"] == "custom" and p["bgm_file"] == "ok.mp3"
    assert p["voice_name"] == "kokoro:if_sara" and p["video_language"] == "it-IT"
    assert p["video_source"] == "pixabay"


def test_slugify():
    assert bridge.slugify("Che cos'è una mesh di AI locali?") == "che-cos-e-una-mesh-di-ai-locali"
    assert bridge.slugify("!!!") == "video"
