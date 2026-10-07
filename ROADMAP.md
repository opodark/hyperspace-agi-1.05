# HyperSpace-AGI Roadmap — Runtime Agenti IA

Missione, lessico e principi architetturali sono fissati in [VISION.md](VISION.md). Questo documento copre stream di lavoro, fasi, deliverable e decisioni operative.

## Stream di lavoro

### Runtime core
- Definire il contratto tra orchestratore, agenti e provider LLM.
- Introdurre un layer di routing per ruoli modello: general, coder, planner, memory, tool-agent.
- Formalizzare code richieste, timeout, retry policy e fallback soltanto verso modelli non censurati verificati; in mancanza, restituire un errore esplicito.
- Separare configurazione runtime, configurazione agenti e segreti operativi tramite `.env` e profili Compose.

### Agent framework
- Standardizzare il ciclo agente: goal, context load, planning, tool execution, memory writeback, result handoff.
- Distinguere agenti persistenti, agenti ephemeral e agenti delegati a task singolo.
- Introdurre subagent policy e capability manifest per limitare scope e permessi operativi.
- Definire ruoli iniziali: orchestrator, planner, coder, repo-analyst, memory-agent, ops-agent.

### Local inference layer
- Assumere Ollama come primo target supportato per Windows e Linux.
- Mantenere una coppia di modelli non censurati di riferimento nella fascia 14B per hardware consumer, con ruoli generalista e coder.
- Catalogare provenienza e verifica dei modelli per ogni ruolo e modalità; impedire il routing automatico verso modelli non verificati, anche tramite provider esterni.
- Esporre sia API native Ollama sia endpoint OpenAI-compatible per compatibilità con tool terzi.
- Introdurre benchmark interni per latenza, RAM, parallelismo e stabilità su macchine 48 GB RAM e oltre.

### Memory layer
- Separare memoria operativa breve, memoria di progetto e memoria persistente long-term.
- Definire formato comune per note agente, decision log, task state e artifact metadata.
- Prevedere policy di garbage collection e summarization per evitare deriva del contesto.
- Collegare la memoria agli agenti come capability esplicita, non come side effect implicito.

### Dreaming e consolidamento
- Eseguire cicli automatici solo quando il nodo è libero, interrompendoli appena arriva lavoro prioritario.
- Trattare ogni sogno come **ipotesi candidata** separata dai fatti e dalla memoria operativa.
- Conservare provenienza, memorie sorgenti, modello, prompt, timestamp e metriche di esecuzione per rendere ogni risultato verificabile.
- Introdurre un ciclo esplicito `hypothesis → reviewed → promoted/rejected`; soltanto i risultati promossi possono entrare nella memoria persistente o nel retrieval degli agenti.
- Valutare utilità, novità, correttezza e costo prima di abilitare condivisione tra nodi o forme di consolidamento automatico.
- Mantenere disabilitati tool e azioni esterne durante i sogni; eventuali capacità operative richiederanno una decisione architetturale separata.

### Ops e deployment
- Consolidare il profilo **Windows Primary Brain** con Ollama su host, HyperSpace in Docker e accesso remoto via Tailscale.
- Preparare il profilo **Linux Primary Brain** come target successivo, con path nativi, systemd e maggiore efficienza operativa.
- Standardizzare healthcheck, logging, restart policy, backup e recovery del nodo principale.
- Formalizzare bootstrap scripts per setup rapido di nuovi nodi.

### Human-agent collaboration
- Introdurre directory `.claude/` come punto di controllo per istruzioni, memoria di progetto e policy per Claude Code.
- Definire convenzioni condivise per editing file, naming, commit, changelog e modifiche infrastrutturali.
- Trattare Claude Code come teammate di sviluppo, non come provider runtime del cervello locale.
- Documentare chiaramente i confini: cosa può essere modificato in autonomia, cosa richiede approvazione, cosa è vietato toccare.
- Eseguire sviluppo e test agentici soltanto nel Code Sandbox offline; il checkout operativo riceve modifiche esclusivamente dopo review separata.

