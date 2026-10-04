# graphify — knowledge graph del repository (strumento di sviluppo)

`graphify` trasforma il monorepo (codice, documentazione, PDF) in un grafo di
conoscenza locale, interrogabile da un coding agent. Serve a orientarsi in una
codebase grande — `control-plane/main.py` da solo supera le 8.800 righe — e a
rispondere a domande tipo "chi chiama cosa", "quali moduli sono collegati",
"spiegami questo simbolo" senza rileggere tutto a mano.

E' uno **strumento di sviluppo**, non un servizio di runtime:

- non compare in `docker-compose.yml` (nessun container e nessuna porta aperta
  sullo stack: l'MCP di default parla su stdio, non su TCP);
- gira sul checkout, installato a versione pinnata con `uv tool` o `pipx`;
- i suoi artefatti finiscono in `graphify-out/`, che e' in `.gitignore`.

## Cosa produce

I due passi sono `extract` (AST locale sul codice, più il passaggio semantico su
documenti e immagini) e `cluster`/`cluster-only` (community detection, report e
viste). Tutto finisce in `graphify-out/`, il percorso di default non committato:

| Artefatto | Contenuto |
|---|---|
| `graph.json` | il grafo (nodi, archi, tipi), macchina-leggibile |
| `graph.html` | vista interattiva del grafo nel browser |
| `GRAPH_REPORT.md` | sintesi leggibile: hub, cluster, segnali, freschezza |
| `manifest.json` | indice incrementale: cosa e' gia' stato estratto |
| `cache/` | cache SHA-256 per file: i rilanci toccano solo il cambiato |
| `.graphify_analysis.json` | analisi interna (cluster, score) usata dai comandi |
| `wiki/` | pagine per community e god node (con `--wiki`) |

Altri export su richiesta: `--svg`, `--graphml`, `--neo4j` (Cypher), `export
callflow-html`. `graph.html` carica `vis-network` da una CDN (con hash SRI):
il grafo resta locale, ma per *guardarlo* nel browser serve la rete.

L'analisi del **codice** usa tree-sitter in locale: nessuna rete, nessuna chiave.
Solo l'estrazione dalla **documentazione** (`.md`, `.txt`, `.pdf`) e dalle
**immagini** passa da un LLM, da puntare su un backend locale (Ollama) così
nessun contenuto del repository esce dalla macchina.

## Installazione

Richiede Python ≥ 3.10 (verificato anche su 3.14). Il comando è `graphify`, ma
il pacchetto su PyPI si chiama **`graphifyy`** (doppia y: gli altri `graphify*`
su PyPI non sono lo stesso progetto). Per estrarre i documenti con un modello
locale serve l'extra `[ollama]`:

```bash
# consigliato: isolato, nel PATH, con versione pinnata
uv tool install "graphifyy[ollama]==0.9.74"

# alternativa equivalente
pipx install "graphifyy[ollama]==0.9.74"
```

Pinnare la versione è deliberato: `graphify` è mantenuto attivamente e giovane —
`0.1.14` esisteva ad aprile 2026, la `0.9.74` è di ottobre — e un aggiornamento
può cambiare output o flag. Un venv dedicato resta possibile, ma `uv tool` e
`pipx` isolano le dipendenze e mettono `graphify` nel PATH.

Senza `[ollama]` la pipeline funziona lo stesso, ma l'estrazione dei documenti
non ha il backend locale a cui appoggiarsi.

## Uso

C'è un wrapper in `scripts/graphify.sh` che verifica l'installazione, si
posiziona sulla root del repository e inoltra ogni argomento senza riscriverlo.
I comandi sono quelli di `graphify --help`, che resta la fonte autorevole:

```bash
./scripts/graphify.sh                                # solo codice: AST locale, zero chiavi
./scripts/graphify.sh extract . --backend ollama     # codice + documenti, tutto in locale
./scripts/graphify.sh cluster-only .                 # GRAPH_REPORT.md + graph.html
./scripts/graphify.sh god-nodes --top 15             # hub architetturali
./scripts/graphify.sh explain "v1_chat_completions"  # call-graph di un simbolo
./scripts/graphify.sh query "..." --budget 800       # BFS sul grafo
./scripts/graphify.sh path "A" "B"                   # cammino più breve tra due nodi
./scripts/graphify.sh affected "X"                   # chi dipende da X
./scripts/graphify.sh update .                       # re-indicizza il codice dopo un refactor
./scripts/graphify.sh --mcp                          # server MCP (stdio) per il coding agent
./scripts/graphify.sh watch .                        # ricostruzione a ogni salvataggio
```

`graphify` **nudo stampa la guida**: la pipeline si esegue con un sottocomando
(`extract`, `update`, `cluster-only`). Il wrapper, senza argomenti, esegue
`extract . --code-only`, cioè la variante che per costruzione non contatta
niente.

Per registrare la skill dentro l'assistente c'è `graphify install` (rileva la
piattaforma — Claude Code e altri — e copia il file di skill nella sua
configurazione): qui la via principale resta la CLI più `--mcp`.

Per l'aggiornamento automatico c'è `graphify hook install`: installa un hook
`post-commit` e un merge driver che unisce `graph.json` senza conflitti, e
incorpora il percorso dell'interprete, quindi funziona anche da client GUI dove
`~/.local/bin` non è nel PATH. Dopo un `git pull` conviene
`./scripts/graphify.sh update .` (re-indicizza il codice, nessun costo LLM). È
comunque un'aggiunta **locale** al clone: gli hook non si committano.

Il server MCP (`--mcp`) è **stdio**, come si aspetta un client MCP dentro l'IDE.
Esiste anche un transport HTTP (`python -m graphify.serve … --transport http`),
ma senza `--host 0.0.0.0` resta loopback-only: qui non si espone.

## Backend LLM: resta locale

L'estrazione da documenti e immagini è l'unico passo che può contattare un LLM.
Senza `--backend` graphify **auto-rileva** in quest'ordine: Gemini → Kimi →
Claude → OpenAI → DeepSeek → Azure → Bedrock → Ollama. La conseguenza pratica è
che basta una chiave esportata nell'ambiente perché i documenti del repository
finiscano a quel provider — e Gemini ha la precedenza. Qui quindi il backend si
passa sempre a mano:

```bash
./scripts/graphify.sh extract . --backend ollama   # codice + documenti, in locale
./scripts/graphify.sh extract . --code-only        # nessun LLM affatto
```

`OLLAMA_BASE_URL` (default `http://localhost:11434`) e `OLLAMA_MODEL`
(auto-rilevata) puntano all'Ollama locale. Il backend Ollama stampa un avviso se
`OLLAMA_API_KEY` non è impostata — basta un valore qualsiasi
(`OLLAMA_API_KEY=local`) per zittirlo: l'endpoint è già quello locale
(`http://localhost:11434/v1`), non un servizio remoto. Il naming delle community
via LLM su 397 community è invece la parte lenta con un modello 4B: se serve solo
la struttura, `cluster-only . --no-label` non chiama nessun modello.

Tre avvertenze, misurate sul campo con Ollama.

**Primo: `GRAPHIFY_OLLAMA_NUM_CTX` non ha effetto.** graphify parla all'endpoint
OpenAI-compatibile `/v1`, e lì manda il contesto dentro
`extra_body {"options": {"num_ctx": N}}`. `options` è un campo **nativo** di Ollama:
su `/v1` viene ignorato. Verificato chiedendo lo stesso modello due volte e
leggendo il contesto effettivo in `ollama ps`:

| Richiesta | `CONTEXT` in `ollama ps` |
|---|---|
| `POST /v1/chat/completions` con `options.num_ctx=4096` | 2048 (default del modello) |
| `POST /api/chat` (nativo) con `options.num_ctx=8192` | 8192 |

Senza un pin effettivo un 8B ricade su `OLLAMA_CONTEXT_LENGTH` (65536 nell'app
macOS): offload su CPU (`ollama ps`: 16 GB, `31%/69% CPU/GPU`) e un chunk da 3,5k
token che non chiude in 1200 s (2 chunk su 3 chiusi con `Request timed out`,
riprodotto). **Rimedio**: agganciare il contesto al **modello** invece che alla
richiesta. Il `PARAMETER num_ctx` di un Modelfile viene onorato dove `options` no:

```bash
printf 'FROM granite3.3:8b\nPARAMETER num_ctx 8192\n' > /tmp/Modelfile.graphify
ollama create granite3.3-g8k -f /tmp/Modelfile.graphify
```

Da lì `ollama ps` mostra 6,4 GB e **100% GPU**, e i chunk si chiudono.

**Secondo: `GRAPHIFY_DISABLE_THINKING=1` non zittisce il ragionamento su Ollama.**
L'endpoint `/v1` accetta la forma che graphify invia
(`{"thinking":{"type":"disabled"}}`), ma il modello continua a scrivere la traccia
nel `content`. Con Ollama il flag va **lasciato spento** e conviene scegliere un
modello che non ragiona affatto (vedi sotto).

**Terzo: il tetto di output non arriva.** Il default di `max_completion_tokens` per
Ollama è 8192 e `/v1` **non applica** il campo che graphify invia: l'output resta
di fatto illimitato finché il modello non si ferma da solo (misurati 9.916 token
prodotti con un tetto richiesto di 4000, `GRAPHIFY_MAX_OUTPUT_TOKENS=4000`). Il
freno che conta è `--token-budget`, che decide quanto testo entra in ogni chunk.
Per un modello locale conviene sempre `--max-concurrency 1`.

## Risultato su questo repository (03/10/2026)

Trial `extract . --code-only` — solo AST, nessun LLM, nessuna chiave — sul codice
del monorepo:

- **6570 nodi · 12492 archi · 397 community** in `graphify-out/`;
- provenienza dichiarata: 97% `EXTRACTED`, 3% `INFERRED` (confidenza media 0.88);
- `.gitignore` rispettato (quindi `data/`, `.venv/` e `reports/` restano fuori) e
  i file `.env.*` saltati d'ufficio come potenzialmente sensibili;
- il report registra il commit di partenza (*Graph Freshness*), così si vede
  quando il grafo è stantio.

Gli hub individuati sono reali e non ovvi — `push_log()` (101 archi), `workflow()`,
`vetrina_dal_documento()`, `nuovo_job()`, `ConnectorManager`,
`v1_chat_completions()` — e `explain "v1_chat_completions"` restituisce il
call-graph con `file:riga`, tipo di arco e provenienza: è il modo più rapido di
leggere `control-plane/main.py` senza aprirlo.

Limite misurato, da non nascondere: `query` in linguaggio naturale fa BFS sulle
parole del testo e su un repo eterogeneo tira dentro community poco pertinenti
(per esempio `tests/`). È utile su domande centrate su un simbolo, meno su
domande aperte; escludere `tests/` con un `.graphifyignore` (stessa sintassi di
`.gitignore`, che viene **fusa** con essa) rende i risultati più netti.

Il passaggio **semantico** via Ollama è stato validato il 03/10/2026. Il modello
che ha passato la prova è **`granite3.3:8b`** (4,9 GB), scelto perché **non
ragiona**: nessuna traccia di thinking da pagare in token, nessun budget bruciato
prima della risposta. Il contesto va agganciato al modello (vedi sopra), quindi si
parte da un modello derivato e si esegue su tutto il repository, escludendo i dati
utente (`data/` è quasi tre quarti dei markdown del repo, ma è il vault della
memoria, non documentazione):

```bash
printf 'FROM granite3.3:8b\nPARAMETER num_ctx 8192\n' > /tmp/Modelfile.graphify
ollama create granite3.3-g8k -f /tmp/Modelfile.graphify

OLLAMA_MODEL=granite3.3-g8k OLLAMA_API_KEY=local GRAPHIFY_OUT=graphify-out-docs \
  ./scripts/graphify.sh extract . --backend ollama --model granite3.3-g8k \
    --max-concurrency 1 --token-budget 6000 --api-timeout 1200 \
    --exclude 'data/**' --exclude 'vendor/**'
```

`--exclude` (ripetibile, sintassi `.gitignore`) restringe il corpus ed è
**persistito** nella config dell'output dir: il rilancio senza flag riusa la stessa
lista. Qui il pass semantico passa da 489 file markdown a **90 file** (89 documenti
e 1 immagine; i soli 54 `.md` fuori da `data/` e `vendor/` pesano 612 KB).

`--token-budget 6000` tiene ogni chunk sotto gli 8192 token del contesto: con il
default di 60000 il prompt verrebbe troncato in silenzio da Ollama, e i nodi
uscirebbero da un testo mutilato. È un batch lungo, da seguire con `ollama ps` (che
deve restare al 100% GPU) e con il log; la cache semantica è incrementale, quindi
un'interruzione non butta il lavoro fatto e il rilancio riparte dai documenti non
ancora processati. Su questo corpus sono **55 chunk** e il primo si chiude in
**~6 minuti**: sono **~5-6 ore** in tutto, da lanciare la sera.

Sul prompt reale di graphify un documento da 16 KB (4.067 token in ingresso)
produce **14 nodi e 14 archi in 2:26**, con `done_reason: stop` (nessun
troncamento), **zero token di ragionamento**, nessun blocco markdown da ripulire,
**0 ID fuori formato** `[a-z0-9_]` e **2.352 token di output — 0,58× l'input**,
contro le 2,5× dei modelli che ragionano. Il throughput misurato è **~18 tok/s** e
il modello resta al **100% GPU** con il contesto agganciato a 8192.

In pipeline, su tre documenti reali (`16.100 token in / 7.442 out`, ~14 minuti), il
grafo esce pulito: 13 nodi, 5 archi, 8 community. Restano due limiti da dichiarare,
perché non si risolvono con un flag.

Il primo limite è la **resa**: dei 3 file dispatchati solo 2 producono nodi.
`persona.md` parla di `shared/persona.py` e il modello attribuisce i nodi a quel
file invece che al documento; graphify scarta poi ogni item la cui `source_file`
non sta fra i file dispatchati in quella run (`scope_semantic_result`, #2926). La
guardia è corretta — impedisce a una run parziale di sostituire il contributo
precedente di un file — ma il costo è che un documento molto "di codice" non entra
nel grafo. Non dipende dalla configurazione: succedeva anche con `qwen3:8b` (2 file
su 5), e non c'è un flag per rimediare (`--prompt-file` riguarda solo
`cache-check`, non il prompt di estrazione).

Il secondo è il **formato degli ID**: sui nodi di codice il modello tiene
l'estensione nello stem (`shared_persona_py_system_block`) dove la specifica vuole
`shared_persona_system_block`. Il charset è rispettato, la corrispondenza con gli
ID del pass AST no: i nodi dei documenti non si agganciano a quelli del codice.

Restano fuori dalla raccomandazione due famiglie. I modelli che **ragionano**
(`qwen3:8b`, `huihui_ai/gemma-4-abliterated:12b`) funzionano — l'esempio minimo dà
6 nodi e 3 community in 2:46, un sottoinsieme di 5 documenti dà 42 nodi e 40 archi
— ma generano a ~10 tok/s e oltre 2× l'input in output: quel sottoinsieme è costato
~19 minuti e l'intero `docs/` sarebbe un job da **8-12 ore**. I modelli **piccoli**
invece non reggono il compito: il 4B *vision-instruct* risponde
`{"nodes":[],"edges":[],"hyperedges":[],"partial":true}` (0 nodi) e i 2B/4B
*reasoning* esauriscono il budget nel ragionamento (`finish_reason=length`,
`content` vuoto) e finiscono "hollow".

In sintesi: la parte **validata e sempre utile** resta il **grafo del codice**
(`extract . --code-only`, zero LLM, zero chiavi). L'estrazione dai documenti ora
funziona bene in locale con un modello ≥8B che non ragiona: è un batch notturno,
con resa ~2/3 dei file e i due limiti qui sopra. L'impronta in memoria conta più
della CPU — questa è una macchina da 16 GB di memoria unificata (MacBook Air M5)
che con lo stack attivo ne lascia liberi ~2-5 GiB, e un 8B con il contesto a 8192
ne chiede ~6,4 GB: prima di lanciare conviene fermare lo stack. L'output finisce in
`graphify-out-docs/` (ignorato da git) senza toccare il `graphify-out/` del codice.

Non usare `--obsidian`: quel flag genera l'output in formato vault Obsidian, che
qui non serve.

## Perché non sostituisce la memoria runtime

`graphify` mappa il repository — codice e documenti — in modo statico e su
richiesta. La memoria di HyperSpace è un'altra cosa: record runtime nello schema
`hyperspace.memory.v1`, sempre attivi e già consultabili da `/dashboard`,
`/diario`, `/conversations` e dalla Infra-UI via SSE. I due non si sovrappongono,
quindi `graphify` non sostituisce e non duplica la memoria: è lo strumento con
cui un agent **legge la codebase**, non con cui la piattaforma **ricorda**.

## Licenza

`graphify` (pacchetto PyPI `graphifyy`) è distribuito sotto licenza
**Apache-2.0** — non MIT: il dato è nel `license_expression` del metadata PyPI
della 0.9.74, confermato dal file `LICENSE` del repository
[Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify). Non viene
ridistribuito con i container; l'elenco delle dipendenze e delle loro licenze
(nessuna copyleft) è in [`THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md).
