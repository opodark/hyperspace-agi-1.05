// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "endurance-2026-10-28", "title": "00MESH Reel Endurance", "aria": "Animazione di 30 secondi sui quattro moduli promossi in HyperSpace AGI 1.05 il 28 ottobre: validatore di bozze speculative, heartbeat distribuito con protezione split-brain a quorum, pool di KV cache a blocchi con auto-eviction, sincronizzazione di stato a 60 Hz con rollback, e 8 test superati, con chiusura sul logo 00MESH."}
/* R&D log del 28/10/2026 pomeriggio (commit 113c769): SpeculativeDraftValidator, DistributedHeartbeatSync,
   DynamicKVMemoryPool, ArcadeStateSyncEngine; tests/test_mesh_r_and_d_modules.py 8/8.
   Parametri dal codice: quorum > 50%, timeout 6 s, 128 blocchi da 1 MB, idle 5 min, 60 Hz, 30 tick di rollback. */

/* ---------- scene 1 · headline (3.0 – 6.6s) ---------- */
function headline(t) {
  const a = 3.0, b = 6.6;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .3);
  x.save(); x.globalAlpha = e;
  const kick = 'R&D LOG · ENDURANCE · 28 OTTOBRE 2026';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .6))), 80, 640, { w: 700, size: 24, col: C.acc, ls: 3 });
  const L = [[['La', C.ink], ['mesh', C.ink], ['che', C.ink]], [['corre', C.acc], ['veloce,', C.acc]],
    [['non', C.ink], ['si', C.ink], ['spezza', C.ink]], [['e', C.ink], ['non', C.ac2], ['perde', C.ac2], ['un', C.ac2], ['tick.', C.ac2]]];
  const lineW = (ln, s) => ln.reduce((acc, [w]) => acc + measure(w, 900, s, FD, -2), 0) + s * .27 * (ln.length - 1);
  const widest = Math.max(...L.map(ln => lineW(ln, 124)));
  const size = Math.min(124, 124 * 920 / widest), LH = size * 1.14;
  words(t, L, 80, 790, LH, size, a + .2, .1, .9, b - .5);
  const yb = 790 + 3 * LH;
  seg(80, yb + 90, 420, yb + 90, { col: C.acc, lw: 6, p: oExpo(P(t, 4.8, 5.4)) * (1 - iCub(P(t, 6.1, 6.5))) });
  T('Quattro moduli nuovi. 8 test verdi.', 80, yb + 170, { w: 500, size: 42, fam: FD, col: C.mute, a: oCub(P(t, 5.0, 5.5)) * (1 - P(t, 6.1, 6.4)) });
  x.restore();
}

