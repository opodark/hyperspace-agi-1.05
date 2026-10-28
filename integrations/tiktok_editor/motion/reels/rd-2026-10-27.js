// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "rd-2026-10-27", "title": "00MESH Reel 1.05", "aria": "Animazione di 30 secondi: la mesh di tre nodi si forma, poi scorrono i cinque filoni R&D di HyperSpace AGI 1.05 — coscienza sintetica, endospore crittografiche, swarm stigmergico, protocolli sovrani, causal AI — e chiude sul logo 00MESH."}
/* R&D log del 27/10/2026: coscienza sintetica, endospore, swarm, protocolli, causal AI. */

/* ---------- scene 1 · headline (3.0 – 6.6s) ---------- */
function headline(t) {
  const a = 3.0, b = 6.6;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .3);
  x.save(); x.globalAlpha = e;
  const kick = 'R&D LOG · 26–27 OTTOBRE 2026';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .6))), 80, 640, { w: 700, size: 24, col: C.acc, ls: 3 });
  const widest = measure('e', 900, 124, FD, -2) + 124 * .27 + measure('sopravvive.', 900, 124, FD, -2);
  const size = Math.min(124, 124 * 920 / widest), LH = size * 1.14;
  words(t, [[['La', C.ink], ['mesh', C.ink], ['che', C.ink]], [['sogna,', C.acc]], [['ricorda', C.ink]], [['e', C.ink], ['sopravvive.', C.ac2]]],
    80, 790, LH, size, a + .2, .11, .9, b - .5);
  const yb = 790 + 3 * LH;
  seg(80, yb + 90, 420, yb + 90, { col: C.acc, lw: 6, p: oExpo(P(t, 4.7, 5.3)) * (1 - iCub(P(t, 6.1, 6.5))) });
  T('Infrastruttura AGI sovrana e distribuita.', 80, yb + 170, { w: 500, size: 42, fam: FD, col: C.mute, a: oCub(P(t, 4.9, 5.4)) * (1 - P(t, 6.1, 6.4)) });
  x.restore();
}

/* ---------- scene 2 · coscienza (6.4 – 11.0s) ---------- */
const AX = [['Depiction of Self', 'persona.json · audit identitario'], ['Imagination', 'persona_dream.py · sogno controfattuale'],
  ['Attention', 'Caveman engine · token governor'], ['Planning', 'RFC-0043 · DAG topologico'], ['Emotion & Valencing', 'gate Human-in-the-Loop']];
function coscienza(t) {
  const a = 6.4, b = 11.0;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — COSCIENZA SINTETICA', [[['Assiomi di', C.ink]], [['Igor Aleksander', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const cx = 540, cy = 1060, R = [70, 125, 180, 235, 290], sp = [2.2, -1.6, 1.15, -.85, .6];
  const kp = P(t, 7.5, 10.8), k = t < 7.5 ? -1 : Math.min(4, Math.floor(kp * 5)), lp = Math.min(1, kp * 5 - Math.max(0, k));
  R.forEach((r, i) => {
    const p = oCub(P(t, 6.9 + i * .12, 7.6 + i * .12)); if (p <= 0) return;
    const on = i === k;
    x.save(); x.strokeStyle = on ? C.acc : C.line; x.lineWidth = on ? 5 : 2.5; x.beginPath();
    x.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * p); x.stroke(); x.restore();
    const g = t * sp[i] + i * 1.3, dx = cx + Math.cos(g) * r, dy = cy + Math.sin(g) * r;
    circ(dx, dy, on ? 12 : 8, { fill: on ? C.acc : C.mute, a: p });
    if (on) circ(dx, dy, 12 + lp * 44, { stroke: C.acc, lw: 2, a: 1 - lp });
  });
  circ(cx, cy, 26 * (1 + .12 * Math.sin(t * 5)), { fill: C.ac2, a: P(t, 6.8, 7.2) });
  for (let q = 0; q < 2; q++) { const u = (t * .7 + q * .5) % 1; circ(cx, cy, 26 + u * 40, { stroke: C.ac2, lw: 2, a: (1 - u) * P(t, 6.8, 7.2) }); }
  if (k >= 0) {
    const al = clamp(lp * 7) * (k === 4 ? 1 : 1 - clamp((lp - .88) * 9));
    const dy = (1 - oExpo(clamp(lp * 4))) * 34;
    T('ASSIOMA 0' + (k + 1), 540, 1426 + dy, { w: 700, size: 24, col: C.acc, al: 'center', ls: 5, a: al });
    T(AX[k][0], 540, 1496 + dy, { w: 900, size: 62, fam: FD, al: 'center', a: al, ls: -1 });
    T(AX[k][1], 540, 1552 + dy, { size: 26, col: C.ac2, al: 'center', a: al });
  }
  for (let i = 0; i < 5; i++) circ(540 + (i - 2) * 32, 1612, i === k ? 7 : 5, { fill: i === k ? C.acc : C.line, a: P(t, 7.3, 7.6) });
  x.restore();
}

