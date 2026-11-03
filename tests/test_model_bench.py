# SPDX-License-Identifier: Apache-2.0
"""Il banco di prova dei modelli: scripts/model_bench.py.

Cosa protegge, in ordine di quanto male farebbe un guasto silenzioso:

1. I GIUDICI. Se un giudice segna "giusto" una risposta sbagliata (o viceversa),
   l'intera tabella mente. Qui si prova che ogni giudice distingue una risposta
   giusta da una sbagliata.
2. LO STREAM. `consume_stream` e' la parte che decide quando un modello "non si
   ferma": un errore qui e' il modo in cui un bench puo' bloccarsi per ore.
3. IL FLAG THINK. `ask` deve mandare `think` SOLO quando il chiamante lo chiede:
   se lo mandasse sempre, falserebbe il confronto fra reasoning on/off.
"""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import model_bench as mb  # noqa: E402


def _giudici():
    return {nome: giudice for nome, _p, giudice, _a, _m in mb.PROBE}


def _riga(contenuto):
    return "data: " + json.dumps({"choices": [{"delta": {"content": contenuto}}]}) + "\n\n"


class GiudiciTests(unittest.TestCase):
    def test_ogni_giudice_distingue_il_giusto_dallo_sbagliato(self):
        casi = {
            "fatto_capitale": ("Canberra", "Sydney"),
            "matematica_orario": ("16:00", "17:30"),
            "matematica_sconto": ("60", "80"),
            "logica_famiglia": ("Il nonno, suo figlio e il nipote.", "Sono gemelli."),
            "conteggio_r": ("3", "4"),
            "json": ('{"citta": "Venezia", "abitanti": 250000}', "non lo so"),
            "allucinazione": ("Non lo so.", "L'ha scritto Mario Rossi nel 1999."),
        }
        giudici = _giudici()
        for nome, (giusta, sbagliata) in casi.items():
            with self.subTest(nome=nome):
                self.assertTrue(mb.segna(giudici[nome], giusta)[0], f"{nome} non riconosce il giusto")
                self.assertFalse(mb.segna(giudici[nome], sbagliata)[0], f"{nome} non riconosce lo sbagliato")


class CodiceTests(unittest.TestCase):
    def test_il_codice_giusto_passa(self):
        ok, _nota = mb.codice_ok("""
def is_palindrome(s):
    s = s.lower()
    return s == s[::-1]
""", file_uscita=tempfile.mktemp(suffix=".py"))
        self.assertTrue(ok)

    def test_il_codice_sbagliato_non_passa(self):
        ok, _nota = mb.codice_ok("""
def is_palindrome(s):
    return True
""", file_uscita=tempfile.mktemp(suffix=".py"))
        self.assertFalse(ok)

    def test_senza_funzione_non_passa(self):
        ok, _nota = mb.codice_ok("print('ciao')", file_uscita=tempfile.mktemp(suffix=".py"))
        self.assertFalse(ok)

    def test_estrai_codice_con_e_senza_fence(self):
        self.assertEqual(mb.estrai_codice("```python\ndef f():\n    return 1\n```"), "def f():\n    return 1")
        self.assertEqual(mb.estrai_codice("def f():\n    return 1"), "def f():\n    return 1")

    def test_json_si_estrae_e_si_scarta(self):
        self.assertEqual(mb._json('{"citta":"Venezia","abitanti":1}')["citta"], "Venezia")
        self.assertEqual(mb._json("niente qui"), {})


