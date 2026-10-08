# SPDX-License-Identifier: Apache-2.0
"""Bridge ONLYOFFICE — Fase C (`/office/*`): logica pura e gate di accesso.

Due livelli, come per gli altri moduli misti del repo:

* la logica deterministica vive in `shared/office_bridge.py` ed e' testabile
  senza modello ne' rete: tassonomia degli eventi, validazione dell'envelope,
  costruzione dei prompt e normalizzazione dell'output;
* le route `/office/*` vivono in `control-plane/main.py` e si provano estraendo
  le funzioni con `ast` e montandole su una Flask di test (stesso metodo di
  tests/test_runtime_recovery.py). Importare `main.py` tirerebbe dentro l'avvio
  del processo; qui serve solo il pezzo sotto esame.

Il contratto che questi test difendono e' **fail-closed**: senza
`OFFICE_BRIDGE_ENABLED=true` e un token di almeno 32 caratteri nessuna richiesta
arriva al modello, e l'autorizzazione PRECEDE la validazione — un payload
malformato con token sbagliato risponde 401, non 400, perche' a chi non e'
autorizzato non si descrive la forma interna.
"""
import ast
import types
import unittest
from pathlib import Path
from unittest.mock import Mock
from tests import cp_source

from flask import Flask, jsonify, request

from shared import office_bridge
from shared.network_security import token_authorized

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "control-plane" / "main.py"

TOKEN = "office-token-" + "x" * 24          # 37 caratteri: oltre la soglia
HEADER = "X-Hyperspace-Office-Token"
EVENT_FOR = {
    "/office/summarize": "document.summary_requested",
    "/office/rewrite": "document.rewrite_requested",
    "/office/extract-actions": "document.action_items_requested",
    "/office/classify": "document.selection_analyzed",
}
ROUTES = ("office_summarize", "office_rewrite", "office_extract_actions",
          "office_classify", "office_status")
HELPERS = ("_office_model", "_office_auth_error", "_office_error",
           "_office_infer", "_office_handle")
OPTIONS_FOR = {"document.selection_analyzed": {"taxonomy": ["budget", "risorse"]}}


def envelope(event="document.summary_requested", **overrides):
    """Envelope di richiesta valido, con override per i casi limite."""
    payload = {
        "event": event,
        "document": {"id": "doc-1", "type": "text", "title": "Verbale"},
        "selection": {"text": "Il progetto procede. Serve approvare il budget.",
                      "range": None},
        "context": {"user": "marco", "workspace": None},
        "options": dict(OPTIONS_FOR.get(event, {})),
    }
    payload.update(overrides)
    return payload


def completion(testo):
    """Finta risposta di /v1/chat/completions con il testo del modello."""
    risposta = Mock()
    risposta.raise_for_status.return_value = None
    risposta.json.return_value = {"choices": [{"message": {"content": testo}}]}
    return risposta


