// SPDX-License-Identifier: Apache-2.0
// spider/bootstrap.js — accende la ragnatela procedurale (Web Crawlers) su ogni
// pagina di HyperSpace, e non la lascia cadere fra una pagina e l'altra.
//
// La ragnatela non e' nostra: e' `web-crawlers` di cyohei9907 (docs/spider.md,
// nel `data/control-plane/vendor/web-crawlers/PROVENANCE.txt`). Qui non c'e' una riga di quel
// codice: lo carichiamo e lo comandiamo dall'esterno tramite la sua API
// pubblica `window.__webCrawler.{start,stop,set,stats}`, quindi questo file
// porta la NOSTRA licenza e resta nostro. E' anche il motivo per cui la
// ragnatela vive in `data/` (gitignorato) e non in `control-plane/vendor/`:
// l'upstream non ha un file di licenza, vendored e tracciato romperebbe
// `tests/test_licensing.py` — che pretende l'header Apache-2.0 su ogni sorgente
// versionato — e mettere la nostra licenza sul codice di un altro sarebbe una
// dichiarazione falsa. Vedi docs/spider.md.
//
// Cosa fa, in quattro punti:
//   1. legge il contratto che il control-plane scrive PRIMA di questo file
//      (`window.__HSPIDER__ = {enabled, source, size, density, search}`) e si
//      spegne subito se `enabled` e' false (SPIDER_ENABLED=false, vedi
//      .env.example);
//   2. carica la ragnatela da `source` — stessa origine, `/spider/spider.js` —
//      e la avvia. Se il file non c'e' (clone pulito: e' gitignorato) non fa
//      nulla e non lancia: la pagina resta identica a com'era;
//   3. ricorda in sessionStorage se e' accesa e con che taglia/densita', cosi'
//      ogni pagina successiva la fa rinascere com'era invece di ripartire da
//      zero. sessionStorage, non localStorage: "ovunque nella navigazione"
//      significa in questa scheda; un'altra scheda e' un'altra ragnatela;
//   4. (se nel contratto c'e' `search`, SPIDER_SEARCH=true) fa da ASSISTENTE ALLA
//      RICERCA: la ragnatela non espone la parola su cui cammina, quindi la
//      ricaviamo NOI con la stessa API pubblica che usa lei
//      (`document.caretRangeFromPoint` + `Intl.Segmenter`), campionando il punto
//      del suo corpo. La parola compare in un chip, e Alt+Shift+F o un clic sul
//      chip aprono la ricerca su SearXNG. Il chip e' un NOSTRO elemento in uno
//      shadow root: la pagina non si tocca, come per tutto il resto del file.
//
// Limite dichiarato, per non promettere piu' di quel che c'e': l'upstream
// `start()` fa entrare la ragnatela dalla parte alta della vista (scelta sua,
// non c'e' API per dirle dove), poi inseguono il mouse. Quello che sopravvive
// alla navigazione e' lo stato — accesa/spenta, taglia, densita' — non la
// posizione esatta delle zampe.
(function () {
  'use strict';

  var cfg = window.__HSPIDER__ || {};
  if (cfg.enabled === false) return;   // SPIDER_ENABLED=false: nessun overlay

  var SRC = cfg.source || '/spider/spider.js';
  var KEY = 'hspider.state';
  // Dove mandare la parola raccolta. Il control-plane lo scrive nel contratto
  // (`search: {port, path}`) solo quando l'assistente e' acceso: assente/null =
  // niente assistente, il ragno resta solo la bella ragnatela di prima.
  var SEARCH = cfg.search || null;
  var SHORTCUT = 'Alt+Shift+F';
  var api = null;

  function stored() {
    try { return JSON.parse(window.sessionStorage.getItem(KEY)) || {}; }
    catch (e) { return {}; }
  }
  function remember(patch) {
    var s = stored();
    for (var k in patch) { if (patch.hasOwnProperty(k)) s[k] = patch[k]; }
    try { window.sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (e) {}
    return s;
  }

  var state = stored();

  // Accesa di default — e' quel che e' stato chiesto: "in ogni parte, me la deve
  // seguire". Con `prefers-reduced-motion` invece parte solo se l'utente l'ha
  // voluta davvero: un animale che cammina sul testo e' esattamente cio' che
  // quella preferenza chiede di non far partire da solo.
  var explicited = typeof state.on === 'boolean';
  var reduced = false;
  try {
    reduced = !!(window.matchMedia &&
                 window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  } catch (e) { /* matchMedia assente: si comporta come "nessuna preferenza" */ }
  var accesa = explicited ? state.on : !reduced;

  // Override esplicito in URL (?spider=off / ?spider=on): serve a chi registra
  // lo schermo o prepara una demo, e viene ricordato come una scelta a mano.
  var q = /[?&]spider=(on|off)\b/.exec(window.location.search);
  if (q) accesa = remember({ on: q[1] === 'on' }).on;

  function opts() {
    return {
      size: state.size || cfg.size || 'M',
      density: state.density || cfg.density || 'normal',
      autoRead: state.autoRead === true,
    };
  }

  function start() {
    if (!api) return false;
    var ok = api.start(opts());
    remember({ on: true });
    return ok;
  }
  function stop() {
    if (!api) return false;
    var ok = api.stop();
    remember({ on: false });
    return ok;
  }
  function toggle() { return (api && api.running) ? stop() : start(); }

  // Alt+Shift+S accende/spegne (lo stesso tasto dell'estensione upstream);
  // Alt+Shift+F manda in ricerca la parola che il ragno sta camminando.
  function onKey(e) {
    if (!e.altKey || !e.shiftKey) return;
    if (e.key === 'S' || e.key === 's' || e.code === 'KeyS') {
      e.preventDefault();
      toggle();
      return;
    }
    if (e.key === 'F' || e.key === 'f' || e.code === 'KeyF') {
      // Solo se c'e' davvero una parola sotto: altrimenti il tasto non e'
      // nostro e non lo consumiamo (la pagina puo' averci i suoi comandi).
      if (cerca(attuale)) e.preventDefault();
    }
  }

  // ── Assistente alla ricerca ────────────────────────────────────────────────
  // La ragnatela non espone la parola su cui cammina: la sua API pubblica e'
  // solo {running,start,stop,set,stats,options}. La ricaviamo qui, dalla stessa
  // API che usa lei — `document.caretRangeFromPoint` per il nodo sotto un punto
  // e `Intl.Segmenter` per i confini di parola — campionando il punto del suo
  // corpo: `stats().spider.vx/vy` sono normalizzati sulla vista (il vendor li
  // calcola come `(posizione - scroll) / innerWidth|Height`), quindi il pixel e'
  // (vx*innerWidth, vy*innerHeight). Cosi' non tocchiamo una riga di codice di
  // terzi e l'upstream resta aggiornabile a parte.

  var seg = null;
  try {
    if (window.Intl && window.Intl.Segmenter) {
      seg = new window.Intl.Segmenter(undefined, { granularity: 'word' });
    }
  } catch (e) { /* niente Segmenter: vale il ripiego dentro parolaIn */ }

  var SKIP = /^(SCRIPT|STYLE|NOSCRIPT|TEXTAREA|INPUT|SELECT|CODE|PRE|SVG)$/;

  function parolaIn(texto, off) {
    if (seg) {
      var it = seg.segment(texto), s;
      for (s of it) {
        if (off >= s.index && off < s.index + s.segment.length) {
          return s.isWordLike ? s.segment : '';
        }
      }
      return '';
    }
    var re = /[^\s]+/g, m;   // ripiego senza Intl.Segmenter
    while ((m = re.exec(texto))) {
      if (off >= m.index && off < m.index + m[0].length) {
        return /[\p{L}\p{N}]/u.test(m[0]) ? m[0] : '';
      }
    }
    return '';
  }

  function wordAt(x, y) {
    if (!document.caretRangeFromPoint) return '';
    var r = document.caretRangeFromPoint(x, y);
    if (!r || !r.startContainer || r.startContainer.nodeType !== 3) return '';
    var el = r.startContainer.parentNode;
    if (!el || SKIP.test(el.nodeName || '')) return '';
    // il nostro stesso chip vive in uno shadow root: mai raccogliere quello
    if (el.getRootNode && el.getRootNode() !== document) return '';
    var p = parolaIn(r.startContainer.nodeValue || '', r.startOffset);
    if (!p || p.length > 64 || !/[\p{L}\p{N}]/u.test(p)) return '';
    return p;
  }

  var chipHost = null, chipWord = null, attuale = '';

  function buildChip() {
    // Tutto creato a mano, niente innerHTML: e' un elemento NOSTRO, in uno
    // shadow root, appeso a <html> — la pagina non si tocca (come il resto).
    chipHost = document.createElement('div');
    chipHost.setAttribute('data-hspider-chip', '');
    chipHost.style.cssText =
      'position:fixed;left:0;top:0;z-index:2147483646;pointer-events:none;' +
      'opacity:0;transition:opacity .12s linear;will-change:transform;';
    var root = chipHost.attachShadow ? chipHost.attachShadow({ mode: 'open' }) : chipHost;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.style.cssText =
      'pointer-events:auto;cursor:pointer;white-space:nowrap;' +
      'font:12px/1.35 system-ui,-apple-system,Segoe UI,sans-serif;' +
      'background:#12151c;color:#e8eaf0;border:1px solid #3a4152;border-radius:10px;' +
      'padding:4px 9px;box-shadow:0 6px 18px rgba(0,0,0,.35);';
    var lente = document.createElement('span');
    lente.textContent = '\uD83D\uDD0E ';
    chipWord = document.createElement('span');
    chipWord.style.cssText = 'font-weight:600';
    var hint = document.createElement('span');
    hint.textContent = '  ' + SHORTCUT;    // il chip dice come si cerca
    hint.style.cssText = 'opacity:.5';
    btn.appendChild(lente);
    btn.appendChild(chipWord);
    btn.appendChild(hint);
    // Clic sul chip = come Alt+Shift+F. stopPropagation: il clic e' nostro, la
    // pagina sotto non deve vederlo (poteva essere una selezione o un link).
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      cerca(attuale);
    });
    root.appendChild(btn);
    document.documentElement.appendChild(chipHost);
  }

  function show(parola, x, y) {
    if (!chipHost) buildChip();
    if (parola !== attuale) { chipWord.textContent = parola; attuale = parola; }
    chipHost.style.transform = 'translate(' + Math.round(x + 16) + 'px,' +
                               Math.round(y - 28) + 'px)';
    chipHost.style.opacity = '1';
  }
  function hide() { if (chipHost) chipHost.style.opacity = '0'; attuale = ''; }

  // Un giro di sondaggio: se il ragno e' in cammino e sotto il suo corpo c'e' una
  // parola, il chip la mostra; altrimenti sparisce. Gira piano (150 ms), non a
  // ogni frame: deve costare poco, e' un di piu' della ragnatela, non il suo scopo.
  function poll() {
    if (!api || !api.running) return hide();
    var st; try { st = api.stats(); } catch (e) { return hide(); }
    var sp = st && st.spider;
    if (!sp) return hide();
    var x = sp.vx * window.innerWidth, y = sp.vy * window.innerHeight;
    var p = wordAt(x, y);
    if (p) show(p, x, y); else hide();
  }

  function install() {
    if (!SEARCH || !window.setInterval) return;   // senza contratto/timer: niente
    window.setInterval(poll, 150);
  }

  // Apre la ricerca sulla parola raccolta, in una scheda nuova. L'URL lo compone
  // il BROWSER (location.hostname): SearXNG sta su un'altra porta dello stesso
  // host, quindi vale sia da localhost sia da un altro dispositivo della rete.
  // `port`/`path` arrivano dal contratto, non sono cablati qui. Ritorna false se
  // non c'e' niente da cercare: chi ci chiama decide se consumare il tasto.
  function cerca(parola) {
    if (!SEARCH || !parola) return false;
    var url = window.location.protocol + '//' + window.location.hostname + ':' +
              SEARCH.port + (SEARCH.path || '/search') + '?q=' + encodeURIComponent(parola);
    window.open(url, '_blank', 'noopener');
    return true;
  }

  function ready() {
    if (!window.__webCrawler) return;   // file assente: la pagina resta intatta
    api = window.__webCrawler;
    if (accesa) start();
    document.addEventListener('keydown', onKey);
    install();
    window.__hspider = {
      toggle: toggle, start: start, stop: stop,
      stats: function () { return api.stats(); },
      // assistente alla ricerca (assente se il contratto non porta `search`)
      word: function () { return attuale; },
      cerca: cerca,
      get state() { return stored(); },
    };
  }

  function load() {
    if (window.__webCrawler) return ready();
    var s = document.createElement('script');
    s.src = SRC;
    s.async = true;
    s.onload = ready;
    // Nessun onerror: se il vendor non c'e' la console mostra gia' il 404 della
    // rotta, che e' l'informazione giusta; qui non serve altro.
    (document.head || document.documentElement).appendChild(s);
  }

  // L'include nelle pagine e' `defer`, quindi di norma lo stato e' gia'
  // 'interactive' e si carica subito; il ramo 'loading' copre chi lo importa
  // a mano nel <head> senza defer.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
