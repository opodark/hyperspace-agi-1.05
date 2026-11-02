# SPDX-License-Identifier: Apache-2.0
# tests/test_qwenputer_bridge.py
"""Test unitari per shared/qwenputer_bridge.py e l'in-weight RISC-V execution."""

import unittest
from shared.qwenputer_bridge import QwenputerBridge


@unittest.skipUnless(
    QwenputerBridge().is_local_runtime_available(),
    "modulo extra qwenputer non installato (bash scripts/install_qwenputer.sh)",
)
class TestQwenputerBridge(unittest.TestCase):
    def setUp(self):
        self.bridge = QwenputerBridge()

    def test_local_runtime_available(self):
        """Verifica che il runtime chipformer/qwenputer sia reperibile."""
        self.assertTrue(self.bridge.is_local_runtime_available())

    def test_riscv_asm_arithmetic(self):
        """Verifica l'esecuzione di calcoli base su registri RISC-V."""
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

    def test_calc_expression_exact_bignum(self):
        """Verifica l'aritmetica a precisione arbitraria senza float drift."""
        expr = "123456789 * 987654321"
        res = self.bridge.execute_calc_expression(expr)
        self.assertTrue(res["success"])
        self.assertEqual(res["result"], "121932631112635269")
        self.assertTrue(res["deterministic"])

    def test_calc_expression_invalid_input(self):
        """Verifica che input non numerici o potenzialmente malevoli vengano rifiutati."""
        bad_expr = "import os; os.system('ls')"
        res = self.bridge.execute_calc_expression(bad_expr)
        self.assertFalse(res["success"])
        self.assertIn("Caratteri non ammessi", res.get("error", ""))

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
