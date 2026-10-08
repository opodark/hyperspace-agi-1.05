// SPDX-License-Identifier: Apache-2.0
// La scheda "Servizi": il catalogo /surfaces esisteva solo come idea di
// consolidamento. Questo test tiene collegata la pagina al catalogo e fissa il
// comportamento del tasto di stato (up/down) misurato dal browser.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'control-plane', 'dashboard.html'), 'utf8');

// 1. aggancio statico: pannello, voce di menu, ricarica e hook in showPanel
assert.match(html, /id="panel-services"/);
assert.match(html, /showPanel\('services',this\)/);
assert.match(html, /onclick="loadSurfaces\(\)"/);
assert.match(html, /if\(name==='services'\)loadSurfaces\(\);/);

const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const start = script.indexOf('// ── SERVIZI / SUPERFICI');
const end = script.indexOf('// ── Deep-link di scheda');
assert.ok(start >= 0 && end > start, 'blocco servizi presente e delimitato');

function contesto(payload, options = {}) {
  const requests = [];
  const grid = { innerHTML: '', querySelectorAll: () => [] };
  const sum = { textContent: '' };
  const ctx = {
    window: { location: { origin: 'http://host:8085', protocol: 'http:', hostname: 'host' } },
    document: {
      getElementById: (id) => (id === 'surfacesGrid' ? grid : id === 'surfacesSummary' ? sum : null),
    },
    fetch: async (url) => {
      requests.push(url);
      if (options.fail) throw new Error('control-plane giu');
      return { ok: true, status: 200, json: async () => payload };
    },
    escH: (v) => String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'),
    console,
  };
  vm.createContext(ctx);
  vm.runInContext(script.slice(start, end), ctx);
  return { ctx, requests, grid, sum };
}

const CATALOGO = {
  surfaces: [
    { id: 'dashboard', label: 'Dashboard Mesh', category: 'control-plane',
      path: '/dashboard', port: null, desc: 'Nodi e task.' },
    { id: 'infra_ui', label: 'Live 3D — Infra UI', category: 'observability',
      path: '/', port: 8099, optional: true, desc: 'Mesh in tempo reale.' },
    { id: 'chat', label: 'Chat (Open WebUI)', category: 'external',
      path: '/', port: 3000, optional: true, desc: 'Chatta con la mesh.' },
  ],
};

(async () => {
  const c = contesto(CATALOGO);

  // 2. costruzione URL: stessa origine per il CP, porta dell'host per il resto
  assert.equal(c.ctx.surfaceUrl({ port: null, path: '/dashboard' }), 'http://host:8085/dashboard');
  assert.equal(c.ctx.surfaceUrl({ port: 8099, path: '/' }), 'http://host:8099/');

  // 3. card: link, porta, path e marcatura opzionale
  const card = c.ctx.surfaceCard(CATALOGO.surfaces[0]);
  assert.match(card, /Dashboard Mesh/);
  assert.match(card, /data-surf="http:\/\/host:8085\/dashboard"/);
  assert.match(card, /questo CP/);
  const card2 = c.ctx.surfaceCard(CATALOGO.surfaces[1]);
  assert.match(card2, /opzionale/);
  assert.match(card2, /:8099/);

  // 4. caricamento: una fetch al catalogo, gruppi nell'ordine delle categorie
  await c.ctx.loadSurfaces();
  assert.deepEqual(c.requests, ['/surfaces']);
  const out = c.grid.innerHTML;
  assert.match(out, /Control plane/);
  assert.match(out, /Osservabilit/);
  assert.match(out, /Servizi esterni/);
  assert.match(out, /Dashboard Mesh/);
  assert.match(out, /Live 3D/);
  assert.match(out, /Chat \(Open WebUI\)/);
  assert.match(c.sum.textContent, /3 superfici/);
  assert.ok(out.indexOf('Control plane') < out.indexOf('Servizi esterni'), 'ordine categorie');

  // 5. il tasto di stato aggiorna pallino ed etichetta
  const dot = { className: '' };
  const stat = { textContent: '' };
  const el = { querySelector: (s) => (s === '.surf-dot' ? dot : s === '.surf-stat' ? stat : null) };
  c.ctx.surfaceUp(el, true);
  assert.equal(dot.className, 'surf-dot up');
  assert.equal(stat.textContent, 'su');
  c.ctx.surfaceUp(el, false);
  assert.equal(dot.className, 'surf-dot down');
  assert.equal(stat.textContent, 'giù?');

  // 6. catalogo vuoto: lo dice, non lascia un riquadro vuoto
  const vuoto = contesto({ surfaces: [] });
  await vuoto.ctx.loadSurfaces();
  assert.match(vuoto.grid.innerHTML, /Nessuna superficie/);

  // 7. errore di rete: messaggio, non crash
  const rotto = contesto(CATALOGO, { fail: true });
  await rotto.ctx.loadSurfaces();
  assert.match(rotto.sum.textContent, /Errore/);
  assert.equal(rotto.grid.innerHTML, '');

  console.log('dashboard services tests passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });
