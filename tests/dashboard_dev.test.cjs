// SPDX-License-Identifier: Apache-2.0
// La scheda "Sviluppo": raccoglie Forge, Dev Sandbox, il grafo del repository e
// il candidato REA in un solo posto. Questo test verifica che il pannello esista,
// che rimandi alle schede giuste e che la sezione REA resti onesta (candidato,
// non collegato) invece di promettere un'integrazione che non c'e'.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'control-plane', 'dashboard.html'), 'utf8');

// il blocco inline deve restare JS valido dopo l'aggiunta del pannello
new vm.Script(html.match(/<script>([\s\S]*?)<\/script>/)[1]);

// 1. pannello e voce di menu
assert.match(html, /id="panel-dev"/);
assert.match(html, /showPanel\('dev',this\)/);

// 2. rimandi alle schede piene (che devono continuare a esistere)
assert.match(html, /<a class="dev-card" href="#forge">/);
assert.match(html, /<a class="dev-card" href="#sandbox">/);
assert.match(html, /id="panel-forge"/);
assert.match(html, /id="panel-sandbox"/);

// 3. grafo del repository: comando e artefatto spiegati, non link rotto
assert.match(html, /graphify\.sh/);
assert.match(html, /graphify-out\/graph\.html/);

// 4. REA: repo, badge "candidato" e i due documenti che ne fissano i limiti
assert.match(html, /github\.com\/morluto\/rea/);
assert.match(html, /class="rea-badge candidate"/);
assert.match(html, /docs\/rea-pilot\.md/);
assert.match(html, /docs\/development-security-tools\.md/);

console.log('dashboard dev panel tests passed');
