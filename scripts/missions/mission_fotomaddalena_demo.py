#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# scripts/missions/mission_fotomaddalena_demo.py
"""Generatore della Demo HyperSpace per Foto Maddalena (Stefano Maddalena, Verbania Intra dal 1947).

Ricostruisce il sito originale in stile HyperSpace:
- Cinematic Dark Studio Aesthetic (Obsidian + Golden Light Bokeh)
- Canvas Motion Design 60 FPS con simulatore interattivo di diaframma (f/1.2 - f/16) e particelle di luce
- Preventivatore interattivo dal vivo (Matrimoni, Maternity, Photo for Work, Digitalizzazione VHS)
- Vetrina gallerie coppie reali e servizi storici
- 100% Standalone (Zero-CDN, caricamento sub-10ms, offline-capable).
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import shared.laya_client as lc


def build_demo(output_path: Path) -> Path:
    print(f"🎬 Creazione Demo HyperSpace per Foto Maddalena...")

    # Consultazione rapida Laya System 1 per tonalità poetica
    os.environ["LAYA_TIMEOUT_S"] = "4.0"
    payoff = "L'Arte della Luce sul Lago Maggiore. Emozioni che sfidano il tempo."
    if lc.is_available():
        decision = lc.decide_choice(
            "Payoff per Foto Maddalena di Stefano Maddalena, Verbania Intra dal 1947",
            {
                "poetic": "L'Arte della Luce sul Lago Maggiore. Emozioni che sfidano il tempo.",
                "heritage": "Dal 1947, custodi della memoria visiva e del reportage matrimoniale d'autore.",
                "modern": "Fotografia d'Autore & Fine Art sul Lago Maggiore: Matrimoni, Ritratti e Corporate.",
            },
            "Seleziona il payoff più prestigioso ed emozionale",
        )
        if decision and decision.get("choice"):
            if decision["choice"] == "heritage":
                payoff = "Dal 1947, custodi della memoria visiva e del reportage matrimoniale d'autore."
            elif decision["choice"] == "modern":
                payoff = "Fotografia d'Autore & Fine Art sul Lago Maggiore: Matrimoni, Ritratti e Corporate."

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Foto Maddalena — Stefano Maddalena Fotografo | Verbania Intra dal 1947</title>
<meta name="description" content="Fotografo a Verbania e sul Lago Maggiore dal 1947. Reportage matrimoniali d'autore, ritratti, maternity, photo for work e laboratorio di stampa fine art.">
<style>
  :root {{
    --bg-dark: #07080c;
    --bg-card: rgba(16, 20, 30, 0.72);
    --bg-card-hover: rgba(22, 28, 44, 0.88);
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-gold: rgba(229, 169, 60, 0.35);
    --gold-primary: #e5a93c;
    --gold-light: #f5cf7a;
    --gold-glow: rgba(229, 169, 60, 0.4);
    --cyan-accent: #00e5ff;
    --text-main: #f5f7fa;
    --text-muted: #9aa4b2;
    --font-heading: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Playfair Display', Georgia, serif;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}

  body {{
    background-color: var(--bg-dark);
    color: var(--text-main);
    font-family: var(--font-sans);
    line-height: 1.6;
    overflow-x: hidden;
    position: relative;
    min-height: 100vh;
  }}

  /* Canvas di sfondo: Simulazione Ottica e Bokeh */
  #opticsCanvas {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 0;
    pointer-events: auto;
  }}

  .page-wrapper {{
    position: relative;
    z-index: 10;
    max-width: 1320px;
    margin: 0 auto;
    padding: 20px 24px 80px 24px;
    pointer-events: none;
  }}

  .interactive {{
    pointer-events: auto;
  }}

  /* Header & Navigation Bar */
  header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 30px;
    background: rgba(11, 14, 22, 0.75);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--border-subtle);
    border-radius: 18px;
    margin-bottom: 40px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
  }}

  .brand-group {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}

  .brand-monogram {{
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--gold-primary), #9a6818);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 900;
    font-size: 1.3rem;
    color: #07080c;
    box-shadow: 0 0 25px var(--gold-glow);
    font-family: var(--font-heading);
  }}

  .brand-title {{
    font-size: 1.25rem;
    font-weight: 850;
    letter-spacing: 0.5px;
    background: linear-gradient(90deg, #ffffff 40%, var(--gold-light) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}

  .brand-sub {{
    font-size: 0.76rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 1px;
  }}

  nav.nav-links {{
    display: flex;
    gap: 22px;
  }}

  nav.nav-links a {{
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.88rem;
    font-weight: 600;
    transition: color 0.2s ease;
  }}

  nav.nav-links a:hover {{
    color: var(--gold-light);
  }}

  .header-cta {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}

  .badge-open {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 30px;
    background: rgba(0, 229, 255, 0.08);
    border: 1px solid rgba(0, 229, 255, 0.3);
    font-size: 0.74rem;
    font-family: var(--font-mono);
    color: var(--cyan-accent);
  }}

  .badge-pulse {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--cyan-accent);
    box-shadow: 0 0 8px var(--cyan-accent);
    animation: pulseDot 2s infinite;
  }}

  @keyframes pulseDot {{
    0% {{ transform: scale(0.9); opacity: 0.7; }}
    50% {{ transform: scale(1.4); opacity: 1; }}
    100% {{ transform: scale(0.9); opacity: 0.7; }}
  }}

  .btn-call {{
    padding: 8px 18px;
    border-radius: 10px;
    background: rgba(229, 169, 60, 0.15);
    border: 1px solid var(--border-gold);
    color: var(--gold-light);
    font-weight: 700;
    font-size: 0.86rem;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.2s ease;
  }}

  .btn-call:hover {{
    background: var(--gold-primary);
    color: #07080c;
    box-shadow: 0 0 20px var(--gold-glow);
  }}

  /* Hero Section */
  .hero-box {{
    text-align: center;
    max-width: 980px;
    margin: 20px auto 50px auto;
    padding: 20px 10px;
  }}

  .hero-heritage-tag {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 6px 18px;
    border-radius: 9999px;
    background: rgba(229, 169, 60, 0.12);
    border: 1px solid rgba(229, 169, 60, 0.3);
    color: var(--gold-light);
    font-size: 0.8rem;
    font-family: var(--font-mono);
    margin-bottom: 24px;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }}

  .hero-title {{
    font-size: 3.8rem;
    font-weight: 900;
    line-height: 1.1;
    letter-spacing: -1.5px;
    margin-bottom: 22px;
    background: linear-gradient(180deg, #ffffff 40%, #d8dfea 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}

  .hero-title span {{
    background: linear-gradient(90deg, var(--gold-light), #ff9e00);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }}

  .hero-subhead {{
    font-size: 1.22rem;
    color: var(--text-muted);
    max-width: 820px;
    margin: 0 auto 36px auto;
    line-height: 1.6;
  }}

  /* Interactive Studio Aperture Console */
  .aperture-console {{
    background: rgba(14, 18, 28, 0.8);
    backdrop-filter: blur(25px);
    border: 1px solid var(--border-gold);
    border-radius: 20px;
    padding: 24px 32px;
    margin: 0 auto 60px auto;
    max-width: 900px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  }}

  .console-title {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
    font-family: var(--font-mono);
    color: var(--gold-light);
    margin-bottom: 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    padding-bottom: 10px;
  }}

  .console-controls-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 20px;
    align-items: center;
  }}

  .control-cell {{
    display: flex;
    flex-direction: column;
    gap: 6px;
    text-align: left;
  }}

  .control-label {{
    font-size: 0.78rem;
    font-family: var(--font-mono);
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
  }}

  .control-val {{
    color: #fff;
    font-weight: 700;
  }}

  input[type="range"] {{
    accent-color: var(--gold-primary);
    cursor: pointer;
    width: 100%;
  }}

  .btn-shutter {{
    padding: 12px 24px;
    background: linear-gradient(135deg, var(--gold-primary), #c9881d);
    color: #07080c;
    border: none;
    border-radius: 12px;
    font-weight: 800;
    font-size: 0.92rem;
    cursor: pointer;
    box-shadow: 0 4px 20px var(--gold-glow);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }}

  .btn-shutter:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(229, 169, 60, 0.6);
  }}

  .btn-shutter:active {{
    transform: scale(0.96);
  }}

  /* Pillars Grid */
  .section-label {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 1.35rem;
    font-weight: 800;
    margin-bottom: 24px;
    letter-spacing: -0.5px;
  }}

  .section-label span {{
    color: var(--gold-primary);
    font-family: var(--font-mono);
  }}

  .pillars-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
    gap: 24px;
    margin-bottom: 60px;
  }}

  .pillar-card {{
    background: var(--bg-card);
    backdrop-filter: blur(18px);
    border: 1px solid var(--border-subtle);
    border-radius: 20px;
    padding: 30px 26px;
    position: relative;
    overflow: hidden;
    transition: transform 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
  }}

  .pillar-card:hover {{
    transform: translateY(-6px);
    border-color: var(--border-gold);
    box-shadow: 0 16px 45px rgba(0, 0, 0, 0.6);
    background: var(--bg-card-hover);
  }}

  .pillar-icon-box {{
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: rgba(229, 169, 60, 0.12);
    border: 1px solid rgba(229, 169, 60, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.6rem;
    margin-bottom: 18px;
  }}

  .pillar-heading {{
    font-size: 1.22rem;
    font-weight: 800;
    margin-bottom: 10px;
    color: #fff;
  }}

  .pillar-desc {{
    font-size: 0.9rem;
    color: var(--text-muted);
    line-height: 1.6;
    margin-bottom: 16px;
  }}

  .pillar-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}

  .tag-pill {{
    font-size: 0.72rem;
    font-family: var(--font-mono);
    padding: 3px 10px;
    border-radius: 6px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #c4cdd8;
  }}

  /* Real Couples Portfolio Showcase */
  .portfolio-section {{
    margin-bottom: 60px;
  }}

  .portfolio-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
    gap: 22px;
  }}

  .portfolio-item {{
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 18px;
    padding: 22px;
    transition: all 0.25s ease;
  }}

  .portfolio-item:hover {{
    border-color: var(--border-gold);
    transform: translateY(-4px);
  }}

  .couple-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }}

  .couple-name {{
    font-size: 1.15rem;
    font-weight: 800;
    color: #fff;
  }}

  .couple-loc {{
    font-size: 0.76rem;
    font-family: var(--font-mono);
    color: var(--gold-light);
  }}

  .couple-desc {{
    font-size: 0.85rem;
    color: var(--text-muted);
    line-height: 1.5;
  }}

  /* Interactive Quick Estimator Widget */
  .estimator-card {{
    background: linear-gradient(145deg, rgba(17, 22, 35, 0.9), rgba(11, 14, 23, 0.95));
    border: 1px solid var(--border-gold);
    border-radius: 24px;
    padding: 36px;
    margin-bottom: 60px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.6);
  }}

  .estimator-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 36px;
  }}

  @media (max-width: 900px) {{
    .estimator-grid {{ grid-template-columns: 1fr; }}
    .hero-title {{ font-size: 2.6rem; }}
    nav.nav-links {{ display: none; }}
  }}

  .calc-group {{
    margin-bottom: 20px;
  }}

  .calc-label {{
    font-size: 0.85rem;
    font-family: var(--font-mono);
    color: var(--gold-light);
    margin-bottom: 10px;
    display: block;
    text-transform: uppercase;
  }}

  select, input[type="text"] {{
    width: 100%;
    padding: 12px 16px;
    background: rgba(8, 10, 16, 0.8);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    color: #fff;
    font-size: 0.95rem;
    outline: none;
    transition: border-color 0.2s ease;
  }}

  select:focus, input[type="text"]:focus {{
    border-color: var(--gold-primary);
  }}

  .addons-list {{
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}

  .addon-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.88rem;
    color: #cbd5e1;
    cursor: pointer;
  }}

  .addon-item input[type="checkbox"] {{
    width: 18px;
    height: 18px;
    accent-color: var(--gold-primary);
    cursor: pointer;
  }}

  .quote-summary-box {{
    background: rgba(7, 9, 14, 0.85);
    border: 1px solid rgba(229, 169, 60, 0.25);
    border-radius: 18px;
    padding: 28px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}

  .summary-service-name {{
    font-size: 1.3rem;
    font-weight: 850;
    color: #fff;
    margin-bottom: 6px;
  }}

  .summary-details {{
    font-size: 0.88rem;
    color: var(--text-muted);
    line-height: 1.6;
    margin-bottom: 20px;
  }}

  .summary-price-box {{
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    padding-top: 18px;
    margin-bottom: 20px;
  }}

  .summary-price-label {{
    font-size: 0.76rem;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
  }}

  .summary-price-val {{
    font-size: 1.8rem;
    font-weight: 900;
    color: var(--gold-light);
  }}

  .btn-quote {{
    padding: 14px 20px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--gold-primary), #bc7b13);
    color: #07080c;
    border: none;
    font-weight: 800;
    font-size: 0.95rem;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    box-shadow: 0 6px 25px var(--gold-glow);
    transition: all 0.2s ease;
  }}

  .btn-quote:hover {{
    transform: translateY(-2px);
    box-shadow: 0 10px 35px rgba(229, 169, 60, 0.6);
  }}

  /* History Timeline */
  .timeline-box {{
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 20px;
    padding: 34px;
    margin-bottom: 60px;
  }}

  .timeline-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 24px;
    margin-top: 20px;
  }}

  .timeline-step {{
    border-left: 2px solid var(--border-gold);
    padding-left: 18px;
  }}

  .timeline-year {{
    font-size: 1.15rem;
    font-weight: 900;
    font-family: var(--font-mono);
    color: var(--gold-light);
    margin-bottom: 4px;
  }}

  .timeline-step-desc {{
    font-size: 0.85rem;
    color: var(--text-muted);
    line-height: 1.5;
  }}

  /* Contacts & Studio Deck */
  .contact-deck {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    margin-bottom: 60px;
  }}

  .contact-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 18px;
    padding: 24px;
  }}

  .contact-card h4 {{
    font-size: 0.95rem;
    font-family: var(--font-mono);
    color: var(--gold-light);
    margin-bottom: 8px;
  }}

  .contact-card p {{
    font-size: 0.92rem;
    color: #e2e8f0;
  }}

  /* Footer */
  footer {{
    border-top: 1px solid var(--border-subtle);
    padding-top: 30px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 16px;
    color: var(--text-muted);
    font-size: 0.82rem;
  }}

  /* Flash Shutter Overlay */
  #shutterOverlay {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: #ffffff;
    opacity: 0;
    pointer-events: none;
    z-index: 9999;
    transition: opacity 0.08s ease-out;
  }}
</style>
</head>
<body>

<!-- Shutter flash animation -->
<div id="shutterOverlay"></div>

<!-- Dynamic Optics Canvas -->
<canvas id="opticsCanvas"></canvas>

<div class="page-wrapper">

  <!-- Header -->
  <header class="interactive">
    <div class="brand-group">
      <div class="brand-monogram">FM</div>
      <div>
        <div class="brand-title">FOTO MADDALENA</div>
        <div class="brand-sub">Stefano Maddalena Fotografo • Dal 1947</div>
      </div>
    </div>

    <nav class="nav-links">
      <a href="#servizi">Servizi</a>
      <a href="#coppie">Matrimoni</a>
      <a href="#preventivatore">Preventivo</a>
      <a href="#storia">Dal 1947</a>
      <a href="#contatti">Contatti</a>
    </nav>

    <div class="header-cta">
      <div class="badge-open">
        <div class="badge-pulse"></div>
        <span>STUDIO APERTO</span>
      </div>
      <a class="btn-call" href="tel:0323401044">📞 0323 401044</a>
    </div>
  </header>

  <!-- Hero Section -->
  <section class="hero-box">
    <div class="hero-heritage-tag interactive">
      ✦ OLTRE 75 ANNI DI STORIA VISIVA • VERBANIA INTRA
    </div>
    <h1 class="hero-title">
      L'ARTE DELLA LUCE SUL <span>LAGO MAGGIORE</span>
    </h1>
    <p class="hero-subhead">
      {payoff} Dalle nozze incantate alle Isole Borromee ai ritratti intimi di famiglia, fino al laboratorio artigianale di stampa Fine Art e digitalizzazione pellicole.
    </p>

    <!-- Aperture & Light Optics Interactive Console -->
    <div class="aperture-console interactive">
      <div class="console-title">
        <span>CONSOLE OTTICA STUDIO // SIMULATORE DI DIAFRAMMA & BOKEH</span>
        <span>60 FPS REAL-TIME LIGHT ENGINE</span>
      </div>

      <div class="console-controls-grid">
        <div class="control-cell">
          <div class="control-label">
            <span>Apertura Diaframma:</span>
            <span class="control-val" id="valAperture">f/1.4 (Max Bokeh)</span>
          </div>
          <input type="range" id="apertureSlider" min="1.2" max="16.0" step="0.2" value="1.4" oninput="updateAperture(this.value)">
        </div>

        <div class="control-cell">
          <div class="control-label">
            <span>Temperatura Colore:</span>
            <span class="control-val" id="valKelvin">3800K (Golden Hour)</span>
          </div>
          <input type="range" id="kelvinSlider" min="2800" max="6500" step="100" value="3800" oninput="updateKelvin(this.value)">
        </div>

        <div class="control-cell">
          <div class="control-label">
            <span>Lame Diaframma:</span>
            <span class="control-val" id="valBlades">9 Lame Circolari</span>
          </div>
          <input type="range" id="bladeSlider" min="6" max="12" step="1" value="9" oninput="updateBlades(this.value)">
        </div>

        <button class="btn-shutter" onclick="triggerShutter()">
          <span>📸 Scatta (Shutter 1/1000s)</span>
        </button>
      </div>
    </div>
  </section>

  <!-- Four Signature Pillars -->
  <div id="servizi" class="section-label interactive">
    <span>// 01</span> I Nostri Servizi Professionali
  </div>

  <div class="pillars-grid interactive">
    
    <!-- Pillar 1 -->
    <div class="pillar-card">
      <div class="pillar-icon-box">💍</div>
      <h3 class="pillar-heading">Matrimoni & Wedding Reportage</h3>
      <p class="pillar-desc">
        Uno stile fotografico spontaneo, raffinato e discreto. Raccontiamo il vostro giorno più bello cogliendo sguardi autentici e dettagli irripetibili sulle rive del Lago Maggiore, Isole Borromee, Stresa e Lago d'Orta.
      </p>
      <div class="pillar-tags">
        <span class="tag-pill">Reportage Naturale</span>
        <span class="tag-pill">Album Fine Art Cuoio</span>
        <span class="tag-pill">Drone 4K Certificato</span>
      </div>
    </div>

    <!-- Pillar 2 -->
    <div class="pillar-card">
      <div class="pillar-icon-box">👶</div>
      <h3 class="pillar-heading">Ritratti, Famiglia & Maternity</h3>
      <p class="pillar-desc">
        Dalla dolcezza dell'attesa materna (Maternity) ai primi giorni del neonato (Newborn), fino alle feste di famiglia, battesimi, prime comunioni e cresime. Sessioni rilassate in studio con luci morbide o all'aperto.
      </p>
      <div class="pillar-tags">
        <span class="tag-pill">Maternity & Nascita</span>
        <span class="tag-pill">Battesimi & Cerimonie</span>
        <span class="tag-pill">Mini-Sessioni Stagionali</span>
      </div>
    </div>

    <!-- Pillar 3 -->
    <div class="pillar-card">
      <div class="pillar-icon-box">💼</div>
      <h3 class="pillar-heading">Photo for Work & Corporate</h3>
      <p class="pillar-desc">
        Narrazione visiva e branding per hotel di charme, architettura, cantieri, ristoranti gourmet, professionisti ed e-commerce del territorio. Immagini ad alto impatto studiate per valorizzare la vostra attività.
      </p>
      <div class="pillar-tags">
        <span class="tag-pill">Architettura & Hotel</span>
        <span class="tag-pill">Food & Ristorazione</span>
        <span class="tag-pill">Ritratti Corporate LinkedIn</span>
      </div>
    </div>

    <!-- Pillar 4 -->
    <div class="pillar-card">
      <div class="pillar-icon-box">🎞️</div>
      <h3 class="pillar-heading">Laboratorio Stampa & Digitalizzazione</h3>
      <p class="pillar-desc">
        Fototessere immediate conformi per passaporto e CIE. Stampa istantanea da smartphone con calibrazione colore artigianale. Riversamento e restauro video da VHS, MiniDV e pellicole 8mm a formati digitali moderni.
      </p>
      <div class="pillar-tags">
        <span class="tag-pill">Fototessere 3 Minuti</span>
        <span class="tag-pill">Stampa Fine Art Giclée</span>
        <span class="tag-pill">Salvataggio VHS / 8mm</span>
      </div>
    </div>

  </div>

  <!-- Featured Real Couples Showcase -->
  <div id="coppie" class="section-label interactive">
    <span>// 02</span> Storie Vere & Matrimoni sul Lago
  </div>

  <div class="portfolio-grid portfolio-section interactive">
    
    <div class="portfolio-item">
      <div class="couple-header">
        <div class="couple-name">Eleonora & Jacopo</div>
        <div class="couple-loc">Villa Rusconi-Clerici, Verbania</div>
      </div>
      <p class="couple-desc">
        Un'atmosfera romantica a bordo lago con la luce dorata del tramonto riflesse sull'acqua. Dalla cerimonia intima alla festa sotto gli alberi secolari.
      </p>
    </div>

    <div class="portfolio-item">
      <div class="couple-header">
        <div class="couple-name">Astrid & Stefano</div>
        <div class="couple-loc">Isola Bella & Pescatori, Stresa</div>
      </div>
      <p class="couple-desc">
        Il fascino barocco delle Isole Borromee. Navigazione privata in motoscafo, scorci suggestivi tra i vicoli e un reportage ricco di emozioni autentiche.
      </p>
    </div>

    <div class="portfolio-item">
      <div class="couple-header">
        <div class="couple-name">Cristina & Domenico</div>
        <div class="couple-loc">Grand Hotel des Iles Borromées</div>
      </div>
      <p class="couple-desc">
        L'eleganza senza tempo della Belle Époque. Scatti spontanei tra saloni affrescati e il parco botanico affacciato sulla baia.
      </p>
    </div>

    <div class="portfolio-item">
      <div class="couple-header">
        <div class="couple-name">Federica & Davide</div>
        <div class="couple-loc">Giardini Botanici di Villa Taranto</div>
      </div>
      <p class="couple-desc">
        Un tripudio di colori e fioriture primaverili. Uno shooting pre-matrimoniale e cerimonia civile all'insegna della freschezza e spontaneità.
      </p>
    </div>

    <div class="portfolio-item">
      <div class="couple-header">
        <div class="couple-name">Elisa & Matteo '24</div>
        <div class="couple-loc">Orta San Giulio & Isola</div>
      </div>
      <p class="couple-desc">
        La poesia del Lago d'Orta. Un matrimonio poetico tra le silenziose vie medievali e il santuario della Madonna del Sasso.
      </p>
    </div>

    <div class="portfolio-item">
      <div class="couple-header">
        <div class="couple-name">Maternity & New Life</div>
        <div class="couple-loc">Studio Foto Maddalena, Intra</div>
      </div>
      <p class="couple-desc">
        Ritratti d'autore dedicati all'attesa e alla purezza dei primi giorni. Atmosfera calda, sicura e accogliente nel nostro studio storico.
      </p>
    </div>

  </div>

  <!-- Interactive Quick Estimator Widget -->
  <div id="preventivatore" class="section-label interactive">
    <span>// 03</span> Calcola Preventivo Indicativo Istantaneo
  </div>

  <div class="estimator-card interactive">
    <div class="estimator-grid">
      
      <!-- Controlli Selettore -->
      <div>
        <div class="calc-group">
          <label class="calc-label" for="serviceSelect">Seleziona Servizio Principale:</label>
          <select id="serviceSelect" onchange="recalculateQuote()">
            <option value="wedding_full">💍 Matrimonio Completo (Giornata Intera + Fine Art Album)</option>
            <option value="wedding_light">🥂 Matrimonio Intimo / Mezza Giornata</option>
            <option value="portrait_studio">👶 Ritratti Famiglia / Maternity / Studio</option>
            <option value="corporate">💼 Servizio Photo for Work / Aziende & Hotel</option>
            <option value="video_transfer">📼 Digitalizzazione Nastri VHS / MiniDV (a cassetta)</option>
            <option value="phototessera">📸 Fototessere Immediate + Stampa Digitale</option>
          </select>
        </div>

        <div class="calc-group">
          <label class="calc-label">Opzioni Aggiuntive Consigliate:</label>
          <div class="addons-list">
            <label class="addon-item">
              <input type="checkbox" id="addDrone" onchange="recalculateQuote()">
              <span>Riprese Aeree con Drone Certificato (+€250)</span>
            </label>
            <label class="addon-item">
              <input type="checkbox" id="addSecondShooter" onchange="recalculateQuote()">
              <span>Secondo Fotografo Professionista dedicato (+€350)</span>
            </label>
            <label class="addon-item">
              <input type="checkbox" id="addParentsAlbum" onchange="recalculateQuote()">
              <span>2 Mini Album Genitori coordinati (+€200)</span>
            </label>
            <label class="addon-item">
              <input type="checkbox" id="addUsbEngraved" checked onchange="recalculateQuote()">
              <span>Cofanetto in Legno con Pen Drive Incisa (Incluso)</span>
            </label>
          </div>
        </div>
      </div>

      <!-- Scheda Riepilogo -->
      <div class="quote-summary-box">
        <div>
          <div class="summary-service-name" id="quoteServiceName">Matrimonio Completo</div>
          <p class="summary-details" id="quoteServiceDetails">
            Copertura totale dai preparativi al taglio torta e balli serali. Consegna di tutti i provini digitali in alta definizione senza filigrane, galleria privata online protetta e album artigianale rilegato a mano.
          </p>
        </div>

        <div>
          <div class="summary-price-box">
            <div class="summary-price-label">Stima Indicativa Trasparente:</div>
            <div class="summary-price-val" id="quotePriceDisplay">€ 1.450</div>
          </div>

          <a class="btn-quote" id="btnWhatsappQuote" href="https://wa.me/393494757202?text=Buongiorno%20Foto%20Maddalena,%20vorrei%20informazioni%20per%20un%20servizio%20fotografico." target="_blank">
            💬 Richiedi Disponibilità su WhatsApp
          </a>
        </div>
      </div>

    </div>
  </div>

  <!-- History Timeline -->
  <div id="storia" class="section-label interactive">
    <span>// 04</span> 78 Anni di Passione Visiva
  </div>

  <div class="timeline-box interactive">
    <h3 style="font-size: 1.3rem; margin-bottom: 8px; color: #fff;">Dal banco ottico alla fotografia del futuro</h3>
    <p style="font-size: 0.92rem; color: var(--text-muted); line-height: 1.6; max-width: 850px;">
      Foto Maddalena nasce nel 1947 a Verbania Intra. Attraversando tre generazioni di tecnologia ottica e chimica, Stefano Maddalena mantiene intatto lo spirito originario: ascolto, rispetto del momento irripetibile e maestria nella gestione della luce naturale.
    </p>

    <div class="timeline-grid">
      <div class="timeline-step">
        <div class="timeline-year">1947</div>
        <div class="timeline-step-desc">
          Fondazione dello studio a Intra. Camera oscura artigianale, lastre fotografiche e i primi ritratti d'epoca che hanno documentato la rinascita del Lago Maggiore.
        </div>
      </div>

      <div class="timeline-step">
        <div class="timeline-year">1980 - 2000</div>
        <div class="timeline-step-desc">
          L'era della pellicola colore e dei grandi matrimoni nelle ville storiche. Il laboratorio si dota di minilab per la stampa di precisione.
        </div>
      </div>

      <div class="timeline-step">
        <div class="timeline-year">OGGI (2026)</div>
        <div class="timeline-step-desc">
          Tecnologia full-frame mirrorless ad altissima risoluzione, ottiche f/1.2 d'avanguardia, stampa Fine Art a pigmenti giclée e droni per prospettive mozzafiato.
        </div>
      </div>
    </div>
  </div>

  <!-- Contacts & Studio Deck -->
  <div id="contatti" class="section-label interactive">
    <span>// 05</span> Lo Studio & Recapiti
  </div>

  <div class="contact-deck interactive">
    <div class="contact-card">
      <h4>📍 DOVE SIAMO</h4>
      <p>Via Perassi 2/b<br>28921 Verbania Intra (VB)<br>Piemonte, Lago Maggiore</p>
    </div>

    <div class="contact-card">
      <h4>📞 RECAPITI DIRETTI</h4>
      <p>Telefono Studio: <strong>0323 401044</strong><br>Cellulare / WhatsApp: <strong>349 4757202</strong><br>Email: <strong>info@fotomaddalena.it</strong></p>
    </div>

    <div class="contact-card">
      <h4>🕒 ORARI DI APERTURA</h4>
      <p>Lunedì – Sabato:<br>Mattina: <strong>09:00 – 12:30</strong><br>Pomeriggio: <strong>15:30 – 19:30</strong><br>Domenica su appuntamento</p>
    </div>

    <div class="contact-card">
      <h4>🏛️ DATI SOCIETARI</h4>
      <p>Foto Maddalena di Stefano Maddalena<br>P.IVA: 02376900037<br>Fotografo Professionista Certificato</p>
    </div>
  </div>

  <!-- Footer -->
  <footer class="interactive">
    <div>
      <strong>Foto Maddalena</strong> © 1947 – 2026 • Tutti i diritti riservati • Verbania Intra (VB)
    </div>
    <div style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--gold-light);">
      HYPERSPACE SOVEREIGN DEMO • 100% STANDALONE • 60 FPS OPTICS ENGINE
    </div>
  </footer>

</div>

<!-- 60 FPS Real-time Optics & Bokeh Simulation Script -->
<script>
(function() {{
  const canvas = document.getElementById('opticsCanvas');
  const ctx = canvas.getContext('2d');

  let width = canvas.width = window.innerWidth;
  let height = canvas.height = window.innerHeight;

  window.addEventListener('resize', () => {{
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    initBokeh();
  }});

  // Parametri Ottici regolabili
  let currentAperture = 1.4;
  let currentKelvin = 3800;
  let currentBlades = 9;

  let mouse = {{ x: width / 2, y: height * 0.35, isHover: false }};
  window.addEventListener('mousemove', (e) => {{
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.isHover = true;
  }});

  // Funzione conversione temperatura colore Kelvin -> RGB
  function kelvinToRgb(k) {{
    const temp = k / 100;
    let r, g, b;

    if (temp <= 66) {{
      r = 255;
      g = 99.4708025861 * Math.log(temp) - 161.1195681661;
      b = temp <= 19 ? 0 : 138.5177312231 * Math.log(temp - 10) - 305.0447927307;
    }} else {{
      r = 329.698727446 * Math.pow(temp - 60, -0.1332047592);
      g = 288.1221695283 * Math.pow(temp - 60, -0.0755148492);
      b = 255;
    }}
    return {{
      r: Math.max(0, Math.min(255, Math.round(r))),
      g: Math.max(0, Math.min(255, Math.round(g))),
      b: Math.max(0, Math.min(255, Math.round(b)))
    }};
  }}

  // Particelle Bokeh Circolari / Poligonali
  const bokehParticles = [];
  const BOKEH_COUNT = 60;

  class BokehOrb {{
    constructor() {{
      this.reset();
    }}

    reset() {{
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.baseRadius = 25 + Math.random() * 85;
      this.vx = (Math.random() - 0.5) * 0.35;
      this.vy = -0.2 - Math.random() * 0.5;
      this.alpha = 0.04 + Math.random() * 0.12;
      this.pulseSpeed = 0.01 + Math.random() * 0.02;
      this.pulseAngle = Math.random() * Math.PI * 2;
    }}

    update() {{
      this.x += this.vx;
      this.y += this.vy;
      this.pulseAngle += this.pulseSpeed;

      if (this.y < -120) this.y = height + 100;
      if (this.x < -100) this.x = width + 80;
      if (this.x > width + 100) this.x = -80;

      // Parallasse delicato col cursore mouse
      if (mouse.isHover) {{
        const dx = (mouse.x - width / 2) * 0.015;
        const dy = (mouse.y - height / 2) * 0.015;
        this.x -= dx * (this.baseRadius / 80);
        this.y -= dy * (this.baseRadius / 80);
      }}
    }}

    draw(apertureFactor, rgb) {{
      const sizeMultiplier = Math.max(0.2, (16.0 - currentAperture) / 14.6);
      const rad = this.baseRadius * (0.8 + Math.sin(this.pulseAngle) * 0.2) * (1.5 - sizeMultiplier * 0.7);

      ctx.save();
      ctx.translate(this.x, this.y);

      ctx.beginPath();
      if (currentBlades >= 10 || currentAperture <= 1.8) {{
        // Cerchio pieno sfocato per diaframmi aperti
        ctx.arc(0, 0, rad, 0, Math.PI * 2);
      }} else {{
        // Poligono con il numero di lamelle del diaframma
        const sides = currentBlades;
        for (let i = 0; i < sides; i++) {{
          const angle = (i / sides) * Math.PI * 2;
          const px = Math.cos(angle) * rad;
          const py = Math.sin(angle) * rad;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }}
        ctx.closePath();
      }}

      // Gradiente radiale con tonalità Kelvin
      const grad = ctx.createRadialGradient(0, 0, rad * 0.1, 0, 0, rad);
      grad.addColorStop(0, `rgba(${{rgb.r}}, ${{rgb.g}}, ${{rgb.b}}, ${{this.alpha * 1.5}})`);
      grad.addColorStop(0.7, `rgba(${{rgb.r}}, ${{rgb.g}}, ${{rgb.b}}, ${{this.alpha * 0.6}})`);
      grad.addColorStop(1, `rgba(${{rgb.r}}, ${{rgb.g}}, ${{rgb.b}}, 0)`);

      ctx.fillStyle = grad;
      ctx.fill();

      // Bordo sottile caratteristico del bokeh ottico
      ctx.strokeStyle = `rgba(${{rgb.r}}, ${{rgb.g}}, ${{rgb.b}}, ${{this.alpha * 0.9}})`;
      ctx.lineWidth = 1.2;
      ctx.stroke();

      ctx.restore();
    }}
  }}

  function initBokeh() {{
    bokehParticles.length = 0;
    for (let i = 0; i < BOKEH_COUNT; i++) {{
      bokehParticles.push(new BokehOrb());
    }}
  }}
  initBokeh();

  // Callback interattivi della Console
  window.updateAperture = function(val) {{
    currentAperture = parseFloat(val);
    let note = currentAperture <= 2.0 ? 'Max Bokeh' : (currentAperture <= 5.6 ? 'Ritratti' : 'Tutto a Fuoco');
    document.getElementById('valAperture').innerText = 'f/' + val + ' (' + note + ')';
  }};

  window.updateKelvin = function(val) {{
    currentKelvin = parseInt(val, 10);
    let desc = currentKelvin < 3200 ? 'Candela Calda' : (currentKelvin < 4500 ? 'Golden Hour' : (currentKelvin < 5600 ? 'Luce Diurna' : 'Cielo Nuvoloso'));
    document.getElementById('valKelvin').innerText = val + 'K (' + desc + ')';
  }};

  window.updateBlades = function(val) {{
    currentBlades = parseInt(val, 10);
    document.getElementById('valBlades').innerText = val + ' Lame ' + (val >= 10 ? 'Circolari' : 'Poligonali');
  }};

  window.triggerShutter = function() {{
    const overlay = document.getElementById('shutterOverlay');
    overlay.style.opacity = '0.9';
    setTimeout(() => {{
      overlay.style.opacity = '0';
    }}, 90);
  }};

  // Loop animazione ottica 60 FPS
  function render() {{
    ctx.clearRect(0, 0, width, height);
    const rgb = kelvinToRgb(currentKelvin);

    // Bagliore centrale morbido
    const centerGrad = ctx.createRadialGradient(mouse.x, mouse.y, 40, mouse.x, mouse.y, width * 0.65);
    centerGrad.addColorStop(0, `rgba(${{rgb.r}}, ${{rgb.g}}, ${{rgb.b}}, 0.08)`);
    centerGrad.addColorStop(1, 'rgba(7, 8, 12, 0)');
    ctx.fillStyle = centerGrad;
    ctx.fillRect(0, 0, width, height);

    // Render particelle Bokeh
    for (let i = 0; i < bokehParticles.length; i++) {{
      bokehParticles[i].update();
      bokehParticles[i].draw(currentAperture, rgb);
    }}

    requestAnimationFrame(render);
  }}
  requestAnimationFrame(render);

  // Logica Preventivatore Istantaneo
  const servicesData = {{
    wedding_full: {{
      name: "Matrimonio Completo d'Autore",
      basePrice: 1450,
      details: "Copertura totale dai preparativi sposi fino al taglio della torta e festa serale. File digitali in alta definizione selezionati e corretti colore uno ad uno, galleria privata online per gli invitati e cofanetto con pen drive in legno."
    }},
    wedding_light: {{
      name: "Matrimonio Intimo / Mezza Giornata",
      basePrice: 850,
      details: "Cerimonia e ricevimento (fino a 5 ore di servizio continuativo). Ideale per matrimoni raccolti, cerimonie civili o fughe romantiche sulle rive del lago."
    }},
    portrait_studio: {{
      name: "Ritratti Famiglia / Maternity / Studio",
      basePrice: 180,
      details: "Sessione fotografica di circa 1h30 in studio o location all'aperto a scelta. Consegna dei migliori scatti ritoccati ad alta risoluzione, pronti per la stampa."
    }},
    corporate: {{
      name: "Servizio Photo for Work / Corporate",
      basePrice: 420,
      details: "Shooting professionale per hotel, ristoranti, architettura, cantieri e team aziendali. Include cessione diritti commerciali per sito web, social e cataloghi cartacei."
    }},
    video_transfer: {{
      name: "Digitalizzazione & Salvataggio Video Analogico",
      basePrice: 25,
      details: "Riversamento professionale da VHS, VHS-C, Video8, Hi8 o MiniDV a file video digitale MP4 (prezzo a cassetta). Conserva per sempre i tuoi ricordi di famiglia."
    }},
    phototessera: {{
      name: "Fototessere Immediate + Stampa Digitale",
      basePrice: 12,
      details: "Set di fototessere conformi ICAO per passaporto, carta d'identità e patente in 3 minuti. Possibilità di stampa immediata di foto ricordo da smartphone su carta professionale."
    }}
  }};

  window.recalculateQuote = function() {{
    const sKey = document.getElementById('serviceSelect').value;
    const item = servicesData[sKey] || servicesData.wedding_full;

    let total = item.basePrice;
    if (document.getElementById('addDrone').checked) total += 250;
    if (document.getElementById('addSecondShooter').checked) total += 350;
    if (document.getElementById('addParentsAlbum').checked) total += 200;

    document.getElementById('quoteServiceName').innerText = item.name;
    document.getElementById('quoteServiceDetails').innerText = item.details;
    document.getElementById('quotePriceDisplay').innerText = '€ ' + total.toLocaleString('it-IT');

    const msg = encodeURIComponent(`Buongiorno Foto Maddalena, ho configurato una richiesta per "${{item.name}}" con stima di €${{total}}. Vorrei verificare la disponibilità per una data.`);
    document.getElementById('btnWhatsappQuote').href = `https://wa.me/393494757202?text=${{msg}}`;
  }};

  recalculateQuote();

}})();
</script>

</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    size_kb = round(len(html.encode("utf-8")) / 1024, 2)
    print(f"✅ Demo creata con successo: {output_path} ({size_kb} KB)")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Foto Maddalena HyperSpace Demo Generator")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "research" / "fotomaddalena_hyperspace_demo.html",
        help="Percorso file HTML generato",
    )
    args = parser.parse_args()
    build_demo(args.output)


if __name__ == "__main__":
    main()
