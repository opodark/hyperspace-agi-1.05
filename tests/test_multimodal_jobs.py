# SPDX-License-Identifier: Apache-2.0
"""Test per la pipeline multimodale (Video, Musica, PDF e Kokoro TTS)."""
import io
import json
import pytest

from shared.image_jobs import (
    determina_famiglia,
    determina_tipo,
    nuovo_job,
    workflow_video,
    workflow_music,
    immagini_da_history,
    FAMIGLIE_MULTIMODALI,
    FAMIGLIA_VIDEO_LTX,
    FAMIGLIA_MUSICA_STABLE,
)
from shared.pdf_generator import generate_pdf_from_markdown


def test_determina_tipo_e_famiglie():
    assert determina_tipo("video:ltx") == "video"
    assert determina_tipo("video:wan2") == "video"
    assert determina_tipo("music:stable-audio") == "music"
    assert determina_tipo("music:musicgen") == "music"
    assert determina_tipo("sdxl-turbo") == "image"
    assert determina_tipo("sd15") == "image"

    assert "video:ltx" in FAMIGLIE_MULTIMODALI
    assert "music:stable-audio" in FAMIGLIE_MULTIMODALI


def test_nuovo_job_video():
    job = nuovo_job(
        prompt="A robotic eagle soaring through neon clouds",
        famiglia=FAMIGLIA_VIDEO_LTX,
        frames=49,
        fps=24,
    )
    assert job["tipo"] == "video"
    assert job["famiglia"] == FAMIGLIA_VIDEO_LTX
    assert job["frames"] == 49
    assert job["fps"] == 24
    assert "robotic eagle" in job["prompt"]


def test_nuovo_job_music():
    job = nuovo_job(
        prompt="Cyberpunk synthwave bassline 120 bpm",
        famiglia=FAMIGLIA_MUSICA_STABLE,
        duration_seconds=30.0,
    )
    assert job["tipo"] == "music"
    assert job["famiglia"] == FAMIGLIA_MUSICA_STABLE
    assert job["duration_seconds"] == 30.0
    assert "synthwave" in job["prompt"]


def test_workflow_video_graph():
    job = {
        "prompt": "Cosmic aurora timelapse",
        "famiglia": FAMIGLIA_VIDEO_LTX,
        "frames": 33,
        "fps": 16,
        "passi": 25,
        "seed": 42,
    }
    graph = workflow_video(job)
    assert isinstance(graph, dict)
    assert "501" in graph  # LTXVideoLoader
    assert "502" in graph  # CLIPTextEncode (prompt)
    assert "504" in graph  # EmptyLTXLatentVideo
    assert "505" in graph  # KSampler
    assert "507" in graph  # VHS_VideoCombine
    assert graph["505"]["inputs"]["steps"] == 25
    assert graph["505"]["inputs"]["seed"] == 42


def test_workflow_music_graph():
    job = {
        "prompt": "Lofi chill beat study session",
        "famiglia": FAMIGLIA_MUSICA_STABLE,
        "duration_seconds": 45.0,
        "passi": 30,
        "seed": 123,
    }
    graph = workflow_music(job)
    assert isinstance(graph, dict)
    assert "601" in graph  # StableAudioLoader
    assert "602" in graph  # StableAudioTextEncode
    assert "603" in graph  # StableAudioSampler
    assert "604" in graph  # SaveAudio
    assert graph["603"]["inputs"]["seconds"] == 45.0
    assert graph["603"]["inputs"]["steps"] == 30
    assert graph["603"]["inputs"]["seed"] == 123


def test_immagini_da_history_estende_multimediali():
    history = {
        "outputs": {
            "10": {
                "videos": [{"filename": "clip1.mp4", "subfolder": "video"}],
            },
            "20": {
                "audio": [{"filename": "song1.mp3", "subfolder": ""}],
            },
            "30": {
                "images": [{"filename": "cover.png", "subfolder": "preview"}],
            },
        }
    }
    estratti = immagini_da_history(history)
    assert "video/clip1.mp4" in estratti
    assert "song1.mp3" in estratti
    assert "preview/cover.png" in estratti


def test_pdf_generation_valid():
    md = """# Relazione Esecutiva HyperSpace

Benvenuto nella presentazione del sistema distribuito.

## Punti Chiave
- **Autonomia**: agenti coordinati via mesh
- **Multimodalità**: video, musica, TTS e immagini
- **Prestazioni**: generazione deterministica e ultra-veloce

| Metrica | Valore | Note |
|---|---|---|
| Latenza PDF | <50ms | Locale ReportLab |
| TTS Kokoro | 82M parametri | OpenAI compatible |

```python
def genera():
    return "ok"
```
"""
    pdf_bytes = generate_pdf_from_markdown(md, title="Test Report", author="HyperSpace")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000


def test_pdf_generation_empty():
    pdf_bytes = generate_pdf_from_markdown("", title="Empty")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
