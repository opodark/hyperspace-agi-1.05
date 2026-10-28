// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "pipeline-2026-10-28", "title": "00MESH Reel Pipeline", "aria": "Animazione di 30 secondi sulla pipeline di ricerca di HyperSpace AGI 1.05: trend scouting con Agent-Reach su sei canali, ricerca notturna che produce prototipi validati, promozione in produzione con AST, compile, pytest e rollback, memoria unica Hermes con tracciabilità causale, con chiusura sul logo 00MESH."}
/* Pipeline R&D al 28/10/2026: Agent-Reach → prototipi notturni → promozione in shared/ → memoria Hermes.
   Numeri dal repository: 24 ispirazioni (trend_inspirations.json, 28/10), 141 file proto_*.py,
   15 promozioni reali in 10 moduli di shared/ (promotions.jsonl, esclusi test e mock). */

/* ---------- scene 1 · headline (3.0 – 6.6s) ---------- */
function headline(t) {
  const a = 3.0, b = 6.6;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .3);
  x.save(); x.globalAlpha = e;
  const kick = 'R&D LOG · PIPELINE · 28 OTTOBRE 2026';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .6))), 80, 640, { w: 700, size: 24, col: C.acc, ls: 3 });
  const L = [[['Legge', C.ink], ['il', C.ink], ['mondo,', C.ink]], [['prototipa', C.acc], ['di', C.acc], ['notte,', C.acc]],
    [['promuove', C.ink], ['ciò', C.ink], ['che', C.ink], ['regge', C.ink]], [['e', C.ink], ['lo', C.ac2], ['ricorda.', C.ac2]]];
  const lineW = (ln, s) => ln.reduce((acc, [w]) => acc + measure(w, 900, s, FD, -2), 0) + s * .27 * (ln.length - 1);
  const widest = Math.max(...L.map(ln => lineW(ln, 124)));
  const size = Math.min(124, 124 * 920 / widest), LH = size * 1.14;
  words(t, L, 80, 790, LH, size, a + .2, .1, .9, b - .5);
  const yb = 790 + 3 * LH;
  seg(80, yb + 90, 420, yb + 90, { col: C.acc, lw: 6, p: oExpo(P(t, 4.8, 5.4)) * (1 - iCub(P(t, 6.1, 6.5))) });
  T('Agent-Reach → prototipi → shared/ → Hermes.', 80, yb + 170, { w: 500, size: 40, fam: FD, col: C.mute, a: oCub(P(t, 5.0, 5.5)) * (1 - P(t, 6.1, 6.4)) });
  x.restore();
}

/* ---------- scene 2 · agent-reach (6.4 – 11.2s) ---------- */
const CH = [['arXiv', 6, C.acc], ['Scholar', 6, C.acc], ['Reddit', 3, C.ac2], ['Web', 3, C.ink], ['YouTube', 3, C.ac2], ['GitHub', 3, C.ink]];
const HITS = (() => { // un'ispirazione alla volta, alternando i canali finché ognuno ha dato i suoi
  const left = CH.map(c => c[1]), out = [];
  for (let r = 0; out.length < 24; r++) for (let k = 0; k < CH.length; k++) if (left[k] > 0) { left[k]--; out.push(k); }
  return out.map((k, i) => [7.4 + i * .12, k]);
})();
function reach(t) {
  const a = 6.4, b = 11.2;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — AGENT-REACH · TREND SCOUTING', [[['Il radar', C.ink]], [['a costo zero', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const CX = 220, Y0 = 700, DY = 92, BOX = [640, 760, 360, 300];
  const bc = [BOX[0] + BOX[2] / 2, BOX[1] + BOX[3] / 2];
  CH.forEach(([n, k, col], i) => {
    const s = oBack(P(t, 6.8 + i * .08, 7.1 + i * .08)), y = Y0 + i * DY;
    pill(CX, y, 220, 60, n, { s, size: 22, stroke: col, col: C.ink });
    seg(CX + 116, y, BOX[0] - 10, bc[1], { col: C.line, lw: 2, a: clamp(s) * .9, dash: [4, 10] });
  });
  let got = 0;
  HITS.forEach(([te, k]) => {
    if (t >= te + .5) { got++; return; }
    if (t < te) return;
    const p = ioCub(P(t, te, te + .5)), y = Y0 + k * DY;
    circ(lerp(CX + 116, BOX[0] - 10, p), lerp(y, bc[1], p), 8, { fill: CH[k][2] });
  });
  const ba = P(t, 7.0, 7.4);
  x.save(); x.globalAlpha *= ba;
  rrect(...BOX, 24); x.fillStyle = C.panel; x.fill(); x.strokeStyle = got === 24 ? C.acc : '#3A3E44'; x.lineWidth = 2.5; x.stroke();
  T('trend_inspirations.json', bc[0], BOX[1] - 22, { size: 20, al: 'center', col: C.mute });
  T(String(got).padStart(2, '0'), bc[0], bc[1] + 40, { w: 900, size: 150, fam: FD, al: 'center', col: got === 24 ? C.acc : C.ink, ls: -4 });
  T('ispirazioni', bc[0], bc[1] + 100, { size: 22, al: 'center', col: C.mute });
  x.restore();
  const oa = P(t, 10.4, 10.8);
  arrow(bc[0] - 90, BOX[1] + BOX[3] + 16, bc[0] - 120, BOX[1] + BOX[3] + 86, oa, C.acc);
  arrow(bc[0] + 90, BOX[1] + BOX[3] + 16, bc[0] + 120, BOX[1] + BOX[3] + 86, oa, C.ac2);
  T('missioni', bc[0] - 130, BOX[1] + BOX[3] + 124, { size: 22, al: 'center', col: C.acc, a: oa });
  T('sogni', bc[0] + 130, BOX[1] + BOX[3] + 124, { size: 22, al: 'center', col: C.ac2, a: oa });
  T('trend_scout_reach.py --save', 540, 1330, { size: 24, al: 'center', a: P(t, 7.6, 8.0) });
  T('testi ripuliti · nessuna credenziale importata', 540, 1380, { size: 22, al: 'center', col: C.mute, a: P(t, 7.8, 8.2) });
  badge(t, '24 ISPIRAZIONI · 6 CANALI', 1490, 10.7);
  x.restore();
}

