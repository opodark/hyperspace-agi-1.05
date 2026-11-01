#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""shared/mesh_critic.py.

Modulo Contraddittore Distribuito (Red Team epistemico) per HyperSpace AGI.
Implementa la Fase E4 dei Livelli di Evidenza della Memoria (docs/memory-evidence-tiers.md):
- Ruolo 'Contraddittore': un modello su un secondo nodo della mesh esamina criticamente
  un'ipotesi teorica, un sogno notturno o una nota analitica.
- Privacy e isolamento: il secondo nodo riceve SOLO la proposizione / sommario dell'ipotesi,
  MAI il contesto raw, le memorie sorgenti o i dati privati degli utenti.
- Preservazione dei livelli (Regola Fondamentale):
  Una critica allegata NON soddisfa alcun livello superiore ('verified' o 'sourced').
  Il record resta 'plausible' (o il livello precedente) e validate_evidence()
  rifiuta qualunque tentativo di salire a 'verified' basato solo su critiche di modelli.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import re
from typing import Any, Callable, Dict, List, Optional

from shared.memory_schema import (
    EVIDENCE_TIERS,
    PLAUSIBLE,
    validate_evidence,
)

RED_TEAM_CRITIQUE_PROMPT = """Sei il Contraddittore e Red Team epistemico della rete HyperSpace AGI.
Il tuo compito è sottoporre a revisione critica e contraddittoria la seguente ipotesi, agendo come avvocato del diavolo metodologico.

Ipotesi da esaminare:
\"\"\"{hypothesis}\"\"\"{extra_context}

Compito:
1. Punti ciechi o assunzioni implicite non verificate.
2. Contro-esempi plausibili o scenari in cui l'ipotesi fallisce.
3. Rischio di bias o correlazioni spurie.

Regole ferree:
- NON validare né elogiare l'ipotesi.
- NON inventare teorie alternative non richieste.
- Mantieni la critica sintetica, densa e rigorosa (max 150-200 parole).
"""


def build_critique_prompt(
    hypothesis_summary: str,
    open_questions: Optional[List[str]] = None,
) -> str:
    """Costruisce il prompt privo di dati sensibili per il modello contraddittore.

    Invia esclusivamente l'ipotesi formulata e le eventuali domande aperte,
    garantendo che nessuna memoria sorgente o contesto privato lasci il nodo locale.
    """
    clean_summary = str(hypothesis_summary or "").strip()
    extra = ""
    if open_questions:
        valid_qs = [str(q).strip() for q in open_questions if str(q).strip()]
        if valid_qs:
            extra = "\n\nDomande aperte allegate:\n" + "\n".join(f"- {q}" for q in valid_qs[:3])

    return RED_TEAM_CRITIQUE_PROMPT.format(
        hypothesis=clean_summary[:2000],
        extra_context=extra,
    )


def parse_critique_text(raw_text: str) -> str:
    """Estrae e ripulisce il testo critico, rimuovendo tag CoT/think e blocchi inutili."""
    text = str(raw_text or "").strip()
    # Rimuove blocchi <think>...</think> tipici dei modelli reasoning
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # Rimuove eventuali recinzioni markdown esterne
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return text.strip()[:2500]