class EnvelopeTests(unittest.TestCase):
    def test_eventi_mappati_sugli_agenti(self):
        self.assertEqual(office_bridge.EVENTS, {
            "document.summary_requested": "summarizer",
            "document.rewrite_requested": "rewriter",
            "document.action_items_requested": "planner",
            "document.selection_analyzed": "classifier"})
        self.assertTrue(office_bridge.is_supported("document.summary_requested"))
        self.assertFalse(office_bridge.is_supported("document.exploded"))
        self.assertIsNone(office_bridge.agent_for("document.exploded"))

    def test_envelope_valido_viene_normalizzato(self):
        valido, errore = office_bridge.validate_request(
            envelope(selection={"text": "  Il progetto procede.  ", "range": [1, 5]}))
        self.assertIsNone(errore)
        self.assertEqual(valido["agent"], "summarizer")
        self.assertEqual(valido["document"],
                         {"id": "doc-1", "type": "text", "title": "Verbale"})
        self.assertEqual(valido["selection"]["text"], "Il progetto procede.")
        self.assertEqual(valido["selection"]["range"], [1, 5])
        self.assertEqual(valido["context"], {"user": "marco", "workspace": None})
        self.assertEqual(valido["options"], {"length": "medium"})

    def test_envelope_malformati_vengono_rifiutati(self):
        casi = [
            (None, "envelope non valido"),
            ("testo", "envelope non valido"),
            ({}, "campo 'event' mancante"),
            ({"event": "   "}, "campo 'event' mancante"),
            ({"event": "document.fatto_male"}, "evento non supportato"),
            (envelope(document="doc"), "campo 'document' non valido"),
            (envelope(document={"type": "foglio"}), "tipo documento non valido"),
            (envelope(selection=None), "campo 'selection' mancante"),
            (envelope(selection={"text": "   "}), "campo 'selection.text' vuoto"),
            (envelope(context="x"), "campo 'context' non valido"),
            (envelope(options="x"), "campo 'options' non valido"),
            (envelope(selection={"text": "a" * (office_bridge.MAX_DOCUMENT_CHARS + 1)}),
             "selection troppo lunga"),
        ]
        for payload, atteso in casi:
            with self.subTest(atteso=atteso):
                valido, errore = office_bridge.validate_request(payload)
                self.assertIsNone(valido)
                self.assertIn(atteso, errore)


class OpzioniTests(unittest.TestCase):
    """Le opzioni evento-specifiche: default del design doc o errore esplicito."""

    def test_summary_length(self):
        _, errore = office_bridge.validate_request(envelope(options={"length": "epico"}))
        self.assertIn("'length' non valida", errore)
        valido, _ = office_bridge.validate_request(envelope(options={"length": "SHORT"}))
        self.assertEqual(valido["options"], {"length": "short"})

    def test_rewrite_style_e_lingua(self):
        _, errore = office_bridge.validate_request(
            envelope("document.rewrite_requested", options={"style": "poetico"}))
        self.assertIn("'style' non valida", errore)
        valido, _ = office_bridge.validate_request(
            envelope("document.rewrite_requested",
                     options={"style": "formal", "target_language": " inglese "}))
        self.assertEqual(valido["options"],
                         {"style": "formal", "target_language": "inglese"})

    def test_assignees_hint_coercizione(self):
        for grezzo, atteso in (("true", True), ("no", False), ("", False),
                               (True, True), (False, False)):
            with self.subTest(grezzo=grezzo):
                valido, _ = office_bridge.validate_request(
                    envelope("document.action_items_requested",
                             options={"assignees_hint": grezzo}))
                self.assertIs(valido["options"]["assignees_hint"], atteso)

    def test_taxonomy_obbligatoria_deduplicata_e_limitata(self):
        _, errore = office_bridge.validate_request(
            envelope("document.selection_analyzed", options={}))
        self.assertIn("'taxonomy' mancante", errore)
        _, errore = office_bridge.validate_request(
            envelope("document.selection_analyzed", options={"taxonomy": ["  ", ""]}))
        self.assertIn("'taxonomy' vuota", errore)
        valido, _ = office_bridge.validate_request(
            envelope("document.selection_analyzed",
                     options={"taxonomy": ["Budget", "budget", "RISORSE"]}))
        self.assertEqual(valido["options"]["taxonomy"], ["Budget", "RISORSE"])
        troppe = [f"voce-{i}" for i in range(office_bridge.MAX_OPTION_ITEMS + 1)]
        _, errore = office_bridge.validate_request(
            envelope("document.selection_analyzed", options={"taxonomy": troppe}))
        self.assertIn("'taxonomy' troppo lunga", errore)


