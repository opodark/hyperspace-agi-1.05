# Revisione autocoding, skill e tool — 7 ottobre 2026

Revisione della working tree locale, mentre Cips prepara la pulizia della 1.04.
Nessuna modifica al codice applicativo, nessun deploy, nessun commit/push.
Le prove usano funzioni reali estratte via AST, handler/modelli finti e storage
in directory temporanee: nessun comando host o tool esterno realmente eseguito.

## Giudizio

HyperSpace è un laboratorio agentico privato con integrazioni concrete e una
base credibile per la 1.05. La forza è collegare modelli locali, documenti,
media, strumenti e artefatti in uno stesso ambiente. L'autocoding generale non
è ancora dimostrato con affidabilità ripetibile. La priorità è far coincidere
le promesse di policy, verifica e budget con ciò che il runtime impone davvero.
Dividere main.py aiuta la manutenzione ma non corregge queste divergenze.

## Riscontri prioritari

### 1. La selezione del catalogo non è un controllo al dispatch

`control-plane/main.py:6175` costruisce `all_tools` dai tool offerti al modello.
A riga 6255 esegue però il nome restituito dal modello attraverso il dispatcher
globale, senza verificarne l'appartenenza all'insieme autorizzato per quella
invocazione. `_execute_tool_call` (3313) cerca in tutti gli handler/connettori.

Riproduzione: harness `tests/test_tool_passthrough.py`, solo `web_search` offerto,
risposta modello finta con `shell_run`; viene chiamato l'handler finto shell_run.
Questo dimostra un bypass del confine di ruolo/catalogo, non l'esecuzione di una
shell reale: eventuali gate specifici del singolo handler restano distinti.
Vale anche per il loop notturno che offre soltanto code_sandbox.

Inoltre `shared/mission_policy.py` descrive verifier come non scrivente, ma gli
concede code_sandbox e `_tool_code_sandbox` (2766) accetta anche write, replace e
discard: manca una policy per azione, oltre che per nome del tool.

Priorità: controllo server-side immediatamente prima del dispatch, propagando
identità, superficie, ruolo, risorse e azioni ammesse. La skill non concede permessi.
Test di accettazione: tool non offerto rifiutato senza chiamare l'handler;
verifier non può scrivere neppure usando il tool sandbox correttamente nominato.

### 2. I criteri di accettazione si perdono

`shared/mission.py:144` salva `success_criteria`. Planner, worker e verifier in
main.py (11596, 11788, 11851) leggono invece `criteria`. Il controller passa loro
il record dello store; la conversione in `criteria` è solo nel payload HTTP.

Riproduzione: missione creata con criterio CRITERION_SENTINEL; lo store lo
conserva, ma il prompt del planner estratto dal codice non lo contiene.

Priorità: un contratto interno unico, con conversioni esplicite solo alle API.
Test: un criterio arriva identico a planner, worker e verifier partendo da una
missione creata attraverso il normale percorso di persistenza.

### 3. Mancanza di verifica può diventare successo

`control-plane/main.py:11840`: se il verifier non restituisce un verdetto valido,
un task con `outcome.ok` diventa pass. Il worker imposta ok sulla presenza di
output testuale (11828). `_mission_llm` assorbe gli errori e restituisce testo
vuoto, rendendo questo fallback rilevante anche per errori d'inferenza.

Riproduzione: verifier finto restituisce `{}`, worker ok con testo senza prove;
esito reale: `pass`, reason `default verdict: pass`.

Priorità: distinguere completamento, verifica e approvazione. Un verifier non
eseguito o illeggibile deve produrre esito non verificato/errore e una policy di
retry limitata. Il successo richiede evidenza coerente con il task: file/diff,
risultato del test, immagine o documento realmente prodotto, a seconda del caso.
Non imporre test software a task puramente informativi.

### 4. I budget della missione non governano il controller

`shared/mission_controller.py:63,202` usa self.budget inizializzato sul controller,
non il budget salvato sul record. Anche il planner usa `_mission_budget()` globale.
`max_tokens_per_task` è dichiarato ma non imposto; il worker restituisce tokens=0.

Riproduzione: MissionStore con max_steps=1, controller default, piano di due
passi dipendenti; entrambi eseguiti e missione done. Non è soltanto un problema
estetico della dashboard.

