# Integrazione TasteSkill (tasteskill.dev) in HyperSpace AGI

Questo documento descrive l'integrazione di **TasteSkill v2** ([tasteskill.dev](https://www.tasteskill.dev/)) nell'ecosistema HyperSpace per la progettazione e costruzione di siti web, landing page e dashboard operative senza "AI slop".

---

## 1. Cos'è TasteSkill

TasteSkill (`Leonxlnx/taste-skill`) è un framework di **Art Direction e Design Taste** per agenti di coding (Antigravity, Cline, Codex, Claude Code). È distillato dallo studio di 247 siti di gallerie d'eccellenza (*One Page Love*, *Awwwards Sites of the Day*).

### Il problema che risolve (Anti-Slop)
I modelli LLM tendono spontaneamente a produrre pagine web generiche e stereotipate:
* Titoli centrati su 3 righe con etichetta superiore.
* Righe identiche di 3 card con icone decorative e gradienti viola/blu.
* Layout piatti privi di sostanza visiva e decisioni tipografiche marcate.

TasteSkill impone:
1. **Decisioni di Art Direction strutturate**: tipografia con scale dimensionali reali, gerarchia e ritmi di spaziatura.
2. **Substance over ornament**: immagini reali del dominio (interfacce reali, diagrammi, illustrazioni del progetto), campi di colore decisi, contenuti completi.
3. **Regole distinte tra Pagine Web e App Screens**:
   * **Pagine (Landing / Marketing)**: focalizzate su scrolling, composizione, messaggio forte e direzione visiva.
   * **App Screens (Dashboard / Cockpit / Analytics)**: regole specifiche per pannelli di lavoro, tabelle dense, metriche reali e controlli operativi (zero vanity numbers, no gradienti futili).

---

## 2. Percorsi e Registrazione nel Repository

| Risorsa | Percorso |
|---|---|
| **Repository Locale Vendored** | `vendor/taste-skill/` |
| **Skill Principale (`SKILL.md`)** | `vendor/taste-skill/skills/taste-skill/SKILL.md` |
| **Regole App Screens & Dashboard** | `vendor/taste-skill/skills/taste-skill/references/app-screens.md` |
| **Script di Decisione Stili** | `vendor/taste-skill/skills/taste-skill/scripts/draw.mjs` |
| **Inspector Browser Real-Time** | `vendor/taste-skill/skills/taste-skill/scripts/inspect.mjs` |
| **Manifest Integrazioni** | `integrations/integrations.manifest.yaml` (voce `taste_skill`) |
| **Symlink per Antigravity** | `~/.gemini/antigravity/skills/taste-skill` |
| **Symlink per Claude Code** | `~/.claude/skills/taste-skill` |

---

## 3. Come Usare TasteSkill per Costruire Nuove Pagine

Quando un agente deve creare o revisionare una pagina o dashboard in HyperSpace:

1. **Leggere la Skill**:
   Consultare `vendor/taste-skill/skills/taste-skill/SKILL.md`.

2. **Selezionare una Direzione di Design per il Sito**:
   Eseguire lo script di estrazione per proporre 3 direzioni ricercate:
   ```bash
   node vendor/taste-skill/skills/taste-skill/scripts/draw.mjs --brief "HyperSpace Sovereign AI Mesh" --out .taste-skill/
   ```

3. **Per Dashboard Operative e Cockpit Screens**:
   Applicare direttamente `vendor/taste-skill/skills/taste-skill/references/app-screens.md`:
   ```bash
   node vendor/taste-skill/skills/taste-skill/scripts/draw.mjs --app --brief "Mesh Analytics & Operations Cockpit" --out .taste-skill/app
   ```

4. **Verifica dello Stato nel Manager**:
   ```bash
   .venv/bin/python scripts/integrations_manager.py status --id taste_skill
   ```
