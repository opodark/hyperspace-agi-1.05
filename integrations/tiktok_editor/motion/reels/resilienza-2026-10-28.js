// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "resilienza-2026-10-28", "title": "00MESH Reel Resilienza", "aria": "Animazione di 30 secondi sulle nuove feature di HyperSpace AGI 1.05: circuit breaker adattivo, token bucket rate limiter, controller PID della latenza, causal AI in Mission Control e 37 test superati, con chiusura sul logo 00MESH."}
/* R&D log del 28/10/2026: circuit breaker, token bucket, PID di latenza, causal AI in Mission Control, test. */

/* ---------- scene 1 · headline (3.0 – 6.6s) ---------- */
function headline(t) {
  const a = 3.0, b = 6.6;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .3);
  x.save(); x.globalAlpha = e;
  const kick = 'R&D LOG · 28 OTTOBRE 2026';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .6))), 80, 640, { w: 700, size: 24, col: C.acc, ls: 3 });
  const L = [[['La', C.ink], ['mesh', C.ink], ['che', C.ink]], [['si', C.acc], ['protegge,', C.acc]], [['si', C.ink], ['dosa', C.ink]], [['e', C.ink], ['si', C.ac2], ['autoregola.', C.ac2]]];
  const lineW = (ln, s) => ln.reduce((acc, [w]) => acc + measure(w, 900, s, FD, -2), 0) + s * .27 * (ln.length - 1);
  const widest = Math.max(...L.map(ln => lineW(ln, 124)));
  const size = Math.min(124, 124 * 920 / widest), LH = size * 1.14;
  words(t, L, 80, 790, LH, size, a + .2, .1, .9, b - .5);
  const yb = 790 + 3 * LH;
  seg(80, yb + 90, 420, yb + 90, { col: C.acc, lw: 6, p: oExpo(P(t, 4.8, 5.4)) * (1 - iCub(P(t, 6.1, 6.5))) });
  T('Quattro feature nuove. 37 test verdi.', 80, yb + 170, { w: 500, size: 42, fam: FD, col: C.mute, a: oCub(P(t, 5.0, 5.5)) * (1 - P(t, 6.1, 6.4)) });
  x.restore();
}

