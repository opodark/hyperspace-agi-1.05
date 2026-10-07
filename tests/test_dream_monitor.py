# SPDX-License-Identifier: Apache-2.0
"""Il monitor dei sogni: fase di ogni sogno, verdetto sul ciclo, fotografia.

Il caso che questi test difendono è quello vero: tre notti senza sogni con il
ciclo acceso (`muto`) devono essere visibili, non invisibili.
"""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.dream_monitor import (FASE_DA_PUBBLICARE,  # noqa: E402
                                  FASE_IN_ATTESA, FASE_IN_CODA, FASE_IN_CORSO,
                                  FASE_PUBBLICATO, FASE_PUBBLICAZIONE_FALLITA,
                                  FASE_SKETCH_FALLITO, fase_di, indice_job,
                                  pipeline, salute, salti, sintesi)

ROMA = ZoneInfo("Europe/Rome")
NOTTE = datetime(2026, 10, 6, 3, 0, tzinfo=ROMA)


def voce(**campi) -> dict:
    base = {"id": "sogno-1", "author": "anna", "tipo": "sogno",
            "ts": "2026-10-06T00:58:12+00:00", "testo": "un sogno", "prompt": "scena"}
    base.update(campi)
    return base


def test_fase_di_segue_l_ordine_dei_fatti():
    assert fase_di(voce()) == FASE_IN_ATTESA
    assert fase_di(voce(), {"stato": "pending"}) == FASE_IN_CODA
    assert fase_di(voce(), {"stato": "running"}) == FASE_IN_CORSO
    assert fase_di(voce(), {"stato": "failed"}) == FASE_SKETCH_FALLITO
    assert fase_di(voce(file="HyperSpace/a.jpg"), {"stato": "done"}) == FASE_DA_PUBBLICARE
    assert fase_di(voce(file="HyperSpace/a.jpg")) == FASE_DA_PUBBLICARE
    assert fase_di(voce(instagram_status="published")) == FASE_PUBBLICATO
    assert fase_di(voce(instagram_status="failed")) == FASE_PUBBLICAZIONE_FALLITA


def test_lesito_pubblicato_vince_su_uno_stato_stantio_della_coda():
    assert fase_di(voce(instagram_status="published"), {"stato": "pending"}) == FASE_PUBBLICATO
    assert fase_di(voce(), None, {"fase": "pubblicato"}) == FASE_PUBBLICATO
    assert fase_di(voce(), None, {"fase": "fallito"}) == FASE_PUBBLICAZIONE_FALLITA


def test_indice_job_accetta_dict_o_lista_e_tiene_il_piu_recente():
    vecchio = {"id": "a", "destinazione": "sogno-1", "stato": "failed", "creato_ts": 1}
    nuovo = {"id": "b", "destinazione": "sogno-1", "stato": "done", "creato_ts": 2}
    for jobs in ({"jobs": {"a": vecchio, "b": nuovo}}, {"a": vecchio, "b": nuovo},
                 [vecchio, nuovo]):
        assert indice_job(jobs)["sogno-1"]["id"] == "b"
    assert indice_job({"jobs": {"x": {"destinazione": "", "stato": "done"}}}) == {}
    assert indice_job(None) == {}


def test_pipeline_unisce_diario_coda_e_registro():
    righe = pipeline(
        [voce(file="HyperSpace/a.jpg")],
        {"jobs": {"j1": {"id": "j1", "destinazione": "sogno-1", "stato": "done",
                         "creato_ts": 1}}},
        {"sogno-1": {"fase": "pubblicato", "dettaglio": "media=42"}})
    assert len(righe) == 1
    assert righe[0]["fase"] == FASE_PUBBLICATO
    assert righe[0]["autore"] == "anna" and righe[0]["disegnato"] is True
    assert righe[0]["job_id"] == "j1"
    assert righe[0]["dettaglio"] == "media=42"
    # le voci che non sono sogni non entrano nel monitor dei sogni
    assert pipeline([voce(tipo="post")], None, None) == []


def test_salute_distingue_ok_attenzione_muto_e_spento():
    assert salute("2026-10-06T00:58:12+00:00", NOTTE)["verdetto"] == "ok"
    assert salute("2026-10-05T00:00:00+00:00", NOTTE)["verdetto"] == "attenzione"
    assert salute("2026-10-02T00:13:37+00:00", NOTTE)["verdetto"] == "muto"
    assert salute("2026-10-02T00:13:37+00:00", NOTTE)["notti"] == 4
    assert salute("2026-10-02T00:13:37+00:00", NOTTE, abilitato=False)["verdetto"] == "spento"
    assert salute(None, NOTTE)["verdetto"] == "muto"


def test_pipeline_non_dipende_dall_ordine_dell_elenco():
    """Il diario consegna dal più recente, la coda dal più vecchio: il monitor ordina."""
    vecchio = voce(id="sogno-1", ts="2026-10-01T00:00:00+00:00")
    nuovo = voce(id="sogno-2", ts="2026-10-06T00:58:12+00:00")
    atteso = ["sogno-2", "sogno-1"]
    assert [r["voce_id"] for r in pipeline([vecchio, nuovo], None, None)] == atteso
    assert [r["voce_id"] for r in pipeline([nuovo, vecchio], None, None)] == atteso
    assert [r["voce_id"] for r in pipeline([nuovo, vecchio], None, None, limit=1)] == ["sogno-2"]


def test_salti_mostra_i_motivi_dal_piu_recente():
    righe = [{"fase": "saltato", "motivo": "fuori finestra"},
             {"fase": "scritto", "voce_id": "sogno-1"},
             {"fase": "saltato", "motivo": "quota esaurita"},
             {"fase": "saltato", "motivo": "intervallo minimo"}]
    assert [r["motivo"] for r in salti(righe, limit=2)] == ["intervallo minimo",
                                                            "quota esaurita"]
    assert salti(righe, limit=0) == []


def test_sintesi_riassume_quota_finestra_pipeline_e_salti():
    eventi = [{"fase": "saltato", "motivo": "quota esaurita",
               "ts": "2026-10-05T23:00:00+00:00"}]
    out = sintesi(
        voci=[voce()], adesso=NOTTE,
        jobs={"jobs": {"j1": {"id": "j1", "destinazione": "sogno-1",
                              "stato": "pending", "creato_ts": 1}}},
        eventi=eventi,
        config={"abilitato": True, "finestra": (0, 8), "quota_per_autrice": 2})
    assert out["quota"] == {"anna": 1, "aurora": 0, "totale": 1}
    assert out["finestra_aperta"] is True
    assert out["prossima_finestra"] is None
    assert out["ultimo_sogno"] == "2026-10-06T00:58:12+00:00"
    assert out["sogni"][0]["fase"] == FASE_IN_CODA
    assert out["salti"][0]["motivo"] == "quota esaurita"
    assert out["config"]["finestra"] == [0, 8]
    assert out["salute"]["verdetto"] == "ok"


def test_sintesi_senza_sogni_e_muta_e_annuncia_la_riapertura():
    out = sintesi(voci=[], adesso=datetime(2026, 10, 6, 12, 0, tzinfo=ROMA),
                  config={"abilitato": True, "finestra": (0, 8)})
    assert out["salute"]["verdetto"] == "muto"
    assert out["ultimo_sogno"] is None
    assert out["finestra_aperta"] is False
    assert out["prossima_finestra"].startswith("2026-10-07T00:00")
