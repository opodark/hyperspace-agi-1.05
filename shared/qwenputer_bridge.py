# SPDX-License-Identifier: Apache-2.0
# shared/qwenputer_bridge.py
"""Bridge Sovrano per Qwenputer & Esecuzione Deterministica In-Weight RISC-V.

Integra il paradigma architetturale di `chipformer` / `qwenputer` (Divyansh Agrawal):
1. [In-Weight CPU]: Compilazione di logica digitale 32-bit RISC-V (RV32IM + Zba)
   direttamente dentro le matrici e gli strati di attenzione del modello neurale.
2. [Gated DeltaNet as RAM]: Uso dello stato ricorrente Gated DeltaNet come banchi
   di memoria RAM a scrittura atomica deterministica (senza allucinazioni).
3. [Zero-Escape Sandbox]: Esecuzione di codice non fidato o calcoli formali
   all'interno della GPU / forward pass, senza toccare il kernel del sistema operativo host.
4. [Mesh Dispatch Multi-Nodo]: Diagnostica e verifica di prontezza sui nodi del cluster
   (Mac M5 Hub, HP OMEN 16 RTX 3070, ASUS V16 48GB).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Modulo extra installato da scripts/install_qwenputer.sh / install-qwenputer.ps1
QWENPUTER_DIR = Path(os.getenv("QWENPUTER_DIR") or ROOT / "modules" / "qwenputer")
RV_DIR = QWENPUTER_DIR / "experimental" / "riscv"
if str(RV_DIR) not in sys.path and RV_DIR.exists():
    sys.path.insert(0, str(RV_DIR))

# Endpoint dei nodi mesh
OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081").rstrip("/")
ASUS_NODE_URL = os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081").rstrip("/")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434").rstrip("/")
LOCAL_COCKPIT_URL = os.getenv("LOCAL_COCKPIT_URL", "http://127.0.0.1:8090").rstrip("/")

CALC_ELF = RV_DIR / "tests" / "data" / "rv" / "calc-bridge.elf"


class QwenputerBridge:
    """Interfaccia sovrana per l'esecuzione RISC-V in-weight e multi-nodo."""

    def __init__(self, rv_dir: Optional[Path] = None):
        self.rv_dir = rv_dir or RV_DIR
        self._ensure_sys_path()

    def _ensure_sys_path(self):
        if self.rv_dir.exists() and str(self.rv_dir) not in sys.path:
            sys.path.insert(0, str(self.rv_dir))

    def is_local_runtime_available(self) -> bool:
        """Verifica se il toolkit chipformer/qwenputer è presente localmente."""
        self._ensure_sys_path()
        try:
            import chipformer.rv.asm as asm  # noqa: F401
            import chipformer.rv.ref as ref  # noqa: F401
            return True
        except ImportError:
            return False

    def execute_riscv_asm(
        self,
        asm_source: str,
        initial_regs: Optional[Dict[str, int]] = None,
        max_steps: int = 100_000,
    ) -> Dict[str, Any]:
        """Assembla ed esegue un programma RISC-V RV32IM sul core di riferimento.
        
        Args:
            asm_source: Codice sorgente assembly RISC-V (istruzioni ADDI, ADD, SUB, MUL, JAL, ECALL).
            initial_regs: Valori iniziali opzionali per i registri (es. {"a0": 10, "a1": 20}).
            max_steps: Soglia massima di istruzioni prima di forzare timeout per loop infiniti.
        """
        self._ensure_sys_path()
        if not self.is_local_runtime_available():
            return {
                "success": False,
                "error": f"Modulo extra qwenputer non installato in {QWENPUTER_DIR} "
                         "(bash scripts/install_qwenputer.sh)",
            }

        try:
            from chipformer.rv import asm, ref

            prog = asm.assemble(asm_source)
            mach = ref.Machine.from_program(prog)

            # Inizializza registri specificati
            if initial_regs:
                for reg_name, val in initial_regs.items():
                    reg_idx = asm.REG.get(reg_name.lower())
                    if reg_idx is not None and 0 <= reg_idx < 32:
                        mach.x[reg_idx] = val & 0xFFFFFFFF

            t0 = time.perf_counter()
            # Esecuzione del trace completo tramite il motore di riferimento
            toks = mach.run(max_records=max_steps)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

            # Mappa i registri di output ABI
            regs_map = {}
            for i, name in enumerate(asm.ABI):
                regs_map[name] = mach.x[i]

            exit_val = mach.x[10]  # a0 (exit status convenzionale)
            is_halted = bool(mach.halted)
            timeout = len(toks) >= max_steps and not is_halted

            return {
                "success": is_halted and not timeout,
                "halted": is_halted,
                "timeout": timeout,
                "steps": mach.steps,
                "trace_tokens_count": len(toks),
                "elapsed_ms": elapsed_ms,
                "exit_code": exit_val,
                "registers": regs_map,
                "a0": regs_map.get("a0", 0),
                "a1": regs_map.get("a1", 0),
                "a2": regs_map.get("a2", 0),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Errore esecuzione RISC-V: {exc}",
            }

    def execute_calc_expression(self, expression: str) -> Dict[str, Any]:
        """Esegue un'espressione matematica tramite il firmware reale calc-bridge.elf,
        sulla macchina di riferimento RV32IM (`chipformer.rv.ref.Machine`).

        Non è ancora l'esecuzione "in-weight" dentro i pesi di Qwen3.5-4B (per quella
        serve il modello compilato reale su GPU CUDA, non disponibile qui): è però la
        stessa macchina di riferimento che il progetto usa per verificare che il
        circuito compilato sia ISA-corretto, e il risultato esce dal firmware C
        compilato in ELF — non da un `eval()` Python. Il buffer di testo P3 viene
        scritto a mano (righe NUL-padded da `TEXT_ROW` byte, a partire dalla riga 1),
        bypassando il tokenizer Qwen, che richiederebbe il checkpoint HF scaricato.
        """
        self._ensure_sys_path()
        if not CALC_ELF.exists():
            return {
                "success": False,
                "error": f"Firmware calc-bridge non trovato: {CALC_ELF}",
            }

        clean_expr = expression.strip()
        if not all(c in "0123456789+-*/()%.^ \n" for c in clean_expr):
            return {
                "success": False,
                "error": f"Caratteri non ammessi nell'espressione: {expression}",
            }

        try:
            from chipformer.rv import bridge as BR
            from chipformer.rv import elf, ref
            from chipformer.rv import spec as S

            prog = elf.program(str(CALC_ELF))
            mach = ref.Machine.from_program(prog)
            BR.park(mach)  # porta il firmware al primo "parcheggio" (pronto per un input)

            # Corpo del tool-call P3 così come lo cattura shared/../bridge.py::Session.qwen,
            # cioè tutto fra <tool_call> (escluso) e </tool_call> (escluso).
            body = f"\n<function=calc>\n<parameter=expression>\n{clean_expr}\n</parameter>\n</function>\n"
            body_bytes = body.encode("utf-8")
            rows: List[bytes] = [bytes(S.TEXT_ROW)] * S.TEXT_ROWS
            for i in range(0, len(body_bytes), S.TEXT_ROW):
                row_idx = 1 + i // S.TEXT_ROW
                if row_idx >= S.TEXT_ROWS:
                    return {"success": False, "error": "Espressione troppo lunga per il buffer P3"}
                rows[row_idx] = body_bytes[i : i + S.TEXT_ROW].ljust(S.TEXT_ROW, b"\0")
            mach.text = rows

            out_before = len(mach.out)
            mach.halted = False
            t0 = time.perf_counter()
            mach.run(max_records=200_000)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

            raw_out = bytes(mach.out[out_before:]).decode("utf-8", errors="replace")
            # Eseguendo sulla macchina di riferimento pura (non sul circuito IR), i marcatori
            # P3 (<tool_response>, <think>, ...) sono token speciali >255: il putchar reale
            # (ecall a7=1) li tronca a un byte (`a0 & 0xFF`), quindi non arrivano come ASCII
            # letterale. Il risultato numerico resta comunque intatto fra gli spazi vuoti.
            result_val = next((line.strip() for line in raw_out.splitlines() if line.strip()), None)

            if result_val is None:
                return {
                    "success": False,
                    "error": f"Il firmware non ha restituito un <tool_response> valido: {raw_out!r}",
                    "raw_output": raw_out,
                }

            return {
                "success": True,
                "expression": expression,
                "result": result_val,
                "steps_simulated": mach.steps,
                "firmware": CALC_ELF.name,
                "elapsed_ms": elapsed_ms,
                "deterministic": True,
                "executed_by": "chipformer.rv.ref.Machine (firmware ELF reale, non eval Python)",
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Errore calcolo calc-bridge: {exc}",
            }

    def check_mesh_nodes_readiness(self) -> Dict[str, Any]:
        """Ispeziona tutti i nodi del cluster per verificare la compatibilità con Qwenputer."""
        report = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "nodes": {},
            "cluster_ready": False,
        }

        # 1. Mac M5 Hub (Master Locale)
        mac_status = {
            "role": "Master Hub & Cognitive Coordinator",
            "os": "macOS (Apple Silicon M5)",
            "local_qwenputer_repo": QWENPUTER_DIR.exists(),
            "local_circuit_runtime": self.is_local_runtime_available(),
            "python_env": sys.version.split()[0],
            "mps_available": False,
            "status": "ready" if self.is_local_runtime_available() else "partial",
        }
        try:
            import torch
            mac_status["torch_version"] = torch.__version__
            mac_status["mps_available"] = bool(torch.backends.mps.is_available())
        except ImportError:
            pass
        report["nodes"]["mac_m5_hub"] = mac_status

        # 2. HP OMEN 16 (GPU Node - RTX 3070 8GB VRAM)
        omen_status = {
            "role": "GPU Heavy Engine & Causal Dreamer",
            "endpoint": OMEN_NODE_URL,
            "reachable": False,
            "tier": "unknown",
            "vram_profile": "NVIDIA RTX 3070 8GB GDDR6 (da specifiche note, non verificato via API)",
            "cuda_triton_ready": None,  # non verificato: nessuna probe CUDA/Triton reale eseguita
            "status": "offline",
        }
        try:
            req = urllib.request.urlopen(f"{OMEN_NODE_URL}/health", timeout=3)
            if req.getcode() == 200:
                data = json.loads(req.read().decode("utf-8"))
                omen_status["reachable"] = True
                omen_status["tier"] = data.get("tier", "unknown")
                omen_status["node_id"] = data.get("node_id", "")
                omen_status["status"] = "ready"
        except Exception as exc:
            omen_status["error"] = str(exc)
        report["nodes"]["hp_omen_16"] = omen_status

        # 3. ASUS V16 (High RAM Node - 48GB Pool)
        asus_status = {
            "role": "High Memory Pool & Deep Context Buffer (48GB)",
            "endpoint": ASUS_NODE_URL,
            "reachable": False,
            "memory_pool": "48GB DDR5 (Ideal for Unquantized QwenPU & DeltaNet Filesystem)",
            "status": "standby_or_offline",
        }
        try:
            req = urllib.request.urlopen(f"{ASUS_NODE_URL}/health", timeout=2)
            if req.getcode() == 200:
                asus_status["reachable"] = True
                asus_status["status"] = "ready"
        except Exception as exc:
            asus_status["note"] = f"Standby/Timeout: {exc}"
        report["nodes"]["asus_v16"] = asus_status

        # Valutazione globale
        # Il cluster è pronto se il Mac Hub ha il runtime e almeno uno tra OMEN o Mac è attivo
        report["cluster_ready"] = mac_status["local_circuit_runtime"] and (
            omen_status["reachable"] or mac_status["status"] == "ready"
        )
        return report
