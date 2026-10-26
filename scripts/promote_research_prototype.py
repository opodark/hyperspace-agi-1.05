#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Runner per la promozione sicura e automatizzata dei prototipi di ricerca Sovrana HyperSpace AGI.

Ponte diretto a scripts/diagnostics/promote_research_prototype.py.
"""
import os
import sys
from pathlib import Path

DIAG_SCRIPT = Path(__file__).resolve().parent / "diagnostics" / "promote_research_prototype.py"
os.execv(sys.executable, [sys.executable, str(DIAG_SCRIPT)] + sys.argv[1:])