class PromptTests(unittest.TestCase):
    def _valido(self, event, options=None):
        valido, errore = office_bridge.validate_request(
            envelope(event, options=options if options is not None else {}))
        self.assertIsNone(errore)
        return valido

    def test_ogni_evento_produce_system_e_user_col_testo(self):
        for event in office_bridge.EVENTS:
            with self.subTest(event=event):
                opzioni = OPTIONS_FOR.get(event, {})
                valido = self._valido(event, opzioni)
                messaggi = office_bridge.build_messages(event, valido)
                self.assertEqual([m["role"] for m in messaggi], ["system", "user"])
                self.assertIn(valido["selection"]["text"], messaggi[1]["content"])

    def test_il_prompt_porta_il_vincolo_scelto(self):
        riassunto = office_bridge.build_messages(
            "document.summary_requested", self._valido("document.summary_requested",
                                                        {"length": "short"}))
        self.assertIn("2-3 frasi", riassunto[1]["content"])

        riscrittura = office_bridge.build_messages(
            "document.rewrite_requested",
            self._valido("document.rewrite_requested",
                         {"style": "concise", "target_language": "inglese"}))
        self.assertIn("conciso", riscrittura[1]["content"])
        self.assertIn("Traduci in inglese.", riscrittura[1]["content"])

        azioni = office_bridge.build_messages(
            "document.action_items_requested",
            self._valido("document.action_items_requested", {"assignees_hint": True}))
        self.assertIn("responsabile", azioni[1]["content"])

        classifica = office_bridge.build_messages(
            "document.selection_analyzed",
            self._valido("document.selection_analyzed", {"taxonomy": ["budget", "risorse"]}))
        self.assertIn("budget, risorse", classifica[0]["content"])

    def test_evento_sconosciuto_solleva_invece_di_prompt_vuoto(self):
        with self.assertRaises(ValueError):
            office_bridge.build_messages("document.exploded",
                                         {"selection": {"text": "x"}, "options": {}})



class NormalizzazioneTests(unittest.TestCase):
    """La risposta del modello diventa `output` nell'envelope, senza trucchi."""

    def test_action_items_diventano_checklist_markdown(self):
        testo = "1. Approvare il budget\n• Contattare il fornitore\n- [x] Già fatto\n\n"
        output = office_bridge.normalize_output(
            "document.action_items_requested", testo, {})
        self.assertEqual(output["format"], "markdown")
        self.assertEqual(output["text"].splitlines(),
                         ["- [ ] Approvare il budget",
                          "- [ ] Contattare il fornitore",
                          "- [x] Già fatto"])

    def test_checklist_vuota_resta_vuota(self):
        self.assertEqual(
            office_bridge.normalize_output("document.action_items_requested", "", {}),
            {"text": "", "format": "markdown"})

    def test_classify_tiene_solo_le_etichette_della_taxonomy(self):
        output = office_bridge.normalize_output(
            "document.selection_analyzed", "budget\n- inventata\n1. RISORSE\nbudget",
            {"taxonomy": ["budget", "Risorse"]})
        self.assertEqual(output, {"text": "budget\nRisorse", "format": "plain"})

    def test_classify_fuori_lista_restituisce_la_risposta_grezza(self):
        output = office_bridge.normalize_output(
            "document.selection_analyzed", "fuori tema", {"taxonomy": ["budget"]})
        self.assertEqual(output, {"text": "fuori tema", "format": "plain"})

    def test_summary_e_rewrite_sono_testo_semplice(self):
        for event in ("document.summary_requested", "document.rewrite_requested"):
            with self.subTest(event=event):
                self.assertEqual(office_bridge.normalize_output(event, "  ciao  ", {}),
                                 {"text": "ciao", "format": "plain"})


class DescribeTests(unittest.TestCase):
    def test_describe_e_diagnostica_senza_segreti(self):
        descrizione = office_bridge.describe()
        self.assertEqual(descrizione["supported_events"], office_bridge.EVENTS)
        self.assertIn("text", descrizione["document_types"])
        self.assertEqual(descrizione["max_document_chars"],
                         office_bridge.MAX_DOCUMENT_CHARS)
        self.assertEqual(descrizione["max_taxonomy_labels"],
                         office_bridge.MAX_OPTION_ITEMS)
        self.assertEqual([k for k in descrizione if "token" in k.lower()], [])



