# SPDX-License-Identifier: Apache-2.0
import ast
import unittest
from pathlib import Path

from shared import mission_policy as policy
from shared.mission import validate_dag


ROOT = Path(__file__).parents[1]

FAKE_CATALOG = [
    {"type": "function", "function": {"name": "web_search"}},
    {"type": "function", "function": {"name": "omega_query"}},
    {"type": "function", "function": {"name": "omega_store"}},
    {"type": "function", "function": {"name": "code_sandbox"}},
    {"type": "function", "function": {"name": "create_website"}},
    {"type": "function", "function": {"name": "get_mesh_status"}},
    {"type": "function", "function": {"name": "website_status"}},
    {"type": "function", "function": {"name": "shell_run"}},
]


class ManifestTests(unittest.TestCase):
    def test_manifest_tool_names_exist_in_control_plane_catalog(self):
        """A typo in a manifest would silently grant fewer tools — catch it."""
        source = (ROOT / "control-plane" / "cp" / "tools_defs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        catalog = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == "_NATIVE_TOOLS"
                    for target in node.targets):
                catalog.update(item["function"]["name"] for item in ast.literal_eval(node.value))
            elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                  and isinstance(node.value.func, ast.Attribute)
                  and node.value.func.attr == "extend"):
                catalog.update(item["function"]["name"]
                               for item in ast.literal_eval(node.value.args[0]))
        for role, manifest in policy.ROLE_MANIFESTS.items():
            for tool in manifest["tools"]:
                self.assertIn(tool, catalog,
                              f"{role} references unknown tool {tool}")

    def test_planner_and_worker_defaults_are_distinct(self):
        self.assertEqual(policy.resolve_manifest("planner")["tools"], [])
        self.assertIn("code_sandbox", policy.resolve_manifest("coder")["tools"])
        self.assertNotIn("code_sandbox", policy.resolve_manifest("worker")["tools"])

    def test_unknown_role_falls_back_to_conservative_worker(self):
        manifest = policy.resolve_manifest("totally-made-up")
        self.assertEqual(manifest["role"], "worker")
        self.assertNotIn("code_sandbox", manifest["tools"])

    def test_coder_requires_review_but_analyst_does_not(self):
        self.assertTrue(policy.review_required("coder"))
        self.assertFalse(policy.review_required("repo-analyst"))

    def test_ops_agent_is_locked_until_flag_is_set(self):
        self.assertEqual(policy.resolve_manifest("ops-agent")["tools"], [])
        self.assertTrue(policy._ops_agent_enabled() in (True, False))
        self.assertNotIn("shell_run", policy.resolve_manifest("worker")["tools"])

    def test_tools_for_role_intersects_catalog_and_preserves_order(self):
        names = [t["function"]["name"] for t in policy.tools_for_role("repo-analyst", FAKE_CATALOG)]
        self.assertEqual(names, ["web_search", "omega_query", "get_mesh_status"])
        self.assertEqual(policy.tools_for_role("planner", FAKE_CATALOG), [])
        self.assertEqual(policy.tools_for_role("coder", FAKE_CATALOG),
                         [{"type": "function", "function": {"name": "code_sandbox"}},
                          {"type": "function", "function": {"name": "create_website"}}])

    def test_only_the_coder_owns_the_static_site_builder(self):
        """`create_website` scrive fuori dalla sandbox: un solo ruolo lo possiede.

        Il sandbox non monta la raccolta ComfyUI delle foto di Anna, quindi
        senza questo tool una missione non può costruire una pagina con la
        galleria. I ruoli read-only e il verifier restano senza: il verifier
        giudica, non costruisce.
        """
        self.assertIn("create_website", policy.resolve_manifest("coder")["tools"])
        for role in ("planner", "repo-analyst", "verifier", "memory-agent", "worker"):
            with self.subTest(role=role):
                self.assertNotIn("create_website", policy.resolve_manifest(role)["tools"])
        names = [t["function"]["name"]
                 for t in policy.tools_for_role("coder", FAKE_CATALOG)]
        self.assertIn("create_website", names)

    def test_the_verifier_can_read_the_static_site_but_never_build_it(self):
        tools = policy.resolve_manifest("verifier")["tools"]
        self.assertIn("website_status", tools)
        self.assertNotIn("create_website", tools)


