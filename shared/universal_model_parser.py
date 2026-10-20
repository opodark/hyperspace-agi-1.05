#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# shared/universal_model_parser.py
"""Universal Model Parser & Caveman Orchestrator per Modelli Eterogenei e Quantizzati.

Risolve l'eterogeneità degli output e i limiti di contesto dei modelli quantizzati
(Qwen 2.5/3, Liquid AI LFM2.5, DeepSeek R1/V3, Gemma 2/4, Mistral NeMo, Granite 3.3)
in esecuzione sulla mesh locale (HP Omen RTX 3070 8GB, Asus V16, Mac M5):

1. **Caveman Engine (Pre-Inference)**:
   Comprime prompt verbali in una sintassi densa, telegrafica e ad alta densità
   informativa, preservando rigorosamente contratti di codice, percorsi, firme e JSON.

2. **Universal Parser (Post-Inference)**:
   - Estrazione ed isolamento del ragionamento Chain-of-Thought (`<think>`, `Thought:`).
   - Estrazione codice con convalida AST Python e riparazione di fence markdown troncate.
   - Parser JSON resiliente (riparazione di virgolette singole, virgole finali, graffe non chiuse).
   - Estrazione chiamate tool multi-formato (XML `<tool_call>`, tag `[TOOL_CALLS]`, JSON puro).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


# -----------------------------------------------------------------------------
# 1. CAVEMAN COMPRESSION ENGINE
# -----------------------------------------------------------------------------

RE_CODE_BLOCK = re.compile(r"(```[a-zA-Z0-9_\-]*\n.*?```)", re.DOTALL)
RE_INLINE_CODE = re.compile(r"(`[^`\n]+`)")
RE_URL_PATH = re.compile(r"(https?://\S+|/[a-zA-Z0-9_\-\./]+|[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)")
RE_XML_TAG = re.compile(r"(<[a-zA-Z0-9_\-]+[^>]*>.*?</[a-zA-Z0-9_\-]+>)", re.DOTALL)

FILLER_PHRASES = [
    # Inglese
    r"\bplease note that\b",
    r"\bit is important to remember that\b",
    r"\bas mentioned previously\b",
    r"\bin order to\b",
    r"\bi would like to inform you that\b",
    r"\bcould you kindly\b",
    r"\bmake sure that you\b",
    r"\bat the present time\b",
    r"\bdue to the fact that\b",
    r"\bfor the purpose of\b",
    r"\bas a matter of fact\b",
    r"\bneedless to say\b",
    r"\bit goes without saying that\b",
    # Italiano
    r"\bsi prega di notare che\b",
    r"\bè importante ricordare che\b",
    r"\bvorrei informarti che\b",
    r"\ballo scopo di\b",
    r"\bcome accennato in precedenza\b",
    r"\bin questo momento\b",
    r"\balla luce del fatto che\b",
    r"\bnon c'è bisogno di dire che\b",
    r"\bassicurati di\b",
    r"\btieni presente che\b",
]

SUBSTITUTIONS = [
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\ballo scopo di\b", re.IGNORECASE), "per"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because"),
    (re.compile(r"\bper via del fatto che\b", re.IGNORECASE), "perché"),
    (re.compile(r"\bat the present time\b", re.IGNORECASE), "now"),
    (re.compile(r"\bin questo momento\b", re.IGNORECASE), "ora"),
    (re.compile(r"\bas soon as possible\b", re.IGNORECASE), "ASAP"),
    (re.compile(r"\bil prima possibile\b", re.IGNORECASE), "subito"),
]


class CavemanEngine:
    """Motore di compressione del prompt pre-inferenza per modelli quantizzati."""

    @staticmethod
    def compress(text: str, aggressive: bool = False) -> Dict[str, Any]:
        """Comprime il testo rimuovendo verbosità e preservando elementi critici."""
        if not text or len(text) < 40:
            return {
                "compressed": text,
                "original_len": len(text),
                "compressed_len": len(text),
                "savings_pct": 0.0,
            }

        original_len = len(text)

        # 1. Protezione dei blocchi di codice e tag XML
        protected_blocks: List[str] = []

        def _stash(match):
            placeholder = f"__PROTECTED_BLOCK_{len(protected_blocks)}__"
            protected_blocks.append(match.group(0))
            return placeholder

        # Maschera blocchi di codice markdown
        stashed_text = RE_CODE_BLOCK.sub(_stash, text)
        # Maschera tag XML/JSON completi
        stashed_text = RE_XML_TAG.sub(_stash, stashed_text)

        # 2. Sostituzioni concettuali
        for pattern, replacement in SUBSTITUTIONS:
            stashed_text = pattern.sub(replacement, stashed_text)

        # 3. Rimozione filler conversazionali
        for filler in FILLER_PHRASES:
            stashed_text = re.sub(filler, "", stashed_text, flags=re.IGNORECASE)

        # 4. Riduzione articoli e pronomi se modalità aggressiva (stile Caveman puro)
        if aggressive:
            aggressive_patterns = [
                (re.compile(r"\b(please|kindly|per favore|gentilmente)\b", re.IGNORECASE), ""),
                (re.compile(r"\b(you should|you must|dovresti|devi)\b", re.IGNORECASE), ""),
                (re.compile(r"\b(that is|which is|che è|il quale è)\b", re.IGNORECASE), ""),
            ]
            for pat, rep in aggressive_patterns:
                stashed_text = pat.sub(rep, stashed_text)

        # 5. Normalizzazione spazi multipli
        stashed_text = re.sub(r"[ \t]+", " ", stashed_text)
        stashed_text = re.sub(r"\n\s*\n\s*\n+", "\n\n", stashed_text).strip()

        # 6. Ripristino dei blocchi protetti
        for idx, block in enumerate(protected_blocks):
            stashed_text = stashed_text.replace(f"__PROTECTED_BLOCK_{idx}__", block)

        compressed_len = len(stashed_text)
        savings = round((1.0 - (compressed_len / max(1, original_len))) * 100.0, 1)

        return {
            "compressed": stashed_text,
            "original_len": original_len,
            "compressed_len": compressed_len,
            "savings_pct": max(0.0, savings),
        }


# -----------------------------------------------------------------------------
# 2. UNIVERSAL POST-INFERENCE PARSER
# -----------------------------------------------------------------------------

@dataclass
class CodeBlock:
    language: str
    code: str
    is_valid_ast: bool = False
    ast_error: Optional[str] = None


@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    raw_str: str = ""


@dataclass
class ParsedModelResponse:
    reasoning_cot: str = ""
    code_blocks: List[CodeBlock] = field(default_factory=list)
    json_data: Optional[Union[Dict[str, Any], List[Any]]] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    clean_text: str = ""
    raw_text: str = ""
    model_hint: str = "auto"
    has_valid_content: bool = False


class UniversalModelParser:
    """Parser unificato per output di LLM quantizzati (Qwen, LFM, DeepSeek, Gemma, Mistral)."""

    RE_COT = re.compile(r"<(?:think|thought)>(.*?)(?:</(?:think|thought)>|$)", re.DOTALL | re.IGNORECASE)
    RE_THOUGHT_PREFIX = re.compile(r"^(?:Thought|Reasoning):\s*(.*?)(?:\n\n(?:Final Answer|Response|Output):|\Z)", re.DOTALL | re.IGNORECASE)
    RE_CODE_FENCE = re.compile(r"```([a-zA-Z0-9_\-]*)\n(.*?)(?:```|\Z)", re.DOTALL)
    RE_QWEN_TOOL = re.compile(r"<tool_call>\s*({.*?})\s*</tool_call>", re.DOTALL)
    RE_MISTRAL_TOOL = re.compile(r"\[TOOL_CALLS\]\s*(\[.*?\]|\{.*?\})", re.DOTALL)

    @classmethod
    def extract_reasoning(cls, text: str) -> Tuple[str, str]:
        """Separa la catena di pensiero (CoT) dal testo effettivo di risposta."""
        cot_parts: List[str] = []
        cleaned = text

        # 1. Cerca tag <think>...</think>
        for match in cls.RE_COT.finditer(text):
            cot_parts.append(match.group(1).strip())
        if cot_parts:
            cleaned = cls.RE_COT.sub("", cleaned).strip()

        # 2. Cerca formato "Thought: ... Final Answer:" se non già trovato
        if not cot_parts:
            m = cls.RE_THOUGHT_PREFIX.search(cleaned)
            if m:
                cot_parts.append(m.group(1).strip())
                cleaned = cls.RE_THOUGHT_PREFIX.sub("", cleaned).strip()

        return "\n\n".join(cot_parts), cleaned

    @classmethod
    def extract_code(cls, text: str, default_lang: str = "python") -> List[CodeBlock]:
        """Estrae blocchi di codice, riparando markdown incompleto e verificando AST."""
        blocks: List[CodeBlock] = []

        matches = list(cls.RE_CODE_FENCE.finditer(text))
        for m in matches:
            lang = m.group(1).strip() or default_lang
            code = m.group(2).strip()
            if not code:
                continue

            valid_ast = False
            ast_err = None
            if lang.lower() in ("python", "py"):
                try:
                    ast.parse(code)
                    valid_ast = True
                except SyntaxError as e:
                    ast_err = f"SyntaxError at line {e.lineno}: {e.msg}"

            blocks.append(CodeBlock(language=lang, code=code, is_valid_ast=valid_ast, ast_error=ast_err))

        # Fallback: Se nessun blocco markdown ma il testo sembra Python grezzo
        if not blocks and ("def " in text or "import " in text or "class " in text):
            lines = [l for l in text.splitlines() if not l.startswith("<think>")]
            candidate = "\n".join(lines).strip()
            try:
                ast.parse(candidate)
                blocks.append(CodeBlock(language="python", code=candidate, is_valid_ast=True))
            except SyntaxError:
                pass

        return blocks

    @classmethod
    def repair_json_string(cls, json_str: str) -> str:
        """Applica euristiche di riparazione per JSON malformati generati da modelli quantizzati."""
        s = json_str.strip()

        # Rimuove wrapping markdown ```json ... ```
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z0-9_\-]*\n?", "", s)
            s = re.sub(r"\n?```$", "", s)
            s = s.strip()

        # Sostituisce virgolette singole con doppie (se non dentro virgolette doppie)
        # Euristica mirata per {'chiave': 'valore'}
        s = re.sub(r"(?<=[{\[,:\s])'([^']+)'(?=[}\],:\s])", r'"\1"', s)

        # Rimuove virgole finali prima di } o ]
        s = re.sub(r",\s*([\}\]])", r"\1", s)

        # Bilanciamento parentesi mancanti alla fine
        open_curly = s.count("{") - s.count("}")
        open_square = s.count("[") - s.count("]")

        if open_square > 0:
            s += "]" * open_square
        if open_curly > 0:
            s += "}" * open_curly

        return s

    @classmethod
    def extract_json(cls, text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """Tenta l'estrazione di un oggetto o array JSON, con algoritmi di auto-riparazione."""
        # Cerca outermost { ... } o [ ... ]
        start_curly = text.find("{")
        end_curly = text.rfind("}")
        start_square = text.find("[")
        end_square = text.rfind("]")

        candidates: List[str] = []

        if start_curly != -1 and end_curly != -1 and end_curly > start_curly:
            candidates.append(text[start_curly:end_curly + 1])
        if start_square != -1 and end_square != -1 and end_square > start_square:
            candidates.append(text[start_square:end_square + 1])

        # Se nessun delimitatore chiuso, prendi dal primo aperto fino alla fine
        if not candidates:
            if start_curly != -1:
                candidates.append(text[start_curly:])
            elif start_square != -1:
                candidates.append(text[start_square:])

        for cand in candidates:
            # 1. Prova parsing nativo
            try:
                return json.loads(cand)
            except Exception:
                pass

            # 2. Prova dopo riparazione euristica
            repaired = cls.repair_json_string(cand)
            try:
                return json.loads(repaired)
            except Exception:
                pass

        return None

    @classmethod
    def extract_tool_calls(cls, text: str) -> List[ToolCall]:
        """Estrae chiamate tool nei formati standard ed eterogenei."""
        calls: List[ToolCall] = []

        # 1. Qwen format: <tool_call>{...}</tool_call>
        for m in cls.RE_QWEN_TOOL.finditer(text):
            raw = m.group(1)
            parsed = cls.extract_json(raw)
            if isinstance(parsed, dict) and "name" in parsed:
                calls.append(ToolCall(
                    name=parsed["name"],
                    arguments=parsed.get("arguments") or parsed.get("parameters") or {},
                    raw_str=raw
                ))

        # 2. Mistral format: [TOOL_CALLS] [...]
        for m in cls.RE_MISTRAL_TOOL.finditer(text):
            raw = m.group(1)
            parsed = cls.extract_json(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "name" in item:
                        calls.append(ToolCall(
                            name=item["name"],
                            arguments=item.get("arguments") or item.get("parameters") or {},
                            raw_str=raw
                        ))
            elif isinstance(parsed, dict) and "name" in parsed:
                calls.append(ToolCall(
                    name=parsed["name"],
                    arguments=parsed.get("arguments") or parsed.get("parameters") or {},
                    raw_str=raw
                ))

        return calls

    @classmethod
    def parse(cls, raw_text: str, model_hint: str = "auto") -> ParsedModelResponse:
        """Esegue l'orchestrazione e l'analisi completa dell'output del modello."""
        if not raw_text:
            return ParsedModelResponse(raw_text=raw_text)

        cot, remaining = cls.extract_reasoning(raw_text)
        code_blocks = cls.extract_code(remaining)
        tool_calls = cls.extract_tool_calls(remaining)
        json_data = cls.extract_json(remaining)

        # Ripulisci testo rimuovendo codice e tool call
        clean_text = cls.RE_CODE_FENCE.sub("", remaining)
        clean_text = cls.RE_QWEN_TOOL.sub("", clean_text)
        clean_text = cls.RE_MISTRAL_TOOL.sub("", clean_text).strip()

        has_valid = bool(code_blocks or tool_calls or json_data or clean_text)

        return ParsedModelResponse(
            reasoning_cot=cot,
            code_blocks=code_blocks,
            json_data=json_data,
            tool_calls=tool_calls,
            clean_text=clean_text,
            raw_text=raw_text,
            model_hint=model_hint,
            has_valid_content=has_valid,
        )
