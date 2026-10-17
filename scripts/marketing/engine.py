#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""HyperSpace Marketing & Adoption Engine — Console CLI & Orchestratore.

Comandi disponibili:
  draft       Genera bozze di contenuto (creative / tech)
  leads       Elabora i contatti della landing page e genera risposte di onboarding
  changelog   Genera changelog e thread tecnici per sviluppatori e community
  status      Mostra lo stato e i KPI delle attività di marketing
  run-daily   Esegue l'intero ciclo giornaliero di marketing con notifica Telegram
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Assicura import corretti dal repository
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.marketing.content_factory import ContentFactory
from scripts.marketing.devrel_changelog import DevRelChangelogGenerator
from scripts.marketing.lead_nurturing import LeadNurturingManager
from scripts.marketing.telegram_gate import TelegramGate


def cmd_draft(args, factory: ContentFactory, gate: TelegramGate):
    print(f"✨ Generazione bozza [{args.track}]...")
    if args.track == "creative":
        draft = factory.generate_creative_draft(author=args.author)
    elif args.track == "tech":
        draft = factory.generate_tech_draft()
    else:
        # Genera entrambe
        d1 = factory.generate_creative_draft(author=args.author)
        d2 = factory.generate_tech_draft()
        print(f"✅ Creata bozza creativa: {d1.draft_id} - '{d1.title}'")
        print(f"✅ Creata bozza tecnica:  {d2.draft_id} - '{d2.title}'")
        if args.notify:
            res1 = gate.send_content_review(d1)
            res2 = gate.send_content_review(d2)
            print(f"📲 Notifiche inviate a Telegram (res1={res1.get('ok')}, res2={res2.get('ok')})")
        return

    print(f"\nID: {draft.draft_id}")
    print(f"Titolo: {draft.title}")
    print(f"Traccia: {draft.track.upper()} ({draft.category})")
    print(f"Canali: {', '.join(draft.channel_targets)}")
    print(f"\n--- TESTO ---\n{draft.text}\n")
    print(f"Tag: {' '.join(draft.tags)}")

    if args.notify:
        res = gate.send_content_review(draft)
        print(f"\n📲 Notifica Telegram inviata: ok={res.get('ok')} (dry_run={res.get('dry_run', False)})")


def cmd_leads(args, lead_mgr: LeadNurturingManager, gate: TelegramGate):
    print("🔍 Verifica nuovi contatti da zerozerocomputer.it...")
    actions = lead_mgr.process_pending_contacts(limit=args.limit)
    if not actions:
        print("ℹ️ Nessun nuovo contatto in attesa di elaborazione.")
        all_actions = lead_mgr.list_actions()
        print(f"Totale lead gestiti finora: {len(all_actions)}")
        return

    print(f"🎯 Trovati {len(actions)} contatti da accogliere:\n")
    for a in actions:
        print(f"• [{a.contact_id}] {a.name} ({a.email}) - Intento: {a.intent}")
        print(f"  Chiave Assegnata: {a.auth_key}")
        print(f"  Bozza Risposta:\n{a.suggested_reply}\n")
        print("-" * 50)
        if args.notify:
            res = gate.send_lead_alert(a)
            print(f"📲 Alert Telegram inviato: ok={res.get('ok')}")


def cmd_changelog(args, devrel: DevRelChangelogGenerator):
    commits = devrel.fetch_recent_commits(limit=args.limit)
    print(f"📦 Estratti {len(commits)} commit recenti da Git.\n")

    if args.format in ("all", "github"):
        print("=== [1. GITHUB RELEASE NOTES] ===")
        print(devrel.format_github_release(version=args.version, items=commits))
        print("\n" + "=" * 50 + "\n")

    if args.format in ("all", "thread"):
        print("=== [2. SOCIAL THREAD (X / LINKEDIN)] ===")
        thread = devrel.format_social_thread(items=commits)
        for i, post in enumerate(thread, 1):
            print(f"--- POST {i} ---")
            print(post)
            print()
        print("=" * 50 + "\n")

    if args.format in ("all", "reddit"):
        print("=== [3. REDDIT DEEP-DIVE (r/LocalLLaMA)] ===")
        print(devrel.format_reddit_post(items=commits))
        print("=" * 50)


