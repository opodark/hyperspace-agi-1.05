// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "atomic-2026-10-29", "title": "00MESH Reel Atomic Sprint", "aria": "Animazione di 30 secondi sullo sprint del 29 ottobre di HyperSpace AGI 1.05: i tre pattern ripresi da Atomic Agent (grammatiche GBNF, traccia NDJSON replayabile, Mutation Guard), i tre moduli promossi in shared/ — isolamento dei nodi degradati, cache semantica cross-agente, work stealing a priorità — e 15 test superati, con chiusura sul logo 00MESH."}
/* R&D log del 29/10/2026 (commit 5bb44d0): shared/gbnf_grammar.py, shared/ndjson_tracer.py, shared/mutation_guard.py
   e i moduli promossi da scripts/diagnostics/mesh_dual_node_atomic_sprint.py.
   Dati veri: data/traces/atomic_dual_sprint_20261029_091406.ndjson (10 eventi, tempi relativi dai `ts`),
   data/proposals/prop_*.json (stato EXECUTED), soglie 200 ms / 5%, similarità ≥ 0.8, test 5+3+4+3. */

/* ---------- scene 1 · headline (3.0 – 6.6s) ---------- */
function headline(t) {
  const a = 3.0, b = 6.6;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .3);
  x.save(); x.globalAlpha = e;
  const kick = 'R&D LOG · ATOMIC SPRINT · 29 OTTOBRE 2026';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .6))), 80, 640, { w: 700, size: 24, col: C.acc, ls: 3 });
  const L = [[['Tre', C.ink], ['pattern', C.ink]], [['da', C.ink], ['Atomic', C.acc], ['Agent,', C.acc]],
    [['tre', C.ink], ['moduli', C.ink]], [['promossi.', C.ac2]]];
  const lineW = (ln, s) => ln.reduce((acc, [w]) => acc + measure(w, 900, s, FD, -2), 0) + s * .27 * (ln.length - 1);
  const widest = Math.max(...L.map(ln => lineW(ln, 124)));
  const size = Math.min(124, 124 * 920 / widest), LH = size * 1.14;
  words(t, L, 80, 790, LH, size, a + .2, .1, .9, b - .5);
  const yb = 790 + 3 * LH;
  seg(80, yb + 90, 420, yb + 90, { col: C.acc, lw: 6, p: oExpo(P(t, 4.8, 5.4)) * (1 - iCub(P(t, 6.1, 6.5))) });
  T('Revisione di Flint 40B sull’ASUS. 15 test verdi.', 80, yb + 170, { w: 500, size: 40, fam: FD, col: C.mute, a: oCub(P(t, 5.0, 5.5)) * (1 - P(t, 6.1, 6.4)) });
  x.restore();
}

