# SPDX-License-Identifier: Apache-2.0
"""Mutation Guard & HITL Proposal Gate per HyperSpace Mesh.

Ispirato al pattern di Human-In-The-Loop (HITL) di Atomic Agent:
separa rigorosamente le scoperte in sola lettura (read-only discovery: grep, read,
inspect, ast) dalle azioni mutanti (file write/delete, shell run, git commit, service restart).

Le azioni mutanti generano una `MutationProposal` tipizzata e controllabile,
che richiede approvazione esplicita prima di essere applicata, rispettando
la regola fondante del repository (AGENTS.md: nessun commit o push senza conferma).
Distingue chiaramente approvazioni manuali (HITL) da esecuzioni dichiarate autonome.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class ActionCategory(str, enum.Enum):
    READ_ONLY = "READ_ONLY"
    MUTATING = "MUTATING"
    CRITICAL_SYSTEM = "CRITICAL_SYSTEM"


class ProposalStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"                    # Approvato esplicitamente da operatore umano
    APPROVED_AUTOMATIC = "APPROVED_AUTOMATIC" # Approvato da pipeline in modalità autonoma esplicita
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


# Tool e azioni intrinsecamente sicuri (sola lettura / osservazione)
READ_ONLY_TOOLS: Set[str] = {
    "read_file",
    "list_dir",
    "grep_search",
    "ripgrep",
    "ast_inspect",
    "get_metrics",
    "node_status",
    "read_log",
    "view_diff",
}

# Azioni sicure all'interno di tool multi-azione come code_sandbox
READ_ONLY_SANDBOX_ACTIONS: Set[str] = {
    "status",
    "catalog",
    "inspect",
    "list",
    "read",
    "diff",
    "check",
    "verify",
}

# Comandi shell/git esplicitamente critici o mutanti
MUTATING_SHELL_PATTERNS = [
    "rm ",
    "mv ",
    "git commit",
    "git push",
    "git reset",
    "git checkout",
    "docker compose up",
    "docker compose down",
    "docker restart",
    "pip install",
    "npm install",
]


@dataclass
class MutationProposal:
    proposal_id: str
    tool_name: str
    arguments: Dict[str, Any]
    summary: str
    category: ActionCategory = ActionCategory.MUTATING
    diff: Optional[str] = None
    status: ProposalStatus = ProposalStatus.PENDING_APPROVAL
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    rejection_reason: Optional[str] = None
    approved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["status"] = self.status.value
        return d


class MutationGuard:
    """Guardiano delle mutazioni con archiviazione e gestione dello stato di approvazione."""

    def __init__(
        self,
        proposals_dir: str = "data/proposals",
        auto_approve_read_only: bool = True,
        strict_git_protection: bool = True,
    ):
        self.proposals_dir = Path(proposals_dir)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        self.auto_approve_read_only = auto_approve_read_only
        self.strict_git_protection = strict_git_protection
        self._proposals: Dict[str, MutationProposal] = {}
        self._load_existing_proposals()

    def _load_existing_proposals(self) -> None:
        """Carica eventuali proposte pendenti dal disco."""
        for pfile in self.proposals_dir.glob("*.json"):
            try:
                data = json.loads(pfile.read_text(encoding="utf-8"))
                prop = MutationProposal(
                    proposal_id=data["proposal_id"],
                    tool_name=data["tool_name"],
                    arguments=data["arguments"],
                    summary=data.get("summary", ""),
                    category=ActionCategory(data.get("category", ActionCategory.MUTATING.value)),
                    diff=data.get("diff"),
                    status=ProposalStatus(data.get("status", ProposalStatus.PENDING_APPROVAL.value)),
                    created_at=data.get("created_at", time.time()),
                    resolved_at=data.get("resolved_at"),
                    rejection_reason=data.get("rejection_reason"),
                    approved_by=data.get("approved_by"),
                )
                self._proposals[prop.proposal_id] = prop
            except Exception:
                continue

    def _save_proposal(self, proposal: MutationProposal) -> None:
        pfile = self.proposals_dir / f"{proposal.proposal_id}.json"
        pfile.write_text(json.dumps(proposal.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def classify_action(cls, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> ActionCategory:
        """Determina la categoria di rischio di un'azione o tool call."""
        t_name = (tool_name or "").lower().strip()
        args = arguments or {}

        if t_name in READ_ONLY_TOOLS:
            return ActionCategory.READ_ONLY

        if "action" in args:
            action = str(args["action"]).lower().strip()
            if action in READ_ONLY_SANDBOX_ACTIONS:
                return ActionCategory.READ_ONLY
            return ActionCategory.MUTATING

        if t_name in ("run_command", "shell_exec", "terminal", "execute_command"):
            cmd = str(args.get("command") or args.get("cmd") or "").strip().lower()
            if any(pat in cmd for pat in ("git commit", "git push", "rm -rf", "reboot", "shutdown")):
                return ActionCategory.CRITICAL_SYSTEM
            if any(pat in cmd for pat in MUTATING_SHELL_PATTERNS):
                return ActionCategory.MUTATING
            if cmd.startswith(("ls", "dir", "cat ", "head ", "tail ", "grep ", "git status", "git diff", "git log")):
                return ActionCategory.READ_ONLY

        return ActionCategory.MUTATING

    def create_proposal(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        summary: str = "",
        diff: Optional[str] = None,
    ) -> MutationProposal:
        """Crea e registra una nuova proposta di mutazione."""
        category = self.classify_action(tool_name, arguments)
        content_hash = hashlib.sha256(
            f"{tool_name}:{json.dumps(arguments, sort_keys=True)}:{time.time()}".encode("utf-8")
        ).hexdigest()[:12]
        proposal_id = f"prop_{content_hash}"

        auto_summary = summary or f"Richiesta esecuzione azione mutante '{tool_name}'"
        proposal = MutationProposal(
            proposal_id=proposal_id,
            tool_name=tool_name,
            arguments=arguments,
            summary=auto_summary,
            category=category,
            diff=diff,
            status=ProposalStatus.PENDING_APPROVAL,
        )

        self._proposals[proposal_id] = proposal
        self._save_proposal(proposal)
        return proposal

    def approve(self, proposal_id: str, approver: str = "human_operator") -> bool:
        """Approva formalmente una proposta pendente.

        Distingue se l'approvazione è data da un 'human_operator' reale o da 'autonomous_pipeline'.
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False
        if proposal.status != ProposalStatus.PENDING_APPROVAL:
            return False

        if approver == "human_operator":
            proposal.status = ProposalStatus.APPROVED
        else:
            proposal.status = ProposalStatus.APPROVED_AUTOMATIC

        proposal.approved_by = approver
        proposal.resolved_at = time.time()
        self._save_proposal(proposal)
        return True

    def reject(self, proposal_id: str, reason: str = "") -> bool:
        """Rifiuta una proposta pendente con motivazione."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False
        if proposal.status != ProposalStatus.PENDING_APPROVAL:
            return False

        proposal.status = ProposalStatus.REJECTED
        proposal.rejection_reason = reason or "Rifiutata dall'utente/governor"
        proposal.resolved_at = time.time()
        self._save_proposal(proposal)
        return True

    def execute_with_guard(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        executor: Callable[[str, Dict[str, Any]], Any],
        proposal_id: Optional[str] = None,
    ) -> Tuple[bool, Any]:
        """Esegue l'azione se è Read-Only oppure se è una mutazione già approvata.

        Ritorna: (successo_o_autorizzato: bool, risultato_o_proposta)
        """
        category = self.classify_action(tool_name, arguments)

        # 1. Azione di sola lettura: bypass immediato
        if category == ActionCategory.READ_ONLY and self.auto_approve_read_only:
            try:
                res = executor(tool_name, arguments)
                return True, res
            except Exception as e:
                return False, f"Execution failed: {e}"

        # 2. Azione mutante con proposta associata
        if proposal_id:
            prop = self._proposals.get(proposal_id)
            if not prop:
                return False, f"Proposta '{proposal_id}' non trovata."
            if prop.status not in (ProposalStatus.APPROVED, ProposalStatus.APPROVED_AUTOMATIC):
                return False, f"Proposta '{proposal_id}' non approvata (stato={prop.status.value})."

            try:
                res = executor(tool_name, arguments)
                prop.status = ProposalStatus.EXECUTED
                self._save_proposal(prop)
                return True, res
            except Exception as e:
                prop.status = ProposalStatus.FAILED
                self._save_proposal(prop)
                return False, f"Execution of approved proposal failed: {e}"

        # 3. Azione mutante senza approvazione: genera nuova proposta e blocca l'esecuzione
        new_prop = self.create_proposal(tool_name, arguments)
        return False, {
            "gated": True,
            "message": "Azione mutante intercettata. Richiede approvazione prima dell'esecuzione.",
            "proposal": new_prop.to_dict(),
        }
