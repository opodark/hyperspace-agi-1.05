# SPDX-License-Identifier: Apache-2.0
"""Unit tests per Universal Model Parser e Caveman Engine (shared/universal_model_parser.py)."""

from unittest import TestCase

from shared.universal_model_parser import CavemanEngine, UniversalModelParser


class CavemanEngineTests(TestCase):
    def test_compress_preserves_code_and_reduces_fluff(self):
        verbose_prompt = (
            "Please note that it is important to remember that in order to configure the system, "
            "you should execute the following code block:\n"
            "```python\ndef start():\n    print('ok')\n```\n"
            "Due to the fact that we need fast execution at the present time, kindly ensure this."
        )
        res = CavemanEngine.compress(verbose_prompt)
        compressed = res["compressed"]

        # Code block intact
        self.assertIn("def start():", compressed)
        self.assertIn("print('ok')", compressed)
        # Filler phrases removed or substituted
        self.assertNotIn("Please note that", compressed)
        self.assertNotIn("due to the fact that", compressed)
        self.assertIn("to configure", compressed)
        self.assertGreater(res["savings_pct"], 15.0)

    def test_compress_preserves_xml_and_paths(self):
        text = "<tool_call>{\"name\": \"get_status\", \"arguments\": {}}</tool_call>\nPath: /repo/shared/diario.py"
        res = CavemanEngine.compress(text)
        self.assertIn("<tool_call>", res["compressed"])
        self.assertIn("/repo/shared/diario.py", res["compressed"])


class UniversalModelParserTests(TestCase):
    def test_extract_reasoning_and_unclosed_cot(self):
        raw = "<think>Analyzing repository architecture and VRAM requirements.</think>Here is the final recommendation."
        cot, text = UniversalModelParser.extract_reasoning(raw)
        self.assertEqual(cot, "Analyzing repository architecture and VRAM requirements.")
        self.assertEqual(text, "Here is the final recommendation.")

        # Unclosed think tag (model cut off)
        unclosed = "<think>Analyzing dependencies and steps... Here is the code without end tag"
        cot_unclosed, text_unclosed = UniversalModelParser.extract_reasoning(unclosed)
        self.assertIn("Analyzing dependencies", cot_unclosed)

    def test_extract_code_ast_validation_and_unclosed_fence(self):
        # Python code with missing closing backticks
        raw_broken = "Here is the function:\n```python\ndef calculate(a: int, b: int) -> int:\n    return a + b\n"
        blocks = UniversalModelParser.extract_code(raw_broken)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].language, "python")
        self.assertTrue(blocks[0].is_valid_ast)
        self.assertIn("def calculate", blocks[0].code)

        # Syntax error detection
        raw_syntax_err = "```python\ndef broken(:\n    pass\n```"
        blocks_err = UniversalModelParser.extract_code(raw_syntax_err)
        self.assertEqual(len(blocks_err), 1)
        self.assertFalse(blocks_err[0].is_valid_ast)
        self.assertIn("SyntaxError", blocks_err[0].ast_error)

    def test_extract_tolerant_json_repairs(self):
        # 1. Single quotes & trailing comma
        messy_json = "{'name': 'hyperspace', 'tier': 'root', 'vram': 8.0,}"
        parsed = UniversalModelParser.extract_json(messy_json)
        self.assertIsInstance(parsed, dict)
        self.assertEqual(parsed.get("name"), "hyperspace")
        self.assertEqual(parsed.get("tier"), "root")
        self.assertEqual(parsed.get("vram"), 8.0)

        # 2. Unclosed braces at end of generation
        unclosed_json = '{"status": "ok", "items": [1, 2, 3'
        parsed_unclosed = UniversalModelParser.extract_json(unclosed_json)
        self.assertIsInstance(parsed_unclosed, dict)
        self.assertEqual(parsed_unclosed.get("status"), "ok")
        self.assertEqual(parsed_unclosed.get("items"), [1, 2, 3])

    def test_extract_tool_calls_qwen_and_mistral(self):
        # Qwen tag
        qwen_raw = '<tool_call>{"name": "check_gpu", "arguments": {"node": "omen"}}</tool_call>'
        calls = UniversalModelParser.extract_tool_calls(qwen_raw)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].name, "check_gpu")
        self.assertEqual(calls[0].arguments, {"node": "omen"})

        # Mistral tag
        mistral_raw = '[TOOL_CALLS] [{"name": "read_file", "arguments": {"path": "main.py"}}]'
        calls_m = UniversalModelParser.extract_tool_calls(mistral_raw)
        self.assertEqual(len(calls_m), 1)
        self.assertEqual(calls_m[0].name, "read_file")
        self.assertEqual(calls_m[0].arguments, {"path": "main.py"})

    def test_full_parse_pipeline(self):
        raw_response = (
            "<think>Need to generate a python utility for monitoring.</think>\n"
            "Here is the requested script:\n\n"
            "```python\ndef monitor():\n    return {'status': 'healthy'}\n```\n"
            "<tool_call>{\"name\": \"notify_operator\", \"arguments\": {\"msg\": \"done\"}}</tool_call>\n"
            "Task executed successfully."
        )
        res = UniversalModelParser.parse(raw_response)
        self.assertEqual(res.reasoning_cot, "Need to generate a python utility for monitoring.")
        self.assertEqual(len(res.code_blocks), 1)
        self.assertTrue(res.code_blocks[0].is_valid_ast)
        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].name, "notify_operator")
        self.assertIn("Task executed successfully", res.clean_text)
        self.assertTrue(res.has_valid_content)
