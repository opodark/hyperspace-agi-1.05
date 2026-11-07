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
import functools
import json
import os
import random
import re
import struct
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import SymbolTableSection
from unicorn import UC_MEM_WRITE, UC_ARCH_X86, UC_HOOK_BLOCK, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_WRITE_UNMAPPED, UC_HOOK_MEM_FETCH_UNMAPPED, UC_MODE_32, Uc, UcError
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.syndwars_decompile_sovereign import PENDING_PATH, SWARS_DIR, _project_include_dirs, ensure_bsndconf, load_jsonl
from scripts.syndwars_ghidra import asm_call_targets, load_inferred_signatures, lookup_declaration
from scripts.syndwars_orchestrate import load_sources, parse_signature

PAGE = 0x1000
LOAD_BASE = 0x00100000
EXTERN_BASE = 0x10000000
EXTERN_SLOT = 0x20000
STACK_BASE = 0x7F000000
STACK_SIZE = 0x40000
RETURN_SENTINEL = 0x7EFF0000
POINTER_ARENA = 0x40000000
ADDRESS_MARGIN = 0x400000
EXPLAIN_LISTING = "ultime"
TRACE_EVENTS_MAX = 20000
TRACE_PCS_KEPT = 400
# Ghidra le legge con la convenzione a registri e ne sbaglia gli argomenti: non si confrontano e nella bozza non possono restare.
DEBUG_FORMATTERS = {"sprintf"}
TRUNCATED_MIN_CALLS = 10
TRUNCATED_RATIO = 0.9
MAX_INSTRUCTIONS = 200_000
# Il C a -O0 esegue molte piu' istruzioni dell'assembly: stesso lavoro, budget piu' alto.
# Casi guidati: un argomento prende un valore che la funzione ha letto dalla memoria, cosi' i rami "uguale" vengono eseguiti.
GUIDED_SEEDS = 30
GUIDED_READS_KEPT = 12
GUIDED_CASES_MAX = 200
CANDIDATE_MAX_INSTRUCTIONS = 5_000_000
# Oltre questa soglia, se i casi senza esito superano gli accordi, la funzione non arrivera' alla maggioranza.
LIMIT_CASES_BEFORE_STOP = 100
MISMATCHES_BEFORE_STOP = 20
# Tetto per funzione, mutanti compresi: una sola funzione lenta non deve fermare tutta la verifica.
FUNCTION_TIME_LIMIT_S = 900
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
    reads: List[int] = field(default_factory=list)
    narrow_args: List[Tuple[str, int, bool]] = field(default_factory=list)


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
        if "(" in param:
            types.append("void *")
            continue
        if "*" in param:
            types.append(param.replace("const", "")[:param.replace("const", "").rindex("*") + 1].strip())
            continue
        words = param.replace("const", "").split()
        if "struct" in words or "long long" in " ".join(words):
            return None
        types.append(" ".join(words[:-1]) if len(words) > 1 else words[0])
    return return_type, types


@functools.lru_cache(maxsize=1)
def project_typedefs() -> Dict[str, str]:
    found: Dict[str, str] = {}
    for root in (SWARS_DIR / "src", SWARS_DIR / "bflibrary" / "include"):
        for header in root.rglob("*.h"):
            text = header.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r"^\s*typedef\s+((?:unsigned\s+|signed\s+)?\w+)\s+(\w+)\s*;", text, re.MULTILINE):
                found.setdefault(match.group(2), " ".join(match.group(1).split()))
    return found


_BUILTIN_WORDS = {"unsigned short": "ushort", "unsigned char": "ubyte", "signed char": "sbyte", "signed short": "short"}
_KNOWN_WIDTHS = {"short", "s16", "ThingIdx", "ushort", "u16", "ubyte", "u8", "TbBool", "char", "sbyte", "s8"}


def resolve_base_type(ctype: str, typedefs: Optional[Dict[str, str]] = None) -> str:
    """Segue i typedef del progetto: `MapCoord` e' un `short`, e il chiamante passa valori di quel dominio."""
    table = project_typedefs() if typedefs is None else typedefs
    base = ctype.replace("const", "").strip()
    for _ in range(8):
        if base in _KNOWN_WIDTHS or base not in table:
            break
        base = table[base]
    return _BUILTIN_WORDS.get(base, base)