/* ---------- scene 2 · speculative drafts (6.4 – 11.2s) ---------- */
const DRAFTS = [['draft A', '✓ valida', 1], ['draft B', '✕ SyntaxError', 0], ['draft C', '✓ valida · più ricca', 2], ['draft D', '✕ pattern vietato', 0]];
function drafts(t) {
  const a = 6.4, b = 11.2;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — SPECULATIVE DRAFT VALIDATOR', [[['Bozze veloci,', C.ink]], [['verifica sicura', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const SRC = [150, 915], DST = [930, 915], CX0 = 300, CW = 420, CH = 96, CY = [700, 830, 960, 1090];
  const na = oBack(P(t, 6.8, 7.3));
  const win = 2, chosen = t >= 9.9;
  DRAFTS.forEach(([n, res, ok], i) => {
    const s = 7.2 + i * .18, cy = CY[i] + CH / 2;
    seg(SRC[0] + 40, SRC[1], CX0 - 8, cy, { col: C.line, lw: 2, a: P(t, s - .2, s), dash: [4, 10] });
    const sa = oCub(P(t, s, s + .35));
    if (sa <= 0) return;
    const chk = 8.1 + i * .4, done = t >= chk + .3, good = ok > 0;
    const isWin = chosen && i === win, dim = chosen && i !== win;
    x.save(); x.globalAlpha *= sa * (dim ? .45 : 1); x.translate((1 - sa) * -60, 0);
    rrect(CX0, CY[i], CW, CH, 18);
    x.fillStyle = isWin ? C.tint : done && !good ? '#2A1512' : C.panel; x.fill();
    x.strokeStyle = isWin ? C.acc : done ? (good ? C.acc : ERR) : '#3A3E44'; x.lineWidth = isWin ? 4 : 2.5; x.stroke();
    T(n, CX0 + 28, CY[i] + 40, { w: 700, size: 24, col: C.ink });
    for (let k = 0; k < 3; k++) seg(CX0 + 28, CY[i] + 62 + k * 10, CX0 + 28 + [210, 150, 180][(k + i) % 3], CY[i] + 62 + k * 10, { col: '#2C3036', lw: 4 });
    if (t >= chk && !done) { // scansione AST
      const sy = lerp(CY[i] + 8, CY[i] + CH - 8, P(t, chk, chk + .3));
      seg(CX0 + 10, sy, CX0 + CW - 10, sy, { col: C.ac2, lw: 3 });
    }
    if (done) T(res, CX0 + CW - 24, CY[i] + 40, { w: 700, size: 20, al: 'right', col: good ? C.acc : ERR });
    x.restore();
  });
  // il draft scelto va al nodo primario
  if (chosen) arrow(CX0 + CW + 8, CY[win] + CH / 2, DST[0] - 48, DST[1] + 10, ioCub(P(t, 9.9, 10.3)), C.acc);
  if (t > 7.0) {
    const u = (t * 1.2) % 1;
    if (t < 8.0) circ(SRC[0], SRC[1], 40 + u * 40, { stroke: C.acc, lw: 2, a: (1 - u) * .6 });
  }
  [[SRC, 'OMEN', 'LFM 24B · bozze', C.acc], [DST, 'V16', 'Flint 40B · verifica', chosen ? C.acc : C.ac2]].forEach(([p, lb, sub, col]) => {
    x.save(); x.translate(p[0], p[1]); x.scale(na, na);
    circ(0, 0, 40, { fill: C.panel, stroke: col, lw: 3 });
    T(lb, 0, 8, { w: 900, size: lb.length > 2 ? 18 : 22, fam: FD, al: 'center', col: C.ink });
    x.restore();
    T(sub, p[0], p[1] + 76, { size: 20, al: 'center', col: C.mute, a: clamp(na) });
  });
  T('select_best_draft()', DST[0], DST[1] - 64, { size: 20, al: 'center', col: C.acc, a: P(t, 10.1, 10.4) });
  T('SpeculativeDraftValidator.verify(draft)', 540, 1300, { size: 24, al: 'center', a: P(t, 7.6, 8.0) });
  T('ast.parse · costrutti richiesti · pattern vietati', 540, 1350, { size: 22, al: 'center', col: C.mute, a: P(t, 7.8, 8.2) });
  badge(t, '4/4 PASSED', 1450, 10.5);
  x.restore();
}

