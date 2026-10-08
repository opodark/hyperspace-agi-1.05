# SPDX-License-Identifier: Apache-2.0
"""Guardrail tests for the Mission Control control-plane integration.

Following `test_dream_routes.py`, these inspect `control-plane/main.py` as source
(AST) instead of importing it: importing the app starts DB work and background
loops. The point is to pin the *security-relevant shape* of the integration:
every route gated by the operator token, tools bound through the manifest,
nothing ever applied.
"""
import ast
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from shared import mission_policy as policy
from shared.mission import TASK_STATUSES


ROOT = Path(__file__).parents[1]
MAIN_SOURCE = (ROOT / "control-plane" / "main.py").read_text(encoding="utf-8")
DASHBOARD = (ROOT / "control-plane" / "dashboard.html").read_text(encoding="utf-8")


def functions(path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    return {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def routes(tree):
    """path -> (handler name, methods) for every @app.route in the module."""
    found = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "route" and decorator.args):
                methods = ["GET"]
                for keyword in decorator.keywords:
                    if keyword.arg == "methods":
                        methods = [element.value for element in keyword.value.elts]
                found[decorator.args[0].value] = (node.name, methods)
    return found


class MissionRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(MAIN_SOURCE)
        cls.control_plane = functions(ROOT / "control-plane" / "main.py")
        cls.route_map = routes(cls.tree)

    def unparse(self, name):
        node = self.control_plane[name] if isinstance(name, str) else name
        return ast.unparse(node)

    def test_mission_routes_exist_with_expected_methods(self):
        expected = {
            "/missions/status": ["GET"],
            "/missions": ["GET", "POST"],
            "/missions/<mission_id>": ["GET"],
            "/missions/<mission_id>/run": ["POST"],
            "/missions/<mission_id>/cancel": ["POST"],
            "/missions/<mission_id>/review": ["POST"],
        }
        for path, methods in expected.items():
            self.assertIn(path, self.route_map, f"missing route {path}")
            self.assertEqual(sorted(self.route_map[path][1]), sorted(methods),
                             f"wrong methods for {path}")

    def test_every_mission_route_requires_the_operator_token(self):
        for path, (handler, _methods) in self.route_map.items():
            if not path.startswith("/missions"):
                continue
            self.assertIn("_dream_review_auth_error", self.unparse(handler),
                          f"{path} is not gated by the operator token")

    def test_review_route_records_but_never_applies(self):
        source = self.unparse(self.control_plane["mission_review"])
        self.assertIn("_dream_review_auth_error", source)
        self.assertIn("applied", source)
        self.assertIn("rationale is required", source)
        # Never touches the sandbox: a review is a decision, not an execution.
        self.assertNotIn("code_sandbox", source)

    def test_worker_binds_tools_through_the_role_manifest(self):
        source = self.unparse(self.control_plane["_mission_worker"])
        self.assertIn("mission_policy.tools_for_role", source)
        self.assertIn("mission_policy.resolve_manifest", source)
        # The raw catalogs must never be handed to a worker directly.
        self.assertNotIn("BUILTIN_TOOLS", source)
        self.assertNotIn("_NATIVE_TOOLS", source)

    def test_worker_lets_the_control_plane_decide_thinking(self):
        """Con i tool in mano il reasoning va spento, come nel percorso chat.

        Un modello reasoning che ragiona risponde a memoria invece di emettere
        `tool_calls`: misurato il 2026-10-06, il coder ha scritto lo script in
        prosa e la sandbox non ha ricevuto nulla. La decisione è una sola in
        tutto il CP — `_decide_thinking` — e deve valere anche qui.
        """
        source = self.unparse(self.control_plane["_mission_worker"])
        self.assertIn("_mission_reasoning", source)
        self.assertIn("data['think']", source)  # ast.unparse usa gli apici singoli

    def test_a_tool_that_writes_outside_the_sandbox_is_still_an_artifact(self):
        """`create_website` scrive in `WEBSITE_DIR`, non nella sandbox usa-e-getta.

        Senza cattura, un task che ha creato davvero una pagina non comparirebbe
        fra gli artifact: l'operatore non saprebbe cosa rivedere. La cattura vive
        accanto a quella della sandbox e l'artifact resta `applied: False`.
        """
        source = self.unparse(self.control_plane["_mission_worker"])
        self.assertIn("_mission_website_artifacts", source)
        artifacts = self.unparse(self.control_plane["_mission_website_artifacts"])
        self.assertIn("website-project", artifacts)
        self.assertIn("applied", artifacts)

    def test_every_mission_model_call_goes_through_the_same_reasoning_rule(self):
        """Planner, worker e verifier chiedono la direttiva alla stessa funzione.

        Il mission loop parla a Ollama su `/v1/chat/completions`, che **ignora**
        il campo `think`: senza `/no_think` nel testo un modello reasoning
        continua a ragionare (32 token col contenuto scartato, un task fermo
        oltre dieci minuti). La direttiva vive in un posto solo.
        """
        reasoning = self.unparse(self.control_plane["_mission_reasoning"])
        self.assertIn("_decide_thinking", reasoning)
        self.assertIn("_is_reasoning_model", reasoning)
        self.assertIn("/no_think", reasoning)
        for handler in ("_mission_plan", "_mission_worker", "_mission_verify"):
            self.assertIn("_mission_reasoning", self.unparse(self.control_plane[handler]),
                          f"{handler} non applica la regola del reasoning")

    def test_controller_is_wired_with_the_three_collaborators(self):
        source = self.unparse(self.control_plane["_initialize_mission_control"])
        self.assertIn("MissionController", source)
        self.assertIn("_mission_plan", source)
        self.assertIn("_mission_worker", source)
        self.assertIn("_mission_verify", source)
        self.assertIn("_mission_budget", source)
        # Il budget è una sola fonte di verità: la policy condivisa.
        self.assertIn("mission_policy", self.unparse(self.control_plane["_mission_budget"]))

    def test_planner_rejects_roles_outside_the_manifest(self):
        source = self.unparse(self.control_plane["_mission_plan"])
        self.assertIn("_mission_role_allowed", source)
        self.unparse(self.control_plane["_mission_role_allowed"])  # must exist

    def test_planner_normalizes_keys_and_dependencies_with_one_rule(self):
        """Tasto e dipendenza devono passare dalla stessa normalizzazione.

        Con due regole diverse — `check_page_includes` da una parte,
        `check-page-includes` dall'altra — lo store rifiuta l'intero piano
        ("task verify-routes depends on unknown task check_page_includes") e la
        missione muore senza eseguire un solo task: visto in produzione il
        2026-10-06. La regola sta in `shared/mission_policy`, una sola volta.
        """
        source = self.unparse(self.control_plane["_mission_plan"])
        self.assertIn("mission_policy.task_key", source)
        self.assertIn("mission_policy.resolve_dependencies", source)
        self.assertNotIn("re.sub", source)  # nessuna regex riscritta nel planner
        self.assertIn("Planner dependencies normalized", source)  # chi la cambia lo dice

    def test_no_prompt_shows_a_null_task_key(self):
        """Lo store salva il tasto in `task_id`: `task.get('key')` da solo è `None` sempre.

        Con la sola lettura di `key` il prompt del planner diceva "Existing tasks:
        None [failed]", quello del worker "Your task (None)" e la payload della
        missione `key: null`. Un tasto `None` non identifica nulla: ogni lettura
        deve ricadere su `task_id`.
        """
        offenders = re.findall(r"\{[a-z_]+\.get\('key'\)\}", MAIN_SOURCE)
        self.assertEqual(offenders, [],
                         f"letture di `key` senza fallback su `task_id`: {offenders}")

    def test_the_mission_payload_never_reports_a_null_key(self):
        source = self.unparse(self.control_plane["_mission_task_public"])
        self.assertIn("task.get('key') or task.get('task_id')", source)

    def test_mission_loop_is_started_in_every_startup_branch(self):
        starts = re.findall(r"^\s+_initialize_mission_control\(\)", MAIN_SOURCE, re.M)
        threads = re.findall(r"target=mission_controller_loop", MAIN_SOURCE)
        self.assertEqual(len(starts), 2)  # __main__ e il ramo gunicorn
        self.assertEqual(len(threads), 2)

    def test_loop_is_opt_in_by_default(self):
        self.assertIn('os.getenv("MISSION_LOOP_ENABLED", "false")', MAIN_SOURCE)

    def test_federation_gateway_does_not_expose_missions(self):
        gateway = ast.parse((ROOT / "federation-gateway" / "main.py").read_text(encoding="utf-8"))
        assignment = next(node for node in gateway.body if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == "ALLOWED_ROUTES"
                                  for target in node.targets))
        self.assertNotIn("/missions", ast.unparse(assignment))

    def test_dashboard_exposes_the_mission_card(self):
        for element in ('id="missionInbox"', 'id="missionObjective"', 'id="missionStatusFilter"',
                        "loadMissions()", "createMission(", "reviewMission(", "cancelMission("):
            self.assertIn(element, DASHBOARD)

    def test_dashboard_exposes_the_mission_flow(self):
        """La card disegna un DAG vivente, non solo una lista di task.

        Il flusso segue la macchina a stati vera (`shared.mission.TASK_STATUSES`):
        se il controller introduce uno stato nuovo e la mappa dei colori non lo
        copre, quel task resterebbe grigio senza che nessun test se ne accorga.
        Qui si pinna il contratto minimo fra HTML e script (container, etichette,
        helper di disegno e mappa dei colori).
        """
        for element in ('id="cyMission"', 'id="missionFlowLabel"', 'id="missionDetail"',
                        "drawMissionFlow(", "missionFlowReLayout(", "missionFlowNode(",
                        "MISSION_FLOW_COLORS", "MISSION_FLOW_LAYOUT"):
            self.assertIn(element, DASHBOARD)
        match = re.search(r"MISSION_FLOW_COLORS=\{([^}]*)\}", DASHBOARD)
        self.assertIsNotNone(match, "MISSION_FLOW_COLORS non trovato nella dashboard")
        colours = set(re.findall(r"([a-z_]+):'", match.group(1)))
        self.assertEqual(colours, TASK_STATUSES,
                         "la legenda del flusso non copre ogni stato del task")