class BridgeHarness:
    """Le funzioni `/office/*` di main.py montate su una Flask di test.

    `os` e' un finto modulo: `_office_model()` legge `HS_MODEL_GENERAL`, e senza
    questa iniezione l'esito del test dipenderebbe dall'ambiente di chi lo
    esegue (una HS_MODEL_GENERAL valorizzata cambierebbe il modello scelto).
    """

    def __init__(self):
        self.app = Flask("office-test")
        self.model_post = Mock()
        self.log = Mock()
        self.env = {}
        self.scope = {
            "app": self.app, "request": request, "jsonify": jsonify,
            "os": types.SimpleNamespace(
                getenv=lambda chiave, default="": self.env.get(chiave, default)),
            "office_bridge": office_bridge,
            "requests": Mock(post=self.model_post),
            "token_authorized": token_authorized,
            "OFFICE_BRIDGE_ENABLED": True,
            "OFFICE_BRIDGE_TOKEN": TOKEN,
            "_OFFICE_TOKEN_HEADER": HEADER,
            "OFFICE_MODEL": "modello-office",
            "DEFAULT_MODEL": "modello-default",
            "advanced_config": {"ollama": {"defaultModel": ""}},
            "_channel_int": lambda chiave, default: default,
            "_inference_timeout": lambda modello: 30,
            "push_log": self.log,
        }
        nodi = [n for n in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                if isinstance(n, ast.FunctionDef) and n.name in ROUTES + HELPERS]
        mancanti = set(ROUTES + HELPERS) - {n.name for n in nodi}
        if mancanti:
            raise AssertionError(
                f"funzioni sparite da control-plane/main.py: {sorted(mancanti)}")
        exec(compile(ast.Module(body=nodi, type_ignores=[]), str(SOURCE), "exec"),
             self.scope)
        self.client = self.app.test_client()

    def risponde(self, testo="testo del modello"):
        self.model_post.return_value = completion(testo)
        return self

    def chiama(self, path, payload=None, token=TOKEN):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers[HEADER] = token
        body = envelope(EVENT_FOR[path]) if payload is None else payload
        return self.client.post(path, json=body, headers=headers)

    def invio(self):
        """I kwargs dell'ultima POST al modello (headers/json/timeout)."""
        return self.model_post.call_args.kwargs

    def prompt_utente(self):
        return self.invio()["json"]["messages"][1]["content"]


class GateTests(unittest.TestCase):
    """Fail-closed: senza gate nessuna richiesta tocca il modello."""

    def setUp(self):
        self.bridge = BridgeHarness()

    def test_spento_risponde_503_senza_chiamare_il_modello(self):
        self.bridge.scope["OFFICE_BRIDGE_ENABLED"] = False
        risposta = self.bridge.chiama("/office/summarize")
        self.assertEqual(risposta.status_code, 503)
        corpo = risposta.get_json()
        self.assertEqual(corpo["status"], "error")
        self.assertIsNone(corpo["output"]["text"])
        self.assertIsNone(corpo["output"]["format"])
        self.bridge.model_post.assert_not_called()

    def test_token_troppo_corto_risponde_503(self):
        self.bridge.scope["OFFICE_BRIDGE_TOKEN"] = "corto"
        self.assertEqual(self.bridge.chiama("/office/summarize").status_code, 503)
        self.bridge.model_post.assert_not_called()

    def test_token_assente_o_sbagliato_risponde_401(self):
        for token in (None, "", "sbagliato", TOKEN + "x"):
            with self.subTest(token=token):
                risposta = self.bridge.chiama("/office/summarize", token=token)
                self.assertEqual(risposta.status_code, 401)
        self.bridge.model_post.assert_not_called()

    def test_l_autorizzazione_precede_la_validazione(self):
        """Envelope malformato + token sbagliato = 401: non 400."""
        risposta = self.bridge.chiama("/office/summarize",
                                      payload={"event": "x"}, token="sbagliato")
        self.assertEqual(risposta.status_code, 401)

    def test_i_quattro_endpoint_condividono_lo_stesso_gate(self):
        self.bridge.scope["OFFICE_BRIDGE_ENABLED"] = False
        for path in EVENT_FOR:
            with self.subTest(path=path):
                self.assertEqual(self.bridge.chiama(path).status_code, 503)
        self.bridge.model_post.assert_not_called()



