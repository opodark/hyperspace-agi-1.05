// SPDX-License-Identifier: Apache-2.0
// La pagina della superficie REA (scripts/rea_surface.py) nel suo comportamento:
// cosa dice quando REA non c'e', cosa mostra per ogni operazione esposta, cosa
// rifiuta prima di chiamare il server, e come rende le tre corsie del report.
// Il sorgente Python contiene la pagina: qui si estrae lo <script> e lo si
// esegue in un contesto finto, con `document`, `fetch` e `FormData` al posto dei
// veri. Quello che si difende e' cosa la pagina dice, non il rendering del
// browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sorgente = fs.readFileSync(
  path.join(__dirname, '..', 'scripts', 'rea_surface.py'), 'utf8');
const pagina = sorgente.match(/_PAGE = r"""([\s\S]*?)"""/)[1];
const script = pagina.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script); // il blocco inline deve restare JS valido

// Le 13 operazioni esposte, come le manda /api/status: 5 statiche e 8 che
// aprono un motore nativo (2 con provider facoltativo, 6 con provider
// obbligatorio). Una sola non vuole un file e non vuole nemmeno un provider.
function op(id, comando, titolo, target, argomento, provider, esecuzione) {
  return {id, comando, titolo, target, argomento,
    argomento_tipo: argomento ? 'testo' : null, provider, esecuzione,
    descrizione: 'descrizione finta di ' + id};
}
const OPS = [
  op('doctor', 'doctor', 'Readiness (doctor)', 'nessuno', null, 'opzionale', 'statica'),
  op('providers', 'providers', 'Provider disponibili', 'nessuno', null, 'non-serve', 'statica'),
  op('capabilities', 'capabilities', 'Capacità', 'nessuno', null, 'non-serve', 'statica'),
  op('analyze', 'analyze', 'Panoramica del target', 'file', null, 'opzionale', 'motore'),
  op('inspect', 'inspect', 'Ispezione del target', 'file', null, 'opzionale', 'motore'),
  op('analyze-js', 'analyze-javascript-application', 'Applicazione JavaScript',
    'file', null, 'non-serve', 'statica'),
  op('inspect-artifact', 'inspect-artifact', 'Contenitore / artefatto',
    'file', null, 'non-serve', 'statica'),
  op('function', 'function', 'Dossier di una funzione', 'file',
    'nome della funzione', 'obbligatorio', 'motore'),
  op('decompile', 'decompile', 'Decompila un indirizzo', 'file',
    'indirizzo (0x...)', 'obbligatorio', 'motore'),
  op('xrefs', 'xrefs', 'Riferimenti a un indirizzo', 'file',
    'indirizzo (0x...)', 'obbligatorio', 'motore'),
  op('instructions', 'instructions', 'Istruzioni di un indirizzo', 'file',
    'indirizzo (0x...)', 'obbligatorio', 'motore'),
  op('search', 'search', 'Cerca testo nel target', 'file',
    'testo da cercare', 'obbligatorio', 'motore'),
  op('trace', 'trace', 'Percorso verso un testo', 'file',
    'testo da cercare', 'obbligatorio', 'motore'),
];

const INSTALL = [
  {nome: 'globale', comando: 'npm install --global rea-agents',
    nota: 'mette `rea` nel PATH'},
  {nome: 'una tantum', comando: 'npx -y rea-agents@latest analyze <target> --json',
    nota: 'nessuna installazione'},
  {nome: 'prova isolata',
    comando: 'npm install --prefix /private/tmp/rea-pilot rea-agents --ignore-scripts',
    nota: 'come la prova del 5 ottobre 2026'},
];

