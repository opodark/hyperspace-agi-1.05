# SPDX-License-Identifier: Apache-2.0
"""La superficie locale per REA (`scripts/rea_surface.py`).

Quattro cose si rompono in silenzio, e questo test le tiene ferme:

  - una rotta che accetta un percorso scelto dal client: il target deve restare
    la copia dentro `data/rea/jobs/<id>/target/`;
  - un'operazione in piu' fra quelle esposte: `setup`, `update`, `uninstall`,
    `import-reference-source` e le operazioni runtime non devono comparire in
    `OPERAZIONI` ne' in una rotta;
  - un lavoro nativo che parte senza provider, dove l'auto-selezione di REA puo'
    avviare Hopper da sola;
  - il report che perde una delle tre corsie (osservato / riferito / limiti) e
    diventa un verdetto invece di una lettura.

REA non e' installato su questa macchina e questi test non provano a
installarlo: usano un finto `rea` scritto in una directory temporanea (uno
script che stampa il documento e esce) oppure chiamano la riduzione su un
documento scritto a mano.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests import cp_source

from scripts import rea_surface as ras

ROOT = Path(__file__).resolve().parents[1]
SORGENTE = (ROOT / "scripts" / "rea_surface.py").read_text(encoding="utf-8")


def finto_rea(cartella: Path, corpo: str) -> Path:
    """Un `rea` finto: uno script eseguibile che risponde come decidiamo noi."""
    percorso = cartella / "rea"
    percorso.write_text("#!/bin/sh\n" + corpo, encoding="utf-8")
    percorso.chmod(0o755)
    return percorso


VERSIONE_FINTA = 'if [ "$1" = "--version" ]; then echo "rea 0.0.0-finto"; exit 0; fi\n'

DOCUMENTO = {
    "target": {"kind": "javascript-application", "path": "app.asar"},
    "modules": [{"id": "a", "label": "index.js"}, {"id": "b", "label": "preload.js"}],
    "coverage": {"percent": 42},
    "artifact_digest": "sha256:" + "ab" * 32,
}


class PerimetroTests(unittest.TestCase):
    """Il perimetro: loopback, niente shell, nessun comando fuori whitelist."""

    def test_solo_loopback(self):
        self.assertEqual(ras.HOST, "127.0.0.1")
        # assertTrue e non assertNotIn: se fallisce, il messaggio stamperebbe
        # l'intero sorgente del modulo.
        self.assertTrue("0.0.0.0" not in SORGENTE,
                        "nessuna stringa di questo file puo' bindare il wildcard")

    def test_niente_shell_ne_interpolazione(self):
        for vietato in ("shell=True", "os.system", "os.popen", "eval(", "exec(",
                        "shlex", "subprocess.call"):
            with self.subTest(vietato=vietato):
                self.assertNotIn(vietato, SORGENTE)

    def test_un_solo_subprocess_run_e_solo_per_la_versione(self):
        """`run` sta in `rea_version`; il lavoro vero passa da `Popen` con argv."""
        chiamate = [n for n in ast.walk(ast.parse(SORGENTE))
                    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and getattr(n.func.value, "id", "") == "subprocess"]
        self.assertEqual(sorted(c.func.attr for c in chiamate), ["Popen", "run"])
        run = [c for c in chiamate if c.func.attr == "run"]
        self.assertEqual(len(run), 1)
        self.assertEqual(run[0].args[0].elts[0].id, "binario")
        self.assertIn("VERSION_TIMEOUT_S", ast.unparse(run[0]))

    def test_le_operazioni_vietate_non_esistono_in_tabella(self):
        esposte = {op.comando for op in ras.OPERAZIONI}
        for vietato in ("setup", "update", "uninstall", "import-reference-source",
                        "capture-process", "reconcile", "browser", "electron"):
            with self.subTest(vietato=vietato):
                self.assertNotIn(vietato, esposte)
        # e l'id non deve riaprirle per un'altra strada
        for vietato in ("setup", "update", "uninstall"):
            self.assertNotIn(vietato, ras._OPS)

    def test_la_pagina_dice_che_non_installa_e_mostra_i_comandi(self):
        for aggancio in ("REA non è installato", "Osservato qui", "Riferito da REA",
                         "Limiti di questa lettura", "installa da sola",
                         "il target non viene eseguito"):
            with self.subTest(aggancio=aggancio):
                self.assertIn(aggancio, ras._PAGE)

    def test_i_limiti_dichiarano_che_non_c_e_un_verdetto(self):
        testo = " ".join(ras.LIMITI_FISSI)
        self.assertIn("Nessuna vulnerabilità è confermata qui", testo)
        self.assertIn("non è stato eseguito", testo)


class OperazioniEsposteTests(unittest.TestCase):
    """La whitelist: cosa puo' partire, e con quale argv esatto."""

    def test_ci_sono_tredici_operazioni_con_id_distinti(self):
        ids = [op.id for op in ras.OPERAZIONI]
        self.assertEqual(len(ids), 13)
        self.assertEqual(len(set(ids)), 13)
        self.assertEqual(list(ras._OPS), ids)
        for op in ras.OPERAZIONI:
            with self.subTest(op=op.id):
                self.assertTrue(op.comando and op.titolo and op.descrizione)
                self.assertIn(op.target, ("file", "nessuno"))
                self.assertIn(op.provider, ("non-serve", "opzionale", "obbligatorio"))
                self.assertIn(op.esecuzione, ("statica", "motore"))

    def test_le_operazioni_native_vogliono_un_provider_esplicito(self):
        native = [op for op in ras.OPERAZIONI if op.esecuzione == "motore"
                  and op.provider != "non-serve"]
        self.assertTrue(native)
        for op in ras.OPERAZIONI:
            with self.subTest(op=op.id):
                if op.id in ("function", "decompile", "xrefs", "instructions",
                             "search", "trace"):
                    self.assertEqual(op.provider, "obbligatorio")

    def test_argv_e_una_lista_e_il_provider_chiude_la_riga(self):
        op = ras._OPS["function"]
        argv = ras.build_argv("/bin/rea", op, Path("/tmp/x/malware.bin"), "main",
                              "hopper")
        self.assertEqual(argv, ["/bin/rea", "function", "/tmp/x/malware.bin",
                                "main", "--provider", "hopper", "--json"])
        senza = ras.build_argv("/bin/rea", ras._OPS["doctor"], None, None, None)
        self.assertEqual(senza, ["/bin/rea", "doctor", "--json"])

    def test_un_provider_non_previsto_non_entra_nell_argv(self):
        provider, errore = ras.valida_provider(ras._OPS["decompile"], "ida-9.1")
        self.assertIsNone(provider)
        self.assertIn("provider sconosciuto", errore)

    def test_nessun_argomento_diventa_un_flag(self):
        """Il testo libero non puo' iniziare con '-' e non puo' avere piu' righe."""
        op = ras._OPS["search"]
        for scarto in ("--provider ghidra", "-o /tmp/x", "due\nrighe", "x" * 201):
            with self.subTest(scarto=scarto):
                valore, errore = ras.valida_argomento(op, scarto)
                self.assertIsNone(valore)
                self.assertIsNotNone(errore)
        valore, errore = ras.valida_argomento(op, "hello world")
        self.assertEqual((valore, errore), ("hello world", None))

    def test_gli_argomenti_tipizzati_vogliono_la_loro_forma(self):
        nome, errore = ras.valida_argomento(ras._OPS["function"], "../../etc/passwd")
        self.assertIsNone(nome)
        self.assertIn("nome della funzione", errore)
        nome, errore = ras.valida_argomento(ras._OPS["function"], "parse_input")
        self.assertEqual((nome, errore), ("parse_input", None))
        buono, _ = ras.valida_argomento(ras._OPS["decompile"], "0x1f40")
        self.assertEqual(buono, "0x1f40")
        cattivo, errore = ras.valida_argomento(ras._OPS["decompile"], "1f40")
        self.assertIsNone(cattivo)
        self.assertIn("indirizzo esadecimale", errore)

    def test_dove_l_operazione_non_prende_argomenti_il_testo_e_rifiutato(self):
        valore, errore = ras.valida_argomento(ras._OPS["doctor"], "qualcosa")
        self.assertIsNone(valore)
        self.assertIn("non accetta un argomento", errore)

    def test_provider_obbligatorio_senza_provider(self):
        provider, errore = ras.valida_provider(ras._OPS["search"], "")
        self.assertIsNone(provider)
        self.assertIn("Hopper", errore)
        provider, errore = ras.valida_provider(ras._OPS["search"], "IDA")
        self.assertEqual((provider, errore), ("ida", None))
        provider, errore = ras.valida_provider(ras._OPS["providers"], "hopper")
        self.assertIsNone(provider)
        self.assertIn("non usa un provider", errore)



