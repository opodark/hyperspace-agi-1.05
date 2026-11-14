# SPDX-License-Identifier: Apache-2.0
"""La sonda dei 64.000 token: scripts/diagnostics/ctx64k_probe.py.

Cosa protegge:
1. LA SOLA LETTURA. Senza --run non deve partire nessuna chiamata che carichi
   un modello: su una GPU occupata vorrebbe dire buttare giu' il lavoro di altri.
2. IL GIUDIZIO. Una chiamata tool col codice sbagliato, o un prompt letto a
   meta', devono risultare NON idonei: e' cosi' che si vede un contesto troncato.
3. LA SELEZIONE. Solo modelli con tool calling e contesto addestrato sufficiente.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts.diagnostics import ctx64k_probe as sonda  # noqa: E402


def _risposta_tool(codice=sonda.CODICE, nome=sonda.TOOL_ATTESO, letti=20500):
    return {
        "message": {"tool_calls": [{"function": {"name": nome, "arguments": {"codice": codice}}}]},
        "prompt_eval_count": letti, "prompt_eval_duration": 10 * 10**9,
        "eval_count": 40, "eval_duration": 2 * 10**9,
    }


class OllamaFinto:
    """Risponde come Ollama e ricorda ogni chiamata ricevuta."""

    def __init__(self, chat=None):
        self.chiamate = []
        self.chat = chat or (lambda corpo: _risposta_tool(
            letti=len(corpo["messages"][1]["content"]) // sonda.CARATTERI_PER_TOKEN))
        self.modelli = {
            "buono:9b": {"capabilities": ["tools", "completion"], "model_info": {"x.context_length": 131072}},
            "corto:8b": {"capabilities": ["tools"], "model_info": {"x.context_length": 40960}},
            "muto:8b": {"capabilities": ["completion"], "model_info": {"x.context_length": 262144}},
        }

    def __call__(self, base, percorso, corpo=None, timeout=30):
        self.chiamate.append((percorso, corpo))
        if percorso == "/api/tags":
            return {"models": [{"name": n, "size": 5 * 10**9} for n in self.modelli]}
        if percorso == "/api/show":
            return self.modelli[corpo["model"]]
        if percorso == "/api/ps":
            return {"models": [{"name": "buono:9b", "context_length": 64000,
                                "size": 10 * 10**9, "size_vram": 10 * 10**9}]}
        if percorso == "/api/chat":
            return self.chat(corpo)
        return {}

    def percorsi(self):
        return [p for p, _ in self.chiamate]


def test_selezione_candidati():
    finto = OllamaFinto()
    elenco = {r["modello"]: r for r in sonda.elenca("http://x", http=finto)}
    assert elenco["buono:9b"]["candidato"] is True
    assert elenco["corto:8b"]["candidato"] is False and "40960" in elenco["corto:8b"]["motivo"]
    assert elenco["muto:8b"]["candidato"] is False and "tool" in elenco["muto:8b"]["motivo"]


def test_senza_run_non_carica_nulla(capsys):
    finto = OllamaFinto()
    assert sonda.main(["--ollama", "http://x"], http=finto) == 0
    assert "/api/chat" not in finto.percorsi()
    assert "/api/generate" not in finto.percorsi()
    assert "Sola lettura" in capsys.readouterr().out


def test_giudizio_distingue_giusto_e_sbagliato():
    assert sonda.giudica(_risposta_tool())[0] is True
    assert sonda.giudica(_risposta_tool(codice="ALTRO"))[0] is False
    assert sonda.giudica(_risposta_tool(nome="strumento_03"))[0] is False
    assert sonda.giudica({"message": {"content": "il codice e' 7Q4"}})[0] is False
    # argomenti arrivati come stringa JSON: accettati
    come_stringa = _risposta_tool()
    come_stringa["message"]["tool_calls"][0]["function"]["arguments"] = json.dumps({"codice": sonda.CODICE})
    assert sonda.giudica(come_stringa)[0] is True


def test_prompt_letto_a_meta_non_e_idoneo():
    finto = OllamaFinto(chat=lambda corpo: _risposta_tool(letti=4000))
    esito = sonda.prova("http://x", "buono:9b", 20000, http=finto)
    assert esito["ok"] is False and "troncato" in esito["motivo"]


def test_misura_completa_e_scarica_il_modello(capsys):
    finto = OllamaFinto()
    assert sonda.main(["--ollama", "http://x", "--run", "--json"], http=finto) == 0
    uscita = json.loads(capsys.readouterr().out)
    (risultato,) = uscita["risultati"]
    assert risultato["modello"] == "buono:9b" and risultato["idoneo"] is True
    assert risultato["quota_gpu"] == 100 and risultato["contesto"] == 64000
    assert [p["prompt_token_attesi"] for p in risultato["prove"]] == list(sonda.TAGLIE_PROMPT)
    chat = [c for p, c in finto.chiamate if p == "/api/chat"]
    assert all(c["options"]["num_ctx"] == 64000 and c["tools"] for c in chat)
    # alla fine il modello viene scaricato dalla VRAM
    assert ("/api/generate", {"model": "buono:9b", "keep_alive": 0}) in finto.chiamate
    assert uscita["caricati_prima"] == ["buono:9b"]


def test_il_codice_sta_all_inizio_e_la_richiesta_alla_fine():
    messaggio = sonda.costruisci_messaggi(2000)[1]["content"]
    assert messaggio.index(sonda.CODICE) < 200
    assert messaggio.rstrip().endswith("Non rispondere a parole.")
    assert len(messaggio) >= 2000 * sonda.CARATTERI_PER_TOKEN