/* ---------- scene 2 · GBNF (6.4 – 11.2s) ---------- */
const GRAMMAR = [ // build_schema_grammar(review_schema), abbreviata: [testo, indice del campo o -1]
  [['root ::= "{" ', -1], ['"verdict"', 0], [': string ,', -1]],
  [['  ', -1], ['"score"', 1], [': number , ', -1], ['"summary"', 2], [': string ,', -1]],
  [['  ', -1], ['"thread_safety"', 3], [': string ,', -1]],
  [['  ', -1], ['"recommendations"', 4], [': string "}"', -1]],
];
const OUT = [ // righe della risposta: [testo, scartato prima, larghezza del valore, colore del valore]
  ['{', 'Ecco la mia analisi:', 0],
  ['  "verdict": ', null, 220, C.ink],
  ['  "score": ', '"nove"', 70, C.acc],
  ['  "summary": ', null, 380, C.ink],
  ['  "thread_safety": ', null, 260, C.ink],
  ['  "recommendations": ', null, 300, C.ink],
  ['}', null, 0],
];
const G_T0 = 7.6, G_ST = .36, G_REJ = .3; // inizio, passo per riga, quanto resta visibile il token scartato
function gbnf(t) {
  const a = 6.4, b = 11.2;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — VINCOLI GRAMMATICALI GBNF', [[['Solo JSON,', C.ink]], [['niente sorprese', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  // tempo di ogni riga: chi ha un token scartato aspetta che sparisca
  const tl = []; let tc = G_T0;
  OUT.forEach(([, rej]) => { tl.push([tc, rej ? tc + G_REJ : tc]); tc += G_ST + (rej ? G_REJ : 0); });
  const field = OUT.findIndex((_, i) => i > 0 && i < 6 && t < tl[i][1]); // campo in corso
  // grammatica
  const ga = P(t, 6.8, 7.2), GY = 690, GH = 168;
  T('V16 · Flint 40B · revisione vincolata', 80, GY - 22, { w: 700, size: 20, col: C.ac2, a: ga });
  x.save(); x.globalAlpha *= ga; rrect(80, GY, 920, GH, 18); x.fillStyle = C.term; x.fill(); x.strokeStyle = '#23262B'; x.lineWidth = 2; x.stroke(); x.restore();
  GRAMMAR.forEach((ln, li) => {
    let gx = 108;
    ln.forEach(([s, k]) => {
      const done = k >= 0 && t >= tl[k + 1][1], cur = k >= 0 && k + 1 === field;
      T(s, gx, GY + 46 + li * 36, { size: 21, col: k < 0 ? '#6E736C' : cur ? C.ac2 : done ? C.acc : C.ink, w: k >= 0 ? 700 : 400, a: ga });
      gx += measure(s, k >= 0 ? 700 : 400, 21, FM);
    });
  });
  // risposta generata
  const OY = 890, oa = P(t, 7.2, 7.5);
  x.save(); x.globalAlpha *= oa; rrect(80, OY, 920, 370, 18); x.fillStyle = C.panel; x.fill(); x.strokeStyle = '#3A3E44'; x.lineWidth = 2; x.stroke(); x.restore();
  T('risposta', 972, OY + 38, { size: 18, al: 'right', col: C.mute, a: oa });
  OUT.forEach(([s, rej, vw, vc], i) => {
    const [tr, ta] = tl[i], y = OY + 58 + i * 46;
    if (rej && t >= tr && t < ta) { // il token fuori grammatica viene bloccato
      const ra = 1 - P(t, ta - .15, ta), sw = measure(rej, 700, 24, FM);
      const rx = 108 + (i === 0 ? 0 : measure(s, 400, 24, FM));
      T(rej, rx, y, { w: 700, size: 24, col: ERR, a: ra });
      seg(rx - 4, y - 8, rx + sw + 4, y - 8, { col: ERR, lw: 3, a: ra, p: P(t, tr + .05, tr + .2) });
      T('✕ fuori grammatica', 972, y, { w: 700, size: 18, al: 'right', col: ERR, a: ra });
    }
    if (t < ta) return;
    const p = oCub(P(t, ta, ta + .2));
    T(s, 108, y, { size: 24, col: i === 0 || i === 6 ? C.acc : C.ink, a: p });
    if (vw) {
      const vx = 108 + measure(s, 400, 24, FM) + 4;
      x.save(); x.globalAlpha *= p; rrect(vx, y - 20, vw * oCub(P(t, ta, ta + .3)), 22, 6); x.fillStyle = vc === C.acc ? C.acc : '#3A3E44'; x.fill(); x.restore();
    }
  });
  if (t >= tl[6][1] + .2) T('JSON valido · 5 campi su 5', 972, OY + 58 + 6 * 46, { w: 700, size: 18, al: 'right', col: C.acc, a: P(t, tl[6][1] + .2, tl[6][1] + .4) });
  T('inject_gbnf_constraint(payload, grammar, backend)', 540, 1320, { size: 22, al: 'center', a: P(t, 7.8, 8.2) });
  T('llama.cpp: grammar · Ollama: format json · OpenAI: response_format', 540, 1366, { size: 19, al: 'center', col: C.mute, a: P(t, 8.0, 8.4) });
  badge(t, '5/5 PASSED', 1460, 10.5);
  x.restore();
}