class _FakeSandbox:
    """Sandbox finto: `status` pubblica l'indice dei workspace solo se lo serve."""

    def __init__(self, workspaces=None, serves_index=True, fail_diff=False, enabled=True):
        self.enabled = enabled
        self.actions = []
        self.serves_index = serves_index
        self.fail_diff = fail_diff
        self._workspaces = list(workspaces or [])

    def call(self, action, arguments=None, timeout=None):
        self.actions.append(action)
        if action == "status":
            payload = {"ok": True}
            if self.serves_index:
                payload["workspaces"] = list(self._workspaces)
            return payload
        if action == "diff":
            if self.fail_diff:
                raise RuntimeError("runner unavailable")
            return {"ok": True, "changed_files": ["app.py"],
                    "diff": "--- a/app.py\n+++ b/app.py\n"}
        raise AssertionError(f"unexpected sandbox action: {action}")


class MissionSandboxArtifactTests(unittest.TestCase):
    """L'elenco dei workspace deve venire da `status`, mai da `list`.

    `list` elenca i file di *un* workspace: senza `workspace_id` fallisce sempre,
    così la revisione umana resterebbe senza diff. Questi test eseguono davvero
    gli helper (via AST) contro un client finto, quindi il bug non può rientrare
    silenziosamente dietro un `except`.
    """

    HELPERS = ("_mission_sandbox_backends", "_mission_sandbox_workspaces",
               "_mission_sandbox_artifacts")

    @classmethod
    def helpers(cls, client):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name in cls.HELPERS],
            type_ignores=[])
        namespace = {"code_sandbox": client}
        exec(compile(module, "<mission-sandbox>", "exec"), namespace)
        return namespace

    def test_workspace_index_comes_from_status(self):
        client = _FakeSandbox(workspaces=[{"workspace_id": "w-1", "label": "before"}])
        workspaces = self.helpers(client)["_mission_sandbox_workspaces"]()
        self.assertEqual(set(workspaces), {"w-1"})
        # `list` non basta: servirebbe un workspace_id e restituirebbe dei file.
        self.assertEqual(client.actions, ["status"])

    def test_hybrid_client_asks_a_backend_that_lists_workspaces(self):
        hybrid = _FakeSandbox(serves_index=False)  # status del wrapper ibrido
        hybrid.primary = _FakeSandbox(serves_index=False)
        hybrid.fallback = _FakeSandbox(workspaces=[{"workspace_id": "w-9", "label": "mission"}])
        workspaces = self.helpers(hybrid)["_mission_sandbox_workspaces"]()
        self.assertEqual(set(workspaces), {"w-9"})
        self.assertEqual(hybrid.primary.actions, ["status"])
        self.assertEqual(hybrid.fallback.actions, ["status"])

    def test_a_disabled_sandbox_reports_no_workspaces(self):
        client = _FakeSandbox(workspaces=[{"workspace_id": "w-1"}], enabled=False)
        self.assertEqual(self.helpers(client)["_mission_sandbox_workspaces"](), {})
        self.assertEqual(client.actions, [])

    def test_artifacts_are_review_gated_and_never_applied(self):
        client = _FakeSandbox(workspaces=[{"workspace_id": "w-1", "label": "before"}])
        helpers = self.helpers(client)
        before = helpers["_mission_sandbox_workspaces"]()
        client._workspaces = [{"workspace_id": "w-1", "label": "before"},
                              {"workspace_id": "w-2", "label": "mission"}]
        artifacts = helpers["_mission_sandbox_artifacts"](before)
        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertEqual(artifact["workspace_id"], "w-2")
        self.assertEqual(artifact["kind"], "sandbox-workspace")
        self.assertFalse(artifact["applied"])
        self.assertEqual(artifact["changed_files"], ["app.py"])
        self.assertIn("+++ b/app.py", artifact["diff"])

    def test_a_failing_diff_does_not_fail_the_task(self):
        client = _FakeSandbox(workspaces=[{"workspace_id": "w-3", "label": "mission"}],
                              fail_diff=True)
        artifacts = self.helpers(client)["_mission_sandbox_artifacts"]({})
        self.assertEqual(len(artifacts), 1)
        self.assertFalse(artifacts[0]["applied"])
        self.assertIn("runner unavailable", artifacts[0]["diff_error"])
        self.assertNotIn("changed_files", artifacts[0])