function stato({found = true} = {}) {
  return {
    workspace: '/tmp/finto/data/rea',
    jobs: {n: 2, bytes: 4096},
    rea: found
      ? {found: true, path: '/usr/local/bin/rea', source: 'PATH',
        version: {testo: '3.2.1-finto', errore: null}}
      : {found: false, path: null, source: null,
        error: "`rea` non e' nel PATH e REA_BIN non e' impostato"},
    ops: OPS, providers: ['hopper', 'ghidra', 'ida'],
    artifacts: ['report.json', 'job.json', 'stdout.json', 'stderr.log'],
    install: INSTALL,
    limits: {timeout_s: 180, upload_mb: 512, output_mb: 8, workspace_mb: 4096,
      queued_max: 3},
    note: 'Nessuna vulnerabilità è confermata qui.',
  };
}

// I due lavori dell'elenco: uno chiuso e uno in corso (che fa partire il
// polling). Il target e' quello che il server ha copiato nella workspace.
const COMPLETO = {
  id: 'abcdef012345', op: 'search', titolo: 'Cerca testo nel target',
  status: 'completed', esito: 'completato', created_at: '2026-10-09T10:00:00Z',
  started_at: '2026-10-09T10:00:01Z', finished_at: '2026-10-09T10:00:09Z',
  exit_code: 0, duration_s: 8.1, argomento: 'configurazione', provider: 'hopper',
  target: {nome: 'demo.exe', bytes: 20480, sha256: 'a'.repeat(64)},
};
const IN_CORSO = Object.assign({}, COMPLETO, {
  id: 'beefbeefbeef', status: 'running', esito: null, exit_code: null,
  duration_s: null, created_at: '2026-10-09T09:00:00Z',
  target: {nome: 'altro.dll', bytes: 1024, sha256: 'b'.repeat(64)},
});

const REPORT = {
  osservato: {
    esito: 'completato', exit_code: 0, durata_s: 8.1, stdout_bytes: 1234,
    stderr_bytes: 12, troncato: {stdout: false, stderr: false},
    comando: ['rea', 'search', 'demo.exe', 'configurazione', '--provider',
      'hopper', '--json'],
  },
  riferito: {
    nota: 'Riduzione del documento REA: chiavi, conteggi e digest.',
    chiavi: [{chiave: 'matches', tipo: 'list', n: 3},
      {chiave: 'coverage', tipo: 'dict', n: null}],
    collezioni: [{per: 'strings', n: 3}],
    digest: [{per: 'binary_sha256', valore: 'deadbeef'}],
  },
  progresso: [{fase: 'providers', messaggio: 'inizializzazione'},
    {fase: 'search', file: 'demo.exe'}],
  limiti: ['Il target non è stato eseguito.',
    'Nessuna vulnerabilità è confermata qui.'],
};

const DETTAGLIO = {job: COMPLETO, report: REPORT};

function elemento() {
  return {innerHTML: '', textContent: '', className: '', value: '', style: {},
    files: [], disabled: false, placeholder: '', children: [],
    appendChild(n) { this.children.push(n); },
    getAttribute() { return null; }, setAttribute() {},
    querySelector() { return null; }, querySelectorAll() { return []; }};
}

