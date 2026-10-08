# Prova autonoma Mission Control: presentazione PDF HyperSpace 1.05

Data: 2026-10-07. Obiettivo: far leggere a Mission Control la documentazione del
repository e ottenere da un coder, in Code Sandbox, una presentazione PDF con
sorgente riproducibile e verifiche. Il PDF precedente
`docs/hyperspace-1.05-presentation.pdf` è una bozza preparata manualmente e non
costituisce un risultato di questa prova.

## Esito

**Fallito: nessuna missione ha prodotto un PDF.** Cinque missioni distinte
sono registrate in `data/missions.jsonl`; i task, i verdetti e gli errori si
possono consultare nella dashboard Mission Control o tramite
`GET /missions/<id>` con token operatore. Nessuna review è stata approvata e
nessun artifact è stato applicato al checkout.

| Missione | Piano | Esito verificato |
| --- | --- | --- |
| `mission-77c3302ed8ef4b15` | planner del modello | `repo-analyst` cerca documenti locali senza tool di lettura del repository; task `failed`, 0 artifact |
| `mission-7ca54eff7a664b9f` | planner del modello, istruito a scegliere solo coder | ignora il vincolo, antepone `repo-analyst`, poi salta i task coder; 0 artifact |
| `mission-204ddd9fb9974947` | piano operatore esplicito, un coder | fallisce `create`: 6 directory workspace occupano il limite di 6; 0 artifact |
| `mission-6c5e7b0699e94513` | piano operatore esplicito, un coder | crea un workspace, poi ripete letture rifiutate; nessuna scrittura né PDF |
| `mission-ba70ae37ace64df1` | piano operatore, istruzioni su path relativi e meno call | crea un workspace, legge almeno due file, subisce una lettura rifiutata e chiude senza scrivere PDF |

La tabella contiene cinque missioni: due con planner autonomo e tre con piano
operatore. In tutti i casi l'esecuzione è stata tracciata dal controller; i
piani operatore isolano la capacità del worker e **non** dimostrano autonomia del
planner.

## Evidenze indipendenti

- L'immagine del runner contiene `README.md`, `VISION.md`, `ROADMAP.md` e
  `docs/mission-control.md` in `/seed`. La dichiarazione del secondo piano secondo
  cui i documenti non esistono era falsa: il ruolo scelto non poteva leggerli.
- Con la capienza iniziale `SANDBOX_MAX_WORKSPACES=6`, il volume conteneva sei
  directory, quattro con metadata di vecchi lavori Dream e due incomplete. Non
  sono state toccate.
- Il solo runner sandbox è stato ricreato con capienza temporanea 8, mantenendo
  il volume. La modifica non è persistita in `.env`: un futuro recreate senza
  override torna al limite di 6.
- Il workspace della quarta missione ha avuto una `create` riuscita, seguita da
  circa quattordici `read` fallite. Il quinto ha avuto `create`, `list` e due
  `read` riuscite, una `read` fallita. Il runner non registra `write` o `run`
  per nessuna delle due. Il controllo diff ha trovato zero file modificati.
- Una lettura diretta con il contratto `path="README.md"` nello stesso workspace
  ha funzionato. Il problema non è la mancanza del file; serve osservabilità
  sugli argomenti di tool e feedback di errore utilizzabile dal modello.
- I due workspace creati da questa prova, entrambi con diff vuoto, sono stati
  scartati. I vecchi workspace Dream sono rimasti intatti.

## Correzioni prima del nuovo tentativo

1. Il planner deve conoscere le capability effettive dei ruoli e rifiutare un
   piano che assegna lettura di file locali al `repo-analyst` senza sandbox.
   Per obiettivi basati sui file, la scelta corretta oggi è `coder` con
   `code_sandbox` o un vero tool read-only del repository da aggiungere.
2. Il controller deve conservare per i task falliti le evidenze strutturate dei
   tool e distinguere un file inesistente, un path assoluto rifiutato, un limite
   di lettura e un budget di iterazioni esaurito. I log generici non devono
   includere contenuti dei documenti o segreti.
3. La quota dei workspace deve avere TTL, pulizia controllata o headroom. Un
   `status` healthy non basta quando `create` è impossibile.
4. Per una presentazione di molte fonti servono letture aggregate e un
   generatore PDF disponibile nel runner. L'immagine attuale non include
   ReportLab; il task richiedeva quindi un generatore PDF senza dipendenze.
5. La nuova prova va misurata con gate indipendenti: file PDF presente,
   signature `%PDF`, conteggio pagine, testo/fonti verificabili e diff del
   workspace, prima della review umana di grafica e contenuti.

Non si può qualificare come “presentazione autonoma” un PDF prodotto fuori da
questo percorso. Il prossimo tentativo deve produrre un workspace reviewable e
un PDF effettivo oppure restare `failed` con motivo tracciato.

## Addendum — secondo ciclo del 7 ottobre, dopo confronto con LangGraph/CrewAI/n8n

**Esito: ancora nessun PDF autonomo.** Questa volta sono stati corretti ostacoli
misurabili prima di lanciare i task. Il planner ora conosce la distinzione fra
ruoli che possono leggere il repository e ruoli senza quel tool; `POST /missions`
accetta `allowed_roles` e il server lo impone anche se il modello propone altro.
Nel runner offline sono presenti ReportLab 4.5.1 e pypdf 6.19.0. La capienza è
stata alzata **solo per il container di questa prova** da 6 a 10 workspace,
senza cancellare i sei precedenti. Il runner dà ora un hint per path non validi
ed emette in audit solo `path_kind` ed `error_code`, senza nomi o contenuti.

| Missione | Esito osservato |
| --- | --- |
| `mission-2076baeeebcd48bc` | Planner produce quattro task ma assegna a `verifier` l'esecuzione dello script: piano incompatibile con i permessi; annullata prima di consumare i task. |
| `mission-d66248862fac4d8b` | Con `allowed_roles=["coder"]` e un solo task il planner sceglie coder, crea un workspace e fa una lettura riuscita; poi ripete letture rifiutate, senza scrivere file. Annullata. |
| `mission-3899ba2fc6994b18` | Terzo tentativo ristretto a due fonti. Docker Desktop cessa di rispondere durante la pianificazione; Control Plane non è più raggiungibile. Missione cancellata nello store per impedirne la ripresa automatica. Nessun task e nessun artifact. |

Durante l'ultimo blocco il Mac aveva circa 5,2 GB liberi su disco, 17,4 GB di
swap usati e ~140 MB di pagine libere. Il backend Docker non era più presente
fra i processi; Ollama rispondeva ancora. Questi dati indicano forte pressione
di risorse, ma **non provano da soli** la causa esatta dell'uscita di Docker.
Il modello Granite caricato per la prova è stato scaricato dalla RAM; il
runtime Bonsai del collega non è stato toccato. Non è stato approvato, applicato,
committato o pushato alcun artifact.

Verifica del codice: 72 test mirati su Mission Control e Sandbox passano,
`ruff --select F821` passa. La priorità successiva resta una prova su macchina
con memoria/disco liberi. Prima di rilanciarla, usare l'audit `path_kind` per
identificare la forma delle letture sbagliate e impedire retry identici; poi
verificare il PDF indipendentemente con firma, pypdf, pagine, testo e fonti.