def select_critic_peer(
    proponent_node_id: Optional[str] = None,
    active_nodes: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Seleziona un nodo peer nella mesh idoneo per il ruolo di contraddittore.

    Criteri di esclusione:
    - Stesso nodo proponente (proponent_node_id).
    - Nodi non attivi o degradati.
    - Nodi con tier 'mobile' e ruolo 'failover' (riservati solo al watchdog/emergenza).
    - Nodi solo browser che non accettano connessioni HTTP in ingresso.
    """
    if not active_nodes:
        return None

    proponent = str(proponent_node_id or "").strip()

    for node in active_nodes:
        if not isinstance(node, dict):
            continue
        nid = str(node.get("node_id") or node.get("id") or "").strip()
        if not nid or (proponent and nid == proponent):
            continue
        if str(node.get("status") or "active").lower() != "active":
            continue
        tier = str(node.get("tier") or "").lower()
        if tier == "mobile" or node.get("mobile_role") == "failover":
            continue
        if tier == "browser":
            continue

        endpoint = node.get("endpoint") or node.get("public_address")
        if not endpoint:
            continue

        model = node.get("model") or node.get("default_model") or "ollama"
        return {
            "node_id": nid,
            "endpoint": str(endpoint).rstrip("/"),
            "model": str(model),
            "tier": tier or "worker",
        }

    return None


def attach_critique(entry: Dict[str, Any], critique: Dict[str, Any]) -> Dict[str, Any]:
    """Allega un blocco di critica al record di memoria o ipotesi.

    Regola di Evidence Tiering (docs/memory-evidence-tiers.md):
    - La critica viene inserita in `evidence.basis` con `kind: "critique"`.
    - Il livello `tier` NON sale MAI (resta `plausible` o il livello preesistente).
    - Verifica che l'intero blocco `evidence` sia valido secondo `validate_evidence()`.
    """
    if not isinstance(entry, dict):
        raise TypeError("entry must be a dict")
    if not isinstance(critique, dict):
        raise TypeError("critique must be a dict")

    kind = critique.get("kind")
    if kind != "critique":
        raise ValueError(f"critique.kind must be 'critique', got {kind}")
    if not str(critique.get("by") or "").strip():
        raise ValueError("critique missing 'by' attribution")
    if not str(critique.get("content") or "").strip():
        raise ValueError("critique missing 'content'")

    # Inizializza evidence se assente
    evidence = entry.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {
            "tier": PLAUSIBLE,
            "basis": [],
            "assigned_by": "mesh_critic",
        }
        entry["evidence"] = evidence

    basis = evidence.setdefault("basis", [])
    if not isinstance(basis, list):
        basis = []
        evidence["basis"] = basis

    # Timestamp ISO se non fornito
    at = critique.get("at")
    if not at:
        at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    clean_critique = {
        "kind": "critique",
        "by": str(critique["by"]).strip()[:150],
        "content": str(critique["content"]).strip()[:2500],
        "at": at,
    }
    basis.append(clean_critique)

    # Assicura che il tier sia valido e non elevato indebitamente
    current_tier = evidence.get("tier")
    if current_tier not in EVIDENCE_TIERS:
        evidence["tier"] = PLAUSIBLE

    # Validazione formale del contratto
    errors = validate_evidence(evidence)
    if errors:
        raise ValueError(f"Violazione contratto memory evidence: {errors}")

    return entry


class MeshCritic:
    """Client coordinatore per richiedere ed allegare critiche contraddittorie dalla mesh."""

    def __init__(
        self,
        node_id: str = "mac-hub",
        control_plane_url: Optional[str] = None,
        timeout_s: float = 8.0,
        peer_executor_fn: Optional[Callable[..., Any]] = None,
    ):
        self.node_id = node_id
        self.control_plane_url = control_plane_url
        self.timeout_s = timeout_s
        self.peer_executor_fn = peer_executor_fn

    def request_critique(
        self,
        hypothesis_summary: str,
        proponent_node_id: Optional[str] = None,
        proponent_model: Optional[str] = None,
        open_questions: Optional[List[str]] = None,
        active_nodes: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Richiede una critica sincrona a un nodo contraddittore (best-effort, non-blocking)."""
        prompt = build_critique_prompt(hypothesis_summary, open_questions)
        proponent = proponent_node_id or self.node_id

        # 1. Se è iniettata una funzione executor (es. nei test o runner locale)
        if self.peer_executor_fn:
            try:
                res = self.peer_executor_fn(
                    prompt=prompt,
                    proponent_node_id=proponent,
                    proponent_model=proponent_model,
                )
                if isinstance(res, dict) and res.get("content"):
                    return {
                        "kind": "critique",
                        "by": str(res.get("by") or f"{res.get('node_id', 'peer')}:{res.get('model', 'llm')}"),
                        "content": parse_critique_text(res.get("content", "")),
                        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                elif isinstance(res, str) and res.strip():
                    return {
                        "kind": "critique",
                        "by": f"peer_node:{proponent_model or 'red_team'}",
                        "content": parse_critique_text(res),
                        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
            except Exception:
                return None

        # 2. Selezione peer dalla mesh
        target_peer = select_critic_peer(proponent, active_nodes)
        if not target_peer:
            return None

        # 3. Chiamata HTTP non-bloccante verso endpoint del peer
        try:
            import urllib.error
            import urllib.request

            endpoint = target_peer["endpoint"]
            url = f"{endpoint}/v1/chat/completions"
            payload = {
                "model": target_peer.get("model", "default"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3,
            }
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    raw_content = ""
                    if choices and isinstance(choices[0], dict):
                        raw_content = choices[0].get("message", {}).get("content", "")
                    if raw_content:
                        return {
                            "kind": "critique",
                            "by": f"{target_peer['node_id']}:{target_peer.get('model', 'llm')}",
                            "content": parse_critique_text(raw_content),
                            "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        }
        except Exception:
            # Rete fallita, timeout o nodo saturo -> fail-open: non blocca il ciclo
            return None

        return None