/* ---------- scene 3 · heartbeat & split-brain (11.0 – 15.8s) ---------- */
const V16_DOWN = 12.9, V16_DEAD = 13.9; // smette di battere · supera il timeout (6 s compressi)
function heartbeat(t) {
  const a = 11.0, b = 15.8;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — DISTRIBUTED HEARTBEAT SYNC', [[['Split-brain', C.ink]], [['sventato', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const N = { M5: [540, 690], OMEN: [250, 1010], V16: [830, 1010] };
  const na = oBack(P(t, 11.3, 11.8)), la = clamp(na);
  const cut = t >= V16_DEAD;
  [['M5', 'OMEN'], ['M5', 'V16'], ['OMEN', 'V16']].forEach(([p, q]) => {
    const toV = q === 'V16';
    seg(...N[p], ...N[q], { col: toV && cut ? '#3A2420' : C.line, lw: 3, a: la, dash: toV && cut ? [8, 10] : null });
    if (toV && cut) {
      const mx = (N[p][0] + N[q][0]) / 2, my = (N[p][1] + N[q][1]) / 2;
      T('✕', mx, my + 10, { w: 700, size: 30, al: 'center', col: ERR, a: P(t, V16_DEAD, V16_DEAD + .2) });
    }
  });
  // battiti: ogni nodo vivo pulsa e manda un battito agli altri
  Object.entries(N).forEach(([id, p], k) => {
    for (let i = 0; i < 12; i++) {
      const tb = 11.7 + i * .38 + k * .11;
      if (tb > t) break;
      if (id === 'V16' && tb >= V16_DOWN) break;
      const age = t - tb; if (age > .5) continue;
      Object.entries(N).forEach(([jd, q]) => {
        if (jd === id) return;
        if (cut && (id === 'V16' || jd === 'V16')) return;
        const pp = oCub(clamp(age / .45));
        circ(lerp(p[0], q[0], pp), lerp(p[1], q[1], pp), 6, { fill: id === 'V16' ? C.ac2 : C.acc, a: 1 - P(age, .4, .5) });
      });
      circ(p[0], p[1], 40 + age * 70, { stroke: C.acc, lw: 2, a: (1 - age / .5) * .7 });
    }
  });
  // timeout di V16
  if (t >= V16_DOWN && t < V16_DEAD + .3) {
    const p = P(t, V16_DOWN, V16_DEAD);
    x.save(); x.strokeStyle = ERR; x.lineWidth = 4; x.beginPath();
    x.arc(N.V16[0], N.V16[1], 56, -Math.PI / 2, -Math.PI / 2 + p * Math.PI * 2); x.stroke(); x.restore();
    T(`timeout ${(p * 6).toFixed(1)} s`, N.V16[0], N.V16[1] - 76, { w: 700, size: 20, al: 'center', col: ERR });
  }
  const sub = { M5: 'mac-m5', OMEN: 'omen-16', V16: cut ? 'asus-v16 · isolato' : 'asus-v16' };
  Object.entries(N).forEach(([id, p]) => {
    const dead = id === 'V16' && cut, col = dead ? ERR : C.acc;
    x.save(); x.translate(p[0], p[1]); x.scale(na, na);
    circ(0, 0, 40, { fill: C.panel, stroke: col, lw: 3, dash: dead ? [6, 6] : null });
    T(id, 0, 8, { w: 900, size: id.length > 2 ? 18 : 22, fam: FD, al: 'center', col: dead ? ERR : C.ink });
    x.restore();
    T(sub[id], p[0], id === 'M5' ? p[1] - 62 : p[1] + 76, { size: 22, al: 'center', col: dead ? ERR : C.mute, a: la });
  });
  // quorum
  const qa = P(t, 11.8, 12.2), QX0 = 140, QX1 = 940, QY = 1170;
  const alive = cut ? 2 : 3, fr = lerp(1, alive / 3, cut ? oCub(P(t, V16_DEAD, V16_DEAD + .4)) : 0);
  x.save(); x.globalAlpha *= qa;
  rrect(QX0, QY, QX1 - QX0, 28, 14); x.fillStyle = '#14171B'; x.fill();
  rrect(QX0, QY, (QX1 - QX0) * fr, 28, 14); x.fillStyle = C.acc; x.fill();
  seg(lerp(QX0, QX1, .5), QY - 14, lerp(QX0, QX1, .5), QY + 42, { col: ERR, lw: 3, dash: [6, 5] });
  T('50%', lerp(QX0, QX1, .5), QY - 22, { w: 700, size: 18, al: 'center', col: ERR });
  T(`attivi ${alive}/3 · ${Math.round(fr * 100)}%`, QX0, QY - 22, { w: 700, size: 22, col: C.ink });
  T(cut ? 'quorum ✓' : 'quorum ✓', QX1, QY - 22, { w: 700, size: 22, al: 'right', col: C.acc });
  x.restore();
  T('V16 da solo: 1/3 · niente quorum, niente split-brain', 540, 1262, { size: 22, al: 'center', col: ERR, a: P(t, V16_DEAD + .5, V16_DEAD + .9) });
  T('DistributedHeartbeatSync.has_quorum()', 540, 1340, { size: 24, al: 'center', a: P(t, 12.0, 12.4) });
  T('timeout 6 s · quorum > 50% dei nodi', 540, 1390, { size: 22, al: 'center', col: C.mute, a: P(t, 12.2, 12.6) });
  badge(t, '1/1 PASSED', 1480, 15.0);
  x.restore();
}

