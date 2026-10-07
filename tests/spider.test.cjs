// SPDX-License-Identifier: Apache-2.0
// Il bootstrap della ragnatela (control-plane/spider/bootstrap.js) eseguito in
// una vm: sono i modi in cui si rompe in silenzio. Una ragnatela che non parte
// non da' errore — semplicemente non c'e'. Qui si controlla che parta quando
// deve, che NON parta quando non deve (kill switch, scelta ricordata,
// prefers-reduced-motion) e che senza il file vendorizzato non lanci niente e non
// lasci residui (window.__hspider), cosi' la pagina resta identica a com'era.
const fs = require('fs');
const vm = require('vm');
const test = require('node:test');
const assert = require('node:assert/strict');

const SORGENTE = fs.readFileSync('control-plane/spider/bootstrap.js', 'utf8');
// Il sorgente senza commenti: i commenti PARLANO di localStorage (`sessionStorage,
// non localStorage`), e un test che cerca la stringa li troverebbe — e passerebbe
// o fallirebbe per il motivo sbagliato.
const CODICE = SORGENTE.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

// Un elemento finto, quanto basta per il chip e per il <script>: il bootstrap
// costruisce NODI (createElement + appendChild + shadow root), non stringhe.
function fintoEl() {
  const e = {
    children: [], attrs: {}, style: {}, handlers: {}, textContent: '',
    nodeName: 'DIV',
    setAttribute(k, v) { e.attrs[k] = v; },
    appendChild(c) { e.children.push(c); return c; },
    addEventListener(t, f) { e.handlers[t] = f; },
    attachShadow() { e.shadow = fintoEl(); return e.shadow; },
    closest() { return null; },
    getRootNode() { return null; },
  };
  return e;
}

// Un finto browser: solo quello che il bootstrap tocca davvero.
function harness(opts) {
  opts = opts || {};
  const creati = [];
  const listeners = {};
  const timers = [];
  const aperti = [];
  const store = Object.assign({}, opts.storage || {});
  const win = {
    __HSPIDER__: opts.hspider || { enabled: true, source: '/spider/spider.js' },
    __webCrawler: null,
    innerWidth: opts.innerWidth || 1000,
    innerHeight: opts.innerHeight || 800,
    sessionStorage: {
      getItem: k => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
    },
    location: {
      search: opts.search || '',
      protocol: 'http:',
      hostname: opts.hostname || 'localhost',
    },
    matchMedia: () => ({ matches: !!opts.reduced }),
    addEventListener: (t, f) => { listeners[t] = f; },
    setInterval: fn => { timers.push(fn); return timers.length; },
    clearInterval: () => {},
    open: url => { aperti.push(url); return {}; },
    document: {
      readyState: opts.readyState || 'interactive',
      head: { appendChild: el => creati.push(el) },
      documentElement: { appendChild: el => creati.push(el) },
      addEventListener: (t, f) => { listeners[t] = f; },
      createElement: () => fintoEl(),
    },
  };
  // Il nodo sotto un punto: al posto di caretRangeFromPoint, il testo e l'offset
  // che il test vuole — la stessa forma che il bootstrap si aspetta.
  if (opts.caret) {
    win.document.caretRangeFromPoint = () => ({
      startContainer: {
        nodeType: 3,
        nodeValue: opts.caret.text,
        parentNode: { nodeName: opts.caret.parent || 'P',
                      getRootNode: () => win.document },
      },
      startOffset: opts.caret.offset,
    });
  }
  win.window = win;
  vm.runInContext(SORGENTE, vm.createContext(win), { filename: 'bootstrap.js' });
  return { win, creati, listeners, store, timers, aperti };
}

// La ragnatela finta: registra start/stop e le opzioni ricevute.
function spia() {
  const chiamate = { start: 0, stop: 0 };
  const finto = {
    running: false, opts: [],
    start(o) { chiamate.start++; finto.running = true; finto.opts.push(Object.assign({}, o)); return true; },
    stop() { chiamate.stop++; finto.running = false; return true; },
    set() {},
    stats: () => ({ running: finto.running }),
  };
  return { finto, chiamate };
}

test('abilitata: carica la ragnatela dalla stessa origine e parte', () => {
  const h = harness();
  assert.equal(h.creati.length, 1, 'un solo <script> aggiunto');
  assert.equal(h.creati[0].src, '/spider/spider.js');
  const s = spia();
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  assert.equal(s.chiamate.start, 1);
  assert.deepEqual(s.finto.opts[0], { size: 'M', density: 'normal', autoRead: false });
  assert.equal(JSON.parse(h.store['hspider.state']).on, true, 'accesa: va ricordato');
  assert.equal(typeof h.win.__hspider.toggle, 'function', 'gancio per la console');
});

