# docs/

Architecture and deployment notes for HyperSpace-AGI. Mission, lexicon and phases live in the root [VISION.md](../VISION.md) / [ROADMAP.md](../ROADMAP.md) — start there. This folder covers specific subsystems and setup guides.

## Setup / deployment

- [tailscale-mesh-setup.md](tailscale-mesh-setup.md) — cross-machine mesh over Tailscale (current transitional remote-access approach).
- [lan-demo.md](lan-demo.md) — fastest way to demo the mesh to someone on the same physical network, no tunnels.
- [onlyoffice-bridge.md](onlyoffice-bridge.md) — ONLYOFFICE ↔ HyperSpace document connector: event map, envelope and the implemented Phase C `/office/*` bridge (dedicated token, dashboard section, curl examples).
- One command to start everything (Windows): `.\scripts\start.ps1` — containers, wait-for-health, then a verdict on services, channels and identity (`-Check`, `-Driver`, `-Stop`; see the root [README](../README.md#quick-start)).
- Quick commands from the terminal: `python scripts/hs.py status|mode|logs|memory|persona|dreams|dream|host|models` — what the stack is doing, and `hs mode off|auto` to command the room bot without touching the browser.
- [host-access.md](host-access.md) — the surface that reaches the machine (host agent, sandbox, argv-only execution) and the staged plan for real shell/terminal access from an external runtime.

## Subsystems

- [dreams.md](dreams.md) — direction and staged roadmap for automatic idle-only memory reflection, including review and promotion rules.
- [hermes.md](hermes.md) — current integration boundary and end-to-end acceptance criteria for Hermes.
- [hermes-gadget-prototype.md](hermes-gadget-prototype.md) — simulatore Hermes Gadget collegato alla chat testuale HyperSpace, con pairing e prova locale.
- **Pole Motion** — progetto in **repository privato separato** (`github.com:opodark/pole-motion`): catalogo, analisi video e verifica sperimentale MuJoCo delle pose di Anna. Non è un servizio del control plane; HyperSpace lo usa soltanto come strumento interno di sviluppo, non come contenitore del progetto o dei suoi asset.
- [memory schema](../memory/schema/README.md) — the `hyperspace.memory.v1` entry contract and retention tiers (operative / project / persistent).
- [tool-skill-forge.md](tool-skill-forge.md) — controlled authoring, review and local IDE workflow for inert tool and skill drafts.
- [comic-builder.md](comic-builder.md) — storyline, continuity bible, episodi e vignette ComfyUI.
- [website-builder.md](website-builder.md) — siti statici isolati con preview, manifest e ZIP.
- [connectors.md](connectors.md) — connector fabric (GitHub, Microsoft 365, Google Workspace and Instagram): the `BaseConnector` contract, discovery, the read/write policy the control plane itself obeys, diagnostics and open limits.
- [persona.md](persona.md) — declared identity of the agent: identity document, live self-model, the verifiable disclosure policy ("I am an AI"), and the human-gated identity dream that proposes self-observations at night.
- [channel.md](channel.md) — external conversation surfaces (a room's chat and private messages): channel tokens, spam classification, moderation escalation and reply pacing decided by the control plane.
- [development-tooling-architecture.md](development-tooling-architecture.md) — one HyperSpace development experience backed by isolated offline, browser, dependency-audit and security-lab runtimes.
- [graphify.md](graphify.md) — repository knowledge graph for coding agents (local tree-sitter AST, plus an optional local LLM for the docs; pinned `graphifyy`, Apache-2.0): a development tool, not part of the runtime stack.
- [spider.md](spider.md) — la ragnatela procedurale (Web Crawlers) che cammina sulle parole di ogni pagina della UI: perché è una dipendenza locale **non versionata** (l'upstream non ha licenza e `tests/test_licensing.py` non può assorbirlo), cosa sopravvive alla navigazione (stato, non posizione), come si spegne (`SPIDER_ENABLED`, Alt+Shift+S, `?spider=off`).
- [comfyui.md](comfyui.md) — ComfyUI sul nodo win11 come volto visivo di HyperSpace: i pesi del modello d'immagine (`install-model.ps1`, verificati per impronta SHA-256), **cosa filtra la catena e cosa no** (nessun anello filtra: l'unico rifiuto possibile nasce dal modello che scrive il prompt), i nodi `HyperSpacePrompt`/`HyperSpaceMesh`, il contratto `/v1/chat/completions` con `surface=comfyui` e `X-Hyperspace-Tools: off`, e il ponte "che tira" per la generazione su richiesta.
- [development-security-tools.md](development-security-tools.md) — current development, debugging and security capabilities, selective ECC integration, and planned specialist workers.
- [mission-control.md](mission-control.md) — orchestratore multi-agente opzionale e limitato: un obiettivo diventa un DAG di task eseguiti da worker con manifest di tool ristretti, codice in sandbox usa-e-getta, nessun artifact mai applicato e revisione umana obbligatoria (rotte `/missions*`, loop spento di default).
- [rea-pilot.md](rea-pilot.md) — prova statica di REA sul web-node, evidenze raccolte e limiti osservati.
- [architecture.md](architecture.md) — core layers (authority, control plane, node/worker, registry, memory graph, infra UI).
- [network-profiles.md](network-profiles.md) — Enterprise Local vs Public Hub deployment profiles.
- [ag-ui.md](ag-ui.md) — AG-UI come **formato di uscita** del control plane: la decisione (P0) — niente SDK a runtime, solo il formato — e lo spike (P1) sul feed di log dietro un flag spento di default, più il vocabolario delle capability che il manifest di Fase 3.5 adotta.
- [web-node.md](web-node.md) — browser-first worker path design intent (see also [web-node/README.md](../web-node/README.md) for the fuller technical spec and current implementation status).
- [growth-strategy.md](growth-strategy.md) — come Aurora e Anna passano da presenza privata a presenza seguita: posizionamento, canali, serie di contenuti, funnel e metriche.
- [tiktok-editor.md](tiktok-editor.md) — Reel Editor locale, brief via HyperSpace, tool per passare media approvati e flusso di estensione revisionato in Auto Forge.
- [sandbox-vita.md](sandbox-vita.md) — la simulazione della loro vita (post, poesia, sogni) su file isolati e un pubblico finto: la stessa giornata dei loop di produzione senza toccare Instagram, e il canale Telegram separato per vederla.
