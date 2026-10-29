# SPDX-License-Identifier: Apache-2.0
"""Unsloth Dataset Adapter per HyperSpace Sovereign Mesh.

Estrae e converte i dati sintetici generati dai nodi mesh
(data/synthetic_cot_dataset.jsonl, data/traces/*.ndjson, prototipi R&D validati)
in dataset formattati (Alpaca / ShareGPT / ChatML) per il fine-tuning con Unsloth (QLoRA 4-bit)
su GPU consumer da 8 GB di VRAM (HP OMEN 16 / ASUS V16).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


SYSTEM_PROMPT_DEFAULT = (
    "Sei un assistente AI sovrano del cluster distribuito HyperSpace AGI 1.05. "
    "Generi codice Python completo, rigorosamente conforme allo standard Apache-2.0, "
    "privo di allucinazioni sintattiche e orientato alla robustezza distribuita e thread-safe."
)


class UnslothDatasetAdapter:
    """Prepara e filtra i dataset di training dai dati operativi e sintetici di HyperSpace."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.synthetic_file = self.data_dir / "synthetic_cot_dataset.jsonl"
        self.traces_dir = self.data_dir / "traces"
        self.prototypes_dir = self.data_dir / "research" / "prototypes"

    def extract_from_synthetic_cot(self, max_samples: Optional[int] = None) -> List[Dict[str, Any]]:
        """Estrae coppie prompt-completamento dal dataset CoT sintetico di OMEN."""
        samples: List[Dict[str, Any]] = []
        if not self.synthetic_file.exists():
            return samples

        with open(self.synthetic_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    # Filtra solo se verificato positivamente
                    if record.get("verified") is False:
                        continue

                    instruction = record.get("prompt_topic") or record.get("prompt") or ""
                    output = record.get("distilled_cot") or record.get("response") or ""
                    if instruction and output:
                        samples.append({
                            "instruction": instruction.strip(),
                            "input": "",
                            "output": output.strip(),
                            "system": SYSTEM_PROMPT_DEFAULT,
                        })
                        if max_samples and len(samples) >= max_samples:
                            break
                except json.JSONDecodeError:
                    continue

        return samples

    def extract_from_ndjson_traces(self) -> List[Dict[str, Any]]:
        """Estrae esempi di tool call e interazioni riuscite dalle tracce NDJSON."""
        samples: List[Dict[str, Any]] = []
        if not self.traces_dir.exists():
            return samples

        for trace_file in self.traces_dir.glob("*.ndjson"):
            try:
                with open(trace_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line)
                        if event.get("event") == "tool_call" and event.get("ok"):
                            tool_name = event.get("tool", "")
                            args = event.get("arguments", {})
                            res = event.get("result_summary", "")
                            if tool_name and args and res:
                                samples.append({
                                    "instruction": f"Invia tool call per '{tool_name}' con argomenti conformi a HyperSpace.",
                                    "input": json.dumps(args, ensure_ascii=False),
                                    "output": f"Tool '{tool_name}' eseguito con successo: {res}",
                                    "system": SYSTEM_PROMPT_DEFAULT,
                                })
            except Exception:
                continue

        return samples

    def export_alpaca_json(self, output_path: str, include_traces: bool = True) -> int:
        """Genera un file JSON in formato Alpaca compatibile direttamente con Unsloth."""
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        dataset = self.extract_from_synthetic_cot()
        if include_traces:
            dataset.extend(self.extract_from_ndjson_traces())

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)

        return len(dataset)