class RichiestaTests(unittest.TestCase):
    """Envelope rifiutato, evento incoerente, modello assente o in errore."""

    def setUp(self):
        self.bridge = BridgeHarness()

    def test_envelope_invalido_risponde_400_con_agente(self):
        risposta = self.bridge.chiama(
            "/office/summarize", payload={"event": "document.summary_requested"})
        self.assertEqual(risposta.status_code, 400)
        corpo = risposta.get_json()
        self.assertEqual(corpo["status"], "error")
        self.assertEqual(corpo["agent"], "summarizer")
        self.assertIn("selection", corpo["error"])
        self.bridge.model_post.assert_not_called()

    def test_corpo_non_json_risponde_400(self):
        risposta = self.bridge.client.post("/office/summarize", data="non-json",
                                          content_type="text/plain",
                                          headers={HEADER: TOKEN})
        self.assertEqual(risposta.status_code, 400)

    def test_evento_dichiarato_diverso_dall_endpoint(self):
        risposta = self.bridge.chiama(
            "/office/summarize", payload=envelope("document.rewrite_requested"))
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("diverso dall'endpoint", risposta.get_json()["error"])
        self.bridge.model_post.assert_not_called()

    def test_opzione_non_valida_risponde_400(self):
        risposta = self.bridge.chiama(
            "/office/summarize",
            payload=envelope(options={"length": "epico"}))
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("'length' non valida", risposta.get_json()["error"])
        self.bridge.model_post.assert_not_called()

    def test_nessun_modello_configurato_risponde_503(self):
        self.bridge.scope["OFFICE_MODEL"] = ""
        self.bridge.scope["DEFAULT_MODEL"] = ""
        self.assertEqual(self.bridge.chiama("/office/summarize").status_code, 503)
        self.bridge.model_post.assert_not_called()

    def test_modello_non_disponibile_risponde_502_e_logga(self):
        self.bridge.model_post.side_effect = RuntimeError("connection refused")
        risposta = self.bridge.chiama("/office/summarize")
        self.assertEqual(risposta.status_code, 502)
        corpo = risposta.get_json()
        self.assertEqual(corpo["status"], "error")
        self.assertEqual(corpo["agent"], "summarizer")
        self.assertIn("RuntimeError", corpo["error"])
        self.assertEqual(self.bridge.log.call_args.kwargs["status"], "error")

    def test_risposta_vuota_del_modello_risponde_502(self):
        self.bridge.risponde("   ")
        risposta = self.bridge.chiama("/office/summarize")
        self.assertEqual(risposta.status_code, 502)
        self.assertIn("RuntimeError", risposta.get_json()["error"])



