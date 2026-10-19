# Piano di separazione: persona ↔ hyperspace generico

- **Stato**: proposta (da validare con Codex e Claude Code)
- **Data**: 2026-10-19
- **Autore**: Cline (Windows)

## 1. Obiettivo

Separare la "persona" (Anna/Aurora, sogni, Instagram, immagini/serie/volto, editor reel)
dal core "hyperspace" generico, così che il core possa essere usato per **azienda/ufficio**
senza trascinare la parte persona. Target: due unità — **core `hyperspace`** + **modulo
`hyperspace-persona`**.

## 2. Principi

1. Il core deve partire e funzionare **senza** persona (modalità azienda/ufficio).
2. La persona diventa un **modulo opzionale**, caricato solo se presente
   (`PERSONA_ENABLED` o auto-detect della presenza del modulo).
3. **Nessun import hard** di moduli persona dentro il core.
4. I segreti (`persona-anna.json`, `persona-aurora.json`) restano **fuori da git**,
   distribuiti via mesh cifrata (già così, vedere i commit `213b71f`/`bcf2bde`).
5. Migrazione per fasi, con **test verdi a ogni passo**.

## 3. Inventario

### 3.1 Moduli "persona" (migrano in `hyperspace-persona`)

`shared/` — persona, sogni, social, immagini:
`persona.py`, `persona_dream.py`, `intimate_diary.py`, `diario.py`,
`dream_log.py`, `dream_monitor.py`, `dream_schedule.py`, `dream_visual.py`,
`dream_evaluation.py`, `development_dream.py`, `social_dreams.py`,
`poetry_image.py`, `dialogue_image.py`, `feed.py`, `post_gen.py`,
`growth_metrics.py`, `sister_status.py`, `sketch.py`, `showcase.py`,
`prompt_immagine.py`, `image_translation.py`, `image_memory_gate.py`,
`instagram_intimacy.py`, `instagram_language.py`, `instagram_memory.py`,
`instagram_outbox.py`, `instagram_project_context.py`, `instagram_vip.py`,
`anna_vision_selection.py`, `vita_sandbox.py`, `reel_daily.py`, `reel_fx.py`.

`control-plane/cp/`: `persona.py`, `instagram.py`, `immagini.py`, `canali.py` (parte).
`control-plane/connectors/`: `instagram.py`.
`web-node/src/`: `anna-mascot.js`.
`integrations/`: `tiktok_editor/`, `sogni/`, `comfyui/` (parte), `apple-intelligence/` (parte).
`scripts/`: `dream_monitor.py`, `dream_scheduler.py`, `serie.py`, `serie_anna.py`,
`ritratto.py`, `prova_colori_anna.py`, `vita_sandbox.py`, `growth_report.py`,
`reel_*.py` (tutti), `instagram_*.py` (tutti), `telegram_bot.py`, `telegram_profile.py`,
`tiktok_editor_service.py`, `reel_daily_scheduler.py`.

`tests/`: `test_persona*`, `test_dream*`, `test_instagram*`, `test_serie_anna`,
`test_prova_colori_anna`, `test_showcase`, `test_riferimento_volto`, `test_sketch`,
`test_feed`, `test_growth_metrics`, `test_post_gen`, `test_sister_status`,
`test_intimate*`, `test_diario*`, `test_poetry_image`, `test_dialogue_image`,
`test_prompt_immagine`, `test_image_translation`, `test_image_memory_gate`,
`test_ask_aurora`, `test_vita_sandbox`, `test_social_dreams`, `test_anna_*`,
`test_reel_*`, `test_tiktok_editor_integration`, `test_channel_immagine`,
`test_telegram_bot`.

`docs/`: `persona.md`, `discord.md`, `social.md`, `channel.md`, `dream-nightly.md`,
`growth-strategy.md`, `comfyui.md` (parte), `connectors.md` (parte).

### 3.2 Restano nel core (riassunto)

