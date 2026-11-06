#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Confronta per esecuzione l'assembly originale e il C decompilato, nello stesso emulatore x86.

Le due versioni partono da input e memoria identici; si confrontano valore di ritorno, scritture in
memoria fuori dallo stack ed esito. La memoria non inizializzata e' pseudocasuale ma uguale per entrambe.

Le funzioni chiamate sono sostituite da stub che registrano nome e argomenti e restituiscono lo stesso valore
alle due versioni: si verifica che la funzione faccia le stesse chiamate, non cio' che fanno le chiamate.
Serve la dichiarazione C di ogni funzione chiamata. Dipendenze: unicorn, pyelftools (solo per questo script).

Uso:
    .venv/bin/python scripts/syndwars_verify.py --cases 300 FILE_C_O_NOME...
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from unicorn import UC_ARCH_X86, UC_HOOK_BLOCK, UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_WRITE_UNMAPPED, UC_HOOK_MEM_FETCH_UNMAPPED, UC_MODE_32, Uc, UcError
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.syndwars_decompile_sovereign import PENDING_PATH, SWARS_DIR, _find_c_declaration, _project_include_dirs, ensure_bsndconf, load_jsonl
from scripts.syndwars_orchestrate import load_sources, parse_signature

PAGE = 0x1000
LOAD_BASE = 0x00100000
EXTERN_BASE = 0x10000000
EXTERN_SLOT = 0x20000
STACK_BASE = 0x7F000000
STACK_SIZE = 0x40000
RETURN_SENTINEL = 0x7EFF0000
POINTER_ARENA = 0x40000000
MAX_INSTRUCTIONS = 200_000
# Il C a -O0 esegue molte piu' istruzioni dell'assembly: stesso lavoro, budget piu' alto.
CANDIDATE_MAX_INSTRUCTIONS = 5_000_000
# Oltre questa soglia, se i casi senza esito superano gli accordi, la funzione non arrivera' alla maggioranza.
LIMIT_CASES_BEFORE_STOP = 100
MISMATCHES_BEFORE_STOP = 20
REGISTERS = (UC_X86_REG_EAX, UC_X86_REG_EDX, UC_X86_REG_EBX, UC_X86_REG_ECX)
RETURN_MASKS = {"char": 0xFF, "ubyte": 0xFF, "sbyte": 0xFF, "TbBool": 0xFF, "u8": 0xFF, "s8": 0xFF,
                "short": 0xFFFF, "ushort": 0xFFFF, "u16": 0xFFFF, "s16": 0xFFFF, "ThingIdx": 0xFFFF}
INTEGER_EDGES = (0, 1, 2, 3, 7, 0x7F, 0x80, 0xFF, 0x100, 0x7FFF, 0x8000, 0xFFFF, 0x10000, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)


SYSTEM_HEADER_STUBS = {
    "time.h": "#include <stddef.h>\ntypedef long time_t;\nstruct tm { int tm_sec; };\n",
    "sys/stat.h": "struct stat { int st_mode; long st_size; };\n",
    "sys/types.h": "#include <stddef.h>\ntypedef long off_t;\ntypedef long ssize_t;\n",
    "stdio.h": "#include <stddef.h>\n#include <stdarg.h>\ntypedef struct _FILE_stub FILE;\n#define FILENAME_MAX 260\n#define EOF (-1)\n",
    "stdlib.h": "#include <stddef.h>\n",
    "string.h": "#include <stddef.h>\n",
    "dirent.h": "typedef struct _DIR_stub DIR;\nstruct dirent { char d_name[256]; };\n",
    "unistd.h": "#include <stddef.h>\n",
    "assert.h": "#define assert(x) ((void)0)\n",
    "limits.h": "#define INT_MAX 2147483647\n#define INT_MIN (-INT_MAX - 1)\n#define SHRT_MAX 32767\n#define LONG_MAX 2147483647L\n",
    "errno.h": "extern int errno;\n",
}


@dataclass
class LoadedObject:
    sections: Dict[int, int] = field(default_factory=dict)
    symbols: Dict[str, int] = field(default_factory=dict)


@dataclass
class RunResult:
    status: str
    eax: int
    writes: Dict[int, int]
    covered: Set[int]
    calls: List[Tuple[Any, ...]] = field(default_factory=list)


