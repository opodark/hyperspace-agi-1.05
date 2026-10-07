# SPDX-License-Identifier: Apache-2.0
"""Il registro dettagliato dei sogni: righe correlate, dedup dei salti, robustezza."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.dream_log import (FASI, RegistroSogni, riga,  # noqa: E402
                              salto_da_scrivere, scrivi)


def test_riga_rifiuta_una_fase_sconosciuta():
    try:
        riga(fase="boh")
    except ValueError as errore:
        assert "boh" in str(errore)
    else:
        raise AssertionError("una fase fuori da FASI deve sollevare ValueError")


def test_riga_normalizza_autore_e_tronca_i_campi_lunghi():
    voce = riga(fase="scritto", autore="Anna", testo="  un   sogno\nlargo ",
                dettaglio="x" * 1000)
    assert voce["autore"] == "anna"
    assert voce["testo"] == "un sogno largo"
    assert len(voce["dettaglio"]) == 400
    assert voce["fase"] in FASI and voce["ts"]


def test_registro_scrive_e_rilegge_con_la_voce_del_sogno(tmp_path):
    percorso = tmp_path / "dreams.jsonl"
    registro = RegistroSogni(str(percorso))
    registro.append(riga(fase="scritto", voce_id="sogno-1", autore="anna"))
    registro.append(riga(fase="pubblicato", voce_id="sogno-1", media_id="42"))
    assert [r["fase"] for r in registro.read()] == ["scritto", "pubblicato"]
    assert registro.ultimo(voce_id="sogno-1")["fase"] == "pubblicato"
    assert registro.ultimo(fase="scritto")["voce_id"] == "sogno-1"
    assert registro.ultimo(fase="inesistente") is None
    assert registro.ultimo_per_voce()["sogno-1"]["media_id"] == "42"
    prima = percorso.read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(prima)["voce_id"] == "sogno-1"


def test_registro_salta_le_righe_rotte_invece_di_perdere_tutto(tmp_path):
    percorso = tmp_path / "dreams.jsonl"
    percorso.write_text('{"fase":"scritto"}\nnon-json\n{"fase":"ignota"}\n'
                        '{"fase":"pubblicato"}\n', encoding="utf-8")
    assert [r["fase"] for r in RegistroSogni(str(percorso)).read()] == ["scritto", "pubblicato"]


def test_registro_senza_percorso_e_un_interruttore_spento():
    assert RegistroSogni("").append(riga(fase="scritto"))["fase"] == "scritto"
    assert RegistroSogni("").read() == []
    assert RegistroSogni("").ultimo() is None


def test_salto_da_scrivere_solo_per_motivo_nuovo_o_cooldown():
    primo = {"motivo": "fuori finestra", "ts": "2026-10-06T00:00:00+00:00"}
    assert salto_da_scrivere("fuori finestra", None)
    assert salto_da_scrivere("fuori finestra", primo,
                             istante="2026-10-06T01:00:00+00:00")
    assert not salto_da_scrivere("fuori finestra", primo,
                                 istante="2026-10-06T00:10:00+00:00")
    assert salto_da_scrivere("quota esaurita", primo,
                             istante="2026-10-06T00:10:00+00:00")
    assert not salto_da_scrivere("", primo)


def test_scrivi_crea_le_cartelle_e_non_fallisce_mai_forte(tmp_path):
    nuovo = tmp_path / "registro" / "dreams.jsonl"
    assert scrivi(str(nuovo), fase="scritto")["fase"] == "scritto"
    assert nuovo.is_file()
    assert scrivi(str(tmp_path), fase="scritto") == {}      # un file che è una cartella
    assert scrivi("", fase="scritto")["fase"] == "scritto"
