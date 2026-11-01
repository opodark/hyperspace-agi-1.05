// SPDX-License-Identifier: Apache-2.0
/* Stile «netdive» — libreria riusabile, estratta da reels/contrattacco-2026-10-31.js.
   build.py la concatena dopo runtime.js quando un reel dichiara `// @meta {"styles": ["netdive", …]}`.
   Pioggia di codice, tunnel 3D, titoli inclinati con sdoppiamento cromatico, linee di velocità, bande cinema,
   intestazione op(), nodi, chip e glitch/flash sui tagli.

   Scritto in coordinate parametriche su W/H (i reel verticali 1080×1920 rendono identici a prima; un reel
   16:9 nativo usa gli stessi disegni su 1920×1080). Il ritmo è specifico del reel: le funzioni che ne hanno
   bisogno lo leggono dall'oggetto NETDIVE, riempito dal reel (power, thump, bIdx, slams, hud). */

const NETDIVE = {
  C: { bg: '#020605', grn: '#00FF9C', cyn: '#00E5FF', red: '#FF1E56', wht: '#EAFBF3', amb: '#FFB000', dim: '#1F4D3E', mid: '#5F8F80' },
  power: () => 0,                    // 0..1, energia della sezione corrente (dal reel)
  thump: () => 0,                    // 0..1, impulso del colpo (dal reel)
  bIdx: () => -1,                    // indice del beat corrente (dal reel)
  slams: [],                         // istanti dei titoli d'impatto, per il flash sui tagli
  hud: { tag: 'NETDIVE // 00MESH', footer: '00MESH' },
};
const NC = NETDIVE.C;
const rnd = n => { const s = Math.sin(n * 91.7 + 47.3) * 43758.5453; return s - Math.floor(s); };