/* ---------- scene 3 · NDJSON trace (11.0 – 15.8s) ---------- */
const EV_COL = { session_start: C.ink, llm_call: C.ac2, mutation_proposal_created: '#E8C547', tool_call: C.acc };
const TRACE = [ // dai `ts` della traccia, in secondi dall'inizio della sessione
  [0.0, 'session_start', '3 candidati'],
  [58.4, 'llm_call', 'flint 58,4 s'],
  [58.4, 'mutation_proposal_created', 'prop_155c2a028ff0'],
  [58.4, 'tool_call', 'write_file ✓'],
  [83.1, 'llm_call', 'flint 24,7 s'],
  [83.1, 'mutation_proposal_created', 'prop_3d8cb58b9c36'],
  [83.1, 'tool_call', 'write_file ✓'],
  [108.3, 'llm_call', 'flint 25,2 s'],
  [108.3, 'mutation_proposal_created', 'prop_0c9538792a26'],
  [108.3, 'tool_call', 'write_file ✓'],
];
const TR_T0 = 11.7, TR_ST = .17, TR_REPLAY = 13.7;
function trace(t) {
  const a = 11.0, b = 15.8;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — TRACCIA NDJSON REPLAYABILE', [[['Ogni evento,', C.ink]], [['una riga', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const fa = P(t, 11.3, 11.7), RY = 724, RH = 52;
  T('data/traces/atomic_dual_sprint_20261029_091406.ndjson', 80, RY - 30, { size: 20, col: C.mute, a: fa });
  x.save(); x.globalAlpha *= fa; rrect(64, RY - 6, 952, TRACE.length * RH + 12, 16); x.fillStyle = C.term; x.fill(); x.strokeStyle = '#23262B'; x.lineWidth = 2; x.stroke(); x.restore();
  const rp = P(t, TR_REPLAY, TR_REPLAY + 1.1), cur = t >= TR_REPLAY && rp < 1 ? Math.floor(rp * TRACE.length) : -1;
  TRACE.forEach(([dt, ev, det], i) => {
    const ti = TR_T0 + i * TR_ST;
    if (t < ti) return;
    const p = oCub(P(t, ti, ti + .25)), y = RY + i * RH + 34;
    if (i === cur) { x.save(); x.globalAlpha *= .9; rrect(72, y - 34, 936, RH - 4, 10); x.fillStyle = C.tint; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 2; x.stroke(); x.restore(); }
    x.save(); x.translate(0, (1 - p) * 18); x.globalAlpha *= p;
    T(String(i), 104, y, { w: 700, size: 20, al: 'right', col: '#6E736C' });
    T('+' + dt.toFixed(1).replace('.', ',') + ' s', 128, y, { size: 20, col: C.mute });
    circ(276, y - 7, 6, { fill: EV_COL[ev] });
    T(ev, 294, y, { w: 700, size: 20, col: EV_COL[ev] });
    T(det, 990, y, { size: 20, al: 'right', col: det.endsWith('✓') ? C.acc : C.ink });
    x.restore();
  });
  if (t >= TR_REPLAY) T('replay()', 1000, RY - 30, { w: 700, size: 20, al: 'right', col: C.acc, a: P(t, TR_REPLAY, TR_REPLAY + .2) });
  T('get_summary() → 10 eventi · 3/3 tool ok · 0 errori', 540, 1316, { size: 22, al: 'center', a: P(t, 13.6, 14.0) });
  T('append-only · thread-safe · una riga JSON per evento', 540, 1362, { size: 19, al: 'center', col: C.mute, a: P(t, 13.8, 14.2) });
  badge(t, '3/3 PASSED', 1460, 15.0);
  x.restore();
}

/* ---------- scene 4 · mutation guard (15.6 – 20.4s) ---------- */
const PROPS = [['prop_155c2a028ff0', 'autonomous_failure_isolator.py'], ['prop_3d8cb58b9c36', 'cross_context_semantic_cache.py'],
  ['prop_0c9538792a26', 'distributed_prioritized_work_stealing.py']];