class MissionWebsiteArtifactTests(unittest.TestCase):
    """Un sito creato fuori dalla sandbox deve comparire fra gli artifact.

    `create_website` scrive in `WEBSITE_DIR`: la cattura è un diff fra prima e
    dopo, come per i workspace. Così un task che non ha creato nulla non inventa
    artifact, e uno che l'ha fatto lo dice. Gli helper sono ESEGUITI davvero,
    contro una cartella temporanea.
    """

    HELPERS = ("_mission_website_ids", "_mission_website_artifacts")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.helpers = self._load(self.temp.name)

    @staticmethod
    def _load(website_dir):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name in MissionWebsiteArtifactTests.HELPERS],
            type_ignores=[])
        namespace = {"WEBSITE_DIR": website_dir, "os": os}
        exec(compile(module, "<mission-website>", "exec"), namespace)
        return namespace

    def _site(self, project_id):
        folder = Path(self.temp.name) / project_id
        folder.mkdir()
        (folder / "manifest.json").write_text("{}", encoding="utf-8")
        (folder / "index.html").write_text("<html></html>", encoding="utf-8")

    def test_a_new_site_is_captured_and_never_applied(self):
        self._site("atelier-aurora-00000001")
        before = self.helpers["_mission_website_ids"]()
        self._site("anna-galleria-00000002")
        artifacts = self.helpers["_mission_website_artifacts"](before)
        self.assertEqual(len(artifacts), 1)
        artifact = artifacts[0]
        self.assertEqual(artifact["kind"], "website-project")
        self.assertEqual(artifact["project_id"], "anna-galleria-00000002")
        self.assertEqual(artifact["preview"], "/website/preview/anna-galleria-00000002/")
        self.assertFalse(artifact["applied"])

    def test_a_task_that_creates_nothing_reports_no_artifact(self):
        self._site("atelier-aurora-00000001")
        before = self.helpers["_mission_website_ids"]()
        self.assertEqual(self.helpers["_mission_website_artifacts"](before), [])

    def test_a_folder_without_a_manifest_is_not_a_project(self):
        (Path(self.temp.name) / "senza-manifest").mkdir()
        self.assertNotIn("senza-manifest", self.helpers["_mission_website_ids"]())

    def test_a_missing_directory_never_raises(self):
        helpers = self._load(str(Path(self.temp.name) / "non-esiste"))
        self.assertEqual(helpers["_mission_website_ids"](), set())


