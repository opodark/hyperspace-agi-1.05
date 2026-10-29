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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import voicebox_client  # noqa: E402  (voci clonate: voice = "voicebox:<profilo>[@motore]")

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELS_DIR = DATA_DIR / "models" / "kokoro"
DEFAULT_PORT = int(os.getenv("KOKORO_PORT", "8880"))
DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "af_nicole")

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


VOICE_ALIASES: Dict[str, str] = {
    # Voci ufficiali Kokoro v1.0
    "if_sara": "if_sara",        # Italiano Donna (Sara)
    "im_nicola": "im_nicola",    # Italiano Uomo (Nicola)
    "af_heart": "af_heart",      # Inglese USA Donna (Heart)
    "af_bella": "af_bella",      # Inglese USA Donna (Bella)
    "af_nicole": "af_nicole",    # Inglese USA Donna (Nicole)
    "af_sky": "af_sky",          # Inglese USA Donna (Sky)
    "am_michael": "am_michael",  # Inglese USA Uomo (Michael)
    "am_adam": "am_adam",        # Inglese USA Uomo (Adam)
    "bf_alice": "bf_alice",      # Inglese UK Donna (Alice)
    "bm_george": "bm_george",    # Inglese UK Uomo (George)
    # Alias amichevoli per l'italiano
    "it": "if_sara",
    "italiano": "if_sara",
    "italian": "if_sara",
    "sara": "if_sara",
    "nicola": "im_nicola",
    "it_sara": "if_sara",
    "it_nicola": "im_nicola",
    "it_elisa": "if_sara",
    # Mappatura dai default OpenAI (usati dai dropdown di Open WebUI)
    "alloy": "af_heart",
    "echo": "im_nicola",
    "fable": "bf_alice",
    "onyx": "am_michael",
    "nova": "af_bella",
    "shimmer": "if_sara",
}


def _resolve_voice(voice: str, text: str = "") -> tuple[str, str]:
    """Risolve la voce e la lingua (en/it). Ritorna (voice_id, lang_code)."""
    v = str(voice or "").strip().lower()
    canonical = VOICE_ALIASES.get(v, v or "af_nicole")

    # Riconoscimento lingua: prefisso 'i' per italiano in Kokoro
    if canonical.startswith("i") or v in ("it", "italiano", "italian", "sara", "nicola"):
        return canonical, "it"

    if canonical in ("af_nicole", "nicole"):
        return "af_nicole", "it"

    # Se la voce è OpenAI generica ma il testo è italiano, usa Nicole
    parole_it = ("ciao", "questo", "grazie", "sono", "perché", "buongiorno", "della", "delle", "degli", "nella", "come")
    if any(p in text.lower() for p in parole_it):
        if canonical in ("im_nicola", "echo", "onyx"):
            return "im_nicola", "it"
        return "af_nicole", "it"

    return canonical, "en-us"


def _generate_fallback_wav(text: str, voice: str = "", sample_rate: int = 24000) -> bytes:
    """Genera un file WAV valido di sintesi fallback per test o quando i pesi non sono presenti."""
    resolved_voice, lang = _resolve_voice(voice, text)

    # Se siamo su macOS e il comando 'say' è disponibile, usalo per generare audio reale
    if sys.platform == "darwin":
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as aiff_f:
                aiff_path = aiff_f.name
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as wav_f:
                wav_path = wav_f.name

            # Scelta voce macOS nativa (Alice per femmina IT, Eddy per maschio IT, Samantha per EN)
            if lang == "it":
                macos_voice = "Eddy" if resolved_voice == "im_nicola" else "Alice"
            else:
                macos_voice = "Samantha"

            subprocess.run(["say", "-v", macos_voice, "-o", aiff_path, text[:400]], check=True, timeout=10)
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
        "default_italian_voice": "if_sara",
        "voices": [
            {"id": "if_sara", "name": "Sara (Italiano Femminile)", "gender": "female", "language": "it"},
            {"id": "im_nicola", "name": "Nicola (Italiano Maschile)", "gender": "male", "language": "it"},
            {"id": "af_heart", "name": "Heart (English Female)", "gender": "female", "language": "en"},
            {"id": "af_bella", "name": "Bella (English Female)", "gender": "female", "language": "en"},
            {"id": "af_nicole", "name": "Nicole (English Female)", "gender": "female", "language": "en"},
            {"id": "am_michael", "name": "Michael (English Male)", "gender": "male", "language": "en"},
            {"id": "bf_alice", "name": "Alice (British Female)", "gender": "female", "language": "en-gb"}
        ],
        "openai_compatible": True
    })