### Tooling unificato per sviluppo e security
- Presentare Dev Sandbox, Forge, benchmark, debug, test, security review e pentest di laboratorio come capacità di un unico HyperSpace.
- Separare i runtime di esecuzione in base all'accesso richiesto: sandbox offline, dependency audit, browser worker e security-lab worker.
- Usare un contratto comune per job, finding, report, artefatti e `traceId`, così coding agent e UI non dipendono dallo strumento concreto.
- Trattare Nmap, ZAP e Playwright come strumenti utili al ciclo di sviluppo dei coding agent, mantenendoli fuori dall'immagine sandbox offline.
- Mantenere il monorepo finché worker e adapter non richiedono release, distribuzione o manutenzione indipendenti.
- Assumere nella fase corrente un ambiente privato single-tenant con due operatori fidati: l'hardening completo resta necessario prima dell'uso pubblico, multiutente o autonomo, ma non blocca benchmark e worker di laboratorio.

### Profili di prodotto: Ufficio e Multimedia
- Dopo il consolidamento dello stack corrente, separare l'esperienza operativa in **HyperSpace Ufficio** e **HyperSpace Multimedia**, mantenendo un unico core condiviso e un solo monorepo.
- Lasciare nel core control-plane, mesh, memoria, autenticazione, routing dei modelli, task, audit, connector policy e protocolli: i due profili non devono diventare fork che evolvono separatamente.
- **HyperSpace Ufficio** abilita bridge ONLYOFFICE, documenti, ricerca, Microsoft 365, automazioni, coding e strumenti di produttività; include una pipeline immagini professionale dedicata a loghi, carta stampata, presentazioni e grafiche web, senza dipendere dalle ricette social del profilo Multimedia.
- Espandere i connector Ufficio verso database ed ERP attraverso contratti read-only per default, credenziali separate, audit e capability granulari; dare priorità ai connector **ServiceNow** e **Microsoft Teams**, necessari per una prova presso un'azienda cliente.
- Introdurre **Anna Desktop Guide**, un assistente visivo locale che comprende ciò che l'utente ha davanti in applicazioni e siti web, mostra un piccolo avatar e offre guida contestuale nell'uso quotidiano del computer.
- Anna Desktop Guide deve privilegiare Accessibility API/UI Automation e DOM del browser; screenshot e OCR/VLM sono fallback espliciti. Acquisizione, conservazione e invio dei contenuti devono essere visibili, revocabili e local-first, con esclusione configurabile di password manager, campi sensibili e applicazioni riservate.
- **HyperSpace Multimedia** abilita ComfyUI, identità visiva, diario, feed, sogni, poesie, canali social e generazione audio/video futura; non deve caricare per default i connector e le UI da ufficio.
- Separare per profilo dashboard, code, storage, segreti, limiti di risorse e policy di autonomia, evitando che un workload multimediale saturi il nodo che sta svolgendo lavoro d'ufficio.
- Realizzare la separazione tramite profili Compose e capability manifest (`core`, `office`, `multimedia`), non duplicando il codice applicativo.

## Roadmap per fasi

### Fase 0 — Riallineamento strategico
- Aggiornare documentazione e naming del progetto: da framework agentico generico a runtime agenti IA.
- Definire missione, scope e casi d'uso primari.
- Allineare il repository ai nuovi concetti: runtime, node, profile, agent role, provider, memory layer.
- Redigere il manifesto operativo del Primary Brain.

### Fase 1 — Windows Primary Brain
- Stabilizzare il setup Asus con Windows come nodo principale provvisorio.
- Fissare `.env`, `docker-compose.yml`, path persistenti e accesso a Ollama host tramite `host.docker.internal`.
- Integrare Tailscale come accesso remoto sicuro al nodo e ai servizi interni.
- Validare la coppia modelli 14B e misurare comportamento reale in RAM, latenza e parallelismo.

### Fase 2 — Runtime orchestration
- Introdurre registry agenti e schema capability-based.
- Implementare task dispatcher con routing per tipo di lavoro e modello.
- Aggiungere memoria operativa, log strutturati e tracciamento esecuzioni.
- Definire protocolli di handoff tra agenti.
- Portare il worker dei sogni dalla prima implementazione al ciclo revisionabile descritto in [docs/dreams.md](docs/dreams.md): output strutturato, provenienza, revisione e promozione controllata.