def cmd_status(args, factory: ContentFactory, lead_mgr: LeadNurturingManager, gate: TelegramGate):
    drafts = factory.list_drafts()
    drafts_by_status = {}
    for d in drafts:
        drafts_by_status[d.status] = drafts_by_status.get(d.status, 0) + 1

    leads = lead_mgr.list_actions()
    leads_by_stage = {}
    for l in leads:
        leads_by_stage[l.stage] = leads_by_stage.get(l.stage, 0) + 1

    print("📊 HYPERSPACE MARKETING & ADOPTION DASHBOARD")
    print("=" * 50)
    print(f"Telegram Gate Configurato: {'SÌ ✅' if gate.is_configured else 'NO ⚠️ (modalità simulata / dry-run)'}")
    print("\n[BOZZE CONTENUTI]")
    print(f"  Totale bozze create:    {len(drafts)}")
    for status, count in drafts_by_status.items():
        print(f"  • {status:<18}: {count}")

    print("\n[LEAD & ONBOARDING WEB]")
    print(f"  Totale lead processati: {len(leads)}")
    for stage, count in leads_by_stage.items():
        print(f"  • {stage:<18}: {count}")
    print("=" * 50)


def cmd_run_daily(args, factory: ContentFactory, lead_mgr: LeadNurturingManager, devrel: DevRelChangelogGenerator, gate: TelegramGate):
    print("🚀 Avvio Ciclo Giornaliero di Marketing & Adozione HyperSpace...")
    print("\n1. Generazione Bozza Narrativa/Artistica...")
    d_creative = factory.generate_creative_draft()
    print(f"   Generata: {d_creative.draft_id} - '{d_creative.title}'")

    print("\n2. Generazione Bozza Tecnica...")
    d_tech = factory.generate_tech_draft()
    print(f"   Generata: {d_tech.draft_id} - '{d_tech.title}'")

    print("\n3. Verifica Lead Landing Page...")
    actions = lead_mgr.process_pending_contacts(limit=10)
    print(f"   Nuovi lead processati: {len(actions)}")

    if gate.is_configured or args.force_notify:
        print("\n4. Invio Bozze su Telegram per Approvazione...")
        res1 = gate.send_content_review(d_creative)
        res2 = gate.send_content_review(d_tech)
        print(f"   Notifica Bozza Creativa: ok={res1.get('ok')}")
        print(f"   Notifica Bozza Tecnica:  ok={res2.get('ok')}")
        for a in actions:
            gate.send_lead_alert(a)
    else:
        print("\nℹ️ Telegram non configurato: bozze salvate localmente in data/marketing/.")
    print("\n✅ Ciclo giornaliero completato con successo.")


def main():
    parser = argparse.ArgumentParser(description="HyperSpace Marketing & Adoption Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # draft
    p_draft = subparsers.add_parser("draft", help="Genera una bozza di contenuto")
    p_draft.add_argument("--track", choices=["creative", "tech", "both"], default="both", help="Traccia di contenuto")
    p_draft.add_argument("--author", default=None, help="Autore per traccia creativa (Aurora o Anna)")
    p_draft.add_argument("--notify", action="store_true", help="Invia su Telegram per approvazione")

    # leads
    p_leads = subparsers.add_parser("leads", help="Processa contatti dal sito web e prepara risposte")
    p_leads.add_argument("--limit", type=int, default=20, help="Numero massimo contatti da analizzare")
    p_leads.add_argument("--notify", action="store_true", help="Invia alert su Telegram")

    # changelog
    p_cl = subparsers.add_parser("changelog", help="Genera note di rilascio e thread dev da Git")
    p_cl.add_argument("--limit", type=int, default=12, help="Numero commit da analizzare")
    p_cl.add_argument("--version", default="1.05.5", help="Versione di rilascio")
    p_cl.add_argument("--format", choices=["all", "github", "thread", "reddit"], default="all")

    # status
    subparsers.add_parser("status", help="Mostra metriche e stato del motore di marketing")

    # run-daily
    p_daily = subparsers.add_parser("run-daily", help="Esegue il ciclo completo giornaliero")
    p_daily.add_argument("--force-notify", action="store_true", help="Forza invio notifiche anche se non su live bot")

    args = parser.parse_args()

    factory = ContentFactory()
    lead_mgr = LeadNurturingManager()
    devrel = DevRelChangelogGenerator()
    gate = TelegramGate(factory=factory, lead_mgr=lead_mgr)

    if args.command == "draft":
        cmd_draft(args, factory, gate)
    elif args.command == "leads":
        cmd_leads(args, lead_mgr, gate)
    elif args.command == "changelog":
        cmd_changelog(args, devrel)
    elif args.command == "status":
        cmd_status(args, factory, lead_mgr, gate)
    elif args.command == "run-daily":
        cmd_run_daily(args, factory, lead_mgr, devrel, gate)


if __name__ == "__main__":
    main()
