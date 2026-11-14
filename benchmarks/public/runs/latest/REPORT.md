# Confronto pubblico — sistema HyperSpace vs modelli di frontiera

> **ATTENZIONE: giro parziale (--limit) per granite_3_3_8b_bare, hyperspace_flint_lfm_laya. NON e' un risultato.**

| Target | Ruolo | Componenti | Ragionamento dichiarato |
|---|---|---|---|
| granite_3_3_8b_bare | model | OMEN RTX 3070 — granite3.3:8b nudo (nessun review gate, nessun tool, inferenza diretta su GPU) | nessun ragionamento/thinking; modello nudo |
| hyperspace_flint_lfm_laya | system | Control Plane OMEN :8085 — generatore flint:latest, revisore LFM 2.5 24B, porta LAYA; surface=workbench, tool off | ragionamento deciso dal CP (think off salvo modelli solo-thinking); nessun budget esterno |

## Punteggi (% — piu' alto e' meglio)

| Benchmark | granite_3_3_8b_bare | hyperspace_flint_lfm_laya |
|---|---|---|
| ifeval | 100.0 | 100.0 |
| gsm8k | 100.0 | 100.0 |

## Come rifare la prova

- **granite_3_3_8b_bare**: lm_eval `0.4.13`, commit `5ae2741e14`, seed 1234, temperatura 0. Comando in `granite_3_3_8b_bare/manifest.json`, risposte grezze in `granite_3_3_8b_bare/`.
- **hyperspace_flint_lfm_laya**: lm_eval `0.4.13`, commit `5ae2741e14`, seed 1234, temperatura 0. Comando in `hyperspace_flint_lfm_laya/manifest.json`, risposte grezze in `hyperspace_flint_lfm_laya/`.

Il sistema HyperSpace include componenti che un modello singolo non ha; la riga `model` (se presente) separa il contributo del modello da quello del sistema.