### Fase 3 — Tooling e collaboration layer
- Integrare ufficialmente Claude Code come agente-collaboratore di sviluppo sul repository Windows.
- Standardizzare `.claude/CLAUDE.md`, policy di editing e checklist per modifiche critiche.
- Abilitare workflow di sviluppo assistito su file locali, review diff e task decomposition.
- Estendere il Tool & Skill Forge dalla fondazione locale già implementata agli adapter di pubblicazione controllata per Open WebUI, MCP e OpenAPI.
- Separare chiaramente runtime production e workspace di sviluppo.
- Consolidare l'esperienza unica descritta in [docs/development-tooling-architecture.md](docs/development-tooling-architecture.md), mantenendo separati runner offline, browser e security lab.
- Portare il benchmark dei modelli nella sandbox e confrontare workflow con e senza skill ECC su fixture verificabili.
- Aggiungere in sequenza report persistenti, dependency audit, Playwright e infine Nmap/ZAP nel laboratorio privato.

### Fase 3.5 — Consolidamento e separazione Ufficio/Multimedia
- Chiudere i lavori concorrenti, ottenere un working tree pulito e validare un avvio completo e ripetibile dello stack attuale.
- Inventariare servizi, route, variabili, volumi e dipendenze, assegnandoli a `core`, `office`, `multimedia` oppure a una capability opzionale condivisa.
- Introdurre profili Compose avviabili separatamente e una configurazione esplicita del profilo attivo.
- Creare una dashboard comune di ingresso con due workspace distinti: Ufficio e Multimedia.
- Dare a ciascun workspace una dashboard mirata: documenti, task e connector per Ufficio; pipeline creative, code ComfyUI, galleria e attività social per Multimedia.
- Separare namespace dei dati e backup, preservando memoria e identità condivise solo dove la policy lo consente.
- Verificare tre deployment: `core+office`, `core+multimedia` e stack completo, senza regressioni nei contratti API comuni.

### Fase 3.6 — HyperSpace Ufficio e Anna Desktop Guide
- Separare un generatore grafico Ufficio dalle pipeline persona/social: preset per logo, intestazione, carta stampata, slide, icone e asset web; output vettoriale quando possibile e raster ad alta risoluzione quando necessario.
- Definire il connector SDK per database ed ERP: introspezione schema controllata, query parametrizzate, sola lettura predefinita, allowlist di tabelle/operazioni, audit e segreti per tenant.
- Implementare per primi i connector ServiceNow e Microsoft Teams, con ambiente demo, scope OAuth minimi e fixture riproducibili prima della prova presso il cliente.
- Costruire Anna Desktop Guide come applicazione companion con core comune e adapter OS: Accessibility API su macOS, UI Automation su Windows e browser extension per il DOM web.
- MVP Desktop Guide: rilevare applicazione/finestra attiva, leggere struttura accessibile e testo selezionato, spiegare l'interfaccia, suggerire il prossimo passo e visualizzare un avatar discreto; nessun click o input autonomo nella prima versione.
- Aggiungere in una fase successiva OCR/screenshot locale per applicazioni non accessibili, memoria di sessione opt-in e azioni assistite sempre confermate dall'utente.
- Preparare modalità aziendale: esclusioni applicative, redazione dati sensibili, retention nulla o limitata, log amministrativi senza contenuto dello schermo e configurazione per tenant.
- Dare ad Anna voce e ascolto attraverso il web-node: push-to-talk, trascrizione Whisper locale, risposta del modello locale, sintesi vocale e avatar con stati visibili.
- Introdurre un selettore adattivo dei modelli WebGPU: benchmark del dispositivo prima del download, profilo compatibile/standard/potenziato e scaricamento dalla GPU dopo inattività.
- Sostituire i modelli dimostrativi da 0,5–1,7B con una scala utile: Gemma 2 2B come fallback, Llama 3.2 3B come baseline iniziale e Gemma 2 9B sui dispositivi realmente capaci.
- Per il rollout aziendale, distribuire e cacheare internamente i pesi evitando download simultanei da Internet; applicare quote, finestre di aggiornamento e limiti di CPU/GPU/batteria.

### Fase 3.7 — Website Builder end-to-end
- Trattare la creazione di siti come caso di consolidamento prioritario: collega in un solo flusso modello coder, Code Sandbox, artefatti, Browser Worker, generazione grafica, review e deployment.
- Aggiungere template versionati per landing page, sito vetrina e applicazione frontend, senza vincolare il core a un singolo framework JavaScript.
- Esporre dalla sandbox una preview temporanea isolata, mai il checkout operativo, con URL a scadenza e limiti espliciti di rete e risorse.
- Usare Playwright per navigazione, screenshot, responsive check, accessibilità di base e raccolta degli errori console; il modello può proporre correzioni sulla base di artefatti verificabili.
- Produrre un bundle scaricabile (ZIP) con manifest, dipendenze, istruzioni di avvio, report delle verifiche e provenienza degli asset.
- Introdurre una promozione esplicita `sandbox → progetto`: diff revisionabile e approvazione umana prima di scrivere nel repository operativo.
- Aggiungere adapter di deploy separati e confermati dall'operatore (static hosting, Aruba, Render); nessun deploy autonomo nella prima versione.
- Integrare il generatore grafico Ufficio per loghi, icone e asset web, privilegiando SVG e composizione deterministica per gli elementi di identità visiva.