/* ---------- grafica: testo d'impatto inclinato, cornici HUD, linee di velocità ---------- */
function skewText(s, X, Y, size, col, o = {}) {
  const { al = 'left', a = 1, split = 0, w = 900, fam = FD } = o;
  if (a <= 0) return;
  x.save(); x.globalAlpha *= a; x.translate(X, Y); x.transform(1, 0, -.18, 1, 0, 0);
  if (split > .5) {
    x.save(); x.globalCompositeOperation = 'lighter';
    T(s, -split, 0, { w, size, fam, col: NC.cyn, al, ls: -3, a: .85 }); T(s, split, split * .4, { w, size, fam, col: NC.red, al, ls: -3, a: .85 });
    x.restore();
  }
  T(s, 0, 0, { w, size, fam, col, al, ls: -3 });
  x.restore();
}
const fitSize = (s, maxW, size) => Math.min(size, size * maxW / measure(s, 900, size, FD, -3));
/* titolo che sbatte: entra grande e sdoppiato, si posa, trema sui beat */
function slam(s, X, Y, size, t, t0, col, o = {}) {
  const p = P(t, t0, t0 + .18); if (p <= 0) return;
  const sc = lerp(1.5, 1, oCub(p)), sz = fitSize(s, o.maxW || 860, size);
  x.save(); x.translate(X, Y); x.scale(sc, sc);
  skewText(s, 0, 0, sz, col, { al: o.al || 'center', split: 26 * (1 - p) + NETDIVE.thump(t) * 12, a: o.a ?? 1 });
  x.restore();
}
function speedLines(cx, cy, t, t0, col = NC.wht) {
  const p = P(t, t0, t0 + .7); if (p <= 0 || p >= 1) return;
  x.save(); x.globalAlpha = (1 - p) * .7; x.strokeStyle = col;
  for (let i = 0; i < 64; i++) {
    const g = i / 64 * Math.PI * 2 + rnd(i + t0) * .08, r0 = 260 + rnd(i * 3 + t0) * 200 + p * 200, r1 = r0 + 300 + rnd(i * 7) * 600;
    x.lineWidth = 2 + rnd(i * 5) * 6; x.beginPath(); x.moveTo(cx + Math.cos(g) * r0, cy + Math.sin(g) * r0); x.lineTo(cx + Math.cos(g) * r1, cy + Math.sin(g) * r1); x.stroke();
  }
  x.restore();
}
function brackets(X, Y, w, h, col, k = 26, lw = 4) {
  x.save(); x.strokeStyle = col; x.lineWidth = lw; x.beginPath();
  [[X, Y, 1, 1], [X + w, Y, -1, 1], [X, Y + h, 1, -1], [X + w, Y + h, -1, -1]].forEach(([a, b, sx, sy]) => { x.moveTo(a + sx * k, b); x.lineTo(a, b); x.lineTo(a, b + sy * k); });
  x.stroke(); x.restore();
}
function chip(s, X, Y, col, t, blink = false) {
  const a = blink ? (Math.floor(t * 4) % 2 ? 1 : .5) : 1, wd = measure(s, 700, 22, FM, 3) + 32;
  x.save(); x.globalAlpha *= a; x.fillStyle = col; x.fillRect(X, Y - 28, wd, 38); x.restore();
  T(s, X + 16, Y, { w: 700, size: 22, col: NC.bg, ls: 3, a });
}
/* intestazione di sezione: codice operazione, titolo inclinato, riga di spiegazione */
function op(t, a, b, code, title, line, col = NC.grn, status = null) {
  const e = env(t, a, b, .1, .2); if (e <= 0) return;
  x.save(); x.globalAlpha *= e;
  const n = Math.floor(code.length * P(t, a, a + .3));
  T(code.slice(0, n), 80, 262, { w: 700, size: 24, col, ls: 4 });
  slam(title, 80, 380, 120, t, a + .05, NC.wht, { al: 'left', maxW: W - 180 });
  x.fillStyle = col; x.fillRect(80, 410, (W - 160) * oExpo(P(t, a + .1, a + .5)), 6);
  T(line, 80, 470, { w: 600, size: 34, fam: FD, col, a: P(t, a + .3, a + .6) });
  if (status) chip(status, W - 340, 262, NC.amb, t, true);
  x.restore();
}
function nodeBox(cx, cy, s, col, on = true, sub = '') {
  x.save(); x.strokeStyle = col; x.lineWidth = 4; x.globalAlpha *= on ? 1 : .35;
  x.fillStyle = 'rgba(2,6,5,0.85)'; x.fillRect(cx - 95, cy - 40, 190, 80); x.strokeRect(cx - 95, cy - 40, 190, 80);
  T(s, cx, cy + 10, { w: 700, size: 26, col, al: 'center' });
  x.restore();
  if (sub) T(sub, cx, cy + 74, { size: 20, col: NC.mid, al: 'center' });
}

