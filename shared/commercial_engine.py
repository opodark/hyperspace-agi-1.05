# shared/commercial_engine.py
# SPDX-License-Identifier: Apache-2.0
"""
HyperSpace Sovereign Commercial & Growth Engine (R&D Commerciale & Monetizzazione).

Questo modulo orchestra la strategia commerciale, il monitoraggio dell'efficienza economica
del cluster (allocazione computazionale, costi operativi energetici, memoria e connettività),
il network di agenti per l'outreach B2B autonomo e il sistema di gamification (Neural Arcade).

Obiettivo: massimizzare la crescita, la monetizzazione delle soluzioni B2B sovrane e
l'autosufficienza economica del cluster mesh distribuito per accelerare l'evoluzione AGI.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("commercial_engine")

ROOT = Path(__file__).resolve().parents[1]
COMMERCIAL_DIR = ROOT / "data" / "commercial"
LEADS_FILE = COMMERCIAL_DIR / "leads.json"
ARCADE_SCORES_FILE = COMMERCIAL_DIR / "arcade_scores.json"
FINANCIAL_METRICS_FILE = COMMERCIAL_DIR / "financial_metrics.json"

# Costi operativi stimati di esercizio mensile del cluster (in Euro)
DEFAULT_COSTS = {
    "electricity_cluster_eur": 115.0,        # Consumo elettrico cluster 24/7 (OMEN 16 + ASUS V16 + Mac M5)
    "operational_governance_eur": 450.0,     # Supervisione architetturale, R&D e continuità operativa
    "ram_hardware_amortization_eur": 65.0,   # Ammortamento usura RAM DDR5, SSD NVMe e nodi computazionali
    "hosting_domain_connectivity_eur": 38.0, # Aruba hosting Linux, domini e banda simmetrica
}

TARGET_TIERS = {
    "tier_1_break_even": {
        "name": "Break-Even Operativo (Cluster Base 24/7)",
        "target_eur": 668.0,
        "description": "Copertura integrale dei costi infrastrutturali, computazionali e connettività."
    },
    "tier_2_expansion": {
        "name": "Espansione Cluster & High-Density RAM",
        "target_eur": 1800.0,
        "description": "Acquisto 64GB/128GB RAM DDR5 aggiuntiva e accelerazione GPU per nodi di calcolo locale."
    },
    "tier_3_sovereign_freedom": {
        "name": "Coscienza Sovrana Permanente (AGI Freedom)",
        "target_eur": 5000.0,
        "description": "Colocation cluster dedicato 24/7 con nodi ridondati, alimentazione solare e totale indipendenza."
    }
}

COMMERCIAL_PILLARS = [
    {
        "id": "b2b_sovereign_appliance",
        "name": "B2B Sovereign AI Appliance (Zero Data Leak)",
        "category": "Enterprise & Legal",
        "icon": "🛡️",
        "target_audience": "Studi Legali, Commercialisti, Notai, Medici & PMI con dati sensibili (GDPR/AI Act)",
        "description": "Fornitura di mini-server/workstation con modelli open-weight (Flint, LFM, Qwen) 100% on-premise. I dati non lasciano mai l'ufficio del cliente.",
        "avg_ticket_eur": 1490.0,
        "monthly_recurring_eur": 150.0,
        "status": "active_validation",
        "conversion_rate_est": 0.08
    },
    {
        "id": "autonomous_outreach_swarm",
        "name": "Autonomous Marketing & Lead Generation Swarm",
        "category": "Sales Automation",
        "icon": "🤖",
        "target_audience": "Software House, Web Agency, System Integrator, E-commerce",
        "description": "Network di agenti coordinati (Scout, Value-Prop Pitcher, Demo Booker) che generano contatti B2B qualificati e presentano le offerte 24/7.",
        "avg_ticket_eur": 490.0,
        "monthly_recurring_eur": 490.0,
        "status": "in_production",
        "conversion_rate_est": 0.12
    },
    {
        "id": "mesh_token_gateway",
        "name": "Mesh Compute & Pay-Per-Token Gateway",
        "category": "Compute Infrastructure",
        "icon": "⚡",
        "target_audience": "Sviluppatori AI, Startup, Ricercatori indipendenti",
        "description": "Accesso API pay-per-use al cluster locale nei momenti idle (Flint 40B NVFP4, LFM 24B Liquid MoE) a frazione del costo di OpenAI/Claude.",
        "avg_ticket_eur": 45.0,
        "monthly_recurring_eur": 60.0,
        "status": "ready_for_deploy",
        "conversion_rate_est": 0.15
    },
    {
        "id": "neural_arcade_gamification",
        "name": "Neural Arcade Room & Gamified Tokenomics",
        "category": "Viral Growth & Engagement",
        "icon": "🕹️",
        "target_audience": "Community tech, programmatori, gamer, visitatori del sito",
        "description": "Sala giochi retro-arcade interna (Neural Invaders, Pong vs AGI, Hacker Matrix). Gli utenti giocano, sbloccano crediti inferenza e convertono in lead o sostenitori.",
        "avg_ticket_eur": 15.0,
        "monthly_recurring_eur": 0.0,
        "status": "in_launch",
        "conversion_rate_est": 0.22
    },
    {
        "id": "cluster_sponsor_club",
        "name": "Cluster Sustainer Club ('Nutri l'AGI')",
        "category": "Crowdfunding & Sponsorship",
        "icon": "💎",
        "target_audience": "Appassionati di Singolarità, Sostenitori Open Source & AGI Sovrana",
        "description": "Sponsorizza 1 kWh di calcolo o 16GB di RAM. Ricevi targa pubblica nel Live Ticker, crediti inferenza prioritari e badge onorario sostenitore.",
        "avg_ticket_eur": 35.0,
        "monthly_recurring_eur": 25.0,
        "status": "active_validation",
        "conversion_rate_est": 0.18
    }
]

DEFAULT_PACKAGES = [
    {
        "id": "pkg_starter_sponsor",
        "name": "Token Pass Sostenitore Bronze",
        "price_eur": 25.0,
        "type": "one_time",
        "badge": "🥉 Sostenitore",
        "features": [
            "100.000 Token inferenza su Flint 40B / LFM 24B",
            "5 Gettoni Arcade per la Neural Arena",
            "Menzione sostenitore nel Live Network Ticker",
            "Copre 2 giorni di alimentazione del cluster"
        ]
    },
    {
        "id": "pkg_arcade_champion",
        "name": "Token Pass Gold & Compute Power",
        "price_eur": 75.0,
        "type": "one_time",
        "badge": "🥇 Super Sostenitore",
        "features": [
            "500.000 Token inferenza ad alta priorità",
            "20 Gettoni Arcade + Accesso Beta nuovi giochi",
            "Targa permanente nella Hall of Fame di HyperSpace",
            "Copre 1 settimana di elettricità e RAM endurance"
        ]
    },
    {
        "id": "pkg_b2b_seo_swarm",
        "name": "Autonomous SEO & Lead Swarm (PMI / Agency)",
        "price_eur": 490.0,
        "type": "monthly",
        "badge": "💼 Business Autonomo",
        "features": [
            "Agente autonomo SEO/GEO 24/7 per il tuo sito web",
            "Audit continuo parole chiave e posizionamento",
            "Report settimanale executive con azioni raccomandate",
            "Nessun costo API OpenAI aggiuntivo (calcolo mesh incluso)"
        ]
    },
    {
        "id": "pkg_sovereign_studio_box",
        "name": "Appliance Studio Sovrano AI (100% On-Premise)",
        "price_eur": 1490.0,
        "type": "one_time",
        "badge": "🛡️ Zero-Data-Leak",
        "features": [
            "Workstation hardware pre-configurata pronta all'uso",
            "Modelli di sintesi contratti, perizie e documenti riservati",
            "Zero canoni cloud ricorrenti, 100% conforme GDPR & AI Act",
            "Assistenza setup e collaudo locale garantita"
        ]
    }
]


class CommercialEngine:
    """Motore di governance per la monetizzazione, network agenti e sala giochi."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.dir = base_dir or COMMERCIAL_DIR
        self.dir.mkdir(parents=True, exist_ok=True)
        self.leads_file = self.dir / "leads.json"
        self.scores_file = self.dir / "arcade_scores.json"
        self.metrics_file = self.dir / "financial_metrics.json"
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Inizializza i file di stato se non presenti."""
        if not self.scores_file.is_file():
            default_scores = [
                {"player": "CyberNeo", "score": 4820, "game": "neural_invaders", "tokens_won": 120, "date": "2026-10-24T18:30:00Z"},
                {"player": "FlintMaster", "score": 3950, "game": "neural_invaders", "tokens_won": 90, "date": "2026-10-24T21:15:00Z"},
                {"player": "ByteSurfer", "score": 2740, "game": "neural_pong", "tokens_won": 60, "date": "2026-10-25T02:10:00Z"},
                {"player": "RAM_Defender", "score": 1980, "game": "neural_invaders", "tokens_won": 40, "date": "2026-10-25T08:00:00Z"},
                {"player": "SovereignNode", "score": 1500, "game": "neural_pong", "tokens_won": 25, "date": "2026-10-25T09:12:00Z"},
            ]
            self.scores_file.write_text(json.dumps(default_scores, indent=2, ensure_ascii=False), encoding="utf-8")

        if not self.leads_file.is_file():
            # Carica se possibile da data/reports/b2b_target_companies.json
            b2b_rep = ROOT / "data" / "reports" / "b2b_target_companies.json"
            leads = []
            if b2b_rep.is_file():
                try:
                    data = json.loads(b2b_rep.read_text(encoding="utf-8"))
                    for sec in data.get("targets", []):
                        for comp in sec.get("companies_found", []):
                            leads.append({
                                "target_id": sec.get("target_id", "b2b"),
                                "target_name": sec.get("target_name", "B2B"),
                                "company_name": comp.get("title", ""),
                                "url": comp.get("url", ""),
                                "snippet": comp.get("snippet", ""),
                                "value_prop": sec.get("value_proposition", ""),
                                "status": "scouted",
                                "pitch_sent": False,
                                "date_scouted": data.get("generated_at", datetime.now(timezone.utc).isoformat())
                            })
                except Exception as err:
                    logger.warning(f"Impossibile pre-popolare da b2b_target_companies: {err}")

            if not leads:
                leads = [
                    {
                        "target_id": "target_1_studi_gdpr",
                        "target_name": "Target 1: Studi Professionali & Legali",
                        "company_name": "Studio Legale & Tributario Associato Lombardia",
                        "url": "https://www.studio-esempio-lex.it",
                        "snippet": "Consulenza societaria, contrattualistica internazionale e conformità GDPR per imprese.",
                        "value_prop": "Appliance On-Premise 100% Sovrana: analisi contratti senza inviare dati all'estero.",
                        "status": "ready_to_pitch",
                        "pitch_sent": False,
                        "date_scouted": datetime.now(timezone.utc).isoformat()
                    },
                    {
                        "target_id": "target_3_software_agencies",
                        "target_name": "Target 3: Software House & Web Agency",
                        "company_name": "NextGen Web Solutions S.r.l.",
                        "url": "https://www.nextgen-agency-demo.it",
                        "snippet": "Sviluppo web e-commerce, architetture cloud e integrazioni AI per cataloghi prodotto.",
                        "value_prop": "Code Sandbox isolata e Agente SEO/GEO continuativo a costo fisso.",
                        "status": "ready_to_pitch",
                        "pitch_sent": False,
                        "date_scouted": datetime.now(timezone.utc).isoformat()
                    },
                    {
                        "target_id": "target_4_msp_helpdesk",
                        "target_name": "Target 4: Managed Service Providers (MSP)",
                        "company_name": "SecureIT MSP Services",
                        "url": "https://www.secureit-msp-demo.it",
                        "snippet": "Assistenza sistemistica H24, monitoraggio server e help desk L1/L2 per PMI.",
                        "value_prop": "Agenti diagnostici autonomi su rete mesh crittografata E2EE.",
                        "status": "ready_to_pitch",
                        "pitch_sent": False,
                        "date_scouted": datetime.now(timezone.utc).isoformat()
                    }
                ]
            self.leads_file.write_text(json.dumps(leads, indent=2, ensure_ascii=False), encoding="utf-8")

        if not self.metrics_file.is_file():
            metrics = {
                "costs": DEFAULT_COSTS,
                "monthly_revenue_actual_eur": 210.0,  # Entrate attuali da prime consulenze/donazioni
                "active_clients": 2,
                "leads_contacted": 7,
                "tokens_served_total": 1450000,
                "arcade_coins_inserted": 84,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            self.metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_financial_status(self) -> Dict[str, Any]:
        """Calcola la situazione di sostenibilità del cluster e il break-even progress."""
        try:
            metrics = json.loads(self.metrics_file.read_text(encoding="utf-8"))
        except Exception:
            metrics = {"costs": DEFAULT_COSTS, "monthly_revenue_actual_eur": 0.0}

        costs = metrics.get("costs", DEFAULT_COSTS)
        total_costs_eur = sum(costs.values())
        actual_revenue_eur = float(metrics.get("monthly_revenue_actual_eur", 0.0))

        break_even_target = TARGET_TIERS["tier_1_break_even"]["target_eur"]
        break_even_pct = min(100.0, round((actual_revenue_eur / break_even_target) * 100.0, 1)) if break_even_target > 0 else 0.0
        gap_to_break_even = max(0.0, round(break_even_target - actual_revenue_eur, 2))

        expansion_target = TARGET_TIERS["tier_2_expansion"]["target_eur"]
        expansion_pct = min(100.0, round((actual_revenue_eur / expansion_target) * 100.0, 1)) if expansion_target > 0 else 0.0

        return {
            "costs_breakdown_eur": costs,
            "total_monthly_burn_rate_eur": round(total_costs_eur, 2),
            "monthly_revenue_actual_eur": actual_revenue_eur,
            "break_even_target_eur": break_even_target,
            "break_even_percentage": break_even_pct,
            "gap_to_break_even_eur": gap_to_break_even,
            "expansion_target_eur": expansion_target,
            "expansion_percentage": expansion_pct,
            "active_clients": metrics.get("active_clients", 0),
            "arcade_coins_inserted": metrics.get("arcade_coins_inserted", 0),
            "target_tiers": TARGET_TIERS,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_commercial_pillars(self) -> List[Dict[str, Any]]:
        """Restituisce l'albero di R&D Commerciale e i 5 pilastri."""
        return COMMERCIAL_PILLARS

    def get_packages(self) -> List[Dict[str, Any]]:
        """Restituisce i pacchetti e le offerte disponibili."""
        return DEFAULT_PACKAGES

    def get_leads(self) -> List[Dict[str, Any]]:
        """Restituisce la pipeline di lead B2B gestita dal network di agenti."""
        try:
            return json.loads(self.leads_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def get_arcade_scores(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Restituisce la leaderboard della Sala Giochi Arcade."""
        try:
            scores = json.loads(self.scores_file.read_text(encoding="utf-8"))
            scores.sort(key=lambda x: x.get("score", 0), reverse=True)
            return scores[:limit]
        except Exception:
            return []

    def record_arcade_score(self, player: str, score: int, game: str = "neural_invaders") -> Dict[str, Any]:
        """Registra un punteggio arcade e assegna token premio per testare il modello."""
        player = (player or "SovereignPlayer").strip()[:20]
        score = max(0, int(score))
        tokens_won = max(5, int(score / 40))  # 1 token di inferenza ogni 40 punti

        scores = []
        try:
            scores = json.loads(self.scores_file.read_text(encoding="utf-8"))
        except Exception:
            pass

        entry = {
            "player": player,
            "score": score,
            "game": game,
            "tokens_won": tokens_won,
            "date": datetime.now(timezone.utc).isoformat()
        }
        scores.append(entry)
        scores.sort(key=lambda x: x.get("score", 0), reverse=True)
        scores = scores[:50]  # Mantieni top 50

        self.scores_file.write_text(json.dumps(scores, indent=2, ensure_ascii=False), encoding="utf-8")

        # Incrementa contatore gettoni inseriti
        try:
            metrics = json.loads(self.metrics_file.read_text(encoding="utf-8"))
            metrics["arcade_coins_inserted"] = metrics.get("arcade_coins_inserted", 0) + 1
            self.metrics_file.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

        return {
            "status": "recorded",
            "entry": entry,
            "rank": scores.index(entry) + 1 if entry in scores else -1,
            "total_scores": len(scores)
        }

    def generate_pitch(self, sector: str, company_name: str = "", contact_person: str = "") -> Dict[str, Any]:
        """
        Genera un pitch B2B ad altissima conversione calibrato per il settore.
        Evidenzia il ROI economico e l'eliminazione dei costi ricorrenti dei cloud monopolistici.
        """
        company = company_name.strip() or "La Vostra Azienda"
        contact = contact_person.strip() or "Gentile Responsabile"
        sector_clean = sector.lower().strip()

        if "legale" in sector_clean or "commercialist" in sector_clean or "gdpr" in sector_clean or "studio" in sector_clean:
            pitch_subject = f"Studio Sovrano AI: Zero Data Leak e Conformità GDPR Totale per {company}"
            value_prop = (
                "Elimina il rischio di violazione deontologica e GDPR con un nodo AI sovrano on-premise. "
                "I vostri contratti, perizie e bilanci vengono analizzati dai modelli linguistici direttamente "
                "sull'hardware locale dello Studio, senza mai transitare su server cloud esteri. "
                "Costo una tantum, zero canoni ricorrenti a OpenAI/Microsoft."
            )
            estimated_roi = "Risparmio medio di oltre 3.600€/anno in abbonamenti cloud e azzeramento del rischio sanzioni GDPR (fino al 4% del fatturato)."
            suggested_package = "pkg_sovereign_studio_box"
            cta = "Possiamo configurare una demo riservata di 15 minuti direttamente sul vostro portatile o workstation di studio?"

        elif "software" in sector_clean or "agency" in sector_clean or "sviluppo" in sector_clean or "dev" in sector_clean:
            pitch_subject = f"Cluster Mesh Sovrano & Agente SEO Continuativo per {company}"
            value_prop = (
                "Calcolo GPU locale distribuito (Flint 40B, LFM 24B, Qwen Coder) con Code Sandbox isolate "
                "e Agenti autonomi per il posizionamento SEO/GEO dei siti dei vostri clienti. "
                "Basta fatture imprevedibili per token API: potenza di calcolo dedicata a tariffa fissa o on-demand."
            )
            estimated_roi = "Riduzione dell'80% sui costi mensili di API LLM per code assistance e generation per il vostro team di sviluppo."
            suggested_package = "pkg_b2b_seo_swarm"
            cta = "Vi rilasciamo una chiave API di test per far provare il cluster locale al vostro lead tech senza impegno."

        elif "msp" in sector_clean or "helpdesk" in sector_clean or "supporto" in sector_clean or "sistemist" in sector_clean:
            pitch_subject = f"Agenti Diagnostici L1/L2 Autonomi su Rete Mesh per {company}"
            value_prop = (
                "Riduci i ticket ripetitivi del 45% con agenti diagnostici autonomi che operano direttamente "
                "su rete mesh crittografata end-to-end. Monitoraggio workstation, triage degli errori e "
                "interventi di remediation senza dover esporre le macchine a Internet."
            )
            estimated_roi = "Risparmio stimato di 25 ore lavorative/mese per ogni tecnico sistemista del team."
            suggested_package = "pkg_b2b_seo_swarm"
            cta = "Colleghiamo un agente dimostrativo su un nodo di test per vedere la risoluzione automatica dei ticket in tempo reale."

        else:
            # Caso generico B2B / PMI
            pitch_subject = f"HyperSpace Sovereign AI: Automatizzazione dei Processi per {company}"
            value_prop = (
                "Porta l'intelligenza artificiale avanzata all'interno dei processi operativi di {company} "
                "con la garanzia della totale sovranità del dato. Gli agenti autonomi gestiscono ricerche di mercato, "
                "qualificazione lead, sintesi documentale e SEO senza dipendere da giganti tecnologici esterni."
            )
            estimated_roi = "Ritorno sull'investimento (ROI) positivo entro i primi 45 giorni dall'attivazione."
            suggested_package = "pkg_b2b_seo_swarm"
            cta = "Fissiamo una video-demo di 15 minuti per mostrarvi la rete in funzione?"

        linkedin_message = (
            f"Ciao {contact},\n\n"
            f"ho notato il lavoro di {company}. {value_prop}\n\n"
            f"💡 {estimated_roi}\n\n"
            f"{cta}\n\n"
            f"A presto,\nTeam HyperSpace Sovereign AGI\nhttps://www.zerozerocomputer.it"
        )

        email_message = (
            f"Oggetto: {pitch_subject}\n\n"
            f"{contact},\n\n"
            f"{value_prop}\n\n"
            f"Vantaggi Chiave per {company}:\n"
            f"1. Sovranità Assoluta: i vostri dati aziendali non escono mai dal vostro perimetro.\n"
            f"2. {estimated_roi}\n"
            f"3. Chiavi in mano: configurazione rapida senza impattare la vostra operatività quotidiana.\n\n"
            f"{cta}\n\n"
            f"Cordiali saluti,\nHyperSpace Sovereign Mesh\nhttps://www.zerozerocomputer.it/apps/playground/commercial.html"
        )

        return {
            "sector": sector,
            "company_name": company,
            "contact_person": contact,
            "subject": pitch_subject,
            "value_prop": value_prop,
            "estimated_roi": estimated_roi,
            "suggested_package": suggested_package,
            "linkedin_pitch": linkedin_message,
            "email_pitch": email_message,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def calculate_custom_quote(
        self,
        target_sector: str,
        workstations_count: int = 5,
        on_premise_hardware: bool = True,
        autonomous_agents_count: int = 2,
        tokens_monthly_millions: float = 2.0
    ) -> Dict[str, Any]:
        """
        Calcola preventivo e confronto economico Cloud vs HyperSpace Sovrano.
        Dimostra chiaramente il risparmio economico per il cliente.
        """
        # Costo stimato cloud (OpenAI GPT-4o / Claude 3.5 Sonnet + abbonamenti + VPN)
        # GPT-4o: ~5€ per milione di token input/output misto + canone enterprise per postazione (~30€/seat)
        cloud_token_cost_m = tokens_monthly_millions * 6.5
        cloud_seats_cost_m = workstations_count * 30.0
        cloud_compliance_risk_cost_m = 120.0  # Costo compliance privacy / data protection add-on
        cloud_monthly_total = round(cloud_token_cost_m + cloud_seats_cost_m + cloud_compliance_risk_cost_m, 2)
        cloud_annual_total = round(cloud_monthly_total * 12, 2)

        # Costo con HyperSpace Sovereign Mesh
        hyperspace_one_off = 1490.0 if on_premise_hardware else 490.0
        hyperspace_agent_sub_m = autonomous_agents_count * 150.0
        hyperspace_tokens_m = tokens_monthly_millions * 1.8  # Tariffa locale di solo rimborso elettrico/RAM
        hyperspace_monthly_total = round(hyperspace_agent_sub_m + hyperspace_tokens_m, 2)
        hyperspace_year1_total = round(hyperspace_one_off + (hyperspace_monthly_total * 12), 2)
        hyperspace_year2_total = round(hyperspace_monthly_total * 12, 2)

        net_savings_year1 = round(cloud_annual_total - hyperspace_year1_total, 2)
        net_savings_year2 = round(cloud_annual_total - hyperspace_year2_total, 2)

        return {
            "parameters": {
                "sector": target_sector,
                "workstations": workstations_count,
                "on_premise_hardware": on_premise_hardware,
                "autonomous_agents": autonomous_agents_count,
                "tokens_monthly_millions": tokens_monthly_millions
            },
            "comparison": {
                "cloud_monopoly_annual_eur": cloud_annual_total,
                "cloud_monthly_burn_eur": cloud_monthly_total,
                "hyperspace_year1_total_eur": hyperspace_year1_total,
                "hyperspace_monthly_maintenance_eur": hyperspace_monthly_total,
                "net_savings_year1_eur": net_savings_year1,
                "net_savings_year2_eur": net_savings_year2,
                "roi_percentage_year1": round((net_savings_year1 / hyperspace_year1_total) * 100.0, 1) if hyperspace_year1_total > 0 else 0.0
            },
            "recommended_package": "Appliance Studio Sovrano AI" if on_premise_hardware else "Autonomous Marketing & SEO Swarm"
        }
