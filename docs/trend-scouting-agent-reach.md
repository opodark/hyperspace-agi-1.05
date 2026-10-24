# Trend Scouting & Social Inspiration via Agent-Reach

Questo modulo integra le capacità di ricerca open-source a costo API zero fornite da **Agent-Reach** (`Panniantong/Agent-Reach`) nel sistema di generazione onirica e creativa di HyperSpace (ciclo sogni e poesie di Anna e Aurora).

---

## Architettura e Flusso

```
                  ┌──────────────────────────────────────────────┐
                  │  Agent-Reach CLI (Zero-Cost Scrapers/Jina)   │
                  │   - Web (Jina Reader)                        │
                  │   - YouTube (yt-dlp metadata/transcripts)    │
                  │   - Reddit (Public web searches)             │
                  │   - GitHub (gh / code & repo search)         │
                  └───────────────────────┬──────────────────────┘
                                          │
                        scripts/diagnostics/trend_scout_reach.py
                                          │
                                          ▼
                      data/control-plane/trend_inspirations.json
                                          │
                                          ▼
                   shared/social_dreams.py :: combined_dream_material()
                                          │
                   ┌──────────────────────┴──────────────────────┐
                   │                                             │
                   ▼                                             ▼
          Eco Sociale Anonimo                       Tendenze del Mondo Reale
    (DM Instagram / Telegram)                 (Coscienza, Arte, Spazio, AI)
                   │                                             │
                   └──────────────────────┬──────────────────────┘
                                          │
                                          ▼
                               Nocturnal Dream Loop
                            (Anna & Aurora Post/Sogni)
```

---

## Utilizzo dello Strumento (`trend_scout_reach.py`)

Lo script si trova in `scripts/diagnostics/trend_scout_reach.py` ed è eseguibile dall'ambiente Python del repository (`.venv`):

```bash
# Esecuzione completa con i temi predefiniti e salvataggio automatico per il dream loop
.venv/bin/python scripts/diagnostics/trend_scout_reach.py --save

# Diagnostica dei canali Agent-Reach
.venv/bin/python scripts/diagnostics/trend_scout_reach.py --doctor

# Ricerca personalizzata su un canale specifico (web, youtube, reddit, github)
.venv/bin/python scripts/diagnostics/trend_scout_reach.py --channel web --query "quantum consciousness aesthetics" --limit 3

# Output in JSON grezzo per integrazioni CLI / API
.venv/bin/python scripts/diagnostics/trend_scout_reach.py --channel youtube --query "space discovery 2026" --json
```

---

## Privacy & Guardrail
* Tutti i testi estratti vengono sanitizzati (`clean_snippet`): rimozione di tag HTML, stripping di URL grezzi e compattazione degli spazi.
* Non vengono mai importati o registrati account o credenziali personali.
* Nel prompt dei sogni (`shared/social_dreams.py`), i trend appaiono marcati come `[tendenza del mondo]`, distinguendosi dagli echi delle conversazioni senza mai contaminare i dati degli utenti.