/* ---------- scene 4 · KV pool (15.6 – 20.4s) ---------- */
const KV_CTX = [['flint-128k', 44, 16.2, C.acc], ['lfm-64k', 24, 16.8, C.ac2], ['chat', 14, 17.4, C.ink], ['nuova sessione', 18, 19.3, '#E8C547']];
const KV_EVICT = 18.6; // la chat ferma viene liberata
const KV = (() => { // simulazione del free-list: ogni contesto prende i primi blocchi liberi
  const free = Array.from({ length: 128 }, (_, i) => i), own = {};
  const take = n => free.splice(0, n);
  own[0] = take(44); own[1] = take(24); own[2] = take(14);
  const back = own[2].slice(); free.unshift(...back); own[3] = take(18);
  return own;
})();
function kvpool(t) {
  const a = 15.6, b = 20.4;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — DYNAMIC KV MEMORY POOL', [[['Contesti lunghi,', C.ink]], [['VRAM in ordine', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const COLS = 16, S = 52, G = 6, GX = 540 - (COLS * (S + G) - G) / 2, GY = 690;
  const ga = P(t, 15.9, 16.3);
  const owner = new Array(128).fill(-1), born = new Array(128).fill(0);
  KV_CTX.forEach(([, , ts], k) => {
    if (t < ts) return;
    if (k === 2 && t >= KV_EVICT + .5) return;
    KV[k].forEach((blk, j) => { const tj = ts + j * .012; if (t >= tj) { owner[blk] = k; born[blk] = tj; } });
  });
  for (let i = 0; i < 128; i++) {
    const c = i % COLS, r = Math.floor(i / COLS), bx = GX + c * (S + G), by = GY + r * (S + G);
    const k = owner[i];
    x.save(); x.globalAlpha *= ga;
    rrect(bx, by, S, S, 8);
    if (k < 0) { x.strokeStyle = '#2A2D32'; x.lineWidth = 2; x.setLineDash([4, 5]); x.stroke(); }
    else {
      const pop = oBack(clamp((t - born[i]) / .25));
      const fading = k === 2 && t >= KV_EVICT ? 1 - P(t, KV_EVICT, KV_EVICT + .5) : 1;
      x.globalAlpha *= fading; x.translate(bx + S / 2, by + S / 2); x.scale(pop, pop); x.translate(-bx - S / 2, -by - S / 2);
      rrect(bx, by, S, S, 8); x.fillStyle = KV_CTX[k][3]; x.fill();
    }
    x.restore();
  }
  // idle timer della chat
  if (t >= 17.8 && t < KV_EVICT + .5) {
    const p = P(t, 17.8, KV_EVICT);
    T(p < 1 ? `chat inattiva · ${Math.round(p * 5)} min` : 'evict_idle_contexts() → liberati 14 blocchi', 540, GY - 28,
      { w: 700, size: 22, al: 'center', col: p < 1 ? '#E8C547' : C.acc });
  }
  // legenda
  const used = owner.filter(o => o >= 0).length;
  const LY = GY + 8 * (S + G) + 50;
  let lx = 80;
  KV_CTX.forEach(([n, , ts, col], k) => {
    const on = t >= ts && !(k === 2 && t >= KV_EVICT + .5);
    const la = on ? 1 : (k === 2 && t >= KV_EVICT + .5) ? .35 : 0;
    if (la <= 0) return;
    x.save(); x.globalAlpha *= la; rrect(lx, LY - 18, 22, 22, 5); x.fillStyle = col; x.fill(); x.restore();
    T(n, lx + 32, LY, { size: 20, col: C.ink, a: la });
    lx += measure(n, 400, 20, FM) + 70;
  });
  T(`liberi ${128 - used}/128`, 1000, LY + 50, { w: 700, size: 22, al: 'right', col: C.acc, a: ga });
  T('DynamicKVMemoryPool.allocate(ctx, blocchi)', 540, 1340, { size: 24, al: 'center', a: P(t, 16.4, 16.8) });
  T('128 blocchi da 1 MB · auto-eviction dopo 5 min di inattività', 540, 1390, { size: 22, al: 'center', col: C.mute, a: P(t, 16.6, 17.0) });
  badge(t, '2/2 PASSED', 1480, 19.7);
  x.restore();
}