### Fase 3.8 — Comic Builder e storyline persistente
- Gestire progetti narrativi con premessa, cast, identità visive e continuity bible.
- Dividere gli episodi in vignette con scena, dialogo e didascalia separati dal prompt immagine.
- Generare una vignetta alla volta tramite la coda ComfyUI e riconciliarne stato e file.
- Comporre tavole ed export senza affidare balloon e testo al modello diffusion.
- Usare la storyline come fonte esplicita per diario e social, senza pubblicazione automatica.

### Fase 4 — Multi-node e mesh
- Passare da accesso singolo via Tailscale a topologia multi-nodo più completa quando il branch mesh sarà pronto.
- Introdurre ruoli nodo: primary brain, worker node, memory node, coding node, edge node.
- Definire sync di stato, delega task inter-node e failover di servizi critici.
- Formalizzare i contratti di rete e autenticazione tra nodi.
- Questa fase è il punto di innesto per il protocollo **HyperSpace Intent Protocol (HIP)** — vedi [Visione a lungo termine](#visione-a-lungo-termine--hyperspace-intent-protocol-hip) più sotto.

### Fase 5 — Linux production profile
- Portare il Primary Brain su Linux quando l'hardware e la direzione finale saranno confermati.
- Tradurre il profilo Windows in deployment Linux con maggiore controllo su processi, filesystem e networking.
- Ottimizzare inferenza locale, startup, persistenza e monitoraggio.
- Rendere Linux il target production-first, lasciando Windows come profilo supportato per bootstrap e transizione.

## Deliverable prioritari

| Priorità | Deliverable | Scopo | Stato |
|---|---|---|---|
| P0 | `VISION.md` | Fissare missione, lessico e obiettivi del runtime | ✅ fatto |
| P0 | `ROADMAP.md` | Rendere esplicite fasi, milestone e stream di lavoro | ✅ fatto |
| P0 | `.env.windows` | Profilo ufficiale Windows Primary Brain | ✅ fatto |
| P0 | `docker-compose.windows.yml` | Stack standard per nodo Asus Windows | ✅ fatto |
| P1 | `.claude/CLAUDE.md` | Regole operative per Claude Code teammate | da fare |
| P1 | `agents/registry.yml` | Catalogo ruoli, modelli e capability agenti | da fare |
| P1 | Code Sandbox | Workspace offline, diff e test senza write-back sul repository operativo | prima versione implementata |
| P1 | Nightly Development Dream | Esperimento notturno con microVM preferita, fallback offline, doppia verifica e review senza auto-apply | implementato |
| P1 | Dream review lifecycle | Revisione, promozione o rifiuto delle ipotesi generate nei periodi di inattività | fondazione implementata |
| P1 | Tool & Skill Forge | Generazione, modifica, validazione e approvazione esplicita di draft inerti | fondazione implementata |
| P1 | Unified Development Tooling | Un'unica UI e un contratto comune per Dev Sandbox, skill, test, debug e security review | architettura fissata; sandbox e Forge implementati |
| P1 | Profili Ufficio/Multimedia | Due workspace e deployment distinti sopra lo stesso core, senza fork della codebase | pianificato dopo il consolidamento |
| P1 | Anna Desktop Guide | Lettura contestuale cross-app con avatar, Accessibility/UI Automation e fallback OCR locale | MVP da avviare subito |
| P1 | Anna Voice nel web-node | Whisper locale, modello WebGPU adattivo, TTS locale e avatar parlante | pianificato; architettura definita |
| P1 | ServiceNow + Teams connectors | Integrazione enterprise pronta per una prova cliente, con OAuth minimo e audit | prioritario nelle prossime settimane |
| P1 | Website Builder end-to-end | Chat → sandbox → preview browser → review → ZIP → promozione/deploy approvato | prioritario; fondazione sandbox già operativa |
| P1 | Comic Builder | Storyline → continuity bible → vignette → tavola → diario/social approvati | core e API MVP implementati |
| P2 | Office Graphics Generator | Loghi, carta stampata, slide e asset web separati dalla pipeline social | pianificato nel profilo Ufficio |
| P2 | Database/ERP Connector SDK | Contratto sicuro e riusabile per database ed ERP | pianificato |
| P1 | Hermes Memory Backend | Sostituire interamente la memoria cognitiva HyperSpace con Hermes; mantenere API, policy, review e viste come adapter senza dual-write | implementato (backend default `hermes`); restano verifica operativa snapshot/recovery e legacy read-only |
| P1 | `profiles/linux-primary/` | Base del futuro target Linux production | da fare |
| P2 | `benchmarks/` | Misure comparabili su modelli, RAM e latenza | da fare |
| P2 | Browser Worker | Playwright, screenshot e Trace Viewer come artefatti di sviluppo | pianificato |
| P2 | Security Lab Worker | Nmap e ZAP su target dichiarati nella rete privata di laboratorio | pianificato |
| P2 | `memory/schema/` | Contratti per memoria breve e persistente | contratto v1 e JSON Schema in `memory/schema/`, implementazione in `shared/memory_schema.py` |
| P2 | Dream evaluation | Dataset e metriche per utilità, novità, correttezza e costo dei sogni | metriche D3 in `shared/dream_evaluation.py`; correttezza e costo dipendono da annotazioni/strumentazione |
| P2 | `ops/bootstrap/` | Script di setup e recovery nodo | da fare |

## Decisioni immediate
- Mantenere **Windows sull'Asus** come piattaforma primaria temporanea.
- Usare **Ollama** come runtime modelli locale standard del progetto.
- Adottare una coppia iniziale di modelli 14B non censurati: un generalista e un coder.
- Usare **Tailscale** come soluzione di accesso remoto e collegamento sicuro in attesa della mesh completa.
- Inserire **Claude Code con Sonnet 5** come teammate di sviluppo che opera sui file locali del repository sotto policy di progetto.
- Mantenere i sogni locali, inattivi per default e separati dalla memoria autorevole finché il ciclo di revisione non è validato.
- Tenere un unico core HyperSpace e un solo monorepo, ma presentare e distribuire due profili operativi distinti — **Ufficio** e **Multimedia** — con servizi, dashboard, risorse e policy separati.
- Dare priorità a benchmark sandboxizzato, report e nuovi strumenti di sviluppo; completare l'hardening end-to-end prima di ampliare utenti, autonomia o esposizione pubblica.

## Rischi principali
- Ambiguità tra "framework di sviluppo" e "runtime operativo", con conseguente dispersione architetturale.
- Eccessiva dipendenza da un singolo host Windows prima della formalizzazione del profilo Linux.
- Crescita non controllata della complessità agentica senza capability boundaries e regole di handoff.
- Assenza iniziale di benchmark strutturati per capire il limite reale dell'hardware consumer.
- Confusione tra agenti runtime interni e agenti-collaboratori esterni al runtime.
- Promozione di ipotesi plausibili ma errate nella memoria persistente, con contaminazione delle decisioni successive.
- Consumo di risorse o latenza sul lavoro interattivo causati da cicli in background non correttamente interrotti.
- Trasformare la sandbox offline in un'immagine monolitica con browser e accesso di rete, perdendo isolamento e rendendo i risultati meno riproducibili.
- Lasciare che il threat model fidato della fase iniziale diventi implicitamente quello di un futuro deployment pubblico o multiutente.

## Criteri di successo
- Un nodo Primary Brain avviabile in modo ripetibile su Windows con setup documentato.
- Almeno due agenti specializzati funzionanti con routing modello distinto.
- Memoria e logging sufficienti a ricostruire una run end-to-end.
- Sogni ricostruibili dalle fonti, revisionabili e incapaci di modificare la memoria autorevole senza promozione esplicita.
- Workflow collaborativo stabile tra sviluppo umano, Claude Code e runtime locale.
- Un coding agent può attraversare modifica, lint, test, analisi statica, report e proposta Forge attraverso un contratto HyperSpace unico, mentre ogni passo gira nel runtime appropriato.
- Profilo Linux già disegnato, anche se non ancora target primario di produzione.

## Sintesi operativa

La roadmap posiziona HyperSpace-AGI come **runtime modulare di agenti IA locali e distribuiti**, non come semplice collezione di script o demo di agenti. Il Primary Brain Windows su Asus è il primo nodo operativo, mentre Ollama, Tailscale e Claude Code costituiscono il primo stack collaborativo concreto da stabilizzare prima dell'evoluzione verso mesh completa e target Linux production-first.

---

## Visione a lungo termine — HyperSpace Intent Protocol (HIP)

Questa sezione era il piano attivo per HyperSpace 1.04 prima del riallineamento a runtime operativo (Fase 0 sopra). Resta la direzione di lungo periodo per la **Fase 4 — Multi-node e mesh**: quando la topologia multi-nodo sarà pronta, HIP è il protocollo candidato per far cooperare runtime agentici eterogenei attraverso il Primary Brain e i nodi worker.

### Vision originale

HyperSpace evolve da piattaforma di agenti distribuiti a protocollo di coordinamento distribuito per agenti IA. Invece di accoppiare gli agenti a un framework specifico, introduce un protocollo aperto che permette a runtime eterogenei di scoprirsi, pubblicizzare capability, negoziare esecuzione e scambiarsi lavoro. L'obiettivo non è sostituire i framework esistenti, ma connetterli.

### Design Philosophy

```
                AI Model
                    │
          Agent Runtime Layer
(OpenClaw, CrewAI, LangGraph, AutoGen...)
                    │
        ==========================
         HyperSpace Intent Protocol
        ==========================
                    │
        HyperSpace Control Plane
                    │
     Distributed Worker Network
```

Ogni runtime resta libero di implementare il proprio reasoning loop; HyperSpace coordina solo l'esecuzione.

### Intent-based execution

Gli agenti pubblicano **Intent** (capability desiderata, non implementazione concreta):

```json
{
  "intent": "translate_document",
  "source_language": "it",
  "target_language": "en",
  "max_latency_ms": 3000,
  "privacy": "private",
  "budget": 0.02
}
```

La rete decide dove eseguire il lavoro.

### Capability Advertisement

Ogni nodo pubblicizza periodicamente le proprie capability:

```json
{
  "node_id": "...",
  "runtime": "OpenClaw",
  "models": ["qwen3-9b", "deepseek-lite"],
  "tools": ["github", "filesystem", "browser"],
  "gpu": true,
  "vram": 8192,
  "ram": 49152,
  "latency_ms": 25
}
```

### Intent Router

Il Control Plane introduce un Intent Router responsabile di: scoprire worker compatibili, valutare policy di esecuzione, stimare costo e latenza, scegliere il nodo ottimale, dispatchare l'esecuzione, raccogliere i risultati.

### Execution Policies (pluggable)

Lowest latency · Lowest cost · Highest accuracy · Local-first · Privacy-first · GPU preferred · CPU only · Browser-first · Enterprise only.

### Runtime Independence

Runtime possibili: OpenClaw, CrewAI, LangGraph, AutoGen, agenti Python custom, Browser Worker. Ogni runtime implementa un adapter HyperSpace leggero.

### Browser Edge Workers

Tab del browser come nodi di esecuzione leggeri (traduzione, summarization, moderazione, embeddings, OCR, inferenza locale WebGPU) — nessun Docker richiesto.

### Enterprise Connector Fabric

L'esecuzione di Intent può puntare a sistemi enterprise tramite connector (GitHub, Microsoft 365, Google Workspace, Jira, GitLab, Slack, REST API), che diventano capability eseguibili invece di integrazioni statiche.

### Future Marketplace (Experimental)

Una versione futura potrebbe introdurre negoziazione decentralizzata delle capability, con i worker che pubblicizzano modelli supportati, latenza attesa, costo stimato, profilo energetico e garanzie di privacy. Nessuna blockchain o criptovaluta richiesta; la logica di marketplace resta opzionale.

### Long-Term Vision

HyperSpace non è un altro framework di agenti: è un layer di orchestrazione e coordinamento che permette a runtime IA indipendenti di cooperare su infrastrutture eterogenee — come HTTP ha standardizzato la comunicazione tra server web, HyperSpace punta a standardizzare l'esecuzione distribuita di intent tra agenti IA.

### Status

Obiettivi di implementazione iniziale (non attivi finché non si entra in Fase 4):

- [ ] Intent schema
- [ ] Capability advertisement
- [ ] Runtime adapter API
- [ ] Intent Router
- [ ] Worker negotiation
- [ ] Browser Worker integration

> Marketplace functionality is considered experimental and will be explored after the protocol stabilizes.