const STATES = [['PENDING_APPROVAL', '#E8C547'], ['APPROVED', C.ac2], ['EXECUTED', C.acc]];
function guard(t) {
  const a = 15.6, b = 20.4;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — MUTATION GUARD', [[['Nessuna scrittura', C.ink]], [['senza proposta', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  // classificazione: le letture passano, le scritture diventano proposte
  const ca = P(t, 15.9, 16.3), CY = 712;
  const s1 = oBack(P(t, 15.9, 16.3)), s2 = oBack(P(t, 16.2, 16.6)), s3 = oBack(P(t, 16.5, 16.9));
  pill(190, CY, 220, 60, 'write_file', { s: s1, bold: true, col: C.ink });
  arrow(308, CY, 382, CY, P(t, 16.1, 16.3), '#5A5F66');
  pill(500, CY, 220, 60, 'MUTATING', { s: s2, bold: true, col: '#E8C547', stroke: '#E8C547', fill: '#221E0C' });
  arrow(618, CY, 692, CY, P(t, 16.4, 16.6), '#5A5F66');
  pill(844, CY, 290, 60, 'MutationProposal', { s: s3, bold: true, col: C.acc, stroke: C.acc, fill: C.tint });
  T('read_file · grep · git status → READ_ONLY, passano senza proposta', 540, CY + 70, { size: 19, al: 'center', col: C.mute, a: ca * P(t, 16.6, 17.0) });
  // le tre proposte dello sprint
  PROPS.forEach(([id, file], i) => {
    const t0 = 16.8 + i * .45, y = 860 + i * 150;
    const pa = oCub(P(t, t0, t0 + .3));
    if (pa <= 0) return;
    const st = t >= t0 + 1.25 ? 2 : t >= t0 + .7 ? 1 : 0, [sl, sc] = STATES[st];
    x.save(); x.globalAlpha *= pa; x.translate((1 - pa) * -50, 0);
    rrect(80, y, 920, 124, 18); x.fillStyle = st === 2 ? C.tint : C.panel; x.fill(); x.strokeStyle = st === 2 ? C.acc : '#3A3E44'; x.lineWidth = st === 2 ? 3 : 2; x.stroke();
    T(id, 112, y + 50, { w: 700, size: 24, col: C.ink });
    T('shared/' + file, 112, y + 92, { size: 19, col: C.mute });
    const pop = oBack(P(t, t0 + [0, .7, 1.25][st], t0 + [0, .7, 1.25][st] + .25));
    const cw = measure(sl, 700, 20, FM, 1) + 44;
    x.save(); x.translate(968 - cw / 2, y + 44); x.scale(pop, pop);
    rrect(-cw / 2, -22, cw, 44, 22); x.fillStyle = C.bg; x.fill(); x.strokeStyle = sc; x.lineWidth = 2.5; x.stroke();
    T(sl, 0, 7, { w: 700, size: 20, al: 'center', col: sc, ls: 1 });
    x.restore();
    T(['create_proposal()', 'approve()', 'execute_with_guard()'][st], 968, y + 92, { size: 18, al: 'right', col: sc });
    x.restore();
  });
  T('una proposta tipizzata in data/proposals/ per ogni scrittura', 540, 1340, { size: 21, al: 'center', a: P(t, 17.4, 17.8) });
  badge(t, '4/4 PASSED', 1460, 19.7);
  x.restore();
}

/* ---------- scene 5 · tre moduli promossi (20.2 – 25.0s) ---------- */
const STEAL = [2, 4, 5, 7, 9]; // deadline in secondi: in testa all'heap il più urgente
function modules(t) {
  const a = 20.2, b = 25.0;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — PROMOSSI IN SHARED/', [[['Dal prototipo', C.ink]], [['alla mesh', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const rows = [690, 910, 1130], RW = 920, RH = 196;
  const panel = (y, s, title, foot) => {
    const p = oCub(P(t, s, s + .3));
    x.save(); x.globalAlpha *= p; x.translate(0, (1 - p) * 30);
    rrect(80, y, RW, RH, 20); x.fillStyle = C.panel; x.fill(); x.strokeStyle = '#3A3E44'; x.lineWidth = 2; x.stroke();
    T(title, 112, y + 46, { w: 700, size: 22, col: C.ink });
    T(foot, 112, y + 172, { size: 18, col: C.mute });
    x.restore();
    return p;
  };
  const chip = (cx, cy, label, col, s) => {
    if (s <= 0) return;
    const cw = measure(label, 700, 19, FM, 1) + 40;
    x.save(); x.translate(cx - cw / 2, cy); x.scale(s, s);
    rrect(-cw / 2, -21, cw, 42, 21); x.fillStyle = C.bg; x.fill(); x.strokeStyle = col; x.lineWidth = 2.5; x.stroke();
    T(label, 0, 7, { w: 700, size: 19, al: 'center', col, ls: 1 }); x.restore();
  };
  // a · isolamento dei nodi degradati
  let s = 20.6, y = rows[0];
  if (panel(y, s, 'autonomous_failure_isolator.py', 'predict_degradation() → isolate_node() · soglie 200 ms, 5% loss') > 0) {
    const v = lerp(80, 240, ioCub(P(t, s + .4, s + 1.3))), GX0 = 112, GX1 = 620, gy = y + 110;
    const thr = lerp(GX0, GX1, 200 / 300), over = v > 200;
    rrect(GX0, gy, GX1 - GX0, 16, 8); x.fillStyle = '#14171B'; x.fill();
    rrect(GX0, gy, (GX1 - GX0) * v / 300, 16, 8); x.fillStyle = over ? ERR : C.acc; x.fill();
    seg(thr, gy - 14, thr, gy + 30, { col: ERR, lw: 3, dash: [5, 5] });
    T('soglia 200 ms', thr + 12, gy - 16, { size: 16, col: ERR });
    T(`omen-16 · latenza ${Math.round(v)} ms`, GX0, gy - 16, { size: 19, col: over ? ERR : C.ink });
    let tc = s + .4; while (tc < s + 1.7 && lerp(80, 240, ioCub(P(tc, s + .4, s + 1.3))) <= 200) tc += .01; // passa i 200 ms
    const st = t < tc ? ['HEALTHY', C.acc] : t < tc + .45 ? ['DEGRADING', '#E8C547'] : ['ISOLATED', ERR];
    chip(968, gy + 8, st[0], st[1], oBack(P(t, s + .3, s + .6)));
  }
  // b · cache semantica
  s = 21.4; y = rows[1];
  if (panel(y, s, 'cross_context_semantic_cache.py', 'LRU da 128 voci · thread-safe · lower() + SequenceMatcher') > 0) {
    const q = 'Qual è lo stato del nodo OMEN';
    const n = Math.floor(q.length * P(t, s + .35, s + 1.0));
    T('→ "' + q.slice(0, n) + (n < q.length ? '▍' : '"'), 112, y + 98, { size: 20, col: C.ink });
    T('≈ "qual è lo stato del nodo omen?"', 112, y + 136, { size: 20, col: C.mute, a: P(t, s + 1.0, s + 1.2) });
    const hit = oBack(P(t, s + 1.3, s + 1.6));
    chip(968, y + 112, 'HIT · 0,98', C.acc, hit);
    T('soglia ≥ 0,8', 968 - 86, y + 160, { size: 16, al: 'center', col: C.mute, a: P(t, s + 1.4, s + 1.6) });
  }
  // c · work stealing a priorità
  s = 22.2; y = rows[2];
  if (panel(y, s, 'distributed_prioritized_work_stealing.py', 'heap per (deadline, costo) · steal() prende il più urgente') > 0) {
    const by = y + 82, BW = 74, BH = 54, BG = 8, w0 = 190, w1 = 700;
    T('W0', 112, by + 36, { w: 700, size: 20, col: ERR });
    T('W1', 642, by + 36, { w: 700, size: 20, col: C.acc });
    for (let k = 0; k < 2; k++) { rrect(w1 + k * (BW + BG), by, BW, BH, 10); x.save(); x.strokeStyle = '#2A2D32'; x.lineWidth = 2; x.setLineDash([4, 5]); x.stroke(); x.restore(); }
    const sp = ioCub(P(t, s + .9, s + 1.4));
    STEAL.forEach((d, k) => {
      const ap = oBack(P(t, s + .3 + k * .08, s + .55 + k * .08));
      if (ap <= 0) return;
      let bx = w0 + k * (BW + BG), byy = by;
      if (k === 0) { bx = lerp(bx, w1, sp); byy = by - Math.sin(sp * Math.PI) * 50; }
      else bx -= (BW + BG) * oCub(P(t, s + 1.3, s + 1.6)); // l'heap si riordina
      x.save(); x.translate(bx + BW / 2, byy + BH / 2); x.scale(ap, ap);
      rrect(-BW / 2, -BH / 2, BW, BH, 10); x.fillStyle = k === 0 ? C.acc : '#2C3036'; x.fill();
      T(d + ' s', 0, 8, { w: 700, size: 19, al: 'center', col: k === 0 ? C.dark : C.ink }); x.restore();
    });
    T('steal(1, 0)', 968, by - 6, { w: 700, size: 19, al: 'right', col: C.acc, a: P(t, s + 1.4, s + 1.6) });
  }
  T('revisione Flint 40B · ast.parse · Mutation Guard', 540, 1392, { size: 21, al: 'center', col: C.mute, a: P(t, 23.0, 23.4) });
  badge(t, '3/3 PASSED', 1474, 24.2);
  x.restore();
}

