"""Uso: SW_GAME_DIR=... SW_X4_DIR=... python make_hires_pages.py <uscita> <palette: pal|pal1|pal2|pal3> <file palette es. QDATA/PAL0.DAT> 512 [forza dettaglio]
   Pagine 512x512 a 8 bit: i colori vengono dall'originale (palette del gioco), il dettaglio dall'IA.
   H = originale ingrandito (bicubico) + (IA 512 - IA sfocata alla risoluzione dell'originale); poi palette piu' vicina."""
import os, sys, numpy as np
from pathlib import Path
from PIL import Image
G = Path(os.environ.get("SW_GAME_DIR", "SWARS"))              # copia del gioco originale (data/ e qdata/)
X4 = Path(os.environ.get("SW_X4_DIR", "x4ai"))               # pagine ingrandite dall'IA: TEXnn_<palette>.png, solo locali
out = Path(sys.argv[1]); name = sys.argv[2]; palfile = sys.argv[3]; S = int(sys.argv[4]); K = float(sys.argv[5]) if len(sys.argv) > 5 else 1.0
out.mkdir(parents=True, exist_ok=True)
raw = np.frombuffer((G / palfile).read_bytes()[:768], dtype=np.uint8).reshape(256, 3).astype(np.float32)
pal = (raw * 255 / 63).round() if raw.max() <= 63 else raw
def up(a, size, mode):  # a: HxWx3 float
    ch = [np.asarray(Image.fromarray(np.clip(a[..., c], 0, 255).astype(np.uint8)).resize((size, size), mode), dtype=np.float32) for c in range(3)]
    return np.stack(ch, -1)
for i in range(6):
    orig = np.frombuffer((G / "DATA" / f"TEX{i:02d}.DAT").read_bytes(), dtype=np.uint8).reshape(256, 256)
    big0 = np.kron(orig, np.ones((S // 256, S // 256), dtype=np.uint8))
    src = X4 / f"TEX{i:02d}_{name}.png"
    if i == 5 or not src.exists():
        (out / f"TEX{i:02d}.DAT").write_bytes(big0.tobytes()); continue
    O = pal[orig]                                    # 256x256x3
    O_up = up(O, S, Image.BICUBIC)
    A = np.asarray(Image.open(src).convert("RGB").resize((S, S), Image.BOX), dtype=np.float32)
    A_low = up(np.asarray(Image.fromarray(A.astype(np.uint8)).resize((256, 256), Image.BOX), dtype=np.float32), S, Image.BICUBIC)
    luma = (0.299 * O_up[..., 0] + 0.587 * O_up[..., 1] + 0.114 * O_up[..., 2])
    w = np.clip((235.0 - luma) / 60.0, 0.0, 1.0)[..., None]   # niente dettaglio sulle zone molto chiare (luci)
    H = np.clip(O_up + K * w * (A - A_low), 0, 255).reshape(-1, 3)
    idx = np.empty(len(H), dtype=np.uint8)
    for s in range(0, len(H), 4096):
        d = ((H[s:s+4096, None, :] - pal[None]) ** 2).sum(-1); idx[s:s+4096] = d.argmin(1)
    idx = idx.reshape(S, S); idx[big0 == 0] = 0
    oluma = (0.299 * pal[big0][..., 0] + 0.587 * pal[big0][..., 1] + 0.114 * pal[big0][..., 2])
    keep = oluma >= 215                                       # texel molto luminosi: si tiene l'indice originale
    idx[keep] = big0[keep]
    (out / f"TEX{i:02d}.DAT").write_bytes(idx.tobytes())
    same = (idx == big0).mean()
    print(f"TEX{i:02d}: indici usati {len(np.unique(idx))}, uguali all'originale ingrandito {same:.1%}")
