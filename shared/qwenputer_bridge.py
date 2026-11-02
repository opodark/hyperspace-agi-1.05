# SPDX-License-Identifier: Apache-2.0
# shared/qwenputer_bridge.py
"""Bridge Sovrano per Qwenputer, Ispezione ELF32 RV32IM & Clean-Room Verification con REA.

Integra il paradigma architetturale di `chipformer` / `qwenputer` (Divyansh Agrawal)
e lo salda con la superficie di analisi statica REA (`scripts/rea_surface.py`):
1. [In-Weight CPU]: Compilazione di logica digitale 32-bit RISC-V (RV32IM + Zba + Bignum)
   direttamente dentro le matrici e gli strati di attenzione del modello neurale.
2. [Gated DeltaNet as RAM]: Uso dello stato ricorrente Gated DeltaNet come banchi
   di memoria RAM a scrittura atomica deterministica (senza allucinazioni).
3. [Zero-Escape Sandbox & Clean-Room REA]:
   - Ispezione statica e disassemblaggio di binari ELF32 RV32IM soft-float (rifiutati
     dalla corsia Ghidra di REA che richiede `EF_RISCV_FLOAT_ABI_DOUBLE`).
   - Verifica dinamica clean-room delle funzioni estratte/decompilate da REA/Ghidra
     tramite vettori di test deterministici e `trace_hash` SHA-256.
4. [Mesh Dispatch Multi-Nodo]: Diagnostica e verifica di prontezza sui nodi del cluster
   (Mac M5 Hub, HP OMEN 16 RTX 3070, ASUS V16 48GB).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
from typing import Any, Dict, List, Optional, Union
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.memory_schema import PLAUSIBLE, REFUTED, SOURCED, VERIFIED, validate_evidence

# Percorso workspace di qwenputer (default: modules/qwenputer da install_qwenputer.sh, fallback: scratch/qwenputer)
_default_qwenputer_dir = ROOT / "modules" / "qwenputer"
if not _default_qwenputer_dir.exists() and (ROOT / "scratch" / "qwenputer").exists():
    _default_qwenputer_dir = ROOT / "scratch" / "qwenputer"
QWENPUTER_DIR = Path(os.getenv("QWENPUTER_DIR", str(_default_qwenputer_dir)))
RV_DIR = QWENPUTER_DIR / "experimental" / "riscv"
if str(RV_DIR) not in sys.path and RV_DIR.exists():
    sys.path.insert(0, str(RV_DIR))

# Endpoint dei nodi mesh
OMEN_NODE_URL = os.getenv("OMEN_NODE_URL", "http://100.104.238.125:8081").rstrip("/")
ASUS_NODE_URL = os.getenv("ASUS_NODE_URL", "http://100.64.31.18:8081").rstrip("/")
ASUS_OLLAMA_URL = os.getenv("ASUS_OLLAMA_URL", "http://100.64.31.18:11434").rstrip("/")
LOCAL_COCKPIT_URL = os.getenv("LOCAL_COCKPIT_URL", "http://127.0.0.1:8090").rstrip("/")

CALC_ELF = RV_DIR / "tests" / "data" / "rv" / "calc-bridge.elf"
REA_JOBS_DIR = ROOT / "data" / "rea" / "jobs"

EM_RISCV = 243
EF_RISCV_RVC = 0x0001
EF_RISCV_FLOAT_ABI_MASK = 0x0006
EF_RISCV_FLOAT_ABI_SOFT = 0x0000
EF_RISCV_FLOAT_ABI_SINGLE = 0x0002
EF_RISCV_FLOAT_ABI_DOUBLE = 0x0004
EF_RISCV_FLOAT_ABI_QUAD = 0x0006


def _hash_trace_tokens(toks: List[int]) -> str:
    """Calcola l'impronta SHA-256 deterministica di uno stream di token di traccia RV32."""
    h = hashlib.sha256()
    for t in toks:
        h.update(int(t & 0xFFFFFFFF).to_bytes(4, "little", signed=False))
    return h.hexdigest()