/* ---------- scene 6 · test suite (24.8 – 27.6s) ---------- */
const TS = [['GBNFBuilder · gbnf_grammar', 5], ['NDJSONTracer · ndjson_tracer', 3], ['MutationGuard · mutation_guard', 4], ['tre moduli promossi', 3]];
function tests(t) {
  const a = 24.8, b = 27.6;
  if (t < a || t > b) return;
  header(t, a, b, '05', '05 — TEST SUITE', [[['Tutto', C.ink]], [['verde.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const N = 15, nf = N * oCub(P(t, 25.2, 26.4)), n = Math.round(nf);
  T(n + '/' + N, 540, 880, { w: 900, size: 210, fam: FD, al: 'center', col: n === N ? C.acc : C.ink, ls: -6, a: P(t, 25.1, 25.4) });
  T('PASSED', 540, 950, { w: 700, size: 30, al: 'center', col: C.acc, ls: 12, a: P(t, 25.2, 25.5) });
  for (let i = 0; i < N; i++) {
    const cx = 540 + (i - (N - 1) / 2) * 56, cy = 1050;
    const lit = i < n, pop = lit ? oBack(clamp((nf - i) * 2)) : 1;
    circ(cx, cy, lit ? 14 * pop : 13, lit ? { fill: C.acc } : { stroke: '#3A3E44', lw: 2 });
  }
  T('test_atomic_agent_patterns.py + test_promoted_atomic_sprint_modules.py', 540, 1150, { size: 18, al: 'center', col: C.mute, a: P(t, 25.2, 25.5) });
  let acc = 0;
  TS.forEach(([f, k], i) => {
    const y = 1230 + i * 56;
    const ready = n >= acc + k; acc += k;
    const la = P(t, 25.3 + i * .15, 25.6 + i * .15);
    T(f, 100, y, { size: 22, col: C.ink, a: la });
    const fw = measure(f, 400, 22, FM);
    seg(100 + fw + 18, y - 7, 860, y - 7, { col: '#2C3036', lw: 2, dash: [2, 8], a: la });
    T(ready ? `${k}/${k} ✓` : '…', 980, y, { w: 700, size: 22, al: 'right', col: ready ? C.acc : C.mute, a: la });
  });
  x.restore();
}

const REEL = {
  date: '29.10.2026',
  tagline: 'Ogni promozione lascia una traccia.',
  sc: [{ a: 6.4, b: 11.2, n: '01' }, { a: 11.0, b: 15.8, n: '02' }, { a: 15.6, b: 20.4, n: '03' }, { a: 20.2, b: 25.0, n: '04' }, { a: 24.8, b: 27.6, n: '05' }],
  cuts: [3.1, 6.5, 11.1, 15.7, 20.3, 24.9, 27.5],
  scenes: [headline, gbnf, trace, guard, modules, tests]
};
