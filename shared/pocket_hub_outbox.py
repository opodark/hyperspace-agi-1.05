# SPDX-License-Identifier: Apache-2.0
"""Registro a sola aggiunta del Pocket Hub: ciò che accade mentre il CP è giù.

Il telefono tiene qui eventi e conversazioni del failover e li riconsegna al
control-plane principale (→ Hermes, via `POST /memory/push`) quando torna. Due
file in una directory: `outbox.ndjson` (le voci, una per riga) e `acked.ndjson`
(gli id che il CP ha confermato). Una voce è "in attesa" finché il suo id non
compare fra i confermati: se il telefono si riavvia a metà della spedizione, si
riparte da dove si era arrivati e non si perde niente. Se la conferma arriva ma
il telefono muore prima di scriverla, la voce viene rispedita: per questo ogni
voce porta un `id` stabile che chi riceve può usare per deduplicare.

Solo libreria standard. Nessun segreto passa di qui: il chiamante decide cosa
mettere in `data`.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List

DEFAULT_MAX_PENDING = 5000


class Outbox:
    def __init__(self, directory: str | os.PathLike, max_pending: int = DEFAULT_MAX_PENDING) -> None:
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._entries = self.dir / "outbox.ndjson"
        self._acked = self.dir / "acked.ndjson"
        self.max_pending = max(10, int(max_pending))
        self._lock = threading.RLock()

    # ── scrittura ────────────────────────────────────────────────────────
    def append(self, kind: str, data: Dict[str, Any]) -> str:
        entry = {"id": uuid.uuid4().hex, "ts": time.time(), "kind": kind, "data": data}
        with self._lock:
            self._write_line(self._entries, entry)
            self._enforce_cap()
        return entry["id"]

    @staticmethod
    def _write_line(path: Path, obj: Dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    # ── lettura ──────────────────────────────────────────────────────────
    def _read(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        out = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue  # riga troncata da un crash: si salta, non si blocca la coda
        return out

    def _acked_ids(self) -> set:
        return {e.get("id") for e in self._read(self._acked)}

    def pending(self) -> List[Dict[str, Any]]:
        with self._lock:
            acked = self._acked_ids()
            return [e for e in self._read(self._entries) if e.get("id") not in acked]

    def stats(self) -> Dict[str, Any]:
        pend = self.pending()
        return {"pending": len(pend), "oldest_ts": pend[0]["ts"] if pend else None}

    # ── riconsegna ───────────────────────────────────────────────────────
    def flush(self, send: Callable[[Dict[str, Any]], bool], batch: int = 100) -> Dict[str, int]:
        """Spedisce in ordine le voci in attesa. Si ferma alla prima non confermata:
        l'ordine cronologico conta e un CP che non risponde non va martellato."""
        sent = 0
        with self._lock:
            pend = self.pending()[: max(1, batch)]
        for entry in pend:
            try:
                ok = bool(send(entry))
            except Exception:
                ok = False
            if not ok:
                break
            with self._lock:
                self._write_line(self._acked, {"id": entry["id"], "ts": time.time()})
            sent += 1
        with self._lock:
            remaining = len(self.pending())
            if remaining == 0:
                self._compact()
        return {"sent": sent, "remaining": remaining}

    def _compact(self) -> None:
        for p in (self._entries, self._acked):
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    def _enforce_cap(self) -> None:
        pend = self.pending()
        markers = [e for e in pend if e.get("kind") == "outbox_overflow"]
        real = [e for e in pend if e.get("kind") != "outbox_overflow"]
        if len(real) <= self.max_pending:
            return
        # Telefono offline a lungo: si butta il più vecchio, ma lo si dice, con un
        # solo marker che somma tutto quello che è stato scartato finora.
        drop = len(real) - self.max_pending
        carried = sum(int(m.get("data", {}).get("dropped", 0)) for m in markers)
        marker = {
            "id": uuid.uuid4().hex, "ts": time.time(), "kind": "outbox_overflow",
            "data": {"dropped": carried + drop, "max_pending": self.max_pending},
        }
        tmp = self._entries.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            for e in [marker, *real[drop:]]:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self._entries)
        try:
            self._acked.unlink()
        except FileNotFoundError:
            pass
