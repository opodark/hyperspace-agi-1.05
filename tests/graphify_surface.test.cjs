// SPDX-License-Identifier: Apache-2.0
// La pagina della superficie del grafo (scripts/graphify_surface.py) nel suo
// comportamento: freschezza, nomi delle community, filtro di ricerca e passaggio
// panoramica -> community. Il sorgente Python contiene la pagina: qui si estrae
// lo <script> e lo si esegue in un contesto finto, con `vis` e `document` al
// posto dei veri. Quello che si difende e' cosa la pagina dice e disegna, non il
// rendering di vis-network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sorgente = fs.readFileSync(
  path.join(__dirname, '..', 'scripts', 'graphify_surface.py'), 'utf8');
const pagina = sorgente.match(/_PAGE = r"""([\s\S]*?)"""/)[1];
const script = pagina.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(script); // il blocco inline deve restare JS valido

// Stesso grafo finto dei test Python: una community con nomi segnaposto
// ("Community 0") e una con un nome dichiarato.
const GRAFO = {
  dir: 'graphify-out',
  nodes: [
    {id: 'a', label: 'push_log', community: 0, community_name: 'Community 0',
      source_file: 'control-plane/cp/log.py', source_location: 'L10', file_type: 'code', _callable: true},
    {id: 'b', label: 'rota', community: 0, community_name: 'Community 0',
      source_file: 'control-plane/cp/log.py', source_location: 'L40', file_type: 'code'},
    {id: 'c', label: 'ricerca', community: 1, community_name: 'Documenti e ricerca',
      source_file: 'docs/graphify.md', source_location: 'L1', file_type: 'doc'},
    {id: 'd', label: 'hs', community: 1, community_name: 'Community 1',
      source_file: 'scripts/hs.py', source_location: 'L1', file_type: 'code'},
  ],
  links: [
    {source: 'a', target: 'b', relation: 'calls', source_file: 'control-plane/cp/log.py'},
    {source: 'a', target: 'c', relation: 'calls', source_file: 'control-plane/cp/log.py'},
    {source: 'b', target: 'c', relation: 'calls', source_file: 'control-plane/cp/log.py'},
    {source: 'd', target: 'c', relation: 'imports_from'},
  ],
  communities: {
    '0': {id: 0, name: 'push_log · control-plane', derived: true, hub: 'push_log',
      hub_id: 'a', hub_file: 'control-plane/cp/log.py', dir: 'control-plane', size: 2,
      files: [{file: 'control-plane', n: 2}]},
    '1': {id: 1, name: 'Documenti e ricerca', derived: false, hub: 'ricerca',
      hub_id: 'c', hub_file: 'docs/graphify.md', dir: 'docs', size: 2,
      files: [{file: 'docs', n: 1}, {file: 'scripts', n: 1}]},
  },
  degree: {a: 2, b: 2, c: 3, d: 1},
  neighbours: {
    a: [{id: 'b', relation: 'calls', dir: 'out'}, {id: 'c', relation: 'calls', dir: 'out'}],
    b: [{id: 'a', relation: 'calls', dir: 'in'}],
    c: [{id: 'a', relation: 'calls', dir: 'in'}, {id: 'b', relation: 'calls', dir: 'in'},
        {id: 'd', relation: 'imports_from', dir: 'in'}],
    d: [{id: 'c', relation: 'imports_from', dir: 'out'}],
  },
  names: {derived: 1, declared: 1, total: 2},
};

const STATO = {
  dir: 'graphify-out', nodes: 4, edges: 4, communities: 2,
  built_at_commit: 'abc1234def', head: 'zzz9999', stale: true,
  generated_at: '2026-10-09T05:53:56Z', age_hours: 1.5, report: true, html: false,
  commands: {update: './scripts/graphify.sh update .',
    cluster: './scripts/graphify.sh cluster-only .',
    html: './scripts/graphify.sh export html',
    service: '.venv/bin/python scripts/graphify_surface.py'},
};

const ELENCO = [{name: 'graphify-out', nodes: 4, edges: 4, communities: 2,
  stale: true, built_at_commit: 'abc1234def', generated_at: '2026-10-09T05:53:56Z'}];

function elemento() {
  return {innerHTML: '', textContent: '', className: '', value: '', style: {},
    children: [], appendChild(n) { this.children.push(n); },
    getAttribute() { return null; }, setAttribute() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    showModal() { this.modal = true; }, close() { this.modal = false; }};
}

function contesto({stato = STATO, grafo = GRAFO, elenco = ELENCO} = {}) {
  const nodi = {}, reti = {};
  const ctx = {
    document: {
      getElementById(id) { return nodi[id] || (nodi[id] = elemento()); },
      createElement() { return elemento(); },
      querySelectorAll() { return []; },
    },
    vis: {
      DataSet: class { constructor(items) { this.items = items; } },
      Network: class {
        constructor(container, data, options) {
          this.data = data; this.options = options; reti.ultima = this;
          (reti.tutte = reti.tutte || []).push(this);
        }
        on() {} destroy() {} selectNodes() {} focus() {}
      },
    },
    fetch: async (url) => ({
      ok: true, status: 200,
      json: async () => (url.startsWith('/api/graphs') ? {root: '/tmp/finto', graphs: elenco}
        : url.startsWith('/api/status') ? stato : grafo),
      text: async () => '# Report\n',
    }),
    alert: (m) => { throw new Error('la pagina ha aperto un alert: ' + m); },
    console,
  };
  vm.createContext(ctx);
  vm.runInContext(script, ctx); // esegue anche il boot() finale
  return {ctx, nodi, reti};
}