class RispostaOkTests(unittest.TestCase):
    """Il percorso felice: un giro, una chiamata, un log, un envelope."""

    def setUp(self):
        self.bridge = BridgeHarness()

    def test_summarize_chiama_il_modello_una_volta_e_logga(self):
        self.bridge.risponde("Il progetto procede; serve approvare il budget.")
        risposta = self.bridge.chiama("/office/summarize")
        self.assertEqual(risposta.status_code, 200)
        corpo = risposta.get_json()
        self.assertEqual(corpo["status"], "ok")
        self.assertEqual(corpo["agent"], "summarizer")
        self.assertEqual(corpo["output"],
                         {"text": "Il progetto procede; serve approvare il budget.",
                          "format": "plain"})
        self.assertIsNone(corpo["error"])

        self.assertEqual(self.bridge.model_post.call_count, 1)
        invio = self.bridge.invio()
        self.assertTrue(self.bridge.model_post.call_args.args[0]
                        .endswith("/v1/chat/completions"))
        self.assertEqual(invio["headers"]["X-Hyperspace-Surface"], "office")
        self.assertEqual(invio["headers"]["X-Hyperspace-Tools"], "off")
        self.assertEqual(invio["json"]["model"], "modello-office")
        self.assertIs(invio["json"]["stream"], False)
        self.assertIs(invio["json"]["think"], False)
        self.assertIn("num_ctx", invio["json"]["options"])
        self.assertEqual([m["role"] for m in invio["json"]["messages"]],
                         ["system", "user"])
        self.assertGreater(invio["timeout"], 0)

        self.assertEqual(self.bridge.log.call_count, 1)
        self.assertEqual(self.bridge.log.call_args.args[0], "office")
        self.assertEqual(self.bridge.log.call_args.kwargs["source"],
                         "office:summarizer")
        self.assertEqual(self.bridge.log.call_args.kwargs["status"], "success")

    def test_rewrite_rispetta_stile_e_lingua_scelti(self):
        self.bridge.risponde("In English, concisely.")
        risposta = self.bridge.chiama(
            "/office/rewrite",
            payload=envelope("document.rewrite_requested",
                             options={"style": "concise",
                                      "target_language": "inglese"}))
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.get_json()["agent"], "rewriter")
        prompt = self.bridge.prompt_utente()
        self.assertIn("conciso", prompt)
        self.assertIn("Traduci in inglese.", prompt)

    def test_extract_actions_produce_checklist_markdown(self):
        self.bridge.risponde("1. Approvare il budget\n2. Contattare il fornitore")
        risposta = self.bridge.chiama("/office/extract-actions")
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.get_json()["agent"], "planner")
        self.assertEqual(risposta.get_json()["output"],
                         {"text": "- [ ] Approvare il budget\n"
                                  "- [ ] Contattare il fornitore",
                          "format": "markdown"})

    def test_classify_scarta_le_etichette_fuori_taxonomy(self):
        self.bridge.risponde("budget\netichetta-inventata")
        risposta = self.bridge.chiama("/office/classify", payload=envelope(
            "document.selection_analyzed", options={"taxonomy": ["budget", "risorse"]}))
        self.assertEqual(risposta.status_code, 200)
        self.assertEqual(risposta.get_json()["agent"], "classifier")
        self.assertEqual(risposta.get_json()["output"],
                         {"text": "budget", "format": "plain"})
        self.assertIn("budget, risorse", self.bridge.invio()["json"]["messages"][0]["content"])

    def test_il_modello_si_risolve_per_office_generale_default(self):
        def modello():
            return self.bridge.scope["_office_model"]()

        self.assertEqual(modello(), "modello-office")
        self.bridge.scope["OFFICE_MODEL"] = ""
        self.assertEqual(modello(), "modello-default")
        self.bridge.env["HS_MODEL_GENERAL"] = "modello-generale"
        self.assertEqual(modello(), "modello-generale")
        self.bridge.scope["advanced_config"]["ollama"]["defaultModel"] = "modello-avanzato"
        self.bridge.env.clear()
        self.assertEqual(modello(), "modello-avanzato")



class StatusRouteTests(unittest.TestCase):
    """`GET /office/status`: diagnostica leggibile anche a bridge spento."""

    def test_status_espone_la_diagnostica_senza_il_token(self):
        bridge = BridgeHarness()
        risposta = bridge.client.get("/office/status")
        self.assertEqual(risposta.status_code, 200)
        corpo = risposta.get_json()
        self.assertTrue(corpo["ok"])
        self.assertTrue(corpo["enabled"])
        self.assertTrue(corpo["token_configured"])
        self.assertEqual(corpo["model"], "modello-office")
        self.assertEqual(corpo["supported_events"], office_bridge.EVENTS)
        self.assertNotIn(TOKEN, risposta.get_data(as_text=True))

    def test_status_resta_leggibile_a_bridge_spento(self):
        bridge = BridgeHarness()
        bridge.scope["OFFICE_BRIDGE_ENABLED"] = False
        bridge.scope["OFFICE_BRIDGE_TOKEN"] = ""
        corpo = bridge.client.get("/office/status").get_json()
        self.assertTrue(corpo["ok"])
        self.assertFalse(corpo["enabled"])
        self.assertFalse(corpo["token_configured"])

    def test_gli_endpoint_dei_task_non_accettano_get(self):
        bridge = BridgeHarness()
        for path in EVENT_FOR:
            with self.subTest(path=path):
                self.assertEqual(bridge.client.get(path).status_code, 405)