/* ---------- scene 3 · ricerca notturna (11.0 – 15.8s) ---------- */
const PROTOS = ['proto_modular_intellect_1792920337.py', 'proto_swarm_emergence_1792923871.py', 'proto_symbolic_causal_mesh_1792927875.py',
  'proto_aleksander_axioms_1792931402.py', 'proto_tokenbucketratelimiter_1793019924.py', 'proto_adaptivemeshcircuitbreaker_1793022231.py'];
function night(t) {
  const a = 11.0, b = 15.8;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — RICERCA NOTTURNA', [[['Studia', C.ink]], [['mentre dormi', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  // luna e finestra notturna
  const ma = P(t, 11.3, 11.7);
  x.save(); x.globalAlpha *= ma;
  circ(920, 400, 44, { fill: C.ac2 }); circ(940, 388, 40, { fill: C.bg });
  x.restore();
  // terminale
  const TX = 80, TY = 680, TW = 920, TH = 470, ta = P(t, 11.4, 11.8);
  x.save(); x.globalAlpha *= ta;
  rrect(TX, TY, TW, TH, 22); x.fillStyle = C.term; x.fill(); x.strokeStyle = '#23262B'; x.lineWidth = 2; x.stroke();
  [ERR, '#E8C547', C.acc].forEach((c, i) => circ(TX + 34 + i * 26, TY + 30, 7, { fill: c, a: .8 }));
  T('data/research/prototypes/', TX + TW - 30, TY + 38, { size: 20, al: 'right', col: C.mute });
  seg(TX, TY + 62, TX + TW, TY + 62, { col: '#1A1D21', lw: 2 });
  x.restore();
  PROTOS.forEach((f, i) => {
    const s = 11.9 + i * .38, y = TY + 112 + i * 58;
    if (t < s) return;
    const n = Math.floor(f.length * P(t, s, s + .3));
    T('$', TX + 34, y, { size: 22, col: C.acc });
    T(f.slice(0, n), TX + 64, y, { size: 22, col: C.ink });
    const ok = P(t, s + .35, s + .5);
    T('✓ AST', TX + TW - 34, y, { w: 700, size: 22, al: 'right', col: C.acc, a: ok });
  });
  const blink = Math.floor(t * 3) % 2 === 0 && t > 14.2;
  if (blink) T('▍', TX + 34, TY + 112 + 6 * 58, { size: 22, col: C.acc });
  const n = Math.round(141 * oCub(P(t, 12.0, 14.6)));
  T(String(n), 80, 1320, { w: 900, size: 120, fam: FD, col: n === 141 ? C.acc : C.ink, ls: -4, a: P(t, 11.9, 12.2) });
  T('prototipi scritti e validati', 80 + measure('141', 900, 120, FD, -4) + 28, 1290, { size: 24, col: C.ink, a: P(t, 12.1, 12.4) });
  T('agi_research_engine · turni notturni sui nodi', 80 + measure('141', 900, 120, FD, -4) + 28, 1326, { size: 20, col: C.mute, a: P(t, 12.2, 12.5) });
  badge(t, 'DOSSIER · PROTOTIPI · SINTESI', 1470, 14.8, C.ac2);
  x.restore();
}