class MissionPlannerAttemptTests(unittest.TestCase):
    """`max_attempts` deve arrivare dal budget, non dal silenzio del modello.

    `MISSION_MAX_TASK_ATTEMPTS` (default 2) era un knob morto: la policy lo
    dichiarava, il planner non lo leggeva, e ogni task nasceva con 1 tentativo —
    con un modello 8B il primo intoppo era terminale e la catena dietro di lui
    restava `skipped`. Qui `_mission_plan` e `_mission_json` sono ESEGUITI
    davvero, con un modello finto.
    """

    RAW = ('{"tasks":[{"key":"build","role":"coder","title":"t",'
           '"instruction":"do it"},'
           '{"key":"verify","role":"verifier","title":"v","instruction":"check",'
           '"dependencies":["build"],"max_attempts":3}]}')

    @classmethod
    def planner(cls, budget_attempts=2, raw=RAW):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name in {"_mission_plan", "_mission_json"}],
            type_ignores=[])
        namespace = {
            "mission_policy": policy,
            "re": re,
            "json": json,
            "MISSION_PLANNER_MODEL": "fake-planner",
            "_mission_budget": lambda: {"max_steps": 40,
                                        "max_task_attempts": budget_attempts},
            "_mission_roles_hint": lambda: "- coder: builds",
            "_mission_reasoning": lambda model, data, messages, tools: (False, ""),
            "_mission_llm": lambda *args, **kwargs: raw,
            "push_log": lambda *args, **kwargs: None,
            "_mission_role_allowed": lambda role: True,
        }
        exec(compile(module, "<mission-plan>", "exec"), namespace)
        return namespace["_mission_plan"]

    def test_absent_max_attempts_takes_the_budget_default(self):
        tasks = self.planner()({"objective": "o", "criteria": []})
        by_key = {task["key"]: task for task in tasks}
        self.assertEqual(by_key["build"]["max_attempts"], 2)
        self.assertEqual(by_key["verify"]["max_attempts"], 2)  # explicit model request cannot raise the cap

    def test_a_lower_budget_lowers_the_default(self):
        tasks = self.planner(budget_attempts=1)({"objective": "o", "criteria": []})
        self.assertEqual(tasks[0]["max_attempts"], 1)

    def test_operator_role_limit_survives_a_wrong_model_role(self):
        raw = ('{"tasks":[{"key":"pdf","role":"repo-analyst",'
               '"instruction":"Read local files and make a PDF"}]}')
        mission = {"objective": "PDF", "success_criteria": [],
                   "policy": {"roles": ["coder"]},
                   "_execution_budget": {"max_steps": 1,
                                         "max_task_attempts": 1}}
        tasks = self.planner(raw=raw)(mission)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["role"], "coder")

    def test_the_planner_keeps_one_workspace_chain_in_a_single_coder_task(self):
        """Un create→write→run nello stesso workspace è UN task, non quattro.

        Misurato il 2026-10-07: il planner spezzava la catena in quattro task coder
        dipendenti; ogni task ricreava un workspace e perdeva l'id a monte, così il
        PDF non arrivava mai. Il workspace usa-e-getta è stato condiviso dentro UN
        tool loop, quindi il prompt del planner deve dirlo.
        """
        prompts = []
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name in {"_mission_plan", "_mission_json"}],
            type_ignores=[])
        namespace = {
            "mission_policy": policy,
            "re": re,
            "json": json,
            "MISSION_PLANNER_MODEL": "fake-planner",
            "_mission_budget": lambda: {"max_steps": 40, "max_task_attempts": 2},
            "_mission_roles_hint": lambda: "- coder: builds",
            "_mission_reasoning": lambda *a: (False, ""),
            "_mission_llm": lambda prompt, *a, **k: (prompts.append(prompt) or self.RAW),
            "push_log": lambda *a, **k: None,
            "_mission_role_allowed": lambda role: True,
        }
        exec(compile(module, "<mission-plan>", "exec"), namespace)
        namespace["_mission_plan"]({"objective": "o", "criteria": []})
        self.assertIn("SINGLE coder task", prompts[-1])
        self.assertIn("reuse that same workspace_id", prompts[-1])


class MissionPlannerShapeTests(unittest.TestCase):
    """La forma del JSON del planner non deve far morire la missione.

    Misurato il 2026-10-06 con `granite3.3-g8k`: il modello ha risposto con UN
    task nudo — `{"key":"planner-001","role":"planner",...}` — invece di
    `{"tasks": [...]}`. Il piano vuoto ha fatto fallire la missione con "invalid
    plan: plan must be a non-empty list of tasks" senza eseguire un solo task, e
    la role `planner` non è comunque eseguibile (zero tool).
    """

    HELPERS = ("_mission_json", "_mission_plan", "_mission_role_allowed",
               "_mission_roles_hint")

    def setUp(self):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name in self.HELPERS],
            type_ignores=[])
        self.text = ""
        self.helpers = {
            "mission_policy": policy, "re": re, "json": json,
            "MISSION_PLANNER_MODEL": "fake-planner",
            "_mission_budget": lambda: {"max_steps": 40, "max_task_attempts": 2},
            "_mission_reasoning": lambda *args: (False, ""),
            "_mission_llm": lambda *args, **kwargs: self.text,
            "push_log": lambda *args, **kwargs: None,
        }
        exec(compile(module, "<mission-plan-shape>", "exec"), self.helpers)

    def plan(self, text):
        self.text = text
        return self.helpers["_mission_plan"]({"objective": "o", "criteria": []})

    def test_a_bare_task_object_becomes_a_one_task_plan(self):
        plan = self.plan('{"key":"planner-001","role":"planner",'
                         '"title":"Plan coder task",'
                         '"instruction":"Decompose objective into a linear sequence"}')
        self.assertEqual(len(plan), 1)
        # `planner` non è eseguibile: ricade sul default conservativo.
        self.assertEqual(plan[0]["role"], "worker")
        self.assertEqual(plan[0]["key"], "planner-001")

    def test_a_bare_array_becomes_the_task_list(self):
        plan = self.plan('[{"key":"build","role":"coder","instruction":"do it"},'
                         '{"key":"check","role":"verifier","instruction":"check",'
                         '"dependencies":["build"]}]')
        self.assertEqual([task["key"] for task in plan], ["build", "check"])
        self.assertEqual(plan[1]["dependencies"], ["build"])

    def test_an_object_without_a_task_is_still_rejected(self):
        self.assertEqual(self.plan('{"answer":"no plan here"}'), [])

    def test_the_planner_role_is_not_an_executor_role(self):
        allowed = self.helpers["_mission_role_allowed"]
        self.assertFalse(allowed("planner"))
        self.assertTrue(allowed("coder"))
        self.assertTrue(allowed("verifier"))

    def test_the_role_hint_never_offers_the_planner_as_an_executor(self):
        hint = self.helpers["_mission_roles_hint"]()
        self.assertNotIn("planner", hint)
        self.assertIn("coder", hint)