/* ---------- scene 2 · circuit breaker (6.4 – 11.2s) ---------- */
const cbState = t => t < 8.6 ? 0 : t < 9.8 ? 1 : t < 10.3 ? 2 : 0; // 0 CLOSED · 1 OPEN · 2 HALF_OPEN
const asusOnline = t => t < 7.7 || t >= 10.0;
function breaker(t) {
  const a = 6.4, b = 11.2;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — ADAPTIVE MESH CIRCUIT BREAKER', [[['Fail-fast', C.ink]], [['istantaneo', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const na = oBack(P(t, 6.8, 7.3)), la = clamp(na);
  const S = [190, 840], A = [880, 720], O = [880, 980];
  const len = Math.hypot(A[0] - S[0], A[1] - S[1]), ux = (A[0] - S[0]) / len, uy = (A[1] - S[1]) / len;
  const BK = [lerp(S[0], A[0], .55), lerp(S[1], A[1], .55)];
  const g1 = [BK[0] - ux * 28, BK[1] - uy * 28], g2 = [BK[0] + ux * 28, BK[1] + uy * 28];
  const st = cbState(t), stCol = [C.acc, ERR, C.ac2][st];
  const on = asusOnline(t);
  // links
  seg(S[0], S[1], O[0], O[1], { col: C.line, lw: 3, a: la });
  seg(S[0], S[1], g1[0], g1[1], { col: C.line, lw: 3, a: la });
  seg(g2[0], g2[1], A[0], A[1], { col: on ? C.line : '#3A2420', lw: 3, a: la, dash: on ? null : [8, 10] });
  seg(BK[0], BK[1], O[0], O[1], { col: C.ac2, lw: 2, a: la * (st === 1 ? .7 : .0), dash: [6, 12], off: -t * 60 });
  // breaker switch
  const open = st === 1 ? oCub(P(t, 8.6, 8.8)) : st === 2 ? .45 : 1 - oCub(P(t, 10.3, 10.5)) * (t >= 10.3 ? 1 : 0) - (t < 8.6 ? 1 : 0);
  const op = clamp(open);
  circ(g1[0], g1[1], 7, { fill: stCol, a: la }); circ(g2[0], g2[1], 7, { fill: stCol, a: la });
  x.save(); x.globalAlpha *= la; x.translate(g1[0], g1[1]); x.rotate(Math.atan2(uy, ux) - op * .8);
  x.strokeStyle = stCol; x.lineWidth = 6; x.lineCap = 'round'; x.beginPath(); x.moveTo(0, 0); x.lineTo(56, 0); x.stroke(); x.restore();
  if (st === 1) T('fail-fast', BK[0], BK[1] - 58, { w: 700, size: 22, al: 'center', col: ERR, a: P(t, 8.6, 8.8) });
  if (st === 1) T('fallback', lerp(BK[0], O[0], .45) - 30, lerp(BK[1], O[1], .45) + 6, { size: 20, al: 'right', col: C.ac2, a: P(t, 8.7, 9.0) });
  // requests
  for (let i = 0; i < 40; i++) {
    const te = 7.0 + i * .22; if (te > t) break;
    const age = t - te; if (age > 1.3) continue;
    if (i % 2 === 1 || (asusOnline(te) && cbState(te) === 0)) {
      if (age > .7) continue;
      const D = i % 2 === 1 ? O : A, p = oCub(clamp(age / .55));
      circ(lerp(S[0], D[0], p), lerp(S[1], D[1], p), 8, { fill: C.acc, a: 1 - P(age, .55, .7) });
      continue;
    }
    const s = cbState(te);
    if (s === 0) { // node offline, breaker still closed → request hangs and times out
      const p = oCub(clamp(age / .55));
      const px = lerp(S[0], A[0], p), py = lerp(S[1], A[1], p);
      circ(px, py, 8, { fill: age > .55 ? ERR : C.acc, a: 1 - P(age, 1.0, 1.3) });
      if (age > .55) T('✕ timeout', A[0], A[1] - 64 - (age - .55) * 30, { w: 700, size: 22, al: 'center', col: ERR, a: 1 - P(age, 1.0, 1.3) });
    } else if (s === 1) { // open → bounce at the breaker, fall back to omen
      let px, py, col = C.acc;
      if (age < .25) { const p = age / .25; px = lerp(S[0], g1[0], p); py = lerp(S[1], g1[1], p); }
      else { const p = oCub(clamp((age - .25) / .5)); px = lerp(g1[0], O[0], p); py = lerp(g1[1], O[1], p); col = C.ac2; }
      circ(px, py, 8, { fill: col, a: 1 - P(age, .75, .9) });
    } else { // half-open probe
      if (age > .8) continue;
      const p = oCub(clamp(age / .6));
      circ(lerp(S[0], A[0], p), lerp(S[1], A[1], p), 10, { fill: C.ac2, a: 1 - P(age, .6, .8) });
      if (age < .6) T('probe', lerp(S[0], A[0], p), lerp(S[1], A[1], p) - 22, { size: 20, al: 'center', col: C.ac2 });
    }
  }
  // nodes
  const nodes = [[S, 'M5', 'chiamante', C.acc], [A, 'V16', on ? 'asus-v16' : 'asus-v16 · offline', on ? C.acc : ERR], [O, 'OMEN', 'omen-16', C.acc]];
  nodes.forEach(([p, lb, sub, col], k) => {
    const u = (t * .6 + k * .3) % 1;
    if (col !== ERR) circ(p[0], p[1], 40 + u * 40, { stroke: col, lw: 2, a: (1 - u) * .6 * la });
    x.save(); x.translate(p[0], p[1]); x.scale(na, na);
    circ(0, 0, 40, { fill: C.panel, stroke: col, lw: 3, dash: col === ERR ? [6, 6] : null });
    T(lb, 0, 8, { w: 900, size: lb.length > 2 ? 18 : 22, fam: FD, al: 'center', col: col === ERR ? ERR : C.ink });
    x.restore();
    T(sub, p[0], p[1] + 76, { size: 22, al: 'center', col: col === ERR ? ERR : C.mute, a: la });
  });
  // state machine
  const sa = P(t, 7.3, 7.7), SY = 1190, SX = [220, 540, 860], SN = ['CLOSED', 'OPEN', 'HALF_OPEN'], SCOL = [C.acc, ERR, C.ac2];
  if (sa > 0) {
    x.save(); x.globalAlpha *= sa;
    arrow(350, SY, 404, SY, 1, C.line); arrow(670, SY, 724, SY, 1, C.line);
    x.strokeStyle = C.line; x.lineWidth = 3; x.beginPath(); x.moveTo(860, SY + 34); x.quadraticCurveTo(540, SY + 120, 230, SY + 40); x.stroke();
    x.fillStyle = C.line; x.beginPath(); x.moveTo(220, SY + 34); x.lineTo(238, SY + 36); x.lineTo(230, SY + 52); x.closePath(); x.fill();
    SN.forEach((n, i) => {
      const act = i === st, pulse = act ? 1 + .05 * Math.sin(t * 8) : 1;
      pill(SX[i], SY, 250, 66, n, { fill: act ? SCOL[i] : '#14171B', stroke: act ? SCOL[i] : '#3A3E44', col: act ? C.dark : '#9EA39A', size: 26, bold: true, s: pulse });
    });
    x.restore();
  }
  T('AdaptiveMeshCircuitBreaker.for_target("asus-v16")', 540, 1370, { size: 24, al: 'center', a: P(t, 7.6, 8.0) });
  T('call · async_call · fallback automatico', 540, 1420, { size: 22, al: 'center', col: C.mute, a: P(t, 7.8, 8.2) });
  badge(t, '7/7 PASSED', 1510, 10.4);
  x.restore();
}