def _format_instruction_mnemonic(ins: Any, abi_names: List[str]) -> str:
    """Formatta un oggetto Inst di chipformer.rv.ref in assembly leggibile con registri ABI."""
    op = ins.op.lower()
    rd = abi_names[ins.rd] if 0 <= ins.rd < len(abi_names) else f"x{ins.rd}"
    rs1 = abi_names[ins.rs1] if 0 <= ins.rs1 < len(abi_names) else f"x{ins.rs1}"
    rs2 = abi_names[ins.rs2] if 0 <= ins.rs2 < len(abi_names) else f"x{ins.rs2}"

    if ins.op in ("ECALL", "EBREAK", "FENCE", "ILLEGAL"):
        return op
    if ins.op in ("LUI", "AUIPC"):
        return f"{op} {rd}, {hex((ins.imm >> 12) & 0xFFFFF)}"
    if ins.op == "JAL":
        return f"{op} {rd}, {ins.imm:+d}"
    if ins.op == "JALR":
        return f"{op} {rd}, {ins.imm}({rs1})"
    if ins.op in ("BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU"):
        return f"{op} {rs1}, {rs2}, {ins.imm:+d}"
    if ins.op in ("LB", "LH", "LW", "LBU", "LHU"):
        return f"{op} {rd}, {ins.imm}({rs1})"
    if ins.op in ("SB", "SH", "SW"):
        return f"{op} {rs2}, {ins.imm}({rs1})"
    if ins.op in ("ADDI", "SLTI", "SLTIU", "XORI", "ORI", "ANDI", "SLLI", "SRLI", "SRAI"):
        return f"{op} {rd}, {rs1}, {ins.imm}"
    if ins.op == "BPRD":
        return f"{op} d{ins.dd}, {ins.imm}"
    return f"{op} {rd}, {rs1}, {rs2}"


class QwenputerBridge:
    """Interfaccia sovrana per esecuzione RISC-V in-weight, ispezione ELF32 e ponte REA."""

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
        initial_mem: Optional[Dict[int, Union[bytes, bytearray]]] = None,
        max_steps: int = 100_000,
    ) -> Dict[str, Any]:
        """Assembla ed esegue un programma RISC-V RV32IM sul core di riferimento.

        Args:
            asm_source: Codice sorgente assembly RISC-V (ADDI, ADD, SUB, MUL, LB, SB, JAL, ECALL).
            initial_regs: Valori iniziali opzionali per i registri (es. {"a0": 0x100}).
            initial_mem: Mappa opzionale {offset_ram_byte: bytes} caricata in RAM prima del run.
            max_steps: Soglia massima di record di traccia prima del timeout.
        """
        self._ensure_sys_path()
        if not self.is_local_runtime_available():
            return {
                "success": False,
                "error": "Runtime chipformer/qwenputer non trovato in scratch/qwenputer",
            }

        try:
            from chipformer.rv import asm, ref, spec as S

            prog = asm.assemble(asm_source)
            mach = ref.Machine.from_program(prog)

            if initial_mem:
                for addr, blob in initial_mem.items():
                    raw = bytes(blob)
                    off = addr - S.RAM_BASE if addr >= S.RAM_BASE else addr
                    for i, b_val in enumerate(raw):
                        byte_pos = off + i
                        word_idx = byte_pos // 4
                        byte_shift = (byte_pos % 4) * 8
                        if 0 <= word_idx < len(mach.ram):
                            mask = ~(0xFF << byte_shift) & 0xFFFFFFFF
                            mach.ram[word_idx] = (mach.ram[word_idx] & mask) | ((b_val & 0xFF) << byte_shift)

            if initial_regs:
                for reg_name, val in initial_regs.items():
                    reg_idx = asm.REG.get(reg_name.lower())
                    if reg_idx is not None and 0 < reg_idx < 32:
                        mach.x[reg_idx] = val & 0xFFFFFFFF

            t0 = time.perf_counter()
            toks = mach.run(max_records=max_steps)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

            regs_map = {name: mach.x[i] for i, name in enumerate(asm.ABI)}
            exit_val = mach.x[10]
            is_halted = bool(mach.halted) and mach.fault is None
            timeout = len(toks) >= max_steps and not mach.halted
            trace_hash = _hash_trace_tokens(toks)

            return {
                "success": is_halted and not timeout,
                "halted": bool(mach.halted),
                "fault": mach.fault,
                "timeout": timeout,
                "steps": mach.steps,
                "trace_tokens_count": len(toks),
                "trace_hash": trace_hash,
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

    def execute_calc_expression(self, expression: str, max_records: int = 200_000) -> Dict[str, Any]:
        """Esegue un'espressione matematica deterministica direttamente sul firmware RV32IM calc-bridge.elf.

        Nessuna valutazione Python (`eval`) sull'host: l'espressione viene caricata nei banchi
        testo della macchina RV32IM (`m.text`), eseguita dal binario RISC-V + coprocessore Bignum
        (`BMAC`, `BMSB`, `BLD`, `BPRD`) e letta dai token `BYTE` di `<tool_response>`.
        """
        self._ensure_sys_path()
        if not CALC_ELF.exists():
            return {
                "success": False,
                "error": f"Firmware calc-bridge non trovato: {CALC_ELF}",
            }

        clean_expr = expression.strip()
        if not clean_expr or not all(
            c in "0123456789+-*/()%., ^gcd" for c in clean_expr
        ):
            return {
                "success": False,
                "error": f"Caratteri non ammessi nell'espressione: {expression}",
            }

        try:
            from chipformer.rv import bridge as BR
            from chipformer.rv import elf, ref, spec as S

            t0 = time.perf_counter()
            prog = elf.program(str(CALC_ELF))
            mach = ref.Machine.from_program(prog)
            BR.park(mach)

            payload = (
                f"\n<function=calc>\n<parameter=expression>\n{clean_expr}\n"
                "</parameter>\n</function>\n"
            ).encode("utf-8")

            rows = [bytes(S.TEXT_ROW)] * S.TEXT_ROWS
            for idx, off in enumerate(range(0, len(payload), S.TEXT_ROW), start=1):
                if idx > S.CAP_MAX:
                    return {
                        "success": False,
                        "error": f"Espressione troppo lunga per il buffer CAP_MAX ({S.CAP_MAX} righe)",
                    }
                rows[idx] = payload[off : off + S.TEXT_ROW].ljust(S.TEXT_ROW, b"\x00")

            mach.text = rows
            toks = mach.run(max_records=max_records)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)

            out_parts: List[str] = []
            for t in toks:
                fam, p = S.family(t)
                if fam == "BYTE":
                    if p < 256:
                        out_parts.append(chr(p))
                    elif p - 256 < len(BR.SPECIALS):
                        out_parts.append(BR.SPECIALS[p - 256])
            raw_out = "".join(out_parts)

            if "<tool_response>" not in raw_out or "</tool_response>" not in raw_out:
                return {
                    "success": False,
                    "error": f"Output firmware incompleto: {raw_out!r}",
                }

            result_str = (
                raw_out.split("<tool_response>", 1)[1]
                .split("</tool_response>", 1)[0]
                .strip()
            )
            if result_str == "error" or not result_str:
                return {
                    "success": False,
                    "error": f"Caratteri non ammessi o sintassi rifiutata da calc-bridge.elf: {expression}",
                }

            return {
                "success": True,
                "expression": expression,
                "result": result_str,
                "steps_executed": mach.steps,
                "trace_tokens_count": len(toks),
                "trace_hash": _hash_trace_tokens(toks),
                "firmware": CALC_ELF.name,
                "elapsed_ms": elapsed_ms,
                "deterministic": True,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Errore calcolo calc-bridge: {exc}",
            }

    # --- REA x Qwenputer: Ispezione statica ELF32 RV32IM & Disassembler ---------------------

    def inspect_rv32_elf(self, elf_path: Union[Path, str]) -> Dict[str, Any]:
        """Analizzatore statico per binari ELF32 RISC-V (RV32IM + Zba + Bignum).

        Copre i binari RV32IM soft-float (`e_flags == 0x0`) che la corsia Ghidra di REA 6.7.0
        rifiuta perché il profilo generico richiede `EF_RISCV_FLOAT_ABI_DOUBLE`.
        Il target non viene eseguito.
        """
        self._ensure_sys_path()
        target = Path(elf_path)
        if not target.exists() or not target.is_file():
            return {"success": False, "error": f"File ELF non trovato: {target}"}

        raw = target.read_bytes()
        sha256_hex = hashlib.sha256(raw).hexdigest()
        if len(raw) < 52 or raw[:4] != b"\x7fELF":
            return {
                "success": False,
                "error": "Il file non è un binario ELF valido",
                "sha256": sha256_hex,
            }

        ei_class = raw[4]
        ei_data = raw[5]
        if ei_class != 1 or ei_data != 1:
            return {
                "success": False,
                "error": f"Supportato solo ELF32 little-endian (trovato class={ei_class}, data={ei_data})",
                "sha256": sha256_hex,
            }

        (
            e_type,
            e_machine,
            e_version,
            e_entry,
            e_phoff,
            e_shoff,
            e_flags,
            e_ehsize,
            e_phentsize,
            e_phnum,
            e_shentsize,
            e_shnum,
            e_shstrndx,
        ) = struct.unpack_from("<HHIIIIIHHHHHH", raw, 16)

        if e_machine != EM_RISCV:
            return {
                "success": False,
                "error": f"Architettura non RISC-V (e_machine={e_machine}, atteso {EM_RISCV})",
                "sha256": sha256_hex,
            }

        float_abi_bits = e_flags & EF_RISCV_FLOAT_ABI_MASK
        float_abi_name = {
            EF_RISCV_FLOAT_ABI_SOFT: "soft-float (RV32IM integer/bignum)",
            EF_RISCV_FLOAT_ABI_SINGLE: "single-float (F)",
            EF_RISCV_FLOAT_ABI_DOUBLE: "double-float (D)",
            EF_RISCV_FLOAT_ABI_QUAD: "quad-float (Q)",
        }.get(float_abi_bits, f"unknown({hex(float_abi_bits)})")

        from chipformer.rv import elf, ref, spec as S

        _, pt_loads = elf.segments(target)
        segments_info: List[Dict[str, Any]] = []
        opcode_hist: Dict[str, int] = {}
        illegal_count = 0
        custom_bignum_count = 0
        total_instructions = 0

        for vaddr, blob in pt_loads:
            if S.ROM_BASE <= vaddr < S.ROM_BASE + 4 * S.ROM_WORDS:
                region = "ROM"
            elif S.DROM_BASE <= vaddr < S.DROM_BASE + 4 * S.DROM_WORDS:
                region = "DROM"
            elif S.RAM_BASE <= vaddr < S.RAM_BASE + 4 * S.RAM_WORDS:
                region = "RAM"
            else:
                region = "EXTERNAL_OR_QEMU"

            is_exec_region = region == "ROM" or (vaddr <= e_entry < vaddr + len(blob))
            if is_exec_region:
                for off in range(0, len(blob) - (len(blob) % 4), 4):
                    w = int.from_bytes(blob[off : off + 4], "little")
                    if w == 0:
                        continue
                    ins = ref.decode(w)
                    total_instructions += 1
                    opcode_hist[ins.op] = opcode_hist.get(ins.op, 0) + 1
                    if ins.op == "ILLEGAL":
                        illegal_count += 1
                    if ins.op in ref.CUSTOM:
                        custom_bignum_count += 1

            segments_info.append({
                "vaddr": hex(vaddr),
                "bytes": len(blob),
                "region": region,
                "executable_entry": bool(vaddr <= e_entry < vaddr + len(blob)),
            })

        # Estrazione tabella simboli SHT_SYMTAB (se presente)
        symbols = self._extract_elf32_symbols(raw, e_shoff, e_shentsize, e_shnum)
        functions = [s for s in symbols if s["kind"] == "func"]
        objects = [s for s in symbols if s["kind"] == "object"]

        is_rom_map = all(s["region"] in ("ROM", "DROM", "RAM") for s in segments_info)

        return {
            "success": True,
            "target": {
                "name": target.name,
                "path": str(target),
                "bytes": len(raw),
                "sha256": sha256_hex,
            },
            "elf_header": {
                "format": "ELF32-riscv-le",
                "e_type": e_type,
                "e_machine": e_machine,
                "entry_point": hex(e_entry),
                "e_flags": hex(e_flags),
                "rvc_compressed": bool(e_flags & EF_RISCV_RVC),
                "float_abi": float_abi_name,
                "rea_ghidra_lane_admitted": float_abi_bits == EF_RISCV_FLOAT_ABI_DOUBLE,
                "qwenputer_rom_map_compatible": is_rom_map and not bool(e_flags & EF_RISCV_RVC),
            },
            "segments": segments_info,
            "symbols": {
                "functions_count": len(functions),
                "objects_count": len(objects),
                "functions": functions,
                "objects": objects,
            },
            "instruction_audit": {
                "total_non_zero_instructions": total_instructions,
                "illegal_instructions_count": illegal_count,
                "custom_bignum_instructions_count": custom_bignum_count,
                "opcode_histogram": dict(
                    sorted(opcode_hist.items(), key=lambda kv: (-kv[1], kv[0]))
                ),
            },
            "executed": False,
        }

    def _extract_elf32_symbols(
        self, raw: bytes, e_shoff: int, e_shentsize: int, e_shnum: int
    ) -> List[Dict[str, Any]]:
        if not e_shoff or not e_shnum or e_shentsize < 40:
            return []
        sections = []
        for i in range(e_shnum):
            off = e_shoff + i * e_shentsize
            if off + 40 > len(raw):
                break
            sections.append(struct.unpack_from("<10I", raw, off))

        syms: List[Dict[str, Any]] = []
        for sh in sections:
            sh_type, sh_offset, sh_size, sh_link, sh_entsize = sh[1], sh[4], sh[5], sh[6], sh[9]
            if sh_type == 2 and sh_entsize >= 16 and 0 <= sh_link < len(sections):
                str_sh = sections[sh_link]
                strtab = raw[str_sh[4] : str_sh[4] + str_sh[5]]
                for off in range(sh_offset, sh_offset + sh_size, sh_entsize):
                    if off + 16 > len(raw):
                        break
                    st_name, st_value, st_size, st_info, _, _ = struct.unpack_from(
                        "<IIIBBH", raw, off
                    )
                    end = strtab.find(b"\x00", st_name)
                    name = (
                        strtab[st_name:end].decode("utf-8", errors="replace")
                        if end != -1
                        else ""
                    )
                    st_type = st_info & 0xF
                    if name and st_type in (1, 2):
                        syms.append({
                            "name": name,
                            "addr": hex(st_value),
                            "addr_int": st_value,
                            "size": st_size,
                            "kind": "func" if st_type == 2 else "object",
                        })
        return sorted(syms, key=lambda s: s["addr_int"])

    def disassemble_rv32_function(
        self,
        elf_path: Union[Path, str],
        symbol_or_addr: str,
        max_instructions: int = 128,
    ) -> Dict[str, Any]:
        """Disassembla una funzione (per nome simbolo o indirizzo esadecimale) da un ELF32 RV32IM."""
        info = self.inspect_rv32_elf(elf_path)
        if not info.get("success"):
            return info

        from chipformer.rv import asm, elf, ref

        funcs = info["symbols"]["functions"]
        target_addr: Optional[int] = None
        target_size: int = max_instructions * 4
        resolved_name: str = symbol_or_addr

        if symbol_or_addr.startswith("0x") or symbol_or_addr.startswith("0X"):
            try:
                target_addr = int(symbol_or_addr, 16)
            except ValueError:
                return {"success": False, "error": f"Indirizzo non valido: {symbol_or_addr}"}
            for fn in funcs:
                if fn["addr_int"] == target_addr:
                    resolved_name = fn["name"]
                    if fn["size"] > 0:
                        target_size = min(fn["size"], max_instructions * 4)
                    break
        else:
            cand = symbol_or_addr.lstrip("_")
            for fn in funcs:
                if fn["name"] == symbol_or_addr or fn["name"].lstrip("_") == cand:
                    target_addr = fn["addr_int"]
                    resolved_name = fn["name"]
                    if fn["size"] > 0:
                        target_size = min(fn["size"], max_instructions * 4)
                    break

        if target_addr is None:
            return {
                "success": False,
                "error": f"Simbolo o funzione '{symbol_or_addr}' non trovato in {Path(elf_path).name}",
                "available_functions": [f["name"] for f in funcs],
            }

        _, pt_loads = elf.segments(elf_path)
        instructions: List[Dict[str, Any]] = []
        for vaddr, blob in pt_loads:
            if vaddr <= target_addr < vaddr + len(blob):
                start_off = target_addr - vaddr
                end_off = min(len(blob), start_off + target_size)
                for off in range(start_off, end_off - (end_off - start_off) % 4, 4):
                    pc = vaddr + off
                    w = int.from_bytes(blob[off : off + 4], "little")
                    ins = ref.decode(w)
                    instructions.append({
                        "addr": hex(pc),
                        "word": f"0x{w:08x}",
                        "op": ins.op,
                        "mnemonic": _format_instruction_mnemonic(ins, asm.ABI),
                    })
                break

        if not instructions:
            return {
                "success": False,
                "error": f"Indirizzo {hex(target_addr)} fuori dai segmenti PT_LOAD",
            }

        return {
            "success": True,
            "target_sha256": info["target"]["sha256"],
            "function": resolved_name,
            "start_addr": hex(target_addr),
            "instruction_count": len(instructions),
            "instructions": instructions,
        }

    def execute_rv32_elf(
        self, elf_path: Union[Path, str], max_records: int = 250_000
    ) -> Dict[str, Any]:
        """Esegue un binario ELF32 RV32IM nella sandbox in-memory priva di syscall host."""
        info = self.inspect_rv32_elf(elf_path)
        if not info.get("success"):
            return info

        from chipformer.rv import elf, ref, spec as S

        t0 = time.perf_counter()
        try:
            if info["elf_header"]["qwenputer_rom_map_compatible"]:
                prog = elf.program(str(elf_path))
                mach = ref.Machine.from_program(prog)
                toks = mach.run(max_records=max_records)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
                out_bytes = bytes(
                    p for t in toks for fam, p in [S.family(t)] if fam == "BYTE" and p < 256
                )
                return {
                    "success": bool(mach.halted) and mach.fault is None,
                    "mode": "qwenputer_rom_map",
                    "target_sha256": info["target"]["sha256"],
                    "halted": bool(mach.halted),
                    "fault": mach.fault,
                    "steps": mach.steps,
                    "exit_code": mach.exit_code,
                    "a0": mach.x[10],
                    "stdout_text": out_bytes.decode("utf-8", errors="replace"),
                    "trace_tokens_count": len(toks),
                    "trace_hash": _hash_trace_tokens(toks),
                    "elapsed_ms": elapsed_ms,
                }
            else:
                cpu = ref.Rv32()
                elf.load_into(cpu, str(elf_path))
                while not cpu.halted and cpu.steps < max_records:
                    cpu.step()
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 3)
                return {
                    "success": bool(cpu.halted),
                    "mode": "rv32_flat_emulator",
                    "target_sha256": info["target"]["sha256"],
                    "halted": bool(cpu.halted),
                    "steps": cpu.steps,
                    "exit_code": cpu.exit_code,
                    "a0": cpu.x[10],
                    "stdout_text": bytes(cpu.out).decode("utf-8", errors="replace"),
                    "elapsed_ms": elapsed_ms,
                }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Errore esecuzione ELF RV32: {exc}",
                "target_sha256": info["target"]["sha256"],
            }

    # --- REA x Qwenputer: Verifica Clean-Room & Bundle con REA ------------------------------

    def verify_cleanroom_equivalence(
        self,
        asm_source: str,
        test_vectors: List[Dict[str, Any]],
        max_steps: int = 100_000,
    ) -> Dict[str, Any]:
        """Verifica che una routine RV32IM clean-room soddisfi tutti i vettori di test e gli invarianti.

        Ogni elemento di `test_vectors` può specificare:
        - `name`: etichetta del caso di test
        - `initial_regs`: es. {"a0": 0x100}
        - `initial_mem`: es. {0x100: b"ciao\\x00"}
        - `expected_regs`: es. {"a0": 436}
        - `expected_exit_code`: es. 436
        """
        if not test_vectors:
            return {
                "success": False,
                "verdict": PLAUSIBLE,
                "error": "Almeno un test_vector è richiesto per certificare l'equivalenza clean-room",
            }

        results: List[Dict[str, Any]] = []
        composite_hasher = hashlib.sha256()
        all_passed = True

        for idx, vec in enumerate(test_vectors):
            name = vec.get("name", f"vector_{idx}")
            init_regs = vec.get("initial_regs") or {}
            init_mem = vec.get("initial_mem") or {}
            exp_regs = vec.get("expected_regs") or {}
            exp_exit = vec.get("expected_exit_code")

            run_res = self.execute_riscv_asm(
                asm_source,
                initial_regs=init_regs,
                initial_mem=init_mem,
                max_steps=max_steps,
            )

            mismatches: List[str] = []
            if not run_res.get("success"):
                mismatches.append(run_res.get("error") or f"fault={run_res.get('fault')} timeout={run_res.get('timeout')}")
            else:
                regs = run_res.get("registers", {})
                for r_name, want_val in exp_regs.items():
                    got_val = regs.get(r_name)
                    if got_val != (want_val & 0xFFFFFFFF):
                        mismatches.append(f"reg {r_name}: atteso {want_val & 0xFFFFFFFF}, ottenuto {got_val}")
                if exp_exit is not None and run_res.get("exit_code") != (exp_exit & 0xFFFFFFFF):
                    mismatches.append(
                        f"exit_code: atteso {exp_exit & 0xFFFFFFFF}, ottenuto {run_res.get('exit_code')}"
                    )

            passed = len(mismatches) == 0
            if not passed:
                all_passed = False

            th = run_res.get("trace_hash", "")
            composite_hasher.update(f"{name}:{th}:{passed}".encode("utf-8"))

            results.append({
                "name": name,
                "passed": passed,
                "steps": run_res.get("steps", 0),
                "exit_code": run_res.get("exit_code"),
                "a0": run_res.get("a0"),
                "trace_hash": th,
                "mismatches": mismatches,
            })

        composite_trace_hash = composite_hasher.hexdigest()
        tier = VERIFIED if all_passed else REFUTED
        if all_passed:
            evidence: Dict[str, Any] = {
                "tier": VERIFIED,
                "basis": [
                    {
                        "kind": "check",
                        "command": f"QwenputerBridge.verify_cleanroom_equivalence(vectors={len(test_vectors)})",
                        "exit_code": 0,
                        "output_sha256": composite_trace_hash,
                        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                ],
            }
        else:
            failed_reasons = [
                f"{r['name']}: {', '.join(r['mismatches'])}"
                for r in results
                if not r["passed"]
            ]
            evidence = {
                "tier": REFUTED,
                "basis": [
                    {
                        "kind": "refutation",
                        "reason": "; ".join(failed_reasons) or "cleanroom vector mismatch",
                    }
                ],
            }
        evidence_errors = validate_evidence(evidence)

        return {
            "success": all_passed,
            "verdict": tier,
            "vectors_total": len(test_vectors),
            "vectors_passed": sum(1 for r in results if r["passed"]),
            "composite_trace_hash": composite_trace_hash,
            "vector_results": results,
            "evidence": evidence,
            "evidence_errors": evidence_errors,
        }

    def prepare_rea_cleanroom_bundle(
        self,
        rea_job_or_id: Union[Path, str],
        asm_source: Optional[str] = None,
        test_vectors: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Collega un lavoro statico di REA (`data/rea/jobs/<id>`) alla verifica clean-room Qwenputer.

        Legge `job.json`, `report.json` e `stdout.json` prodotti da `scripts/rea_surface.py`,
        estrae l'impronta `sha256` del binario osservato, l'`evidence_id` di REA e l'eventuale
        pseudocodice decompilato da Ghidra, e se sono forniti `asm_source` e `test_vectors`
        certifica l'equivalenza in camera bianca RV32IM senza mai eseguire il binario originale.
        """
        job_dir = Path(rea_job_or_id)
        if not job_dir.exists() and (REA_JOBS_DIR / str(rea_job_or_id)).exists():
            job_dir = REA_JOBS_DIR / str(rea_job_or_id)

        if not job_dir.exists() or not job_dir.is_dir():
            return {"success": False, "error": f"Job REA non trovato: {rea_job_or_id}"}

        job_file = job_dir / "job.json"
        report_file = job_dir / "report.json"
        stdout_file = job_dir / "stdout.json"

        job_data = json.loads(job_file.read_text(encoding="utf-8")) if job_file.exists() else {}
        report_data = json.loads(report_file.read_text(encoding="utf-8")) if report_file.exists() else {}
        stdout_data = json.loads(stdout_file.read_text(encoding="utf-8")) if stdout_file.exists() else {}

        target_info = job_data.get("target") or (report_data.get("osservato") or {}).get("target") or {}
        decompiled_c = stdout_data.get("normalized_result") or stdout_data.get("raw_result")
        rea_evidence_id = stdout_data.get("evidence_id")

        static_provenance = {
            "rea_job_id": job_data.get("id") or job_dir.name,
            "operation": job_data.get("op") or stdout_data.get("operation"),
            "argument": job_data.get("argomento"),
            "provider": job_data.get("provider") or (stdout_data.get("provider") or {}).get("id"),
            "target_name": target_info.get("nome") or (stdout_data.get("subject") or {}).get("name"),
            "target_sha256": target_info.get("sha256")
            or ((stdout_data.get("subject") or {}).get("digest") or {}).get("sha256"),
            "rea_evidence_id": rea_evidence_id,
            "decompiled_c": decompiled_c,
            "target_executed_on_host": False,
        }

        cleanroom_verification = None
        if asm_source and test_vectors:
            cleanroom_verification = self.verify_cleanroom_equivalence(asm_source, test_vectors)

        verdict = (
            cleanroom_verification["verdict"]
            if cleanroom_verification
            else (SOURCED if decompiled_c else PLAUSIBLE)
        )

        return {
            "success": True,
            "verdict": verdict,
            "static_provenance": static_provenance,
            "cleanroom_verification": cleanroom_verification,
            "boundaries": [
                "Il binario originale analizzato da REA non è mai stato eseguito sull'host.",
                "La verifica dinamica avviene esclusivamente sul micro-programma RV32IM clean-room dentro QwenputerBridge.",
            ],
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

        # 2. HP OMEN 16 (GPU Node - RTX 3070 8GB VRAM / 32GB RAM)
        omen_status = {
            "role": "GPU Heavy Engine & Causal Dreamer",
            "endpoint": OMEN_NODE_URL,
            "reachable": False,
            "tier": "unknown",
            "vram_profile": "NVIDIA RTX 3070 8GB GDDR6 / 32GB System RAM",
            "cuda_triton_ready": None,
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

        report["cluster_ready"] = mac_status["local_circuit_runtime"] and (
            omen_status["reachable"] or mac_status["status"] == "ready"
        )
        return report