function contesto({statoServito = stato(), jobs = [COMPLETO, IN_CORSO],
  dettagli = {}, creazione = {status: 202, corpo: {job: COMPLETO}},
  rompi = false} = {}) {
  const nodi = {}, chiamate = [], timer = [];
  function risposta(status, corpo) {
    return {ok: status < 400, status, json: async () => corpo};
  }
  const FormDataFinto = class {
    constructor() { this.voci = []; }
    append(chiave, valore, nome) { this.voci.push([chiave, valore, nome]); }
  };
  const ctx = {
    document: {getElementById(id) { return nodi[id] || (nodi[id] = elemento()); }},
    FormData: FormDataFinto,
    fetch: async (url, opzioni) => {
      chiamate.push({url, opzioni});
      if (rompi) throw new Error('fetch failed');
      if (url.startsWith('/api/status')) return risposta(200, statoServito);
      if (opzioni && opzioni.method === 'POST') {
        return risposta(creazione.status, creazione.corpo);
      }
      if (url.startsWith('/api/jobs/')) {
        const id = decodeURIComponent(url.slice('/api/jobs/'.length));
        const d = dettagli[id]
          || {job: jobs.find((j) => j.id === id) || null, report: null};
        if (!d.job) return risposta(404, {error: 'lavoro non trovato'});
        return risposta(200, d);
      }
      if (url.startsWith('/api/jobs')) {
        return risposta(200, {jobs, workspace: '/tmp/finto/data/rea'});
      }
      return risposta(404, {error: 'rotta finta'});
    },
    // Nessun timer parte davvero: i callback finiscono in `timer` e li esegue
    // il test, cosi' una pagina che va in polling non appende il processo.
    setTimeout: (fn, ms) => { timer.push({fn, ms}); return timer.length; },
    clearTimeout: () => {},
    console,
  };
  vm.createContext(ctx);
  vm.runInContext(script, ctx); // esegue anche il boot() finale
  return {ctx, nodi, chiamate, timer};
}

const attendi = () => new Promise((r) => setTimeout(r, 20));
const post = (chiamate) => chiamate.filter(
  (c) => c.opzioni && c.opzioni.method === 'POST');
const file = (nome) => ({name: nome, size: 20480});