class _FakePolicy:
    DEFAULT_ROLE = "coder"

    @staticmethod
    def resolve_manifest(role):
        return {"max_iterations": 6, "model_class": "code"}

    @staticmethod
    def tools_for_role(role, catalog):
        return [{"type": "function", "function": {"name": "code_sandbox"}}]


class MissionWorkerFailureTests(unittest.TestCase):
    """Un guasto del modello deve finire in `error` del task, non in un KeyError.

    `_run_tool_loop` segnala i fallimenti di modello/trasporto con un payload
    `{"error": {...}}`: leggerlo come una completion faceva morire il task con
    `KeyError: 'choices'`, cioè proprio il messaggio inutile che l'operatore non
    può diagnosticare. Qui il worker viene ESEGUITO (via AST) contro un loop
    finto, così il ramo non può regredire dietro un `except`.
    """

    @staticmethod
    def worker(loop_response, seen=None, reasoning_model=False):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name in {"_mission_worker", "_mission_reasoning"}],
            type_ignores=[])

        def fake_loop(data, *args, **kwargs):
            if seen is not None:
                seen.append(data)
            return loop_response

        namespace = {
            "mission_policy": _FakePolicy,
            "_catalogo_nativi": lambda: {},
            "_mission_model_for": lambda role: "fake-model",
            "_mission_task_context": lambda mission, task: "",
            "_mission_chain_workspace_id": lambda mission, task: "",
            "_mission_num_ctx": lambda: 16384,
            # Le decisioni del CP sul reasoning, iniettate come gli altri
            # collaboratori: `_mission_reasoning` è eseguita davvero e le usa.
            "_decide_thinking": lambda model, data, messages, tools: False,
            "_is_reasoning_model": lambda model: reasoning_model,
            "_run_tool_loop": fake_loop,
            "_mission_sandbox_workspaces": lambda: {},
            "_mission_sandbox_artifacts": lambda *args, **kwargs: [],
            "_mission_website_ids": lambda: set(),
            "_mission_website_artifacts": lambda before: [],
            "code_sandbox": type("Client", (), {"enabled": True})(),
            "advanced_config": {"ollama": {"url": "http://ollama.invalid"}},
            # L'endpoint di inferenza della missione è iniettato come gli altri
            # collaboratori: `_mission_worker` non deve cablare l'URL a mano.
            "_mission_inference_base": lambda: "http://ollama.invalid",
        }
        exec(compile(module, "<mission-worker>", "exec"), namespace)
        return namespace["_mission_worker"]

    TASK = {"key": "t-1", "role": "coder", "title": "write it", "instruction": "do it"}
    LOOP = {"choices": [{"message": {"content": "created palindrome.py"}}]}

    def test_the_payload_carries_the_control_plane_thinking_decision(self):
        """`think` arriva al modello esattamente come nel percorso chat.

        Con dei tool in mano il reasoning va spento: un modello reasoning che
        ragiona risponde a memoria invece di emettere `tool_calls`. Misurato il
        2026-10-06, il coder ha scritto lo script in prosa e la sandbox non ha
        ricevuto nulla — la missione è finita senza artifact.
        """
        seen = []
        self.worker(self.LOOP, seen)(self.TASK, {"objective": "o"})
        self.assertEqual(seen[0]["think"], False)
        self.assertEqual(seen[0]["model"], "fake-model")
        # Un modello non-reasoning non riceve direttive: il campo `think` basta.
        self.assertNotIn("/no_think", seen[0]["messages"][0]["content"])

    def test_a_reasoning_model_also_gets_the_nothink_directive(self):
        """Il campo `think` da solo non basta: l'endpoint compat di Ollama lo ignora.

        Con `/no_think` nel system la stessa richiesta produce la tool_call in
        45 s con 48 token; senza, il ragionamento resta acceso, il contenuto
        torna vuoto (`content: ''`) e il task non finisce più.
        """
        seen = []
        self.worker(self.LOOP, seen, reasoning_model=True)(self.TASK, {"objective": "o"})
        self.assertEqual(seen[0]["think"], False)
        self.assertTrue(seen[0]["messages"][0]["content"].startswith("/no_think\n"))
        self.assertIn("bounded, auditable mission", seen[0]["messages"][0]["content"])

    def test_a_tool_loop_error_becomes_the_task_error(self):
        result = self.worker({"error": {"message": "model overloaded"}})(self.TASK, {"objective": "o"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "model overloaded")
        self.assertEqual(result["role"], "coder")

    def test_an_answer_without_choices_is_a_clean_failure(self):
        result = self.worker({})(self.TASK, {"objective": "o"})
        self.assertFalse(result["ok"])
        self.assertIn("no output", result["error"])

    def test_a_normal_completion_is_returned_as_the_worker_output(self):
        loop = {"choices": [{"message": {"content": "created palindrome.py"}}]}
        result = self.worker(loop)(self.TASK, {"objective": "o"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["output"], "created palindrome.py")
        self.assertEqual(result["model"], "fake-model")
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(result["error"], "")

    def test_the_coder_is_told_to_reuse_an_upstream_workspace(self):
        """Un task a valle non deve creare un secondo workspace e spezzare la catena.

        Misurato il 2026-10-07: `create-workspace` completava, poi `write-script`
        chiamava di nuovo `create` e scriveva in un sandbox nuovo e vuoto; il diff
        non conteneva il PDF atteso. Il system prompt deve dire di riusare il
        `workspace_id` ricevuto a monte e di non richiamare `create` quando c'è già.
        """
        seen = []
        self.worker(self.LOOP, seen)(self.TASK, {"objective": "o"})
        system = seen[0]["messages"][0]["content"]
        self.assertIn("reuse that exact id", system)
        self.assertIn("do NOT call create", system)

    def test_the_coder_is_told_not_to_repeat_a_failing_call(self):
        """Il guard della sandbox aborta un retry identico: il prompt deve avvisare."""
        seen = []
        self.worker(self.LOOP, seen)(self.TASK, {"objective": "o"})
        system = seen[0]["messages"][0]["content"]
        self.assertIn("never repeat an identical failing call", system)


class _FakeInspectSandbox:
    """Sandbox finto per il gate PDF: risponde solo a `inspect`."""

    def __init__(self, result, enabled=True):
        self.enabled = enabled
        self.result = result
        self.calls = []

    def call(self, action, arguments=None, timeout=None):
        self.calls.append((action, dict(arguments or {})))
        if action != "inspect":
            raise AssertionError(f"unexpected sandbox action: {action}")
        return self.result


class MissionPdfGateTests(unittest.TestCase):
    """Il gate PDF e' indipendente dal modello: fatti dal runner, non prosa.

    Una missione che chiede un PDF non deve poter dire `pass` su un file che non
    e' un PDF. Il gate interroga il runner (azione `inspect`): firma `%PDF`,
    pagine, testo estraibile. Questi test eseguono gli helper veri via AST contro
    un client finto, quindi il controllo non puo' sparire dietro un `except`.
    """

    HELPERS = ("_mission_expects_pdf", "_mission_pdf_candidates", "_mission_pdf_gate")

    @classmethod
    def helpers(cls, client):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name in cls.HELPERS],
            type_ignores=[])
        namespace = {"code_sandbox": client, "re": re,
                     "_ARTIFACT_PDF": re.compile(r"\.pdf$", re.IGNORECASE)}
        exec(compile(module, "<mission-pdf-gate>", "exec"), namespace)
        return namespace

    def test_a_real_pdf_passes_the_gate(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 6,
                                      "text_chars": 1200})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a briefing PDF"},
            [{"workspace_id": "w-1", "changed_files": ["artifacts/brief.pdf"]}])
        self.assertTrue(gate["ok"])
        self.assertEqual(client.calls, [("inspect", {"workspace_id": "w-1",
                                                     "path": "artifacts/brief.pdf"})])

    def test_a_file_without_a_pdf_signature_is_rejected(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": False, "pages": None,
                                      "text_chars": None})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a PDF"},
            [{"workspace_id": "w-1", "changed_files": ["brief.pdf"]}])
        self.assertFalse(gate["ok"])
        self.assertIn("not a readable PDF", gate["reason"])

    def test_a_pdf_with_no_extractable_text_is_not_verified(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 2,
                                      "text_chars": 0})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a PDF"},
            [{"workspace_id": "w-1", "changed_files": ["brief.pdf"]}])
        self.assertFalse(gate["ok"])

    def test_a_mission_without_a_pdf_has_no_gate(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 1,
                                      "text_chars": 10})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Write a summary"},
            [{"workspace_id": "w-1", "changed_files": ["artifacts/brief.pdf"]}])
        self.assertIsNone(gate)
        self.assertEqual(client.calls, [])

    def test_an_empty_workspace_diff_fails_the_gate(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 1,
                                      "text_chars": 10})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a PDF"},
            [{"workspace_id": "w-1", "changed_files": ["notes.txt"]}])
        self.assertFalse(gate["ok"])
        self.assertIn("no .pdf", gate["reason"])
        self.assertEqual(client.calls, [])

    def test_a_disabled_sandbox_leaves_the_verdict_to_the_model(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 1,
                                      "text_chars": 10}, enabled=False)
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a PDF"},
            [{"workspace_id": "w-1", "changed_files": ["brief.pdf"]}])
        self.assertIsNone(gate)
        self.assertEqual(client.calls, [])

    def test_criteria_alone_can_declare_the_pdf_expectation(self):
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 1,
                                      "text_chars": 10})
        expects = self.helpers(client)["_mission_expects_pdf"](
            {"objective": "Write a document", "success_criteria": ["Ship a real PDF"]})
        self.assertTrue(expects)

    def test_a_task_without_a_pdf_candidate_is_not_gated(self):
        """Un task intermedio non deve fallire per un PDF che non ha ancora prodotto.

        `create-workspace` e `write-pdf-script` non hanno `.pdf` nel diff: a livello
        task il gate tace (`None`) e lascia parlare il verdetto del modello; solo la
        missione pretende che un PDF esista (2026-10-07, missione di briefing).
        """
        client = _FakeInspectSandbox({"ok": True, "magic_ok": True, "pages": 1,
                                      "text_chars": 10})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a PDF"},
            [{"workspace_id": "w-1", "changed_files": []}], "task")
        self.assertIsNone(gate)
        self.assertEqual(client.calls, [])

    def test_a_task_that_produced_a_bad_pdf_is_still_gated(self):
        """A livello task il gate scatta solo se il task ha davvero prodotto un .pdf."""
        client = _FakeInspectSandbox({"ok": True, "magic_ok": False, "pages": None,
                                      "text_chars": None})
        gate = self.helpers(client)["_mission_pdf_gate"](
            {"objective": "Produce a PDF"},
            [{"workspace_id": "w-1", "changed_files": ["artifacts/brief.pdf"]}], "task")
        self.assertFalse(gate["ok"])
        self.assertEqual(client.calls, [("inspect", {"workspace_id": "w-1",
                                                     "path": "artifacts/brief.pdf"})])


