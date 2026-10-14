#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Runner locale e autonomo per il microservizio Laya in HyperSpace (System 1).

Avvia il server decisionale su loopback (default porta 8097).
Rileva automaticamente l'accelerazione hardware (MPS su Apple Silicon, CUDA su NVIDIA, o CPU).
Non richiede modifiche al core di HyperSpace: dialoga via HTTP JSON con shared/laya_client.py.

Uso:
  python scripts/laya_service.py
  python scripts/laya_service.py --port 8097 --device mps
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("laya-service")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("LAYA_HOST", "127.0.0.1"),
                        help="Host bind per il servizio Laya (default: %(default)s)")
    parser.add_argument("--port", type=int, default=int(os.getenv("LAYA_PORT", "8097")),
                        help="Porta HTTP del servizio Laya (default: %(default)s)")
    parser.add_argument("--device", default=os.getenv("LAYA_DEVICE", "auto"),
                        choices=["auto", "mps", "cuda", "cpu", "xpu"],
                        help="Device di inferenza per i pesi (default: %(default)s)")
    parser.add_argument("--models", default=os.getenv("LAYA_MODELS", "multilingual,english"),
                        help="Modelli da precaricare (default: %(default)s)")
    args = parser.parse_args()

    # Verifica presenza pacchetto laya
    try:
        import laya
    except ImportError:
        logger.error(
            "Il pacchetto 'laya' non è installato in questo ambiente.\n"
            "Per installarlo con supporto server:\n"
            "  pip install 'laya[serve]'\n"
            "Su macOS con MPS (Metal):\n"
            "  pip install torch transformers laya"
        )
        return 1

    try:
        from laya.serve import create_app
        import uvicorn
    except ImportError:
        # Fallback a script server diretto se presente
        logger.error("Dipendenze server mancanti: installare con 'pip install \"laya[serve]\" uvicorn'")
        return 1

    logger.info("Inizializzazione Laya Decision Engine v%s...", getattr(laya, "__version__", "unknown"))
    logger.info("Device selezionato: %s, Modelli: %s", args.device, args.models)

    os.environ["LAYA_HOST"] = args.host
    os.environ["LAYA_PORT"] = str(args.port)
    os.environ["LAYA_MODELS"] = args.models
    if args.device != "auto":
        os.environ["LAYA_DEVICE"] = args.device

    app = create_app()
    logger.info("Avvio server HTTP su http://%s:%d...", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