@app.route("/v1/audio/voices", methods=["GET"])
def list_voices():
    """Elenco voci disponibili (con supporto nativo italiano e stili miscelati)."""
    return jsonify({
        "voices": voicebox_client.voice_listing() + [
            {"id": "if_sara", "name": "Sara (Standard)", "gender": "female", "language": "it", "description": "Voce italiana naturale di riferimento"},
            {"id": "poetica", "name": "Sara (Stile Poetico)", "gender": "female", "language": "it", "description": "Cadenza lirica, morbida e melodica (Sara + Aoede)"},
            {"id": "documentarista", "name": "Sara (Stile Documentarista)", "gender": "female", "language": "it", "description": "Cadenza autorevole, riflessiva da reportage (Sara + Emma)"},
            {"id": "giornalista", "name": "Sara (Stile Giornalista)", "gender": "female", "language": "it", "description": "Cadenza dinamica, incisiva e brillante (Sara + Bella)"},
            {"id": "teatrale", "name": "Sara (Stile Teatrale)", "gender": "female", "language": "it", "description": "Cadenza espressiva, intensa e drammatica (Sara + Isabella)"},
            {"id": "im_nicola", "name": "Nicola", "gender": "male", "language": "it", "description": "Voce italiana naturale maschile"},
            {"id": "af_heart", "name": "Heart", "gender": "female", "language": "en", "description": "Voce calda e profonda (USA)"},
            {"id": "af_nicole", "name": "Nicole", "gender": "female", "language": "en", "description": "Voce sussurrata e rilassante (USA)"},
            {"id": "bf_emma", "name": "Emma", "gender": "female", "language": "en-gb", "description": "Voce aristocratica ed elegante (UK)"}
        ]
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

    raw_voice = str(data.get("voice", DEFAULT_VOICE)).strip() or DEFAULT_VOICE
    if voicebox_client.is_voicebox_voice(raw_voice):
        # Voce clonata: la sintesi la fa l'app Voicebox sul Mac, non Kokoro.
        try:
            wav = voicebox_client.synthesize(raw_voice, text, data.get("language"))
        except voicebox_client.VoiceboxError as exc:
            return jsonify({"error": str(exc)}), 502
        return Response(wav, mimetype="audio/wav")
    play_on_speaker = bool(data.get("play", False))
    voice, lang = _resolve_voice(raw_voice, text)
    speed = float(data.get("speed", 1.0))
    fmt = str(data.get("response_format", "mp3")).strip().lower()
    if fmt not in ("mp3", "wav", "ogg"):
        fmt = "wav"

    # 1. Prova sintesi ONNX nativa con Kokoro
    if _init_kokoro() and _kokoro_instance is not None:
        try:
            import soundfile as sf  # type: ignore

            # Gestione stili miscelati (Voice Blending) per cadenze specifiche
            target_voice = voice
            v_key = raw_voice.lower()
            if v_key in ("poetica", "sara_poetica", "poesia"):
                sara = _kokoro_instance.get_voice_style("if_sara")
                aoede = _kokoro_instance.get_voice_style("af_aoede")
                target_voice = 0.6 * sara + 0.4 * aoede
                lang = "it"
                if speed == 1.0:
                    speed = 0.92
            elif v_key in ("documentarista", "sara_doc", "documentario"):
                sara = _kokoro_instance.get_voice_style("if_sara")
                emma = _kokoro_instance.get_voice_style("bf_emma")
                target_voice = 0.65 * sara + 0.35 * emma
                lang = "it"
                if speed == 1.0:
                    speed = 0.94
            elif v_key in ("giornalista", "sara_news", "notizie"):
                sara = _kokoro_instance.get_voice_style("if_sara")
                bella = _kokoro_instance.get_voice_style("af_bella")
                target_voice = 0.6 * sara + 0.4 * bella
                lang = "it"
                if speed == 1.0:
                    speed = 1.05
            elif v_key in ("teatrale", "sara_teatrale", "drammatica"):
                sara = _kokoro_instance.get_voice_style("if_sara")
                isabella = _kokoro_instance.get_voice_style("bf_isabella")
                target_voice = 0.55 * sara + 0.45 * isabella
                lang = "it"
                if speed == 1.0:
                    speed = 0.90

            try:
                samples, sample_rate = _kokoro_instance.create(text, voice=target_voice, speed=speed, lang=lang)
            except TypeError:
                samples, sample_rate = _kokoro_instance.create(text, voice=target_voice, speed=speed)

            buf = io.BytesIO()
            sf_format = "WAV" if fmt == "wav" else "OGG"
            sf.write(buf, samples, sample_rate, format=sf_format)
            buf.seek(0)

            if play_on_speaker:
                try:
                    import tempfile, subprocess
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f_play:
                        f_play.write(buf.getvalue())
                        play_p = f_play.name
                    if sys.platform == "darwin":
                        subprocess.Popen(["afplay", play_p])
                except Exception:
                    pass

            return Response(buf.read(), mimetype=f"audio/{fmt}")
        except Exception as exc:
            print(f"[kokoro] Errore sintesi ONNX: {exc}, passo al fallback.")

    # 2. Sintesi Fallback deterministica (WAV ad alta fedeltà con Alice/Eddy su macOS)
    wav_bytes = _generate_fallback_wav(text, voice=raw_voice)
    return Response(wav_bytes, mimetype="audio/wav")


@app.route("/v1/audio/transcriptions", methods=["POST", "OPTIONS"])
def audio_transcriptions():
    """Endpoint compatibile OpenAI Speech-to-Text (/v1/audio/transcriptions).
    
    Supporta la trascrizione del microfono inviata da Open WebUI usando Whisper.
    """
    if request.method == "OPTIONS":
        return "", 204

    if "file" not in request.files:
        return jsonify({"error": "Parametro 'file' mancante", "text": ""}), 400

    audio_file = request.files["file"]
    lang = request.form.get("language", "it")

    import tempfile
    suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in_path = tmp_in.name
        audio_file.save(tmp_in_path)

    # Converti in WAV 16kHz per Whisper se necessario
    wav_path = tmp_in_path + ".wav"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", tmp_in_path, "-ar", "16000", "-ac", "1", wav_path],
                       capture_output=True, check=True, timeout=15)
        target_path = wav_path
    except Exception:
        target_path = tmp_in_path

    try:
        whisper_bin = "/opt/homebrew/bin/whisper"
        if os.path.exists(whisper_bin):
            out_dir = tempfile.gettempdir()
            stem = Path(target_path).stem
            cmd = [
                whisper_bin, target_path,
                "--model", "tiny",
                "--language", lang,
                "--output_format", "json",
                "--output_dir", out_dir
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            json_out = Path(out_dir) / f"{stem}.json"
            if json_out.exists():
                with open(json_out, "r", encoding="utf-8") as f:
                    data = json.load(f)
                try:
                    os.remove(json_out)
                except Exception:
                    pass
                return jsonify({"text": data.get("text", "").strip()})

        return jsonify({"text": ""})
    except Exception as exc:
        return jsonify({"error": str(exc), "text": ""}), 500
    finally:
        for p in (tmp_in_path, wav_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


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
