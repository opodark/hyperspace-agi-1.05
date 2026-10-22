#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generazione batch di 20 scene 9:16, audio Nicole e montaggio progetto Reel Editor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SHARE_DIR = Path(os.getenv("TIKTOK_EDITOR_SHARE_DIR", "/Users/opo/hyperspace_share"))
PROJECT_NAME = "poesia-cibernetica-nicole"
PROJECT_DIR = SHARE_DIR / "reel-projects" / PROJECT_NAME
MEDIA_DIR = PROJECT_DIR / "media"
COMFY_OUT = Path("/Users/opo/ComfyUI-Shared/output/HyperSpace")

# 20 Prompts per le 20 scene visive della poesia di Brautigan (verticale 9:16, 576x1024)
SCENES = [
    ("scene_01.jpg", "A dreamy cybernetic meadow at dawn, soft morning mist, wildflowers interwoven with glowing micro-circuits, 9:16 vertical, cinematic photo, 8k"),
    ("scene_02.jpg", "A gentle doe resting peacefully beside a sleek vintage-futuristic computer monitor in tall grass, 9:16 vertical, soft sunlight"),
    ("scene_03.jpg", "Mechanical flowers unfolding with spinning crystal petals and fiber-optic stems, morning dew, 9:16 vertical, macro photography"),
    ("scene_04.jpg", "Wild deer and white wolves grazing calmly together beside solar glass terminals, idyllic utopian cybernetics, 9:16 vertical"),
    ("scene_05.jpg", "Crystal clear mountain river flowing over polished stones and submerged glowing circuits, 9:16 vertical, pure water"),
    ("scene_06.jpg", "Water droplets leaping from a pristine stream towards an azure sky, sparkling reflections of blue light, 9:16 vertical"),
    ("scene_07.jpg", "Deep ancient pine forest with towering conifers intertwined with glowing amber conduits and brass electronics, 9:16 vertical"),
    ("scene_08.jpg", "Warm sunlight filtering through towering pine needles, illuminating organic electronic panels on mossy bark, 9:16 vertical"),
    ("scene_09.jpg", "A majestic stag with crystalline glowing antlers walking past a retro mainframe overgrown with ivy, 9:16 vertical"),
    ("scene_10.jpg", "Mechanical flower blossoms with spinning iridescent petals beside a forest pool, water lilies, tranquil wilderness, 9:16 vertical"),
    ("scene_11.jpg", "A curious red fox looking up at floating ambient data-orbs drifting among ferns, warm twilight, 9:16 vertical"),
    ("scene_12.jpg", "Vast panoramic cybernetic landscape, rolling green hills and wind sculptures under clear sunny skies, 9:16 vertical"),
    ("scene_13.jpg", "A harmonious cybernetic ecology, post-scarcity peaceful nature, clean air and distant mountains, 9:16 vertical"),
    ("scene_14.jpg", "Humans and wildlife resting together in a sun-drenched floral meadow, liberation from toil, peace, 9:16 vertical"),
    ("scene_15.jpg", "A human hand gently caressing a wild doe in warm golden afternoon light, connection with nature, 9:16 vertical"),
    ("scene_16.jpg", "Ancient moss-covered computing monolith standing quietly like a sacred menhir in an old forest clearing, 9:16 vertical"),
    ("scene_17.jpg", "Birds perched on solar-tree branches with glowing fruit-like crystal nodes, soft sky, 9:16 vertical"),
    ("scene_18.jpg", "A benevolent giant guardian machine covered in flowering vines watching over forest animals, 9:16 vertical, gentle eyes"),
    ("scene_19.jpg", "A loving cybernetic guardian machine radiating warm amber grace over a slumbering valley under twilight stars, 9:16 vertical"),
    ("scene_20.jpg", "Epic sunset vista over the cybernetic utopia, earth and machines united in perfect loving harmony, cinematic masterpiece, 9:16 vertical"),
]

# Sottotitoli SRT allineati con i tempi precisi di Nicole (62.25 secondi)
SRT_CONTENT = """1
00:00:00,000 --> 00:00:05,000
Mi piace pensare
(e prima sarà, meglio sarà!)

2
00:00:05,000 --> 00:00:13,480
a un prato cibernetico
dove mammiferi e computer vivono insieme

3
00:00:13,480 --> 00:00:17,680
in una reciproca armonia programmata,
come acqua pura che sfiora un cielo limpido.

4
00:00:17,680 --> 00:00:22,760
Mi piace pensare
(proprio adesso, per favore!)

5
00:00:22,760 --> 00:00:27,880
a una foresta cibernetica
piena di pini ed elettronica,

6
00:00:27,880 --> 00:00:37,480
dove i cervi passeggiano serenamente
accanto ai computer come se fossero fiori dai petali rotanti.

7
00:00:37,480 --> 00:00:47,880
Mi piace pensare (deve essere così!)
a un'ecologia cibernetica

8
00:00:47,880 --> 00:00:57,880
dove siamo liberi dalle nostre fatiche
e ricongiunti alla natura, ritornati ai nostri fratelli e sorelle mammiferi,

9
00:00:57,880 --> 01:02:25,000
e tutti vegliati
da macchine di amorevole grazia.
"""