def attendi_record(cartella_job: Path, secondi: float = 10.0) -> dict:
    """Aspetta che il runner chiuda il libro, poi legge `job.json`."""
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        record = ras.scarica_json(cartella_job / "job.json") or {}
        if record.get("status") not in ("queued", "running"):
            return record
        time.sleep(0.05)
    ultimo = ras.scarica_json(cartella_job / "job.json")
    raise AssertionError(f"il lavoro non si e' concluso in {secondi}s: {ultimo}")


class RunnerTests(unittest.TestCase):
    """Il runner: un processo, con un tetto di tempo, in una copia del target."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cartella = Path(self.tmp.name)

    def _job(self, jobs_dir: Path, comando: list[str]) -> Path:
        job_id = "abcdef012345"
        cartella_job = jobs_dir / job_id
        (cartella_job / "target").mkdir(parents=True)
        (cartella_job / "target" / "campione.bin").write_bytes(b"MZ" + b"\0" * 64)
        ras.scrivi_json(cartella_job / "job.json", {
            "id": job_id, "op": "analyze", "titolo": "Panoramica del target",
            "status": "queued", "comando": comando,
            "target": {"nome": "campione.bin", "bytes": 66, "sha256": "0" * 64},
        })
        return cartella_job

    def _runner(self, binario: Path, jobs_dir: Path, **extra) -> ras.Runner:
        runner = ras.Runner(str(binario), jobs_dir, **extra)
        runner.start()
        self.addCleanup(runner.stop)
        return runner

    def test_un_comando_che_riesce_scrive_report_e_job(self):
        binario = finto_rea(self.cartella, VERSIONE_FINTA
                            + "echo '{\"coverage\":{\"percent\":42}}'\nexit 0\n")
        jobs_dir = self.cartella / "jobs"
        cartella_job = self._job(jobs_dir, [str(binario), "doctor", "--json"])
        runner = self._runner(binario, jobs_dir, timeout=20)
        runner.accoda({"id": "abcdef012345"})
        record = attendi_record(cartella_job)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["esito"], "completato")
        self.assertEqual(record["exit_code"], 0)
        report = ras.scarica_json(cartella_job / "report.json")
        self.assertTrue(report["riferito"]["json_valido"])
        self.assertIn(b"coverage", (cartella_job / "stdout.json").read_bytes())
        self.assertEqual(report["osservato"]["target"]["nome"], "campione.bin")
        self.assertEqual(report["osservato"]["comando"][0], str(binario))

    def test_un_comando_che_non_finisce_viene_terminato(self):
        binario = finto_rea(self.cartella, VERSIONE_FINTA + "sleep 30\n")
        jobs_dir = self.cartella / "jobs"
        cartella_job = self._job(jobs_dir, [str(binario), "analyze", "campione.bin", "--json"])
        runner = self._runner(binario, jobs_dir, timeout=1)
        inizio = time.monotonic()
        runner.accoda({"id": "abcdef012345"})
        record = attendi_record(cartella_job, secondi=20)
        durata = time.monotonic() - inizio
        self.assertEqual(record["esito"], "timeout")
        self.assertIsNone(record["exit_code"])
        self.assertLess(durata, 12, "il gruppo deve morire subito dopo il timeout")
        report = ras.scarica_json(cartella_job / "report.json")
        self.assertEqual(report["osservato"]["esito"], "timeout")

    def test_un_binario_che_non_parte_non_ferma_la_coda(self):
        jobs_dir = self.cartella / "jobs"
        cartella_job = self._job(jobs_dir, ["/niente/rea", "doctor", "--json"])
        runner = self._runner(Path("/niente/rea"), jobs_dir, timeout=5)
        runner.accoda({"id": "abcdef012345"})
        record = attendi_record(cartella_job)
        self.assertEqual(record["esito"], "non avviato")
        self.assertEqual(record["status"], "failed")

    def test_la_coda_conta_e_si_svuota(self):
        binario = finto_rea(self.cartella, VERSIONE_FINTA + "exit 0\n")
        runner = self._runner(binario, self.cartella / "jobs", timeout=5)
        self.assertTrue(runner.posti_liberi())
        runner.in_coda = ras.MAX_IN_CODA
        self.assertFalse(runner.posti_liberi())




class RiduzioneTests(unittest.TestCase):
    """Le tre corsie, sulle forme che il `rea` vero produce davvero.

    Le fixture qui sotto non sono inventate: sono i byte che REA 6.1.0 scrive
    su stdout e stderr (documento su stdout, `rea_progress` su stderr), presi
    dalla prova del 2026-10-09 con il pacchetto installato.
    """

    def _riduci(self, stdout: str, stderr: str = "", exit_code: int = 0) -> dict:
        return ras.riduci(stdout.encode(), stderr.encode(), exit_code, 0.5,
                          ["rea", "doctor", "--json"], None)

    def test_il_progresso_annidato_diventa_una_timeline_leggibile(self):
        righe = (
            '{"rea_progress":{"phase":"parse_javascript_source",'
            '"completed":0,"total":1,"message":"Parsing and projecting '
            'index.js (1/2)","sequence":4}}\n'
            '{"rea_progress":{"phase":"seal_javascript_application_graph",'
            '"completed":0,"total":1,"message":"Sealing the validated '
            'application graph","sequence":7}}\n')
        progresso = ras._progresso(righe)
        self.assertEqual(len(progresso), 2)
        self.assertEqual(progresso[0]["fase"], "parse_javascript_source")
        self.assertEqual(progresso[0]["messaggio"], "Parsing and projecting index.js (1/2)")
        self.assertEqual(progresso[1]["fase"], "seal_javascript_application_graph")
        self.assertNotIn("?", [voce["fase"] for voce in progresso])

    def test_il_progresso_e_solo_cio_che_si_dichiara_tale(self):
        """Una riga JSON senza il marcatore `rea_progress` non e' un passo."""
        progresso = ras._progresso('{"rea_progress":{"phase":"providers"}}\n'
                                   '{"rea_progress":{"phase":"read","file":"demo.exe"}}\n'
                                   '{"phase":"search","file":"demo.exe"}\n')
        self.assertEqual([voce["fase"] for voce in progresso], ["providers", "read"])
        self.assertEqual(progresso[1]["file"], "demo.exe")

    def test_un_codice_non_zero_senza_envelope_lo_dice_la_nota(self):
        """`doctor` esce 1 quando l'ambiente non e' pronto: non e' un errore."""
        documento = ('{"healthy": false, "environment_healthy": false,\n'
                     ' "scope_checks": [{"name": "hopper", "ok": false}]}\n')
        report = self._riduci(documento, exit_code=1)
        self.assertEqual(report["osservato"]["esito"], "non completato")
        self.assertIsNone(report["errore"])
        self.assertTrue(report["riferito"]["json_valido"])
        self.assertIn("codice 1", report["riferito"]["nota"])
        self.assertEqual(report["riferito"]["verdetto"],
                         {"healthy": False, "environment_healthy": False})

    def test_un_envelope_d_errore_non_diventa_un_verdetto(self):
        documento = ('{"error": "Analysis failed", "code": "provider_unavailable",\n'
                     ' "category": "unavailable", "retryable": true}\n')
        report = self._riduci(documento, exit_code=1)
        self.assertEqual(report["errore"]["code"], "provider_unavailable")
        self.assertEqual(report["errore"]["spiegazione"],
                         ras.CATEGORIE_ERRORE["unavailable"])
        self.assertIsNone(report["riferito"]["verdetto"])
        self.assertEqual(report["riferito"]["nota"], "Documento JSON letto e ridotto.")

    def test_stdout_che_non_e_json_lo_dichiara_invece_di_indovinarlo(self):
        report = self._riduci("non sono json\n", exit_code=1)
        self.assertFalse(report["riferito"]["json_valido"])
        self.assertEqual(report["riferito"]["chiavi"], [])
        self.assertIn("stderr.log", report["riferito"]["nota"])