/* ---------- scene 3 · token bucket (11.0 – 15.8s) ---------- */
const TB = (() => {
  const reqs = [];
  for (let s = 11.8; s < 15.2; s += .5) reqs.push([s, 0]);
  for (let s = 12.0; s < 15.2; s += .7) reqs.push([s, 2]);
  for (let s = 12.8; s < 14.0; s += .08) reqs.push([s, 1]);
  reqs.sort((p, q) => p[0] - q[0]);
  const CAP = 12, RF = .3, dt = 1 / 120, samples = [], served = [];
  let tok = CAP, acc = 0, q = [], ri = 0;
  for (let i = 0; i <= 5.0 / dt; i++) {
    const tt = 11.0 + i * dt;
    acc += dt; if (acc >= RF) { acc -= RF; if (tok < CAP) tok++; }
    while (ri < reqs.length && reqs[ri][0] <= tt) q.push(reqs[ri++]);
    while (q.length && tok > 0) { const r = q.shift(); tok--; served.push([tt, r[1]]); }
    samples.push([tok, q.length, served.length]);
  }
  return { reqs, served, samples, CAP, RF, dt };
})();
function bucket(t) {
  const a = 11.0, b = 15.8;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — TOKEN BUCKET RATE LIMITER', [[['VRAM', C.ink]], [['protetta', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const sm = TB.samples[clamp(Math.floor((t - 11) / TB.dt), 0, TB.samples.length - 1)];
  const [tok, ql, nserved] = sm;
  const va = P(t, 11.3, 11.7);
  const SRC = [['dev loop', 790, C.acc], ['batch notturno', 960, C.ac2], ['chat', 1130, C.ink]];
  const BX0 = 420, BX1 = 660, BY0 = 820, BY1 = 1130, GATE = [BX0, 1000];
  x.save(); x.globalAlpha *= va;
  SRC.forEach(([n, y, col]) => { T(n, 80, y + 8, { size: 22, col: C.ink }); circ(310, y, 8, { fill: col }); });
  // bucket
  x.strokeStyle = '#4A4F55'; x.lineWidth = 6; x.lineJoin = 'round'; x.beginPath(); x.moveTo(BX0, BY0); x.lineTo(BX0, BY1); x.lineTo(BX1, BY1); x.lineTo(BX1, BY0); x.stroke();
  for (let i = 0; i < TB.CAP; i++) {
    const c = i % 4, r = Math.floor(i / 4), tx = BX0 + 22 + c * 52, ty = BY1 - 18 - (r + 1) * 52;
    x.save(); rrect(tx, ty, 40, 40, 8);
    if (i < tok) { x.fillStyle = C.acc; x.fill(); } else { x.strokeStyle = '#2A2D32'; x.lineWidth = 2; x.setLineDash([4, 5]); x.stroke(); }
    x.restore();
  }
  T(`${tok}/${TB.CAP}`, 540, BY0 - 24, { w: 700, size: 26, al: 'center', col: tok === 0 ? ERR : C.acc });
  // refill drip
  const ph = ((t - 11) % TB.RF) / TB.RF;
  if (tok < TB.CAP) { x.save(); x.globalAlpha *= 1 - ph * .3; rrect(530, lerp(700, BY1 - 70 - Math.floor(tok / 4) * 52, iCub(ph)), 20, 20, 5); x.fillStyle = C.acc; x.fill(); x.restore(); }
  T('refill', 540, 700, { size: 20, al: 'center', col: C.mute });
  x.restore();
  // arriving requests
  TB.reqs.forEach(([ta, si]) => {
    if (t < ta - .45 || t >= ta) return;
    const p = ioCub(P(t, ta - .45, ta)), [, y, col] = SRC[si];
    circ(lerp(310, GATE[0] - 10, p), lerp(y, GATE[1], p), 7, { fill: col });
  });
  // queue (wait_and_acquire)
  for (let i = 0; i < Math.min(ql, 10); i++) circ(BX0 + 14 + i * 22, BY1 + 44, 8, { fill: C.ac2, a: va });
  if (ql > 0) T(`coda ${ql} · wait_and_acquire`, BX0, BY1 + 100, { size: 20, col: C.ac2 });
  // served → GPU
  let load = 0;
  TB.served.forEach(([ts, si]) => {
    if (ts <= t) load += Math.max(0, 1 - (t - ts) / 1.0);
    if (t < ts || t > ts + .45) return;
    const p = ioCub(P(t, ts, ts + .45));
    circ(lerp(BX1 + 6, 790, p), 990 + Math.sin(p * Math.PI) * -30, 7, { fill: SRC[si][2] });
  });
  // gpu
  x.save(); x.globalAlpha *= va;
  rrect(790, 820, 210, 310, 22); x.fillStyle = C.panel; x.fill(); x.strokeStyle = '#3A3E44'; x.lineWidth = 2.5; x.stroke();
  T('omen-rtx3070', 895, 800, { size: 20, al: 'center', col: C.mute });
  const vh = 240, vy0 = 860 + vh, lv = clamp(.26 + load * .055, 0, .84);
  rrect(860, 860, 70, vh, 10); x.fillStyle = '#14171B'; x.fill();
  const gg = x.createLinearGradient(0, vy0, 0, 860); gg.addColorStop(0, C.acc); gg.addColorStop(1, C.ac2);
  x.save(); rrect(860, vy0 - vh * lv, 70, vh * lv, 10); x.fillStyle = gg; x.fill(); x.restore();
  seg(845, 860 + vh * .1, 945, 860 + vh * .1, { col: ERR, lw: 3, dash: [8, 6] });
  T('limite', 895, 852, { size: 18, al: 'center', col: ERR });
  T('VRAM', 895, 1122, { w: 700, size: 20, al: 'center', col: C.ink });
  x.restore();
  T(`status() → tokens ${tok}/${TB.CAP} · coda ${ql} · serviti ${nserved}`, 540, 1290, { size: 24, al: 'center', a: P(t, 11.9, 12.3) });
  T('TokenBucketRateLimiter.for_device("omen-rtx3070")', 540, 1370, { size: 24, al: 'center', a: P(t, 12.1, 12.5) });
  T('acquire · wait_and_acquire · acquire_async', 540, 1420, { size: 22, al: 'center', col: C.mute, a: P(t, 12.3, 12.7) });
  badge(t, '7/7 PASSED', 1510, 14.9);
  x.restore();
}

