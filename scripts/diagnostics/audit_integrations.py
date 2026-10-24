#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Audit e Health Check delle Integrazioni HyperSpace.
Esegue l'ispezione di tutti i repository e moduli integrati dichiarati
in integrations/integrations.manifest.yaml, ne verifica l'allineamento con
l'upstream remoto e l'integrità tramite i test non-regressivi associati.

Uso:
  .venv/bin/python scripts/diagnostics/audit_integrations.py
  .venv/bin/python scripts/diagnostics/audit_integrations.py --verify-all
  .venv/bin/python scripts/diagnostics/audit_integrations.py --output data/reports/integrations_audit.json
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.integrations_manager import IntegrationsManager


def run_audit(verify_tests: bool = False, output_path: Path | None = None) -> dict:
    manager = IntegrationsManager()
    print("🔍 Avvio audit delle integrazioni e verifica upstream...")
    statuses = manager.check_upstream(timeout_sec=6)

    test_results = {}
    if verify_tests:
        print("\n🧪 Esecuzione test di non-regressione per i moduli registrati...")
        for entry in statuses:
            mod_id = entry["id"]
            if entry.get("test_command"):
                print(f"  → Test {mod_id}...", end=" ", flush=True)
                res = manager.run_verify(mod_id)
                test_results[mod_id] = res
                if res.get("success"):
                    print("✅ PASS")
                elif res.get("skipped"):
                    print(f"⚠️ SKIP ({res.get('message')})")
                else:
                    print(f"❌ FAIL ({res.get('error', 'exit code ' + str(res.get('returncode')))})")

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_integrations": len(statuses),
        "integrations": statuses,
        "test_results": test_results,
    }

    print("\n" + manager.format_table(statuses, with_upstream=True))

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Report salvato in: {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Audit Integrazioni HyperSpace")
    parser.add_argument("--verify-all", action="store_true", help="Esegue anche i test non-regressivi di ciascun modulo")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data" / "reports" / "integrations_audit.json",
        help="File di output per il report JSON",
    )
    args = parser.parse_args()
    run_audit(verify_tests=args.verify_all, output_path=args.output)


if __name__ == "__main__":
    main()
