// SPDX-License-Identifier: Apache-2.0
/* HyperSpace Motion Reels — motore condiviso (canvas 1080×1920 o 1920×1080, 30 s o più).
   build.py lo concatena in quest'ordine dentro un'unica IIFE, preceduto da `const CFG = {dur, land}`:
   runtime.js (helper e motivi) → reels/<id>.js (scene + const REEL) → player.js.
   Le scene disegnano sempre in coordinate verticali 1080×1920. In orizzontale (CFG.land) le scene vanno
   su una tela verticale fuori schermo: header() scrive il titolo nella colonna sinistra e la parte
   visiva (REEL.crop, in y verticali) viene copiata nella colonna destra. */

const LAND = CFG.land, W = LAND ? 1920 : 1080, H = LAND ? 1080 : 1920, DUR = CFG.dur, PW = 1080, PH = 1920;
const C = { bg:'#07080A', panel:'#0E1013', ink:'#E8EAE3', mute:'#9EA39A', dim:'#6E736C', line:'#2C3036', grid:'#15171B',
  acc:'#C6F432', ac2:'#A99BFF', term:'#050607', tint:'#1C2209', dark:'#0A0B07' };
const FD = '"MeshDisplay","Inter Display",system-ui,sans-serif';
const FM = '"MeshMono","DejaVu Sans Mono",ui-monospace,monospace';
const cv = document.getElementById('cv'), X0 = cv.getContext('2d');
const pcv = LAND ? Object.assign(document.createElement('canvas'), { width: PW, height: PH }) : null;
const PX = pcv ? pcv.getContext('2d') : X0;
let x = X0; // contesto corrente: in orizzontale le scene disegnano su PX
function onMain(fn) { const k = x; x = X0; try { fn(); } finally { x = k; } }
let HNUM = null; // numero di scena imposto da un reel che ne raccoglie altri (vedi header)

/* ---------- math & easing ---------- */
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, p) => a + (b - a) * p;
const P = (t, a, b) => clamp((t - a) / (b - a));
const oExpo = p => p >= 1 ? 1 : 1 - Math.pow(2, -10 * p);
const oCub = p => 1 - Math.pow(1 - p, 3);
const iCub = p => p * p * p;
const ioCub = p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
const oBack = p => { const c1 = 1.70158, c3 = c1 + 1; return p <= 0 ? 0 : 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); };
const env = (t, a, b, fi = .4, fo = .4) => Math.min(oCub(P(t, a, a + fi)), 1 - iCub(P(t, b - fo, b)));

/* ---------- drawing helpers ---------- */
function setF(w, s, fam) { x.font = `${w} ${s}px ${fam}`; }
function T(s, X, Y, o = {}) {
  const { w = 400, size = 28, fam = FM, col = C.ink, al = 'left', a = 1, ls = 0 } = o;
  if (a <= 0) return;
  x.save(); x.globalAlpha *= a; setF(w, size, fam); x.letterSpacing = ls + 'px';
  x.fillStyle = col; x.textAlign = al; x.textBaseline = 'alphabetic'; x.fillText(s, X, Y); x.restore();
}
function measure(s, w, size, fam, ls = 0) {
  x.save(); setF(w, size, fam); x.letterSpacing = ls + 'px'; const m = x.measureText(s).width; x.restore(); return m;
}
function circ(cx, cy, r, o = {}) {
  const { fill, stroke, lw = 2, a = 1, dash } = o;
  if (a <= 0 || r <= 0) return;
  x.save(); x.globalAlpha *= a; x.beginPath(); x.arc(cx, cy, r, 0, Math.PI * 2);
  if (fill) { x.fillStyle = fill; x.fill(); }
  if (stroke) { x.lineWidth = lw; x.strokeStyle = stroke; if (dash) x.setLineDash(dash); x.stroke(); }
  x.restore();
}
function seg(x1, y1, x2, y2, o = {}) {
  const { col = C.line, lw = 2, a = 1, dash, off = 0, p = 1 } = o;
  if (a <= 0 || p <= 0) return;
  x.save(); x.globalAlpha *= a; x.strokeStyle = col; x.lineWidth = lw; x.lineCap = 'round';
  if (dash) { x.setLineDash(dash); x.lineDashOffset = off; }
  x.beginPath(); x.moveTo(x1, y1); x.lineTo(lerp(x1, x2, p), lerp(y1, y2, p)); x.stroke(); x.restore();
}
function ring(cx, cy, r, o = {}) {
  const { col, lw = 2, dash, rot = 0, a = 1 } = o;
  if (r <= 0 || a <= 0) return;
  x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.rotate(rot); x.strokeStyle = col; x.lineWidth = lw;
  if (dash) x.setLineDash(dash); x.beginPath(); x.arc(0, 0, r, 0, Math.PI * 2); x.stroke(); x.restore();
}
function rrect(X, Y, w, h, r) { x.beginPath(); x.roundRect(X, Y, w, h, r); }

/* word-by-word masked reveal, used for every headline */
function words(t, lines, X, Y0, LH, size, t0, stag, dur, tOut) {
  let i = 0;
  const sp = size * .27;
  lines.forEach((ln, li) => {
    const y = Y0 + li * LH;
    let cx = X;
    for (const [s, col] of ln) {
      const wd = measure(s, 900, size, FD, -2);
      const pin = oExpo(P(t, t0 + i * stag, t0 + i * stag + dur));
      const pout = tOut != null ? iCub(P(t, tOut + i * .03, tOut + i * .03 + .35)) : 0;
      if (pin > 0 && pout < 1) {
        const dy = (1 - pin) * size * 1.15 - pout * size * 1.15;
        x.save(); x.beginPath(); x.rect(cx - 8, y - size * 1.0, wd + 16, size * 1.3); x.clip();
        T(s, cx, y + dy, { w: 900, size, fam: FD, col, ls: -2 });
        x.restore();
      }
      cx += wd + sp; i++;
    }
  });
}
/* letter cascade for the wordmark */
function letters(t, str, cx, y, size, t0, stag, dur) {
  const ch = [...str], ls = -4;
  const ws = ch.map(c => measure(c, 900, size, FD, ls));
  let px = cx - ws.reduce((a, b) => a + b, 0) / 2;
  ch.forEach((c, i) => {
    const p = oExpo(P(t, t0 + i * stag, t0 + i * stag + dur));
    if (p > 0) {
      x.save(); x.beginPath(); x.rect(px - 12, y - size, ws[i] + 24, size * 1.28); x.clip();
      T(c, px, y + (1 - p) * size, { w: 900, size, fam: FD, col: c === '0' ? C.acc : C.ink, ls });
      x.restore();
    }
    px += ws[i];
  });
}

/* ---------- persistent layers ---------- */
function bg(t) {
  x.fillStyle = C.bg; x.fillRect(0, 0, W, H);
  const o = (t * 22) % 64;
  x.save(); x.strokeStyle = C.grid; x.lineWidth = 2; x.beginPath();
  for (let gx = -64 + o; gx < W + 64; gx += 64) { x.moveTo(gx, 0); x.lineTo(gx, H); }
  for (let gy = -64 + o; gy < H + 64; gy += 64) { x.moveTo(0, gy); x.lineTo(W, gy); }
  x.stroke(); x.restore();
  const gx = W / 2 + Math.sin(t * .35) * W * .24, gy = H / 2 + Math.cos(t * .27) * H * .22;
  let g = x.createRadialGradient(gx, gy, 0, gx, gy, 640);
  g.addColorStop(0, 'rgba(198,244,50,0.07)'); g.addColorStop(1, 'rgba(198,244,50,0)');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  g = x.createRadialGradient(W - gx + 80, H - gy, 0, W - gx + 80, H - gy, 560);
  g.addColorStop(0, 'rgba(169,155,255,0.07)'); g.addColorStop(1, 'rgba(169,155,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  g = x.createRadialGradient(W / 2, H / 2, 380, W / 2, H / 2, 1150);
  g.addColorStop(0, 'rgba(7,8,10,0)'); g.addColorStop(1, 'rgba(7,8,10,0.94)');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
}
function logo(cx, cy, t) {
  const pts = [[0, -15], [-14, 10], [14, 10]].map(([a, b]) => [cx + a, cy + b]);
  x.save(); x.strokeStyle = '#5A5F66'; x.lineWidth = 2; x.beginPath();
  x.moveTo(...pts[0]); x.lineTo(...pts[1]); x.lineTo(...pts[2]); x.closePath(); x.stroke(); x.restore();
  pts.forEach(p => circ(p[0], p[1], 5.5, { fill: C.bg, stroke: C.acc, lw: 2.5 }));
  circ(cx, cy + 1, 3.6 * (1 + .25 * Math.sin(t * 4)), { fill: C.ac2 });
}
function hud(t) {
  const a = P(t, .5, 1.1);
  if (a <= 0) return;
  x.save(); x.globalAlpha = a;
  const ty = LAND ? 80 : 160, by = LAND ? H - 76 : 1702, bar = by + 34, R = W - 80;
  logo(98, ty - 10, t);
  T('00MESH', 134, ty, { w: 700, size: 28, ls: 2 });
  T('HYPERSPACE AGI 1.05', R, ty, { size: 22, col: C.mute, al: 'right', ls: 4 });
  T('R&D LOG · ' + REEL.date, 80, by, { size: 20, col: C.mute, ls: 3 });
  let cur = null; for (const s of REEL.sc) if (t >= s.a + .2 && t < s.b - .2) cur = s;
  if (cur) T(cur.n + ' / ' + String(REEL.sc.length).padStart(2, '0'), R, by, { w: 700, size: 20, col: C.acc, al: 'right', ls: 3 });
  seg(80, bar, R, bar, { col: C.line, lw: 4 });
  seg(80, bar, R, bar, { col: C.acc, lw: 4, p: t / DUR });
  for (const s of REEL.sc) circ(lerp(80, R, s.a / DUR), bar, 6, { fill: t >= s.a ? C.acc : C.line });
  x.restore();
}
function cuts(t) {
  for (const c of REEL.cuts) {
    const p = P(t, c - .25, c + .3);
    if (p <= 0 || p >= 1) continue;
    const y = lerp(-140, H + 140, ioCub(p));
    const g = x.createLinearGradient(0, y - 160, 0, y + 18);
    g.addColorStop(0, 'rgba(198,244,50,0)'); g.addColorStop(1, 'rgba(198,244,50,0.16)');
    x.fillStyle = g; x.fillRect(0, y - 160, W, 178);
    x.save(); x.globalAlpha = .9; x.fillStyle = C.acc; x.fillRect(0, y + 18, W, 3); x.restore();
  }
}

/* ---------- shared motifs ---------- */
function mesh(cx, cy, R, t, f, a = 1, labels = true) {
  if (a <= 0 || f <= 0) return;
  const ang = [-90, 150, 30].map(d => d * Math.PI / 180);
  const N = ang.map(g => [cx + Math.cos(g) * R * f, cy + Math.sin(g) * R * f]);
  const fa = clamp(f);
  x.save(); x.globalAlpha *= a;
  [[0, 1], [1, 2], [2, 0]].forEach(([i, j], k) => {
    const col = k === 1 ? C.ac2 : C.acc;
    seg(N[i][0], N[i][1], N[j][0], N[j][1], { col: C.line, lw: 3, a: fa });
    seg(N[i][0], N[i][1], N[j][0], N[j][1], { col, lw: 3, a: fa * .6, dash: [8, 20], off: -t * 80 });
    for (let q = 0; q < 2; q++) {
      const u = (t * .5 + k * .31 + q * .5) % 1;
      circ(lerp(N[i][0], N[j][0], u), lerp(N[i][1], N[j][1], u), 7, { fill: col, a: fa });
    }
  });
  N.forEach((p, k) => {
    seg(cx, cy, p[0], p[1], { col: C.line, lw: 2, a: fa * .8, dash: [4, 10] });
    const u = (t * .7 + k * .4) % 1;
    circ(lerp(cx, p[0], u), lerp(cy, p[1], u), 4.5, { fill: C.ink, a: fa });
  });
  for (let k = 0; k < 2; k++) { const u = (t * .6 + k * .5) % 1; circ(cx, cy, 14 + u * 90, { stroke: C.ac2, lw: 2, a: (1 - u) * .8 * fa }); }
  circ(cx, cy, 14, { fill: C.ac2, a: fa });
  const L = ['M5', 'OMEN', 'V16'], SUB = ['Mac M5 Hub', 'HP OMEN 16', 'ASUS V16'];
  N.forEach((p, k) => {
    const u = (t * .5 + k * .33) % 1;
    circ(p[0], p[1], 36 + u * 54, { stroke: C.acc, lw: 2, a: (1 - u) * .7 * fa });
    circ(p[0], p[1], 36, { fill: C.panel, stroke: C.acc, lw: 3 });
    T(L[k], p[0], p[1] + 8, { w: 900, size: L[k].length > 2 ? 18 : 22, fam: FD, al: 'center', a: fa });
    if (labels) T(SUB[k], p[0], k === 0 ? p[1] - 62 : p[1] + 82, { size: 22, al: 'center', col: C.mute, a: clamp(f * 1.6 - .6) });
  });
  x.restore();
}
function header(t, a, b, num, kicker, lines) {
  const e = env(t, a, b, .35, .35);
  if (e <= 0) return;
  if (HNUM) { num = HNUM; kicker = kicker.replace(/^\d\d/, HNUM); }
  onMain(() => {
    x.save(); x.globalAlpha = e * .9; setF(900, LAND ? 560 : 640, FD); x.letterSpacing = '-20px'; x.textAlign = 'right';
    x.lineWidth = 3; x.strokeStyle = '#1F2227';
    x.strokeText(num, LAND ? 900 - 120 * P(t, a, b) : W + 60 - 150 * P(t, a, b), LAND ? 980 : 1330); x.restore();
    const n = Math.floor(kicker.length * P(t, a + .15, a + .7));
    const cursor = (t < a + .9 && Math.floor(t * 6) % 2 === 0) ? '▍' : '';
    T(kicker.slice(0, n) + cursor, 80, LAND ? 300 : 330, { w: 700, size: 24, col: C.acc, ls: 3, a: e });
    words(t, lines, 80, LAND ? 420 : 444, LAND ? 92 : 96, LAND ? 82 : 86, a + .25, .09, .8, b - .55);
  });
}

/* ---------- scene 0 · intro (0 – 3.2s) ---------- */
const LY = LAND ? { my: 400, mr: 210, wy: 850, ws: 150, sy: 925, oy: 330, or: 170, oly: 700, osy: 770, oty: 850, opy: 945 }
  : { my: 880, mr: 300, wy: 1400, ws: 170, sy: 1480, oy: 800, or: 230, oly: 1250, osy: 1330, oty: 1430, opy: 1530 };
function intro(t) {
  if (t > 3.3) return;
  const e = 1 - iCub(P(t, 2.75, 3.2));
  const s = 1 + .15 * iCub(P(t, 2.6, 3.2)), cx = W / 2;
  x.save(); x.globalAlpha = e; x.translate(cx, LY.my + 20); x.scale(s, s); x.translate(-cx, -LY.my - 20);
  const sp = ioCub(P(t, .9, 1.7));
  if (sp <= 0) {
    for (let k = 0; k < 3; k++) { const u = P(t, .3 + k * .2, 1.3 + k * .2); if (u > 0 && u < 1) circ(cx, LY.my, 16 + u * 230, { stroke: C.acc, lw: 3, a: (1 - u) * .8 }); }
    circ(cx, LY.my, 20 * oBack(P(t, .15, .65)), { fill: C.acc });
  } else mesh(cx, LY.my, LY.mr, t, sp, 1);
  letters(t, '00MESH', cx, LY.wy, LY.ws, 1.5, .06, .8);
  T('HYPERSPACE AGI 1.05', cx, LY.sy, { size: 30, al: 'center', col: C.mute, ls: 10, a: P(t, 2.0, 2.4) });
  x.restore();
}

const ERR = '#FF6B5B';
function arrow(x1, y1, x2, y2, p, col) {
  if (p <= 0) return;
  seg(x1, y1, x2, y2, { col, lw: 3, p });
  if (p >= 1) {
    const g = Math.atan2(y2 - y1, x2 - x1);
    x.save(); x.fillStyle = col; x.translate(x2, y2); x.rotate(g); x.beginPath(); x.moveTo(0, 0); x.lineTo(-16, -8); x.lineTo(-16, 8); x.closePath(); x.fill(); x.restore();
  }
}

/* shared bits */
function badge(t, text, y, t0, col = C.acc) {
  const p = oBack(P(t, t0, t0 + .35)); if (p <= 0) return;
  const wd = measure(text, 700, 26, FM, 3) + 80;
  x.save(); x.translate(540, y); x.scale(p, p);
  rrect(-wd / 2, -32, wd, 64, 32); x.fillStyle = C.tint; x.fill(); x.strokeStyle = col; x.lineWidth = 2.5; x.stroke();
  circ(-wd / 2 + 32, 0, 7, { fill: col });
  T(text, 14, 9, { w: 700, size: 26, al: 'center', col, ls: 3 });
  x.restore();
}
function pill(cx, cy, w, h, label, o = {}) {
  const { fill = '#14171B', stroke = '#3A3E44', col = '#C9CCC4', size = 24, bold = false, s = 1, lw = 2.5 } = o;
  if (s <= 0) return;
  x.save(); x.translate(cx, cy); x.scale(s, s);
  rrect(-w / 2, -h / 2, w, h, h / 2); x.fillStyle = fill; x.fill(); x.strokeStyle = stroke; x.lineWidth = lw; x.stroke();
  T(label, 0, size * .36, { size, al: 'center', col, w: bold ? 700 : 400 });
  x.restore();
}

/* ---------- scene 7 · outro (ultimi 2.6 s) ---------- */
function outro(t) {
  const a = DUR - 2.6, cx = W / 2;
  if (t < a) return;
  const e = oCub(P(t, a, a + .4));
  x.save(); x.globalAlpha = e;
  mesh(cx, LY.oy, LY.or, t, oBack(P(t, a + .1, a + .8)), 1, false);
  letters(t, '00MESH', cx, LY.oly, LY.ws, a + .4, .06, .8);
  T('HYPERSPACE AGI 1.05', cx, LY.osy, { size: 30, al: 'center', col: C.mute, ls: 10, a: P(t, a + .8, a + 1.2) });
  T(REEL.tagline, cx, LY.oty, { w: 600, size: 42, fam: FD, al: 'center', a: oCub(P(t, a + 1.0, a + 1.5)) });
  const ps = oBack(P(t, a + 1.3, a + 1.7));
  if (ps > 0) {
    const lb = REEL.cta || 'os.zerozerocomputer.it', wd = measure(lb, 700, 30, FM) + 64;
    x.save(); x.translate(cx, LY.opy); x.scale(ps, ps); rrect(-wd / 2, -38, wd, 76, 38); x.fillStyle = C.acc; x.fill();
    T(lb, 0, 11, { w: 700, size: 30, al: 'center', col: C.dark }); x.restore();
  }
  x.restore();
}

/* ---------- compositor ---------- */
/* REEL.layers può sostituire i livelli fissi ({ bg, intro, outro, hud, cuts }, una funzione di t;
   `() => {}` lo spegne) e il colore della dissolvenza in apertura e chiusura (fade). */
function frame(t) {
  const L = REEL.layers || {};
  x = X0; x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = 1; x.shadowBlur = 0;
  (L.bg || bg)(t); (L.intro || intro)(t);
  if (LAND) {
    PX.setTransform(1, 0, 0, 1, 0, 0); PX.globalAlpha = 1; PX.clearRect(0, 0, PW, PH);
    x = PX; for (const scene of REEL.scenes) scene(t); x = X0;
    // fascia verticale (y) che va nella colonna destra: REEL.crop, fissa o in funzione di t
    const crop = typeof REEL.crop === 'function' ? REEL.crop(t) : REEL.crop || [600, 1540], ch = crop[1] - crop[0];
    const dh = H - 240, dw = PW * dh / ch;
    x.drawImage(pcv, 0, crop[0], PW, ch, W - 60 - dw, 120, dw, dh);
  } else for (const scene of REEL.scenes) scene(t);
  (L.outro || outro)(t); (L.hud || hud)(t); (L.cuts || cuts)(t);
  const k = Math.max(1 - P(t, 0, .35), P(t, DUR - .4, DUR));
  if (k > 0) { x.globalAlpha = k; x.fillStyle = L.fade || C.bg; x.fillRect(0, 0, W, H); x.globalAlpha = 1; }
}