/* ---------- scene 5 · arcade state sync (20.2 – 25.0s) ---------- */
const AT0 = 20.6, AIN = 21.7, AARR = 22.1, AY = 860; // l'input remoto parte a AIN e arriva 24 tick dopo
const ballX = t => 150 + (t - AT0) * 175;
const predY = () => AY;
const realY = t => AY - Math.min(130, Math.max(0, t - AIN) * 150);
function arcade(t) {
  const a = 20.2, b = 25.0;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — ARCADE STATE SYNC ENGINE', [[['60 Hz,', C.ink]], [['zero lag', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const pa = P(t, 20.5, 20.9), PX0 = 80, PX1 = 1000, PY0 = 680, PY1 = 1000;
  x.save(); x.globalAlpha *= pa;
  rrect(PX0, PY0, PX1 - PX0, PY1 - PY0, 24); x.fillStyle = '#0B0D10'; x.fill(); x.strokeStyle = '#23262B'; x.lineWidth = 2; x.stroke();
  x.restore();
  const tt = clamp(t, AT0, 24.6), rec = P(t, AARR + .2, AARR + .45);
  // traiettoria predetta (fantasma) dopo l'arrivo dell'input
  if (t >= AARR) {
    x.save(); x.strokeStyle = '#5A5F66'; x.lineWidth = 3; x.setLineDash([6, 8]); x.beginPath();
    x.moveTo(ballX(AIN), predY()); x.lineTo(ballX(Math.min(tt, AARR + .2)), predY()); x.stroke(); x.restore();
    if (t < AARR + 1.2) T('predizione', ballX(AARR) + 30, AY + 44, { size: 20, col: '#8A8F87', a: 1 - P(t, AARR + .9, AARR + 1.2) });
  }
  // traiettoria vera, ricostruita col replay
  x.save(); x.strokeStyle = C.acc; x.lineWidth = 5; x.lineJoin = 'round'; x.beginPath();
  for (let i = 0; i <= 120; i++) {
    const u = lerp(AT0, tt, i / 120);
    const y = t >= AARR + .2 ? realY(u) : predY();
    i ? x.lineTo(ballX(u), y) : x.moveTo(ballX(u), y);
  }
  x.globalAlpha *= pa; x.stroke(); x.restore();
  const by = t < AARR + .2 ? predY() : lerp(predY(), realY(tt), oCub(rec));
  if (pa > 0) {
    circ(ballX(tt), by, 18, { fill: C.acc, a: pa });
    const u2 = (t * 1.5) % 1; circ(ballX(tt), by, 18 + u2 * 26, { stroke: C.acc, lw: 2, a: (1 - u2) * pa });
  }
  // input in ritardo
  if (t >= AIN) {
    const p = ioCub(P(t, AIN, AARR));
    const sx = 980, sy = 720;
    if (t < AARR) circ(lerp(sx, ballX(AARR), p), lerp(sy, AY - 30, p), 9, { fill: C.ac2 });
    T('↑ input remoto', sx, sy - 10, { w: 700, size: 20, al: 'right', col: C.ac2, a: P(t, AIN, AIN + .2) * (1 - P(t, 23.6, 23.9)) });
  }
  if (t >= AARR) T('arriva 24 tick dopo → rollback e replay', 540, PY1 - 26, { w: 700, size: 22, al: 'center', col: C.ac2, a: P(t, AARR, AARR + .2) });
  // buffer circolare dei tick
  const tick = 1200 + Math.round((tt - AT0) * 60), RY = 1090, CW = 26, CG = 4, RX = 540 - (30 * (CW + CG) - CG) / 2;
  const replay = t >= AARR && t < AARR + .45, back = Math.round((AARR - AIN) * 60);
  const ra = P(t, 20.7, 21.1);
  x.save(); x.globalAlpha *= ra;
  for (let i = 0; i < 30; i++) {
    const tk = tick - 29 + i, inReplay = (replay || (t >= AARR && t < AARR + 1)) && tk >= tick - back;
    const sweep = replay ? tick - back + Math.round(back * P(t, AARR + .05, AARR + .4)) : tick;
    rrect(RX + i * (CW + CG), RY, CW, 44, 6);
    x.fillStyle = tk === tick ? C.acc : inReplay && tk <= sweep ? C.ac2 : '#14171B'; x.fill();
  }
  x.restore();
  T(`tick ${tick}`, RX, RY - 18, { w: 700, size: 20, col: C.ink, a: ra });
  T('buffer di rollback · 30 tick', RX + 30 * (CW + CG) - CG, RY - 18, { size: 20, al: 'right', col: C.mute, a: ra });
  T('ArcadeStateSyncEngine.rollback_and_replay(tick)', 540, 1240, { size: 24, al: 'center', a: P(t, 21.0, 21.4) });
  T('tick fisso 60 Hz · predizione locale · riconciliazione deterministica', 540, 1290, { size: 22, al: 'center', col: C.mute, a: P(t, 21.2, 21.6) });
  badge(t, '1/1 PASSED', 1380, 24.2);
  x.restore();
}