test('SPIDER_ENABLED=false: nessuna richiesta, nessun overlay, pagina intatta', () => {
  const h = harness({ hspider: { enabled: false, source: '/spider/spider.js' } });
  assert.equal(h.creati.length, 0);
  assert.equal(h.win.__hspider, undefined);
});

test('spenta a mano una volta, resta spenta sulle pagine successive', () => {
  const h = harness({ storage: { 'hspider.state': JSON.stringify({ on: false }) } });
  assert.equal(h.creati.length, 1, 'il file lo carica comunque: non parte e basta');
  const s = spia();
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  assert.equal(s.chiamate.start, 0);
});

test('taglia e densita scelte sopravvivono alla navigazione', () => {
  const h = harness({ storage: { 'hspider.state': JSON.stringify({ on: true, size: 'L', density: 'wild', autoRead: true }) } });
  const s = spia();
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  assert.deepEqual(s.finto.opts[0], { size: 'L', density: 'wild', autoRead: true });
});

test('prefers-reduced-motion: non parte da sola, ma una scelta esplicita vince', () => {
  const ridotto = harness({ reduced: true });
  const s1 = spia();
  ridotto.win.__webCrawler = s1.finto;
  ridotto.creati[0].onload();
  assert.equal(s1.chiamate.start, 0, 'nessuna preferenza espressa: non parte');

  const voluto = harness({ reduced: true, storage: { 'hspider.state': JSON.stringify({ on: true }) } });
  const s2 = spia();
  voluto.win.__webCrawler = s2.finto;
  voluto.creati[0].onload();
  assert.equal(s2.chiamate.start, 1, 'l\'utente l\'ha accesa: parte');
});

test('Alt+Shift+S commuta e ricorda', () => {
  const h = harness();
  const s = spia();
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  let prevenuto = false;
  h.listeners.keydown({ altKey: true, shiftKey: true, key: 'S', preventDefault: () => { prevenuto = true; } });
  assert.equal(s.chiamate.stop, 1);
  assert.equal(prevenuto, true, 'la combinazione non deve anche arrivare alla pagina');
  assert.equal(JSON.parse(h.store['hspider.state']).on, false);
  h.listeners.keydown({ altKey: true, shiftKey: true, key: 'S', preventDefault: () => {} });
  assert.equal(s.chiamate.start, 2);
  // una 'S' senza modificatori non deve toccare niente
  h.listeners.keydown({ altKey: false, shiftKey: false, key: 'S', preventDefault: () => {} });
  assert.equal(s.chiamate.start + s.chiamate.stop, 3);
});

test('?spider=off salta la vista e lo ricorda', () => {
  const h = harness({ search: '?spider=off' });
  const s = spia();
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  assert.equal(s.chiamate.start, 0);
  assert.equal(JSON.parse(h.store['hspider.state']).on, false);
});

test('senza il file vendorizzato non lancia e non lascia residui', () => {
  const h = harness();
  assert.doesNotThrow(() => h.creati[0].onload());
  assert.equal(h.win.__hspider, undefined);
  assert.equal(h.win.__webCrawler, null);
});

test('include senza defer: aspetta il DOMContentLoaded', () => {
  const h = harness({ readyState: 'loading' });
  assert.equal(h.creati.length, 0, 'non carica mentre il documento sta ancora arrivando');
  assert.equal(typeof h.listeners.DOMContentLoaded, 'function');
  h.listeners.DOMContentLoaded();
  assert.equal(h.creati.length, 1);
});

test('il bootstrap e\' nostro: niente API da estensione, niente DOM della pagina', () => {
  assert.doesNotMatch(CODICE, /chrome\./, 'non e\' un content script di estensione');
  assert.doesNotMatch(CODICE, /document\.body/, 'scrive solo un <script> nell\'head');
  assert.doesNotMatch(CODICE, /innerHTML/, 'la pagina non si tocca');
});

test('niente localStorage: lo stato e\' della scheda, non della macchina', () => {
  assert.doesNotMatch(CODICE, /localStorage/);
  assert.match(CODICE, /sessionStorage/);
});