@dataclass
class Callee:
    name: str
    return_type: str
    params: List[str]
    address: int
    pop_bytes: int = 0


def parse_declaration(declaration: str) -> Optional[Tuple[str, List[str]]]:
    """(tipo di ritorno, tipi dei parametri); None se uno stub non puo' rappresentarla."""
    text = declaration.strip().rstrip(";").strip()
    match = re.match(r"(.+?)\b\w+\s*\((.*)\)$", text, re.DOTALL)
    if not match:
        return None
    return_type = re.sub(r"\b(?:extern|static|inline|__inline__)\b", "", match.group(1)).strip()
    params: List[str] = []
    depth = 0
    current = ""
    for char in match.group(2):
        depth += char == "("
        depth -= char == ")"
        if char == "," and not depth:
            params.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip() and current.strip() != "void":
        params.append(current.strip())
    types: List[str] = []
    for param in params:
        if param == "...":
            return None
        if "(" in param or "*" in param:
            types.append("void *")
            continue
        words = param.replace("const", "").split()
        if "struct" in words or "long long" in " ".join(words):
            return None
        types.append(" ".join(words[:-1]) if len(words) > 1 else words[0])
    return return_type, types


def narrow_value(ctype: str, raw: int) -> int:
    """Il valore come lo vede il C dopo la conversione al tipo, esteso a 32 bit."""
    if "*" in ctype:
        return raw & 0xFFFFFFFF
    base = ctype.replace("const", "").strip()
    if base in ("short", "s16", "ThingIdx"):
        return struct.unpack("<h", struct.pack("<H", raw & 0xFFFF))[0] & 0xFFFFFFFF
    if base in ("ushort", "u16"):
        return raw & 0xFFFF
    if base in ("ubyte", "u8", "TbBool"):
        return raw & 0xFF
    if base in ("char", "sbyte", "s8"):
        return struct.unpack("<b", struct.pack("<B", raw & 0xFF))[0] & 0xFFFFFFFF
    return raw & 0xFFFFFFFF


def stub_return(callee: Callee, sequence: int, seed: int) -> int:
    rng = random.Random(f"{seed}:{callee.name}:{sequence}")
    if "*" in callee.return_type:
        return POINTER_ARENA + 0x800000 + rng.randrange(0x1000) * 4
    pick = rng.random()
    raw = 0 if pick < 0.3 else 1 if pick < 0.5 else rng.randrange(0x100) if pick < 0.85 else rng.getrandbits(32)
    return narrow_value(callee.return_type, raw)


class Image:
    """Oggetti ELF i386 caricati e rilocati a mano in un unico spazio di indirizzi."""

    def __init__(self) -> None:
        self.blobs: List[Tuple[int, bytes]] = []
        self.next_base = LOAD_BASE
        self.externs: Dict[str, int] = {}
        self.globals: Dict[str, int] = {}
        self.locals: Dict[str, int] = {}

    def _extern(self, name: str) -> int:
        # Anche i simboli locali dell'assembly: il C deve toccare la stessa tabella, non una copia.
        if name in self.globals or name in self.locals:
            return self.globals.get(name, self.locals.get(name))
        if name not in self.externs:
            self.externs[name] = EXTERN_BASE + len(self.externs) * EXTERN_SLOT + 0x1000
        return self.externs[name]

    def load(self, path: Path) -> LoadedObject:
        loaded = LoadedObject()
        with open(path, "rb") as fh:
            elf = ELFFile(fh)
            buffers: Dict[int, bytearray] = {}
            for index, section in enumerate(elf.iter_sections()):
                if section["sh_flags"] & 0x2 and section["sh_size"]:
                    align = max(section["sh_addralign"], 16)
                    self.next_base = (self.next_base + align - 1) & ~(align - 1)
                    loaded.sections[index] = self.next_base
                    buffers[index] = bytearray(b"\0" * section["sh_size"] if section["sh_type"] == "SHT_NOBITS" else section.data())
                    self.next_base += section["sh_size"]
            symtab = next(s for s in elf.iter_sections() if isinstance(s, SymbolTableSection))
            for symbol in symtab.iter_symbols():
                shndx = symbol["st_shndx"]
                if isinstance(shndx, int) and shndx in loaded.sections and symbol.name:
                    address = loaded.sections[shndx] + symbol["st_value"]
                    loaded.symbols[symbol.name] = address
                    if symbol["st_info"]["bind"] == "STB_GLOBAL":
                        self.globals[symbol.name] = address
                    else:
                        self.locals.setdefault(symbol.name, address)

            def resolve(symbol: Any) -> int:
                shndx = symbol["st_shndx"]
                if isinstance(shndx, int) and shndx in loaded.sections:
                    return loaded.sections[shndx] + symbol["st_value"]
                return self._extern(symbol.name)

            for section in elf.iter_sections():
                if section["sh_type"] != "SHT_REL" or section["sh_info"] not in buffers:
                    continue
                target_index = section["sh_info"]
                buffer = buffers[target_index]
                base = loaded.sections[target_index]
                for relocation in section.iter_relocations():
                    offset = relocation["r_offset"]
                    kind = relocation["r_info_type"]
                    value = resolve(symtab.get_symbol(relocation["r_info_sym"]))
                    addend = struct.unpack_from("<i", buffer, offset)[0]
                    if kind == 1:  # R_386_32
                        struct.pack_into("<I", buffer, offset, (value + addend) & 0xFFFFFFFF)
                    elif kind in (2, 4):  # R_386_PC32, R_386_PLT32
                        struct.pack_into("<I", buffer, offset, (value + addend - (base + offset)) & 0xFFFFFFFF)
                    else:
                        raise ValueError(f"rilocazione non gestita: {kind}")
            for index, buffer in buffers.items():
                self.blobs.append((loaded.sections[index], bytes(buffer)))
        return loaded


