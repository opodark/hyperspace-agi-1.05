#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Banchi di sprite a doppia risoluzione per Syndicate Wars, nello stesso formato .tab/.dat.

I colori vengono dallo sprite originale (palette del gioco); l'IA aggiunge solo il dettaglio ad alta frequenza;
il profilo e' arrotondato con Scale2x. Gli sprite senza versione IA usano solo Scale2x.
Il risultato e' `<uscita>/mspr-Nh.tab` e `<uscita>/mspr-Nh.dat`: ogni sprite ha larghezza e altezza doppie
rispetto all'originale (indice per indice), e il gioco lo usa al posto dell'originale quando disegna in scala.

Formato (da bflibrary/src/general/gspr_std.c):
  .tab  record da 6 byte: uint32 offset nel .dat, uint8 larghezza, uint8 altezza
  .dat  per ogni riga: N>0 -> N indici di palette; N<0 (come byte con segno) -> salta -N pixel trasparenti; 0 -> fine riga

Uso (solo locale: sono dati EA/Bullfrog derivati dalla copia installata del gioco):
  SW_GAME_DIR=".../SWARS" SW_AI_DIR=".../sprites-ai" python make_hires_sprites.py <uscita> [banco ...] [--check]
  con SW_GAME_DIR che contiene DATA/ e QDATA/, e SW_AI_DIR che contiene MSPR-N/NNNN.png (x4, RGBA).
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

SCALE = 2
BRIGHT_LUMA = 215.0       # texel molto luminosi: si tiene l'indice originale
DETAIL_FADE = (235.0, 60.0)


def load_palette(path: Path) -> np.ndarray:
    raw = np.frombuffer(path.read_bytes()[:768], dtype=np.uint8).reshape(256, 3).astype(np.float32)
    return (raw * 255 / 63).round() if raw.max() <= 63 else raw


def decode_sprite(dat: bytes, offset: int, width: int, height: int) -> Tuple[np.ndarray, np.ndarray]:
    """(indici h x w, maschera h x w) di uno sprite; tollera dati malformati."""
    idx = np.zeros((height, width), dtype=np.uint8)
    mask = np.zeros((height, width), dtype=bool)
    p = offset
    for y in range(height):
        x = 0
        while p < len(dat):
            b = dat[p]
            p += 1
            if b == 0:
                break
            if b > 127:
                x += 256 - b
            else:
                for _ in range(b):
                    if p >= len(dat):
                        break
                    if x < width:
                        idx[y, x] = dat[p]
                        mask[y, x] = True
                    x += 1
                    p += 1
    return idx, mask


def encode_sprite(idx: np.ndarray, mask: np.ndarray) -> bytes:
    """Righe codificate come da formato; i trasparenti finali di riga si omettono."""
    out = bytearray()
    height, width = idx.shape
    for y in range(height):
        x = 0
        while x < width:
            if not mask[y, x]:
                start = x
                while x < width and not mask[y, x]:
                    x += 1
                if x == width:
                    break  # trasparenti fino a fine riga: basta il terminatore
                skip = x - start
                while skip > 0:
                    step = min(skip, 127)
                    out.append(256 - step)
                    skip -= step
            else:
                start = x
                while x < width and mask[y, x]:
                    x += 1
                run = idx[y, start:x]
                for i in range(0, len(run), 127):
                    chunk = run[i:i + 127]
                    out.append(len(chunk))
                    out.extend(int(v) for v in chunk)
        out.append(0)
    return bytes(out)


def _resize(channels: np.ndarray, size: Tuple[int, int], mode: int) -> np.ndarray:
    return np.stack([np.asarray(Image.fromarray(np.clip(channels[..., c], 0, 255).astype(np.uint8)).resize(size, mode),
                                dtype=np.float32) for c in range(channels.shape[-1])], -1)


def _premult_resize(rgb: np.ndarray, alpha: np.ndarray, size: Tuple[int, int], mode: int) -> Tuple[np.ndarray, np.ndarray]:
    """Ridimensiona colore e alfa senza far sanguinare il colore dei pixel trasparenti."""
    weight = alpha[..., None] / 255.0
    premult = rgb * weight
    stack = np.concatenate([premult, alpha[..., None]], -1)
    # float a 8 bit per canale: il colore premoltiplicato sta gia' in 0..255
    resized = np.stack([np.asarray(Image.fromarray(np.clip(stack[..., c], 0, 255).astype(np.uint8)).resize(size, mode),
                                   dtype=np.float32) for c in range(4)], -1)
    a = resized[..., 3]
    color = resized[..., :3] / np.maximum(a[..., None] / 255.0, 1e-3)
    return np.clip(color, 0, 255), a


def nearest_palette(colors: np.ndarray, palette: np.ndarray) -> np.ndarray:
    flat = colors.reshape(-1, 3)
    out = np.empty(len(flat), dtype=np.uint8)
    for start in range(0, len(flat), 4096):
        d = ((flat[start:start + 4096, None, :] - palette[None]) ** 2).sum(-1)
        out[start:start + 4096] = d.argmin(1)
    return out.reshape(colors.shape[:2])


