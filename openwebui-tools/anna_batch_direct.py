# SPDX-License-Identifier: Apache-2.0
"""
title: Anna Batch diretto
description: Accoda fino a 50 scene numerate senza attendere un modello linguistico.
version: 0.2.0
"""

# Managed by HyperSpace webui-tools-register.

import asyncio
import json
import os
import re
import urllib.error
import urllib.request


LINE = re.compile(r"^\s*(?:[-*]\s*)?(\d{1,2})[.)]\s+(.+?)\s*$")
POSE = re.compile(r"^\[(pose|preset)=([^\]]+)\]\s*(?:\[strength=([^\]]+)\]\s*)?(.+)$")
URL = "http://control-plane:8085/webui-tools/anna/batch"


def parse_scenes(message):
    scenes = []
    for line in message.splitlines():
        match = LINE.match(line)
        if match:
            scene = match.group(2).strip()
            if len(scene) > 1000:
                raise ValueError(f"Scena {len(scenes) + 1}: oltre 1000 caratteri")
            pose = POSE.match(scene)
            if pose:
                kind, name, strength, description = pose.groups()
                if not name.strip() or not description.strip():
                    raise ValueError(f"Scena {len(scenes) + 1}: posa o descrizione vuota")
                item = {"scene": description.strip(),
                        "pose_image" if kind == "pose" else "pose_preset": name.strip()}
                if strength is not None:
                    try:
                        item["pose_strength"] = float(strength)
                    except ValueError as error:
                        raise ValueError(f"Scena {len(scenes) + 1}: strength non numerico") from error
                scenes.append(item)
            else:
                if scene.startswith(("[pose=", "[preset=")):
                    raise ValueError(f"Scena {len(scenes) + 1}: sintassi della posa non valida")
                scenes.append(scene)
    if not scenes:
        raise ValueError("Non trovo scene numerate: usa '1. descrizione', '2. descrizione', ecc.")
    if len(scenes) > 50:
        raise ValueError(f"Trovate {len(scenes)} scene: il massimo per invio è 50. Nulla è stato accodato.")
    return scenes


def submit(scenes):
    token = os.getenv("WEBUI_TOOLS_TOKEN", "")
    if len(token) < 32:
        raise ValueError("WEBUI_TOOLS_TOKEN non configurato; nulla è stato accodato")
    data = json.dumps({"scene": scenes}).encode("utf-8")
    request = urllib.request.Request(URL, data=data, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc)
            return detail if isinstance(detail, dict) else {"error": str(detail)}
        except (ValueError, OSError):
            raise ValueError(f"Endpoint batch: HTTP {exc.code}") from exc


def format_result(result):
    if result.get("error"):
        return "Anna Batch: " + str(result["error"])
    accepted = result.get("accepted") or []
    rejected = result.get("rejected") or []
    lines = [f"Anna Batch: {len(accepted)} accodate, {len(rejected)} rifiutate."]
    if accepted:
        labels = []
        for item in accepted:
            label = f"{item['index']}={item['job_id']}"
            mode = item.get("pose_mode")
            if mode:
                name = item.get("pose_image") or item.get("pose_preset") or ""
                label += f" ({mode}{':' + name if name else ''})"
            labels.append(label)
        lines.append("ID accettati: " + ", ".join(labels))
        without_pose = sum(not item.get("pose_mode") for item in accepted)
        if without_pose:
            lines.append(
                f"{without_pose} scene senza vincolo di posa: per gesti precisi di mani e dita "
                "usa [pose=pose/nome.jpg] davanti alla descrizione."
            )
    if rejected:
        lines.append("Da correggere o ritentare (solo queste): " + "; ".join(
            f"{item.get('index', '?')}: {item.get('error', 'rifiutata')}" for item in rejected))
    lines.append("Stato: http://127.0.0.1:8085/activity")
    return "\n".join(lines)


class Pipe:
    async def pipe(self, body: dict) -> str:
        messages = body.get("messages") or []
        user_messages = [item.get("content") for item in messages
                         if item.get("role") == "user" and isinstance(item.get("content"), str)]
        if not user_messages:
            return "Anna Batch: incolla un elenco numerato da 1 a 50 scene."
        try:
            scenes = parse_scenes(user_messages[-1])
            result = await asyncio.to_thread(submit, scenes)
            return format_result(result)
        except (ValueError, OSError) as exc:
            return f"Anna Batch: {exc}. Se l'invio è scaduto, controlla il monitor prima di ritentare."
