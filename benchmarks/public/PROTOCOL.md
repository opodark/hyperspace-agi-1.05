# Protocollo del confronto pubblico

Frase che possiamo difendere: **«Il sistema HyperSpace, con questi componenti, ottiene X; costo e dati restano in casa.»**
Non: «HyperSpace batte Claude/Gemini».

## Regole
1. Stesso harness per tutti: EleutherAI lm-evaluation-harness, versione fissata e registrata nel manifesto.
2. Benchmark a punteggio automatico, nessun modello giudice: ifeval, gsm8k, gpqa_diamond_cot_zeroshot, mmlu_pro, bbh_cot_zeroshot.
3. Temperatura 0, seed fisso, stesso tetto di token. Il livello di ragionamento (medium per i modelli di frontiera) va dichiarato per ogni target in `declared_reasoning`, dopo averlo verificato nella documentazione del produttore.
4. Il sistema e il modello nudo sono righe separate (`system` / `model`). Un sistema con review gate o più tentativi non è alla pari di un modello singolo: la tabella lo dice.
5. Previsioni scritte prima (`predictions-2026-11-03.json`), margine di pareggio ±3 punti, un solo giro dichiarato. I benchmark persi si pubblicano.
6. Si pubblica `runs/<data>/`: manifesto e risposte grezze di ogni target, più `REPORT.md`. Mai le chiavi.

## Da fare prima del giro vero
- Compilare i `FILL_ME` di `targets.example.json` (copiato in `targets.json`): ID esatti dei modelli, parametro di sforzo "medium" di Gemini e di Claude, nodo e quantizzazione del modello nudo.
- Installare lm_eval in un venv a parte (con gli extra `api`; GPQA richiede l'accesso al dataset su Hugging Face) e impostare `HS_LM_EVAL`.
- Impostare `GEMINI_API_KEY` e `ANTHROPIC_API_KEY` nell'ambiente.
- Un giro di fumo con `--limit 20` per controllare che le metriche si leggano; non è un risultato.

## Fase 2 (non ancora fatta)
Codice (EvalPlus, LiveCodeBench) e tool calling (BFCL) usano harness propri; da verificare come puntarli a un endpoint compatibile prima di inserirli.

### GAIA (agenti generali) — verificato 2026-11-13, dal codice della Space
- Classifica pubblica Hugging Face (`gaia-benchmark/leaderboard`) che accetta un **agente/sistema**, non solo un modello: campi nome agente, famiglia del modello, esempio di system prompt, URL, organizzazione, email.
- Invio: JSONL con `task_id` e `model_answer`, sullo split **test** (301 domande: 93/159/49 per livello; risposte private). La validazione (165 domande, pubblica) serve a mettere a punto il runner.
- Vincoli: account HF con più di 60 giorni, un invio al giorno, stessa coppia modello/organizzazione una sola volta, un 100% pieno viene rifiutato.
- Dataset gated: le domande non si ripubblicano. Le risposte grezze in `runs/` contengono solo `task_id` e risposta, mai il testo delle domande.
- Runner: `scripts/gaia_bench.py` (tool del client `fetch_url` e, con `--allow-python`, `run_python`; allegati non ancora gestiti). Regole lette dal codice della Space: possono cambiare, ricontrollarle prima dell'invio.

### Artificial Analysis
Valutazioni proprie e pesanti (Terminal-Bench, HLE-Diamond, ecc.), nessun processo di inserimento pubblico (solo modulo di contatto, «custom benchmarking»). Non rieseguibile da noi; da riconsiderare solo con un endpoint pubblico stabile.

## Condizioni applicate (aggiornato 2026-11-03)
- **Stop sequences:** lo stop dei task (`Question:` ecc.) è sostituito da `until=</s>` per TUTTI i target. Motivo verificato: sul percorso HyperSpace lo stop agisce anche sui token di ragionamento e taglia la generazione prima della risposta (Flint: 78 caratteri di ragionamento con stop, `#### 18` senza).
- **Sistema HyperSpace:** richieste con `surface=workbench` e `X-Hyperspace-Tools: off` (niente persona né tool nativi); compressione dei prompt spenta (default); revisore LAYA = LFM 2.5 24B via `HYPERSPACE_CHAT_REVIEW_MODEL`; generatore `flint:latest`. Il codice del control plane sull'OMEN è al commit indicato nel manifesto.
- **Gemini:** passa da `scripts/public_bench_proxy.py`, che toglie solo il campo `seed` (l'endpoint di Google lo rifiuta). Va avviato prima del giro. Il parametro `reasoning_effort=medium` non è ancora confermato come accettato.
- **Log:** i log di esecuzione di lm_eval possono contenere la chiave nell'intestazione degli errori. Si pubblicano solo manifesto e risposte, mai i log.
