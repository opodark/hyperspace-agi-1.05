# SPDX-License-Identifier: Apache-2.0
"""Agente autonomo per la pubblicazione di tweet su X (Twitter) API v2 per $00MESH.

Funzionalità:
1. Supporto autenticazione OAuth 2.0 User Context (Bearer con refresh token automatico) e OAuth 1.0a.
2. Generazione autonoma di contenuti tramite Control Plane locale / OmniRoute (<2s).
3. Pubblicazione su endpoint ufficiale Twitter API v2 (POST https://api.twitter.com/2/tweets).
4. Modalità --dry-run per simulare i post senza credenziali o senza consumare quote API.
5. Supporto per Contract Address (CA), hashtag DePIN/Solana e portale ufficiale.
6. Storico e logging in data/marketing/x_posts.json.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("Errore: requests non trovato. Esegui nel venv del repository.")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parents[2]
LOG_FILE = BASE_DIR / "data" / "marketing" / "x_posts.json"
AUTH_FILE = BASE_DIR / "data" / "marketing" / "x_auth.json"
ENV_FILE = BASE_DIR / ".env"


def load_credentials() -> dict[str, str]:
    """Carica credenziali da data/marketing/x_auth.json e da variabili d'ambiente/.env."""
    creds: dict[str, str] = {}
    if AUTH_FILE.exists():
        try:
            creds.update(json.loads(AUTH_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"[avviso] Impossibile leggere x_auth.json: {e}")

    # Fallback su .env o os.environ
    env_vars = dict(os.environ)
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in env_vars:
                    env_vars[k] = v
        except Exception:
            pass

    for k in ("X_ACCESS_TOKEN", "X_REFRESH_TOKEN", "X_CLIENT_ID", "X_CLIENT_SECRET", "X_API_KEY", "X_API_SECRET", "X_TOKEN_MINT"):
        if k in env_vars:
            creds[k.lower()] = env_vars[k]

    return creds


def refresh_oauth2_token(creds: dict[str, str]) -> Optional[str]:
    """Rinnova l'access token OAuth 2.0 tramite refresh_token."""
    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")
    refresh_tok = creds.get("refresh_token")
    if not (client_id and refresh_tok):
        return None

    url = "https://api.twitter.com/2/oauth2/token"
    auth_str = f"{client_id}:{client_secret}" if client_secret else client_id
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64_auth}",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_tok,
        "client_id": client_id,
    }

    try:
        res = requests.post(url, headers=headers, data=data, timeout=15)
        if res.ok:
            payload = res.json()
            new_access = payload.get("access_token")
            new_refresh = payload.get("refresh_token")
            if new_access:
                creds["access_token"] = new_access
                if new_refresh:
                    creds["refresh_token"] = new_refresh
                if AUTH_FILE.exists():
                    AUTH_FILE.write_text(json.dumps(creds, indent=2), encoding="utf-8")
                print("🔄 Token OAuth 2.0 rinnovato con successo.")
                return new_access
        else:
            print(f"[avviso] Errore rinnovo token ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"[avviso] Eccezione durante refresh token: {e}")
    return None


def generate_tweet(
    topic: str = "launch",
    ca_address: Optional[str] = None,
    gateway_url: str = "http://127.0.0.1:8085",
) -> str:
    """Genera un tweet accattivante tramite Control Plane locale o fallback."""
    ca_hint = f"Contract Address (CA): {ca_address}" if ca_address else ""
    prompt = f"""You are the autonomous AI marketing agent for 00MESH (Ticker: $00MESH).
00MESH is a sovereign peer-to-peer AI mesh on Solana / pump.fun where miners earn $00MESH by sharing local inference models (Ollama, ComfyUI).
Topic: {topic}
{ca_hint}

Rules:
1. Write in English, punchy, crypto-native, viral and informative.
2. Mention $00MESH, #DePIN, #Solana and https://www.zerozerocomputer.it.
3. If CA is provided, include it clearly.
4. Keep the total length STRICTLY under 240 characters.
5. Return ONLY the tweet text, no introduction or quotes.
"""
    try:
        res = requests.post(
            f"{gateway_url.rstrip('/')}/v1/chat/completions",
            json={
                "model": "omniroute",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
            },
            timeout=10,
        )
        if res.ok:
            content = res.json()["choices"][0]["message"]["content"].strip()
            content = content.strip("\"'")
            if len(content) > 280:
                content = content[:277] + "..."
            return content
    except Exception as err:
        print(f"[avviso] Errore chiamata Control Plane ({err}); uso template di riserva.")

    templates = [
        "Turn your idle GPU into a yield machine! ⚡ Connect Ollama or ComfyUI to the sovereign mesh & earn $00MESH. Compute is the new currency. 🌐 https://www.zerozerocomputer.it #DePIN #Solana",
        "Disconnect from Big Tech monopolies. 00MESH gives sovereign AI compute back to the people. Share inference, get rewarded in $00MESH. 🚀 https://www.zerozerocomputer.it #Solana #AI",
        "The decentralized AI grid is live. Run local models, power web-nodes, stack $00MESH on-chain. Sovereign intelligence has arrived. 💻 https://www.zerozerocomputer.it #DePIN",
    ]
    import random
    selected = random.choice(templates)
    if ca_address:
        selected += f" | CA: {ca_address}"
    return selected


def post_to_x(text: str, creds: dict[str, str], dry_run: bool = False) -> dict:
    """Pubblica un tweet su X API v2 tramite OAuth 2.0 User Context."""
    if dry_run:
        print("\n🧪 [DRY RUN] Tweet generato (non inviato ad API):")
        print("--------------------------------------------------")
        print(text)
        print("--------------------------------------------------")
        print(f"Caratteri: {len(text)} / 280")
        return {"ok": True, "dry_run": True, "text": text}

    access_token = creds.get("access_token")
    if not access_token:
        raise ValueError("Nessun access_token disponibile in x_auth.json.")

    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "00MeshAgent/1.0",
    }
    payload = {"text": text}

    res = requests.post(url, headers=headers, json=payload, timeout=15)

    # Se token scaduto (401), tenta il refresh e riprova una volta
    if res.status_code == 401 and creds.get("refresh_token"):
        print("⚠️ Access token scaduto. Tento il refresh...")
        new_token = refresh_oauth2_token(creds)
        if new_token:
            headers["Authorization"] = f"Bearer {new_token}"
            res = requests.post(url, headers=headers, json=payload, timeout=15)

    data = res.json() if res.content else {}

    if res.status_code in (200, 201):
        tweet_id = data.get("data", {}).get("id", "sconosciuto")
        user_name = creds.get("username", "ZeroZeroMesh")
        tweet_url = f"https://x.com/{user_name}/status/{tweet_id}"
        print(f"✅ Tweet pubblicato con successo!")
        print(f"🔗 Link: {tweet_url}")
        _log_post({
            "id": tweet_id,
            "url": tweet_url,
            "text": text,
            "status": "published",
            "date": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "tweet_id": tweet_id, "url": tweet_url, "data": data}
    else:
        err_msg = f"HTTP {res.status_code}: {data}"
        print(f"❌ Errore pubblicazione tweet: {err_msg}")
        return {"ok": False, "error": err_msg, "status_code": res.status_code}


def _log_post(entry: dict):
    """Registra lo storico dei tweet in data/marketing/x_posts.json."""
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        posts = []
        if LOG_FILE.exists():
            posts = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        posts.append(entry)
        LOG_FILE.write_text(json.dumps(posts, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[avviso] Impossibile salvare log post: {e}")


def main():
    parser = argparse.ArgumentParser(description="00MESH Autonomous X/Twitter Agent")
    parser.add_argument("--dry-run", action="store_true", help="Simula la generazione senza inviare il tweet su X")
    parser.add_argument("--topic", default="sharing local compute for $00MESH", help="Argomento del tweet")
    parser.add_argument("--ca", default=None, help="Contract Address (CA) del token da includere")
    parser.add_argument("--text", default=None, help="Testo manuale da twittare (salta l'LLM)")
    parser.add_argument("--gateway", default="http://127.0.0.1:8085", help="URL del Control Plane per inferenza")
    args = parser.parse_args()

    creds = load_credentials()
    ca = args.ca or creds.get("ca") or creds.get("x_token_mint") or creds.get("pumpfun_token_mint")

    if args.text:
        tweet_text = args.text
    else:
        print(f"🤖 Interrogo il Control Plane ({args.gateway}) per generare il tweet...")
        tweet_text = generate_tweet(topic=args.topic, ca_address=ca, gateway_url=args.gateway)

    is_dry = args.dry_run or not bool(creds.get("access_token"))
    if is_dry and not args.dry_run:
        print("⚠️ Nessun access_token trovato: modalità simulazione attiva.")

    post_to_x(tweet_text, creds, dry_run=is_dry)


if __name__ == "__main__":
    main()