class RotteTests(unittest.TestCase):
    """Le rotte: la whitelist, la copia nella workspace, il report, gli artefatti."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cartella = Path(self.tmp.name)
        self.workspace = self.cartella / "workspace-rea"
        self.binario = finto_rea(
            self.cartella,
            VERSIONE_FINTA + "echo '{\"target\":{\"kind\":\"asar\"},\"modules\":[{},{}]}'\n")
        app = ras.build_app(workspace=self.workspace,
                            trovato={"found": True, "path": str(self.binario),
                                     "source": "test"})
        self.addCleanup(self._ferma, app)
        self.client = app.test_client()
        self.jobs = self.workspace / "jobs"

    @staticmethod
    def _ferma(app):
        runner = app.config.get("REA_RUNNER")
        if runner is not None:
            runner.stop()

    # — attrezzi —
    def _campione(self, nome="app.asar", contenuto=b"ASAR" + b"\x00" * 60) -> Path:
        percorso = self.cartella / Path(nome).name
        percorso.write_bytes(contenuto)
        return percorso

    def _accoda(self, op="analyze-js", nome="app.asar", file=True, **campi):
        dati = {"op": op}
        dati.update(campi)
        manico = None
        if file:
            manico = self._campione(nome).open("rb")
            dati["file"] = (manico, nome)
        try:
            risposta = self.client.post("/api/jobs", data=dati,
                                        content_type="multipart/form-data")
        finally:
            if manico is not None:
                manico.close()
        return risposta

    def _completato(self, risposta):
        job_id = risposta.get_json()["job"]["id"]
        return job_id, attendi_record(self.jobs / job_id)

    # — il perimetro —
    def test_health_e_status_dichiarano_il_perimetro(self):
        salute = self.client.get("/health").get_json()
        self.assertTrue(salute["ok"])
        self.assertTrue(salute["static_only"])
        self.assertEqual(salute["host"], "127.0.0.1")
        self.assertTrue(salute["rea"])
        stato = self.client.get("/api/status").get_json()
        self.assertEqual(stato["workspace"], str(self.workspace))
        self.assertEqual(len(stato["ops"]), 13)
        self.assertEqual(stato["providers"], list(ras.PROVIDER))
        self.assertEqual(stato["artifacts"], list(ras.ARTEFATTI))
        self.assertEqual(stato["limits"]["timeout_s"], ras.TIMEOUT_S)
        self.assertEqual(len(stato["install"]), len(ras.COMANDI_INSTALLAZIONE))
        elenco = self.client.get("/api/operations").get_json()
        self.assertEqual([op["id"] for op in elenco["operations"]],
                         [op.id for op in ras.OPERAZIONI])

    def test_la_pagina_serve_le_tre_corsie(self):
        risposta = self.client.get("/")
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("text/html", risposta.headers["Content-Type"])
        corpo = risposta.get_data(as_text=True)
        for aggancio in ("Osservato qui", "Riferito da REA", "Limiti di questa lettura",
                         "REA non è installato", "il target non viene eseguito"):
            with self.subTest(aggancio=aggancio):
                self.assertIn(aggancio, corpo)
        # niente risorse esterne: la pagina parla solo con le rotte di questo file
        self.assertNotIn("http://", corpo.replace("http://127.0.0.1", ""))
        self.assertNotIn("https://", corpo)

    # — la whitelist —
    def test_un_operazione_non_esposta_e_un_400_e_non_lascia_cartelle(self):
        for corpo in ({"op": "setup"}, {"op": "uninstall"}, {"op": "capture-process"},
                      {"op": ""}, {"op": "doctor; rm -rf /"}):
            with self.subTest(corpo=corpo):
                risposta = self._accoda(file=False, **corpo)
                self.assertEqual(risposta.status_code, 400)
                self.assertIn("operazione non esposta", risposta.get_json()["error"])
        self.assertEqual(list(self.jobs.iterdir()), [])

    def test_un_lavoro_su_file_senza_file_e_un_400(self):
        risposta = self._accoda(file=False)
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("serve un file", risposta.get_json()["error"])
        self.assertEqual(list(self.jobs.iterdir()), [])

    def test_un_argomento_o_un_provider_sbagliato_non_crea_il_lavoro(self):
        risposta = self._accoda(op="function", argomento="main")
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("Hopper", risposta.get_json()["error"])
        risposta = self._accoda(op="decompile", argomento="niente", provider="hopper")
        self.assertEqual(risposta.status_code, 400)
        self.assertIn("indirizzo esadecimale", risposta.get_json()["error"])
        risposta = self._accoda(op="search", argomento="--provider ghidra",
                                provider="ghidra")
        self.assertEqual(risposta.status_code, 400)
        risposta = self._accoda(op="providers", argomento="tanto", file=False)
        self.assertEqual(risposta.status_code, 400)
        self.assertEqual(list(self.jobs.iterdir()), [])

    # — la copia del target —
    def test_il_target_finisce_nella_workspace_e_non_e_il_percorso_del_client(self):
        risposta = self._accoda(nome="../../evil.asar")
        self.assertEqual(risposta.status_code, 202)
        job_id, record = self._completato(risposta)
        self.assertEqual(record["status"], "completed")
        nome = record["target"]["nome"]
        self.assertEqual(nome, "evil.asar")
        percorso = self.jobs / job_id / "target" / nome
        self.assertTrue(percorso.is_file())
        self.assertEqual(record["target"]["sha256"], ras.sha256_file(percorso))
        self.assertLessEqual(record["target"]["bytes"], 64)
        comando = record["comando"]
        self.assertEqual(comando[0], str(self.binario))
        self.assertEqual(comando[1], "analyze-javascript-application")
        self.assertEqual(comando[2], str(percorso))
        self.assertEqual(comando[-1], "--json")
        self.assertNotIn(str(self.cartella / "evil.asar"), " ".join(comando))
        self.assertEqual(Path(comando[2]).parent.name, "target")

    def test_l_argv_di_un_operazione_nativa_porta_il_provider_scelto(self):
        risposta = self._accoda(op="function", argomento="parse_input", provider="GHIDRA")
        self.assertEqual(risposta.status_code, 202)
        job_id = risposta.get_json()["job"]["id"]
        comando = ras.scarica_json(self.jobs / job_id / "job.json")["comando"]
        self.assertEqual(comando[1], "function")
        self.assertEqual(comando[3], "parse_input")
        self.assertEqual(comando[4:], ["--provider", "ghidra", "--json"])

    # — il report e gli artefatti —
    def test_il_report_arriva_dopo_il_lavoro_e_con_le_tre_corsie(self):
        job_id, record = self._completato(self._accoda())
        corpo = self.client.get(f"/api/jobs/{job_id}").get_json()
        self.assertEqual(corpo["job"]["id"], job_id)
        report = corpo["report"]
        self.assertEqual(report["osservato"]["esito"], "completato")
        self.assertEqual(report["osservato"]["exit_code"], 0)
        self.assertEqual(report["osservato"]["target"], record["target"])
        self.assertEqual(len(report["limiti"]), len(ras.LIMITI_FISSI))
        self.assertTrue(report["riferito"]["json_valido"])
        self.assertEqual([v["n"] for v in report["riferito"]["chiavi"]
                          if v["chiave"] == "modules"], [2])


    def test_l_artefatto_si_scarica_solo_dall_elenco_e_solo_se_esiste(self):
        job_id, _ = self._completato(self._accoda())
        for nome in ("report.json", "stdout.json", "stderr.log", "job.json"):
            with self.subTest(nome=nome):
                risposta = self.client.get(f"/api/jobs/{job_id}/artifact/{nome}")
                self.assertEqual(risposta.status_code, 200)
        grezzo = self.client.get(f"/api/jobs/{job_id}/artifact/report.json")
        self.assertEqual(json.loads(grezzo.get_data(as_text=True))["osservato"]["esito"],
                         "completato")
        for nome in ("passwd", "report.json.bak", "niente.json"):
            with self.subTest(nome=nome):
                risposta = self.client.get(f"/api/jobs/{job_id}/artifact/{nome}")
                self.assertEqual(risposta.status_code, 404)

    def test_il_documento_grezzo_non_e_il_report(self):
        """`stdout.json` e' quello che REA ha stampato: la riduzione non lo sostituisce."""
        job_id, _ = self._completato(self._accoda())
        stdout = self.client.get(f"/api/jobs/{job_id}/artifact/stdout.json")
        documento = json.loads(stdout.get_data(as_text=True))
        self.assertEqual(documento["target"]["kind"], "asar")
        self.assertEqual(len(documento["modules"]), 2)

    def test_un_lavoro_finito_a_meta_non_ha_ancora_report(self):
        job_id = "0f0f0f0f0f0f"
        cartella = self.jobs / job_id
        cartella.mkdir(parents=True)
        ras.scrivi_json(cartella / "job.json", {"id": job_id, "op": "analyze",
                                                "status": "queued", "esito": None})
        corpo = self.client.get(f"/api/jobs/{job_id}").get_json()
        self.assertIsNone(corpo["report"])
        self.assertEqual(self.client.get(
            f"/api/jobs/{job_id}/artifact/report.json").status_code, 404)

    def test_un_id_che_non_e_dei_nostri_e_un_404(self):
        for scarto in ("niente", "abcdef01234", "ABCDEF012345", "0f0f0f0f0f0f0f"):
            with self.subTest(scarto=scarto):
                risposta = self.client.get(f"/api/jobs/{scarto}")
                self.assertEqual(risposta.status_code, 404)

    def test_l_elenco_dei_lavori_e_dal_piu_recente(self):
        primo, _ = self._completato(self._accoda())
        secondo, _ = self._completato(self._accoda(op="inspect-artifact"))
        elenco = self.client.get("/api/jobs").get_json()
        ids = [voce["id"] for voce in elenco["jobs"]]
        self.assertEqual(sorted(ids), sorted([primo, secondo]))
        self.assertEqual([voce["status"] for voce in elenco["jobs"]],
                         ["completed", "completed"])
        self.assertEqual([voce["esito"] for voce in elenco["jobs"]],
                         ["completato", "completato"])
        # `created_at` ha il secondo come grana: su due lavori nati nello stesso
        # secondo l'ordine non e' un contratto, ma il piu' recente resta in cima.
        date = [voce["created_at"] for voce in elenco["jobs"]]
        self.assertEqual(date, sorted(date, reverse=True))
        self.assertEqual(elenco["workspace"], str(self.workspace))

    # — i tetti —
    def test_la_coda_piena_e_429_e_la_workspace_piena_e_507(self):
        app = ras.build_app(workspace=self.workspace,
                            trovato={"found": True, "path": str(self.binario),
                                     "source": "test"})
        self.addCleanup(self._ferma, app)
        client = app.test_client()
        runner = app.config["REA_RUNNER"]
        runner.in_coda = ras.MAX_IN_CODA
        risposta = self._accoda_con(client)
        self.assertEqual(risposta.status_code, 429)
        self.assertIn("coda e' piena", risposta.get_json()["error"])
        runner.in_coda = 0
        originale = ras.MAX_WORKSPACE_BYTES
        ras.MAX_WORKSPACE_BYTES = 0
        self.addCleanup(setattr, ras, "MAX_WORKSPACE_BYTES", originale)
        risposta = self._accoda_con(client)
        self.assertEqual(risposta.status_code, 507)
        self.assertIn("workspace e' piena", risposta.get_json()["error"])
        self.assertEqual(list(self.jobs.iterdir()), [])

    def _accoda_con(self, client):
        manico = self._campione().open("rb")
        try:
            return client.post("/api/jobs",
                               data={"op": "analyze-js", "file": (manico, "app.asar")},
                               content_type="multipart/form-data")
        finally:
            manico.close()



