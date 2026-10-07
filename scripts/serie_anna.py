#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""La serie notturna: cinquanta varianti di Anna in coda mentre la stanza dorme.

Perché esiste (2026-10-02): `scripts/serie.py` fa dodici varianti e **aspetta** ogni
immagine (minuti l'una, `--attesa`) perché serve a *giudicare* una serie guardandola
finire. Una serie **notturna** è un'altra cosa: la si accoda e si va a dormire, e la
mattina dopo c'è di che scegliere. Da lì due differenze che nessuna delle due sta bene
dentro `serie.py`:

  - **la coda è più corta della serie.** `IMAGE_QUEUE_MAX` (nel `.env`) è il tetto dei
    job in attesa o in corso, e il commento che lo dichiara in `control-plane/main.py`
    lo dice già: *«una serie notturna può però essere più lunga della coda
    interattiva»*. Trenta scene con un tetto di ventiquattro si accodano **aspettando**:
    quando la coda risponde `coda piena` (HTTP 429, che è `RuntimeError` dentro
    `ImmagineQueue.accoda`) lo script dorme e ritenta, e i job che avanzano entrano
    mano a mano che il ponte ne conclude uno. Non si perde nessuna scena e non si alza
    il tetto per una notte sola — che è la cosa che romperebbe la coda interattiva.
  - **l'esito non si aspetta per forza.** Di default lo script *accoda e basta*: il
    lavoro resta nella coda del control-plane (che sopravvive al riavvio), e il ponte
    del Mac lo macina per conto suo. Con `--indice` invece aspetta la fine di tutte e
    scrive la pagina con le immagini, che è quello che serve la mattina dopo.

Le scene sono cinquanta — colori, abiti, ambienti e pose — e **tutte** passano da
`shared.showcase.verifica_vetrina` prima di essere accodate: una scena che chiede una
nudità o un soggetto minorenne viene rifiutata, la ragione resta nel log, e le altre
partono lo stesso. Non è una formalità: è la differenza fra una serie che si ferma e
una che consegna ventinove varianti.

Quattro scene (21–24) sono **glamour in lingerie**, col vocabolario che il canale ha
già sancito nella banda VIP (`glamorous lingerie editorial`, `fully clothed intimate
apparel`, `elegant sensual pose`): niente nudità — quella resta al creatore e alle
muse — ma nemmeno il maglione largo. Il negativo resta quello dichiarato (contiene
`nudità`), quindi `--creatore` **non** va usato qui: toglierebbe dal negativo proprio
la parola che tiene i vestiti addosso.

Le pose sono il terzo pezzo di ogni scena (`standing`, `seated`, `lying`, `walking`,
`dancing`, `arms_open`): dove la famiglia non ha il ControlNet openpose la posa resta
al testo (`serie.posa_da_mandare`) invece di far fallire il job. Il volto non si tocca:
resta quello della vetrina (`riferimento`), perché una serie di trenta serve a scegliere
un abito, non una persona.

Uso:
    python scripts/serie_anna.py --prova                  # stampa le trenta scene, non accoda
    python scripts/serie_anna.py                          # accoda e basta (per la notte)
    python scripts/serie_anna.py --indice /tmp/anna.html  # accoda, aspetta, scrive la pagina
    python scripts/serie_anna.py --solo 21,22,23,24       # solo le scene glamour
    python scripts/serie_anna.py --pausa 90 --pazienza 14400
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Gli helper del canale sono quelli di `ritratto.py` (token dal .env, chiamata JSON) e
# le manopole della serie quelle di `serie.py` (`posa_da_mandare`, `conta_token`,
# `misura_file`, `scrivi_indice`): si prendono, non si ricopiano — due implementazioni
# dello stesso protocollo divergono, e a divergere sarebbe quella che si usa di rado.
import ritratto as cli  # noqa: E402
import serie  # noqa: E402
from shared.image_jobs import (FAMIGLIA_DEFAULT, RIFERIMENTO_FORZA_DEFAULT,  # noqa: E402
                               riferimento_supportato)
from shared.showcase import (negativo_ritratto, prompt_ritratto, verifica_vetrina,  # noqa: E402
                             vetrina_con_quadro_erotismo, vetrina_dal_documento)

# Le manopole della serie, prese da `serie.py`: sono pure (non toccano stato) e
# condividerle non lega i due script — evita soltanto che la lettura di un JPEG, il
# conteggio dei token e la pagina dell'indice esistano in due copie che divergono.
conta_token = serie.conta_token
misura_file = serie.misura_file
scrivi_indice = serie.scrivi_indice
posa_da_mandare = serie.posa_da_mandare

# Le trenta varianti: (nome, scena, posa). L'ordine è per costo del dettaglio — prima i
# volti (dove si giudica un'identità), poi i piani medi (dove si giudica un abito), poi
# le figure intere (dove si giudica una posa) — e dentro ogni blocco cambia una cosa
# sola: un abito, un colore, una luce. Così una scena che non piace non porta con sé la
# posa che piaceva.
#
# A differenza di `serie.py` le scene NON ripetono i capelli: la vetrina di Anna li ha
# già nello stile (`black hair with purple tips`), che sta davanti a tutto nel prompt, e
# ripeterli consumerebbe finestra CLIP — che è il vero tetto di una scena. Qui la scena
# dice inquadratura, abito, ambiente e luce, e basta.
SCENE: Tuple[Tuple[str, str, str], ...] = (
    # ── Volti: dove si giudica l'identità (la posa è del testo, non serve imporla) ──
    ("01-volto-aurora", "close-up face, front view, calm gaze at viewer, "
                        "green and violet aurora light, dark background", ""),
    ("02-volto-sorriso", "close-up portrait, soft smile, head tilted, "
                         "warm golden rim light, dark backdrop", ""),
    ("03-volto-libro", "close-up face, looking down at an open book, "
                       "amber reading lamp, dark library shelves", ""),
    ("04-volto-pioggia", "close-up face, damp hair, cool teal light, "
                         "rain-streaked window behind", ""),
    ("05-volto-candela", "close-up portrait, three-quarter view, "
                         "warm candlelight, deep shadow", ""),

    # ── Piani medi: dove si giudica l'abito. Un capo e una luce per scena, e la ──
    # ── palette gira intorno al sole (nero/viola) invece di ripeterlo.          ──
    ("06-busto-maglia", "upper body, black turtleneck sweater, arms crossed, "
                        "crimson studio light, dark wall", ""),
    ("07-busto-camicia", "upper body, white silk shirt, open collar, "
                         "soft window light, pale grey wall", ""),
    ("08-busto-bomber", "upper body, teal bomber jacket, hands in pockets, "
                        "neon signs at night", ""),
    ("09-busto-vestito", "upper body, crimson velvet dress, looking away, "
                         "chandelier bokeh, dark ballroom", ""),
    ("10-busto-trench", "upper body, beige trench coat, rain, "
                        "cool blue street light, blurred city", ""),
    ("11-busto-maglione", "upper body, oversized cream knit sweater, holding a cup, "
                          "morning light, window", ""),
    ("12-busto-corsetto", "black satin corset, upper body, glamorous lingerie editorial, "
                          "fully clothed, elegant sensual pose, warm rim light, dark studio", ""),
    ("13-busto-setasbieco", "ivory silk slip, upper body, glamorous lingerie editorial, "
                            "fully clothed, elegant sensual pose, soft box light, dark studio", ""),

    # ── Figure intere: dove si giudica una posa. Il ControlNet la impone, ──
    # ── quindi la scena può permettersi di descrivere solo il resto.     ──
    ("14-figura-abitoviola", "full body, long violet evening gown, marble hall, "
                             "chandelier light", "standing"),
    ("15-figura-tailleur", "full body, grey tailored suit, glass corridor, "
                           "rain on glass", "walking"),
    ("16-figura-cappotto", "full body, long black coat, snowy street at night, "
                           "neon reflections", "standing"),
    ("17-figura-jeans", "full body, denim jacket and jeans, wet cobblestone street, "
                        "warm streetlamps", "standing"),
    ("18-figura-abitoverde", "full body, emerald satin dress, greenhouse at dusk, "
                             "hanging plants", "standing"),
    ("19-figura-danza", "full body, flowing white dress, rooftop at sunset, "
                        "city skyline", "dancing"),
    ("20-figura-piumino", "full body, black puffer coat and boots, "
                          "neon-lit alley after rain", "walking"),

    # ── Glamour in lingerie: il vocabolario della banda VIP, e nient'altro. ──
    # ── L'abito viene PRIMA delle parole di banda: nella finestra CLIP della ──
    # ── vetrina (lo stile è lungo) ci entra per primo, e la banda lo tiene    ──
    # ── vestito (`fully clothed`).                                          ──
    ("21-figura-calze", "black lace bodysuit with sheer stockings, full body, standing, "
                        "glamorous lingerie editorial, fully clothed, elegant sensual pose, "
                        "warm studio light, dark backdrop", "standing"),
    ("22-seduta-chaise", "seated on a velvet chaise longue, legs crossed, "
                         "ivory satin slip with sheer stockings, glamorous lingerie editorial, "
                         "fully clothed, elegant sensual pose, soft window light", "seated"),
    ("23-figura-reggicalze", "full body, standing, deep violet corset with sheer "
                             "thigh-high stockings, glamorous lingerie editorial, fully clothed, "
                             "elegant sensual pose, violet rim light", "standing"),
    ("24-sdraiata-divano", "lying on a dark sofa, champagne silk robe over black lace, "
                           "sheer stockings, glamorous lingerie editorial, fully clothed, "
                           "elegant sensual pose, candlelight", "lying"),

    # ── Il resto del corpo e dell'ambiente: la stanza con dentro qualcuno. ──
    ("25-seduta-poltrona", "seated on an armchair, legs crossed, black knit sweater, "
                           "dim lamp, scattered books", "seated"),
    ("26-seduta-davanzale", "seated on a windowsill, knees drawn up, grey hoodie, "
                            "city lights bokeh at dusk", "seated"),
    ("27-sdraiata-erba", "lying on night grass, dark clothes, fireflies, "
                         "green glow", "lying"),
    ("28-seduta-treno", "seated by a train window, chin on hand, long camel coat, "
                        "passing fields, golden hour", "seated"),
    ("29-figura-faro", "full body, arms open, long grey knit dress, stormy sea, "
                       "lighthouse beam", "arms_open"),
    ("30-figura-studio", "full body, plain dark grey studio backdrop, simple black top, "
                         "soft box light", "standing"),

    # ── Boudoir e danza: erotismo adulto non grafico. L'abbigliamento resta ──
    # ── dichiarato; il negativo della vetrina continua a escludere nude. ──
    ("31-danza-neon", "full body, black fitted dance bodysuit and ankle boots, sensual heels dance, violet and blue neon bars, dramatic silhouette, fully clothed", "dancing"),
    ("32-danza-velo", "full body, deep violet satin bodysuit with a flowing sheer robe, slow contemporary dance, dark studio, rose rim light, fully clothed", "dancing"),
    ("33-boudoir-poltrona", "seated sideways on a velvet armchair, black lace bodysuit with a silk robe, adult boudoir editorial, elegant sensual pose, candlelit studio, fully clothed", "seated"),
    ("34-boudoir-specchio", "full body, ivory satin slip and long robe, looking over shoulder into a tall mirror, adult boudoir editorial, warm dressing-room lights, fully clothed", "standing"),
    ("35-danza-rosso", "full body, crimson velvet catsuit, expressive arms and arched back, solo stage dance, red theatre spotlight, fully clothed", "dancing"),
    ("36-corsetto-finestra", "seated by a rain-streaked window, violet corset over a black silk blouse, sheer stockings, adult glamour editorial, blue night city bokeh, fully clothed", "seated"),
    ("37-body-argento", "full body, silver sequined bodysuit under an oversized black blazer, fashion dance rehearsal, dark mirror studio, fully clothed", "standing"),
    ("38-tango-solo", "full body, black satin dress with a high slit over opaque tights, solo tango pose, smoky ballroom, amber spotlight, fully clothed", "dancing"),
    ("39-divano-seta", "lying elegantly on a dark velvet sofa, champagne silk robe over a black lace bodysuit, adult boudoir editorial, soft candlelight, fully clothed", "lying"),
    ("40-danza-tetto", "full body, black fitted jumpsuit and heeled boots, night rooftop dance, indigo skyline, wind in long hair, fully clothed", "dancing"),
    ("41-paillettes", "full body, midnight-blue sequined mini dress with opaque stockings, disco floor reflection, confident fashion pose, fully clothed", "standing"),
    ("42-velo-luna", "full body, long translucent violet overskirt over a fitted black bodysuit, moonlit slow dance, artificial garden lights, fully clothed", "dancing"),
    ("43-sedia-regista", "seated backward on a director chair, black corset top under a tailored jacket, adult glamour editorial, soft box and deep shadows, fully clothed", "seated"),
    ("44-cabina", "full body, ivory satin camisole with high-waisted black trousers, dressing-room editorial, hand on curtain, warm bulbs, fully clothed", "standing"),
    ("45-danza-piume", "full body, black fringe dance dress over opaque bodysuit, motion blur from a jazz dance turn, violet stage haze, fully clothed", "dancing"),
    ("46-piscina-notte", "full body, black one-piece fashion swimsuit with a long sheer cover-up, night poolside editorial, neon reflections, fully clothed", "standing"),
    ("47-letto-editoriale", "reclining on a neatly made dark satin bed, velvet robe over a lace bodysuit, adult boudoir fashion editorial, low warm light, fully clothed", "lying"),
    ("48-danza-industriale", "full body, graphite sleeveless jumpsuit and heeled boots, powerful contemporary dance in a concrete studio, blue rim light, fully clothed", "dancing"),
    ("49-ritratto-sensuale", "upper body, black lace top beneath a velvet blazer, bare shoulders covered by the jacket, adult glamour portrait, intimate amber light, fully clothed", ""),
    ("50-silhouette-aurora", "full body silhouette, violet fitted bodysuit and flowing coat, arms raised in a final dance pose, bright aurora backlight, black studio, fully clothed", "dancing"),
)


def scelte(solo: str) -> List[Tuple[str, str, str]]:
    """Le varianti da fare: tutte, o quelle nominate in `--solo` (numeri o nomi).

    Il numero si confronta con lo zero davanti (`7` → `07`): senza, `--solo 1`
    pescherebbe anche 10, 11 e 12 con una sottostringa. Stessa regola di
    `serie.scelte`, e per lo stesso motivo: `--solo 21,22,23,24` deve pescare le
    quattro glamour e non mezza serie.
    """
    volute = [voce.strip().lower() for voce in (solo or "").split(",") if voce.strip()]
    if not volute:
        return list(SCENE)
    scelte_fatte: List[Tuple[str, str, str]] = []
    for nome, scena, posa in SCENE:
        numero = nome.split("-")[0]
        for voluta in volute:
            if (voluta == nome.lower() or voluta.zfill(2) == numero
                    or (voluta.isdigit() and int(voluta) == int(numero))):
                scelte_fatte.append((nome, scena, posa))
                break
    return scelte_fatte


def accoda_aspettando(base: str, token: str, variante: dict, *, scena: str,
                      seed: Optional[int], creatore: bool, pausa_s: float,
                      pazienza_s: float, log: Callable = print,
                      accoda: Callable = cli.accoda_ritratto,
                      dormi: Callable = time.sleep) -> Tuple[Optional[dict], str, float]:
    """Accoda un job, **aspettando che la coda si liberi** se è piena.

    È la ragione per cui questo script esiste. `ImmagineQueue.accoda` rifiuta con
    HTTP 429 (`coda piena`) oltre `IMAGE_QUEUE_MAX`, e una serie di trenta con un tetto
    di ventiquattro non entra in un colpo: qui il rifiuto non è un fallimento ma un
    «aspetta», e i job che avanzano entrano man mano che il ponte conclude i primi.

    Si ritenta su HTTP 429 (coda piena) e su HTTP 0 (control-plane non raggiungibile
    per un istante): sono le due cose che passano da sole. Tutto il resto — una scena
    rifiutata, un payload che il server non accetta, un token sbagliato — è un errore
    che ritentare non sana, e si riporta subito invece di girare tutta la notte per
    niente. `pazienza_s` è il tetto complessivo per UNA scena: oltre, si rinuncia e la
    si dichiara «non accodata», così il log della mattina dice quale manca e perché.

    `accoda` e `dormi` sono parametri per i test (nessuno vuole aspettare sessanta
    secondi veri per verificare che si aspetti sessanta secondi) e tornano a
    `cli.accoda_ritratto` / `time.sleep` nella vita reale.
    """
    inizio = time.monotonic()
    scadenza = inizio + max(0.0, pazienza_s)
    while True:
        stato, dati = accoda(base, token, variante, scena=scena, seed=seed, creatore=creatore)
        if stato == 201 and dati.get("ok"):
            return dati.get("job") or {}, "", time.monotonic() - inizio
        motivo = (str(dati.get("error") or dati.get("errore") or "").strip()
                  or f"HTTP {stato}")[:160]
        if stato not in (0, 429) or time.monotonic() >= scadenza:
            return None, motivo, time.monotonic() - inizio
        # Si dice quanto si è disposti ad aspettare: una coda piena alle tre del
        # mattino è normale, una coda piena per due ore vuol dire che il ponte non
        # macina, e chi legge il log deve poterlo capire senza contare le righe.
        log(f"    {motivo} — aspetto {int(pausa_s)}s "
            f"(ne ho per altri {int(max(0.0, scadenza - time.monotonic()))}s)")
        dormi(max(1.0, pausa_s))


def stato_coda(base: str, token: str) -> str:
    """Com'è la coda adesso: è la riga che la mattina dice se manca ancora qualcosa."""
    stato, dati = cli.chiama(f"{base}/image/status", token, timeout=15)
    if stato != 200:
        return f"non leggibile (HTTP {stato or dati.get('errore', '')})"
    return f"in coda {dati.get('in_coda')}, in esecuzione {dati.get('in_esecuzione')}"


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # I testi hanno accenti e trattini lunghi; e questa serie gira di notte,
        # spesso con l'uscita su un file: senza `line_buffering` il log resta vuoto
        # fino alla fine, e un log che non si legge mentre gira non è un log.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    parser = argparse.ArgumentParser(
        description="Accoda una serie notturna di varianti della stessa persona "
                    "(volti, abiti, ambienti, pose) e aspetta che la coda le assorba.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--persona", default="", help="documento di identità (default: quello del repo)")
    parser.add_argument("--solo", default="", help="solo alcune scene: numeri o nomi, separati da virgola")
    parser.add_argument("--prova", action="store_true",
                        help="stampa le scene, i token e i rifiuti: non accoda nulla")
    parser.add_argument("--seed", type=int, default=None, help="un altro seed = un'altra persona")
    # Il volto, come in `serie.py`: si mette in ComfyUI/input una volta e tutte le
    # trenta lo portano al job. È la ragione per cui una serie è una serie.
    parser.add_argument("--riferimento", default="",
                        help="immagine del volto da usare come riferimento per TUTTE le "
                             "scene (serve una famiglia con IP-Adapter)")
    parser.add_argument("--riferimento-forza", type=float, default=None,
                        help="peso del riferimento sul volto (default: quello dichiarato, "
                             f"{RIFERIMENTO_FORZA_DEFAULT})")
    parser.add_argument("--comfy", default=os.getenv("COMFY_URL", cli.COMFY_DEFAULT),
                        help="indirizzo di ComfyUI: serve solo a mettere il riferimento "
                             "nella sua cartella input")
    parser.add_argument("--misura", default="", help="LxA del PRIMO passaggio (default: quella dichiarata)")
    parser.add_argument("--fix", type=int, default=None, help="secondo passaggio 2× (default: quello dichiarato)")
    parser.add_argument("--passi", type=int, default=None, help="passi (default: quelli dichiarati)")
    parser.add_argument("--url", default=os.getenv("CHANNEL_URL", "http://127.0.0.1:8085"))
    parser.add_argument("--pausa", type=float, default=60.0,
                        help="secondi fra due tentativi quando la coda è piena (default 60)")
    parser.add_argument("--pazienza", type=float, default=7200.0,
                        help="per OGNI scena: quanto si aspetta in tutto che la coda si "
                             "liberi, prima di dichiararla non accodata (default 7200: due "
                             "ore, il tempo di parecchie immagini col tetto di 1800 s del ponte)")
    parser.add_argument("--attesa", type=float, default=2400.0,
                        help="con --indice: secondi di attesa massima per OGNI immagine "
                             "(default 2400, come `serie.py`)")
    parser.add_argument("--output", default=os.getenv("COMFY_OUTPUT_DIR", ""),
                        help="cartella di output di ComfyUI: serve a leggere la misura dei file")
    parser.add_argument("--indice", default="",
                        help="dove scrivere la pagina HTML con le immagini: aspetta la fine "
                             "di tutte (senza, lo script accoda e va a dormire)")
    parser.add_argument("--tokenizer", default=os.getenv("SD15_TOKENIZER_DIR", ""),
                        help="cartella del tokenizer di SD 1.5: serve solo a contare i token (77)")
    parser.add_argument("--creatore", action="store_true",
                        help="NON serve a QUESTE scene, che sono tutte vestite: toglierebbe "
                             "«nudità» dal negativo, cioè l'unica parola che tiene i vestiti "
                             "addosso. Resta per simmetria con `ritratto.py`/`serie.py`")
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")

    percorso = cli.trova_persona(args.persona)
    if percorso is None:
        print("documento di identità non trovato: usa --persona <file>")
        return 1
    try:
        documento = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"documento illeggibile ({percorso}): {e}")
        return 1
    vetrina = vetrina_dal_documento(documento)
    if args.misura:
        pezzi = str(args.misura).lower().replace(" ", "").split("x")
        try:
            vetrina["larghezza"], vetrina["altezza"] = int(pezzi[0]), int(pezzi[1])
        except (IndexError, ValueError):
            print(f"--misura non capita: {args.misura} (serve LxA, per esempio 512x768)")
            return 1
    if args.fix is not None:
        vetrina["fix"] = int(args.fix)
    if args.passi is not None:
        vetrina["passi"] = int(args.passi)

    # Il riferimento chiesto a mano vince su quello del documento, e vale per tutte e
    # trenta le scene: una serie è il posto dove si giudica un volto, e giudicarlo su
    # trenta volti diversi non è un giudizio.
    if args.riferimento:
        nome_riferimento = cli.prepara_riferimento(args.riferimento, args.comfy)
        if not nome_riferimento:
            return 1
        vetrina["riferimento"] = nome_riferimento
    if args.riferimento_forza is not None:
        vetrina["riferimento_forza"] = float(args.riferimento_forza)
    famiglia_volto = str(vetrina.get("famiglia") or FAMIGLIA_DEFAULT)
    if vetrina.get("riferimento") and not riferimento_supportato(famiglia_volto):
        print(f"STOP: la famiglia «{famiglia_volto}» non ha l'adattatore del volto "
              "(IP-Adapter + CLIP-ViT): il riferimento non arriverebbe al modello. "
              "Togli --riferimento, o usa la famiglia che ce l'ha.")
        return 1

    tok = conta_token(args.tokenizer)
    varianti = scelte(args.solo)
    if not varianti:
        print("nessuna scena da fare: --solo non ha trovato nulla")
        return 1
    print(f"documento: {percorso}")
    print(f"identità:  {documento.get('name', '?')} ({documento.get('kind', '?')})")
    print(f"vetrina:   seed {vetrina['seed']} · {vetrina['larghezza']}x{vetrina['altezza']} · "
          f"{vetrina['passi']} passi · fix {int(vetrina.get('fix') or 0)}")
    print("modello:   " + (str(vetrina.get("famiglia") or "")
                           or "(famiglia di default della coda)")
          + (f" · {vetrina['modello']}" if vetrina.get("modello") else ""))
    print(f"serie:     {len(varianti)} scene · pause {int(args.pausa)}s · "
          f"pazienza {int(args.pazienza)}s per scena"
          + (" · indice alla fine" if args.indice else " · si accoda e basta"))
    if vetrina.get("riferimento"):
        print(f"riferimento: {vetrina['riferimento']} · forza {vetrina['riferimento_forza']}"
              + (" (dalla riga di comando, non dal documento)" if args.riferimento else ""))
    else:
        print("riferimento: nessuno — il volto lo decide il seed (stesso seed, stesso "
              "disegno; scene diverse possono cambiare il volto)")
    if args.creatore:
        print("creatore:  ATTENZIONE — le scene di questa serie sono vestite, e questo "
              "toglie «nudità» dal negativo: la parola che le tiene vestite")

    token = ""
    if not args.prova:
        token = cli.token_canale()
        if not token:
            print("nessun token di canale in .env (CHANNEL_CLIENTS): la coda non è raggiungibile")
            return 1
        stato, dati = cli.chiama(f"{base}/image/status", token, timeout=15)
        if stato == 200:
            print(f"control-plane {base}: ok ({stato_coda(base, token)})")
        else:
            print(f"control-plane {base}: non raggiungibile ({stato or dati.get('errore', '')})")
            return 1

    esiti: List[dict] = []
    attese_s = 0.0
    for numero, (nome, scena, posa) in enumerate(varianti, start=1):
        # La posa è della variante, e va solo dove il ControlNet la sa imporre: dove
        # manca, `posa_da_mandare` torna vuoto e il testo fa come ha sempre fatto.
        variante = {**vetrina, "scena": scena, "pose_preset": posa_da_mandare(vetrina, posa)}
        aggiunte = []
        if args.creatore and str(scena).strip():
            variante, aggiunte = vetrina_con_quadro_erotismo(variante)
        print("")
        print(f"[{numero}/{len(varianti)}] {nome} — {scena}")
        if variante["pose_preset"]:
            print(f"  posa: {variante['pose_preset']} (ControlNet openpose)")
        elif posa:
            print(f"  posa: {posa} — lasciata al testo (la famiglia non ha il "
                  "ControlNet openpose: imporla farebbe fallire il job)")
        if aggiunte:
            print("  quadro: " + ", ".join(aggiunte) + " — scritto qui (la scena non lo dichiara)")
        problemi = verifica_vetrina(variante, documento, creatore=args.creatore)
        if problemi:
            print("  RIFIUTATA — il documento di questa persona non la permette:")
            for problema in problemi:
                print(f"    - {problema}")
            esiti.append({"nome": nome, "scena": scena, "stato": "rifiutata"})
            continue
        if tok:
            # Il tetto è 77 token e CLIP legge l'INIZIO del prompt: quello che conta non
            # è il totale (la dichiarazione in coda lo supera sempre, ed è la ragione per
            # cui sta anche nella prima frase dello stile) ma se `stile + scena` ci sta.
            quanti = len(tok.encode(f"{vetrina.get('stile')}. {variante['scena']}"))
            print(f"  stile+scena {quanti} token su 77"
                  + ("" if quanti <= 77 else " ← NON ci sta tutto: la coda della scena "
                                             "non arriva al modello"))
        if args.prova:
            print(f"  {prompt_ritratto(variante)}")
            continue
        # La scena va passata come ARGOMENTO, non solo dentro la variante: è da lì che
        # `accoda_ritratto` calcola l'offset del seed. Con la scena sola nel dizionario il
        # prompt è giusto e il seed resta uno per tutte — la serie del 2026-10-01 è uscita
        # così, otto immagini con un seed solo, la stessa palette in tutte.
        job, motivo, atteso = accoda_aspettando(
            base, token, variante, scena=scena, seed=args.seed, creatore=args.creatore,
            pausa_s=args.pausa, pazienza_s=args.pazienza)
        attese_s += atteso
        if job is None:
            print(f"  NON ACCODADA: {motivo}")
            esiti.append({"nome": nome, "scena": scena, "stato": "non accodata", "motivo": motivo})
            continue
        fattore = int(job.get("fix") or 0)
        print(f"  job {job['id']}: {job['larghezza']}x{job['altezza']} passi={job['passi']} "
              f"seed={job['seed']}"
              + (f" · fix {fattore}× → {job['larghezza'] * fattore}x{job['altezza'] * fattore}"
                 if fattore > 1 else "")
              + (f" · in coda dopo {int(atteso)}s di attesa" if atteso >= 1 else ""))
        esiti.append({"nome": nome, "scena": scena, "job": job["id"], "seed": job["seed"],
                      "stato": "accodata"})

    if args.prova:
        return 0

    accodate = [voce for voce in esiti if voce.get("job")]
    rifiutate = [voce for voce in esiti if voce.get("stato") == "rifiutata"]
    non_accodate = [voce for voce in esiti if voce.get("stato") == "non accodata"]
    print("")
    print(f"accodate {len(accodate)} scene su {len(varianti)}"
          + (f" · {len(rifiutate)} rifiutate" if rifiutate else "")
          + (f" · {len(non_accodate)} non accodate" if non_accodate else "")
          + (f" · {int(attese_s)}s passati ad aspettare la coda" if attese_s >= 1 else ""))
    # La coda com'è ADESSO: è la riga che la mattina dice se il lavoro è finito o se
    # c'è ancora qualcosa che gira (e quindi vale la pena aspettare prima di giudicare).
    print(f"coda: {stato_coda(base, token)}")
    for voce in esiti:
        print(f"  {voce['nome']:<20} {voce.get('stato', ''):<12} "
              f"{str(voce.get('job') or ''):<12} {voce.get('motivo') or ''}")

    if args.indice and accodate:
        print("")
        print(f"aspetto {len(accodate)} immagini per l'indice (fino a {int(args.attesa)}s "
              "l'una: sono in parallelo, non in fila)…")
        for voce in accodate:
            finale = cli.aspetta_job(base, token, voce["job"], attesa_s=args.attesa, ogni_s=15)
            esito = finale.get("esito") or {}
            voce["stato"] = finale.get("stato", "?")
            if voce["stato"] == "done" and esito.get("file"):
                completo = ((Path(args.output) / esito["file"]) if args.output
                            else Path(esito["file"]))
                voce["file"] = str(completo)
                voce["misura"] = misura_file(completo) if completo.is_file() else None
                voce["durata_s"] = round((esito.get("durata_ms") or 0) / 1000)
                print(f"  {voce['nome']:<20} fatto in {voce['durata_s']}s: {esito['file']}"
                      + (f" · {voce['misura'][0]}x{voce['misura'][1]}" if voce["misura"]
                         else " · misura non letta"))
            else:
                voce["motivo"] = str(esito.get("errore") or "")
                print(f"  {voce['nome']:<20} non concluso: stato={voce['stato']} {voce['motivo']}")
        fatte = [voce for voce in accodate if voce.get("file")]
        if scrivi_indice(Path(args.indice), fatte, documento, vetrina):
            print(f"indice: {args.indice} ({len(fatte)} immagini)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
