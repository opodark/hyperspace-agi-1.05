#!/usr/bin/env python3
"""
LinkedIn Bulletin Post Generator & Publisher for HyperSpace 00MESH.
Formats and manages daily posts based on network bulletins, Telegram, and Moltbook updates.
Tailored specifically for B2B Targets:
- Target 1: Studi Professionali & Consulenza (Privacy GDPR, Elaborazione Documentale On-Premise)
- Target 3: Software House & Web Agency (Code Sandbox, Pipeline SEO/GEO, Calcolo Distribuito)
- Target 4: Help Desk, Controllo Remoto & MSP (Assistenza Autonoma L1/L2, Monitoraggio Mesh E2EE)
"""

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("linkedin_bulletin")

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"
OUTPUT_FILE = DATA_DIR / "linkedin_daily_posts.json"
SCHEDULE_FILE = DATA_DIR / "linkedin_schedule_plan.json"

BULLETINS = [
    {
        "id": "bulletin_target1_gdpr_privacy",
        "title": "AI Sovrana On-Premise: Elaborazione Documentale a Zero Rischio GDPR",
        "target": "Target 1: Studi Professionali, Studi Legali, Commercialisti & Consulenti",
        "summary": "Analisi di bilanci, contratti riservati e fascicoli senza inviare un singolo byte ai server cloud esteri. L'AI gira interamente sul ferro locale.",
        "text": (
            "Perché uno studio legale o commercialista dovrebbe rischiare la violazione del GDPR inviando contratti riservati, "
            "visure o bilanci aziendali alle API di cloud esteri?\n\n"
            "Con l'infrastruttura sovrana di HyperSpace 00MESH, l'intelligenza artificiale lavora on-premise direttamente sull'hardware dello studio "
            "(Mac Apple Silicon o server locali dedicati).\n\n"
            "I vantaggi operativi per i professionisti:\n"
            "• Zero data leak: nessun dato dei clienti finisce nel training set di terzi.\n"
            "• Elaborazione massiva di PDF, perizie e documenti contabili con modelli linguistici locali (LFM 2.5 e Qwen sovrani).\n"
            "• Piena conformità con le direttive del Garante Privacy e normative europee AI Act.\n\n"
            "L'AI non deve essere un compromesso tra efficienza e riservatezza dei clienti.\n\n"
            "Scopri come installare un nodo locale sovrano: https://www.zerozerocomputer.it\n\n"
            "#GDPR #Privacy #IntelligenzaArtificiale #StudiLegali #Commercialisti #OnPremise #DataSovereignty #HyperSpace #ZeroZeroComputer"
        ),
        "cta_url": "https://www.zerozerocomputer.it/join.html"
    },
    {
        "id": "bulletin_target3_software_agencies",
        "title": "Mesh di Calcolo per Software House & Web Agency: Code Sandbox e Automazione SEO/GEO",
        "target": "Target 3: Software House, Web Agency & Dev Team",
        "summary": "Condivisione di calcolo GPU tra team, sandbox isolate per esecuzione codice e ottimizzazione continua dei siti per i motori di ricerca generativi.",
        "text": (
            "I costi per le API proprietarie e la frammentazione degli ambienti di test stanno erodendo i margini dei dev team e delle agenzie digitali.\n\n"
            "HyperSpace 00MESH introduce un approccio alternativo per Software House e Web Agency:\n\n"
            "1. Mesh di Calcolo Locale: connetti i server di sviluppo (NVIDIA, AMD, Apple Silicon via Ollama o LM Studio) in un cluster peer-to-peer crittografato.\n"
            "2. Secure Code Sandbox: esecuzione isolata di script, microservizi e test automatici senza sporcare i sistemi host.\n"
            "3. Autonomous SEO & GEO Pipeline: agenti autonomi integrati con Google Search Console e verifiche GEO (Generative Engine Optimization) per posizionare i portali clienti su Perplexity, ChatGPT e Google in modo continuativo.\n\n"
            "Infrastruttura flessibile, codice trasparente e sovranità computazionale per il vostro team tecnico.\n\n"
            "Architettura e specifiche tecniche: https://www.zerozerocomputer.it\n\n"
            "#SoftwareHouse #WebAgency #DevOps #AgenticAI #SEO #GEO #OpenSource #FullStack #HyperSpace #ZeroZeroMesh"
        ),
        "cta_url": "https://www.zerozerocomputer.it"
    },
    {
        "id": "bulletin_target4_msp_helpdesk",
        "title": "Help Desk L1/L2 Autonomo e Monitoraggio Remoto Mesh per MSP e IT Support",
        "target": "Target 4: MSP (Managed Service Provider), Assistenza IT & Help Desk L1/L2",
        "summary": "Diagnostica proattiva dei nodi, telemetria cifrata end-to-end e risoluzione automatica delle anomalie ripetitive per liberare i tecnici sistemisti.",
        "text": (
            "Per i Managed Service Provider (MSP) e i reparti Help Desk, l'80% del tempo dei tecnici viene assorbito da verifiche di routine, "
            "reset, diagnostiche su workstation e controlli di disponibilità.\n\n"
            "HyperSpace 00MESH abilita una gestione distribuita ad alta efficienza per l'assistenza sistemistica:\n\n"
            "• Agenti di Diagnostica L1/L2: analizzano log di sistema, anomalie hardware e carichi termici in background, intervenendo prima che il cliente lamenti un disservizio.\n"
            "• Rete Mesh E2EE: connessione sicura punto-punto senza esporre porte aperte su Internet o VPN complesse.\n"
            "• WebGPU 1-Click: possibilità per i clienti remoti di validare diagnostiche direttamente dal browser, senza installare agent invasivi.\n\n"
            "Meno ticket ripetitivi per il vostro team IT, tempi di risposta azzerati per le aziende assistite.\n\n"
            "Approfondisci le integrazioni per Managed IT Services: https://www.zerozerocomputer.it\n\n"
            "#MSP #ITSupport #HelpDesk #SystemAdministrator #RemoteMonitoring #EdgeAI #CyberSecurity #HyperSpace #ZeroZeroComputer"
        ),
        "cta_url": "https://www.zerozerocomputer.it"
    }
]