Priorità: budget effettivo derivato da limite globale e limite richiesto, applicato
prima di ogni chiamata e prenotazione di lavoro. Propagare deadline/cancellazione
fino al trasporto e al runner. Da lettura: future.cancel non interrompe un thread
già avviato, e il context manager del pool ne aspetta l'uscita; il timeout della
missione non equivale oggi a uno stop immediato dell'operazione sottostante.

### 5. Qualsiasi review fa sparire le attese di revisione

`shared/mission_controller.py:69` usa `bool(mission.reviews)` senza considerare
azione, task o versione/hash dell'artefatto. Riproduzione: un task coder done
con artefatto ha una review pendente; aggiungendo defer, reopen o reject,
`pending_review` restituisce zero in tutti e tre i casi.

Non dimostra applicazione automatica del codice: quella resta assente. Dimostra
che la coda di revisione e la guardia di ripresa non rappresentano la decisione.
Priorità: ultima decisione pertinente, associata ad artefatto/versione; defer e
reopen devono restare pendenti, reject deve essere distinguibile da approve,
nuovi artefatti richiedono una propria revisione.

## Skill e hook: stato reale e proposta

La Forge ha controlli utili: draft, approvazione legata all'hash, selezione esplicita
con hyperspace_skills, limite di contesto e provenienza upstream. È testo di
riferimento, non un motore di hook. `attach_skills` è chiamato nell'ingresso chat;
missioni e sviluppo notturno costruiscono percorsi propri. Il filtro WebUI Anna
attiva tool_ids per due nomi di modello esatti: è un adattatore specifico, non
un selettore generale di capacità.

Manca un legame strutturato tra skill, tool necessari, disponibilità nel runtime
e prova del risultato. Esempio: conoscere la skill anydoc non garantisce che
quella richiesta abbia il tool WebUI converti_documento_markdown. Il tool vive
nel registry WebUI; non va confuso con un tool nativo offerto automaticamente a
ogni missione. Wayfinder ha migliorato persistenza e handoff, ma non risolve il
dispatch o la verifica della successiva missione: vale anche per il mio lavoro.

Propongo quattro punti d'intervento comuni, con funzioni testabili e payload
tipizzati, senza un sistema di script shell arbitrari caricati dalle skill:

| Punto | Responsabilità | Prova minima |
| --- | --- | --- |
| Prima del contesto | Selezionare workflow approvati pertinenti; leggere metadati prima dei testi; controllare tool richiesti e contesto disponibile | Se anydoc non è eseguibile, dichiararlo prima della promessa di conversione |
| Prima del tool | Validare nome, argomenti, azione, scope, budget, cancellazione e autorizzazione | Tool/azione fuori capacità non raggiunge l'handler |
| Dopo il tool | Normalizzare risultato, errore, artefatti e tempi; retry soltanto quando sicuro | Un errore non compare come successo; una scrittura non viene duplicata da un retry |
| Prima della conclusione | Confrontare prove e criteri, conservare il risultato e la revisione pertinente | Nessun test eseguito significa non verificato, non pass |

Un contesto di esecuzione comune dovrebbe includere run/task ID, chiamante,
superficie, ruolo, capacità consentite, skill selezionate con versione/hash,
deadline e budget residuo. Il risultato comune dovrebbe distinguere completato,
esito, errore, artefatti e prove. Il nome del tool non basta per autorizzarlo.
Chat, Mission Control, sviluppo notturno, MCP e WebUI possono mantenere ingressi
diversi ma devono convergere su questo controllo prima dell'esecuzione.

Nei log del tool loop (main.py:6254–6256) argomenti/risultati sono tagliati a 120
caratteri, non redatti per schema, e il risultato è registrato come success anche
quando è testo d'errore. Propongo eventi correlati e campi sensibili redatti prima
del logging. La redazione non va affidata al modello.

## Dove il progetto è forte

- Produce artefatti reali: siti, documenti Markdown, immagini e reel hanno percorsi
  implementati. Le verifiche live precedenti sono registrate nell'AGENT-LOG;
  questa revisione non ha ripetuto render o pubblicazioni.
- L'isolamento della sandbox è sostanziale: Compose disabilita la rete, usa root
  filesystem read-only, drop delle capability e limiti di processo/memoria/CPU.
- Forge separa proposta, approvazione e uso; le skill upstream sono versionate
  e verificate. Questo è una buona base per distribuirne l'uso senza eseguire
  automaticamente codice importato.
- Esistono moduli già separati e testabili: MissionStore/controller, policy,
  registry WebUI, Wayfinder. Cips ha confini reali su cui lavorare.