class MissionInferenceEndpointTests(unittest.TestCase):
    """`MISSION_INFERENCE_URL` devia la SOLA missione, senza toccare chat e canali.

    Serve a provare un modello servito fuori da Ollama (es. Bonsai 2 27B su
    `llama-server`) senza cambiare l'inferenza del resto del control-plane:
    planner, worker e verifier leggono un endpoint da un solo posto. Vuota =
    comportamento di prima (l'Ollama del CP), e in quel caso la fonte resta
    `advanced_config`, che `set_advanced_config` puo' cambiare a caldo.
    """

    @staticmethod
    def base(env_url, cp_url):
        tree = ast.parse(MAIN_SOURCE)
        module = ast.Module(
            body=[node for node in tree.body
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "_mission_inference_base"],
            type_ignores=[])
        namespace = {"MISSION_INFERENCE_URL": env_url,
                     "advanced_config": {"ollama": {"url": cp_url}}}
        exec(compile(module, "<mission-inference-base>", "exec"), namespace)
        return namespace["_mission_inference_base"]

    def test_an_override_moves_only_the_mission(self):
        base = self.base("http://host.docker.internal:8080/", "http://ollama.invalid")
        self.assertEqual(base(), "http://host.docker.internal:8080")

    def test_without_an_override_the_control_plane_ollama_is_used(self):
        base = self.base("", "http://host.docker.internal:11434/")
        self.assertEqual(base(), "http://host.docker.internal:11434")

    def test_the_worker_does_not_cable_the_endpoint_by_hand(self):
        """Solo `_mission_inference_base` conosce l'URL: il worker lo chiede."""
        source = functions(ROOT / "control-plane" / "main.py")["_mission_worker"]
        unparsed = ast.unparse(source)
        self.assertIn("_mission_inference_base", unparsed)
        self.assertNotIn("advanced_config", unparsed)


if __name__ == "__main__":
    unittest.main()