def generate_bulletin_posts():
    """Generates the structured daily post repository and scheduling plan."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now(timezone.utc).isoformat()
    
    report = {
        "version": "1.0.0",
        "generated_at": now,
        "policy": "1 post al giorno su LinkedIn collegato a bollettini, Telegram e Moltbook",
        "total_posts": len(BULLETINS),
        "posts": BULLETINS
    }
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Salvati {len(BULLETINS)} post LinkedIn in {OUTPUT_FILE}")
    
    # Crea un piano di pubblicazione per i prossimi 3 giorni
    schedule_plan = []
    days_labels = ["Giorno 1 (Oggi)", "Giorno 2 (Domani)", "Giorno 3 (Dopodomani)"]
    for idx, post in enumerate(BULLETINS):
        schedule_plan.append({
            "slot": days_labels[idx],
            "bulletin_id": post["id"],
            "target": post["target"],
            "title": post["title"],
            "status": "ready_for_review_or_publish",
            "published": (idx == 0) # Segna il primo come pronto immediato
        })
        
    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump({"schedule": schedule_plan, "last_updated": now}, f, indent=2, ensure_ascii=False)
        
    logger.info(f"Piano di programmazione salvato in {SCHEDULE_FILE}")
    return report

def get_next_daily_post():
    """Returns the ready post for today."""
    if not OUTPUT_FILE.exists():
        generate_bulletin_posts()
        
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["posts"][0] if data.get("posts") else None

if __name__ == "__main__":
    result = generate_bulletin_posts()
    print("\n" + "="*70)
    print("HYPERSPACE 00MESH — PIANO POST LINKEDIN GIORNALIERI (TARGET B2B)")
    print("="*70)
    for i, post in enumerate(result["posts"], 1):
        print(f"\n[{i}/3] {post['target']}")
        print(f"TITOLO: {post['title']}")
        print(f"ANTEPRIMA:\n{post['text'][:280]}...\n")
