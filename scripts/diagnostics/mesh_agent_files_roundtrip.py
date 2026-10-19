#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/diagnostics/mesh_agent_files_roundtrip.py
"""Round-trip di verifica per lo scambio dei file di protocollo agenti
(AGENTS.md, AGENT-LOG.md) sul canale P2P della mesh.

Dimostra che il "piccolo filesystem distribuito per le patch" già esistente
(shared/mesh_sync.py -> direct_files) trasporta i file di protocollo agente
senza modifiche. Nessuna rete coinvolta: pack -> apply in una cartella
temporanea -> verifica SHA-256.

È lo stesso percorso usato da `scripts/mesh_distribute.py --files ...`:
qui si verifica solo il round-trip locale (payload -> applicazione -> checksum).

Uso:
  python scripts/diagnostics/mesh_agent_files_roundtrip.py
  python scripts/diagnostics/mesh_agent_files_roundtrip.py --files AGENTS.md,AGENT-LOG.md --repo .
"""

import argparse
import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.mesh_sync import create_git_patch_payload, apply_mesh_update  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", default="AGENTS.md,AGENT-LOG.md")
    ap.add_argument("--repo", default=str(ROOT), help="radice del repository sorgente")
    args = ap.parse_args(argv)

    files = [f.strip() for f in args.files.split(",") if f.strip()]
    repo = Path(args.repo)

    payload = create_git_patch_payload(repo_dir=str(repo), include_files=files)
    print(f"type={payload['type']}  direct_files={sorted(payload['direct_files'])}")

    total = 0
    for f in files:
        info = payload["direct_files"].get(f)
        if not info:
            print(f"  MISSING: {f} non trovato in {repo}")
            return 1
        total += info["size"]
        print(f"  {f}: {info['size']} bytes  sha256={info['sha256'][:16]}...")
    print(f"  payload ~{total} bytes (poi gzip + base64 + E2EE in transito)")

    with tempfile.TemporaryDirectory() as d:
        res = apply_mesh_update(payload, repo_dir=d)
        print(f"apply: success={res['success']} errors={res['errors']}")
        ok = res["success"] and not res["errors"]
        for f in files:
            orig = (repo / f).read_bytes()
            got = (Path(d) / f).read_bytes()
            same = hashlib.sha256(orig).hexdigest() == hashlib.sha256(got).hexdigest()
            ok = ok and same
            print(f"  {f}: {'MATCH' if same else 'MISMATCH'} ({len(got)} bytes)")
        print("ROUNDTRIP:", "OK" if ok else "FAILED")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