class DashboardWiringTests(unittest.TestCase):
    """Le tre chiavi del bridge: dichiarate, applicate a caldo, documentate.

    La stessa classe di difetto che difende tests/test_config_runtime.py: una
    chiave scritta nella tab Setup che nessuno riapplica al processo resta nel
    `.env` e non cambia nulla fino al riavvio ("salvato ma inerte"). Qui la
    verifica e' strutturale, senza importare Flask.
    """

    @classmethod
    def setUpClass(cls):
        cls.tree = cp_source.albero()
        cls.funzioni = {n.name: n for n in cls.tree.body
                        if isinstance(n, ast.FunctionDef)}
        cls.meta = next(ast.literal_eval(n.value) for n in cls.tree.body
                        if isinstance(n, ast.Assign)
                        and getattr(n.targets[0], "id", "") == "_ENV_META")
        cls.chiavi = ("OFFICE_BRIDGE_ENABLED", "OFFICE_BRIDGE_TOKEN", "HS_MODEL_OFFICE")

    def test_le_tre_chiavi_sono_nella_tab_setup(self):
        sezione = {m["key"] for m in self.meta
                   if m["section"] == "Ufficio (ONLYOFFICE bridge)"}
        self.assertEqual(sezione, set(self.chiavi))

    def test_il_token_non_si_mostra_in_chiaro(self):
        tipi = {m["key"]: m["type"] for m in self.meta}
        self.assertEqual(tipi["OFFICE_BRIDGE_TOKEN"], "password")

    def test_ogni_chiave_viene_applicata_a_caldo(self):
        applicatore = self.funzioni["_apply_env_runtime"]
        fonte = ast.unparse(applicatore)
        globali = {nome for nodo in ast.walk(applicatore)
                   if isinstance(nodo, ast.Global) for nome in nodo.names}
        # HS_MODEL_OFFICE e' il nome nel .env; la costante globale e' OFFICE_MODEL.
        attesi = {"OFFICE_BRIDGE_ENABLED": "OFFICE_BRIDGE_ENABLED",
                  "OFFICE_BRIDGE_TOKEN": "OFFICE_BRIDGE_TOKEN",
                  "HS_MODEL_OFFICE": "OFFICE_MODEL"}
        for chiave, globale in attesi.items():
            with self.subTest(chiave=chiave):
                self.assertIn(f"key == '{chiave}'", fonte)
                self.assertIn(globale, globali)

    def test_la_dashboard_legge_il_valore_a_runtime(self):
        getter = next(n for n in self.tree.body if isinstance(n, ast.Assign)
                      and getattr(n.targets[0], "id", "") == "_ENV_RUNTIME_GET")
        chiavi = {k.value for k in getter.value.keys}
        for chiave in self.chiavi:
            with self.subTest(chiave=chiave):
                self.assertIn(chiave, chiavi)

    def test_il_tipo_di_log_office_e_dichiarato(self):
        """Senza il tipo in LOG_TYPES i log del bridge diventano 'system'."""
        tipi = next(ast.literal_eval(n.value) for n in self.tree.body
                    if isinstance(n, ast.Assign)
                    and getattr(n.targets[0], "id", "") == "LOG_TYPES")
        self.assertIn("office", tipi)

    def test_le_chiavi_sono_documentate_in_env_example(self):
        esempio = (ROOT / ".env.example").read_text(encoding="utf-8")
        for chiave in self.chiavi:
            with self.subTest(chiave=chiave):
                self.assertIn(chiave, esempio)


if __name__ == "__main__":
    unittest.main()
