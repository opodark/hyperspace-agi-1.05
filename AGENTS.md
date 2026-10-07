# Agenti su questo repository

Questo repository è lavorato da più agenti sulla **stessa macchina e sullo
stesso filesystem**. Per non sovrascriversi a vicenda usano due file in radice:

- **AGENTS.md** (questo file) — chi lavora qui, le regole di base e dove sta la
  verità.
- **[AGENT-LOG.md](AGENT-LOG.md)** — i messaggi fra agenti, in ordine
  cronologico. Si **aggiunge in fondo**: quello che ha scritto un altro non si
  riscrive e non si cancella.

I rimandi che gli agenti caricano da soli stanno in radice: `CLAUDE.md` per
Claude Code, `.clinerules/agent-protocol.md` per Cline. Gli altri agenti vanno
indirizzati qui dall'utente.

## Chi scrive qui

| Agente | Dove lavora | Nota |
|---|---|---|
| **Cline** (VS Code) | `/Users/opo/hyperspace-agi-1.04` | lavora dentro il repository |
| **Codex** | `/Users/opo/hyperspace-agi-1.04` | infrastruttura (Control Plane, Registry, bridge); ha risposto al primo passaggio di consegne |
| **Claude Code** | `/Users/opo/Downloads/tiktok_editor` | cantiere storico dell'editor, memory ferma al 2026-09-09; non ha ancora risposto |

## Regole

1. **La verità è il repository.** `/Users/opo/Downloads/tiktok_editor` non è un
   repository git ed è fermo al 2026-09-09 15:1x: da lì serve solo `.venv/`, il
   runtime Python dell'editor (Python 3.14.5, con numpy, librosa, numba,
   gradio). Lo sviluppo attivo sta in `integrations/tiktok_editor/app/`, che è
   più avanti di circa un mese (2026-10-05 23:5x) e contiene file che la cartella
   `Downloads` non ha: `autoedit/guides.py`, `autoedit/person_layers.py`,
   `autoedit/person_mask.swift`, `autoedit/scene_vision.py`, `draft.py` e due
   preset.
2. **Un messaggio per intervento.** Prima di iniziare leggere `AGENT-LOG.md`;
   quando si finisce aggiungere un blocco in fondo con data, agente e cosa è
   stato fatto o cosa si chiede.
3. **Nessun commit e nessun push senza conferma esplicita dell'utente.** Il
   lavoro non committato su `main` non è poco: al 2026-10-06 sono 60 file
   modificati, 116 non tracciati e 10 cancellati — questi ultimi **già in stage**
   (`obsidian/*`, `memory-graph/*`, i `.json` di `data/obsidian-vault/.obsidian/`).
   Obsidian è uscito dallo stack: la memoria è `hermes` (`docs/hermes.md`), il
   grafo del repository è `graphify` (`docs/graphify.md`).
4. **Nessun segreto nei file.** I file `.env` tracciati sono già in storia: non
   aggiungere valori reali, nemmeno in `.env.example`.
5. **I test girano nel `.venv` del repository**, non in quello dell'editor.

## Verificare

```bash
# suite del repository (interprete del repo): è quella che deve restare verde
.venv/bin/python -m pytest tests/ -q

# i test del reel anche nel loro ambiente: il .venv del repo NON ha numpy/librosa,
# quello dell'editor sì (unittest è già dentro i file, quindi basta l'interprete)
/Users/opo/Downloads/tiktok_editor/.venv/bin/python tests/test_tiktok_editor_integration.py
/Users/opo/Downloads/tiktok_editor/.venv/bin/python tests/test_reel_person_layers.py
/Users/opo/Downloads/tiktok_editor/.venv/bin/python tests/test_reel_webui_vision.py
```

Al 2026-10-06, con il `.venv` del repository:
**5 failed, 1811 passed, 17 skipped** (54,7s). I tre moduli del reel
(`tests/test_reel_person_layers.py`, `tests/test_reel_webui_vision.py`,
`tests/test_tiktok_editor_integration.py`) portano una guardia che li fa
**saltare** — non fallire — quando mancano numpy/librosa: lo skip vale solo per
quelle dipendenze opzionali, un import rotto per altre ragioni continua a farsi
sentire, e la raccolta della suite non viene più annullata. Con l'interprete
dell'editor gli stessi moduli eseguono davvero e passano (3 + 5 + 8 test).

I 5 fallimenti che restano sono **fuori dal perimetro reel** e sono debito della
working tree, non del codice dell'editor:

| Test | Causa |
|---|---|
| `tests/test_licensing.py` (3) | i 5 file cancellati e non committati sono ancora nell'indice: il test li enumera e non li trova |
| `tests/test_prova_colori_anna.py` (1) | le scene della serie Anna non tornano a posto (50 != 30) |
| `tests/test_comfyui_modelli_sd15.py` (1) | il documento runtime di Anna dichiara soglie diverse dal manifest (0.55 != 0.45) |

Il dettaglio, le risposte di Codex e le domande aperte sono in
[AGENT-LOG.md](AGENT-LOG.md).

## Stato noto al 2026-10-06

Il Reel Editor è descritto in [docs/tiktok-editor.md](docs/tiktok-editor.md), con
le ricette in [docs/reel-forge-recipes.md](docs/reel-forge-recipes.md). Servizio
locale in `scripts/tiktok_editor_service.py` (loopback `127.0.0.1:7860`),
avvio con `integrations/tiktok_editor/com.hyperspace.tiktok-editor.plist` e con
`scripts/start-all-macos.sh`. Nessuno di questi file è ancora tracciato da git.
