#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/kokoro_tts_service.py
"""Servizio Locale Kokoro TTS con interfaccia compatibile OpenAI (/v1/audio/speech).

Progettato per:
1. Sintesi vocale ultra-realistica per Open WebUI (impostando TTS OpenAI a http://localhost:8880/v1)
2. Sintesi vocale per la Web-Node AI Studio (/web/audio/speech)
3. Voiceover automatico per Reel TikTok/Instagram e narrazioni multimodali.

Supporta voci maschili e femminili (italiano ed inglese):
- af_heart (default, voce calda e naturale)
- af_bella, af_nicole, af_sky
- it_nicola, it_elisa (italiano)
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.request
import wave

from flask import Flask, Response, jsonify, request

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELS_DIR = DATA_DIR / "models" / "kokoro"
DEFAULT_PORT = int(os.getenv("KOKORO_PORT", "8880"))

# URL ufficiali pesi ONNX Kokoro-82M v1.0
KOKORO_ONNX_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_BIN_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

app = Flask("kokoro-tts-service")

_kokoro_instance = None
_kokoro_loaded = False


def _init_kokoro() -> bool:
    """Inizializza l'istanza Kokoro ONNX se i pesi sono disponibili."""
    global _kokoro_instance, _kokoro_loaded
    if _kokoro_loaded:
        return _kokoro_instance is not None

    model_path = MODELS_DIR / "kokoro-v1.0.onnx"
    voices_path = MODELS_DIR / "voices-v1.0.bin"

    if model_path.exists() and voices_path.exists():
        try:
            from kokoro_onnx import Kokoro  # type: ignore
            _kokoro_instance = Kokoro(str(model_path), str(voices_path))
            _kokoro_loaded = True
            print(f"[kokoro] Modello ONNX caricato con successo da {MODELS_DIR}")
            return True
        except Exception as e:
            print(f"[kokoro] Impossibile caricare kokoro_onnx: {e}")

    _kokoro_loaded = True
    return False


def _generate_fallback_wav(text: str, sample_rate: int = 24000) -> bytes:
    """Genera un file WAV valido di sintesi fallback per test o quando i pesi non sono presenti."""
    # Se siamo su macOS e il comando 'say' è disponibile, usalo per generare audio reale
    if sys.platform == "darwin":
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as aiff_f:
                aiff_path = aiff_f.name
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_f:
                wav_path = wav_f.name

            # Voce italiana o inglese
            voice = "Alice" if any(w in text.lower() for w in ("ciao", "questo", "grazie", "sono", "il", "la")) else "Samantha"
            subprocess.run(["say", "-v", voice, "-o", aiff_path, text[:400]], check=True, timeout=10)
            subprocess.run(["ffmpeg", "-y", "-i", aiff_path, "-ar", str(sample_rate), wav_path], capture_output=True, check=True, timeout=10)

            with open(wav_path, "rb") as f:
                wav_bytes = f.read()

            try:
                os.remove(aiff_path)
                os.remove(wav_path)
            except Exception:
                pass
            return wav_bytes
        except Exception:
            pass

    # Sintesi deterministica a onde armoniche modulata sulle sillabe del testo
    duration_s = max(0.8, min(8.0, len(text) * 0.05))
    num_samples = int(duration_s * sample_rate)
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16 bit
        wf.setframerate(sample_rate)

        # Genera tono morbido modulato da formanti (suono di voce sintetico)
        frames = bytearray()
        base_freq = 220.0  # La3
        for i in range(num_samples):
            t = i / sample_rate
            # Modulazione ampiezza (inviluppo sillabico)
            envelope = math.sin(math.pi * (t / duration_s)) * 0.6
            vowel_mod = (math.sin(2 * math.pi * 3.5 * t) + 1.0) * 0.5
            sample_val = math.sin(2 * math.pi * base_freq * t) * 0.6 + math.sin(2 * math.pi * (base_freq * 2) * t) * 0.3
            sample_int = int(sample_val * envelope * vowel_mod * 16000)
            sample_int = max(-32767, min(32767, sample_int))
            frames.extend(struct.pack("<h", sample_int))

        wf.writeframes(frames)

    return buffer.getvalue()


