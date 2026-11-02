# SPDX-License-Identifier: Apache-2.0
# tests/test_qwenputer_bridge.py
"""Test unitari per shared/qwenputer_bridge.py, l'in-weight RISC-V execution e la verifica Clean-Room REA."""

import json
from pathlib import Path
import tempfile
import unittest

from shared.memory_schema import REFUTED, VERIFIED, validate_evidence
from shared.qwenputer_bridge import REA_JOBS_DIR, RV_DIR, QwenputerBridge


@unittest.skipUnless(
    QwenputerBridge().is_local_runtime_available(),
    "modulo extra qwenputer non installato (bash scripts/install_qwenputer.sh)",
)
class TestQwenputerBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = QwenputerBridge()
        self.rv_data_dir = RV_DIR / "tests" / "data" / "rv"

    def test_local_runtime_available(self):
        """Verifica che il runtime chipformer/qwenputer sia reperibile."""
        self.assertTrue(self.bridge.is_local_runtime_available())

    def test_riscv_asm_arithmetic(self):
        """Verifica l'esecuzione di calcoli base su registri RISC-V e il trace_hash."""
        source = """
        li a0, 35
        li a1, 65
        add a0, a0, a1
        li a7, 93
        ecall
        """
        res = self.bridge.execute_riscv_asm(source)
        self.assertTrue(res["success"])
        self.assertEqual(res["a0"], 100)
        self.assertEqual(res["exit_code"], 100)
        self.assertGreater(res["steps"], 0)
        self.assertTrue(res["halted"])
        self.assertEqual(len(res["trace_hash"]), 64)

    def test_riscv_asm_loop_and_mult(self):
        """Verifica cicli di branching e moltiplicazione hardware (RV32M)."""
        # Calcolo fattoriale di 4: 4 * 3 * 2 * 1 = 24
        source = """
        li a0, 4
        li a1, 1
        fact_loop:
            mul a1, a1, a0
            addi a0, a0, -1
            bgtz a0, fact_loop
        mv a0, a1
        li a7, 93
        ecall
        """
        res = self.bridge.execute_riscv_asm(source)
        self.assertTrue(res["success"])
        self.assertEqual(res["a0"], 24)
        self.assertFalse(res["timeout"])

    def test_calc_expression_exact_bignum_and_rv32_elf(self):
        """Verifica l'esecuzione reale di calc-bridge.elf nella CPU RV32IM + Bignum."""
        res_mul = self.bridge.execute_calc_expression("123456789 * 987654321")
        self.assertTrue(res_mul["success"])
        self.assertEqual(res_mul["result"], "121932631112635269")
        self.assertTrue(res_mul["deterministic"])
        self.assertGreater(res_mul["steps_executed"], 1000)
        self.assertEqual(len(res_mul["trace_hash"]), 64)

        res_gcd = self.bridge.execute_calc_expression("gcd(1071, 462)")
        self.assertTrue(res_gcd["success"])
        self.assertEqual(res_gcd["result"], "21")

        res_frac = self.bridge.execute_calc_expression("84/18")
        self.assertTrue(res_frac["success"])
        self.assertEqual(res_frac["result"], "14/3")

    def test_calc_expression_invalid_input(self):
        """Verifica che input non numerici o potenzialmente malevoli vengano rifiutati."""
        bad_expr = "import os; os.system('ls')"
        res = self.bridge.execute_calc_expression(bad_expr)
        self.assertFalse(res["success"])
        self.assertIn("Caratteri non ammessi", res.get("error", ""))

    def test_inspect_and_disassemble_rv32_elf(self):
        """Verifica l'ispezione statica e il disassemblaggio di ELF32 RV32IM soft-float."""
        crc_elf = self.rv_data_dir / "c-crc32.elf"
        calc_elf = self.rv_data_dir / "calc-bridge.elf"

        info_crc = self.bridge.inspect_rv32_elf(crc_elf)
        self.assertTrue(info_crc["success"])
        self.assertFalse(info_crc["elf_header"]["rea_ghidra_lane_admitted"])
        self.assertTrue(info_crc["elf_header"]["qwenputer_rom_map_compatible"])
        self.assertEqual(info_crc["instruction_audit"]["illegal_instructions_count"], 0)

        info_calc = self.bridge.inspect_rv32_elf(calc_elf)
        self.assertTrue(info_calc["success"])
        self.assertGreater(info_calc["instruction_audit"]["custom_bignum_instructions_count"], 0)

        dis_main = self.bridge.disassemble_rv32_function(crc_elf, "main")
        self.assertTrue(dis_main["success"])
        self.assertGreater(dis_main["instruction_count"], 10)
        mnemonics = [i["mnemonic"] for i in dis_main["instructions"]]
        self.assertTrue(any(m.startswith("xor ") for m in mnemonics))
        self.assertTrue(any(m.startswith("jalr ") for m in mnemonics))

    def test_execute_rv32_elf_crc32(self):
        """Verifica l'esecuzione clean-room di un binario ELF32 RV32IM (c-crc32.elf)."""
        crc_elf = self.rv_data_dir / "c-crc32.elf"
        res = self.bridge.execute_rv32_elf(crc_elf)
        self.assertTrue(res["success"])
        self.assertEqual(res["exit_code"], 1095738169)
        self.assertEqual(len(res["trace_hash"]), 64)

    def test_verify_cleanroom_equivalence_verified_and_refuted(self):
        """Verifica la certificazione clean-room (VERIFIED e REFUTED) con schema evidence valido."""
        asm_parse_input = """
            mv a1, a0
            li a0, 0
        loop:
            lbu t0, 0(a1)
            beq t0, zero, done
            addi a0, a0, 6
            add a0, a0, t0
            addi a1, a1, 1
            j loop
        done:
            li a7, 93
            ecall
        """
        vectors_ok = [
            {
                "name": "empty_string",
                "initial_regs": {"a0": 0x200},
                "initial_mem": {0x200: b"\x00"},
                "expected_regs": {"a0": 0},
                "expected_exit_code": 0,
            },
            {
                "name": "string_ciao",
                "initial_regs": {"a0": 0x200},
                "initial_mem": {0x200: b"ciao\x00"},
                "expected_regs": {"a0": 436},
                "expected_exit_code": 436,
            },
        ]
        res_ok = self.bridge.verify_cleanroom_equivalence(asm_parse_input, vectors_ok)
        self.assertTrue(res_ok["success"])
        self.assertEqual(res_ok["verdict"], VERIFIED)
        self.assertEqual(res_ok["vectors_passed"], 2)
        self.assertEqual(validate_evidence(res_ok["evidence"]), [])

        vectors_bad = [
            {
                "name": "wrong_expectation",
                "initial_regs": {"a0": 0x200},
                "initial_mem": {0x200: b"ciao\x00"},
                "expected_regs": {"a0": 999},
                "expected_exit_code": 999,
            }
        ]
        res_bad = self.bridge.verify_cleanroom_equivalence(asm_parse_input, vectors_bad)
        self.assertFalse(res_bad["success"])
        self.assertEqual(res_bad["verdict"], REFUTED)
        self.assertEqual(validate_evidence(res_bad["evidence"]), [])

    def test_prepare_rea_cleanroom_bundle_fixture_and_live(self):
        """Verifica il collegamento tra un job statico REA (Ghidra) e la camera bianca Qwenputer."""
        asm_parse_input = """
            mv a1, a0
            li a0, 0
        loop:
            lbu t0, 0(a1)
            beq t0, zero, done
            addi a0, a0, 6
            add a0, a0, t0
            addi a1, a1, 1
            j loop
        done:
            li a7, 93
            ecall
        """
        vectors = [
            {
                "name": "string_A",
                "initial_regs": {"a0": 0x200},
                "initial_mem": {0x200: b"A\x00"},
                "expected_regs": {"a0": 71},
                "expected_exit_code": 71,
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir) / "mock_job"
            job_dir.mkdir()
            (job_dir / "job.json").write_text(
                json.dumps({
                    "id": "mock_job",
                    "op": "decompile",
                    "argomento": "0x100000460",
                    "provider": "ghidra",
                    "target": {"nome": "prova_nativa", "sha256": "a" * 64},
                }),
                encoding="utf-8",
            )
            (job_dir / "stdout.json").write_text(
                json.dumps({
                    "evidence_id": "ev_" + "b" * 64,
                    "normalized_result": "int _parse_input(char *p) { ... }",
                }),
                encoding="utf-8",
            )
            bundle = self.bridge.prepare_rea_cleanroom_bundle(job_dir, asm_parse_input, vectors)
            self.assertTrue(bundle["success"])
            self.assertEqual(bundle["verdict"], VERIFIED)
            self.assertFalse(bundle["static_provenance"]["target_executed_on_host"])
            self.assertEqual(bundle["static_provenance"]["target_sha256"], "a" * 64)

        real_job = REA_JOBS_DIR / "4c8555419121"
        if real_job.exists():
            real_bundle = self.bridge.prepare_rea_cleanroom_bundle("4c8555419121", asm_parse_input, vectors)
            self.assertTrue(real_bundle["success"])
            self.assertEqual(real_bundle["verdict"], VERIFIED)
            self.assertEqual(
                real_bundle["static_provenance"]["target_sha256"],
                "2b066d2f9ab75263641f35b68a63493a8c70e559451e5c60c23a1483a9bd1b87",
            )

    def test_mesh_nodes_readiness_structure(self):
        """Verifica la struttura del report di diagnostica mesh."""
        report = self.bridge.check_mesh_nodes_readiness()
        self.assertIn("timestamp", report)
        self.assertIn("nodes", report)
        self.assertIn("cluster_ready", report)
        nodes = report["nodes"]
        self.assertIn("mac_m5_hub", nodes)
        self.assertIn("hp_omen_16", nodes)
        self.assertIn("asus_v16", nodes)
        self.assertEqual(nodes["mac_m5_hub"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
