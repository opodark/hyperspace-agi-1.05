#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
B2B Target Research & Intelligence for HyperSpace 00MESH.
Safely scouts potential business clients and partners across 3 key target verticals:
- Target 1: Studi Professionali & Consulenza (Legal, Accounting, GDPR Data Sovereignty)
- Target 3: Software House & Web Agency (Code Sandbox, Distributed Local Compute, SEO/GEO)
- Target 4: MSP & IT Support / Help Desk (Remote Monitoring, E2EE Mesh, L1/L2 Diagnostic Agents)

Uses local SearxNG instance to avoid API rate limits, bans, or external token costs.
"""

import sys
import json
import urllib.parse
import urllib.request
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("b2b_research")

SEARXNG_URL = "http://127.0.0.1:8092/search"
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reports"
OUTPUT_FILE = REPORTS_DIR / "b2b_target_companies.json"

TARGET_QUERIES = [
    {
        "target_id": "target_3_software_agencies",
        "target_name": "Target 3: Software House & Web Agency",
        "rationale": "Sviluppo software custom, web app, e-commerce ed AI integration. Necessitano di ambienti di calcolo condivisi (mesh), code sandbox isolate e automazione SEO/GEO continuativa.",
        "queries": [
            "software house milano varese sviluppo software custom",
            "agenzia web ecommerce sviluppo b2b lombardia",
            "system integrator milano cloud devops microservizi"
        ],
        "value_proposition": "Calcolo GPU locale distribuito (senza costi API OpenAI), code sandbox protetta per microservizi, e tool autonomo SEO/GEO per i siti dei loro clienti."
    },
    {
        "target_id": "target_4_msp_helpdesk",
        "target_name": "Target 4: Managed Service Providers (MSP) & Help Desk / Controllo Remoto",
        "rationale": "Fornitori di servizi IT gestiti, assistenza sistemistica, controllo remoto e supporto L1/L2 per PMI. Hanno bisogno di ridurre i ticket ripetitivi e monitorare workstation/server in modo sicuro.",
        "queries": [
            "managed service provider msp it supporto milano varese",
            "assistenza sistemistica help desk pmi lombardia",
            "monitoraggio remoto infrastrutture it aziende varese milano"
        ],
        "value_proposition": "Agenti diagnostici L1/L2 autonomi, rete mesh E2EE per controllo remoto sicuro senza VPN complesse, WebGPU per diagnostica rapida da browser."
    },
    {
        "target_id": "target_1_studi_professionali_gdpr",
        "target_name": "Target 1: Studi Professionali, Studi Legali & Commercialisti (GDPR/Compliance)",
        "rationale": "Gestione di grandi volumi di contratti, bilanci, perizie e cartelle riservate. Impossibilitati per deontologia e GDPR a inviare dati sensibili a LLM cloud esteri.",
        "queries": [
            "studio legale tributario milano digitalizzazione compliance gdpr",
            "studio commercialisti associati milano varese consulenza aziendale",
            "consulenza privacy gdpr sicurezza dati studi professionali lombardia"
        ],
        "value_proposition": "Modelli AI sovrani (LFM 2.5, Qwen) eseguiti 100% on-premise sull'hardware dello studio: zero data leak, conformità totale GDPR e AI Act europeo."
    }
]

DISALLOWED_DOMAINS = [
    "wikipedia.org", "paginegialle.it", "paginebianche.it", "trova-aperto.it",
    "facebook.com", "instagram.com", "youtube.com", "amazon.it", "ebay.it",
    "indeed.com", "linkedin.com/jobs", "subito.it"
]

def query_searxng(query: str, max_results: int = 5):
    """Executes a search query against the local SearxNG instance."""
    params = urllib.parse.urlencode({"q": query, "format": "json"})
    url = f"{SEARXNG_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "HyperSpace-B2B-Scout/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            filtered = []
            for r in results:
                url_str = r.get("url", "")
                if any(dis in url_str.lower() for dis in DISALLOWED_DOMAINS):
                    continue
                filtered.append({
                    "title": r.get("title", ""),
                    "url": url_str,
                    "snippet": r.get("content", "")
                })
                if len(filtered) >= max_results:
                    break
            return filtered
    except Exception as e:
        logger.warning(f"Errore query SearxNG per '{query}': {e}")
        return []

def run_b2b_scout():
    """Runs targeted intelligence research across all 3 sectors."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "origin_node": "Zero Zero Computer (Saronno / Lombardia)",
        "sectors": []
    }
    
    total_companies = 0
    for target in TARGET_QUERIES:
        logger.info(f"Ricerca in corso per: {target['target_name']}...")
        companies_map = {}
        for q in target["queries"]:
            items = query_searxng(q, max_results=4)
            for it in items:
                domain = urllib.parse.urlparse(it["url"]).netloc
                if domain and domain not in companies_map:
                    companies_map[domain] = {
                        "name": it["title"].split("|")[0].split("-")[0].strip(),
                        "domain": domain,
                        "url": it["url"],
                        "summary": it["snippet"][:240] + ("..." if len(it["snippet"]) > 240 else ""),
                        "fit_reason": target["value_proposition"]
                    }
        
        target_entry = {
            "target_id": target["target_id"],
            "target_name": target["target_name"],
            "rationale": target["rationale"],
            "value_proposition": target["value_proposition"],
            "companies_identified": list(companies_map.values())[:6]
        }
        total_companies += len(target_entry["companies_identified"])
        report["sectors"].append(target_entry)
        
    report["total_leads_scouted"] = total_companies
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Ricerca completata: {total_companies} aziende target identificate e salvate in {OUTPUT_FILE}")
    return report

if __name__ == "__main__":
    rep = run_b2b_scout()
    print("\n" + "="*70)
    print("HYPERSPACE B2B TARGET RESEARCH DOSSIER")
    print("="*70)
    for sector in rep["sectors"]:
        print(f"\n### {sector['target_name']}")
        print(f"Valore per loro: {sector['value_proposition']}")
        print("Aziende individuate:")
        for c in sector["companies_identified"]:
            print(f"  • {c['name']} ({c['domain']}) -> {c['url']}")
    print("\n" + "="*70)
