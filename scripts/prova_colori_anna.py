#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Le quattro prove di colore: un vestito, un fondo e una posa diversi in ognuna.

Perché esistono (2026-10-02): la serie notturna è uscita slavata — saturazione media 0,14
e il verde dominante in diciannove immagini su trenta, anche dove la scena chiedeva
viola, teal o cremisi. La causa non era il seed (erano trenta, diversi, con la stessa
palette): era l'adattatore del volto, acceso su **tutti** i passi e sui *value*, che
portava dentro anche il **fondo verde** del riferimento canonico. Il rimedio è nel grafo
(`end_at: 0.6`, vedi `shared/image_jobs.py`) e nel documento (`riferimento_forza: 0.55`),
e la serie di controllo lo misura a parità di scena e di seed.

Queste quattro prove misurano un'altra cosa, e la misurano meglio: **dove finisce il
colore**. Ognuna chiede due colori in un colpo solo — uno addosso e uno alle spalle —
presi da due lati opposti della ruota, e **la luce resta neutra** (bianca, da softbox o
da finestra): nella **scena** le uniche sorgenti di colore sono l'abito e il fondo, e
l'immagine risponde a una domanda sola. Lo stile della persona però ne porta una sua —
`green and violet aurora accents`, che sta in tutte e quattro — e non sposta il confronto
*fra* le prove, ma è una terza sorgente di verde: va tenuta a mente leggendo la 32 (viola)
e la 33 (teal), dove una tinta debole può essere sua e non della scena.

| Prova | Vestito | Fondo | Posa |
|---|---|---|---|
| 31 | cremisi (caldo) | indaco (freddo) | `standing` |
| 32 | viola (freddo) | ocra (caldo) | `seated` |
| 33 | teal (freddo) | terracotta (caldo) | `walking` |
| 34 | magenta | **grigio** (neutro) | `lying` |

Le si guarda così: se escono pastello e verdi, il riferimento decide ancora; se si
vedono **due** tinte, decide la scena. La 34 è il controllo dentro le prove — non ha
nessun fondo colorato che aiuti, quindi un magenta che si vede *anche sul grigio* vuol
dire che il colore è tornato comunque.

Il motore è quello della serie (`scripts/serie_anna.py`): coda che si aspetta invece di
perdere la scena, vetrina dal documento, posa al ControlNet dove c'è, pagina dell'indice
alla fine. Qui si sostituisce **solo** l'elenco delle scene: ricopiare `accoda_aspettando`
e la scrittura dell'indice in un secondo script vorrebbe dire due copie dello stesso
protocollo che, col tempo, divergono.

Uso (tutte le manopole sono quelle della serie):
    python scripts/prova_colori_anna.py --prova          # stampa le quattro prove, non accoda
    python scripts/prova_colori_anna.py --indice ~/ComfyUI-Shared/output/prove-colori.html \
        --output ~/ComfyUI-Shared/output
    python scripts/prova_colori_anna.py --solo 31,34     # due prove sole
    python scripts/prova_colori_anna.py --riferimento-forza 0   # il separatore: senza volto
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Il motore è della serie, non una copia: `main`, `accoda_aspettando`, la vetrina dal
# documento e l'indice restano quelli provati dalla serie notturna.
import serie_anna  # noqa: E402

# Le quattro prove: (nome, scena, posa). I numeri continuano quelli della serie (31–34)
# così `--solo 31` pesca una prova sola con la stessa regola di `--solo 21`.
#
# L'ordine delle parole è quello della serie e non è decorativo: nella finestra CLIP
# della vetrina (lo stile è lungo) l'abito entra **per primo** e il fondo dopo — un fondo
# scritto davanti all'abito è un fondo che vince.
PROVE: Tuple[Tuple[str, str, str], ...] = (
    ("31-prova-rosso-indaco",
     "full body, long crimson wool coat, deep indigo wall behind, "
     "neutral softbox light", "standing"),
    ("32-prova-viola-ocra",
     "seated on a wooden stool, violet silk blouse, ochre plaster wall behind, "
     "neutral white window light", "seated"),
    ("33-prova-teal-terracotta",
     "full body, teal velvet blazer and trousers, terracotta brick wall behind, "
     "neutral daylight", "walking"),
    ("34-prova-magenta-grigio",
     "full body, lying on a bare grey floor, magenta satin dress, "
     "neutral softbox light", "lying"),
)


def main(argv=None) -> int:
    """Le quattro prove al posto delle trenta scene, con lo stesso motore.

    `SCENE` si scambia e si rimette a posto: un modulo che lascia il globale cambiato
    dietro di sé farebbe mentire chi lo importa dopo (i test della serie, per esempio).
    """
    originale = serie_anna.SCENE
    serie_anna.SCENE = PROVE
    try:
        return serie_anna.main(argv)
    finally:
        serie_anna.SCENE = originale


if __name__ == "__main__":
    raise SystemExit(main())
