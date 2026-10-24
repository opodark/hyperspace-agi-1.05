# SPDX-License-Identifier: Apache-2.0
"""Turn recent social conversations into privacy-preserving dream prompts."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


_URL = re.compile(r"https?://\S+", re.IGNORECASE)
_MENTION = re.compile(r"(?<!\w)@[A-Za-z0-9_.]{1,64}")
_SPACE = re.compile(r"\s+")
_TRIVIAL = re.compile(
    r"^(?:ciao|hey|hi|hello|ei|ehi|buongiorno|buonasera|come stai|ok|grazie)[!?. ]*$",
    re.IGNORECASE,
)


def load_trend_inspirations(path: str | Path | None = None, *, limit: int = 3, max_chars: int = 240) -> list[str]:
    """Load fresh privacy-preserving trend snippets harvested via Agent-Reach.

    Returns up to ``limit`` non-empty inspiration strings.
    """
    candidate_paths = [
        Path(path) if path else None,
        Path("data/control-plane/trend_inspirations.json"),
        Path("/app/data/trend_inspirations.json"),
    ]
    file_path = None
    for p in candidate_paths:
        if p and p.is_file():
            file_path = p
            break
    if not file_path:
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw_items = data.get("inspirations") or []
        cleaned: list[str] = []
        for item in raw_items:
            text = _SPACE.sub(" ", str(item or "")).strip()
            text = _URL.sub("[link]", text)[:max_chars].rstrip()
            if text and len(text) >= 12:
                cleaned.append(text)
            if len(cleaned) >= max(0, int(limit)):
                break
        return cleaned
    except Exception:
        return []


def combined_dream_material(turns=(), *, trend_path: str | Path | None = None,
                            limit: int = 5, max_trends: int = 2) -> list[str]:
    """Combine inbound conversational echoes with external harvested cultural trends.

    Ensures a balanced, privacy-preserving mix for the nocturnal dream prompt.
    """
    social = social_dream_inspirations(turns, limit=limit)
    trends = load_trend_inspirations(trend_path, limit=max_trends)

    combined = []
    # Interleave social whispers and cultural trends
    max_len = max(len(social), len(trends))
    for i in range(max_len):
        if i < len(social) and len(combined) < limit:
            combined.append(social[i])
        if i < len(trends) and len(combined) < limit:
            combined.append(f"[tendenza del mondo] {trends[i]}")

    return combined[:limit]



def social_dream_inspirations(turns, *, limit: int = 5, max_chars: int = 240) -> list[str]:
    """Return recent distinct social messages without authors, handles or URLs.

    ``turns`` is expected newest-first, like ``ConversationLog.list()``. Chat IDs
    are used only to diversify the sample and never appear in the returned text.
    """
    result: list[str] = []
    seen_text: set[str] = set()
    seen_chats: set[str] = set()
    allowed = {"instagram", "telegram", "web", "webui"}
    for turn in turns or ():
        channel = str(turn.get("channel") or "").lower()
        surface = str(turn.get("surface") or "").lower()
        if channel not in allowed and surface not in allowed:
            continue
        chat = str(turn.get("chat") or "")
        if chat and chat in seen_chats:
            continue
        for message in reversed(turn.get("messages") or []):
            text = _SPACE.sub(" ", str(message.get("text") or "")).strip()
            if len(text) < 8 or _TRIVIAL.match(text):
                continue
            text = _URL.sub("[link]", _MENTION.sub("una persona", text))[:max_chars].rstrip()
            key = text.casefold()
            if key in seen_text:
                continue
            result.append(text)
            seen_text.add(key)
            if chat:
                seen_chats.add(chat)
            break
        if len(result) >= max(0, int(limit)):
            break
    return result
