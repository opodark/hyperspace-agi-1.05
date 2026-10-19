// SPDX-License-Identifier: Apache-2.0
// tests/anna_mascot.test.cjs
// Test suite per la mascotte anime di Anna (web-node/src/anna-mascot.js).
// Verifica isolamento, gestione delle preferenze, shortcuts, animazioni e safe degradation.

const fs = require('fs');
const test = require('node:test');
const assert = require('node:assert/strict');

const SORGENTE = fs.readFileSync('web-node/src/anna-mascot.js', 'utf8');

test('anna-mascot.js contiene l\'header di licenza SPDX Apache-2.0', () => {
  assert.ok(SORGENTE.includes('SPDX-License-Identifier: Apache-2.0'));
});

test('anna-mascot.js definisce i tratti canonici di Anna (ChickMixFlat, 00MESH, citazioni)', () => {
  assert.ok(SORGENTE.includes('ChickMixFlat'));
  assert.ok(SORGENTE.includes('ANNA_QUOTES'));
  assert.ok(SORGENTE.includes('Alt+Shift+A'));
});

test('anna-mascot.js include tutte le macchine a stati fisiche (idle, walk, run, sit, drag, fall)', () => {
  for (const st of ['idle', 'walk', 'run', 'sit', 'drag', 'fall']) {
    assert.ok(SORGENTE.includes(`state-${st}`) || SORGENTE.includes(`'${st}'`), `manca lo stato ${st}`);
  }
});

test('anna-mascot.js rispetta prefers-reduced-motion e session storage', () => {
  assert.ok(SORGENTE.includes('(prefers-reduced-motion: reduce)'));
  assert.ok(SORGENTE.includes('sessionStorage'));
});