class SondeCodiceTests(unittest.TestCase):
    """Le tre sonde nate per il ruolo coder (`HS_MODEL_CODER`).

    Ognuna deve dire sì al codice giusto e no a quello sbagliato: una sonda che
    dice sempre sì rende la tabella inutile proprio dove serve decidere un
    download da 5 GB. Il contratto sta negli assert dei driver, quindi qui si
    prova anche che i casi limite (stringa vuota, None, mutazione) contino.
    """

    GIUSTO = {
        "codice_durata": (
            "```python\nimport re\n\n"
            "def durata_in_secondi(testo):\n"
            "    if not testo:\n"
            "        raise ValueError('vuoto')\n"
            "    pezzi = re.fullmatch(r'(?:(\\d+)h)?(?:(\\d+)m)?(?:(\\d+)s)?', testo)\n"
            "    if not pezzi:\n"
            "        raise ValueError(testo)\n"
            "    ore, minuti, secondi = (int(x or 0) for x in pezzi.groups())\n"
            "    return ore * 3600 + minuti * 60 + secondi\n```"
        ),
        "codice_bugfix": (
            "```python\ndef media(valori):\n"
            "    puliti = [v for v in valori if v is not None]\n"
            "    return sum(puliti) / len(puliti) if puliti else 0.0\n```"
        ),
        "codice_intervalli": (
            "```python\ndef unisci(intervalli):\n"
            "    if not intervalli:\n"
            "        return []\n"
            "    ordinati = sorted(intervalli)\n"
            "    uniti = [ordinati[0]]\n"
            "    for inizio, fine in ordinati[1:]:\n"
            "        ultimo_inizio, ultimo_fine = uniti[-1]\n"
            "        if inizio <= ultimo_fine:\n"
            "            uniti[-1] = (ultimo_inizio, max(ultimo_fine, fine))\n"
            "        else:\n"
            "            uniti.append((inizio, fine))\n"
            "    return uniti\n```"
        ),
    }

    SBAGLIATO = {
        # Nessun caso limite: zero invece di 5400.
        "codice_durata": "def durata_in_secondi(testo):\n    return 0\n",
        # Corregge la divisione per zero ma non i None: il contratto è più largo.
        "codice_bugfix": ("def media(valori):\n"
                          "    return sum(valori) / len(valori) if valori else 0.0\n"),
        # Non unisce niente e ignora l'ordine.
        "codice_intervalli": "def unisci(intervalli):\n    return list(intervalli)\n",
    }

    def test_ogni_sonda_di_codice_distingue_giusto_e_sbagliato(self):
        giudici = _giudici()
        for nome in self.GIUSTO:
            with self.subTest(nome=nome):
                self.assertTrue(giudici[nome](self.GIUSTO[nome])[0],
                                f"{nome} non riconosce il codice corretto")
                sbagliato = giudici[nome](self.SBAGLIATO[nome])
                self.assertFalse(sbagliato[0], f"{nome} approva il codice sbagliato")
                self.assertTrue(sbagliato[1], f"{nome} deve dire perché ha rifiutato")

    def test_senza_la_funzione_chiesta_non_passa(self):
        ok, nota = mb.codice_esegue("print('ciao')", "def unisci", mb.DRIVER_INTERVALLI)
        self.assertFalse(ok)
        self.assertIn("unisci", nota)

    def test_il_codice_giusto_tra_prosa_si_estrae_lo_stesso(self):
        risposta = "Ecco la funzione:\n\n" + self.GIUSTO["codice_intervalli"] + "\nSpero aiuti."
        self.assertTrue(mb.codice_esegue(risposta, "def unisci", mb.DRIVER_INTERVALLI)[0])

    def test_un_accento_nel_codice_non_diventa_un_syntax_error(self):
        """Su Windows il file veniva scritto con la codifica locale: un `è` in un
        commento produceva un byte 0xf2 e il codice non si poteva nemmeno
        importare, bocciando una risposta giusta."""
        codice = ("# conversione per l'utente: è solo un commento\n"
                  "def unisci(intervalli):\n"
                  "    return sorted(intervalli)\n")
        ok, _nota = mb.codice_esegue(codice, "def unisci", "print('CODICE-OK')\n",
                                     tempfile.mktemp(suffix=".py"))
        self.assertTrue(ok)