def replicate(idx: np.ndarray, mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    ones = np.ones((SCALE, SCALE), dtype=np.uint8)
    return np.kron(idx, ones), np.kron(mask.astype(np.uint8), ones).astype(bool)


def scale2x_keys(keys: np.ndarray) -> np.ndarray:
    """Scale2x su una matrice di interi: arrotonda le scalette senza inventare valori nuovi."""
    a = np.pad(keys, 1, mode="constant", constant_values=-1)
    p, up, right, left, down = a[1:-1, 1:-1], a[:-2, 1:-1], a[1:-1, 2:], a[1:-1, :-2], a[2:, 1:-1]
    e0 = np.where((left == up) & (left != down) & (up != right), up, p)
    e1 = np.where((up == right) & (up != left) & (right != down), right, p)
    e2 = np.where((down == left) & (down != right) & (left != up), left, p)
    e3 = np.where((right == down) & (right != up) & (down != left), down, p)
    h, w = keys.shape
    out = np.empty((h * 2, w * 2), dtype=keys.dtype)
    out[0::2, 0::2] = e0
    out[0::2, 1::2] = e1
    out[1::2, 0::2] = e2
    out[1::2, 1::2] = e3
    return out


def upscale_sprite(idx: np.ndarray, mask: np.ndarray, ai_rgba: Optional[np.ndarray],
                   palette: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Sprite a doppia risoluzione: colori originali, dettaglio e profilo dall'IA."""
    height, width = idx.shape
    keys = scale2x_keys(np.where(mask, idx.astype(np.int32), -1))
    base_mask = keys >= 0
    base_idx = np.where(base_mask, keys, 0).astype(np.uint8)
    if ai_rgba is None or ai_rgba.shape[0] != height * 4 or ai_rgba.shape[1] != width * 4:
        return base_idx, base_mask
    size = (width * SCALE, height * SCALE)
    original = palette[idx]
    o_up, o_alpha = _premult_resize(original, mask.astype(np.float32) * 255, size, Image.BICUBIC)
    ai_color, ai_alpha = _premult_resize(ai_rgba[..., :3].astype(np.float32), ai_rgba[..., 3].astype(np.float32), size, Image.BOX)
    low_color, _ = _premult_resize(ai_color, ai_alpha, (width, height), Image.BOX)
    low_up, _ = _premult_resize(low_color, np.full((height, width), 255.0, dtype=np.float32), size, Image.BICUBIC)
    luma = 0.299 * o_up[..., 0] + 0.587 * o_up[..., 1] + 0.114 * o_up[..., 2]
    weight = np.clip((DETAIL_FADE[0] - luma) / DETAIL_FADE[1], 0.0, 1.0)[..., None]
    # sui pixel aggiunti dal profilo l'interpolazione non ha colore affidabile: si usa quello di Scale2x, senza dettaglio
    edge = (o_alpha < 128)[..., None]
    start = np.where(edge, palette[base_idx], o_up)
    weight = np.where(edge, 0.0, weight)
    colors = np.clip(start + weight * (ai_color - low_up), 0, 255)
    new_idx = nearest_palette(colors, palette)
    new_mask = base_mask   # l'alfa dell'IA ricalca il profilo originale (352 sprite su 363 identici): non aiuta
    luma_base = 0.299 * palette[base_idx][..., 0] + 0.587 * palette[base_idx][..., 1] + 0.114 * palette[base_idx][..., 2]
    keep = (luma_base >= BRIGHT_LUMA) & base_mask
    new_idx[keep] = base_idx[keep]
    return new_idx, new_mask


def convert_bank(game: Path, ai_dir: Path, name: str, out: Path, palette: np.ndarray, check: bool = False) -> str:
    tab = (game / "DATA" / f"{name}.TAB").read_bytes()
    dat = (game / "DATA" / f"{name}.DAT").read_bytes()
    count = len(tab) // 6
    out_dat = bytearray()
    out_tab = bytearray()
    ai_used = 0
    bad = 0
    for i in range(count):
        offset, width, height = struct.unpack_from("<IBB", tab, i * 6)
        if width == 0 or height == 0 or offset >= len(dat) or width * SCALE > 255 or height * SCALE > 255:
            out_tab += struct.pack("<IBB", 0, 0, 0)
            continue
        idx, mask = decode_sprite(dat, offset, width, height)
        if check and i % 97 == 0:
            again = decode_sprite(encode_sprite(idx, mask), 0, width, height)
            if not (np.array_equal(again[1], mask) and np.array_equal(again[0][mask], idx[mask])):
                bad += 1
        ai_path = ai_dir / name / f"{i:04d}.png"
        ai = np.asarray(Image.open(ai_path).convert("RGBA")) if ai_path.exists() else None
        if ai is not None:
            ai_used += 1
        new_idx, new_mask = upscale_sprite(idx, mask, ai, palette)
        out_tab += struct.pack("<IBB", len(out_dat), new_idx.shape[1], new_idx.shape[0])
        out_dat += encode_sprite(new_idx, new_mask)
    suffix = name.lower().replace("-", "-")
    (out / f"{suffix}h.tab").write_bytes(bytes(out_tab))
    (out / f"{suffix}h.dat").write_bytes(bytes(out_dat))
    return f"{name}: {count} sprite, {ai_used} con IA, dat {len(out_dat)} byte" + (f", ritorno non fedele: {bad}" if check else "")


def main(argv: List[str]) -> int:
    check = "--check" in argv
    args = [a for a in argv[1:] if a != "--check"]
    if not args:
        print(__doc__)
        return 2
    out = Path(args[0])
    banks = args[1:] or [f"MSPR-{n}" for n in range(6)]
    game = Path(os.environ.get("SW_GAME_DIR", "SWARS"))
    ai_dir = Path(os.environ.get("SW_AI_DIR", "sprites-ai"))
    out.mkdir(parents=True, exist_ok=True)
    palette = load_palette(game / "QDATA" / "PAL0.DAT")
    for name in banks:
        print(convert_bank(game, ai_dir, name, out, palette, check), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
