// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "panoramica-2026-10-29", "title": "00MESH Panoramica R&D", "aria": "Animazione di 60 secondi che riassume tre giorni di R&D di HyperSpace AGI 1.05, dal 27 al 29 ottobre: dieci scene prese dai cinque reel — endospore crittografiche, memoria stigmergica, circuit breaker, controller PID, Agent-Reach, memoria Hermes, bozze speculative, heartbeat a quorum, Mutation Guard e moduli promossi — poi il diario dei cinque reel e il logo 00MESH.", "dur": 60, "formats": ["9:16", "16:9"], "parts": ["rd-2026-10-27", "resilienza-2026-10-28", "pipeline-2026-10-28", "endurance-2026-10-28", "atomic-2026-10-29"]}
/* Panoramica di 60 s: non ridisegna nulla, rimonta le scene dei cinque reel spostandole nel tempo.
   Ogni scena gira col suo tempo originale (t - inizio slot + inizio della scena nel suo reel)
   e prende il numero della panoramica (HNUM). In 16:9 la fascia REEL.crop va a destra. */

const DIARY = { // reel → [titolo, data] per l'etichetta di provenienza e il diario finale
  'rd-2026-10-27': ['Cinque filoni R&D', '27.10'],
  'resilienza-2026-10-28': ['Resilienza', '28.10'],
  'pipeline-2026-10-28': ['Pipeline di ricerca', '28.10'],
  'endurance-2026-10-28': ['Endurance', '28.10'],
  'atomic-2026-10-29': ['Atomic Sprint', '29.10'],
};
const PICK = [['rd-2026-10-27', 2], ['rd-2026-10-27', 3], ['resilienza-2026-10-28', 1], ['resilienza-2026-10-28', 3],
  ['pipeline-2026-10-28', 1], ['pipeline-2026-10-28', 4], ['endurance-2026-10-28', 1], ['endurance-2026-10-28', 2],
  ['atomic-2026-10-29', 3], ['atomic-2026-10-29', 4]];
const SLOTS = (() => { // ogni scena dura quanto nel suo reel; 0,2 s di sovrapposizione come nei reel da 30 s
  let at = 6.4;
  return PICK.map(([id, k]) => {
    const src = PARTS[id], s = src.sc[k - 1], len = s.b - s.a, slot = { id, src: src.scenes[k], s0: s.a, at, len };
    at += len - .2;
    return slot;
  });
})();
const RECAP_A = 52.0, RECAP_B = 57.6;

function play(i, t) {
  const { id, src, s0, at, len } = SLOTS[i];
  if (t < at - .05 || t > at + len + .05) return;
  HNUM = String(i + 1).padStart(2, '0');
  try { src(t - at + s0); } finally { HNUM = null; }
  // etichetta di provenienza: in verticale sopra il titolo, in orizzontale sotto
  const e = env(t, at, at + len, .35, .35), [title, day] = DIARY[id];
  onMain(() => {
    if (LAND) {
      T('DAL REEL «' + title.toUpperCase() + '» · ' + day, 80, 640, { size: 20, col: C.mute, ls: 3, a: e * P(t, at + .6, at + 1.0) });
      T(PARTS[id].tagline, 80, 700, { w: 500, size: 34, fam: FD, col: '#C9CCC4', a: e * P(t, at + .8, at + 1.2) });
    } else T('DAL REEL «' + title.toUpperCase() + '» · ' + day, 80, 272, { size: 18, col: C.mute, ls: 3, a: e * P(t, at + .6, at + 1.0) });
  });
}
function endospore(t) { play(0, t); }
function swarm(t) { play(1, t); }
function breaker(t) { play(2, t); }
function pid(t) { play(3, t); }
function reach(t) { play(4, t); }
function memory(t) { play(5, t); }
function drafts(t) { play(6, t); }
function heartbeat(t) { play(7, t); }
function guard(t) { play(8, t); }
function modules(t) { play(9, t); }