def update_manifest():
    """Aggiorna il manifest.json con i file multimediali effettivamente presenti."""
    existing_media = sorted([f.name for f in MEDIA_DIR.glob("scene_*.jpg") if f.is_file()])
    manifest = {
        "creator": "Altro progetto",
        "title": "Poesia Cibernetica - Voce di Nicole",
        "brief": "Reel della poesia di Richard Brautigan recitata dalla voce di Nicole (Kokoro 82M), 20 scene a ritmo contemplativo su utopia uomo-macchina-natura in 9:16 con sottotitoli sincronizzati.",
        "audio_file": "audio.wav",
        "subtitles_file": "subtitles.srt",
        "filenames": existing_media if existing_media else [s[0] for s in SCENES]
    }
    manifest_file = PROJECT_DIR / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[reel] Manifest TikTok Editor aggiornato: {len(existing_media)} media pronti.")


def setup_project():
    """Inizializza la cartella del progetto, copia l'audio e scrive i sottotitoli."""
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copia Audio Nicole
    src_audio = Path("/tmp/poesia_nicole.wav")
    target_audio = PROJECT_DIR / "audio.wav"
    if src_audio.exists():
        shutil.copy2(src_audio, target_audio)
        print(f"[reel] Audio Nicole copiato: {target_audio}")
    else:
        print("[reel] AVVISO: /tmp/poesia_nicole.wav non trovato!", file=sys.stderr)

    # 2. Scrive Sottotitoli SRT e VTT
    srt_file = PROJECT_DIR / "subtitles.srt"
    srt_file.write_text(SRT_CONTENT.strip(), encoding="utf-8")
    print(f"[reel] Sottotitoli SRT scritti: {srt_file}")

    # 3. Scrive manifest.json iniziale per il TikTok Editor
    update_manifest()


def queue_image_job(prompt: str, seed: int, steps: int = 10, width: int = 576, height: int = 1024) -> str | None:
    """Invia un job di generazione immagine al Control Plane per ComfyUI."""
    url = "http://127.0.0.1:8085/web/image/generate"
    payload = json.dumps({
        "prompt": prompt,
        "family": "sdxl-turbo",
        "width": width,
        "height": height,
        "steps": steps,
        "seed": seed,
        "requester": "poem-reel-generator"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("job_id")
    except Exception as e:
        print(f"[reel] Errore accodamento job: {e}", file=sys.stderr)
        return None


def wait_and_collect_images(jobs: list[tuple[str, str]]):
    """Monitora i job in coda e copia le immagini risultanti nella cartella media del progetto."""
    print(f"\n[reel] Monitoraggio di {len(jobs)} generazioni ComfyUI...")
    pending = list(jobs)

    while pending:
        next_pending = []
        for job_id, target_name in pending:
            status_url = f"http://127.0.0.1:8085/web/image/status?id={job_id}"
            try:
                with urllib.request.urlopen(status_url, timeout=5) as resp:
                    st = json.loads(resp.read().decode())
                if st.get("ok") and st.get("status") == "done":
                    target_dest = MEDIA_DIR / target_name
                    rel_file = st.get("file")
                    src_file = None
                    if rel_file:
                        src_candidate = Path("/Users/opo/ComfyUI-Shared/output") / rel_file
                        if src_candidate.exists():
                            src_file = src_candidate
                    if not src_file:
                        files = sorted(COMFY_OUT.glob("*.jpg"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if files:
                            src_file = files[0]
                    if src_file and src_file.exists():
                        shutil.copy2(src_file, target_dest)
                        print(f"[reel] ✓ Completata {target_name} ({src_file.name}) -> {target_dest}")
                        update_manifest()
                elif st.get("ok") and st.get("status") in ("queued", "running", "pending"):
                    next_pending.append((job_id, target_name))
                else:
                    print(f"[reel] Stato job terminato o anomalo per {job_id}: {st}", file=sys.stderr)
            except Exception as e:
                print(f"[reel] Errore verifica stato {job_id}: {e}", file=sys.stderr)
                next_pending.append((job_id, target_name))

        pending = next_pending
        if pending:
            time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description="Assembla Reel Poesia Cibernetica per TikTok Editor")
    parser.add_argument("--setup-only", action="store_true", help="Prepara solo audio, sottotitoli e manifest")
    parser.add_argument("--all", action="store_true", help="Accoda tutte le 20 scene su ComfyUI")
    parser.add_argument("--queue", type=int, default=5, help="Numero di scene da accodare subito su ComfyUI (default 5)")
    parser.add_argument("--steps", type=int, default=15, help="Passi di campionamento (default 15)")
    parser.add_argument("--watch", action="store_true", help="Attende e raccoglie le immagini man mano che vengono generate")
    args = parser.parse_args()

    print("=== Preparazione Progetto Reel: Poesia Cibernetica con Nicole ===")
    setup_project()

    if args.setup_only:
        print("[reel] Setup completato. Progetto disponibile in TikTok Editor.")
        return 0

    count = len(SCENES) if args.all else min(len(SCENES), max(1, args.queue))
    print(f"\n[reel] Invio di {count} job di generazione immagine a ComfyUI...")
    queued = []
    for i in range(count):
        filename, prompt = SCENES[i]
        target_path = MEDIA_DIR / filename
        if target_path.exists():
            print(f"[reel] Scena già presente: {filename}")
            continue

        jid = queue_image_job(prompt, seed=100 + i, steps=args.steps)
        if jid:
            print(f"[reel] Accodato {filename} (Job ID: {jid})")
            queued.append((jid, filename))
        time.sleep(0.5)

    print(f"\n[reel] {len(queued)} job inviati a ComfyUI.")
    print(f"[reel] Per monitorare in tempo reale: http://127.0.0.1:8188")
    print(f"[reel] Per montare il video: apri http://127.0.0.1:7860 -> 'Progetti preparati in WebUI' -> '{PROJECT_NAME}'")

    if args.watch and queued:
        wait_and_collect_images(queued)

    return 0


if __name__ == "__main__":
    sys.exit(main())