(async () => {
  // 1. REA trovato: pill verde, banner che dice cosa questa superficie non fa
  //    e con quali limiti (timeout e un lavoro alla volta)
  const c = contesto();
  await attendi();
  assert.equal(c.nodi.pillRea.textContent, 'rea 3.2.1-finto · PATH');
  assert.equal(c.nodi.pillRea.className, 'pill ok');
  assert.equal(c.nodi.banner.className, 'ok');
  assert.equal(c.nodi.banner.style.display, 'block');
  assert.match(c.nodi.banner.innerHTML, /Solo analisi statica/);
  assert.match(c.nodi.banner.innerHTML, /\/usr\/local\/bin\/rea/);
  assert.match(c.nodi.banner.innerHTML, /timeout 180 s/);

  // 2. l'elenco delle operazioni esposte: 13 voci, 8 dichiarano che aprono un
  //    motore nativo, 3 non vogliono file
  assert.equal((c.nodi.opsList.innerHTML.match(/class="op"/g) || []).length, 13);
  assert.equal((c.nodi.opsList.innerHTML
    .match(/il provider lo scegli tu/g) || []).length, 6);
  assert.equal((c.nodi.opsList.innerHTML
    .match(/provider facoltativo/g) || []).length, 2);
  assert.equal((c.nodi.opsList.innerHTML.match(/senza file/g) || []).length, 3);
  assert.match(c.nodi.opsList.innerHTML, /rea analyze-javascript-application/);
  assert.match(c.nodi.foot.innerHTML, /data\/rea|finto\/data\/rea/);
  assert.match(c.nodi.foot.innerHTML, /lavori 2 \(4096 B\)/);

  // 3. le tendine: la prima operazione e' il doctor, i provider sono quelli
  //    dichiarati dal server piu' la voce "automatico"
  assert.equal((c.nodi.opSel.innerHTML.match(/<option/g) || []).length, 13);
  assert.equal(c.nodi.opSel.value, 'doctor');
  assert.equal((c.nodi.provSel.innerHTML.match(/<option/g) || []).length, 4);
  assert.match(c.nodi.provSel.innerHTML, /- automatico -/);
  assert.match(c.nodi.provSel.innerHTML, /hopper/);

  // 4. il doctor non vuole file: il campo sparisce, l'argomento si spegne e il
  //    bottone dice "Esegui"
  c.ctx.scegliOp(0);
  assert.equal(c.nodi.fileInp.style.display, 'none');
  assert.equal(c.nodi.fileInp.disabled, true);
  assert.equal(c.nodi.argLbl.textContent, 'Argomento (non serve)');
  assert.equal(c.nodi.argInp.disabled, true);
  assert.equal(c.nodi.argInp.placeholder, '');
  assert.equal(c.nodi.btnRun.textContent, 'Esegui');
  assert.equal(c.nodi.provSel.disabled, false); // il doctor lo accetta
  c.ctx.scegliOp(1); // providers: provider non-serve
  assert.equal(c.nodi.provSel.disabled, true);

  // 5. la funzione: file richiesto, argomento col suo nome, provider da
  //    scegliere e l'avviso che l'automatico puo' avviare Hopper da solo
  c.ctx.scegliOp(7);
  assert.equal(c.nodi.fileInp.style.display, '');
  assert.equal(c.nodi.fileInp.disabled, false);
  assert.equal(c.nodi.argLbl.textContent, 'nome della funzione');
  assert.equal(c.nodi.argInp.placeholder, 'nome della funzione');
  assert.equal(c.nodi.btnRun.textContent, 'Analizza');
  assert.equal(c.nodi.provSel.disabled, false);
  assert.match(c.nodi.opInfo.innerHTML, /può avviare Hopper da sola/);

  // 6. l'analisi JavaScript avverte che qui si caricano file singoli
  c.ctx.scegliOp(5);
  assert.match(c.nodi.opInfo.innerHTML, /Serve un <code>\.asar<\/code>/);

  // 7. prima di chiamare il server la pagina rifiuta: file mancante, provider
  //    mancante su un'operazione obbligatoria, argomento mancante
  await c.ctx.invia(null);
  assert.equal(c.nodi.formMsg.textContent, 'serve un file da analizzare');
  assert.equal(post(c.chiamate).length, 0);

  c.ctx.scegliOp(11); // search
  c.nodi.fileInp.files = [file('demo.exe')];
  await c.ctx.invia(null);
  assert.match(c.nodi.formMsg.textContent, /scegli un provider/);
  assert.match(c.nodi.formMsg.textContent, /Hopper/);
  assert.equal(post(c.chiamate).length, 0);

  c.nodi.provSel.value = 'hopper';
  await c.ctx.invia(null);
  assert.equal(c.nodi.formMsg.textContent, 'serve: testo da cercare');
  assert.equal(post(c.chiamate).length, 0);

  // 8. l'indirizzo si chiede con la sua etichetta, non con "argomento"
  c.ctx.scegliOp(8); // decompile
  await c.ctx.invia(null);
  assert.equal(c.nodi.formMsg.textContent, 'serve: indirizzo (0x...)');
  assert.equal(post(c.chiamate).length, 0);
  console.log('rea surface page tests: stato, operazioni e rifiuti — ok');

  // 9. il lavoro parte davvero: il corpo porta op, provider, argomento ripulito
  //    e file, e la pagina apre subito il report del lavoro creato
  const ok = contesto({dettagli: {'abcdef012345': DETTAGLIO}});
  await attendi();
  ok.ctx.scegliOp(11); // search
  ok.nodi.fileInp.files = [file('demo.exe')];
  ok.nodi.provSel.value = 'hopper';
  ok.nodi.argInp.value = '  configurazione  ';
  await ok.ctx.invia(null);
  const inviate = post(ok.chiamate);
  assert.equal(inviate.length, 1);
  assert.equal(inviate[0].url, '/api/jobs');
  const corpo = inviate[0].opzioni.body.voci;
  assert.equal(corpo.map((v) => v[0]).join(','), 'op,provider,argomento,file');
  assert.equal(corpo[0][1], 'search');
  assert.equal(corpo[1][1], 'hopper');
  assert.equal(corpo[2][1], 'configurazione'); // gli spazi se ne vanno
  assert.equal(corpo[3][1].name, 'demo.exe');
  assert.equal(corpo[3][2], 'demo.exe'); // il nome del file, non un percorso
  assert.equal(ok.nodi.formMsg.textContent, 'Lavoro in coda: abcdef012345');
  assert.equal(ok.nodi.btnRun.disabled, false);
  assert.equal(ok.nodi.jobsCount.textContent, '2');
  assert.match(ok.nodi.jobList.innerHTML, /job sel" data-id="abcdef012345/);
  assert.match(ok.nodi.jobList.innerHTML, /in corso/);
  assert.match(ok.nodi.jobList.innerHTML, /altro\.dll/);

  // 10. il report: le tre corsie, il comando, gli artefatti grezzi
  const det = ok.nodi.detail.innerHTML;
  assert.match(det, /Cerca testo nel target/);
  assert.match(det, /abcdef012345/);
  assert.match(det, /rea search demo\.exe configurazione --provider hopper --json/);
  assert.match(det, /Osservato qui/);
  assert.match(det, /8\.1 s/);
  assert.match(det, /1234 B/);
  assert.match(det, /troncato<\/td><td>no<\/td>/);
  assert.match(det, /<b>operazione<\/b><span>rea search demo\.exe/);
  assert.match(det, /<b>provider<\/b><span>hopper<\/span>/);
  assert.match(det, /non sono dichiarazioni di REA/);
  assert.match(det, /Riferito da REA/);
  assert.match(det, /list · 3/);      // le chiavi del documento, col conteggio
  assert.match(det, /deadbeef/);      // un digest riferito da REA
  assert.match(det, /Progresso dichiarato da REA/);
  assert.match(det, /providers — inizializzazione/);
  assert.ok(det.includes('a'.repeat(64)), 'lo sha256 misurato da noi sta nel report');
  assert.ok(det.includes('/api/jobs/abcdef012345/artifact/report.json'));
  assert.ok(det.includes('/api/jobs/abcdef012345/artifact/stderr.log'));
  assert.equal((det.match(/\/artifact\//g) || []).length, 4);
  assert.match(det, /Limiti di questa lettura/);
  assert.match(det, /Nessuna vulnerabilità è confermata qui\./);

  // 11. un lavoro fallito: il codice di uscita assente si dice "timeout", il
  //     troncamento si dichiara e l'envelope d'errore di REA si traduce
  const fallito = Object.assign({}, COMPLETO, {
    id: 'feedfeedfeed', status: 'failed', esito: 'timeout',
    exit_code: null, duration_s: 180.0,
  });
  const conErrore = {
    osservato: {esito: 'timeout', exit_code: null, durata_s: 180.0,
      stdout_bytes: 8388608, stderr_bytes: 0,
      troncato: {stdout: true, stderr: false},
      comando: ['rea', 'function', 'demo.exe', 'main', '--provider', 'hopper',
        '--json']},
    errore: {code: 'timeout', category: 'timeout',
      spiegazione: 'REA ha superato il tempo massimo',
      message: 'killed after 180s', remediation: 'alza il timeout',
      retryable: true},
    limiti: ['Il target non è stato eseguito.'],
  };
  c.ctx.renderDettaglio({job: fallito, report: conErrore});
  const err = c.nodi.detail.innerHTML;
  assert.match(err, /— \(timeout\)/);
  assert.match(err, /sì: tetto di raccolta raggiunto/);
  assert.match(err, /class="box-err"/);
  assert.match(err, /timeout · timeout/);
  assert.match(err, /killed after 180s/);
  assert.match(err, /REA segnala che si può ritentare\./);
  c.ctx.renderDettaglio({job: {}});
  assert.match(c.nodi.detail.innerHTML, /Report non leggibile\./);


  // 12. polling: finche' il lavoro e' in corso la pagina lo richiede da sola,
  //     quando e' chiuso non lascia timer appesi
  assert.equal(ok.ctx.POLL, null); // il lavoro mostrato si e' chiuso subito
  const poll = contesto();
  await attendi();
  await poll.ctx.apri('beefbeefbeef');
  assert.equal(typeof poll.ctx.POLL, 'number');
  assert.equal(poll.timer[0].ms, 1200);
  const prima = poll.chiamate.length;
  await poll.timer[0].fn(); // il giro di polling, eseguito a mano
  await attendi();
  assert.ok(poll.chiamate.length > prima,
    'il giro di polling deve richiedere di nuovo il lavoro');
  assert.equal(poll.timer[1].ms, 1200);
  await poll.ctx.apri('abcdef012345');
  assert.equal(poll.ctx.POLL, null);


  // 13. REA assente: la pagina stampa i comandi e dice che non installa nulla
  const manca = contesto({statoServito: stato({found: false})});
  await attendi();
  assert.equal(manca.nodi.pillRea.textContent, 'rea non trovato');
  assert.equal(manca.nodi.pillRea.className, 'pill warn');
  assert.equal(manca.nodi.banner.className, '');
  assert.match(manca.nodi.banner.innerHTML, /REA non è installato/);
  assert.match(manca.nodi.banner.innerHTML, /npm install --global rea-agents/);
  assert.match(manca.nodi.banner.innerHTML, /\/private\/tmp\/rea-pilot/);
  assert.match(manca.nodi.banner.innerHTML, /rea setup/);
  assert.match(manca.nodi.banner.innerHTML, /non è nel PATH/);
  assert.equal((manca.nodi.opSel.innerHTML.match(/<option/g) || []).length, 13,
    'la whitelist resta visibile anche senza REA');

  // 14. superficie giu': la pagina lo dice invece di restare a "Caricamento…"
  const giu = contesto({rompi: true});
  await attendi();
  assert.equal(giu.nodi.pillRea.textContent, 'superficie non raggiungibile');
  assert.match(giu.nodi.jobList.innerHTML, /fetch failed/);

  // 15. nessun lavoro ancora: l'elenco invita a cominciare da un file
  const vuoto = contesto({jobs: []});
  await attendi();
  assert.equal(vuoto.nodi.jobsCount.textContent, '0');
  assert.match(vuoto.nodi.jobList.innerHTML, /Nessun lavoro\./);

  // 16. le corsie da sole: vuote restano vuote, e l'osservato mancante non
  //     diventa mai una conclusione
  assert.match(c.ctx.laneOsservato(null), /REA non ha ancora chiuso questo lavoro/);
  assert.equal(c.ctx.timeline(null), '');
  assert.equal(c.ctx.timeline([]), '');
  assert.equal(c.ctx.laneRiferito(null), '');
  assert.equal(c.ctx.laneLimiti([]), '');
  assert.equal(c.ctx.boxErrore(null), '');
  assert.ok(c.ctx.artefatti('x').includes('/api/jobs/x/artifact/stdout.json'));
  assert.equal((c.ctx.artefatti('x').match(/<a /g) || []).length, 4);

  // 17. il progresso vero (righe rea_progress annidate) resta leggibile, e il
  //     verdetto di `doctor` compare invece di restare sepolto in 92 KB
  const timeline = c.ctx.timeline([{fase: 'parse_javascript_source',
    messaggio: 'Parsing and projecting index.js (1/2)', file: ''}]);
  assert.match(timeline, /parse_javascript_source/);
  assert.match(timeline, /Parsing and projecting index\.js \(1\/2\)/);
  const conVerdetto = c.ctx.laneRiferito({nota: 'Il documento c\'e\' e si legge, ma REA '
    + 'e\' uscito con codice 1 senza un envelope d\'errore.',
    verdetto: {healthy: false, environment_healthy: false}});
  assert.match(conVerdetto, /verdetto di REA/);
  assert.match(conVerdetto, /healthy: false/);
  assert.match(conVerdetto, /environment_healthy: false/);
  const senzaVerdetto = c.ctx.laneRiferito({nota: 'Documento JSON letto e ridotto.',
    verdetto: null});
  assert.doesNotMatch(senzaVerdetto, /verdetto di REA/);

  console.log('rea surface page tests passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });
