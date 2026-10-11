// SPDX-License-Identifier: Apache-2.0
// La scheda "Sviluppo": raccoglie Forge, Dev Sandbox, il grafo del repository e
// la superficie REA in un solo posto. Questo test verifica che il pannello
// esista, che rimandi alle schede giuste e che la sezione REA resti onesta
// (opzionale, da installare) invece di promettere quello che non c'e'.
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

// 3b. il grafo ora ha una superficie: la card la apre dal catalogo /surfaces,
//     così host e porta non vengono copiati nel markup (fonte unica) e la porta
//     scritta nella card resta quella vera.
assert.match(html, /onclick="openSurface\('graphify'\)"/);
assert.match(html, /async function openSurface\(id\)/);
assert.match(html, /fetch\('\/surfaces'\)/);
assert.match(html, /:7871/);

// 4. REA: repo, badge "opzionale", la superficie locale e i documenti che ne
//    fissano i limiti. La card apre la superficie dal catalogo /surfaces (fonte
//    unica di host e porta), come fa quella di graphify.
assert.match(html, /github\.com\/morluto\/rea/);
assert.match(html, /class="rea-badge candidate"/);
assert.match(html, /onclick="openSurface\('rea'\)"/);
assert.match(html, /:7872/);
assert.match(html, /docs\/rea-surface\.md/);
assert.match(html, /docs\/rea-pilot\.md/);
assert.match(html, /docs\/development-security-tools\.md/);

console.log('dashboard dev panel tests passed');