const attendi = () => new Promise((r) => setTimeout(r, 20));

(async () => {
  // 1. grafo stantio: la pagina lo dice e mette i comandi per rigenerare
  const c = contesto();
  await attendi();
  assert.equal(c.nodi.fresh.textContent, 'stantio');
  assert.equal(c.nodi.fresh.className, 'pill warn');
  assert.equal(c.nodi.banner.style.display, 'block');
  assert.match(c.nodi.banner.innerHTML, /abc1234def/);
  assert.match(c.nodi.banner.innerHTML, /\.\/scripts\/graphify\.sh update \./);
  assert.match(c.nodi.foot.textContent, /4 nodi · 4 archi/);
  assert.match(c.nodi.foot.textContent, /etichette derivate: 1\/2/);

  // 2. l'elenco community: il nome derivato al posto del segnaposto, la
  //    directory accanto a un nome dichiarato, e la ricerca che filtra
  assert.match(c.nodi.comList.innerHTML, /push_log · control-plane/);
  assert.match(c.nodi.comList.innerHTML, /derivata/);
  assert.match(c.nodi.comList.innerHTML, /Documenti e ricerca/);
  assert.match(c.nodi.comList.innerHTML, /· docs/);
  assert.equal(c.nodi.comCount.textContent, '2/2');
  c.nodi.q.value = 'log';
  c.ctx.renderCommunities();
  assert.equal(c.nodi.comCount.textContent, '1/2');
  assert.match(c.nodi.comList.innerHTML, /push_log/);
  assert.ok(!/Documenti e ricerca/.test(c.nodi.comList.innerHTML),
    'la ricerca su "log" non deve lasciare la community dei documenti');
  c.nodi.q.value = '';
  c.ctx.renderCommunities();

  // 3. panoramica: un nodo per community, un arco per coppia di community
  //    (a-c e b-c si sommano in un solo arco pesato 2; d-c resta dentro la 1)
  const panoramica = c.reti.ultima;
  assert.equal(panoramica.data.nodes.items.length, 2);
  assert.equal(panoramica.data.edges.items.length, 1);
  assert.equal(panoramica.data.edges.items[0].value, 2);
  assert.match(panoramica.data.nodes.items[0].title, /push_log · control-plane/);
  assert.match(c.nodi.legend.innerHTML, /Panoramica/);

  // 4. dettaglio di una community: solo i suoi nodi e i suoi archi interni
  c.ctx.drawCommunity(0);
  const dettaglio = c.reti.ultima;
  // join e non deepEqual: l'array nasce dentro il contesto vm, con un altro
  // prototipo, e deepStrictEqual lo considererebbe diverso da uno del test.
  assert.equal(dettaglio.data.nodes.items.map((n) => n.id).sort().join(','), 'a,b');
  assert.equal(dettaglio.data.edges.items.length, 1); // a -> b
  assert.match(c.nodi.legend.innerHTML, /push_log · control-plane/);
  assert.match(c.nodi.inspect.innerHTML, /hub/);
  assert.match(c.nodi.inspect.innerHTML, /push_log/);

  // 5. ispettore di un simbolo: file, community e chi lo chiama
  c.ctx.inspectNode('c');
  assert.match(c.nodi.inspect.innerHTML, /docs\/graphify\.md:L1/);
  assert.match(c.nodi.inspect.innerHTML, /Documenti e ricerca/);
  assert.match(c.nodi.inspect.innerHTML, /Chiamato da \(3\)/);
  assert.match(c.nodi.inspect.innerHTML, /&larr; push_log/);
  c.ctx.inspectNode('inesistente');
  assert.match(c.nodi.inspect.innerHTML, /non trovato/);

  // 6. grafo allineato a HEAD: niente banner, pill verde (non un allarme)
  const fresco = contesto({stato: {...STATO, stale: false, head: 'abc1234'}});
  await attendi();
  assert.equal(fresco.nodi.fresh.className, 'pill ok');
  assert.equal(fresco.nodi.banner.style.display, 'none');

  // 7. freschezza ignota e nessun grafo: due stati che la pagina dice a parole
  const ignoto = contesto({stato: {...STATO, stale: null, built_at_commit: null}});
  await attendi();
  assert.equal(ignoto.nodi.fresh.textContent, 'freschezza ignota');
  assert.match(ignoto.nodi.banner.innerHTML, /non posso dire se è stantio/);
  const vuoto = contesto({elenco: []});
  await attendi();
  assert.match(vuoto.nodi.comList.innerHTML, /Nessun grafo trovato/);
  assert.match(vuoto.nodi.comList.innerHTML, /graphify\.sh/);

  console.log('graphify surface page tests passed');
})().catch((error) => { console.error(error); process.exitCode = 1; });