/* ---------- scene 4 · PID (15.6 – 20.4s) ---------- */
const PX0 = 110, PX1 = 980, PY0 = 700, PY1 = 1070, PT = 900, TAU = 4.0, DIST = 2.2;
const devPID = u => 150 * Math.exp(-1.4 * u) * Math.cos(4.2 * u) + (u > DIST ? 115 * Math.exp(-2.2 * (u - DIST)) * Math.cos(5 * (u - DIST)) : 0);
const devRaw = u => 150 * Math.exp(-.3 * u) + (u > DIST ? 120 * (1 - Math.exp(-2 * (u - DIST))) : 0);
const pidY = d => clamp(PT - d, PY0 + 6, PY1 - 6);
function pid(t) {
  const a = 15.6, b = 20.4;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — INFERENCE LATENCY PID', [[['Latenza', C.ink]], [['sotto controllo', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const ca = P(t, 15.9, 16.3);
  x.save(); x.globalAlpha *= ca;
  rrect(PX0 - 30, PY0 - 30, PX1 - PX0 + 60, PY1 - PY0 + 60, 24); x.fillStyle = '#0B0D10'; x.fill(); x.strokeStyle = '#23262B'; x.lineWidth = 2; x.stroke();
  for (let i = 1; i < 4; i++) seg(PX0, lerp(PY0, PY1, i / 4), PX1, lerp(PY0, PY1, i / 4), { col: '#16181C', lw: 2 });
  seg(PX0, PT, PX1, PT, { col: C.acc, lw: 3, dash: [10, 10], a: .9 });
  T('target', PX1, PT - 14, { w: 700, size: 20, al: 'right', col: C.acc });
  T('latenza ↑', PX0, PY0 + 4, { size: 20, col: C.mute });
  T('tempo →', PX1, PY1 + 2, { size: 20, al: 'right', col: C.mute });
  x.restore();
  const hu = TAU * oCub(P(t, 16.1, 19.9) ** 1) ;
  const X = u => lerp(PX0, PX1, u / TAU);
  if (hu > 0) {
    // disturbance marker
    if (hu >= DIST) {
      const da = P(hu, DIST, DIST + .2);
      seg(X(DIST), PY0 + 30, X(DIST), PY1, { col: C.ac2, lw: 2, dash: [5, 8], a: da });
      T('carico MoE', X(DIST) + 12, PY0 + 34, { size: 20, col: C.ac2, a: da });
    }
    // uncontrolled ghost
    x.save(); x.strokeStyle = '#5A5F66'; x.lineWidth = 3; x.setLineDash([6, 8]); x.beginPath();
    for (let i = 0; i <= 120; i++) { const u = hu * i / 120; const yy = pidY(devRaw(u)); i ? x.lineTo(X(u), yy) : x.moveTo(X(u), yy); }
    x.stroke(); x.restore();
    if (hu > 1) T('senza PID', X(hu) - 8, pidY(devRaw(hu)) - 16, { size: 20, al: 'right', col: '#8A8F87' });
    // controlled curve
    x.save(); x.strokeStyle = C.acc; x.lineWidth = 5; x.lineJoin = 'round'; x.shadowColor = C.acc; x.shadowBlur = 16; x.beginPath();
    for (let i = 0; i <= 240; i++) { const u = hu * i / 240; const yy = pidY(devPID(u)); i ? x.lineTo(X(u), yy) : x.moveTo(X(u), yy); }
    x.stroke(); x.restore();
    const hy = pidY(devPID(hu));
    circ(X(hu), hy, 9, { fill: C.acc });
    const u2 = (t * 1.5) % 1; circ(X(hu), hy, 9 + u2 * 26, { stroke: C.acc, lw: 2, a: 1 - u2 });
  }
  // token budget bar
  const d = devPID(hu), f = clamp(.6 - d / 150 * .35, .15, .95);
  const ba = P(t, 16.3, 16.7);
  T('token budget · adjust_token_limit()', PX0 - 30, 1170, { size: 22, col: C.ink, a: ba });
  const dir = d > 12 ? ['▼ riduce', ERR] : d < -12 ? ['▲ rilascia', C.acc] : ['● stabile', C.ac2];
  T(dir[0], PX1 + 30, 1170, { w: 700, size: 22, al: 'right', col: dir[1], a: ba });
  x.save(); x.globalAlpha *= ba;
  rrect(PX0 - 30, 1192, PX1 - PX0 + 60, 30, 15); x.fillStyle = '#14171B'; x.fill();
  rrect(PX0 - 30, 1192, (PX1 - PX0 + 60) * f, 30, 15); x.fillStyle = C.acc; x.fill();
  x.restore();
  T('u(t) = Kp·e + Ki·∫e dt + Kd·de/dt', 540, 1300, { w: 700, size: 28, al: 'center', a: P(t, 16.6, 17.0) });
  T('anti-windup clamping · niente throttling termico', 540, 1356, { size: 22, al: 'center', col: C.mute, a: P(t, 16.8, 17.2) });
  T('da uno studio AST notturno su OMEN · Granite 3.3', 540, 1398, { size: 22, al: 'center', col: C.ac2, a: P(t, 17.0, 17.4) });
  badge(t, '5/5 PASSED', 1490, 19.4);
  x.restore();
}

