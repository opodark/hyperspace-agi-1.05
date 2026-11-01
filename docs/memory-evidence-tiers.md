# Livelli di evidenza della memoria — proposta di design

Stato (2026-11-01): **fasi E0, E1, E2, E3 ed E4 implementate**. L'intero ciclo
dei quattro livelli di evidenza e dei tre ruoli (proponente, contraddittore,
verificatore) è ora attivo e testato. Scrivono `evidence` la promozione dei
sogni (`sourced`/`plausible`), l'azione `refute` del lifecycle (`refuted`),
il motore di ricerca notturno (`plausible`), la promozione prototipi (`verified`
se con test esercitanti convalidati, `plausible` se non esercitati), e il
contraddittore distribuito (`critique` allegata senza alzare il livello).

## Da dove viene l'idea

Il progetto di ricerca [ACS Framework](https://tensorrent.github.io/ACS-Framework/)
(Bradley Wallace, ricercatore indipendente) classifica ogni affermazione in
quattro livelli: verificata dalla suite di test, dimostrata in un paper,
verificata solo numericamente, falsificata. Le falsificate restano in un
registro append-only e **un livello non sale mai in automatico**.

Da ACS prendiamo solo il metodo. Il materiale è sotto licenza SIP v1.1, che
vieta l'uso commerciale senza licenza scritta: qui non si copia testo né codice,
e lo schema sotto è scritto da zero con nomi e significati nostri.

## Cosa esiste già

| Pezzo | Dove | Cosa risolve |
|---|---|---|
| Livelli di retention `operative` / `project` / `persistent` | `shared/memory_schema.py`, `memory/schema/` | **quanto a lungo** vive un record |
| Stati `active` / `quarantined` / `revoked` | stesso schema, `scripts/hermes_memory_bridge.py::lifecycle` | se un record è **visibile** al retrieval |
| Ciclo dei sogni `hypothesis → promoted / rejected / revoked` | `node/dreaming.py`, `docs/dreams.md` | separa ipotesi generate da note accettate |
| Promozione prototipi R&D in `shared/` con pytest e rollback | `scripts/diagnostics/promote_research_prototype.py` | non rompere la suite quando entra codice nuovo |

## Il buco

Nessuno di questi campi dice **quanto è affidabile** un record, né **perché**.

- `dream_insight` è `persistent` e quindi "autorevole" solo perché una persona
  l'ha promosso: la promozione registra chi e perché, non quale prova la regge.
- Un sogno rifiutato resta in `dreams.jsonl` (ultime 100 righe), ma nessun
  agente lo consulta prima di riproporre la stessa ipotesi: `docs/dreams.md`
  lo lascia come decisione aperta ("come evitare che memorie quasi duplicate
  generino cicli ripetitivi").
- Il motore di ricerca notturno (`shared/agi_research_engine.py`) scrive dossier
  senza alcun livello. Al 2026-11-01 in `data/research/agi_deep_dives.jsonl`
  ci sono 346 dossier: **162 hanno `findings_summary` vuoto** e 144 hanno un
  prototipo che supera solo il controllo sintattico AST. Tutti alimentano
  `AGI_SWARM_SYNTHESIS.md` e i "semi" dei sogni.
- `data/research/promotions.jsonl` (71 promozioni) registra classi e file, ma
  non quali test sono girati, con che esito, né se quei test esercitano davvero
  il modulo promosso: la suite lanciata è sempre la stessa lista fissa.

## Proposta: il campo `evidence`

Un campo opzionale nell'involucro `hyperspace.memory.v1`. Lo schema JSON ha già
`additionalProperties: true`, quindi è un'aggiunta compatibile: i record vecchi
restano validi e la versione non cambia.

```json
{
  "evidence": {
    "tier": "verified",
    "basis": [
      {"kind": "check", "command": "pytest tests/test_x.py::test_y",
       "exit_code": 0, "output_sha256": "…", "at": "2026-11-01T10:00:00Z"}
    ],
    "assigned_by": "promote_research_prototype",
    "history": [
      {"from": "plausible", "to": "verified", "at": "…", "by": "…", "reason": "…"}
    ]
  }
}
```

### I quattro livelli

| `tier` | Significato | Prova minima in `basis` |
|---|---|---|
| `verified` | riprodotto da un controllo deterministico | `check`: comando, esito, hash dell'output, data; rieseguibile |
| `sourced` | sostenuto da una fonte controllabile | `source`: URL o ID di memoria, con hash del contenuto citato; oppure `review`: decisione umana attribuita **con** fonti |
| `plausible` | prodotto da un modello, non verificato | nessuna; è il default di ogni output di modello |
| `refuted` | smentito | `refutation`: motivo e prova (check fallito, fonte contraria, decisione motivata) |

Un record senza `evidence` è trattato come `plausible`. Così tutta la memoria
esistente resta leggibile senza migrazione, e prudente per default.

### Regole

1. **Nessuna promozione automatica.** Un livello sale solo se arriva una prova
   del tipo richiesto. La confidenza autodichiarata dal modello (`confidence`
   nei sogni) non è una prova e non sposta il livello.
2. **Il verificatore di `verified` non è un modello.** È un test, uno script,
   un hash che torna. Un altro LLM che "conferma" produce al massimo una critica
   da allegare, non una prova. È lo stesso principio già scritto in `AGENTS.md`
   per Mission Control: validatori indipendenti dal giudizio del modello.
3. **Scendere è automatico, salire no.** Se un controllo che reggeva un record
   `verified` fallisce, il record torna `plausible` e va in `quarantined` finché
   qualcuno non decide. `refuted` richiede sempre un motivo esplicito.
4. **`refuted` non è `revoked`.** `revoked` nasconde un record sbagliato da
   inserire. `refuted` conserva un'ipotesi che si è rivelata falsa, perché è
   **utile saperlo**: resta fuori dal retrieval normale ma risponde a una query
   dedicata di controllo contraddizioni. Non si cancella mai.
5. **Il livello viaggia con il contenuto.** Il retrieval restituisce sempre
   `tier` insieme al testo; i prompt degli agenti devono citarlo e non
   presentare un `plausible` come fatto.
6. **Nessun livello si propaga a valle.** Una nota derivata da fonti `verified`
   parte comunque `plausible`: la derivazione è opera del modello.

## Tre ruoli, non tre modelli

Il ciclo che GPT ha suggerito (uno propone, uno contraddice, uno verifica) si
appoggia su pezzi che ci sono già:

| Ruolo | Chi | Cosa produce |
|---|---|---|
| Proponente | worker dei sogni, motore di ricerca, agenti in chat | record `plausible` |
| Contraddittore | un modello su **un altro nodo** (la mesh) | critiche allegate al record; non cambia il livello |
| Verificatore | test, script, controllo fonti, persona | la prova che alza o abbassa il livello |

Il contraddittore su un altro nodo risponde anche a una decisione aperta di
`docs/dreams.md` ("se e quando usare più nodi per criticare una stessa ipotesi"),
con lo stesso vincolo: riceve l'ipotesi, non le memorie sorgenti.

## Garbage collector delle allucinazioni (Implementato ✅)

Il termine non c'era ancora nel repository; con questi livelli è implementato come modulo dedicato (`shared/memory_gc.py`) e diagnostica CLI (`scripts/diagnostics/memory_garbage_collector.py`):

- **Scadenza:** i record `plausible` di retention `project`, mai consultati (`access_count == 0`) e
  senza prove dopo N giorni (default: 14 giorni), vanno in `quarantined` (non cancellati).
- **Controllo contro il registro `refuted`:** una nuova ipotesi molto simile a
  una già smentita (stessa sovrapposizione di token che usa
  `shared/dream_evaluation.py` per la novità: `token_overlap >= 0.8` contro `refuted` di Hermes e `dream_rejected.jsonl`) viene marcata e messa in quarantena, non arrivando in
  inbox come nuova. Questo chiude i cicli ripetitivi dei sogni.
- **Ricontrollo:** i record `verified` vengono rieseguiti a campione; un esito
  diverso (exit_code != 0) li fa scendere a `plausible` (regola 3: 'Un esito diverso li fa scendere') tramite l'azione `downgrade` del bridge.
- **Invarianti ferree:** MAI cancellare `refuted`, MAI alzare livelli, MAI toccare `MEMORY.md` o il
  profilo utente (`USER.md`), MAI toccare memorie persistenti (`dream_insight`, `vault_note`).
- **Control Plane & CLI:** esposto endpoint `POST /memory/gc` in `control-plane/cp/memoria.py` e comando CLI `scripts/diagnostics/memory_garbage_collector.py` con opzioni `--apply`, `--dry-run`, `--days`, `--threshold` e `--json`.

## Ordine di implementazione proposto

| Fase | Contenuto | Accettazione |
|---|---|---|
| E0 ✅ | Campo `evidence` in `shared/memory_schema.py` e nello schema JSON; `validate_entry` controlla livello e prova minima; `evidence_tier` legge il livello effettivo; il tipo `critique` allega critiche senza valere come prova | test: un `verified` senza `check` riuscito è invalido; una `critique` non soddisfa nessun livello; un record senza `evidence` resta valido ed è `plausible` |
| E1 ✅ | `HermesMemoryClient.query`/`entries` e il ripiego sul mirror (`_memory_search_local`) etichettano ogni voce con `evidence_tier`; `omega_query` mostra il livello all'agente (`[tipo · livello]`) e la sua descrizione chiede di citarlo; `DreamJournal.review(..., sources=[...])` scrive `sourced` solo con fonti citate dal revisore, altrimenti `plausible`; la dashboard chiede le fonti alla promozione | un `dream_insight` promosso senza fonti non risulta mai `verified` né `sourced`; un livello dichiarato senza prova valida viene letto come `plausible` |
| E2 ✅ | **Memoria**: azione `refute` in `POST /memory/lifecycle` (bridge: nuova revisione con `refutation`, motivo obbligatorio, record ancora attivo e leggibile; pulsante "Smentisci" in `infra-ui`); `omega_query` esclude i `refuted` e li restituisce solo con `evidence="refuted"`. **Sogni**: registro append-only `dream_rejected.jsonl` (un rifiuto umano resta anche quando `dreams.jsonl` ruota a 100 righe; `reopen` toglie il blocco aggiungendo un evento); un nuovo sogno con sovrapposizione ≥ 0,8 a uno rifiutato viene salvato già `rejected` da `dedup`, con la gemella citata e `reopen` ancora possibile | un'ipotesi quasi uguale a una rifiutata non torna in inbox come nuova; un `refuted` senza motivo non vale come smentita |
| E3 ✅ | Motore di ricerca: dossier con `findings_summary` vuoto esclusi dalla sintesi; `promotions.jsonl` registra comando, esito e hash dei test che toccano il modulo | una promozione senza test che importano il modulo resta `plausible` |
| E4 ✅ | Contraddittore su un secondo nodo | le critiche sono allegate e attribuite; nessun livello cambia per effetto di un modello |
| GC ✅ | Garbage collector delle allucinazioni (`shared/memory_gc.py`, `scripts/diagnostics/memory_garbage_collector.py`, azione `downgrade` nel bridge, endpoint `POST /memory/gc`) | scadenza plausible inattivi > 14d, blocco collisioni con refuted, ricontrollo check verified con declassamento se falliscono, invarianti di sicurezza garantite |

Ogni fase è piccola, reversibile e non tocca dati esistenti: un record vecchio
resta valido in tutte.

## Decisioni aperte

- Rifiutare un sogno lo toglie dall'inbox delle gemelle ma **non** lo rende
  `refuted`: un rifiuto può voler dire "falso" come "poco utile". Marcare
  `refuted` resta un'azione esplicita sulla memoria.
- Nel bridge `revoke` funziona anche su un record `refuted`: la regola "mai
  cancellare `refuted`" vale per i job automatici, non per una pulizia
  dell'operatore (es. dati personali).

- Chi può assegnare `sourced` a una review: solo l'operatore, o anche una
  policy locale che controlla che le fonti esistano e che gli hash tornino.
- Valore di N per la scadenza dei `plausible`.
- Se il registro `refuted` va condiviso fra nodi (D5 dei sogni) o resta locale.
- Se ACS stesso va letto come fonte esterna (skill in sola lettura su
  `claims.json`, verifica isolata su OMEN): rimandato, non necessario per questo
  design.