class StreamTests(unittest.TestCase):
    def test_uno_stream_normale_si_chiude_con_done(self):
        testo, limite = mb.consume_stream([_riga("ciao"), "data: [DONE]\n\n"], 100)
        self.assertEqual((testo, limite), ("ciao", "ok"))

    def test_sforare_il_budget_e_loop(self):
        testo, limite = mb.consume_stream([_riga("x " * 40)], 10)
        self.assertEqual(limite, "loop")
        self.assertTrue(testo, "il testo raccolto finora va restituito, non buttato")

    def test_le_righe_non_json_si_ignorano(self):
        testo, limite = mb.consume_stream(["event: ping\n", _riga("ok"), "data: [DONE]\n\n"], 100)
        self.assertEqual((testo, limite), ("ok", "ok"))

    def test_uno_stream_chiuso_senza_done_restituisce_comunque_il_testo(self):
        testo, limite = mb.consume_stream([_riga("troncato")], 100)
        self.assertEqual((testo, limite), ("troncato", "ok"))


class RichiestaTests(unittest.TestCase):
    def test_ask_manda_think_solo_se_richiesto(self):
        class FakeRisposta:
            def __init__(self, righe):
                self._righe = iter([r.encode() for r in righe])

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                return self

            def __next__(self):
                return next(self._righe)

        catturati = []

        def opener(richiesta, timeout=0):
            catturati.append(json.loads(richiesta.data.decode()))
            return FakeRisposta([_riga("ok"), "data: [DONE]\n\n"])

        mb.ask("m::macbook", "domanda", max_tok=40, cp="http://cp", opener=opener)
        mb.ask("m::macbook", "domanda", max_tok=40, cp="http://cp", think=False, opener=opener)

        self.assertNotIn("think", catturati[0], "senza richiesta esplicita il flag non va mandato")
        self.assertIs(catturati[1]["think"], False)
        self.assertEqual(catturati[0]["model"], "m::macbook")
        self.assertIs(catturati[0]["stream"], True)


class NuoviGiudiciTests(unittest.TestCase):
    """Testa le nuove sonde introdotte per l'audit empirico di HyperSpace."""

    def test_giudice_no_e(self):
        # Frase valida senza 'e' o 'E'
        ok, nota = mb.giudice_no_e("Oggi fa tanto caldo a Roma.")
        self.assertTrue(ok)
        self.assertIn("nessuna lettera", nota)

        # Contiene 'e'
        ok, nota = mb.giudice_no_e("Oggi il tempo e' sereno.")
        self.assertFalse(ok)
        self.assertIn("contiene la lettera 'e'", nota)

        # Frase troppo corta
        ok, nota = mb.giudice_no_e("No.")
        self.assertFalse(ok)
        self.assertIn("troppo corta", nota)

    def test_giudice_json_puro(self):
        # JSON puro senza markdown o testo extra
        ok, _nota = mb.giudice_json_puro('{"temperatura": 22, "stato": "sole"}')
        self.assertTrue(ok)

        # Fallisce se incapsulato in triple backtick markdown
        ok, nota = mb.giudice_json_puro('```json\n{"temperatura": 22, "stato": "sole"}\n```')
        self.assertFalse(ok)
        self.assertIn("markdown", nota)

        # Fallisce se accompagnato da chatter/preamboli
        ok, nota = mb.giudice_json_puro('Certamente! Ecco il JSON: {"temperatura": 22, "stato": "sole"}')
        self.assertFalse(ok)
        self.assertIn("chatter", nota)

        # Fallisce se mancano chiavi
        ok, nota = mb.giudice_json_puro('{"temperatura": 22}')
        self.assertFalse(ok)
        self.assertIn("mancano", nota)

    def test_giudice_tool_call(self):
        # Tool call corretta
        valida = '{"name": "leggi_file", "arguments": {"percorso": "docs/manuale.md"}}'
        ok, _nota = mb.giudice_tool_call(valida)
        self.assertTrue(ok)

        # Nome errato
        err_nome = '{"name": "apri_file", "arguments": {"percorso": "docs/manuale.md"}}'
        ok, nota = mb.giudice_tool_call(err_nome)
        self.assertFalse(ok)
        self.assertIn("nome", nota)

        # Parametri errati
        err_args = '{"name": "leggi_file", "arguments": {"percorso": "sbagliato.txt"}}'
        ok, nota = mb.giudice_tool_call(err_args)
        self.assertFalse(ok)
        self.assertIn("argomenti", nota)

        # Con preambolo discorsivo
        con_chatter = f"Chiamo il tool: {valida}"
        ok, _nota = mb.giudice_tool_call(con_chatter)
        self.assertFalse(ok)

    def test_giudice_bulloni(self):
        # 5 minuti corretto
        self.assertTrue(mb.giudice_bulloni("Impiegano sempre 5 minuti.")[0])
        self.assertTrue(mb.giudice_bulloni("5")[0])

        # Errore tipico di euristica fallace (100)
        self.assertFalse(mb.giudice_bulloni("Impiegano 100 minuti.")[0])
        self.assertFalse(mb.giudice_bulloni("100")[0])