/* ---------- scene 5 · causal × mission control (20.2 – 25.0s) ---------- */
const MS = [['trend:swarm', 'mission:a1', true], ['trend:moe', 'mission:b2', false], ['trend:rag', 'mission:c3', true]];
const MLOG = [];
MS.forEach(([tr, mi, ok], k) => {
  const s = 20.7 + k * .95;
  MLOG.push([s + .55, [['+ ', C.acc], [tr + ' → ' + mi, C.ink]]]);
  MLOG.push([s + 1.75, [['+ ', C.acc], [mi + ' → ', C.ink], [ok ? 'success' : 'error:timeout', ok ? C.acc : ERR]]]);
});
MLOG.sort((p, q) => p[0] - q[0]);
function missions(t) {
  const a = 20.2, b = 25.0;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — CAUSAL AI × MISSION CONTROL', [[['Ogni missione', C.ink]], [['lascia traccia', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const LY = [740, 880, 1020], NX = [210, 540, 870], NW = 250;
  T('trend scouting', NX[0], 668, { size: 20, al: 'center', col: C.mute, a: P(t, 20.5, 20.8) });
  T('missione', NX[1], 668, { size: 20, al: 'center', col: C.mute, a: P(t, 20.5, 20.8) });
  T('finish()', NX[2], 668, { size: 20, al: 'center', col: C.mute, a: P(t, 20.5, 20.8) });
  MS.forEach(([tr, mi, ok], k) => {
    const s = 20.7 + k * .95, y = LY[k];
    arrow(NX[0] + NW / 2 + 6, y, NX[1] - NW / 2 - 10, y, ioCub(P(t, s + .25, s + .55)), C.acc);
    arrow(NX[1] + NW / 2 + 6, y, NX[2] - NW / 2 - 10, y, ioCub(P(t, s + 1.1, s + 1.35)), ok ? C.acc : ERR);
    pill(NX[0], y, NW, 60, tr, { s: oBack(P(t, s, s + .3)), size: 22, stroke: C.ac2, col: C.ink });
    const ms = oBack(P(t, s + .5, s + .8)), running = t >= s + .6 && t < s + 1.15, done = t >= s + 1.15;
    pill(NX[1], y, NW, 60, mi, { s: ms, size: 22, stroke: done ? (ok ? C.acc : ERR) : '#4A4F55', col: C.ink });
    if (running) { x.save(); rrect(NX[1] - NW / 2 - 8, y - 38, NW + 16, 76, 38); x.strokeStyle = C.acc; x.lineWidth = 3; x.setLineDash([24, 200]); x.lineDashOffset = -t * 500; x.stroke(); x.restore(); }
    const os = oBack(P(t, s + 1.3, s + 1.6));
    pill(NX[2], y, NW, 60, ok ? '✓ successo' : '✕ timeout', { s: os, size: 22, fill: ok ? C.tint : '#2A1512', stroke: ok ? C.acc : ERR, col: ok ? C.acc : ERR, bold: true });
    // packets into the causal graph
    [[s + .55, NX[0], C.ac2], [s + 1.35, NX[2], ok ? C.acc : ERR]].forEach(([ts, px, col]) => {
      if (t < ts - .4 || t > ts) return;
      const p = ioCub(P(t, ts - .4, ts));
      circ(lerp(px, 540, p), lerp(y + 32, 1150, p), 8, { fill: col });
    });
  });
  // json panel
  const pa = P(t, 20.6, 21.0);
  x.save(); x.globalAlpha *= pa;
  rrect(60, 1150, 960, 300, 24); x.fillStyle = C.term; x.fill(); x.strokeStyle = '#2A2D32'; x.lineWidth = 2; x.stroke();
  T('data/research/causal_memory_graph.json', 96, 1194, { size: 20, col: C.dim });
  seg(62, 1214, 1018, 1214, { col: '#1C1F23', lw: 2 });
  let li = 0;
  MLOG.forEach(([ts, segs]) => {
    if (t < ts) return;
    const p = oExpo(P(t, ts, ts + .3)), y = 1254 + li * 34;
    let px = 96 - (1 - p) * 30;
    x.save(); x.globalAlpha *= p;
    if (t < ts + .5) { x.fillStyle = 'rgba(198,244,50,0.08)'; x.fillRect(62, y - 24, 956, 32); }
    segs.forEach(([s, col]) => { T(s, px, y, { size: 22, col }); px += measure(s, 400, 22, FM); });
    x.restore(); li++;
  });
  x.restore();
  T('MissionStore.finish() · handle_api_missions_create', 540, 1506, { size: 22, al: 'center', col: C.mute, a: P(t, 21.2, 21.6) });
  badge(t, '18/18 PASSED', 1586, 24.2);
  x.restore();
}