def narrow_value(ctype: str, raw: int) -> int:
    """Il valore come lo vede il C dopo la conversione al tipo, esteso a 32 bit."""
    if "*" in ctype:
        return raw & 0xFFFFFFFF
    base = resolve_base_type(ctype)
    if base in ("short", "s16", "ThingIdx"):
        return struct.unpack("<h", struct.pack("<H", raw & 0xFFFF))[0] & 0xFFFFFFFF
    if base in ("ushort", "u16"):
        return raw & 0xFFFF
    if base in ("ubyte", "u8", "TbBool"):
        return raw & 0xFF
    if base in ("char", "sbyte", "s8"):
        return struct.unpack("<b", struct.pack("<B", raw & 0xFF))[0] & 0xFFFFFFFF
    return raw & 0xFFFFFFFF


def pointee_width(ctype: str) -> int:
    """Byte che uno stub puo' scrivere dietro un puntatore allo stack; 0 se la dimensione non si conosce."""
    if "*" not in ctype:
        return 4  # Firma ricavata: il tipo non si conosce, l'argomento e' comunque un indirizzo.
    base = resolve_base_type(ctype[:ctype.rindex("*")])
    if ctype.count("*") > 1:
        return 4
    return {"short": 2, "s16": 2, "ushort": 2, "u16": 2, "ThingIdx": 2, "ubyte": 1, "u8": 1, "char": 1, "sbyte": 1, "s8": 1,
            "int": 4, "long": 4, "ulong": 4, "u32": 4, "s32": 4}.get(base, 0)


def apply_memory_helper(emu: Uc, name: str, raw: Sequence[int]) -> bool:
    """`memset` e simili fanno davvero il loro lavoro: spesso preparano buffer che la funzione poi legge."""
    if name not in ("memset", "memcpy", "memmove") or len(raw) < 3 or raw[2] > 0x10000:
        return False
    try:
        data = bytes([raw[1] & 0xFF]) * raw[2] if name == "memset" else bytes(emu.mem_read(raw[1], raw[2]))
        emu.mem_write(raw[0], data)
    except UcError:
        pass  # Destinazione non mappata: stesso esito per le due versioni.
    return True


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


def _helper_operands(emu: Uc) -> Tuple[int, int]:
    esp = emu.reg_read(UC_X86_REG_ESP)
    left, right = struct.unpack("<QQ", emu.mem_read(esp + 4, 16))
    return left, right


def _signed64(value: int) -> int:
    return value - (1 << 64) if value >> 63 else value


def _truncated_div(left: int, right: int) -> int:
    quotient = abs(left) // abs(right)
    return -quotient if (left < 0) != (right < 0) else quotient


# Il compilatore a 32 bit chiama queste funzioni per l'aritmetica a 64 bit: l'assembly usa `div` e `idiv`.
COMPILER_HELPERS = {
    "__udivdi3": lambda a, b: a // b,
    "__umoddi3": lambda a, b: a % b,
    "__divdi3": lambda a, b: _truncated_div(_signed64(a), _signed64(b)),
    "__moddi3": lambda a, b: _signed64(a) - _truncated_div(_signed64(a), _signed64(b)) * _signed64(b),
}