/* ---------- headline (3.0 – 6.6s) ---------- */
function headline(t) {
  const a = 3.0, b = 6.6;
  if (t < a || t > b) return;
  onMain(() => {
    const e = env(t, a, b, .3, .3);
    x.save(); x.globalAlpha = e;
    const ky = LAND ? 330 : 640, y0 = LAND ? 470 : 790, maxW = LAND ? 1500 : 920, max = LAND ? 132 : 124;
    const kick = 'R&D LOG · 27 – 29 OTTOBRE 2026';
    T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .6))), 80, ky, { w: 700, size: 24, col: C.acc, ls: 3 });
    const L = LAND ? [[['Tre', C.ink], ['giorni', C.ink], ['di', C.ink], ['R&D', C.acc]], [['in', C.ink], ['sessanta', C.ac2], ['secondi.', C.ac2]]]
      : [[['Tre', C.ink], ['giorni', C.ink]], [['di', C.ink], ['R&D', C.acc]], [['in', C.ink], ['sessanta', C.ac2]], [['secondi.', C.ac2]]];
    const lineW = (ln, s) => ln.reduce((acc, [w]) => acc + measure(w, 900, s, FD, -2), 0) + s * .27 * (ln.length - 1);
    const widest = Math.max(...L.map(ln => lineW(ln, max)));
    const size = Math.min(max, max * maxW / widest), LH = size * 1.14;
    words(t, L, 80, y0, LH, size, a + .2, .1, .9, b - .5);
    const yb = y0 + (L.length - 1) * LH;
    seg(80, yb + 90, 420, yb + 90, { col: C.acc, lw: 6, p: oExpo(P(t, 4.8, 5.4)) * (1 - iCub(P(t, 6.1, 6.5))) });
    T('Dieci scene da cinque reel, tutte disegnate dal codice.', 80, yb + 170, { w: 500, size: 40, fam: FD, col: C.mute, a: oCub(P(t, 5.0, 5.5)) * (1 - P(t, 6.1, 6.4)) });
    x.restore();
  });
}

/* ---------- diario dei cinque reel (52.0 – 57.6s) ---------- */
function diary(t) {
  const a = RECAP_A, b = RECAP_B;
  if (t < a || t > b) return;
  header(t, a, b, '11', '11 — IL DIARIO', [[['Tre giorni,', C.ink]], [['cinque reel.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  Object.entries(DIARY).forEach(([id, [title, day]], i) => {
    const t0 = a + .5 + i * .32, y = 690 + i * 164, p = oCub(P(t, t0, t0 + .35));
    if (p <= 0) return;
    x.save(); x.globalAlpha *= p; x.translate((1 - p) * -40, 0);
    seg(84, y + 8, 84, y + 132, { col: i === 4 ? C.acc : '#3A3E44', lw: 4 });
    T(day + '.2026', 112, y + 34, { w: 700, size: 22, col: C.acc, ls: 2 });
    T(title, 112, y + 90, { w: 900, size: 52, fam: FD, col: C.ink, ls: -1 });
    T(PARTS[id].tagline, 112, y + 130, { size: 22, col: C.mute });
    x.restore();
  });
  x.restore();
}

const REEL = {
  date: '27–29.10.2026',
  tagline: 'La mesh che cresce ogni notte.',
  crop: [600, 1580],
  sc: [...SLOTS.map((s, i) => ({ a: s.at, b: s.at + s.len, n: String(i + 1).padStart(2, '0') })), { a: RECAP_A, b: RECAP_B, n: '11' }],
  cuts: [3.1, 6.5, 10.9, 15.3, 19.9, 24.5, 29.1, 33.7, 38.3, 42.9, 47.5, 52.1, 57.5],
  scenes: [headline, endospore, swarm, breaker, pid, reach, memory, drafts, heartbeat, guard, modules, diary]
};
