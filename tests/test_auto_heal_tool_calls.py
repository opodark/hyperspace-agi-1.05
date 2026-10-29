# SPDX-License-Identifier: Apache-2.0
"""Test per l'Auto-Healing dei tool call emessi come testo (sintassi Qwen/Hermes/ChatML).

Quando un modello open-source emette `<|tool_call_start|>[func(arg=...)]<|tool_call_end|>`
nel testo della risposta invece che nel JSON OpenAI `tool_calls`, il Control Plane
lo converte al volo in un vero tool call strutturato per non rompere client come Cline.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "control-plane"))

from cp.chat import _extract_raw_tool_calls, _auto_heal_response_tool_calls


class TestAutoHealToolCalls(unittest.TestCase):
    def test_qwen_chatml_single_tool_call(self):
        text = (
            "Iniziamo esplorando la codebase di pole-motion-engine.\n\n"
            "<|tool_call_start|>[run_commands(command='find /Users/opo/pole-motion-engine -type f | head -100')]<|tool_call_end|>"
        )
        cleaned, calls = _extract_raw_tool_calls(text)
        self.assertEqual(cleaned, "Iniziamo esplorando la codebase di pole-motion-engine.")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "run_commands")
        args = json.loads(calls[0]["function"]["arguments"])
        self.assertEqual(args["command"], "find /Users/opo/pole-motion-engine -type f | head -100")

    def test_qwen_chatml_multiple_tool_calls(self):
        text = (
            "Eseguo due operazioni:\n"
            "<|tool_call_start|>[read_file(path='main.py'), list_dir(path='src')]<|tool_call_end|>"
        )
        cleaned, calls = _extract_raw_tool_calls(text)
        self.assertEqual(cleaned, "Eseguo due operazioni:")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["function"]["name"], "read_file")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"])["path"], "main.py")
        self.assertEqual(calls[1]["function"]["name"], "list_dir")
        self.assertEqual(json.loads(calls[1]["function"]["arguments"])["path"], "src")

    def test_xml_json_tool_call(self):
        text = (
            "Procedo alla lettura: "
            "<tool_call>{\"name\": \"execute_command\", \"arguments\": {\"cmd\": \"ls -la\"}}</tool_call>"
        )
        cleaned, calls = _extract_raw_tool_calls(text)
        self.assertEqual(cleaned, "Procedo alla lettura:")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["function"]["name"], "execute_command")
        self.assertEqual(json.loads(calls[0]["function"]["arguments"])["cmd"], "ls -la")

    def test_auto_heal_response_dict(self):
        fake_resp = {
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Analizzo il repo.\n<|tool_call_start|>[run_commands(command='git status')]<|tool_call_end|>"
                }
            }]
        }
        healed = _auto_heal_response_tool_calls(fake_resp)
        msg = healed["choices"][0]["message"]
        self.assertEqual(healed["choices"][0]["finish_reason"], "tool_calls")
        self.assertEqual(msg["content"], "Analizzo il repo.")
        self.assertIn("tool_calls", msg)
        self.assertEqual(len(msg["tool_calls"]), 1)
        self.assertEqual(msg["tool_calls"][0]["function"]["name"], "run_commands")

    def test_no_op_on_normal_text(self):
        normal_resp = {
            "choices": [{
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Questo è un normale messaggio senza tool."
                }
            }]
        }
        healed = _auto_heal_response_tool_calls(normal_resp)
        self.assertEqual(healed["choices"][0]["finish_reason"], "stop")
        self.assertNotIn("tool_calls", healed["choices"][0]["message"])

    def test_unclosed_block_with_complete_json_is_recovered(self):
        text = 'Leggo. <tool_call>{"name": "read_files", "arguments": {"files": [{"path": "AGENTS.md"}]}}'
        cleaned, calls = _extract_raw_tool_calls(text)
        self.assertEqual(cleaned, "Leggo.")
        self.assertEqual([c["function"]["name"] for c in calls], ["read_files"])

    def test_unclosed_block_truncated_is_left_alone(self):
        text = "<think>ok</think><tool_call>run_commands"
        cleaned, calls = _extract_raw_tool_calls(text)
        self.assertEqual(calls, [])
        self.assertEqual(cleaned, text)

    def test_undeclared_tool_name_is_not_healed(self):
        resp = {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant",
            "content": "<tool_call>{\"name\": \"shell_command\", \"arguments\": {}}</tool_call>"}}]}
        healed = _auto_heal_response_tool_calls(resp, {"run_commands", "read_files"})
        self.assertEqual(healed["choices"][0]["finish_reason"], "stop")
        self.assertNotIn("tool_calls", healed["choices"][0]["message"])

    def test_declared_tool_name_is_healed(self):
        resp = {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant",
            "content": "<tool_call>{\"name\": \"run_commands\", \"arguments\": {}}</tool_call>"}}]}
        healed = _auto_heal_response_tool_calls(resp, {"run_commands"})
        self.assertEqual(healed["choices"][0]["finish_reason"], "tool_calls")


if __name__ == "__main__":
    unittest.main()
