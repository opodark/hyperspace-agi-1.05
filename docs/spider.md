# La ragnatela sulle pagine (Web Crawlers)

Ogni pagina della UI di HyperSpace ha una **ragnatela procedurale che cammina sul
testo**: le zampe si piantano sulle parole vere (`caretRangeFromPoint` +
`Intl.Segmenter`), il contatto fa "glitchare" la parola per un istante — contorni,
monospace, rotazioni, barre di seta, fili, fantasmi — e poi la parola torna com'era.
Non è un effetto *della* pagina: è un **overlay** sopra di essa, e la pagina non
viene toccata nemmeno per un frame.

La vuoi sempre addosso: la ragnatela entra in ogni pagina servita (control-plane e
infra-ui), insegue il mouse, e se la spegni resta spenta mentre navighi.

## Da dove viene (e perché NON è nel repo)

Il codice è [`web-crawlers` di cyohei9907](https://github.com/cyohei9907/web-crawlers)
— "A procedural spider that walks on the DOM", JS×CSS puri, niente build, niente
dipendenze. Il file che usiamo è `extension/src/spider.js` dell'upstream, quello
dell'estensione: un IIFE autonomo che espone
`window.__webCrawler.{start, stop, set, stats}` e non usa nessuna API `chrome.*`,
quindi si carica in una pagina normale come qualunque `<script>`.

`data/control-plane/vendor/web-crawlers/PROVENANCE.txt` tiene commit, data e
SHA-256 del file copiato. La copia in
`data/control-plane/vendor/web-crawlers/spider.js` è **byte per byte** quella
dell'autore.

**Perché in `data/control-plane/` e non in `control-plane/vendor/`.** L'upstream
non ha un file di licenza (`LICENSE`/`COPYING` non esistono): su GitHub, senza
licenza, il default è *tutti i diritti riservati*. Il repo non può assorbirlo
nemmeno volendo: `tests/test_licensing.py` enumera ogni sorgente versionato con
`git ls-files` e pretende l'header `SPDX-License-Identifier: Apache-2.0` su
`.py .js .mjs .sh .ps1`. Un `spider.js` di terzi tracciato lo farebbe fallire;
mettergli il **nostro** header sarebbe una dichiarazione falsa di licenza. È una
dipendenza **locale, non ridistribuita**.

E perché proprio quella cartella: il container del control-plane **non** gira
dalla repo, gira da `/app` (copia dell'immagine) e vede una sola cartella di dati,
il volume `./data/control-plane -> /app/data`. Quindi `control-plane/` non è un
posto possibile (finisce nell'immagine), e `data/` non basta (il resto di `data/`
dentro il container non esiste). `data/control-plane/vendor/web-crawlers/` è
l'unico posto che è insieme fuori da git, visibile a runtime e aggiornabile senza
ricostruire l'immagine. Il `.gitignore` generale (`**/data/`) lo copre già: c'è
anche una riga esplicita, che serve a chi legge. Il control-plane lo trova con
`_spider_vendor_path()`, che prova `/app/data/...` e `../data/control-plane/...`
(vedi `tests/test_spider.py`).

Il *comando* invece è nostro: `control-plane/spider/bootstrap.js`, Apache-2.0,
non contiene una riga del codice upstream — carica la ragnatela e la pilota
dall'esterno. Se un giorno l'autore concede una licenza esplicita, il file può
traslocare in `control-plane/vendor/web-crawlers/` con una voce in
`THIRD-PARTY-NOTICES.md`.

## Cosa è stato agganciato

| pezzo | dove | cosa fa |
|---|---|---|
| le 10 pagine | `control-plane/*.html` (8) e `infra-ui/*.html` (2) | una riga sola: `<script defer src="/spider/bootstrap.js"></script>` prima di `</head>` |
| contratto + bootstrap | `GET /spider/bootstrap.js` (CP) | scrive `window.__HSPIDER__={enabled, source, search}` e poi il bootstrap; `Cache-Control: no-store` |
| la ragnatela | `GET /spider/spider.js` (CP) | serve il file vendorizzato da `data/control-plane/vendor/web-crawlers/`; **404 con un commento JS** se non c'è |
| la stessa riga sul bridge | `GET /spider/{bootstrap,spider}.js` (`infra-ui/server.py`) | inoltra al CP: la bridge non tiene una copia, e la riga nelle pagine resta identica |

Un solo asset per pagina (`/spider/bootstrap.js`) invece di due: la config e il
codice arrivano insieme, niente seconda richiesta, e c'è **una riga sola** da
mettere in ogni `<head>`.

Una nota che vale la pena sapere prima di cercare un bug: **il container non gira
dalla repo.** Il CP monta la repo solo per il `.env`, e per il resto gira da `/app`,
cioè da una copia dell'immagine costruita da `control-plane/Dockerfile` — che copia
le 8 HTML e (da questo intervento) `control-plane/spider/` in `./spider`. Quindi
cambiare le pagine o il bootstrap richiede **un rebuild**, non un riavvio:
`docker compose build control-plane bridge && docker compose up -d control-plane bridge`
(la bridge ha la stessa struttura: `infra-ui/Dockerfile` copia `server.py` e le 2
HTML). Il file di terzi invece **no**: sta nel volume `./data/control-plane`, quindi
si aggiorna a caldo, senza ricostruire niente.

## Cosa fa, esattamente

`control-plane/spider/bootstrap.js`, quattro passi:

1. **Legge il contratto.** Se `window.__HSPIDER__.enabled === false` esce subito:
   nessun overlay, nessuna richiesta, pagina identica.
2. **Carica la ragnatela** da `/spider/spider.js` (stessa origine) e la avvia con
   le opzioni ricordate. Se il file non c'è, `onerror` **non fa niente**: la
   console mostra il 404 della rotta — che è l'informazione giusta — e la pagina
   resta quella di prima. Un clone senza il vendor non si accorge di nulla.
3. **Ricorda lo stato** in `sessionStorage` (chiave `hspider.state`): accesa/spenta,
   `size`, `density`, `autoRead`. È questo che rende "mi segue nella navigazione":
   ogni pagina successiva la fa rinascere com'era.
4. **(se `search` c'è) Fa da assistente alla ricerca.** Raccoglie la parola sotto
   il corpo del ragno e la offre in un chip; il chip e `Alt+Shift+F` aprono la
   ricerca su SearXNG. Dettagli nella sezione qui sotto.

### Cosa sopravvive alla navigazione, e cosa no

Sopravvive lo **stato**. Non la posizione delle zampe: l'upstream `start()` fa
entrare la ragnatela dalla parte alta della vista e non espone nessuna API per
dirle dove comparire. Dopo qualche frame sulla nuova pagina è di nuovo addosso al
cursore — `mousemove` la attira — quindi in pratica la ritrovi subito; il punto è
che *non* è una continuazione geometrica, ed è meglio dirlo che farlo sembrare.
Per una continuazione esatta servirebbe una patch al file upstream, che oggi non
facciamo: resta quello dell'autore.

`sessionStorage`, non `localStorage`: "ovunque nella navigazione" significa in
questa scheda. Un'altra scheda è un'altra ragnatela, che è il comportamento meno
sorprendente.

## Comandi

| come | effetto |
|---|---|
| `Alt+Shift+S` | accende / spegne (lo stesso tasto dell'estensione upstream) |
| `Alt+Shift+F` (o un clic sul chip) | manda in ricerca la parola sotto il ragno: apre SearXNG in una scheda nuova |
| `?spider=off` / `?spider=on` nell'URL | salta o impone la ragnatela per quella vista, e lo ricorda |
| `window.__hspider.toggle()/start()/stop()/stats()/state/word()/cerca()` | dalla console |
| `SPIDER_ENABLED=false` in `.env` (o dalla tab Setup → *Interfaccia (UI)*) | la toglie da tutte le pagine alla ricarica successiva: la rotta risponde `enabled:false` |
| `SPIDER_SEARCH=false` in `.env` (o dalla tab Setup → *Interfaccia (UI)*) | lascia la ragnatela ma toglie l'assistente: niente chip, niente ricerca |

## Il ragno come assistente alla ricerca

Il ragno cammina sulle **parole vere** della pagina. Da qui l'idea: mentre cammina,
la parola che ha sotto diventa una cosa su cui si può cercare. Acceso
(`SPIDER_SEARCH=true`, l'interruttore è nella stessa sezione della tab Setup della
ragnatela), compare un piccolo **chip** vicino al ragno con la parola che sta
calpestando; `Alt+Shift+F` — o un clic sul chip — apre quella parola su **SearXNG**
in una scheda nuova. Sulla pagina della bridge funziona uguale: è la stessa riga
di bootstrap.

**Perché è tutto qui e non tocca il codice di terzi.** La ragnatela *non espone la
parola su cui cammina*: la sua API pubblica è solo
`{running, start, stop, set, stats, options}`. Quindi la parola la ricaviamo **noi**,
con la stessa API che usa lei — `document.caretRangeFromPoint` per il nodo sotto un
punto e `Intl.Segmenter` per i confini di parola — campionando il punto del suo
corpo: `stats().spider.vx/vy` sono normalizzati sulla vista (`(posizione - scroll)
/ innerWidth|Height`), quindi il pixel è `(vx*innerWidth, vy*innerHeight)`. Così il
file di terzi resta quello dell'autore, aggiornabile con il comando qui sotto, e
nessuno deve forkarlo.

**L'URL lo compone il browser** (`location.hostname` + `SEARXNG_PORT`, dal
contratto `/spider/bootstrap.js`): SearXNG sta su un'altra porta dello stesso host,
quindi vale sia da `localhost` sia da un altro dispositivo della rete.

**Il chip è un elemento NOSTRO**, creato a mano (`createElement`, niente `innerHTML`)
in uno shadow root appeso a `<html>`: la pagina non si tocca — la stessa regola di
tutto il resto del bootstrap, ed è ciò che `tests/test_spider.py` controlla. Il chip
non ruba i clic della pagina (`stopPropagation`): un clic su una parola resta un
clic per la pagina, la ricerca parte solo dal chip o da `Alt+Shift+F`. Il sondaggio
gira piano (una volta ogni 150 ms), non a ogni frame.

### Accessibilità

Se il sistema chiede `prefers-reduced-motion: reduce`, la ragnatela **non parte da
sola**: un animale che cammina sul testo è esattamente ciò che quella preferenza
chiede di non far iniziare senza una scelta. Chi la vuole la accende una volta
(Alt+Shift+S) e da lì in poi è ricordata, anche con quella preferenza attiva. Con
`SPIDER_ENABLED=false` la preferenza non conta: non c'è proprio.

## Limiti dichiarati

- **Le altre origini non si toccano.** Lo `desktop.html` apre anche servizi su
  porte/domini diversi (Reel Editor, Open WebUI, SearXNG, Grafana…): uno script
  in-pagina non può entrare lì, e non proviamo a farlo. Per quelle l'unico
  strumento giusto è l'**estensione Chrome dell'upstream** ("release the spider on
  any web page"), che è un'installazione del browser, non una modifica al repo.
- **`web-node/*.html` e `control-plane/vendor/panel-foundry/`** sono superfici
  separate (nodo web e editor Comic Builder vendorizzato): fuori da questo
  intervento. Il test di guardia copre `control-plane/*.html` e `infra-ui/*.html`.
- **Costo**: una `requestAnimationFrame` continua per pagina, con la camera che
  legge il DOM. È l'upstream; per spegnerla del tutto vale `SPIDER_ENABLED=false`.
  L'assistente aggiunge un sondaggio ogni 150 ms, e solo mentre il ragno cammina.
- **Il chip non c'è sempre.** Il corpo del ragno a volte è sullo spazio bianco fra
  due parole (o su un'immagine, o su un pulsante): lì non c'è niente da raccogliere
  e il chip non compare. Raccoglie *la parola quando ci si posa sopra*, non a ogni
  istante. E il nostro `wordAt` duplica ~40 righe di `caretRangeFromPoint` +
  `Intl.Segmenter`: se l'upstream cambia la sua idea di "parola", le due possono
  divergere — è il prezzo di non forkare il file di terzi.

## Come si aggiorna la ragnatela

```bash
git clone --depth 1 https://github.com/cyohei9907/web-crawlers /tmp/web-crawlers
cp /tmp/web-crawlers/extension/src/spider.js data/control-plane/vendor/web-crawlers/spider.js
shasum -a 256 data/control-plane/vendor/web-crawlers/spider.js   # aggiornare PROVENANCE.txt
```

Poi una ricarica: né il bootstrap né il file vendorizzato sono cacheati
(`no-store` / `max_age=0`).

## Test

- `tests/test_spider.py` — guardia "nessuna pagina dimenticata" (tutte le pagine
  servite devono avere l'include **una volta sola**), le due rotte del CP, il
  proxy del bridge, il kill switch (`_spider_enabled` eseguita davvero, non solo
  letta), **l'interruttore dell'assistente** (`_spider_search_enabled` /
  `_spider_search` eseguite davvero: spento non manda niente, e senza ragnatela
  non esiste), l'impronta SHA-256 del file vendorizzato e il vincolo che **non deve
  essere tracciato da git**.
- `tests/spider.test.cjs` (`node --test`, come gli altri `tests/*.test.cjs`) —
  il bootstrap eseguito in una `vm`: parte quando è abilitato, non parte con
  `enabled:false`, non parte con `prefers-reduced-motion` senza una scelta
  esplicita, ricorda accesa/spenta, `Alt+Shift+S` commuta, e senza ragnatela non
  lancia e non lascia `window.__hspider`. Per l'assistente: il chip raccoglie la
  parola sotto il corpo del ragno, `Alt+Shift+F` (e il clic sul chip) aprono
  l'URL giusto su SearXNG, senza parola il chip non compare — e senza `search`
  nel contratto l'assistente non esiste (nessun sondaggio).
- `docs/spider.md` è la fonte di verità di questo file di test: se una delle due
  cambia, l'altra è un bug.