test('legge il contratto del control-plane (enabled, source)', () => {
  assert.match(SORGENTE, /__HSPIDER__/);
  assert.match(SORGENTE, /\/spider\/spider\.js/);
  assert.match(SORGENTE, /__webCrawler/);
});


// ── Assistente alla ricerca ────────────────────────────────────────────────
// La ragnatela non espone la parola su cui cammina: la ricava il bootstrap. Qui
// si guida a mano il sondaggio (h.timers[0]) perche' i timer del finto browser
// sono registrati, non veri — un intervallo vero terrebbe vivo il processo.

const CON_SEARCH = {
  enabled: true, source: '/spider/spider.js',
  search: { port: 8092, path: '/search' },
};

// Ragnatela accesa, con `search` nel contratto, in cammino sotto il cursore.
function conRagno(extra) {
  const h = harness(Object.assign({ hspider: CON_SEARCH }, extra || {}));
  const s = spia();
  s.finto.stats = () => ({ running: true, spider: { vx: 0.5, vy: 0.5 } });
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  return h;
}

test('il ragno raccoglie la parola sotto di se in un chip', () => {
  const h = conRagno({ caret: { text: 'ciao mondo', offset: 6 } });
  assert.equal(h.timers.length, 1, 'un solo sondaggio');
  h.timers[0]();
  assert.equal(h.creati.length, 2, "il chip e' un elemento nostro, dopo lo <script>");
  const chip = h.creati[1];
  assert.equal(chip.attrs['data-hspider-chip'], '');
  const btn = chip.shadow.children[0];
  assert.equal(btn.children[1].textContent, 'mondo', 'la parola sotto il ragno');
  assert.equal(chip.style.opacity, '1');
  assert.equal(h.win.__hspider.word(), 'mondo', 'esposta anche alla console');
});

test('Alt+Shift+F apre la ricerca sulla parola raccolta', () => {
  const h = conRagno({ caret: { text: 'alfa beta', offset: 6 } });
  h.timers[0]();
  let prevenuto = false;
  h.listeners.keydown({ altKey: true, shiftKey: true, key: 'F', code: 'KeyF',
                        preventDefault: () => { prevenuto = true; } });
  assert.deepEqual(h.aperti, ['http://localhost:8092/search?q=beta']);
  assert.equal(prevenuto, true, "con una parola sotto, il tasto e' nostro");
});

test('il clic sul chip apre la stessa ricerca', () => {
  const h = conRagno({ caret: { text: 'alfa beta', offset: 6 } });
  h.timers[0]();
  const btn = h.creati[1].shadow.children[0];
  btn.handlers.click({ preventDefault() {}, stopPropagation() {} });
  assert.deepEqual(h.aperti, ['http://localhost:8092/search?q=beta']);
});

test('sullo spazio bianco niente chip, e Alt+Shift+F non tocca la pagina', () => {
  const h = conRagno({ caret: { text: '   ', offset: 1 } });
  h.timers[0]();
  assert.equal(h.creati.length, 1, "nessun chip: sotto il ragno non c'e' una parola");
  let prevenuto = false;
  h.listeners.keydown({ altKey: true, shiftKey: true, key: 'F', code: 'KeyF',
                        preventDefault: () => { prevenuto = true; } });
  assert.equal(prevenuto, false, 'senza parola il tasto resta della pagina');
  assert.deepEqual(h.aperti, []);
});

test('col ragno fermo il chip sparisce', () => {
  const h = conRagno({ caret: { text: 'ciao mondo', offset: 6 } });
  h.timers[0]();
  assert.equal(h.creati[1].style.opacity, '1');
  h.win.__webCrawler.running = false;
  h.timers[0]();
  assert.equal(h.creati[1].style.opacity, '0');
});

test("senza search nel contratto l'assistente non esiste", () => {
  const h = harness({ caret: { text: 'ciao mondo', offset: 6 } });  // hspider senza search
  const s = spia();
  h.win.__webCrawler = s.finto;
  h.creati[0].onload();
  assert.equal(h.timers.length, 0, 'nessun sondaggio senza search nel contratto');
});

test("l'assistente e' nel file, e non tocca la pagina", () => {
  assert.match(CODICE, /caretRangeFromPoint/);
  assert.match(CODICE, /Segmenter/);
  assert.match(CODICE, /Alt\+Shift\+F/);
  assert.match(CODICE, /data-hspider-chip/);
  assert.doesNotMatch(CODICE, /innerHTML/);
  assert.doesNotMatch(CODICE, /document\.body/);
});