/* ---------- scene 3 · endospore (10.8 – 15.4s) ---------- */
const SH = [[540, 700, 'alberto-founder', -1], [254, 1195, 'guido-cips-partner', 1], [826, 1195, 'offline-paper-vault', 1]];
const CL = [[100, 905, 'MEGA', 'left'], [980, 905, 'Dropbox', 'right'], [100, 1095, 'OneDrive', 'left'], [980, 1095, 'WebDAV/S3', 'right']];
function ecgY(rx) {
  const pts = [[0, 0], [290, 0], [310, -16], [330, 10], [348, -78], [366, 46], [384, 0], [680, 0]];
  for (let i = 1; i < pts.length; i++) if (rx <= pts[i][0]) { const [x0, y0] = pts[i - 1], [x1, y1] = pts[i]; return lerp(y0, y1, (rx - x0) / (x1 - x0)); }
  return 0;
}
function spore(t) {
  const a = 10.8, b = 15.4;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — ENDOSPORE CRITTOGRAFICHE', [[['Continuità', C.ink]], [['biomimetica', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const cx = 540, cy = 1030, s = oBack(P(t, 11.1, 11.8));
  ring(cx, cy, 205 * s, { col: C.acc, lw: 2.5, dash: [2, 12], rot: t * .3, a: .8 });
  ring(cx, cy, 155 * s, { col: '#3A3E44', lw: 16, dash: [52, 18], rot: -t * .5 });
  ring(cx, cy, 115 * s, { col: C.ac2, lw: 3, dash: [150, 36, 8, 36], rot: t * .8 });
  // spores flying to the clouds
  const ca = P(t, 13.1, 13.5);
  CL.forEach((c, ci) => {
    if (t >= 13.2) for (let q = 0; q < 5; q++) {
      const u = ((t - 13.2) * .8 + q / 5 + ci * .13) % 1, pe = oCub(u);
      circ(lerp(cx, c[0], pe), lerp(cy, c[1], pe) - Math.sin(u * Math.PI) * 40, 5.5, { fill: C.ac2, a: Math.sin(Math.PI * u) * ca });
    }
    circ(c[0], c[1], 8, { fill: C.ac2, a: ca });
    circ(c[0], c[1], 8 + ((t * .9 + ci * .25) % 1) * 22, { stroke: C.ac2, lw: 2, a: ca * (1 - ((t * .9 + ci * .25) % 1)) });
    T(c[2], c[3] === 'left' ? c[0] + 22 : c[0] - 22, c[1] + 8, { size: 22, al: c[3], col: C.ink, a: ca });
  });
  // core + lock
  circ(cx, cy, 72 * s, { fill: '#13160C', stroke: C.acc, lw: 3 });
  const lk = oBack(P(t, 11.9, 12.25)), sy = (1 - lk) * -18;
  x.save(); x.globalAlpha *= clamp(s); x.strokeStyle = C.acc; x.lineWidth = 7; x.lineCap = 'round'; x.beginPath();
  x.moveTo(cx - 19, cy - 4 + sy); x.lineTo(cx - 19, cy - 16 + sy); x.arc(cx, cy - 16 + sy, 19, Math.PI, 0); x.lineTo(cx + 19, cy - 4 + sy); x.stroke();
  x.fillStyle = C.acc; rrect(cx - 30, cy - 6, 60, 44, 8); x.fill(); x.restore();
  circ(cx, cy + 12, 6, { fill: '#13160C', a: clamp(s) });
  // shamir shards
  const shA = SH.map((_, i) => oBack(P(t, 12.0 + i * .15, 12.5 + i * .15)));
  const pairs = [[0, 1], [1, 2], [2, 0]];
  const act = t >= 12.6 ? Math.floor((t - 12.6) / .8) % 3 : -1, ap = t >= 12.6 ? ((t - 12.6) / .8) % 1 : 0;
  pairs.forEach(([i, j], k) => {
    const A = SH[i], B = SH[j];
    seg(A[0], A[1], B[0], B[1], { col: C.line, lw: 2, a: clamp(Math.min(shA[i], shA[j])), dash: [6, 10] });
    if (k === act) seg(A[0], A[1], B[0], B[1], { col: C.acc, lw: 5, a: Math.sin(Math.PI * ap), p: oCub(clamp(ap * 2)) });
  });
  SH.forEach((d, i) => {
    const sc = shA[i]; if (sc <= 0) return;
    const on = act >= 0 && pairs[act].includes(i);
    x.save(); x.translate(d[0], d[1]); x.rotate(Math.PI / 4); x.scale(sc, sc);
    x.fillStyle = on ? C.acc : C.panel; x.strokeStyle = C.acc; x.lineWidth = 3; x.fillRect(-18, -18, 36, 36); x.strokeRect(-18, -18, 36, 36); x.restore();
    T(d[2], d[0], d[1] + (d[3] < 0 ? -44 : 62), { size: 22, al: 'center', col: on ? C.ink : C.mute, a: clamp(sc) });
  });
  T('SHAMIR 2-SU-3 · GF(2⁸)', 540, 1350, { w: 700, size: 30, al: 'center', ls: 2, a: P(t, 12.6, 13.0) });
  // dead-man's switch heartbeat
  const ea = P(t, 12.4, 12.8);
  if (ea > 0) {
    const head = 680 * (((t - 12.4) / 1.3) % 1);
    x.save(); x.globalAlpha *= ea; x.strokeStyle = C.line; x.lineWidth = 2; x.beginPath(); x.moveTo(200, 1450); x.lineTo(880, 1450); x.stroke();
    x.strokeStyle = C.acc; x.lineWidth = 4; x.lineJoin = 'round'; x.shadowColor = C.acc; x.shadowBlur = 14; x.beginPath();
    for (let rx = 0; rx <= head; rx += 4) { const yy = 1450 + ecgY(rx); rx ? x.lineTo(200 + rx, yy) : x.moveTo(200, yy); }
    x.stroke(); x.restore();
    circ(200 + head, 1450 + ecgY(head), 7, { fill: C.acc, a: ea });
    T('dead-man’s switch · heartbeat', 540, 1520, { size: 22, al: 'center', col: C.mute, a: ea });
    T('AES-256-GCM · HKDF-SHA256 · multi-cloud', 540, 1566, { size: 22, al: 'center', col: C.mute, a: P(t, 13.4, 13.8) });
  }
  x.restore();
}

/* ---------- scene 4 · swarm (15.2 – 19.8s) ---------- */
const CURVES = [[[150, 800], [350, 600], [730, 600], [930, 800]], [[150, 800], [400, 830], [680, 770], [930, 800]], [[150, 800], [350, 1000], [730, 1000], [930, 800]]];
const bez = (c, u) => { const v = 1 - u; return [0, 1].map(d => v * v * v * c[0][d] + 3 * v * v * u * c[1][d] + 3 * v * u * u * c[2][d] + u * u * u * c[3][d]); };
const EV = [[300, 1150, '[1,0,0]', 'acc', 16.7, -1], [380, 1390, '[0,0,1]', 'ac2', 17.0, 1], [500, 1270, '[1,1,0]', 'acc', 17.15, 1],
  [640, 1270, '[1,2,0]', 'acc', 17.45, 1], [800, 1150, '[2,0,0]', 'ac2', 17.9, -1], [860, 1390, '[1,2,2]', 'acc', 18.15, 1]];
function swarm(t) {
  const a = 15.2, b = 19.8;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — SWARM · IN PRODUZIONE', [[['Memoria', C.ink]], [['stigmergica', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const na = P(t, 15.5, 15.9);
  CURVES.forEach((c, k) => {
    const s0 = 15.7 + k * .55, dp = ioCub(P(t, s0, s0 + 1.1));
    if (dp <= 0) return;
    const ev = Math.exp(-1.1 * Math.max(0, t - (s0 + 1.1)));
    const col = k === 2 ? C.ac2 : C.acc;
    x.save(); x.globalAlpha *= ev; x.strokeStyle = col; x.lineWidth = 12; x.lineCap = 'round'; x.shadowColor = col; x.shadowBlur = 24; x.beginPath();
    for (let i = 0; i <= 60; i++) { const p = bez(c, i / 60 * dp); i ? x.lineTo(p[0], p[1]) : x.moveTo(p[0], p[1]); }
    x.stroke(); x.restore();
    for (let q = 0; q < 3; q++) { const u = ((t - s0) * .45 + q / 3) % 1; const p = bez(c, u); circ(p[0], p[1], 7, { fill: C.ink }); }
  });
  circ(150, 800, 26, { fill: C.panel, stroke: C.ink, lw: 3, a: na });
  circ(930, 800, 26, { fill: C.panel, stroke: C.acc, lw: 3, a: na });
  const u0 = (t * .8) % 1; circ(930, 800, 26 + u0 * 40, { stroke: C.acc, lw: 2, a: (1 - u0) * na });
  T('agenti', 150, 872, { size: 22, al: 'center', col: C.mute, a: na });
  T('task', 930, 872, { size: 22, al: 'center', col: C.mute, a: na });
  T('I(t) = I₀ · e^(−λt)', 540, 1032, { size: 26, al: 'center', col: C.mute, a: P(t, 16.6, 17.0) });
  // vector clocks
  ['M5', 'OMEN', 'V16'].forEach((n, i) => {
    const y = 1150 + i * 120, p = oCub(P(t, 16.2 + i * .1, 16.8 + i * .1));
    T(n, 80, y + 8, { size: 24, col: C.ink, a: p });
    seg(210, y, 1000, y, { col: C.line, lw: 3, p });
  });
  arrow(300, 1150, 488, 1260, ioCub(P(t, 16.8, 17.15)), C.acc);
  arrow(640, 1270, 848, 1380, ioCub(P(t, 17.55, 18.15)), C.acc);
  EV.forEach(([ex, ey, lb, ck, te, side]) => {
    const p = oBack(P(t, te, te + .35)); if (p <= 0) return;
    const col = C[ck];
    circ(ex, ey, 11 * p, { fill: col });
    T(lb, ex, side < 0 ? ey - 26 : ey + 48, { size: 22, al: 'center', col: C.ink, a: clamp(p) });
  });
  const bp = oBack(P(t, 18.5, 18.85));
  if (bp > 0) {
    const lb = '[2,0,0] ‖ [1,2,2] → concorrenti', wd = measure(lb, 700, 26, FM) + 56;
    x.save(); x.translate(540, 1500); x.scale(bp, bp); rrect(-wd / 2, -34, wd, 64, 32); x.fillStyle = '#1A1630'; x.fill();
    x.strokeStyle = C.ac2; x.lineWidth = 2; x.stroke(); T(lb, 0, 9, { w: 700, size: 26, al: 'center', col: C.ac2 }); x.restore();
  }
  T('Consenso senza master · zero lock centrali', 540, 1590, { size: 22, al: 'center', col: C.mute, a: P(t, 18.7, 19.1) });
  x.restore();
}

/* ---------- scene 5 · protocolli (19.6 – 23.8s) ---------- */
const TL = [
  [['→ ', 'dim'], ['GET /web-node/llms.txt ', 'ink'], ['200', 'acc']],
  [['→ ', 'dim'], ['GET /.well-known/ai-agent.json ', 'ink'], ['200', 'acc']],
  [['  ', 'dim'], ['capabilities: inference · rate-limit', 'mute']],
  [['⇄ ', 'dim'], ['negoziazione inferenza ', 'ink'], ['ok', 'acc']],
  [['◆ ', 'dim'], ['key_hint ✓ ', 'ink'], ['sha256 match', 'mute']],
  [['◇ ', 'dim'], ['qwen3 · thinking ', 'ink'], ['isolato', 'ac2']],
  [['← ', 'dim'], ['content ', 'ink'], ['pulito', 'acc'], [' · reasoning separato', 'mute']],
  [['● ', 'acc'], ['handshake completato', 'ink']]
];
function proto(t) {
  const a = 19.6, b = 23.8;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — TEST LIVE · 27 OTT', [[['Protocolli', C.ink]], [['sovrani', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const ap = oExpo(P(t, 19.95, 20.6)), oy = (1 - ap) * 80;
  const X0 = 60, Y0 = 640 + oy, TW = 960, TH = 780;
  x.save(); x.globalAlpha *= ap;
  rrect(X0, Y0, TW, TH, 28); x.fillStyle = C.term; x.fill(); x.strokeStyle = '#2A2D32'; x.lineWidth = 2; x.stroke();
  [0, 1, 2].forEach(i => circ(X0 + 40 + i * 28, Y0 + 38, 8, { fill: '#2C3036' }));
  T('agent-handshake · mesh.zerozerocomputer.it', X0 + 140, Y0 + 46, { size: 22, col: C.dim });
  seg(X0 + 2, Y0 + 76, X0 + TW - 2, Y0 + 76, { col: '#1C1F23', lw: 2 });
  x.save(); rrect(X0, Y0 + 78, TW, TH - 80, [0, 0, 28, 28]); x.clip();
  const sy = Y0 + 78 + ((t * 300) % (TH + 200)) - 200;
  const g = x.createLinearGradient(0, sy, 0, sy + 200);
  g.addColorStop(0, 'rgba(198,244,50,0)'); g.addColorStop(.5, 'rgba(198,244,50,0.06)'); g.addColorStop(1, 'rgba(198,244,50,0)');
  x.fillStyle = g; x.fillRect(X0, sy, TW, 200);
  let cursorAt = null;
  TL.forEach((ln, li) => {
    const ts = 20.5 + li * .32; if (t < ts) return;
    let n = Math.floor((t - ts) * 75), px = X0 + 44;
    const y = Y0 + 150 + li * 76;
    for (const [s, ck] of ln) {
      if (n <= 0) break;
      const part = s.slice(0, n); n -= s.length;
      T(part, px, y, { size: 28, col: C[ck] });
      px += measure(part, 400, 28, FM);
    }
    cursorAt = [px, y];
  });
  if (cursorAt && Math.floor(t * 4) % 2 === 0) T('▍', cursorAt[0] + 4, cursorAt[1], { size: 28, col: C.acc });
  x.restore(); x.restore();
  T('Discovery autonoma · thinking isolato · chiavi SHA-256', 540, 1510, { size: 22, al: 'center', col: C.mute, a: P(t, 21.2, 21.6) });
  x.restore();
}

