# SPDX-License-Identifier: Apache-2.0
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.dream_schedule import (choose_author, conteggi_del_giorno,  # noqa: E402
                                   in_hour_window, prossima_finestra)

ROMA = ZoneInfo("Europe/Rome")


def test_night_window_supports_regular_and_midnight_ranges():
    assert in_hour_window(3, 0, 8)
    assert not in_hour_window(12, 0, 8)
    assert in_hour_window(23, 22, 6)
    assert in_hour_window(2, 22, 6)


def test_choose_author_balances_and_stops_at_cap():
    assert choose_author({"anna": 0, "aurora": 0}, maximum=2, turn=0) == "anna"
    assert choose_author({"anna": 1, "aurora": 0}, maximum=2, turn=0) == "aurora"
    assert choose_author({"anna": 2, "aurora": 1}, maximum=2, turn=0) == "aurora"
    assert choose_author({"anna": 2, "aurora": 2}, maximum=2, turn=0) is None


def test_conteggi_del_giorno_usa_il_giorno_locale_e_non_quello_utc():
    """Lo stesso istante è "oggi" a Roma e "ieri" altrove: la quota segue il fuso."""
    now = datetime(2026, 10, 6, 3, 0, tzinfo=ROMA)
    voci = [
        {"author": "anna", "tipo": "sogno", "ts": "2026-10-06T00:58:12+00:00"},    # 02:58 locali
        {"author": "aurora", "tipo": "sogno", "ts": "2026-10-05T23:00:00+00:00"},  # 01:00 locali
        {"author": "anna", "tipo": "sogno", "ts": "2026-10-04T22:00:00+00:00"},    # due giorni prima
        {"author": "anna", "tipo": "post", "ts": "2026-10-06T01:00:00+00:00"},     # tipo diverso
    ]
    conteggi, ultimo = conteggi_del_giorno(voci, now)
    assert conteggi == {"anna": 1, "aurora": 1}
    assert datetime.fromtimestamp(ultimo, tz=timezone.utc) == datetime(
        2026, 10, 6, 0, 58, 12, tzinfo=timezone.utc)


def test_conteggi_del_giorno_ignora_un_ts_illeggibile():
    now = datetime(2026, 10, 6, 3, 0, tzinfo=ROMA)
    conteggi, ultimo = conteggi_del_giorno(
        [{"author": "anna", "tipo": "sogno", "ts": "non-una-data"}], now)
    assert conteggi == {"anna": 0, "aurora": 0}
    assert ultimo == 0.0


def test_prossima_finestra_annuncia_la_riapertura_solo_da_fuori():
    mezzogiorno = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)
    notte = datetime(2026, 10, 6, 3, 0, tzinfo=timezone.utc)
    assert prossima_finestra(mezzogiorno, 0, 8) == datetime(
        2026, 10, 7, 0, 0, tzinfo=timezone.utc)
    assert prossima_finestra(notte, 0, 8) is None
    assert prossima_finestra(mezzogiorno, 22, 6) == datetime(
        2026, 10, 6, 22, 0, tzinfo=timezone.utc)
    assert prossima_finestra(mezzogiorno, 0, 0) is None       # finestra sempre aperta


def test_choose_author_rispetta_il_tetto_totale():
    assert choose_author({"anna": 1, "aurora": 0}, maximum=2, turn=0,
                         total_maximum=1) is None
    assert choose_author({"anna": 0, "aurora": 0}, maximum=2, turn=0,
                         total_maximum=1) == "anna"
    # senza total_maximum il comportamento storico resta invariato
    assert choose_author({"anna": 1, "aurora": 0}, maximum=2, turn=0) == "aurora"

