# SPDX-License-Identifier: Apache-2.0
"""tests/test_endurance_validation.py.

I gate di validazione della sessione di endurance: un prototipo vuoto non e' "AST valida",
e un JSON citato nella prosa del modello non e' un handshake "STRICT JSON".
"""
from __future__ import annotations

import ast
import unittest

from scripts.diagnostics.mesh_1hour_endurance_session import has_substantive_code, parse_strict_json

REMEDIATION_KEYS = ("action_id", "target_node", "directive", "status")


class TestSubstantiveCode(unittest.TestCase):
    def test_empty_module_is_not_substantive(self):
        self.assertFalse(has_substantive_code(ast.parse("")))
        self.assertFalse(has_substantive_code(ast.parse("# solo commento\n")))

    def test_class_or_function_is_substantive(self):
        self.assertTrue(has_substantive_code(ast.parse("class A:\n    pass\n")))
        self.assertTrue(has_substantive_code(ast.parse("def f():\n    return 1\n")))
        self.assertTrue(has_substantive_code(ast.parse("async def f():\n    return 1\n")))


class TestStrictJson(unittest.TestCase):
    def test_plain_and_fenced_json_accepted(self):
        raw = '{"action_id":"a","target_node":"n","directive":"d","status":"dispatched"}'
        self.assertIsNotNone(parse_strict_json(raw, REMEDIATION_KEYS))
        self.assertIsNotNone(parse_strict_json(f"```json\n{raw}\n```", REMEDIATION_KEYS))
        self.assertIsNotNone(parse_strict_json(f"<think>ragiono</think>{raw}", REMEDIATION_KEYS))

    def test_reasoning_closed_by_unbalanced_think_tag_then_json_accepted(self):
        """Il <think> iniziale lo mette il template: nella risposta compare solo </think>."""
        raw = ('We need JSON. Thus final: {"action_id":"x"}\n\nThus final.</think>'
               '{"action_id":"a","target_node":"n","directive":"d","status":"dispatched"}')
        self.assertIsNotNone(parse_strict_json(raw, REMEDIATION_KEYS))

    def test_reasoning_truncated_before_think_close_is_rejected(self):
        truncated = 'We need to respond. The JSON would be {"action_id":"a","target_node":"n","directive":"d","status":"s"} but'
        self.assertIsNone(parse_strict_json(truncated, REMEDIATION_KEYS))

    def test_reasoning_prose_quoting_the_prompt_is_rejected(self):
        leaked = ('We need to parse the user\'s request. The user says: "Consuma questo evento ..."\n'
                  '{"action_id":"act-endurance-34","target_node":"asus-v16","directive":"x","status":"dispatched"}')
        self.assertIsNone(parse_strict_json(leaked, REMEDIATION_KEYS))

    def test_missing_keys_and_non_objects_rejected(self):
        self.assertIsNone(parse_strict_json('{"action_id":"a"}', REMEDIATION_KEYS))
        self.assertIsNone(parse_strict_json("[1, 2]"))
        self.assertIsNone(parse_strict_json(""))
        self.assertIsNone(parse_strict_json(None))


if __name__ == "__main__":
    unittest.main()
