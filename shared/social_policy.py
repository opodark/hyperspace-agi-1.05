# SPDX-License-Identifier: Apache-2.0
"""Politica della pubblicazione social automatica: pura, senza rete né token.

Come `shared/connector_policy.py`: decide SE un contenuto può uscire su un
canale (instagram/x) e QUANDO (finestra oraria del tipo), ma non esegue nulla.
Il publisher applica il verdetto. Regole: interruttore generale e per canale,
dry-run, tetti giornalieri (per tipo e per canale), finestre orarie, nessun
contenuto esplicito nel pubblico, disclosure IA obbligatoria su Instagram
(su X la disclosure è il campo `made_with_ai`).
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CANALI = ("instagram", "x")
TIPI = ("sogno", "poesia", "dialogo", "post")
PERSONE = ("anna", "aurora")

# Tetto giornaliero per tipo. `post` è 0: il loop del feed produce bozze e non
# pubblica in automatico; i dialoghi ne escono uno solo al giorno.
CAP_PER_TIPO = {"sogno": 1, "poesia": 1, "dialogo": 1, "post": 0}

# Finestre di pubblicazione (ore locali, Europa/Roma). X parte mezz'ora dopo IG
# per non affiancare due post identici sullo stesso minuto.
FINESTRE = {
    "sogno": ((7, 0), (10, 0)),
    "poesia": ((12, 0), (15, 0)),
    "dialogo": ((18, 0), (21, 0)),
    "post": ((7, 0), (23, 0)),
}

# Marcatori di disclosure IA che la composizione mette sempre in didascalia.
MARCATORI_IA = ("#AIDreams", "#AIPoetry", "#AIDialogo", "#AIAuthor", "#IA")

# Termini che nel pubblico non devono passare: il contenuto intimo resta nel
# ramo DM (`shared/intimate_diary.py`). È una rete di sicurezza, non il gate
# primario: i prompt pubblici non producono quel registro.
TERMINI_ESPLICITI = (
    "nudo", "nuda", "nudi", "sesso", "sessuale", "sessuali", "erotico",
    "erotica", "erotici", "esplicito", "esplicita", "espliciti", "porno",
    "pornografico", "pornografica", "penetrazione", "orgasmo",
)
_ESPLICITO = re.compile(r"\b(" + "|".join(TERMINI_ESPLICITI) + r")\b")

DEFAULT = {
    "SOCIAL_PUBLISH_ENABLED": "true",
    "SOCIAL_IG_ENABLED": "true",
    "SOCIAL_X_ENABLED": "false",
    "SOCIAL_DRY_RUN": "true",
    "SOCIAL_HOLD_MINUTES": "15",
    "SOCIAL_MAX_PER_DAY": "3",
    "SOCIAL_MIN_GAP_MINUTES": "180",
    "SOCIAL_TIMEZONE": "Europe/Rome",
}


def _vero(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "sì", "si", "yes", "on"}


def _intero(v, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


class SocialPolicy:
    def __init__(self, cfg=None):
        self.cfg = dict(DEFAULT)
        if cfg:
            self.cfg.update({k: str(v) for k, v in cfg.items() if v is not None})

    @classmethod
    def from_env(cls, environ=None) -> "SocialPolicy":
        env = os.environ if environ is None else environ
        cfg = {k: env[k] for k in DEFAULT if k in env}
        # Retrocompatibilità: il vecchio flag dei sogni resta alias del canale IG.
        if "SOCIAL_IG_ENABLED" not in cfg and "INSTAGRAM_DREAM_PUBLISH_ENABLED" in env:
            cfg["SOCIAL_IG_ENABLED"] = env["INSTAGRAM_DREAM_PUBLISH_ENABLED"]
        return cls(cfg)

    @property
    def enabled(self) -> bool:
        return _vero(self.cfg.get("SOCIAL_PUBLISH_ENABLED", "true"))

    @property
    def dry_run(self) -> bool:
        return _vero(self.cfg.get("SOCIAL_DRY_RUN", "true"))

    @property
    def hold_minuti(self) -> int:
        return max(0, _intero(self.cfg.get("SOCIAL_HOLD_MINUTES"), 15))

    def canale_abilitato(self, canale: str) -> bool:
        if not self.enabled:
            return False
        if canale == "instagram":
            return _vero(self.cfg.get("SOCIAL_IG_ENABLED", "true"))
        if canale == "x":
            return _vero(self.cfg.get("SOCIAL_X_ENABLED", "false"))
        return False

    def tetto_canale(self, canale: str) -> int:
        return max(0, _intero(self.cfg.get("SOCIAL_MAX_PER_DAY"), 3))

    def tetto_tipo(self, tipo: str) -> int:
        return int(CAP_PER_TIPO.get(tipo, 0))

    @property
    def gap_minimo_s(self) -> float:
        return max(0, _intero(self.cfg.get("SOCIAL_MIN_GAP_MINUTES"), 180)) * 60.0

    def fuso(self) -> ZoneInfo:
        try:
            return ZoneInfo(str(self.cfg.get("SOCIAL_TIMEZONE", "Europe/Rome")))
        except Exception:
            return ZoneInfo("Europe/Rome")

    def finestra(self, tipo: str, canale: str, adesso: datetime) -> tuple[datetime, bool]:
        """(istante in cui può uscire, è già dentro la finestra).

        Fuori finestra il tipo aspetta la prossima apertura dello stesso giorno
        o del giorno dopo; dentro, risponde con `adesso` (il publish_after lo
        fisserà poi il chiamante aggiungendo l'hold).
        """
        start, end = FINESTRE.get(tipo, FINESTRE["post"])
        local = adesso.astimezone(self.fuso())
        sh, sm = start
        eh, em = end
        if canale == "x":
            sm += 30
            if sm >= 60:
                sh = (sh + 1) % 24
                sm -= 60
            em += 30
            if em >= 60:
                eh = (eh + 1) % 24
                em -= 60
        apertura = local.replace(hour=sh, minute=sm, second=0, microsecond=0)
        chiusura = local.replace(hour=eh, minute=em, second=0, microsecond=0)
        if apertura <= local < chiusura:
            return local, True
        if local < apertura:
            return apertura, False
        return apertura + timedelta(days=1), False

    def check_voce(self, voce: dict, canale: str, adesso: datetime, *,
                   conteggi=None, ultimo_ts: float = 0.0) -> tuple[bool, str]:
        """(ok, motivo) — tutte le guardie tranne la finestra oraria.

        `conteggi`: `{tipo: numero già pubblicati oggi su questo canale}`.
        `ultimo_ts`: epoch dell'ultima pubblicazione del canale (per il gap).
        """
        if not self.enabled:
            return False, "SOCIAL_PUBLISH_ENABLED non è true"
        if canale not in CANALI:
            return False, f"canale sconosciuto: {canale!r}"
        if not self.canale_abilitato(canale):
            return False, f"canale {canale} spento"
        voce = voce if isinstance(voce, dict) else {}
        tipo = str(voce.get("tipo") or "").strip().lower()
        if tipo not in TIPI:
            return False, f"tipo sconosciuto: {tipo!r}"
        persona = str(voce.get("persona") or voce.get("author") or "").strip().lower()
        if persona not in PERSONE:
            return False, f"persona sconosciuta: {persona!r}"
        testo = " ".join(str(voce.get("testo") or "").split())
        if not testo:
            return False, "testo vuoto"
        if _ESPLICITO.search(testo.lower()):
            return False, "contenuto esplicito nel pubblico"
        caption = str(voce.get("caption") or "")
        limite = 2200 if canale == "instagram" else 280
        if len(caption or testo) > limite:
            return False, f"testo oltre il limite del canale {canale}"
        if canale == "instagram" and not any(m in (caption or testo)
                                             for m in MARCATORI_IA):
            return False, "manca la disclosure IA nella didascalia"
        conteggi = conteggi or {}
        if int(conteggi.get(tipo, 0)) >= self.tetto_tipo(tipo):
            return False, f"tetto giornaliero raggiunto per {tipo}"
        if sum(int(conteggi.get(t, 0)) for t in TIPI) >= self.tetto_canale(canale):
            return False, f"tetto giornaliero del canale raggiunto ({self.tetto_canale(canale)})"
        if ultimo_ts and adesso.timestamp() - float(ultimo_ts) < self.gap_minimo_s:
            return False, "intervallo minimo fra due pubblicazioni non passato"
        return True, ""