/* ---------- scene 6 · causal (23.6 – 27.6s) ---------- */
const CN = { pipe: [330, 740, 'pipeline ✓'], blk: [750, 740, 'blocco ✕'], a: [200, 880, 'agente α'], b: [540, 880, 'agente β'], m: [880, 880, 'merge'],
  st: [330, 1020, 'sub-task'], rt: [750, 1020, 'retry'], tc: [200, 1160, 'tool call'], rl: [540, 1160, 'rate-limit'], cx: [880, 1160, 'context'],
  cm: [330, 1300, 'commit'], cf: [750, 1300, 'config'] };
const CE = [['blk', 'b'], ['blk', 'm'], ['pipe', 'a'], ['pipe', 'b'], ['b', 'rt'], ['m', 'rt'], ['a', 'st'], ['rt', 'rl'], ['rt', 'cx'], ['st', 'tc'], ['rl', 'cf'], ['cx', 'cf'], ['tc', 'cm']];
const LV = { blk: 24.5, b: 24.95, m: 24.95, rt: 25.4, rl: 25.85, cx: 25.85, cf: 26.3 };
function causal(t) {
  const a = 23.6, b = 27.6;
  if (t < a || t > b) return;
  header(t, a, b, '05', '05 — CAUSAL AI · PEARL-STYLE', [[['Root-cause', C.ink]], [['lineage', C.ink]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const ea = P(t, 24.1, 24.4);
  CE.forEach(([p, c]) => {
    const A = CN[p], B = CN[c];
    seg(A[0], A[1] + 31, B[0], B[1] - 31, { col: C.line, lw: 2.5, a: ea });
    if (LV[p] != null && LV[c] != null && LV[c] > LV[p]) {
      const q = ioCub(P(t, LV[c] - .45, LV[c]));
      seg(A[0], A[1] + 31, B[0], B[1] - 31, { col: C.acc, lw: 4, p: q });
      if (q > 0 && q < 1) circ(lerp(A[0], B[0], q), lerp(A[1] + 31, B[1] - 31, q), 8, { fill: C.acc });
    }
  });
  if (t > 24.3) { const u = ((t - 24.3) * .8) % 1; rrect(750 - 115 - u * 24, 740 - 31 - u * 24, 230 + u * 48, 62 + u * 48, 31 + u * 24); x.save(); x.globalAlpha *= (1 - u); x.strokeStyle = C.ac2; x.lineWidth = 2; x.stroke(); x.restore(); }
  Object.entries(CN).forEach(([key, [nx, ny, lb]]) => {
    const li = (ny - 740) / 140, p = oBack(P(t, 23.9 + li * .08, 24.3 + li * .08)); if (p <= 0) return;
    const vis = LV[key] != null && t >= LV[key], root = key === 'cf' && t >= LV.cf;
    const pulse = vis ? 1 + .12 * Math.sin(Math.PI * clamp((t - LV[key]) / .3)) : 1;
    x.save(); x.translate(nx, ny); x.scale(p * pulse, p * pulse);
    rrect(-115, -31, 230, 62, 31); x.fillStyle = root ? C.acc : vis ? C.tint : '#14171B'; x.fill();
    x.strokeStyle = vis ? C.acc : '#3A3E44'; x.lineWidth = 2.5; x.stroke();
    T(lb, 0, 9, { size: 26, al: 'center', col: root ? C.dark : vis ? C.ink : '#C9CCC4', w: root ? 700 : 400 });
    x.restore();
  });
  if (t >= LV.cf) {
    const u = ((t - LV.cf) * .9) % 1;
    x.save(); x.globalAlpha *= 1 - u; rrect(750 - 115 - u * 30, 1300 - 31 - u * 30, 230 + u * 60, 62 + u * 60, 31 + u * 30); x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke(); x.restore();
    T('CAUSA RADICE', 750, 1388, { w: 700, size: 26, al: 'center', col: C.acc, ls: 4, a: P(t, 26.35, 26.6) });
  }
  T('58 nodi · 52 archi · BFS retrospettivo', 540, 1476, { size: 24, al: 'center', col: C.mute, a: P(t, 24.3, 24.7) });
  T('prossimo passo: do-calculus predittivo', 540, 1524, { size: 22, al: 'center', col: C.ac2, a: P(t, 26.5, 26.9) });
  x.restore();
}

const REEL = {
  date: '27.10.2026',
  tagline: 'La mesh che sogna, ricorda e sopravvive.',
  sc: [{ a: 6.4, b: 11.0, n: '01' }, { a: 10.8, b: 15.4, n: '02' }, { a: 15.2, b: 19.8, n: '03' }, { a: 19.6, b: 23.8, n: '04' }, { a: 23.6, b: 27.6, n: '05' }],
  cuts: [3.1, 6.5, 10.9, 15.3, 19.7, 23.7, 27.5],
  scenes: [headline, coscienza, spore, swarm, proto, causal]
};