class SenzaReaTests(unittest.TestCase):
    """REA non c'e': la superficie lo dice e **non** installa niente."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cartella = Path(self.tmp.name)
        self.workspace = self.cartella / "workspace-rea"
        self.app = ras.build_app(workspace=self.workspace,
                                 trovato={"found": False, "path": None, "source": None,
                                          "error": "`rea` non e' nel PATH"})
        self.client = self.app.test_client()

    def test_lo_stato_dice_cosa_manca_e_con_quali_comandi(self):
        stato = self.client.get("/api/status").get_json()
        self.assertFalse(stato["rea"]["found"])
        self.assertEqual(stato["install"][0]["comando"], "npm install --global rea-agents")
        self.assertEqual(len(stato["install"]), 3)
        self.assertFalse(self.client.get("/health").get_json()["rea"])

    def test_un_lavoro_non_parte_e_la_risposta_porta_i_comandi(self):
        risposta = self.client.post("/api/jobs", data={"op": "doctor"},
                                    content_type="multipart/form-data")
        self.assertEqual(risposta.status_code, 503)
        corpo = risposta.get_json()
        self.assertIn("REA non e' disponibile", corpo["error"])
        self.assertEqual(len(corpo["install"]), 3)
        self.assertEqual(list((self.workspace / "jobs").iterdir()), [])

    def test_la_rotta_che_accoda_non_esiste_senza_runner(self):
        self.assertIsNone(self.app.config["REA_RUNNER"])

    def test_check_esce_uno_e_stampa_i_comandi(self):
        # REA_BIN puntato a un file che non c'e': l'esito "non trovato" non
        # dipende da cosa e' installato sulla macchina che esegue i test.
        esito = self._check({"PATH": str(self.cartella / "vuoto"),
                             "REA_BIN": str(self.cartella / "niente")})
        self.assertEqual(esito.returncode, 1)
        self.assertIn("NON trovato", esito.stdout)
        self.assertIn("npm install --global rea-agents", esito.stdout)
        self.assertIn("non installera' niente", esito.stdout)

    def test_check_esce_zero_con_un_rea_finto_nel_path(self):
        finto_rea(self.cartella, VERSIONE_FINTA + "exit 0\n")
        esito = self._check({"PATH": str(self.cartella)})
        self.assertEqual(esito.returncode, 0, esito.stderr)
        self.assertIn("rea 0.0.0-finto", esito.stdout)
        self.assertIn("Superficie pronta", esito.stdout)

    def _check(self, extra_env):
        """`--check` in un processo a parte, con l'ambiente che decidiamo noi.

        In un processo a parte perche' `rea_binary()` legge `os.environ` del
        processo: cambiare PATH qui dentro non direbbe niente. PATH vuoto o con
        solo il finto `rea`: nessuna probabilita' di pescare quello vero.
        """
        ambiente = {"PATH": "/nonexistent", "HOME": str(self.cartella),
                    "PYTHONPATH": str(ROOT),
                    "REA_SURFACE_WORKSPACE": str(self.cartella / "rea-da-check")}
        ambiente.update(extra_env)
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "rea_surface.py"),
                               "--check"], capture_output=True, text=True, timeout=60,
                              env=ambiente)



class ContrattoConLoStackTests(unittest.TestCase):
    """La superficie e' annunciata dove gli altri la cercano, con la stessa porta."""

    def setUp(self):
        self.catalogo = ast.literal_eval(cp_source.assegnazioni()["SURFACES"])

    def test_il_catalogo_annuncia_la_stessa_porta(self):
        voci = [voce for voce in self.catalogo if voce["id"] == "rea"]
        self.assertEqual(len(voci), 1, "una superficie sola, con un id stabile")
        voce = voci[0]
        self.assertEqual(voce["port"], ras.PORT)
        self.assertEqual(voce["path"], "/")
        self.assertEqual(voce["category"], "dev")
        self.assertTrue(voce.get("optional"),
                        "REA puo' non essere installato: senza di lui la superficie "
                        "parte lo stesso e mostra i comandi")

    def test_la_dashboard_apre_la_superficie_e_non_dice_piu_candidato(self):
        dashboard = (ROOT / "control-plane" / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("openSurface('rea')", dashboard)
        self.assertIn(f":{ras.PORT}", dashboard)
        self.assertNotIn("candidato &middot; non collegato", dashboard,
                         "la card deve dire che la superficie esiste e dove")

    def test_start_tutto_la_avvia_solo_se_rea_c_e(self):
        script = (ROOT / "scripts" / "start-all-macos.sh").read_text(encoding="utf-8")
        self.assertIn("scripts/rea_surface.py", script)
        self.assertIn(str(ras.PORT), script)
        self.assertIn('"$rea_python" "$REPO/scripts/rea_surface.py" --check', script,
                      "senza `rea` la superficie non parte (il check viene prima)")

    def test_la_documentazione_la_descrive(self):
        doc = (ROOT / "docs" / "rea-surface.md").read_text(encoding="utf-8")
        self.assertIn("rea_surface.py", doc)
        self.assertIn(str(ras.PORT), doc)
        self.assertIn("npm install --global rea-agents", doc)


if __name__ == "__main__":
    unittest.main()

