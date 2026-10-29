# SPDX-License-Identifier: Apache-2.0
"""Client minimo per l'API locale di Voicebox (voci clonate: Qwen3-TTS, Chatterbox, ...).

Voicebox gira sul Mac come app (127.0.0.1:17493). Qui si parla solo con quella
porta: il testo da sintetizzare non esce dal computer.

    voicebox:<profilo>[@<motore>]     es. "voicebox:Albi ita@chatterbox", "voicebox:Albi"

Il profilo si cerca per nome (senza maiuscole) o per id; il motore, se manca, è
quello predefinito del profilo, altrimenti `qwen`. Solo libreria standard.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VOICEBOX_URL = os.getenv("VOICEBOX_URL", "http://127.0.0.1:17493").rstrip("/")
# Cache: una voce + un testo = un audio. Serve perché i client (MoneyPrinterTurbo) chiudono la
# richiesta dopo 120 s e Voicebox ne impiega molti di più, e perché permette di registrare un
# audio fatto a mano nell'app. Il motore non fa parte della chiave: vale l'ultimo audio salvato.
CACHE_DIR = Path(os.getenv("VOICEBOX_CACHE_DIR", Path(__file__).resolve().parents[1] / "data" / "voicebox-cache"))
PREFIX = "voicebox:"
ENGINES = ("qwen", "qwen_custom_voice", "luxtts", "chatterbox", "chatterbox_turbo", "tada", "kokoro")
DEFAULT_ENGINE = "qwen"
LANGS = {"zh", "en", "ja", "ko", "de", "fr", "ru", "pt", "es", "it", "he", "ar", "da", "el",
         "fi", "hi", "ms", "nl", "no", "pl", "sv", "sw", "tr"}


class VoiceboxError(RuntimeError):
    pass


def _call(method: str, path: str, body: dict | None = None, timeout: float = 30,
          base: str | None = None) -> bytes:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request((base or VOICEBOX_URL) + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise VoiceboxError(f"Voicebox {e.code} su {path}: {e.read().decode('utf-8', 'replace')[:200]}") from None
    except (urllib.error.URLError, OSError) as e:
        raise VoiceboxError(f"Voicebox non raggiungibile su {base or VOICEBOX_URL}: apri l'app ({e})") from None


def is_voicebox_voice(voice: str) -> bool:
    return str(voice or "").strip().lower().startswith(PREFIX)


def parse_voice(voice: str) -> tuple[str, str | None]:
    """'voicebox:Albi ita@chatterbox' -> ('Albi ita', 'chatterbox')."""
    rest = str(voice).strip()[len(PREFIX):].strip()
    name, sep, engine = rest.rpartition("@")
    if sep and engine.strip().lower() in ENGINES:
        return name.strip(), engine.strip().lower()
    return rest, None


def profiles(base: str | None = None) -> list[dict]:
    data = json.loads(_call("GET", "/profiles", base=base) or b"[]")
    return data if isinstance(data, list) else data.get("profiles", [])


def find_profile(name: str, base: str | None = None) -> dict:
    wanted = name.strip().lower()
    items = profiles(base)
    for p in items:
        if wanted in (str(p.get("id", "")).lower(), str(p.get("name", "")).strip().lower()):
            return p
    names = ", ".join(sorted(str(p.get("name")) for p in items)) or "nessuno"
    raise VoiceboxError(f"profilo Voicebox «{name}» non trovato (disponibili: {names})")


def _cache_file(profile_id: str, text: str) -> Path:
    norm = re.sub(r"[\W_]+", " ", text.casefold()).strip()
    return CACHE_DIR / (hashlib.sha256(f"{profile_id}\n{norm}".encode("utf-8")).hexdigest()[:32] + ".wav")


def cache_put(voice: str, text: str, wav: bytes, base: str | None = None) -> Path:
    """Registra un audio già fatto per questa voce e questo testo."""
    name, _ = parse_voice(voice) if is_voicebox_voice(voice) else (voice, None)
    f = _cache_file(find_profile(name, base)["id"], text)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(wav)
    return f


def synthesize(voice: str, text: str, language: str | None = None, timeout: float = 300,
               base: str | None = None, use_cache: bool = True) -> bytes:
    """Genera il parlato con la voce clonata e restituisce i byte WAV."""
    name, engine = parse_voice(voice) if is_voicebox_voice(voice) else (voice, None)
    profile = find_profile(name, base)
    cached = _cache_file(profile["id"], text)
    if use_cache and cached.exists():
        return cached.read_bytes()
    engine = engine or profile.get("default_engine") or DEFAULT_ENGINE
    lang = language or profile.get("language") or "en"
    if lang not in LANGS:
        lang = "en"
    job = json.loads(_call("POST", "/generate", {
        "profile_id": profile["id"], "text": text, "language": lang, "engine": engine,
    }, timeout=30, base=base))
    gen_id = job["id"]
    deadline = time.monotonic() + timeout
    while True:
        item = json.loads(_call("GET", f"/history/{urllib.parse.quote(gen_id)}", base=base))
        status = item.get("status")
        if status == "completed":
            wav = _call("GET", f"/history/{urllib.parse.quote(gen_id)}/export-audio",
                        timeout=60, base=base)
            if use_cache:
                cached.parent.mkdir(parents=True, exist_ok=True)
                cached.write_bytes(wav)
            return wav
        if status in ("failed", "error", "cancelled"):
            raise VoiceboxError(f"generazione {status}: {item.get('error') or 'senza dettagli'}")
        if time.monotonic() > deadline:
            try:
                _call("POST", f"/generate/{urllib.parse.quote(gen_id)}/cancel", base=base)
            except VoiceboxError:
                pass
            raise VoiceboxError(f"tempo scaduto dopo {timeout:.0f}s (motore {engine})")
        time.sleep(0.5)


def voice_listing(base: str | None = None) -> list[dict]:
    """Voci in formato /v1/audio/voices; vuoto se Voicebox non è aperto."""
    try:
        items = profiles(base)
    except VoiceboxError:
        return []
    return [{"id": f"{PREFIX}{p.get('name')}", "name": f"{p.get('name')} (voce clonata, Voicebox)",
             "language": p.get("language"), "engine": p.get("default_engine") or DEFAULT_ENGINE,
             "description": "Motori: " + ", ".join(ENGINES)} for p in items]
