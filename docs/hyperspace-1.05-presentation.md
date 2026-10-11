# HyperSpace AGI 1.05 — presentazione di progetto

Presentazione generata il 2026-10-07 dalla documentazione del repository.

## La tesi

HyperSpace è un runtime operativo per agenti IA locali e distribuiti: coordina
modelli, strumenti, memoria, policy e nodi su lavoro reale di sviluppo,
automazione e conoscenza. Non è una chat con qualche tool aggiunto.

## Traguardi raggiunti

- Control plane con API compatibile OpenAI, routing, tool loop e dashboard.
- Mission Control: obiettivo → DAG bounded → worker per ruolo → verifica →
  review umana; gli artifact restano in sandbox usa-e-getta.
- Code Sandbox, Tool & Skill Forge e hook per allowlist, budget, evidenze e
  cancellazione cooperativa.
- Hermes come direzione backend della memoria, Dream review e graphify.
- Connector fabric per GitHub, Google Workspace, Microsoft 365 e Instagram.
- Canali, web node e profili Ufficio/Multimedia.
- AnyDoc, PDF inspector, Website Builder, Comic Builder e Reel Editor come
  flussi verticali documentati o prototipati.

## Il vantaggio

Il valore non è un singolo modello: è il confine operativo. Ogni agente ha ruolo,
capability, budget, evidenze e una revisione distinta dall'applicazione.
L'inferenza locale con Ollama riduce la dipendenza da un provider; Docker e
sandbox separano il lavoro generato dal checkout operativo; i connector portano
il runtime dentro sistemi reali.

## Quattro sbocchi commerciali

### Enterprise Local

Agenti su dati interni, connettori, audit e inferenza locale. Licenza/supporto
annuale, setup e integrazioni a progetto.

### Agent Operations Platform

Missioni bounded, sandbox, review e report per team tecnici. Abbonamento per
workspace o nodo, con livelli di supporto.

### HyperSpace Ufficio

Conversione documenti, PDF inspection, Office bridge e memoria di progetto.
Pacchetto installabile per studi, agenzie e reparti interni.

### HyperSpace Multimedia

Reel, immagini, fumetti e pipeline narrative con identità persistente. Licenza
studio e servizi di produzione.

## Piano 0–18 mesi

- **0–3 mesi:** un pilota pagante Enterprise Local o Ufficio, caso d'uso stretto,
  metriche e installazione assistita.
- **3–9 mesi:** installer, profili, backup/recovery, benchmark, audit export e
  contratto connector ripetibile.
- **9–18 mesi:** Linux production, browser worker, mesh con capability
  advertisement, tenancy e marketplace dopo l'hardening.

## Stato onesto

La mesh multi-node completa, HIP, failover generalizzato, benchmark comparabili,
profilo Linux production-first, browser worker completo e multi-tenancy sono
direzioni roadmap. Hermes richiede ancora verifica operativa di snapshot e
recovery. La selezione semantica delle skill e i benchmark LLM reali sono aperti.

## Metriche di prodotto

Tempo dall'obiettivo al diff approvabile; costo e latenza per missione; task
conclusi senza intervento extra; errori bloccati dalla policy; tempo di
installazione e recovery; retention e valore prodotto nel caso d'uso pilota.

## Tesi finale

HyperSpace ha già una base rara: tratta l'agente come un componente operativo
governato, non come una conversazione brillante. Il prossimo salto commerciale
è rendere un profilo verticale ripetibile, misurabile, installabile e
supportabile.

## Fonti

README.md, VISION.md, ROADMAP.md e i documenti in `docs/` su architettura,
Mission Control, sandbox, Forge, Hermes, connettori, Dream, sviluppo/security,
profili Ufficio/Multimedia, Reel Editor, Website, Comic Builder, networking e
crescita. Inventario completo: `rg --files docs | sort`.