def run_case(image: Image, entry: int, args: Sequence[int], stack_args: Sequence[int], cdecl: bool, seed: int,
             callees: Sequence[Callee] = (), saved_seed: Optional[int] = None, max_instructions: int = MAX_INSTRUCTIONS,
             collect_reads: bool = False, trace: Optional[Dict[str, Any]] = None) -> RunResult:
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    low = min(b for b, _ in image.blobs) & ~(PAGE - 1)
    high = (max(b + len(d) for b, d in image.blobs) + PAGE) & ~(PAGE - 1)
    uc.mem_map(low, high - low)
    for base, data in image.blobs:
        uc.mem_write(base, data)
    uc.mem_map(STACK_BASE, STACK_SIZE)
    # Il seme alternativo cambia anche lo stack: serve a vedere se l'originale legge locali non inizializzate.
    uc.mem_write(STACK_BASE, fill_page(seed if saved_seed is None else saved_seed, STACK_BASE) * (STACK_SIZE // PAGE))
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
    narrow_args: List[Tuple[str, int, bool]] = []
    sequences: Dict[str, int] = {}

    def on_stub(emu: Uc, _address: int, _size: int, callee: Callee) -> None:
        esp = emu.reg_read(UC_X86_REG_ESP)
        seen = []
        raw_values = []
        if callee.name in DEBUG_FORMATTERS:
            emu.reg_write(UC_X86_REG_EAX, 0)  # solo messaggi di debug: la bozza li toglie, vedi drop_debug_sprintf
            return
        for index, ctype in enumerate(callee.params):
            if not cdecl and index < len(REGISTERS):
                raw = emu.reg_read(REGISTERS[index])
            else:
                slot = index if cdecl else index - len(REGISTERS)
                raw = struct.unpack("<I", emu.mem_read(esp + 4 + slot * 4, 4))[0]
            raw_values.append(raw)
            if is_narrow_type(ctype):
                narrow_args.append((callee.name, index, looks_like_address(raw, len(image.externs))))
            # Le due versioni tengono i buffer locali in punti diversi dello stack.
            seen.append("stack" if STACK_BASE <= raw < STACK_BASE + STACK_SIZE else narrow_value(ctype, raw))
        calls.append((callee.name, *seen))
        sequence = sequences.get(callee.name, 0)
        sequences[callee.name] = sequence + 1
        if not apply_memory_helper(emu, callee.name, raw_values):
            # Il chiamato riempie spesso i buffer locali: stesso contenuto ai due lati, non stesso indirizzo.
            for index, raw in enumerate(raw_values):
                width = pointee_width(callee.params[index])
                if width and STACK_BASE <= raw < STACK_BASE + STACK_SIZE:
                    value = random.Random(f"{seed}:{callee.name}:{sequence}:{index}").getrandbits(8 * width)
                    emu.mem_write(raw, value.to_bytes(width, "little"))
        if callee.return_type != "void":
            emu.reg_write(UC_X86_REG_EAX, stub_return(callee, sequence, seed))

    helper_fault = [False]

    def on_helper(emu: Uc, _address: int, _size: int, operation: Any) -> None:
        left, right = _helper_operands(emu)
        if right == 0:
            helper_fault[0] = True  # Come `div` per zero nell'assembly.
            emu.emu_stop()
            return
        result = operation(left, right) & 0xFFFFFFFFFFFFFFFF
        emu.reg_write(UC_X86_REG_EAX, result & 0xFFFFFFFF)
        emu.reg_write(UC_X86_REG_EDX, result >> 32)

    for name, operation in COMPILER_HELPERS.items():
        if name in image.externs and cdecl:
            address = image.externs[name]
            uc.mem_map(address & ~(PAGE - 1), PAGE)
            uc.mem_write(address, b"\xc3")
            uc.hook_add(UC_HOOK_CODE, on_helper, operation, address, address)

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

    reads: List[int] = []

    def on_read(emu: Uc, _access: int, address: int, size: int, _value: int, _data: Any) -> None:
        if size not in (2, 4) or STACK_BASE <= address < STACK_BASE + STACK_SIZE or len(reads) >= GUIDED_READS_KEPT:
            return
        try:
            raw = bytes(emu.mem_read(address, size))
        except UcError:
            page = address & ~(PAGE - 1)
            raw = fill_page(seed, page)[address - page:address - page + size]
        value = int.from_bytes(raw, "little", signed=True)
        if value not in reads:
            reads.append(value)

    if collect_reads:
        uc.hook_add(UC_HOOK_MEM_READ, on_read)
    uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    if trace is not None:
        trace.setdefault("mem", [])
        trace.setdefault("pcs", [])

        def on_trace_mem(_emu: Uc, access: int, address: int, size: int, _value: int, _data: Any) -> None:
            if STACK_BASE <= address < STACK_BASE + STACK_SIZE or len(trace["mem"]) >= TRACE_EVENTS_MAX:
                return
            if access == UC_MEM_WRITE:
                number = _value & ((1 << (8 * size)) - 1)
            else:
                try:
                    number = int.from_bytes(bytes(_emu.mem_read(address, size)), "little")
                except UcError:
                    number = -1
            event = ("scrive" if access == UC_MEM_WRITE else "legge", address, size, number)
            if not trace["mem"] or trace["mem"][-1][:3] != event[:3]:
                trace["mem"].append(event)
                trace.setdefault("pc_of", []).append(_emu.reg_read(UC_X86_REG_EIP))

        def on_trace_code(_emu: Uc, address: int, _size: int, _data: Any) -> None:
            trace["pcs"].append(address)
            if len(trace["pcs"]) > TRACE_PCS_KEPT:
                del trace["pcs"][0]

        uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, on_trace_mem)
        uc.hook_add(UC_HOOK_CODE, on_trace_code)
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
        if helper_fault[0]:
            status = "fault:21"
        elif uc.reg_read(UC_X86_REG_EIP) != RETURN_SENTINEL:
            status = "limit"
    except UcError as exc:
        status = f"fault:{exc.errno}"
    # Conta lo stato finale: riscrivere il valore gia' presente non cambia nulla.
    changed = {a: v for a, v in writes.items() if initial.get(a) != v}
    return RunResult(status, uc.reg_read(UC_X86_REG_EAX), changed, covered, calls, reads, narrow_args)


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
    for label in asm_call_targets(target["asm_code"]):
        name = re.sub(r"^(?:ac_|ASM_)", "", label)
        if name != target["func_name"]:
            found.setdefault(name, label)
    return found


def build_callees(target: Dict[str, Any], image: Image, asm: LoadedObject, candidate: LoadedObject,
                  inferred: Optional[Dict[str, str]] = None) -> Tuple[List[Callee], List[Callee], List[str]]:
    """Stub per i due lati e l'elenco delle chiamate che non si possono rappresentare."""
    asm_side: List[Callee] = []
    c_side: List[Callee] = []
    blocked: List[str] = []
    sources = list(load_sources(target["c_file"]))
    for name, label in called_functions(target).items():
        parsed = ("int", []) if name in DEBUG_FORMATTERS else parse_declaration(lookup_declaration(name, sources, inferred))
        if not parsed:
            blocked.append(name)
            continue
        return_type, params = parsed
        asm_address = asm.symbols.get(label, image.externs.get(label))
        if asm_address is None:
            blocked.append(name)
            continue
        asm_side.append(Callee(name, return_type, params, asm_address, max(0, len(params) - len(REGISTERS)) * 4))
        c_address = candidate.symbols.get(name, image.externs.get(name, image.globals.get(name, image.locals.get(name))))
        if c_address is not None:
            c_side.append(Callee(name, return_type, params, c_address))
    return asm_side, c_side, blocked


def is_narrow_type(ctype: str) -> bool:
    return narrow_value(ctype, 0x12345678) != 0x12345678


def looks_like_address(raw: int, extern_count: int) -> bool:
    """Il valore cade fra i dati globali simulati (con margine per gli indici) o nell'arena dei puntatori."""
    return (EXTERN_BASE - ADDRESS_MARGIN <= raw < EXTERN_BASE + extern_count * EXTERN_SLOT + ADDRESS_MARGIN
            or POINTER_ARENA <= raw < POINTER_ARENA + ADDRESS_MARGIN * 8)


def truncated_addresses(asm_seen: Dict[Tuple[str, int], List[int]], c_seen: Dict[Tuple[str, int], List[int]]) -> List[str]:
    """Parametri dichiarati stretti (short, byte) dove l'assembly passa quasi sempre un indirizzo e la bozza no.

    Il confronto delle chiamate riduce entrambi i lati al tipo dichiarato, quindi un puntatore troncato dalla bozza
    non si vede: `rotate_obj(..., short zang)` passava il verificatore e nel gioco andava in crash."""
    found = []
    for key, (addresses, total) in asm_seen.items():
        c_addresses, c_total = c_seen.get(key, [0, 0])
        if total >= TRUNCATED_MIN_CALLS and addresses >= total * TRUNCATED_RATIO and c_addresses < c_total * TRUNCATED_RATIO:
            found.append(f"{key[0]}#{key[1]}")
    return sorted(found)


def disassemble_object(obj: Path) -> Tuple[Dict[int, str], Dict[str, int]]:
    """({offset: istruzione}, {simbolo: offset}) dalla disassemblazione dell'oggetto assemblato."""
    done = subprocess.run(["objdump", "-d", "--no-show-raw-insn", str(obj)], capture_output=True, text=True)
    lines: Dict[int, str] = {}
    symbols: Dict[str, int] = {}
    for line in done.stdout.splitlines():
        header = re.match(r"([0-9a-f]+) <([^>]+)>:", line)
        if header:
            symbols[header.group(2)] = int(header.group(1), 16)
            continue
        row = re.match(r"\s*([0-9a-f]+):\s*(.*)", line)
        if row:
            lines[int(row.group(1), 16)] = row.group(2).strip()
    return lines, symbols


def explain_divergence(original: Dict[str, Any], rebuilt: Dict[str, Any], names: Dict[int, str], listing: Dict[int, str],
                       delta: int) -> List[str]:
    """Testo che indica dove originale e bozza smettono di comportarsi allo stesso modo.

    Confronta la sequenza di letture e scritture su memoria non di stack (le due versioni toccano i dati nello stesso
    ordine anche se il codice e' diverso) e mostra le ultime istruzioni eseguite dall'originale."""
    def name_of(address: int) -> str:
        best = max((a for a in names if a <= address), default=None)
        return f"{names[best]}+{address - best:#x}" if best is not None and address - best < 0x100000 else f"{address:#x}"

    def show(event: Tuple[str, int, int, int]) -> str:
        return f"{event[0]} {name_of(event[1])} ({event[2]} byte) = {event[3]:#x}"

    a, b = original["mem"], rebuilt["mem"]
    out: List[str] = []
    # Il compilatore ordina gli accessi diversamente: si confrontano gli insiemi, non le sequenze.
    # Un accesso da 4 byte dell'originale e due da 2 byte della bozza sono lo stesso dato: si confrontano i byte toccati.
    def covered(events: List[Tuple[str, int, int, int]], kind: str) -> Set[int]:
        return {address + k for e in events if e[0] == kind for address in (e[1],) for k in range(e[2])}

    covered_a = {kind: covered(a, kind) for kind in ("legge", "scrive")}
    covered_b = {kind: covered(b, kind) for kind in ("legge", "scrive")}
    only_a = [(i, e) for i, e in enumerate(a) if not all(e[1] + k in covered_b[e[0]] for k in range(e[2]))]
    only_b = [(i, e) for i, e in enumerate(b) if not all(e[1] + k in covered_a[e[0]] for k in range(e[2]))]
    out.append(f"accessi alla memoria: originale {len(a)}, bozza {len(b)}")
    out.append(f"   solo l'originale ({len(only_a)}): " + "; ".join(f"#{i} {show(e)}" for i, e in only_a[:4]))
    out.append(f"   solo la bozza ({len(only_b)}): " + "; ".join(f"#{i} {show(e)}" for i, e in only_b[:4]))
    for label, events, only in (("originale", a, only_a), ("bozza", b, only_b)):
        if only:
            first = only[0][0]
            out.append(f"   attorno al primo accesso solo {label} (#{first}): " + "; ".join(show(e) for e in events[max(0, first - 4):first + 2]))
    # Stessi indirizzi ma valori diversi: la prima scrittura dell'originale il cui valore finale non coincide.
    def last_values(events: List[Tuple[str, int, int, int]]) -> Dict[int, int]:
        values: Dict[int, int] = {}
        for kind, address, size, number in events:
            if kind == "scrive":
                for k in range(size):
                    values[address + k] = (number >> (8 * k)) & 0xFF
        return values

    final_a, final_b = last_values(a), last_values(b)
    for index, event in enumerate(a):
        if event[0] == "scrive" and any(final_a.get(event[1] + k) != final_b.get(event[1] + k) for k in range(event[2])):
            wrong = next(k for k in range(event[2]) if final_a.get(event[1] + k) != final_b.get(event[1] + k))
            out.append(f"   prima scrittura con valore finale diverso: originale #{index} {show(event)}; "
                       f"al byte {event[1] + wrong:#x} originale {final_a.get(event[1] + wrong)}, bozza {final_b.get(event[1] + wrong)}")
            if original.get("pc_of") and index < len(original["pc_of"]):
                pc = original["pc_of"][index] - delta
                out.append(f"      istruzione che scrive (offset {pc:#x}) e le {EXPLAIN_LISTING} prima nell'assembly:")
                for offset in sorted(o for o in listing if pc - 120 <= o <= pc):
                    out.append(f"         {offset:#06x}  {listing[offset]}")
            out.append("      letture dell'originale prima: " + "; ".join(show(e) for e in a[max(0, index - 8):index]))
            twin = next((j for j, e in enumerate(b) if e[0] == "scrive" and e[1] <= event[1] < e[1] + e[2]), None)
            if twin is not None:
                out.append(f"      la bozza scrive li' a #{twin}: " + "; ".join(show(e) for e in b[max(0, twin - 8):twin + 1]))
            break
    first_a = [e for e in a if e[0] == "scrive"][:10]
    first_b = [e for e in b if e[0] == "scrive"][:10]
    out.append("   prime scritture, originale: " + "; ".join(f"{name_of(e[1])}={e[3]:#x}" for e in first_a))
    out.append("   prime scritture, bozza:     " + "; ".join(f"{name_of(e[1])}={e[3]:#x}" for e in first_b))
    out.append("ultime istruzioni dell'originale (la penultima decisione e' quasi sempre un salto condizionato):")
    for pc in original["pcs"][-12:]:
        out.append(f"   {pc - delta:#06x}  {listing.get(pc - delta, '?')}")
    return out


def same_behaviour(first: RunResult, second: RunResult, mask: int) -> bool:
    return (first.status == second.status and (first.eax & mask) == (second.eax & mask)
            and first.writes == second.writes and first.calls == second.calls)


def compare_function(target: Dict[str, Any], code: str, work: Path, asm_obj: Path, cases: int, label: str,
                     max_mismatches: int = MISMATCHES_BEFORE_STOP, deadline: Optional[float] = None,
                     explain: bool = False) -> Dict[str, Any]:
    explain = explain or bool(os.environ.get("SW_EXPLAIN"))
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
    inferred = load_inferred_signatures()
    asm_callees, c_callees, blocked = build_callees(target, image, asm, candidate, inferred)
    blocked += [formatter for formatter in sorted(DEBUG_FORMATTERS)
                if re.search(rf"\b{formatter}\s*\(", code) and formatter not in blocked]
    if blocked:
        return {"func": name, "verdict": "unsupported_calls", "error": ", ".join(blocked)}
    start, end = function_extent(asm.symbols, name, target["asm_line_count"])
    listing: Dict[int, str] = {}
    delta = 0
    if explain:
        listing, object_symbols = disassemble_object(asm_obj)
        # con due simboli allo stesso indirizzo objdump ne stampa uno solo
        delta = start - object_symbols.get(f"ASM_{name}", object_symbols.get(name, 0))
        known: Dict[int, str] = {}
        for table in (image.globals, image.locals, image.externs, asm.symbols, candidate.symbols):
            known.update({address: symbol for symbol, address in table.items()})
    # `return_ignored`: nessun chiamante usa il ritorno, che nell'originale e' un residuo di registro.
    mask = 0 if return_type == "void" or target.get("return_ignored") else RETURN_MASKS.get(resolve_base_type(return_type), 0xFFFFFFFF)

    rng = random.Random(0x5EED)
    agreed = inconclusive = completed = undefined = disagreed = 0
    stopped_early = False
    mismatches: List[Dict[str, Any]] = []
    covered: Set[int] = set()
    timed_out = False
    asm_faults = [0]
    explanation: List[str] = []
    narrow_asm: Dict[Tuple[str, int], List[int]] = {}
    narrow_c: Dict[Tuple[str, int], List[int]] = {}
    def compare_case(case: int, values: List[int]) -> str:
        """Esegue le due versioni con lo stesso seme: 'agree', 'limit', 'undefined' o 'mismatch'."""
        nonlocal disagreed, completed
        reg_args, stack_args = values[:4], values[4:]
        original = run_case(image, start, reg_args, stack_args, False, case + 1, asm_callees)
        budget = CANDIDATE_MAX_INSTRUCTIONS if original.status == "ok" else MAX_INSTRUCTIONS
        rebuilt = run_case(image, candidate.symbols[name], values, [], True, case + 1, c_callees, max_instructions=budget)
        covered.update(a for a in original.covered if start <= a < end)
        for seen_args, table in ((original.narrow_args, narrow_asm), (rebuilt.narrow_args, narrow_c)):
            for callee, index, is_address in seen_args:
                slot = table.setdefault((callee, index), [0, 0])
                slot[0] += is_address
                slot[1] += 1
        if original.status == "limit" and rebuilt.status == "limit":
            return "limit"
        # L'originale va in errore (divisione che trabocca, puntatore folle) e la bozza no: con quegli ingressi nessun
        # chiamante vero puo' arrivarci. Si conta a parte; resta un mismatch se e' la bozza ad andare in errore.
        if original.status.startswith("fault") and rebuilt.status == "ok":
            asm_faults[0] += 1
            return "asm_fault"
        same_status = original.status.split(":")[0] == rebuilt.status.split(":")[0]
        same_return = (original.eax & mask) == (rebuilt.eax & mask)
        if same_status and (original.status != "ok" or (same_return and original.writes == rebuilt.writes and original.calls == rebuilt.calls)):
            completed += original.status == "ok"
            return "agree"
        # Se l'assembly cambia esito coi soli registri non inizializzati, nessun C puo' riprodurlo.
        # Piu' semi: un valore non inizializzato e poi mascherato puo' coincidere per caso.
        probes = (run_case(image, start, reg_args, stack_args, False, case + 1, asm_callees, saved_seed=(case + 1) * 0x10001 + k) for k in range(3))
        if any(not same_behaviour(original, probe, mask) for probe in probes):
            return "undefined"
        disagreed += 1
        # Si spiega un caso in cui entrambe le versioni finiscono normalmente: gli altri sono quasi sempre ingressi folli.
        if explain and not explanation and (original.status == "ok" and rebuilt.status == "ok" or len(mismatches) >= 4):
            original_trace: Dict[str, Any] = {}
            rebuilt_trace: Dict[str, Any] = {}
            run_case(image, start, reg_args, stack_args, False, case + 1, asm_callees, trace=original_trace)
            run_case(image, candidate.symbols[name], values, [], True, case + 1, c_callees, max_instructions=budget, trace=rebuilt_trace)
            explanation.extend(explain_divergence(original_trace, rebuilt_trace, known, listing, delta))
        if len(mismatches) < 5:
            diff = sorted(a for a in set(original.writes) | set(rebuilt.writes) if original.writes.get(a) != rebuilt.writes.get(a))
            mismatches.append({"case": case + 1, "args": [hex(v & 0xFFFFFFFF) for v in values],
                               "status": [original.status, rebuilt.status],
                               "return": [hex(original.eax & mask), hex(rebuilt.eax & mask)],
                               "write_diffs": [hex(a) for a in diff[:6]], "n_write_diffs": len(diff),
                               "write_values": [[hex(a), original.writes.get(a), rebuilt.writes.get(a)] for a in diff[:6]],
                               "calls": [] if original.calls == rebuilt.calls else [str(original.calls[:4]), str(rebuilt.calls[:4])]})
        return "mismatch"

    first_values: List[List[int]] = []
    for case in range(cases):
        if deadline is not None and time.monotonic() > deadline:
            stopped_early = timed_out = True
            break
        values = choose_args(params, rng)
        if case < GUIDED_SEEDS:
            first_values.append(values)
        outcome = compare_case(case, values)
        if outcome == "limit":
            inconclusive += 1
            if inconclusive > LIMIT_CASES_BEFORE_STOP and inconclusive > agreed:
                stopped_early = True
                break
        elif outcome == "agree":
            agreed += 1
        elif outcome == "undefined":
            undefined += 1
        elif outcome == "asm_fault":
            continue
        elif disagreed >= max_mismatches:
            stopped_early = True
            break

    # Casi guidati: gli input casuali non coincidono quasi mai con i valori in memoria e i rami "uguale" restano scoperti.
    guided = guided_failed = 0
    scalar = [i for i, (ctype, _p) in enumerate(params) if "*" not in ctype]
    for case, values in enumerate(first_values):
        if stopped_early or guided >= GUIDED_CASES_MAX or not scalar:
            break
        reg_args, stack_args = values[:4], values[4:]
        seen = run_case(image, start, reg_args, stack_args, False, case + 1, asm_callees, collect_reads=True).reads
        for read in seen:
            for index in scalar:
                if guided >= GUIDED_CASES_MAX or (deadline is not None and time.monotonic() > deadline):
                    break
                trial = list(values)
                trial[index] = narrow_value(params[index][0], read & 0xFFFFFFFF) & 0xFFFFFFFF  # come farebbe un chiamante vero
                guided += 1
                guided_failed += compare_case(case, trial) == "mismatch"
    coverage = len(covered) / max(1, end - start)
    verdict = "mismatch" if disagreed else "inconclusive" if agreed < cases // 2 else "agree"
    if verdict == "agree" and completed < cases // 2:
        verdict = "inconclusive"  # Un guasto comune non confronta nulla.
    truncated = truncated_addresses(narrow_asm, narrow_c)
    if truncated and verdict == "agree":
        verdict = "mismatch"
    return {"func": name, "verdict": verdict, "agreed": agreed, "completed": completed, "disagreed": disagreed, "inconclusive": inconclusive, "undefined_input": undefined, "stopped_early": stopped_early, "timed_out": timed_out,
            "guided": guided, "guided_failed": guided_failed, "asm_faults": asm_faults[0], "explanation": explanation, "truncated_addresses": truncated, "inferred_callees": sorted(c.name for c in asm_callees if c.name in inferred and not lookup_declaration(c.name, load_sources(target["c_file"]))),
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


def mutation_score(target: Dict[str, Any], code: str, work: Path, asm_obj: Path, cases: int, label: str,
                   deadline: Optional[float] = None) -> Dict[str, Any]:
    killed, survived, unbuilt, timed_out = 0, [], 0, 0
    signature = target["current_c_stub"].split("{")[0].strip()
    for index, (description, mutant) in enumerate(make_mutants(code, signature)):
        outcome = compare_function(target, mutant, work, asm_obj, cases, f"{label}_m{index}", max_mismatches=1, deadline=deadline)
        if outcome.get("timed_out"):
            timed_out += 1  # Ne' preso ne' sopravvissuto: la prova resta incompleta.
        elif outcome["verdict"] == "not_built":
            unbuilt += 1
        elif outcome["verdict"] == "mismatch":
            killed += 1
        else:
            survived.append(description)
    return {"killed": killed, "survived": survived, "unbuilt": unbuilt, "timed_out": timed_out}


def verify_one(target: Dict[str, Any], code: str, asm_obj: Path, cases: int, with_mutants: bool) -> Dict[str, Any]:
    """Un processo per funzione: ognuno ha la sua cartella, cosi' gli stub degli header non si intralciano."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        deadline = time.monotonic() + FUNCTION_TIME_LIMIT_S
        result = compare_function(target, code, work, asm_obj, cases, "cand", deadline=deadline)
        if result["verdict"] == "agree" and with_mutants:
            result["mutants"] = mutation_score(target, code, work, asm_obj, cases, "cand", deadline=deadline)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("functions", nargs="+", help="nome funzione oppure nome=percorso/file.c")
    parser.add_argument("--cases", type=int, default=300)
    parser.add_argument("--code-dir", default=str(ROOT / "data" / "nightly" / "syndwars_ghidra"))
    parser.add_argument("--output", default="")
    parser.add_argument("--no-mutants", action="store_true")
    parser.add_argument("--explain", action="store_true", help="al primo mismatch mostra dove originale e bozza divergono")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args()
    if args.explain:
        os.environ["SW_EXPLAIN"] = "1"
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
                for line in result.get("explanation", []):
                    print(f"   | {line}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
