#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Modulo di invio email per HyperSpace (SMTP).

Supporta STARTTLS (porta 587), SSL (porta 465) o SMTP standard.
Invia email multipart (Plain Text + HTML con grafica coerente alla landing page)
per la consegna sicura delle chiavi di accesso mesh agli utenti.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def is_smtp_configured() -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    return bool(host and user)


def get_smtp_config() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587").strip() or 587),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", "").strip(),
        "from_addr": os.getenv("SMTP_FROM", "").strip() or os.getenv("SMTP_USER", "").strip(),
        "use_ssl": os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes"},
    }


def render_key_email(name: str, auth_key: str, landing_url: str = "https://oszerozero.onrender.com/") -> tuple[str, str]:
    """Restituisce (testo_semplice, html) formattati con le credenziali e le istruzioni."""
    clean_name = (name or "utente").strip()
    clean_key = auth_key.strip()

    text = f"""Ciao {clean_name},

Ecco la tua chiave di accesso personale per i modelli remoti della rete neurale HyperSpace Mesh:

--------------------------------------------------
CHIAVE MESH: {clean_key}
--------------------------------------------------

Come iniziare:
1. Accedi alla Web UI pubblica: {landing_url}
2. Clicca in alto a destra su "🔑 Chiave Mesh"
3. Incolla la tua chiave e premi "Verifica e Accedi"

La chat passerà automaticamente su "Mesh Remota", sbloccando tutti i modelli ad alte prestazioni distribuiti sulla rete (inclusi modelli abliterated e cluster GPU dedicati).

Se hai domande o feedback, rispondi pure a questa email.

A presto,
Il Team di HyperSpace AGI
https://zerozerocomputer.it/
"""

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>La tua Chiave HyperSpace Mesh</title>
</head>
<body style="margin: 0; padding: 0; background-color: #060810; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #060810; padding: 40px 15px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 580px; background-color: #0c1022; border: 1px solid rgba(0, 243, 255, 0.25); border-radius: 14px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.6);">
          
          <!-- Header Banner -->
          <tr>
            <td style="padding: 30px 30px 20px 30px; background: linear-gradient(135deg, rgba(0, 243, 255, 0.1) 0%, rgba(157, 0, 255, 0.1) 100%); border-bottom: 1px solid rgba(255,255,255,0.06);">
              <div style="font-size: 11px; font-weight: 700; letter-spacing: 2px; color: #00f3ff; text-transform: uppercase; margin-bottom: 6px;">HYPERSPACE AGI // NETWORK</div>
              <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">Chiave di Accesso Mesh</h1>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding: 30px;">
              <p style="margin: 0 0 18px 0; font-size: 15px; line-height: 1.6; color: #cbd5e1;">
                Ciao <strong style="color: #ffffff;">{clean_name}</strong>,<br>
                la tua richiesta di accesso ai modelli remoti della rete neurale distribuita <strong>HyperSpace</strong> è stata approvata.
              </p>

              <!-- Key Badge Box -->
              <div style="background-color: #070a16; border: 1px dashed #00f3ff; border-radius: 10px; padding: 18px 20px; margin: 24px 0; text-align: center;">
                <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #94a3b8; margin-bottom: 8px;">La tua Chiave Personale</div>
                <div style="font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 20px; font-weight: 700; color: #00f3ff; letter-spacing: 1px; word-break: break-all;">
                  {clean_key}
                </div>
              </div>

              <h2 style="font-size: 16px; font-weight: 700; color: #ffffff; margin: 24px 0 12px 0;">Come attivare l'accesso:</h2>
              <ol style="margin: 0 0 24px 0; padding-left: 20px; font-size: 14px; line-height: 1.7; color: #94a3b8;">
                <li>Apri l'interfaccia Web: <a href="{landing_url}" style="color: #00f3ff; text-decoration: none;">{landing_url}</a></li>
                <li>Clicca in alto a destra sul pulsante <strong>🔑 Chiave Mesh</strong></li>
                <li>Incolla la tua chiave e clicca <strong>Verifica e Accedi</strong></li>
              </ol>

              <!-- Action Button -->
              <div style="text-align: center; margin: 32px 0 16px 0;">
                <a href="{landing_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #00f3ff 0%, #00a8ff 100%); color: #060810; font-weight: 700; font-size: 14px; text-decoration: none; padding: 12px 28px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0, 243, 255, 0.35);">
                  Accedi a HyperSpace Mesh &rarr;
                </a>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 20px 30px; background-color: #080b18; border-top: 1px solid rgba(255,255,255,0.04); font-size: 12px; color: #64748b; text-align: center; line-height: 1.5;">
              HyperSpace AGI 1.04 &middot; Sistema Neurale Cooperativo &middot; <a href="https://zerozerocomputer.it/" style="color: #64748b; text-decoration: underline;">zerozerocomputer.it</a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
    return text, html


def send_key_email(to_email: str, name: str, auth_key: str, landing_url: str = "https://oszerozero.onrender.com/") -> tuple[bool, str]:
    """Invia l'email con la chiave all'utente.
    
    Ritorna (success: bool, message: str).
    """
    cfg = get_smtp_config()
    if not cfg["host"] or not cfg["user"]:
        return False, "SMTP non configurato (imposta SMTP_HOST e SMTP_USER nel file .env)"

    clean_to = str(to_email or "").strip()
    if not clean_to:
        return False, "Indirizzo email di destinazione mancante"

    text_body, html_body = render_key_email(name=name, auth_key=auth_key, landing_url=landing_url)

    msg = EmailMessage()
    msg["Subject"] = f"🔑 La tua Chiave di Accesso a HyperSpace Mesh ({auth_key})"
    msg["From"] = cfg["from_addr"]
    msg["To"] = clean_to
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        if cfg["use_ssl"] or cfg["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=12.0) as server:
                if cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=12.0) as server:
                server.ehlo()
                try:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                except Exception:
                    # Server non supporta STARTTLS, continua in chiaro se consentito
                    pass
                if cfg["password"]:
                    server.login(cfg["user"], cfg["password"])
                server.send_message(msg)
        return True, f"Email inviata con successo a {clean_to}"
    except Exception as exc:
        return False, f"Errore SMTP durante l'invio a {clean_to}: {exc}"
