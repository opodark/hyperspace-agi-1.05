# Contratto di memoria — `hyperspace.memory.v1`

Questo documento definisce il formato comune di un **record di memoria** in
HyperSpace, cioè l'unità scambiata fra nodi, control-plane e backend Hermes.
L'implementazione in-process è in [`shared/memory_schema.py`](../../shared/memory_schema.py);
lo schema JSON è in [`hyperspace.memory.v1.schema.json`](hyperspace.memory.v1.schema.json).

## Perché un contratto

Prima del contratto i record usavano nomi di campo ad hoc (`ts`/`timestamp`,
`type`/`event_type`, `content`/`prompt`/`response`), rendendo fragile ogni
lettura incrociata. Il contratto fissa un involucro unico e dichiara a quale
**livello di retention** appartiene ogni record, così la garbage collection e il
retrieval possono distinguere ciò che scade da ciò che resta.

## Involucro (envelope)

Un record normalizzato contiene almeno:

| Campo | Tipo | Obbligatorio | Significato |
|---|---|---|---|
| `schema` | string | sì | sempre `hyperspace.memory.v1` |
| `id` | string | sì | identità stabile (esplicita o hash del contenuto) |
| `ts` | string | no | timestamp ISO-8601 UTC (alias legacy: `timestamp`, `created_at`) |
| `type` | string | sì | tipo di record (vedi sotto) |
| `content` | string | sì | contenuto ricercabile |
| `source` | string | sì | origine (`mesh`, `dream`, nodo, plugin, bridge esterni…) |
| `surface` | string | no | mezzo/contesto di provenienza (`openwebui`, `web-node`, `terminal`, `channel:cam4`, …) |
| `node_id` | string | no | nodo di provenienza |
| `model` | string | no | modello che ha prodotto il record |
| `task_id` | string | no | task/sessione di appartenenza |
| `status` | string | sì | `active`, `quarantined`, `revoked` |
| `priority` | int | no | 1–5, default 3 |
| `access_count` | int | no | contatore, default 0 |
| `retention` | string | no | override esplicito del livello (vedi sotto) |
| `evidence` | object | no | livello di evidenza e prove (vedi sotto); assente = `plausible` |

Il contenuto ricercabile è derivato in quest'ordine: `content`, poi `summary`,
poi `detail`, infine la coppia `prompt`+`response`.

## Tipi di record

`memory` (interazione runtime), `note` (nota), `decision` (decisione),
`task_state` (stato di task), `artifact` (metadati artefatto), `dream`
(ipotesi non attendibile), `dream_insight` (nota promossa), `vault_note`
(nota esterna ingerita da omega).

## Livelli di retention

Il livello può essere dichiarato esplicitamente con `retention`; altrimenti
deriva dal tipo:

- **operative** — memoria breve soggetta a TTL (`memory`, `task_state`):
  interazioni runtime, scadono e vengono potate.
- **project** — memoria di progetto/sessione (`dream`, `note`, `decision`,
  `artifact`): vive oltre il singolo task ma non è ancora conoscenza promossa.
- **persistent** — conoscenza long-term autorevole (`dream_insight`,
  `vault_note`): note promosse o curate, source of truth in Hermes.

La classificazione è esposta da `classify_retention` /
`is_persistent` / `is_operative` / `is_project`.

## Livelli di evidenza

La retention dice **quanto a lungo** vive un record; `evidence` dice **quanto è
affidabile e perché**. Il design completo è in
[`docs/memory-evidence-tiers.md`](../../docs/memory-evidence-tiers.md).

| `evidence.tier` | Prova minima richiesta in `evidence.basis` |
|---|---|
| `verified` | un `check` riuscito: `command`, `exit_code` = 0, `output_sha256`, `at` |
| `sourced` | un `source` (`ref`, `content_sha256`) oppure una `review` (`by`, `sources`) |
| `plausible` | nessuna: default di ogni output di modello e dei record senza `evidence` |
| `refuted` | una `refutation` con `reason` |

Il tipo `critique` (`by`, `content`) allega la critica di un altro agente senza
soddisfare alcun livello: un modello non alza mai il livello di un record. Il
livello effettivo si legge con `evidence_tier`; un livello sconosciuto vale
`plausible`.

## Validazione

`validate_entry` restituisce l'elenco delle violazioni (vuoto = valido):
contenuto assente, `type`/`status`/`retention` sconosciuti, timestamp non
interpretabile, `priority` fuori intervallo, blocco `evidence` con livello
sconosciuto o senza la prova che il livello richiede (`validate_evidence`).

## Collegamento con il resto del sistema

- `scripts/hermes_memory_bridge.py` scrive gli entry con
  `display_metadata.schema = "hyperspace.memory.v1"` e usa la stessa identità
  stabile (`id` o hash SHA-256 del contenuto canonico).
- Le ipotesi Dream restano in `dreams.jsonl`; la promozione produce un
  `dream_insight` persistente in Hermes (vedi `docs/dreams.md`).
- La valutazione dei sogni (D3) legge questi record tramite
  `shared/dream_evaluation.py`.
