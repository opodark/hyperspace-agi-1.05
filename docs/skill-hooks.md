# Hook di selezione delle skill

`shared/skill_hooks.py` aggiunge `before_context` al tool loop comune a chat e
worker Mission Control. La selezione è deterministica, offline e senza nuove
dipendenze. Non cambia i permessi e non esegue script contenuti nelle skill.

## Sorgente e adattamento

Il riferimento importato è `diet103/claude-code-infrastructure-showcase`, commit
`07f75ce3c301259e857343596e7883b8ce5a9f50`, licenza MIT. La copia originale
`vendor/skill-hooks/skill-activation-prompt.ts` e la licenza sono fissate con
SHA-256 nel manifest. La copia è materiale di riferimento, non un programma
installato: dipende da altri moduli upstream che qui non vengono eseguiti.
Il selettore Python riprende il principio dei trigger dichiarativi, ma usa
regole locali, parole intere e controlli Forge. Nessun classificatore remoto,
regex configurabile dall'utente o installazione npm.

DeepAgents e i middleware Microsoft/Anthropic rimangono riferimenti valutati:
non sono dipendenze importate e non vengono presentati come integrazioni attive.

## Regole iniziali

| Famiglia | Trigger (parole intere, senza distinzione maiuscole) | Capacità necessaria | Ruoli |
| --- | --- | --- | --- |
| ECC security-review | security, sicurezza, vulnerability, vulnerabilità | code_sandbox | coder, verifier, chat |
| ECC verification-loop | test, tests, pytest, verifica, regression, regressione | code_sandbox | coder, verifier, chat |
| anydoc convert-documents-to-markdown | converti, convert, conversione | converti_documento_markdown | worker, chat |
| Wayfinder wayfinder | wayfinder, pianifica, planning | wayfinder_map | chat |
| Firecrawl firecrawl-scrape | url, web, pagina, page, skill.md, leggi, read | web_fetch | worker, repo-analyst, chat |

Le regole sono definite nel codice server, associate ai prefissi ID dei bundle.
Si considera l'ultimo messaggio utente testuale, che nelle missioni contiene
obiettivo, criteri e istruzione del task. Non si ispezionano file dell'host.
Sono ammessi soltanto artifact di tipo skill, approvati, con hash del sorgente
corrispondente all'approvazione. La scelta esplicita già inserita nel contesto
ha precedenza. Si caricano al massimo due skill nel limite condiviso di 24000
byte, inclusa l'introduzione di sicurezza e l'eventuale adattatore Wayfinder.

Le skill sono contesto di supporto e non impongono da sole una specifica scelta
di tool. Per una richiesta che contiene un URL esplicito, il tool loop del chat
usa una regola deterministica: offre `web_fetch`, nasconde `web_search` per quel
turno e blocca la risposta in prosa se il fetch non riesce o restituisce nessun
contenuto. Questo evita che una ricerca per URL venga scambiata per lettura della
pagina.

## Osservabilità e limiti

Nel feed log `type=skill`, evento `before_context selection`, ciascun candidato
ha ID, motivazione, trigger corrispondenti e tool mancanti. Non si registra il
prompt o il sorgente integrale. Motivi: selected, not_approved, approval_stale,
role_mismatch, missing_tools, no_trigger, selection_limit, context_rejected.
I record Forge non leggibili, troppo grandi o symlink vengono ignorati; lettura
limitata ai primi 1000 file JSON in ordine lessicografico. Le selezioni sono in
ordine ID, non classificate per rilevanza semantica.

Il percorso senza tool non attiva questo hook. Planner e verifica finale, che
usano completion senza tool, restano esclusi. Le skill approvate manualmente
restano disponibili attraverso il percorso chat esistente. La presenza del tool
nel catalogo non garantisce che il suo servizio sia sano: errori di esecuzione
restano responsabilità degli hook di runtime e delle evidenze.

Questa versione non implementa caricamento progressivo su richiesta del modello,
selezione semantica, trigger sui percorsi dei file o benchmark di qualità con LLM.
I test verificano selezione e integrazione nel loop con modelli simulati.

I controlli before_tool/after_tool già in `shared/tool_runtime.py` continuano a
far rispettare allowlist, azioni, budget ed evidenze. La verifica di conclusione
resta in Mission Control: una skill selezionata non costituisce prova di successo.