/* ---------- scene 4 · promozione (15.6 – 20.4s) ---------- */
const GATES = ['ast.parse', 'backup .bak', 'compile()', 'pytest'], GY = [690, 790, 890, 990];
const RUNS = [[16.2, 'circuit_breaker', true], [17.2, 'test rosso', false], [18.2, 'rate_limiter', true]];
const OK_XY = [290, 1150], KO_XY = [790, 1150];
function runPos(t, s, ok) { // giù attraverso i cancelli, poi a sinistra (shared/) o a destra (rollback)
  if (t < s) return null;
  const d = P(t, s, s + .9), br = P(t, s + .95, s + 1.35);
  if (br <= 0) return [540, lerp(630, GY[3], ioCub(d))];
  const D = ok ? OK_XY : KO_XY;
  return [lerp(540, D[0], ioCub(br)), lerp(GY[3], D[1] - 50, ioCub(br))];
}
function promote(t) {
  const a = 15.6, b = 20.4;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — PROMOZIONE IN PRODUZIONE', [[['Passa solo', C.ink]], [['ciò che regge', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  seg(540, 640, 540, GY[3], { col: C.line, lw: 3, a: P(t, 15.9, 16.2), dash: [6, 10] });
  // stato dei cancelli: si accendono al passaggio dell'ultima corsa partita
  let cur = null; for (const r of RUNS) if (t >= r[0]) cur = r;
  GATES.forEach((g, i) => {
    let fill = '#14171B', stroke = '#3A3E44', col = '#9EA39A';
    if (cur) {
      const p = runPos(t, cur[0], cur[2]);
      const reached = p && (p[1] >= GY[i] - 20 || P(t, cur[0] + .95, cur[0] + 1.35) > 0);
      const fail = !cur[2] && i === 3;
      if (reached) { stroke = fail ? ERR : C.acc; col = fail ? ERR : C.acc; fill = fail ? '#2A1512' : C.tint; }
    }
    pill(540, GY[i], 340, 64, g, { s: oBack(P(t, 15.9 + i * .08, 16.2 + i * .08)), size: 24, bold: true, fill, stroke, col });
  });
  // uscite
  const xa = P(t, 16.0, 16.4);
  let nOk = 0, nKo = 0;
  RUNS.forEach(([s, , ok]) => { if (t >= s + 1.35) ok ? nOk++ : nKo++; });
  pill(OK_XY[0], OK_XY[1], 300, 70, `shared/ · ${nOk}`, { s: xa, size: 26, bold: true, fill: C.tint, stroke: C.acc, col: C.acc });
  pill(KO_XY[0], KO_XY[1], 300, 70, nKo ? '↺ rollback' : 'rollback', { s: xa, size: 26, bold: true, fill: nKo ? '#2A1512' : '#14171B', stroke: nKo ? ERR : '#3A3E44', col: nKo ? ERR : '#9EA39A' });
  // corse
  RUNS.forEach(([s, name, ok]) => {
    const p = runPos(t, s, ok);
    if (!p || t > s + 1.6) return;
    const fail = !ok && t >= s + .8, col = fail ? ERR : C.acc;
    circ(p[0], p[1], 13, { fill: col, a: 1 - P(t, s + 1.35, s + 1.6) });
    if (t < s + .95) T(name, 540 + 190, p[1] + 8, { size: 20, col: fail ? ERR : C.ink, a: P(t, s, s + .15) });
  });
  T('promote_research_prototype.py', 540, 1300, { size: 24, al: 'center', a: P(t, 16.4, 16.8) });
  T('fail-closed · rollback istantaneo · registro promotions.jsonl', 540, 1350, { size: 22, al: 'center', col: C.mute, a: P(t, 16.6, 17.0) });
  badge(t, '15 PROMOZIONI · 10 MODULI', 1460, 19.5);
  x.restore();
}

/* ---------- scene 5 · memoria hermes (20.2 – 25.0s) ---------- */
const SAT = ['MEMORY.md', 'USER.md', 'state.db · FTS5', 'skill'];
const CHAIN = ['trend', 'missione', 'prototipo', 'shared/'];
function memory(t) {
  const a = 20.2, b = 25.0;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — MEMORIA HERMES', [[['Una sola', C.ink]], [['memoria', C.ac2]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const HC = [540, 870], cs = oBack(P(t, 20.5, 20.9));
  // satelliti in orbita lenta
  SAT.forEach((s, i) => {
    const g = -Math.PI / 2 + i * Math.PI / 2 + Math.PI / 4 + t * .12, R = 220;
    const px = HC[0] + Math.cos(g) * R * 1.4, py = HC[1] + Math.sin(g) * R * .82;
    const sa = P(t, 20.8 + i * .12, 21.1 + i * .12);
    seg(HC[0], HC[1], px, py, { col: C.ac2, lw: 2, a: sa * .5, dash: [6, 10], off: -t * 50 });
    pill(px, py, measure(s, 400, 22, FM) + 48, 56, s, { s: oBack(sa), size: 22, stroke: C.ac2, col: C.ink });
  });
  for (let k = 0; k < 2; k++) { const u = (t * .6 + k * .5) % 1; circ(HC[0], HC[1], 92 + u * 70, { stroke: C.ac2, lw: 2, a: (1 - u) * .7 * clamp(cs) }); }
  x.save(); x.translate(HC[0], HC[1]); x.scale(cs, cs);
  circ(0, 0, 92, { fill: C.panel, stroke: C.ac2, lw: 4 });
  T('HERMES', 0, 4, { w: 900, size: 32, fam: FD, al: 'center', col: C.ink });
  T('source of truth', 0, 36, { size: 15, al: 'center', col: C.mute, a: P(t, 21.0, 21.4) });
  x.restore();
  // catena causale
  const CY = 1200, CXS = [180, 420, 660, 900];
  T('CausalMemoryGraph.trace_lineage()', 540, CY - 66, { size: 22, al: 'center', col: C.ink, a: P(t, 21.8, 22.2) });
  CHAIN.forEach((c, i) => {
    const s = 22.2 + i * .45, lit = t >= s + .25;
    if (i) arrow(CXS[i - 1] + 97, CY, CXS[i] - 103, CY, ioCub(P(t, s, s + .25)), C.acc);
    pill(CXS[i], CY, 186, 58, c, { s: oBack(P(t, s, s + .3)), size: 22, bold: lit, fill: lit ? C.tint : '#14171B', stroke: lit ? C.acc : '#3A3E44', col: lit ? C.acc : C.ink });
  });
  T('i sogni entrano solo dopo la review', 540, 1320, { size: 22, al: 'center', col: C.mute, a: P(t, 23.2, 23.6) });
  badge(t, 'UNA MEMORIA · NESSUN DOPPIONE', 1420, 24.0, C.ac2);
  x.restore();
}

/* ---------- scene 6 · numeri (24.8 – 27.6s) ---------- */
const NUMS = [[24, 'ispirazioni', 290, 800], [141, 'prototipi', 790, 800], [15, 'promozioni', 790, 1120], [1, 'memoria', 290, 1120]];
function numbers(t) {
  const a = 24.8, b = 27.6;
  if (t < a || t > b) return;
  header(t, a, b, '05', '05 — LA PIPELINE', [[['Dal mondo', C.ink]], [['alla memoria.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  NUMS.forEach(([v, lb, cx, cy], i) => {
    const s = 25.1 + i * .25, p = oCub(P(t, s, s + .8)), n = Math.round(v * p);
    T(String(n), cx, cy, { w: 900, size: 170, fam: FD, al: 'center', col: n === v ? (i === 3 ? C.ac2 : C.acc) : C.ink, ls: -6, a: P(t, s, s + .2) });
    T(lb, cx, cy + 56, { size: 24, al: 'center', col: C.mute, ls: 4, a: P(t, s + .1, s + .3) });
  });
  arrow(450, 740, 620, 740, ioCub(P(t, 25.4, 25.7)), C.line);
  arrow(790, 880, 790, 990, ioCub(P(t, 25.6, 25.9)), C.line);
  arrow(620, 1060, 450, 1060, ioCub(P(t, 25.9, 26.2)), C.line);
  x.restore();
}

const REEL = {
  date: '28.10.2026',
  tagline: 'Legge il mondo, ricorda ciò che regge.',
  sc: [{ a: 6.4, b: 11.2, n: '01' }, { a: 11.0, b: 15.8, n: '02' }, { a: 15.6, b: 20.4, n: '03' }, { a: 20.2, b: 25.0, n: '04' }, { a: 24.8, b: 27.6, n: '05' }],
  cuts: [3.1, 6.5, 11.1, 15.7, 20.3, 24.9, 27.5],
  scenes: [headline, reach, night, promote, memory, numbers]
};