/* ---------- scene 6 · test suite (24.8 – 27.6s) ---------- */
const TS = [['speculative_draft_validator', 4], ['distributed_heartbeat_sync', 1], ['dynamic_kv_memory_pool', 2], ['arcade_state_sync_engine', 1]];
function tests(t) {
  const a = 24.8, b = 27.6;
  if (t < a || t > b) return;
  header(t, a, b, '05', '05 — TEST SUITE', [[['Tutto', C.ink]], [['verde.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const n = Math.round(8 * oCub(P(t, 25.2, 26.4)));
  T(n + '/8', 540, 880, { w: 900, size: 210, fam: FD, al: 'center', col: n === 8 ? C.acc : C.ink, ls: -6, a: P(t, 25.1, 25.4) });
  T('PASSED', 540, 950, { w: 700, size: 30, al: 'center', col: C.acc, ls: 12, a: P(t, 25.2, 25.5) });
  for (let i = 0; i < 8; i++) {
    const cx = 540 + (i - 3.5) * 76, cy = 1050;
    const lit = i < n, pop = lit ? oBack(clamp((8 * oCub(P(t, 25.2, 26.4)) - i) * 2)) : 1;
    circ(cx, cy, lit ? 16 * pop : 15, lit ? { fill: C.acc } : { stroke: '#3A3E44', lw: 2 });
  }
  T('tests/test_mesh_r_and_d_modules.py', 540, 1150, { size: 22, al: 'center', col: C.mute, a: P(t, 25.2, 25.5) });
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
  date: '28.10.2026',
  tagline: 'La mesh che regge anche sotto sforzo.',
  sc: [{ a: 6.4, b: 11.2, n: '01' }, { a: 11.0, b: 15.8, n: '02' }, { a: 15.6, b: 20.4, n: '03' }, { a: 20.2, b: 25.0, n: '04' }, { a: 24.8, b: 27.6, n: '05' }],
  cuts: [3.1, 6.5, 11.1, 15.7, 20.3, 24.9, 27.5],
  scenes: [headline, drafts, heartbeat, kvpool, arcade, tests]
};