def fill_page(seed: int, address: int) -> bytes:
    """Contenuto stabile per caso e indirizzo: valori piccoli, cosi' indici e liste restano plausibili."""
    rng = random.Random((seed << 32) ^ address)
    out = bytearray()
    for _ in range(PAGE // 4):
        pick = rng.random()
        if pick < 0.3:
            value = 0
        elif pick < 0.5:
            value = rng.randrange(8)
        elif pick < 0.75:
            value = rng.randrange(0x100)
        elif pick < 0.9:
            value = rng.randrange(0x10000)
        else:
            value = rng.getrandbits(32)
        out += struct.pack("<I", value)
    return bytes(out)


def run_case(image: Image, entry: int, args: Sequence[int], stack_args: Sequence[int], cdecl: bool, seed: int,
             callees: Sequence[Callee] = (), saved_seed: Optional[int] = None, max_instructions: int = MAX_INSTRUCTIONS) -> RunResult:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    low = min(b for b, _ in image.blobs) & ~(PAGE - 1)
    high = (max(b + len(d) for b, d in image.blobs) + PAGE) & ~(PAGE - 1)
    uc.mem_map(low, high - low)
    for base, data in image.blobs:
        uc.mem_write(base, data)
    uc.mem_map(STACK_BASE, STACK_SIZE)
    uc.mem_write(STACK_BASE, fill_page(seed, STACK_BASE) * (STACK_SIZE // PAGE))
    uc.mem_map(RETURN_SENTINEL & ~(PAGE - 1), PAGE)
    uc.mem_write(RETURN_SENTINEL, b"\xf4")

    def on_unmapped(emu: Uc, _access: int, address: int, _size: int, _value: int, _data: Any) -> bool:
        page = address & ~(PAGE - 1)
        try:
            emu.mem_map(page, PAGE)
            emu.mem_write(page, fill_page(seed, page))
            return True
        except UcError:
            return False

    uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED | UC_HOOK_MEM_WRITE_UNMAPPED, on_unmapped)

    writes: Dict[int, int] = {}
    covered: Set[int] = set()
    calls: List[Tuple[Any, ...]] = []
    sequences: Dict[str, int] = {}

    def on_stub(emu: Uc, _address: int, _size: int, callee: Callee) -> None:
        esp = emu.reg_read(UC_X86_REG_ESP)
        seen = []
        for index, ctype in enumerate(callee.params):
            if not cdecl and index < len(REGISTERS):
                raw = emu.reg_read(REGISTERS[index])
            else:
                slot = index if cdecl else index - len(REGISTERS)
                raw = struct.unpack("<I", emu.mem_read(esp + 4 + slot * 4, 4))[0]
            # Le due versioni tengono i buffer locali in punti diversi dello stack.
            seen.append("stack" if STACK_BASE <= raw < STACK_BASE + STACK_SIZE else narrow_value(ctype, raw))
        calls.append((callee.name, *seen))
        sequence = sequences.get(callee.name, 0)
        sequences[callee.name] = sequence + 1
        if callee.return_type != "void":
            emu.reg_write(UC_X86_REG_EAX, stub_return(callee, sequence, seed))

    for callee in callees:
        page = callee.address & ~(PAGE - 1)
        if not low <= callee.address < high:
            try:
                uc.mem_map(page, PAGE)
                uc.mem_write(page, fill_page(seed, page))
            except UcError:
                pass  # Due stub nella stessa pagina.
        # Nella convenzione Watcom e' il chiamato a togliere dallo stack i propri argomenti.
        code = b"\xc3" if not callee.pop_bytes else b"\xc2" + struct.pack("<H", callee.pop_bytes)
        uc.mem_write(callee.address, code)
        uc.hook_add(UC_HOOK_CODE, on_stub, callee, callee.address, callee.address)


    initial: Dict[int, int] = {}

    def on_write(emu: Uc, _access: int, address: int, size: int, value: int, _data: Any) -> None:
        if STACK_BASE <= address < STACK_BASE + STACK_SIZE:
            return
        for i in range(size):
            byte_address = address + i
            if byte_address not in initial:
                try:
                    initial[byte_address] = emu.mem_read(byte_address, 1)[0]
                except UcError:
                    page = byte_address & ~(PAGE - 1)
                    initial[byte_address] = fill_page(seed, page)[byte_address - page]
            writes[byte_address] = (value >> (8 * i)) & 0xFF

    def on_block(_emu: Uc, address: int, size: int, _data: Any) -> None:
        covered.update(range(address, address + size))

    uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    if not cdecl:  # La copertura si misura solo sull'assembly.
        uc.hook_add(UC_HOOK_BLOCK, on_block)

    esp = STACK_BASE + STACK_SIZE - 0x2000
    if cdecl:
        for value in reversed(list(args) + list(stack_args)):
            esp -= 4
            uc.mem_write(esp, struct.pack("<I", value & 0xFFFFFFFF))
    else:
        for value in reversed(list(stack_args)):
            esp -= 4
            uc.mem_write(esp, struct.pack("<I", value & 0xFFFFFFFF))
        for register, value in zip(REGISTERS, args):
            uc.reg_write(register, value & 0xFFFFFFFF)
    esp -= 4
    uc.mem_write(esp, struct.pack("<I", RETURN_SENTINEL))
    uc.reg_write(UC_X86_REG_ESP, esp)
    rng = random.Random(seed if saved_seed is None else saved_seed)
    unset = list(REGISTERS[len(args):]) if not cdecl else []
    for register in (*unset, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP):
        uc.reg_write(register, rng.randrange(0x10000))

    status = "ok"
    try:
        uc.emu_start(entry, RETURN_SENTINEL, count=max_instructions)
        if uc.reg_read(UC_X86_REG_EIP) != RETURN_SENTINEL:
            status = "limit"
    except UcError as exc:
        status = f"fault:{exc.errno}"
    # Conta lo stato finale: riscrivere il valore gia' presente non cambia nulla.
    changed = {a: v for a, v in writes.items() if initial.get(a) != v}
    return RunResult(status, uc.reg_read(UC_X86_REG_EAX), changed, covered, calls)


def choose_args(params: Sequence[Tuple[str, str]], rng: random.Random) -> List[int]:
    values = []
    for index, (ctype, _name) in enumerate(params):
        if "*" in ctype:
            values.append(POINTER_ARENA + index * 0x100000 + rng.randrange(0, 0x1000) * 4)
            continue
        pick = rng.random()
        raw = (rng.choice(INTEGER_EDGES) if pick < 0.25 else rng.randrange(8) if pick < 0.45 else rng.randrange(0x100) if pick < 0.7
               else rng.randrange(0x10000) if pick < 0.9 else rng.getrandbits(32))
        values.append(narrow_value(ctype, raw))
    return values


def assemble_original(work: Path) -> Path:
    obj = work / "swars.o"
    subprocess.run(["clang", "-target", "i386-unknown-linux-gnu", "-x", "assembler-with-cpp", "-c",
                    str(SWARS_DIR / "src" / "swars.sx"), "-o", str(obj)], check=True, capture_output=True, text=True, timeout=180)
    return obj


def compile_candidate(code: str, c_rel: str, work: Path, label: str) -> Tuple[Optional[Path], str]:
    """Compila a 32 bit coi soli header del file originale; gli header di sistema mancanti restano vuoti."""
    ensure_bsndconf()
    stubs = work / "stubs"
    stubs.mkdir(exist_ok=True)
    original = (SWARS_DIR / c_rel).read_text(encoding="utf-8", errors="replace")
    includes = re.findall(r'^\s*#\s*include\s+"[^"]+"', original, re.MULTILINE)
    source = work / f"{label}.c"
    source.write_text("\n".join(includes) + "\n" + code + "\n", encoding="utf-8")
    obj = work / f"{label}.o"
    cmd = ["clang", "-target", "i386-unknown-linux-gnu", "-ffreestanding", "-fno-pic", "-fno-builtin", "-O0", "-w", "-std=gnu99",
           "-Wno-implicit-function-declaration", "-Wno-int-conversion", "-Wno-implicit-int", "-Wno-incompatible-pointer-types",
           "-ferror-limit=0", "-DLB_HAVE_STDINT_H=1", "-DPACKAGE_NAME=\"syndwarsfx\"", "-DPACKAGE_VERSION=\"0.6\"", "-DVERSION=\"0.6\"", "-DLBS_PACKAGE=1",
           f"-I{stubs}", "-I/tmp", *[f"-I{d}" for d in _project_include_dirs(SWARS_DIR)], "-c", str(source), "-o", str(obj)]
    for _ in range(40):
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return obj, ""
        missing = re.search(r"fatal error: '([^']+)' file not found", result.stderr)
        if missing:
            stub = stubs / missing.group(1)
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("#pragma once\n" + SYSTEM_HEADER_STUBS.get(missing.group(1), ""), encoding="utf-8")
            continue
        # Globali definite nel .c originale: qui contano solo per l'indirizzo, uguale per entrambe le versioni.
        undeclared = sorted(set(re.findall(r"use of undeclared identifier '(\w+)'", result.stderr)))
        if not undeclared:
            return None, "\n".join(sorted(set(re.findall(r"error: .*", result.stderr)))[:12])
        text = source.read_text(encoding="utf-8")
        source.write_text("".join(f"extern int {name};\n" for name in undeclared) + text, encoding="utf-8")
    return None, "troppi header mancanti"


def function_extent(asm_symbols: Dict[str, int], name: str, asm_lines: int) -> Tuple[int, int]:
    start = asm_symbols[f"ASM_{name}"]
    after = [a for a in asm_symbols.values() if a > start]
    return start, min(after) if after else start + asm_lines * 8


def called_functions(target: Dict[str, Any]) -> Dict[str, str]:
    """{nome C: etichetta chiamata dall'assembly}, senza la funzione stessa."""
    found: Dict[str, str] = {}
    for label in re.findall(r"\bcall\s+([A-Za-z_]\w*)", target["asm_code"]):
        name = re.sub(r"^(?:ac_|ASM_)", "", label)
        if name != target["func_name"]:
            found.setdefault(name, label)
    return found


def build_callees(target: Dict[str, Any], image: Image, asm: LoadedObject, candidate: LoadedObject) -> Tuple[List[Callee], List[Callee], List[str]]:
    """Stub per i due lati e l'elenco delle chiamate che non si possono rappresentare."""
    asm_side: List[Callee] = []
    c_side: List[Callee] = []
    blocked: List[str] = []
    sources = list(load_sources(target["c_file"]))
    for name, label in called_functions(target).items():
        parsed = parse_declaration(_find_c_declaration(name, sources))
        if not parsed:
            blocked.append(name)
            continue
        return_type, params = parsed
        asm_address = asm.symbols.get(label, image.externs.get(label))
        if asm_address is None:
            blocked.append(name)
            continue
        asm_side.append(Callee(name, return_type, params, asm_address, max(0, len(params) - len(REGISTERS)) * 4))
        c_address = candidate.symbols.get(name, image.externs.get(name, image.globals.get(name)))
        if c_address is not None:
            c_side.append(Callee(name, return_type, params, c_address))
    return asm_side, c_side, blocked


def same_behaviour(first: RunResult, second: RunResult, mask: int) -> bool:
    return (first.status == second.status and (first.eax & mask) == (second.eax & mask)
            and first.writes == second.writes and first.calls == second.calls)


def compare_function(target: Dict[str, Any], code: str, work: Path, asm_obj: Path, cases: int, label: str,
                     max_mismatches: int = MISMATCHES_BEFORE_STOP) -> Dict[str, Any]:
    name = target["func_name"]
    return_type, _n, params = parse_signature(target["current_c_stub"])
    obj, error = compile_candidate(code, target["c_file"], work, label)
    if not obj:
        return {"func": name, "verdict": "not_built", "error": error}

    image = Image()
    asm = image.load(asm_obj)
    candidate = image.load(obj)
    if name not in candidate.symbols:
        return {"func": name, "verdict": "not_built", "error": "simbolo assente"}
    asm_callees, c_callees, blocked = build_callees(target, image, asm, candidate)
    if blocked:
        return {"func": name, "verdict": "unsupported_calls", "error": ", ".join(blocked)}
    start, end = function_extent(asm.symbols, name, target["asm_line_count"])
    mask = 0 if return_type == "void" else RETURN_MASKS.get(return_type.replace("const", "").strip(), 0xFFFFFFFF)

    rng = random.Random(0x5EED)
    agreed = inconclusive = completed = undefined = disagreed = 0
    stopped_early = False
    mismatches: List[Dict[str, Any]] = []
    covered: Set[int] = set()
    for case in range(cases):
        values = choose_args(params, rng)
        reg_args, stack_args = values[:4], values[4:]
        original = run_case(image, start, reg_args, stack_args, False, case + 1, asm_callees)
        budget = CANDIDATE_MAX_INSTRUCTIONS if original.status == "ok" else MAX_INSTRUCTIONS
        rebuilt = run_case(image, candidate.symbols[name], values, [], True, case + 1, c_callees, max_instructions=budget)
        covered |= {a for a in original.covered if start <= a < end}
        if original.status == "limit" and rebuilt.status == "limit":
            inconclusive += 1
            if inconclusive > LIMIT_CASES_BEFORE_STOP and inconclusive > agreed:
                stopped_early = True
                break
            continue
        same_status = original.status.split(":")[0] == rebuilt.status.split(":")[0]
        same_return = (original.eax & mask) == (rebuilt.eax & mask)
        if same_status and (original.status != "ok" or (same_return and original.writes == rebuilt.writes and original.calls == rebuilt.calls)):
            agreed += 1
            completed += original.status == "ok"
            continue
        # Se l'assembly cambia esito coi soli registri non inizializzati, nessun C puo' riprodurlo.
        probe = run_case(image, start, reg_args, stack_args, False, case + 1, asm_callees, saved_seed=case + 1 + 0x10000)
        if not same_behaviour(original, probe, mask):
            undefined += 1
            continue
        disagreed += 1
        if len(mismatches) < 5:
            diff = sorted(a for a in set(original.writes) | set(rebuilt.writes) if original.writes.get(a) != rebuilt.writes.get(a))
            mismatches.append({"case": case + 1, "args": [hex(v) for v in values],
                               "status": [original.status, rebuilt.status],
                               "return": [hex(original.eax & mask), hex(rebuilt.eax & mask)],
                               "write_diffs": [hex(a) for a in diff[:6]], "n_write_diffs": len(diff),
                               "calls": [] if original.calls == rebuilt.calls else [str(original.calls[:4]), str(rebuilt.calls[:4])]})
        if disagreed >= max_mismatches:
            stopped_early = True
            break
    coverage = len(covered) / max(1, end - start)
    verdict = "mismatch" if disagreed else "inconclusive" if agreed < cases // 2 else "agree"
    if verdict == "agree" and completed < cases // 2:
        verdict = "inconclusive"  # Un guasto comune non confronta nulla.
    return {"func": name, "verdict": verdict, "agreed": agreed, "completed": completed, "disagreed": disagreed, "inconclusive": inconclusive, "undefined_input": undefined, "stopped_early": stopped_early,
            "coverage": round(coverage, 3), "mismatches": mismatches}


MUTATIONS = {"<=": "<", ">=": ">", "==": "!=", "!=": "==", "<": "<=", ">": ">=", "+": "-", "-": "+", "&&": "||", "||": "&&"}
_MUTABLE_RE = re.compile(r"(?<![-<>=!&|+])(<=|>=|==|!=|&&|\|\||<|>|\+|-)(?![-<>=&|+])")


def make_mutants(code: str, signature: str, limit: int = 6) -> List[Tuple[str, str]]:
    """Piccoli errori plausibili sparsi nel corpo: se il test non li vede, la sua prova e' debole."""
    start = code.index(signature) + len(signature)
    body_start = code.index("{", start)
    sites = []
    for match in _MUTABLE_RE.finditer(code, body_start):
        line_start = code.rfind("\n", 0, match.start()) + 1
        line = code[line_start:code.find("\n", match.end())]
        if re.match(r"\s*(?:int|u32|short|ushort|ubyte|char|long|struct)\b[^=]*;\s*$", line):
            continue
        before = code[match.start() - 1] if match.start() else " "
        if match.group(1) in ("<", ">", "+", "-") and (before in "(,*" or code[match.end():match.end() + 1] in "x0"):
            if match.group(1) in ("<", ">"):
                sites.append(match)
            continue
        sites.append(match)
    step = max(1, len(sites) // limit)
    mutants = []
    for match in sites[::step][:limit]:
        mutants.append((f"{match.group(1)}->{MUTATIONS[match.group(1)]}@{code.count(chr(10), 0, match.start()) + 1}",
                        code[:match.start()] + MUTATIONS[match.group(1)] + code[match.end():]))
    return mutants


def mutation_score(target: Dict[str, Any], code: str, work: Path, asm_obj: Path, cases: int, label: str) -> Dict[str, Any]:
    killed, survived, unbuilt = 0, [], 0
    signature = target["current_c_stub"].split("{")[0].strip()
    for index, (description, mutant) in enumerate(make_mutants(code, signature)):
        outcome = compare_function(target, mutant, work, asm_obj, cases, f"{label}_m{index}", max_mismatches=1)
        if outcome["verdict"] == "not_built":
            unbuilt += 1
        elif outcome["verdict"] == "mismatch":
            killed += 1
        else:
            survived.append(description)
    return {"killed": killed, "survived": survived, "unbuilt": unbuilt}


def verify_one(target: Dict[str, Any], code: str, asm_obj: Path, cases: int, with_mutants: bool) -> Dict[str, Any]:
    """Un processo per funzione: ognuno ha la sua cartella, cosi' gli stub degli header non si intralciano."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        result = compare_function(target, code, work, asm_obj, cases, "cand")
        if result["verdict"] == "agree" and with_mutants:
            result["mutants"] = mutation_score(target, code, work, asm_obj, cases, "cand")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("functions", nargs="+", help="nome funzione oppure nome=percorso/file.c")
    parser.add_argument("--cases", type=int, default=300)
    parser.add_argument("--code-dir", default=str(ROOT / "data" / "nightly" / "syndwars_ghidra"))
    parser.add_argument("--output", default="")
    parser.add_argument("--no-mutants", action="store_true")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args()
    targets = {t["func_name"]: t for t in load_jsonl(PENDING_PATH)}
    results: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        asm_obj = assemble_original(Path(tmp))
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as pool:
            pending = []
            for item in args.functions:
                name, _, explicit = item.partition("=")
                path = Path(explicit) if explicit else Path(args.code_dir) / f"{name}.base.c"
                pending.append(pool.submit(verify_one, targets[name], path.read_text(encoding="utf-8"), asm_obj, args.cases, not args.no_mutants))
            for future in concurrent.futures.as_completed(pending):
                result = future.result()
                results.append(result)
                if args.output:
                    Path(args.output).write_text(json.dumps(results, indent=1), encoding="utf-8")
                print(f"[{len(results)}/{len(pending)}] {result['func']}: {result['verdict']} accordo={result.get('agreed')} conclusi={result.get('completed')} "
                      f"diversi={result.get('disagreed')} inconcl={result.get('inconclusive')} indefiniti={result.get('undefined_input')} "
                      f"copertura={result.get('coverage')} mutanti={result.get('mutants')} {result.get('error', '')[:300]}", flush=True)
                for mismatch in result.get("mismatches", [])[:2]:
                    print(f"   {json.dumps(mismatch)[:300]}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
