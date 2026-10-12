#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deploy automatico del Web-Node su Aruba Hosting Linux tramite FTP.

Legge le credenziali da .env (o variabili d'ambiente):
    ARUBA_FTP_HOST       default: 89.46.104.211 (IP diretto cluster FTP Aruba, bypassa proxy Cloudflare)
    ARUBA_FTP_USER       es: 19829119@aruba.it
    ARUBA_FTP_PASSWORD   obbligatoria
    ARUBA_FTP_DIR        default: www.zerozerocomputer.it

Uso:
    python scripts/deploy_web_node_aruba.py
    python scripts/deploy_web_node_aruba.py --test       # verifica solo connessione e credenziali
    python scripts/deploy_web_node_aruba.py --dry-run    # simula upload senza modificare file remoti
    python scripts/deploy_web_node_aruba.py --force      # ricarica tutti i file ignorando la dimensione
"""
from __future__ import annotations

import argparse
import ftplib
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist" / "web-node-aruba"
ARUBA_DIRECT_FTP_IP = "89.46.104.211"


def load_env_file(dotenv_path: Path) -> dict[str, str]:
    """Legge un file .env senza librerie terze."""
    env = {}
    if not dotenv_path.is_file():
        return env
    try:
        for line in dotenv_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip("'\"")
            env[k] = v
    except Exception:
        pass
    return env


def get_config() -> dict[str, str]:
    """Recupera la configurazione FTP da environment o .env."""
    local_env = load_env_file(ROOT / ".env")
    
    host = os.getenv("ARUBA_FTP_HOST") or local_env.get("ARUBA_FTP_HOST") or ARUBA_DIRECT_FTP_IP
    user = os.getenv("ARUBA_FTP_USER") or local_env.get("ARUBA_FTP_USER") or ""
    pwd = os.getenv("ARUBA_FTP_PASSWORD") or local_env.get("ARUBA_FTP_PASSWORD") or ""
    remote_dir = os.getenv("ARUBA_FTP_DIR") or local_env.get("ARUBA_FTP_DIR") or "www.zerozerocomputer.it"
    
    # Fallback su INSTAGRAM_FTP_* se ARUBA_FTP_* non è impostato
    if not user and (os.getenv("INSTAGRAM_FTP_USER") or local_env.get("INSTAGRAM_FTP_USER")):
        user = os.getenv("INSTAGRAM_FTP_USER") or local_env.get("INSTAGRAM_FTP_USER")
    if not pwd and (os.getenv("INSTAGRAM_FTP_PASSWORD") or local_env.get("INSTAGRAM_FTP_PASSWORD")):
        pwd = os.getenv("INSTAGRAM_FTP_PASSWORD") or local_env.get("INSTAGRAM_FTP_PASSWORD")

    remote_dir = remote_dir.strip().strip("/")
    if remote_dir == "zerozerocomputer.it":
        remote_dir = "www.zerozerocomputer.it"

    return {
        "host": host.strip(),
        "user": user.strip(),
        "password": pwd.strip(),
        "remote_dir": remote_dir,
    }


def resolve_ftp_host(host: str) -> str:
    """Se l'host FTP risolve su IP Cloudflare (che blocca porta 21), usa l'IP diretto FTP di Aruba."""
    try:
        ip = socket.gethostbyname(host)
        if ip.startswith("172.67.") or ip.startswith("104.21.") or ip.startswith("188.114."):
            print(f"ℹ️  {host} è dietro proxy Cloudflare ({ip}); uso IP FTP diretto Aruba ({ARUBA_DIRECT_FTP_IP}).")
            return ARUBA_DIRECT_FTP_IP
        return ip
    except Exception:
        return ARUBA_DIRECT_FTP_IP


def connect_ftp(cfg: dict[str, str]) -> ftplib.FTP:
    """Stabilisce connessione FTP passiva con credenziali redatte."""
    if not cfg["user"] or not cfg["password"]:
        raise ValueError(
            "Credenziali Aruba FTP mancanti. Inserisci in .env:\n"
            "  ARUBA_FTP_USER=<tuo_utente_aruba>\n"
            "  ARUBA_FTP_PASSWORD=<tua_password_ftp>\n"
            "  ARUBA_FTP_HOST=89.46.104.211 (opzionale)\n"
            "  ARUBA_FTP_DIR=www.zerozerocomputer.it (opzionale)"
        )
    target_host = resolve_ftp_host(cfg["host"])
    print(f"📡 Connessione FTP verso {target_host} come {cfg['user']}...")
    ftp = ftplib.FTP(target_host, timeout=35)
    ftp.set_pasv(True)
    ftp.login(cfg["user"], cfg["password"])
    print("✓ Autenticazione FTP riuscita!")
    return ftp


def ensure_remote_dir(ftp: ftplib.FTP, remote_path: str):
    """Crea ricorsivamente le sottocartelle remote se non esistono."""
    if not remote_path or remote_path == ".":
        return
    parts = [p for p in remote_path.replace("\\", "/").strip("/").split("/") if p]
    curr = ""
    for part in parts:
        curr = f"{curr}/{part}" if curr else part
        try:
            ftp.mkd(curr)
        except ftplib.error_perm:
            pass  # Esiste già


def get_remote_file_sizes(ftp: ftplib.FTP, remote_base: str) -> dict[str, int]:
    """Mappa ricorsivamente i file remoti con la relativa dimensione per upload incrementale."""
    sizes = {}
    
    def scan_dir(path: str):
        target = f"{remote_base}/{path}".strip("/") if path else remote_base
        try:
            lines = []
            ftp.dir(target, lines.append)
            for line in lines:
                parts = line.split(maxsplit=8)
                if len(parts) < 9:
                    continue
                is_dir = line.startswith("d")
                name = parts[8].strip()
                if name in {".", ".."}:
                    continue
                rel_item = f"{path}/{name}".strip("/") if path else name
                if is_dir:
                    scan_dir(rel_item)
                else:
                    try:
                        sizes[rel_item] = int(parts[4])
                    except (ValueError, IndexError):
                        sizes[rel_item] = -1
        except Exception:
            pass

    scan_dir("")
    return sizes


def deploy(cfg: dict[str, str], force: bool = False, dry_run: bool = False, skip_build: bool = False) -> int:
    """Esegue build e sincronizzazione dei file statici verso Aruba."""
    # 1. Compila il pacchetto se necessario
    if not skip_build:
        print("🔨 Compilazione web-node (scripts/build-web-node-aruba.sh)...")
        res = subprocess.run(["bash", str(ROOT / "scripts" / "build-web-node-aruba.sh")], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"❌ Errore durante la build: {res.stderr}", file=sys.stderr)
            return 1
        print("✓ Build web-node completata con successo.")

    if not DIST_DIR.is_dir():
        print(f"❌ Cartella dist non trovata: {DIST_DIR}", file=sys.stderr)
        return 1

    ftp = connect_ftp(cfg)
    try:
        remote_base = cfg["remote_dir"]
        ensure_remote_dir(ftp, remote_base)

        print(f"📂 Cartella remota di destinazione: /{remote_base or '.'}")
        print("🔍 Analisi file remoti esistenti...")
        remote_sizes = {} if force else get_remote_file_sizes(ftp, remote_base)

        # Scansiona file locali
        local_files = []
        for p in DIST_DIR.rglob("*"):
            if p.is_file():
                rel = p.relative_to(DIST_DIR).as_posix()
                local_files.append((p, rel))

        print(f"📦 Totale file locali da verificare: {len(local_files)}")
        uploaded_count = 0
        skipped_count = 0
        total_bytes = 0

        t0 = time.time()
        always_upload_exts = {".html", ".js", ".mjs", ".css", ".json", ".txt", ".xml", ".htaccess"}
        for local_path, rel_path in local_files:
            size = local_path.stat().st_size
            remote_size = remote_sizes.get(rel_path)
            is_code_or_markup = local_path.suffix.lower() in always_upload_exts or local_path.name == ".htaccess"

            if not force and not is_code_or_markup and remote_size is not None and remote_size == size:
                skipped_count += 1
                continue

            remote_file_path = f"{remote_base}/{rel_path}".strip("/")
            parent_dir = "/".join(remote_file_path.split("/")[:-1])
            
            if dry_run:
                print(f"  [DRY-RUN] Caricherei: {rel_path} ({size} byte) -> /{remote_file_path}")
                uploaded_count += 1
                total_bytes += size
                continue

            ensure_remote_dir(ftp, parent_dir)
            with open(local_path, "rb") as fh:
                ftp.storbinary(f"STOR {remote_file_path}", fh)
            
            uploaded_count += 1
            total_bytes += size
            print(f"  ↑ Caricato: {rel_path} ({round(size / 1024, 1)} KB)")

        elapsed = round(time.time() - t0, 1)
        mb = round(total_bytes / (1024 * 1024), 2)
        print("\n" + "=" * 60)
        if dry_run:
            print(f"✨ [DRY-RUN] Simulazione terminata in {elapsed}s: {uploaded_count} file da aggiornare ({mb} MB), {skipped_count} invariati.")
        else:
            print(f"🚀 DEPLOY COMPLETATO in {elapsed}s!")
            print(f"   • File aggiornati: {uploaded_count} ({mb} MB)")
            print(f"   • File già aggiornati (saltati): {skipped_count}")
            print(f"   • Sito online: https://www.zerozerocomputer.it")
            print(f"   • Chat online: https://www.zerozerocomputer.it/chat.html")
        print("=" * 60)
        return 0
    finally:
        try:
            ftp.quit()
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy automatico del Web-Node su Aruba Hosting Linux tramite FTP.")
    parser.add_argument("--test", action="store_true", help="Verifica solo la connessione e le credenziali FTP")
    parser.add_argument("--dry-run", action="store_true", help="Simula l'upload senza inviare file al server")
    parser.add_argument("--force", action="store_true", help="Ricarica tutti i file ignorando la dimensione")
    parser.add_argument("--skip-build", action="store_true", help="Non ricompilare il pacchetto dist prima dell'upload")
    args = parser.parse_args()

    cfg = get_config()

    if args.test:
        try:
            ftp = connect_ftp(cfg)
            print("Elenco directory radice:")
            ftp.dir()
            ftp.quit()
            print("\n✓ Test connessione superato con successo!")
            return 0
        except Exception as err:
            print(f"\n❌ Errore durante il test di connessione: {err}", file=sys.stderr)
            return 1

    try:
        return deploy(cfg, force=args.force, dry_run=args.dry_run, skip_build=args.skip_build)
    except Exception as err:
        print(f"\n❌ Errore durante il deploy: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