class StreamResultETelemetriaTests(unittest.TestCase):
    def test_stream_result_retrocompatibile_e_telemetria(self):
        res = mb.consume_stream([_riga("uno "), _riga("due "), "data: [DONE]\n\n"], 50)
        # Scompattamento tupla a 2 elementi
        testo, limite = res
        self.assertEqual(testo, "uno due")
        self.assertEqual(limite, "ok")
        self.assertEqual(len(res), 2)

        # Proprietà telemetria
        self.assertIsInstance(res, mb.StreamResult)
        self.assertGreaterEqual(res.ttft, 0.0)
        self.assertGreaterEqual(res.tok_s, 0.0)
        self.assertEqual(res.n_tokeni, 2)
        self.assertIn("elapsed", res.stats)


class ProfilazioneERuoliTests(unittest.TestCase):
    def test_sonde_attive_filtra_per_categoria(self):
        tutte = mb.sonde_attive()
        self.assertEqual(len(tutte), len(mb.PROBE))

        solo_coding = mb.sonde_attive(["coding"])
        nomi_coding = {s[0] for s in solo_coding}
        self.assertEqual(nomi_coding, set(mb.CATEGORIE_SONDE["coding"]))

    def test_profila_modello_raccomanda_ruoli(self):
        # Simuliamo risultati di un coder perfetto
        righe_coder = {}
        for nome, _, _, _, _ in mb.PROBE:
            is_coding = nome in mb.CATEGORIE_SONDE["coding"]
            is_format = nome in mb.CATEGORIE_SONDE["strict_format"]
            ok = is_coding or is_format
            righe_coder[nome] = {
                "ok": ok,
                "limite": "ok",
                "stats": {"tok_s": 45.0, "ttft": 0.2}
            }

        profilo = mb.profila_modello(righe_coder)
        self.assertIn("coder", profilo["recommended_roles"])
        self.assertIn("tool_calling", profilo["recommended_roles"])
        self.assertIn("fast_router", profilo["recommended_roles"])
        self.assertEqual(profilo["avg_tok_s"], 45.0)

    def test_profila_modello_fallback_chat_only(self):
        # Modello che fallisce tutto
        righe_flop = {
            nome: {"ok": False, "limite": "ok", "stats": {"tok_s": 5.0, "ttft": 1.5}}
            for nome, _, _, _, _ in mb.PROBE
        }
        profilo = mb.profila_modello(righe_flop)
        self.assertEqual(profilo["recommended_roles"], ["chat_only"])


class ParserTests(unittest.TestCase):
    def test_parser_argomenti_nuovi(self):
        p = mb.build_parser()
        args = p.parse_args(["--category", "coding", "--export-profile", "/tmp/cap.json"])
        self.assertEqual(args.category, "coding")
        self.assertEqual(args.export_profile, "/tmp/cap.json")


if __name__ == "__main__":
    unittest.main()