/* ---------- livelli fissi: pioggia di codice, tunnel, bande cinema, HUD, glitch ---------- */
const COLS = Array.from({ length: Math.ceil(W / 36) }, (_, i) => ({ x: 18 + i * 36, sp: 160 + rnd(i) * 420, off: rnd(i + 40) * H, len: 10 + Math.floor(rnd(i + 80) * 18) }));
const GLY = '0123456789ABCDEF<>/#';
function netBg(t) {
  x.fillStyle = NC.bg; x.fillRect(0, 0, W, H);
  const pw = NETDIVE.power(t);
  // tunnel: quadrati in prospettiva che vengono incontro, più veloci sui drop
  const cx = W / 2 + Math.sin(t * .7) * 40, cy = H / 2 + 20 + Math.cos(t * .5) * 30, spd = .35 + pw * 1.4, ph = (t * spd) % 1;
  x.save();
  for (let i = 0; i < 14; i++) {
    const z = (i + 1 - ph) / 14, s = 1 / (z * z * 3 + .05) * 90;
    if (s > 2400) continue;
    x.globalAlpha = clamp((1 - z) * .55 + NETDIVE.thump(t) * .25) * (1 - P(s, 1400, 2400));
    x.strokeStyle = i % 4 === 0 ? NC.cyn : NC.dim; x.lineWidth = i % 4 === 0 ? 3 : 2;
    x.strokeRect(cx - s * .6, cy - s, s * 1.2, s * 2);
  }
  x.globalAlpha = .35; x.strokeStyle = NC.dim; x.lineWidth = 2; x.beginPath();
  [[0, 0], [W, 0], [0, H], [W, H], [W / 2, 0], [W / 2, H], [0, H / 2], [W, H / 2]].forEach(([a, b]) => { x.moveTo(cx, cy); x.lineTo(a, b); });
  x.stroke(); x.restore();
  // pioggia di codice
  x.save(); setF(700, 26, FM); x.textAlign = 'center';
  COLS.forEach((c, i) => {
    const head = (c.off + t * c.sp * (.6 + pw * .8)) % (H + c.len * 32);
    for (let k = 0; k < c.len; k++) {
      const y = head - k * 32; if (y < 0 || y > H) continue;
      const ch = GLY[Math.floor(rnd(i * 31 + k + Math.floor(t * 6)) * GLY.length)];
      x.fillStyle = k === 0 ? NC.wht : NC.grn; x.globalAlpha = (k === 0 ? .6 : (1 - k / c.len) * .3) * (.5 + pw * .5);
      x.fillText(ch, c.x, y);
    }
  });
  x.restore();
  // scossa sul colpo, resta attiva per le scene (frame() riparte pulito a ogni fotogramma)
  const s = NETDIVE.thump(t) * 12, bi = NETDIVE.bIdx(t);
  x.translate((rnd(bi) - .5) * s, (rnd(bi + 9) - .5) * s);
}
function cineHud(t) {
  x.setTransform(1, 0, 0, 1, 0, 0);
  x.fillStyle = '#000'; x.fillRect(0, 0, W, 150); x.fillRect(0, H - 140, W, 140);
  const a = P(t, .2, .8);
  T(NETDIVE.hud.tag, 80, 96, { w: 700, size: 24, col: NC.grn, ls: 4, a });
  const link = Math.round(100 * clamp(NETDIVE.power(t) * 1.1));
  T('LINK ' + String(link).padStart(3, ' ') + '%', W - 80, 96, { w: 700, size: 24, col: link > 80 ? NC.red : NC.cyn, al: 'right', ls: 4, a });
  const tc = 'T+' + String(Math.floor(t / 60)).padStart(2, '0') + ':' + (t % 60).toFixed(1).padStart(4, '0');
  T(NETDIVE.hud.footer, 80, H - 76, { size: 20, col: NC.mid, ls: 3, a });
  T(tc, W - 80, H - 76, { w: 700, size: 20, col: NC.grn, al: 'right', ls: 2, a });
  x.fillStyle = NC.dim; x.fillRect(80, H - 52, W - 160, 4); x.fillStyle = NC.red; x.fillRect(80, H - 52, (W - 160) * t / DUR, 4);
  x.save(); x.fillStyle = 'rgba(0,0,0,0.18)'; for (let y = 150; y < H - 140; y += 3) x.fillRect(0, y, W, 1); x.restore();
  const v = x.createRadialGradient(W / 2, H / 2, 500, W / 2, H / 2, 1150);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.7)'); x.fillStyle = v; x.fillRect(0, 150, W, H - 290);
}
function netCuts(t) {
  for (const c of REEL.cuts) {
    const p = P(t, c - .1, c + .16); if (p <= 0 || p >= 1) continue;
    const amt = Math.sin(p * Math.PI);
    for (let i = 0; i < 10; i++) {
      const y = 150 + Math.floor(rnd(i + c * 10) * (H - 290)), h = 16 + rnd(i * 7 + c) * 110, off = (rnd(i * 13 + c) - .5) * 300 * amt;
      x.drawImage(x.canvas, 0, y, W, h, off, y, W, h);
    }
  }
  for (const s of NETDIVE.slams) { const f = 1 - P(t, s, s + .22); if (t >= s && f > 0) { x.fillStyle = `rgba(234,251,243,${f * .8})`; x.fillRect(0, 0, W, H); } }
}