Control-plane core (`assistant`, `battito`, `bottles`, `budget`, `chat`, `config`,
`doctor_mesh`, `env_meta`, `federazione`, `forge`, `http`, `inferenza`, `log`, `memoria`,
`mesh`, `metriche`, `mission`, `model_caps`, `tool`, `tools_defs`, `webnode`),
`shared/` core (`mesh_sync`, `db`, `identity`, `crypto_channel`, `node_*`, `mission_*`,
`memory_*`, `hermes_*`, `code_sandbox`, `web_search`, `web_topology`, `tokenomics`,
`connector_policy`, `office_bridge`, `shell_*`, `skill_*`, `tool_runtime`, `registry_client`,
ecc.), `node/`, `worker/`, `authority/`, `registry/`, `federation-gateway/`, `gateway/`,
`sandbox/`, `hostctl/`, `infra-ui/`, `memory/`, `connectors/` (`github`, `google`,
`office365`, `manager`, `base`), `web-node/` (eccetto `anna-mascot.js`), script e test core.

### 3.3 File "misti" da spezzare (decisione in Fase 1)

- `shared/image_jobs.py` — coda generica + ricette persona (SDXL/Pony, ChickMixFlat/Anna).
- `control-plane/cp/canali.py` — canali generici + persona (telegram/discord/instagram).
- `control-plane/cp/immagini.py` — route immagini generiche + volto Anna.
- `control-plane/main.py` — **import hard** di persona/canali/immagini/instagram da rendere opzionali.
- `shared/social_*.py` (`social_policy`, `social_queue`, `social_text`) — social generico vs sogni/persona.
- `integrations/comfyui/` — ponte generico (ComfyUI) + ricette/volto persona.
- `web-node/` — landing generica + parti persona (mascotte, sezione immagini).

## 4. Interfaccia plugin (extension point)

Il core espone un **registro plugin** (`control-plane/cp/plugin_registry.py`, nuovo):

```python
# core — carica la persona solo se presente
persona = load_optional("hyperspace_persona")   # None se il modulo non c'è

# nel bootstrap del CP:
if persona is not None:
    persona.register(app, cfg)   # registra route, canali, tool
```

La persona espone un unico entry point `register(app, cfg)` che:
- registra le route (`/dreams/*`, `/instagram/*`, `/immagini/*`, `/diario/*`);
- registra i driver di canale (telegram, instagram, discord) nel registro canali esistente;
- registra i tool (via `tools_defs`/forge) senza toccare il core.

`PERSONA_ENABLED` (env) = true/false/auto; `auto` = carica se il modulo è importabile.

## 5. Fasi

1. **Boundary** — validare file-per-file l'elenco §3 con Codex e Claude Code (soprattutto i "misti").
2. **Decouple** — introdurre `plugin_registry`, rendere opzionali gli import di `main.py`;
   il core deve partire e passare i test **senza** persona (flag off).
3. **Estrazione** — spostare i file persona nel modulo `hyperspace-persona/` (stesso repo, poi eventuale repo separato).
4. **Wiring** — auto-load + `register(app, cfg)`, test verdi in entrambe le modalità (con/senza persona).
5. **Segreti & distribuzione** — confermare che `persona-*.json` restino fuori git e via mesh;
   aggiornare `mesh_distribute.py --personas` se il path cambia.

## 6. Rischi & vincoli

- **Domini incrociati**: `integrations/tiktok_editor` è di Claude Code, `comfyui` di
  Cline+Codex, `web-node`/`telegram` di vari — ogni spostamento va coordinato via `AGENT-LOG.md`.
- **Segreti**: non committare mai `persona-*.json` né riferimenti a contenuti espliciti nel piano.
- **Suite**: la migrazione deve mantenere verde la suite core (`.venv`) e i test reel
  (interprete dell'editor).
- **RBAC mesh**: aggiornare gli scope di ruolo (`shared/mesh_sync.py`) se i path dei file cambiano
  (`worker-gpu` tocca `scripts/reel_*.py` e `shared/image_jobs.py`).

## 7. Definizione di done

- Il core gira con `PERSONA_ENABLED=false` e produce un CP azienda/ufficio pulito.
- La persona gira con `PERSONA_ENABLED=true` senza modifiche al core.
- Suite verde in entrambe le modalità; nessun import hard di persona nel core.
- `persona-*.json` assenti da git; distribuzione via mesh funzionante.

