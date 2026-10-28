# SPDX-License-Identifier: Apache-2.0
"""
Speculative Draft Validator per HyperSpace Sovereign Mesh.

Implementa lo speculative drafting asimmetrico: consente a modelli ausiliari
o a nodi leggeri/veloci (es. HP OMEN 24B Coder) di proporre bozze di codice
o contratti, mentre il nodo primario (es. ASUS Flint 40B o Mac M5 Hub) esegue
la validazione rapida parallela (sintassi, AST, vincoli e contratti) senza
dover rigenerare da zero l'intero output.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class Draft:
    """Rappresenta una bozza di codice o risposta generata speculativamente."""
    source: str
    model_id: str
    task_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Esito della validazione rapida del draft."""
    status: str  # "ACCEPTED" | "REJECTED"
    ast_valid: bool
    errors: List[str] = field(default_factory=list)
    node_count: int = 0
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def is_accepted(self) -> bool:
        return self.status == "ACCEPTED"


class SpeculativeDraftValidator:
    """
    Validatore speculativo parallelo con controllo AST, sintassi e contratti.
    """

    def __init__(
        self,
        required_constructs: Optional[List[str]] = None,
        disallow_patterns: Optional[List[str]] = None,
        custom_rules: Optional[List[Callable[[str, ast.AST], Optional[str]]]] = None
    ):
        self.required_constructs = required_constructs or []
        self.disallow_patterns = disallow_patterns or ["__import__('os').system", "shutil.rmtree('/')"]
        self.custom_rules = custom_rules or []

    def verify(self, draft: Draft) -> ValidationResult:
        """Esegue validazione rapida AST e semantica del draft."""
        t0 = time.perf_counter()
        errors: List[str] = []
        source = draft.source.strip()

        if not source:
            elapsed = (time.perf_counter() - t0) * 1000
            return ValidationResult(status="REJECTED", ast_valid=False, errors=["Bozza vuota"], elapsed_ms=elapsed)

        for pat in self.disallow_patterns:
            if pat in source:
                errors.append(f"Pattern non consentito rilevato: '{pat}'")

        tree: Optional[ast.AST] = None
        ast_valid = False
        node_count = 0
        classes: List[str] = []
        functions: List[str] = []

        try:
            tree = ast.parse(source, filename=f"<draft_{draft.model_id}>")
            ast_valid = True
            node_count = sum(1 for _ in ast.walk(tree))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append(node.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions.append(node.name)

        except SyntaxError as syn_err:
            errors.append(f"SyntaxError (linea {syn_err.lineno}): {syn_err.msg}")

        # Controllo costrutti richiesti
        if ast_valid and self.required_constructs:
            for req in self.required_constructs:
                if req == "class" and not classes:
                    errors.append("Nessuna classe definita nella bozza (richiesta da specifica)")
                elif req == "def" and not functions:
                    errors.append("Nessuna funzione definita nella bozza (richiesta da specifica)")

        # Esecuzione regole custom se AST è valido
        if tree is not None:
            for rule in self.custom_rules:
                try:
                    rule_err = rule(source, tree)
                    if rule_err:
                        errors.append(rule_err)
                except Exception as exc:
                    errors.append(f"Errore validazione custom: {exc}")

        elapsed = (time.perf_counter() - t0) * 1000
        status = "ACCEPTED" if not errors and ast_valid else "REJECTED"

        return ValidationResult(
            status=status,
            ast_valid=ast_valid,
            errors=errors,
            node_count=node_count,
            classes=classes,
            functions=functions,
            elapsed_ms=round(elapsed, 3)
        )

    def select_best_draft(self, drafts: List[Draft]) -> Optional[Draft]:
        """Verifica una serie di bozze concorrenti e seleziona la prima valida o più complessa."""
        accepted: List[tuple[Draft, ValidationResult]] = []
        for draft in drafts:
            res = self.verify(draft)
            if res.is_accepted:
                accepted.append((draft, res))

        if not accepted:
            return None

        # Ordina per complessità nodi AST decrescente (più ricca e completa)
        accepted.sort(key=lambda item: item[1].node_count, reverse=True)
        return accepted[0][0]