@app.route("/health", methods=["GET"])
@app.route("/", methods=["GET"])
def health():
    has_onnx = _init_kokoro()
    return jsonify({
        "status": "ok",
        "service": "kokoro-tts",
        "engine": "kokoro-onnx" if has_onnx else "system-tts-fallback",
        "port": DEFAULT_PORT,
        "voices": ["af_heart", "af_bella", "af_nicole", "af_sky", "it_nicola", "it_elisa"],
        "openai_compatible": True
    })


@app.route("/v1/models", methods=["GET"])
def list_models():
    return jsonify({
        "object": "list",
        "data": [
            {
                "id": "kokoro",
                "object": "model",
                "created": 1735689600,
                "owned_by": "hexgrad"
            },
            {
                "id": "tts-1",
                "object": "model",
                "created": 1735689600,
                "owned_by": "openai-compatible"
            }
        ]
    })


@app.route("/v1/audio/speech", methods=["POST", "OPTIONS"])
def audio_speech():
    """Endpoint compatibile OpenAI Text-to-Speech (/v1/audio/speech)."""
    if request.method == "OPTIONS":
        return "", 204

    data = request.get_json(force=True, silent=True) or {}
    text = str(data.get("input", "")).strip()
    if not text:
        return jsonify({"error": "Parametro 'input' mancante o vuoto"}), 400

    voice = str(data.get("voice", "af_heart")).strip()
    speed = float(data.get("speed", 1.0))
    fmt = str(data.get("response_format", "mp3")).strip().lower()
    if fmt not in ("mp3", "wav", "ogg"):
        fmt = "wav"

    # 1. Prova sintesi ONNX nativa con Kokoro
    if _init_kokoro() and _kokoro_instance is not None:
        try:
            import soundfile as sf  # type: ignore
            samples, sample_rate = _kokoro_instance.create(text, voice=voice, speed=speed)
            buf = io.BytesIO()
            sf_format = "WAV" if fmt == "wav" else "OGG"
            sf.write(buf, samples, sample_rate, format=sf_format)
            buf.seek(0)
            return Response(buf.read(), mimetype=f"audio/{fmt}")
        except Exception as exc:
            print(f"[kokoro] Errore sintesi ONNX: {exc}, passo al fallback.")

    # 2. Sintesi Fallback deterministica (WAV)
    wav_bytes = _generate_fallback_wav(text)
    return Response(wav_bytes, mimetype="audio/wav")


def download_models():
    """Scarica i pesi ONNX Kokoro-82M in data/models/kokoro/."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "kokoro-v1.0.onnx"
    voices_path = MODELS_DIR / "voices-v1.0.bin"

    print("=== Download Pesi Kokoro-82M ONNX ===")
    if not model_path.exists():
        print(f"Download kokoro-v1.0.onnx (~300 MB) da {KOKORO_ONNX_URL}...")
        urllib.request.urlretrieve(KOKORO_ONNX_URL, model_path)
        print("Model ONNX scaricato.")
    else:
        print("kokoro-v1.0.onnx già presente.")

    if not voices_path.exists():
        print(f"Download voices-v1.0.bin (~20 MB) da {VOICES_BIN_URL}...")
        urllib.request.urlretrieve(VOICES_BIN_URL, voices_path)
        print("Voices BIN scaricato.")
    else:
        print("voices-v1.0.bin già presente.")
    print("Download completato con successo!")


def main():
    parser = argparse.ArgumentParser(description="Kokoro TTS Service (OpenAI-compatible /v1/audio/speech)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Porta di ascolto (default {DEFAULT_PORT})")
    parser.add_argument("--host", default="0.0.0.0", help="Host di ascolto (default 0.0.0.0)")
    parser.add_argument("--download-models", action="store_true", help="Scarica i pesi ONNX ufficiali")
    args = parser.parse_args()

    if args.download_models:
        download_models()
        return

    _init_kokoro()
    print(f"[kokoro] Avvio servizio su http://{args.host}:{args.port}")
    print(f"[kokoro] Endpoint OpenAI TTS disponibile su http://{args.host}:{args.port}/v1/audio/speech")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