class BudgetTests(unittest.TestCase):
    def test_defaults_when_nothing_is_set(self):
        budget = policy.parse_budget(env={})
        self.assertEqual(budget["max_concurrency"], policy.BUDGET_DEFAULTS["max_concurrency"])
        self.assertEqual(budget["max_steps"], policy.BUDGET_DEFAULTS["max_steps"])

    def test_env_overrides_defaults(self):
        budget = policy.parse_budget(env={"MISSION_MAX_STEPS": "7", "MISSION_MAX_CONCURRENCY": "3"})
        self.assertEqual(budget["max_steps"], 7)
        self.assertEqual(budget["max_concurrency"], 3)

    def test_request_overrides_win_over_env(self):
        budget = policy.parse_budget(env={"MISSION_MAX_STEPS": "7"}, overrides={"max_steps": 2})
        self.assertEqual(budget["max_steps"], 2)

    def test_values_are_clamped_to_safe_ranges(self):
        budget = policy.parse_budget(env={}, overrides={"max_concurrency": 999, "max_steps": 0,
                                                        "max_replans": -5})
        self.assertEqual(budget["max_concurrency"], policy.MAX_CONCURRENCY_CEILING)
        self.assertGreaterEqual(budget["max_steps"], 1)
        self.assertGreaterEqual(budget["max_replans"], 0)

    def test_bad_env_value_falls_back_to_default(self):
        budget = policy.parse_budget(env={"MISSION_MAX_STEPS": "not-a-number"})
        self.assertEqual(budget["max_steps"], policy.BUDGET_DEFAULTS["max_steps"])

    def test_exhaustion_checks_steps_replans_and_time(self):
        budget = policy.parse_budget(env={}, overrides={"max_steps": 5, "max_replans": 1,
                                                        "max_wall_seconds": 100})
        self.assertFalse(policy.budget_exhausted(budget, steps=5, replans=1, elapsed_seconds=100))
        self.assertTrue(policy.budget_exhausted(budget, steps=6, replans=0, elapsed_seconds=0))
        self.assertTrue(policy.budget_exhausted(budget, steps=0, replans=2, elapsed_seconds=0))
        self.assertTrue(policy.budget_exhausted(budget, steps=0, replans=0, elapsed_seconds=101))


class PlanNormalizationTests(unittest.TestCase):
    """Il piano di un modello da 8B deve arrivare valido a `validate_dag`.

    La regressione che questi test difendono è stata vista in produzione il
    2026-10-06: `granite3.3-g8k` ha scritto il tasto `check_page_includes` e la
    dipendenza dello stesso task come `check_page_includes`, ma il planner
    normalizzava *solo* il tasto (`check-page-includes`): lo store ha rifiutato
    l'intera missione con "task verify-routes depends on unknown task
    check_page_includes" — zero task eseguiti per un trattino basso.
    """

    @staticmethod
    def _as_the_planner_cleans(raw_tasks):
        """La stessa sequenza del planner: tasto unico, alias, dipendenze risolte."""
        taken, alias, tasks = set(), {}, []
        for index, raw in enumerate(raw_tasks):
            key = policy.task_key(raw.get("key"), f"t{index + 1}")
            while key in taken:
                key = f"{key}-{index + 1}"
            taken.add(key)
            if raw.get("key"):
                alias.setdefault(str(raw["key"]).strip(), key)
            alias.setdefault(key, key)
            tasks.append({"key": key, "role": raw.get("role", "worker"),
                          "dependencies": list(raw.get("dependencies") or [])})
        return policy.resolve_dependencies(tasks, alias)

    def test_the_underscore_plan_that_broke_the_mission_now_validates(self):
        tasks = self._as_the_planner_cleans([
            {"key": "check_page_includes", "role": "repo-analyst"},
            {"key": "verify-routes", "role": "coder", "dependencies": ["check_page_includes"]},
        ])
        self.assertEqual([t["key"] for t in tasks], ["check-page-includes", "verify-routes"])
        self.assertEqual(tasks[1]["dependencies"], ["check-page-includes"])
        validate_dag(tasks)  # non deve sollevare: è la regressione del 2026-10-06

    def test_task_key_is_the_only_normalization_rule(self):
        self.assertEqual(policy.task_key("Check_Page Includes"), "check-page-includes")
        # I separatori diventano `-` uno per uno, senza compressione: è la regola
        # che il planner applicava già ai tasti, ora condivisa con le dipendenze.
        self.assertEqual(policy.task_key("  Step__One  "), "step--one")
        self.assertEqual(policy.task_key("", "t3"), "t3")
        self.assertEqual(policy.task_key("___", "t1"), "t1")
        self.assertLessEqual(len(policy.task_key("x" * 200)), policy.KEY_MAX)

    def test_dependency_that_points_at_nothing_is_dropped_not_fatal(self):
        tasks = policy.resolve_dependencies([
            {"key": "a", "dependencies": []},
            {"key": "b", "dependencies": ["a", "mai-pianificato", "b"]},
        ])
        self.assertEqual(tasks[1]["dependencies"], ["a"])
        validate_dag(tasks)

    def test_dependency_written_with_spaces_or_caps_still_resolves(self):
        tasks = self._as_the_planner_cleans([
            {"key": "read the page", "role": "repo-analyst"},
            {"key": "verify", "role": "verifier", "dependencies": ["Read The Page"]},
        ])
        self.assertEqual(tasks[0]["key"], "read-the-page")
        self.assertEqual(tasks[1]["dependencies"], ["read-the-page"])

    def test_duplicate_keys_do_not_leave_dangling_dependencies(self):
        tasks = self._as_the_planner_cleans([
            {"key": "step", "role": "worker"},
            {"key": "step", "role": "coder"},
            {"key": "verify", "role": "verifier", "dependencies": ["step"]},
        ])
        self.assertEqual([t["key"] for t in tasks], ["step", "step-2", "verify"])
        self.assertEqual(tasks[2]["dependencies"], ["step"])
        validate_dag(tasks)

    def test_original_dependency_list_is_not_mutated(self):
        source = [{"key": "a", "dependencies": []},
                  {"key": "b", "dependencies": ["a"]}]
        policy.resolve_dependencies(source)
        self.assertEqual(source[1]["dependencies"], ["a"])


if __name__ == "__main__":
    unittest.main()