/* ---------- scene 6 · test suite (24.8 – 27.6s) ---------- */
const TS = [['test_adaptive_mesh_circuit_breaker.py', 7], ['test_token_bucket_rate_limiter.py', 7], ['test_inference_latency_pid.py', 5], ['test_mission.py', 18]];
function tests(t) {
  const a = 24.8, b = 27.6;
  if (t < a || t > b) return;
  header(t, a, b, '05', '05 — TEST SUITE', [[['Tutto', C.ink]], [['verde.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const n = Math.round(37 * oCub(P(t, 25.2, 26.6)));
  const nn = String(n).padStart(2, '0');
  T(nn + '/37', 540, 880, { w: 900, size: 210, fam: FD, al: 'center', col: n === 37 ? C.acc : C.ink, ls: -6, a: P(t, 25.1, 25.4) });
  T('PASSED', 540, 950, { w: 700, size: 30, al: 'center', col: C.acc, ls: 12, a: P(t, 25.2, 25.5) });
  for (let i = 0; i < 37; i++) {
    const c = i % 13, r = Math.floor(i / 13), cx = 540 + (c - 6) * 58, cy = 1040 + r * 56;
    const lit = i < n, pop = lit ? oBack(clamp((37 * oCub(P(t, 25.2, 26.6)) - i) * 2)) : 1;
    circ(cx, cy, lit ? 11 * pop : 10, lit ? { fill: C.acc } : { stroke: '#3A3E44', lw: 2 });
  }
  let acc = 0;
  TS.forEach(([f, k], i) => {
    const y = 1260 + i * 56;
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
  tagline: 'La mesh che si protegge da sola.',
  sc: [{ a: 6.4, b: 11.2, n: '01' }, { a: 11.0, b: 15.8, n: '02' }, { a: 15.6, b: 20.4, n: '03' }, { a: 20.2, b: 25.0, n: '04' }, { a: 24.8, b: 27.6, n: '05' }],
  cuts: [3.1, 6.5, 11.1, 15.7, 20.3, 24.9, 27.5],
  scenes: [headline, breaker, bucket, pid, missions, tests]
};