- CI Python 3.11/3.12 e test JS esistono. Molti test verificano comportamenti,
  non solo stringhe. Non è un progetto privo di disciplina tecnica.

## Debolezze di prodotto e manutenzione

- Il numero di funzionalità cresce più rapidamente della loro integrazione.
  Cataloghi, token, store e percorsi di esecuzione diversi aumentano il costo di
  capire cosa un agente può realmente fare in ciascuna superficie.
- Avere molti test verdi non misura il successo dell'agente. Durante questa
  revisione 91 test mirati e 18 subtest passano, mentre le cinque riproduzioni
  sopra mostrano difetti non coperti. I test AST sono utili ma non verificano
  da soli bootstrap, HTTP reale, modello, tool e artefatto nella stessa prova.
- Non emerge ancora una valutazione ripetibile del vantaggio delle skill:
  la documentazione indica il benchmark con/senza skill come prossimo lavoro.
  Non attribuire alla skill un miglioramento senza misurare esiti, tempi,
  tentativi e interventi umani sullo stesso insieme di compiti.
- L'installazione è ancora legata al Mac operativo (runtime editor esterno,
  servizi host e dati locali). Il target attuale dichiarato è privato e fidato,
  non un prodotto multiutente pronto a essere esposto.
- Documentazione e stato divergono: AGENTS riporta ancora il vecchio baseline;
  mission-control.md indica Diagnostics e budget per-missione applicati.
  Nello snapshot main.py ha 12.011 righe, dashboard 2.929; ci sono 70 modifiche,
  10 cancellazioni in stage e 128 voci non tracciate (anche directory). La CI
  remota non certifica una working tree ancora non pubblicata.

## Ordine consigliato per 1.05

1. Convertire le cinque riproduzioni in regressioni comportamentali e correggere
   i contratti dopo il coordinamento con Cips. Non aggiungere autonomia finché
   dispatch, criteri, verdetti, budget e review non corrispondono alle promesse.
2. Separare catalogo, selezione e dispatch; introdurre contesto di esecuzione e
   policy per azione. Cips può preservare la compatibilità delle rotte mentre
   estrae questi confini, senza rinominare contratti e cambiare semantica insieme.
3. Collegare skill approvate a capacità disponibili e registrare perché sono
   state scelte o escluse; rendere questa selezione visibile all'operatore.
4. Benchmark di compiti reali ripetuti con/senza skill: modifica codice con test,
   conversione documento, sito con asset, ripresa di una missione e gestione di
   errore/rifiuto. Il giudizio deriva dagli artefatti, non dalla prosa del modello.
5. Preparare una release riproducibile e ripulita, poi trasferire la base 1.05
   nel nuovo remoto come concordato, dopo i commit di Cips.

La raccomandazione è concentrare la 1.05 sull'affidabilità dell'esecuzione e sulla
visibilità delle prove, prima di ampliare ulteriormente il catalogo.


## Intervento successivo — 2026-10-07

Corrette le cinque riproduzioni: allowlist al dispatch, propagazione dei criteri,
verifica senza fallback positivo, budget effettivi e review legata alla versione
registrata degli artifact. Aggiunti contesto Invocation, filtro azioni del
verifier, evidenze strutturate, contabilizzazione dei tentativi e checkpoint.
Contratti e limiti aggiornati in `docs/mission-control.md`; regressioni in
`tests/test_agent_runtime_regressions.py`.

Validazione: 143 test mirati e 28 subtest; suite completa 1963 passati,
17 saltati, 755 subtest, due fallimenti Anna già presenti (scene 50/30 e
manifest runtime divergente). Frontend: 26 test Node passati.
La selezione comune delle skill, i benchmark reali e la riproducibilità della
release restano aperti. Le verifiche con modelli e tool simulati non dimostrano
ancora un miglioramento misurato dell'autocoding su missioni reali.

### Primo hook di selezione implementato

`shared/skill_hooks.py` collega la selezione deterministica al loop condiviso
chat/worker missione: solo skill approvate, hash corrente, ruolo compatibile,
capacità offerte, al massimo due skill e contesto entro 24000 byte. Motivazioni
visibili nel log `skill`. Riferimento diet103 importato a commit fisso con MIT;
regole e limiti in `docs/skill-hooks.md`. Restano aperti selezione semantica,
caricamento progressivo, copertura dei percorsi senza tool e benchmark reali.
