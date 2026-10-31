// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "contrattacco-2026-10-31", "title": "00MESH Reel Contrattacco", "dur": 76, "aria": "Animazione di 76 secondi in stile anime cyberpunk, con immersione nella rete, pioggia di codice e titoli d'impatto su musica techno con rullo di marcia. Ogni notte ci provano: allarmi di accessi, phishing e scansioni. Basta subire: contrattacco. 00MESH entra in rete per primo e attacca i sistemi del cliente prima degli altri, con autorizzazione: red team con Strix (in sviluppo), ricognizione con il Security Lab, detonazione degli exploit in una sandbox senza rete, journal che annulla gli errori, chiavi divise in tre, cancello MCP con scudo esagonale, mesh privata con il telefono come hub di riserva (in sviluppo). Chiusura: documentato, reversibile, locale, nostro. Con noi non si scherza. os.zerozerocomputer.it, solo su sistemi propri o autorizzati."}
/* Reel «contrattacco» sul brano «die Stimmen gewinnen langsam» (172 BPM), tempi dai beat reali (librosa) in BT.
   Intro 0–11.10 (rullo da 8.29) · drop 11.10–19.55 · stacco –22.38 · drop –30.88 · pausa –36.46 · drop –45.00 · stacco –47.81
   · drop –67.57 (calo 53.45–56.29) · rullo finale –73.21 · ultimo attacco e chiusura –76.
   Il contrattacco è red team sui sistemi del cliente, con autorizzazione: nessun attacco verso terzi. Le scene illustrano, non misurano. */

const Z = { bg: '#020605', grn: '#00FF9C', cyn: '#00E5FF', red: '#FF1E56', wht: '#EAFBF3', amb: '#FFB000', dim: '#1F4D3E', mid: '#5F8F80' };
const BT = [0.163,0.511,0.859,1.207,1.556,1.904,2.252,2.624,2.972,3.32,3.669,4.017,4.389,4.737,5.085,5.457,5.805,6.153,6.502,6.85,7.221,7.57,7.918,8.29,8.661,8.986,9.334,9.683,10.054,10.403,10.751,11.099,11.447,11.796,12.144,12.492,12.841,13.212,13.56,13.909,14.257,14.605,14.954,15.325,15.673,16.045,16.393,16.718,17.09,17.438,17.786,18.135,18.483,18.855,19.203,19.551,19.9,20.271,20.619,20.991,21.339,21.687,22.036,22.384,22.732,23.104,23.452,23.824,24.172,24.52,24.869,25.217,25.565,25.937,26.285,26.633,26.982,27.33,27.701,28.05,28.398,28.746,29.095,29.466,29.814,30.163,30.534,30.883,31.231,31.556,31.904,32.276,32.624,32.972,33.321,33.692,34.04,34.389,34.714,35.039,35.387,35.736,36.084,36.455,36.827,37.222,37.593,37.941,38.29,38.638,38.986,39.335,39.683,40.054,40.403,40.751,41.099,41.448,41.819,42.167,42.516,42.864,43.236,43.584,43.932,44.28,44.652,45.0,45.325,45.674,46.045,46.393,46.765,47.113,47.462,47.81,48.135,48.506,48.878,49.226,49.575,49.923,50.294,50.643,50.991,51.339,51.688,52.059,52.407,52.756,53.104,53.452,53.801,54.172,54.52,54.869,55.24,55.589,55.937,56.285,56.61,56.959,57.33,57.702,58.05,58.398,58.77,59.118,59.443,59.815,60.163,60.511,60.86,61.208,61.579,61.928,62.276,62.624,62.996,63.344,63.692,64.041,64.412,64.76,65.109,65.457,65.829,66.177,66.502,66.85,67.199,67.57,67.918,68.29,68.615,69.01,69.381,69.73,70.078,70.426,70.751,71.1,71.448,71.796,72.144,72.516,72.864,73.213,73.561,73.932,74.281,74.629,74.977,75.326,75.697,76.045];
const HOT = [[11.099, 19.551], [22.384, 30.883], [36.455, 45.0], [47.81, 53.452], [56.285, 67.57], [73.213, 76]];
const SLAMS = [11.099, 22.384, 36.455, 47.81, 56.285, 73.213];

/* ---------- ritmo ---------- */
function bIdx(t) { let i = -1; while (i + 1 < BT.length && BT[i + 1] <= t) i++; return i; }
const sinceB = t => { const i = bIdx(t); return i < 0 ? 9 : t - BT[i]; };
const beatsIn = (a, b) => BT.filter(v => v >= a - 1e-3 && v < b - 1e-3);
const hot = t => HOT.some(([a, b]) => t >= a && t < b);
const power = t => hot(t) ? 1 : t < 11.099 ? .1 + .55 * P(t, 5.5, 11.0) : t >= 67.57 ? .3 + .6 * P(t, 67.57, 73.2) : .3;
const thump = t => Math.exp(-sinceB(t) * 8) * power(t);
const rnd = n => { const s = Math.sin(n * 91.7 + 47.3) * 43758.5453; return s - Math.floor(s); };

/* ---------- grafica: testo d'impatto inclinato, cornici HUD, linee di velocità ---------- */
function skewText(s, X, Y, size, col, o = {}) {
  const { al = 'left', a = 1, split = 0, w = 900, fam = FD } = o;
  if (a <= 0) return;
  x.save(); x.globalAlpha *= a; x.translate(X, Y); x.transform(1, 0, -.18, 1, 0, 0);
  if (split > .5) {
    x.save(); x.globalCompositeOperation = 'lighter';
    T(s, -split, 0, { w, size, fam, col: Z.cyn, al, ls: -3, a: .85 }); T(s, split, split * .4, { w, size, fam, col: Z.red, al, ls: -3, a: .85 });
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
  skewText(s, 0, 0, sz, col, { al: o.al || 'center', split: 26 * (1 - p) + thump(t) * 12, a: o.a ?? 1 });
  x.restore();
}
function speedLines(cx, cy, t, t0, col = Z.wht) {
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
  T(s, X + 16, Y, { w: 700, size: 22, col: Z.bg, ls: 3, a });
}
/* intestazione di sezione: codice operazione, titolo inclinato, riga di spiegazione */
function op(t, a, b, code, title, line, col = Z.grn, status = null) {
  const e = env(t, a, b, .1, .2); if (e <= 0) return;
  x.save(); x.globalAlpha *= e;
  const n = Math.floor(code.length * P(t, a, a + .3));
  T(code.slice(0, n), 80, 262, { w: 700, size: 24, col, ls: 4 });
  slam(title, 80, 380, 120, t, a + .05, Z.wht, { al: 'left', maxW: 900 });
  x.fillStyle = col; x.fillRect(80, 410, 920 * oExpo(P(t, a + .1, a + .5)), 6);
  T(line, 80, 470, { w: 600, size: 34, fam: FD, col, a: P(t, a + .3, a + .6) });
  if (status) chip(status, 740, 262, Z.amb, t, true);
  x.restore();
}
function nodeBox(cx, cy, s, col, on = true, sub = '') {
  x.save(); x.strokeStyle = col; x.lineWidth = 4; x.globalAlpha *= on ? 1 : .35;
  x.fillStyle = 'rgba(2,6,5,0.85)'; x.fillRect(cx - 95, cy - 40, 190, 80); x.strokeRect(cx - 95, cy - 40, 190, 80);
  T(s, cx, cy + 10, { w: 700, size: 26, col, al: 'center' });
  x.restore();
  if (sub) T(sub, cx, cy + 74, { size: 20, col: Z.mid, al: 'center' });
}

/* ---------- livelli fissi: pioggia di codice, tunnel, bande cinema, HUD, glitch ---------- */
const COLS = Array.from({ length: 30 }, (_, i) => ({ x: 18 + i * 36, sp: 160 + rnd(i) * 420, off: rnd(i + 40) * 1920, len: 10 + Math.floor(rnd(i + 80) * 18) }));
const GLY = '0123456789ABCDEF<>/#';
function netBg(t) {
  x.fillStyle = Z.bg; x.fillRect(0, 0, W, H);
  const pw = power(t);
  // tunnel: quadrati in prospettiva che vengono incontro, più veloci sui drop
  const cx = 540 + Math.sin(t * .7) * 40, cy = 980 + Math.cos(t * .5) * 30, spd = .35 + pw * 1.4, ph = (t * spd) % 1;
  x.save();
  for (let i = 0; i < 14; i++) {
    const z = (i + 1 - ph) / 14, s = 1 / (z * z * 3 + .05) * 90;
    if (s > 2400) continue;
    x.globalAlpha = clamp((1 - z) * .55 + thump(t) * .25) * (1 - P(s, 1400, 2400));
    x.strokeStyle = i % 4 === 0 ? Z.cyn : Z.dim; x.lineWidth = i % 4 === 0 ? 3 : 2;
    x.strokeRect(cx - s * .6, cy - s, s * 1.2, s * 2);
  }
  x.globalAlpha = .35; x.strokeStyle = Z.dim; x.lineWidth = 2; x.beginPath();
  [[0, 0], [W, 0], [0, H], [W, H], [W / 2, 0], [W / 2, H], [0, H / 2], [W, H / 2]].forEach(([a, b]) => { x.moveTo(cx, cy); x.lineTo(a, b); });
  x.stroke(); x.restore();
  // pioggia di codice
  x.save(); setF(700, 26, FM); x.textAlign = 'center';
  COLS.forEach((c, i) => {
    const head = (c.off + t * c.sp * (.6 + pw * .8)) % (1920 + c.len * 32);
    for (let k = 0; k < c.len; k++) {
      const y = head - k * 32; if (y < 0 || y > 1920) continue;
      const ch = GLY[Math.floor(rnd(i * 31 + k + Math.floor(t * 6)) * GLY.length)];
      x.fillStyle = k === 0 ? Z.wht : Z.grn; x.globalAlpha = (k === 0 ? .6 : (1 - k / c.len) * .3) * (.5 + pw * .5);
      x.fillText(ch, c.x, y);
    }
  });
  x.restore();
  // scossa sul colpo, resta attiva per le scene (frame() riparte pulito a ogni fotogramma)
  const s = thump(t) * 12, bi = bIdx(t);
  x.translate((rnd(bi) - .5) * s, (rnd(bi + 9) - .5) * s);
}
function cineHud(t) {
  x.setTransform(1, 0, 0, 1, 0, 0);
  x.fillStyle = '#000'; x.fillRect(0, 0, W, 150); x.fillRect(0, H - 140, W, 140);
  const a = P(t, .2, .8);
  T('NETDIVE // 00MESH', 80, 96, { w: 700, size: 24, col: Z.grn, ls: 4, a });
  const link = Math.round(100 * clamp(power(t) * 1.1));
  T('LINK ' + String(link).padStart(3, ' ') + '%', 1000, 96, { w: 700, size: 24, col: link > 80 ? Z.red : Z.cyn, al: 'right', ls: 4, a });
  const tc = 'T+' + String(Math.floor(t / 60)).padStart(2, '0') + ':' + (t % 60).toFixed(1).padStart(4, '0');
  T('OPERAZIONE CONTRATTACCO · 31.10.2026', 80, H - 76, { size: 20, col: Z.mid, ls: 3, a });
  T(tc, 1000, H - 76, { w: 700, size: 20, col: Z.grn, al: 'right', ls: 2, a });
  x.fillStyle = Z.dim; x.fillRect(80, H - 52, 920, 4); x.fillStyle = Z.red; x.fillRect(80, H - 52, 920 * t / DUR, 4);
  x.save(); x.fillStyle = 'rgba(0,0,0,0.18)'; for (let y = 150; y < H - 140; y += 3) x.fillRect(0, y, W, 1); x.restore();
  const v = x.createRadialGradient(540, 960, 500, 540, 960, 1150);
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
  for (const s of SLAMS) { const f = 1 - P(t, s, s + .22); if (t >= s && f > 0) { x.fillStyle = `rgba(234,251,243,${f * .8})`; x.fillRect(0, 0, W, H); } }
}

/* ---------- intro · ogni notte ci provano (0 – 11.10s) ---------- */
const ALERTS = ['accesso SSH fallito', 'phishing in arrivo', 'scansione delle porte', 'bot sul form di login', 'password provate a raffica', 'allegato sospetto', 'ransomware?', 'credenziali in vendita', 'traffico strano alle 03:00', 'DNS falsificato?', 'admin/admin?', 'ancora login falliti'];
function nightly(t) {
  if (t > 11.3) return;
  const out = 1 - P(t, 11.0, 11.15);
  x.save(); x.globalAlpha *= out;
  skewText('OGNI NOTTE', 80, 300, 96, Z.wht, { a: P(t, .2, .5) * (1 - P(t, 8.0, 8.29)), split: 6 * (1 - P(t, .2, .6)) });
  skewText('CI PROVANO.', 80, 400, 96, Z.red, { a: P(t, 1.2, 1.5) * (1 - P(t, 8.0, 8.29)), split: 6 * (1 - P(t, 1.2, 1.6)) });
  // finestre d'allarme che si accumulano, una ogni due battute, poi si spezzano al drop
  ALERTS.forEach((s, i) => {
    const t0 = BT[1 + i * 2]; if (t < t0) return;
    const p = oBack(P(t, t0, t0 + .2)), wx = 90 + rnd(i * 5) * 420, wy = 560 + rnd(i * 9) * 820 + (i % 2) * 40;
    const shatter = P(t, 11.0, 11.15);
    x.save(); x.translate(wx + 230, wy + 60); x.scale(p, p); x.rotate((rnd(i) - .5) * .06 + shatter * (rnd(i + 2) - .5));
    x.fillStyle = 'rgba(20,4,10,0.92)'; x.fillRect(-230, -60, 460, 120); x.strokeStyle = Z.red; x.lineWidth = 3; x.strokeRect(-230, -60, 460, 120);
    x.fillStyle = Z.red; x.fillRect(-230, -60, 460, 34);
    T('ALLARME · 03:' + String(10 + i * 3).padStart(2, '0'), -214, -36, { w: 700, size: 18, col: Z.bg, ls: 2 });
    T(s, -214, 30, { size: 26, col: Z.wht });
    x.restore();
  });
  // il rullo: una parola per battuta
  const roll = [[0, 'BASTA'], [2, 'SUBIRE.'], [4, 'È ORA'], [5, 'DI'], [6, 'PASSARE'], [7, 'AL...']];
  roll.forEach(([k, s]) => {
    const t0 = BT[23 + k], nextK = roll.find(r => r[0] > k), t1 = nextK ? BT[23 + nextK[0]] : 11.099;
    if (t < t0 || t >= t1) return;
    x.fillStyle = 'rgba(2,6,5,0.7)'; x.fillRect(0, 760, W, 360);
    slam(s, 540, 1000, 190, t, t0, k >= 6 ? Z.red : Z.wht);
  });
  x.restore();
}

/* ---------- 01 · contrattacco e immersione (11.10 – 19.55s) ---------- */
function dive(t) {
  const a = 11.099, b = 19.551;
  if (t < a || t > b) return;
  const e = env(t, a, b, .05, .2);
  x.save(); x.globalAlpha *= e;
  speedLines(540, 960, t, a);
  if (t < 13.909) {
    slam('CONTRATTACCO', 540, 1010, 190, t, a, Z.red);
    T('// OPERAZIONE AUTORIZZATA', 540, 1110, { w: 700, size: 30, col: Z.grn, al: 'center', ls: 4, a: P(t, 11.8, 12.1) });
  } else if (t < 16.718) {
    slam('DIVE', 540, 900, 260, t, 13.909, Z.cyn);
    T('00MESH entra in rete per primo', 540, 1040, { w: 600, size: 40, fam: FD, col: Z.wht, al: 'center', a: P(t, 14.2, 14.5) });
    const layer = beatsIn(13.909, t + 1e-3).length;
    T('LAYER ' + String(Math.min(layer, 8)).padStart(2, '0') + ' / 08', 540, 1140, { w: 700, size: 30, col: Z.grn, al: 'center', ls: 4 });
  } else {
    T('una squadra di agenti AI', 540, 860, { w: 900, size: 64, fam: FD, col: Z.wht, al: 'center', a: P(t, 16.718, 16.9) });
    T('su macchine nostre.', 540, 950, { w: 900, size: 64, fam: FD, col: Z.grn, al: 'center', a: P(t, 17.438, 17.6) });
    ['M5', 'OMEN', 'ASUS', 'S24'].forEach((n, i) => {
      const t0 = BT[48 + i * 2], p = oBack(P(t, t0, t0 + .2));
      if (p <= 0) return;
      x.save(); x.translate(195 + i * 230, 1160); x.scale(p, p); nodeBox(0, 0, n, Z.cyn); x.restore();
    });
  }
  x.restore();
}

/* ---------- stacco · ti attacchiamo noi (19.55 – 22.38s) ---------- */
function weFirst(t) {
  const a = 19.551, b = 22.384;
  if (t < a || t > b) return;
  const e = env(t, a, b, .05, .15);
  x.save(); x.globalAlpha *= e;
  slam('TI ATTACCHIAMO', 540, 880, 150, t, a, Z.wht);
  slam('NOI.', 540, 1060, 220, t, 20.271, Z.red);
  slam('PRIMA DI LORO.', 540, 1220, 110, t, 20.991, Z.grn);
  x.restore();
}

/* ---------- 02 · Strix, red team sui tuoi sistemi (22.38 – 30.88s) ---------- */
const PATH = [['SITO', 200, 760], ['LOGIN', 640, 860], ['API', 300, 1040], ['DATABASE', 720, 1160], ['BACKUP', 340, 1340]];
const FOUND = ['header mancanti', 'password debole', 'endpoint senza auth', 'porta esposta', 'backup in chiaro'];
function strixOp(t) {
  const a = 22.384, b = 30.883;
  if (t < a || t > b) return;
  op(t, a, b, 'OP.01 // RED TEAM', 'STRIX', 'pentest con agenti AI sui TUOI sistemi', Z.red, 'IN SVILUPPO');
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  const hits = beatsIn(23.104, 28.05).filter((_, i) => i % 2 === 0).slice(0, 5);
  PATH.forEach(([n, px, py], i) => {
    if (i > 0) {
      const [, qx, qy] = PATH[i - 1], p = P(t, hits[i] - .3, hits[i]);
      x.strokeStyle = Z.dim; x.lineWidth = 3; x.beginPath(); x.moveTo(qx, qy); x.lineTo(px, py); x.stroke();
      if (p > 0) { x.strokeStyle = Z.red; x.lineWidth = 5; x.beginPath(); x.moveTo(qx, qy); x.lineTo(lerp(qx, px, p), lerp(qy, py, p)); x.stroke(); }
    }
    const got = t >= hits[i];
    nodeBox(px, py, n, got ? Z.red : Z.mid);
    if (got) {
      ring(px, py, 60 + P(t, hits[i], hits[i] + .4) * 120, { col: Z.red, lw: 4, a: 1 - P(t, hits[i], hits[i] + .4) });
      T('TROVATA: ' + FOUND[i], px + (px < 540 ? 115 : -115), py + 8, { w: 700, size: 22, col: Z.amb, al: px < 540 ? 'left' : 'right', a: P(t, hits[i], hits[i] + .1) });
    }
  });
  ['REPORT', 'FIX', 'RITEST'].forEach((s, i) => {
    const t0 = BT[79 + i * 2]; if (t < t0) return;
    chip(s, 90 + i * 290, 1500, i === 2 ? Z.grn : Z.cyn, t);
    if (i < 2) T('→', 290 + i * 290, 1500, { w: 700, size: 30, col: Z.wht });
  });
  x.restore();
}

/* ---------- pausa · ricognizione nel Security Lab (30.88 – 36.46s) ---------- */
const HOSTS = [[.3, 210, '192.168.1.10 · 22 ssh'], [1.2, 140, '192.168.1.20 · 443 https'], [2.4, 260, '192.168.1.31 · 3389 rdp'], [3.7, 190, '192.168.1.40 · 8080 http'], [5.0, 120, '192.168.1.50 · 445 smb']];
function recon(t) {
  const a = 30.883, b = 36.455;
  if (t < a || t > b) return;
  op(t, a, b, 'OP.02 // RICOGNIZIONE', 'SECURITY LAB', 'nmap · nikto · gobuster, solo sulla rete autorizzata', Z.cyn);
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  const cx = 540, cy = 1000, R = 300, sw = (t - a) * 1.6;
  [1, .66, .33].forEach(k => ring(cx, cy, R * k, { col: Z.dim, lw: 2 }));
  x.strokeStyle = Z.dim; x.beginPath(); x.moveTo(cx - R, cy); x.lineTo(cx + R, cy); x.moveTo(cx, cy - R); x.lineTo(cx, cy + R); x.stroke();
  x.save(); x.beginPath(); x.moveTo(cx, cy); x.arc(cx, cy, R, sw - .5, sw); x.closePath(); x.fillStyle = 'rgba(0,229,255,0.18)'; x.fill(); x.restore();
  seg(cx, cy, cx + Math.cos(sw) * R, cy + Math.sin(sw) * R, { col: Z.cyn, lw: 3 });
  HOSTS.forEach(([g, r, lb], i) => {
    const found = ((sw - g) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2) < 3 || sw > g + 3;
    if (sw < g) return;
    circ(cx + Math.cos(g) * r, cy + Math.sin(g) * r, 10, { fill: Z.grn, a: found ? 1 : .4 });
    T(lb, 120, 1360 + i * 44, { size: 26, col: Z.grn, a: P(sw, g, g + .2) });
  });
  T('target fuori lista → rifiutato prima di partire', 540, 1600, { w: 700, size: 26, col: Z.amb, al: 'center', a: P(t, 34.4, 34.7) });
  x.restore();
}

/* ---------- 03 · detonazione in sandbox (36.46 – 45.00s) ---------- */
const CAGEL = ['rete: OFF', 'root: sola lettura', 'utente: non-root', 'docker socket: NO', 'CPU · RAM · PID: limitati', 'esce solo un diff'];
function detonate(t) {
  const a = 36.455, b = 45.0;
  if (t < a || t > b) return;
  op(t, a, b, 'OP.03 // DETONAZIONE', 'SANDBOX', 'ogni exploit si prova in gabbia', Z.amb);
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  const cx = 330, cy = 1040, s = 210;
  // cubo in prospettiva
  const d = 70;
  x.strokeStyle = Z.amb; x.lineWidth = 4;
  x.strokeRect(cx - s, cy - s, 2 * s, 2 * s); x.strokeRect(cx - s + d, cy - s - d, 2 * s, 2 * s);
  x.beginPath(); [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([u, v]) => { x.moveTo(cx + u * s, cy + v * s); x.lineTo(cx + u * s + d, cy + v * s - d); }); x.stroke();
  const boomT = 39.335, inP = oCub(P(t, 37.6, 39.2));
  if (t < boomT) {
    x.save(); x.translate(lerp(cx - 420, cx, inP), cy); x.rotate(t * 3);
    x.fillStyle = Z.red; x.fillRect(-34, -34, 68, 68); x.restore();
    T('payload', lerp(cx - 420, cx, inP), cy + 80, { size: 22, col: Z.red, al: 'center' });
  } else {
    const p = P(t, boomT, boomT + .8);
    for (let i = 0; i < 40; i++) {
      const g = rnd(i) * Math.PI * 2, r = Math.min(s - 12, 20 + p * 400 * rnd(i + 5));
      x.fillStyle = i % 2 ? Z.red : Z.amb; x.globalAlpha = 1 - P(t, boomT + 1.2, boomT + 2.4) * .7;
      x.fillRect(cx + Math.cos(g) * r - 6, cy + Math.sin(g) * r - 6, 12, 12);
    }
    x.globalAlpha = 1;
    if (t < boomT + .3) { x.fillStyle = 'rgba(255,176,0,0.35)'; x.fillRect(cx - s, cy - s, 2 * s, 2 * s); }
    T('CONTENUTO.', cx, cy + s + 70, { w: 900, size: 44, fam: FD, col: Z.grn, al: 'center', a: P(t, 40.0, 40.3) });
  }
  CAGEL.forEach((s2, i) => {
    const t0 = BT[106 + i * 3]; if (!t0 || t < t0) return;
    T('▸ ' + s2, 600, 900 + i * 62, { w: i === 5 ? 700 : 400, size: 26, col: i === 5 ? Z.cyn : Z.wht, a: P(t, t0, t0 + .12) });
  });
  x.restore();
}

/* ---------- stacco · e se sbagliamo? (45.00 – 47.81s) ---------- */
function ifWrong(t) {
  const a = 45.0, b = 47.81;
  if (t < a || t > b) return;
  const e = env(t, a, b, .05, .15);
  x.save(); x.globalAlpha *= e;
  slam('E SE', 540, 900, 170, t, a, Z.wht);
  slam('SBAGLIAMO?', 540, 1080, 170, t, 45.674, Z.amb);
  x.restore();
}

/* ---------- 04 · journal e rollback (47.81 – 53.45s) ---------- */
const NDJ = ['{"ev":"plan","step":41}', '{"ev":"write","file":"nginx.conf"}', '{"ev":"restart","svc":"web"}', '{"ev":"error","code":502}', '{"ev":"rollback","to":41}', '{"ev":"verify","ok":true}'];
function journal(t) {
  const a = 47.81, b = 53.452;
  if (t < a || t > b) return;
  op(t, a, b, 'OP.04 // ROLLBACK', 'CTRL+Z', 'ogni passo nel journal, ogni passo annullabile', Z.cyn);
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  brackets(70, 700, 940, 640, Z.cyn);
  T('data/traces/*.ndjson', 110, 752, { size: 22, col: Z.mid });
  const times = [48.135, 48.878, 49.575, 50.294, 51.339, 52.407];
  const rew = t > 50.643 && t < 51.339;
  NDJ.forEach((s, i) => {
    if (t < times[i]) return;
    const y = 820 + i * 76, col = i === 3 ? Z.red : i === 4 ? Z.amb : i === 5 ? Z.grn : Z.wht;
    if (rew && i === 3) { x.fillStyle = 'rgba(255,30,86,0.25)'; x.fillRect(90, y - 40, 900, 56); }
    T(s, 110, y, { w: i >= 3 ? 700 : 400, size: 28, col, a: P(t, times[i], times[i] + .1) });
  });
  if (rew) {
    skewText('<< REWIND', 540, 1440, 90, Z.cyn, { al: 'center', split: 10 });
    for (let k = 0; k < 8; k++) { const y = 700 + ((t * 2200 + k * 210) % 640); x.fillStyle = 'rgba(0,229,255,0.2)'; x.fillRect(70, y, 940, 5); }
  }
  if (t > 52.407) slam('RIPRISTINATO', 540, 1450, 90, t, 52.407, Z.grn);
  x.restore();
}

/* ---------- calo · le chiavi (53.45 – 56.29s) ---------- */
function keys(t) {
  const a = 53.452, b = 56.285;
  if (t < a || t > b) return;
  op(t, a, b, 'OP.05 // CHIAVI', 'SPORE', 'chiave madre in 3 pezzi, ne bastano 2', Z.grn);
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  const split = oCub(P(t, 53.801, 54.3)), back = oCub(P(t, 55.24, 55.6));
  const pos = [[-1, 0], [0, -1], [1, 0]];
  pos.forEach(([u, v], i) => {
    const r = 240 * split * (i < 2 ? 1 - back : 1);
    const px = 540 + u * r, py = 1000 + v * r * .8;
    x.save(); x.translate(px, py); x.rotate(i * 2.1 + split * .3);
    x.fillStyle = i < 2 ? Z.grn : Z.dim; x.beginPath(); x.moveTo(0, -70); x.lineTo(70, 50); x.lineTo(-70, 50); x.closePath(); x.fill();
    x.restore();
    T(['FONDATORE', 'SOCIO', 'CARTA'][i], px, py + 110, { w: 700, size: 22, col: i < 2 ? Z.grn : Z.mid, al: 'center', a: split * (i < 2 ? 1 - back : 1) });
  });
  T('CHIAVE', 540, 1110, { w: 700, size: 26, col: Z.grn, al: 'center', a: back });
  if (t > 55.6) T('2 / 3 → APERTA', 540, 1320, { w: 700, size: 36, col: Z.grn, al: 'center' });
  T('ECDH · AES-256-GCM · anti-replay', 540, 1440, { size: 26, col: Z.mid, al: 'center', a: P(t, 54.2, 54.5) });
  x.restore();
}

/* ---------- 05 · il cancello MCP con lo scudo esagonale (56.29 – 61.93s) ---------- */
function hexShield(cy, t, hitT) {
  const r = 46, h = r * Math.sqrt(3);
  for (let row = -1; row <= 1; row++) for (let i = -7; i <= 7; i++) {
    const hx = 540 + i * r * 1.5, hy = cy + row * h + (i & 1) * h / 2;
    const flash = hitT.reduce((m, ht) => Math.max(m, (1 - P(t, ht, ht + .35)) * (t >= ht ? 1 : 0) * Math.max(0, 1 - Math.abs(hx - 540) / 600)), 0);
    x.save(); x.globalAlpha *= .35 + flash * .65; x.strokeStyle = flash > .1 ? Z.amb : Z.cyn; x.lineWidth = 3; x.beginPath();
    for (let k = 0; k < 6; k++) { const g = k * Math.PI / 3; x.lineTo(hx + Math.cos(g) * r * .92, hy + Math.sin(g) * r * .92); }
    x.closePath(); x.stroke(); x.restore();
  }
}
function gateOp(t) {
  const a = 56.285, b = 61.928;
  if (t < a || t > b) return;
  op(t, a, b, 'OP.06 // ACCESSO', 'GATE', '/mcp: senza token non entra nessuno', Z.cyn);
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  const sy = 1180, beats = beatsIn(56.61, 61.6);
  hexShield(sy, t, beats.filter((_, i) => i % 4 !== 3));
  beats.forEach((bt, i) => {
    const ok = i % 4 === 3, lx = 160 + rnd(i * 3) * 760, p = P(t, bt - .45, bt);
    if (t < bt - .45) return;
    if (t < bt) { x.fillStyle = ok ? Z.grn : Z.red; x.fillRect(lerp(lx, ok ? 540 : lx, p) - 14, lerp(620, sy - 120, p) - 14, 28, 28); return; }
    if (ok) { const q = P(t, bt, bt + .5); x.fillStyle = Z.grn; x.globalAlpha = 1 - q; x.fillRect(526, lerp(sy - 120, sy + 260, q), 28, 28); x.globalAlpha = 1; }
    else if (t < bt + .45) T(i % 3 ? '401' : '429', lx, sy - 160 - P(t, bt, bt + .45) * 60, { w: 900, size: 40, fam: FD, col: Z.red, al: 'center', a: 1 - P(t, bt + .25, bt + .45) });
  });
  T('token · allowlist dei tool · rate limit · circuit breaker', 540, 1520, { size: 24, col: Z.mid, al: 'center', a: P(t, 57.0, 57.3) });
  x.restore();
}

/* ---------- 06 · la mesh e l'hub in tasca (61.93 – 67.57s) ---------- */
const MN = [['M5', 300, 880], ['OMEN', 780, 880], ['ASUS', 300, 1260], ['S24', 780, 1260]];
function meshOp(t) {
  const a = 61.928, b = 67.57;
  if (t < a || t > b) return;
  const down = t > 63.692, promo = t > 64.76, hub = promo ? 3 : 0;
  op(t, a, b, 'OP.07 // RETE', 'LA MESH', 'Tailscale: dentro solo i nostri nodi', Z.grn, promo ? 'IN SVILUPPO' : null);
  const e = env(t, a, b, .1, .2);
  x.save(); x.globalAlpha *= e;
  MN.forEach(([, nx, ny], i) => {
    if (i === hub || (down && i === 0)) return;
    const [, hx, hy] = MN[hub];
    x.strokeStyle = promo ? Z.amb : Z.grn; x.lineWidth = 3; x.setLineDash([14, 10]); x.lineDashOffset = -t * 90;
    x.beginPath(); x.moveTo(nx, ny); x.lineTo(hx, hy); x.stroke(); x.setLineDash([]);
  });
  MN.forEach(([n, nx, ny], i) => {
    const dead = down && i === 0, isHub = i === hub;
    nodeBox(nx, ny, n, dead ? Z.red : isHub ? Z.amb : Z.grn, !dead, dead ? 'GIÙ' : isHub ? (promo ? 'POCKET HUB' : 'HUB') : i === 2 ? 'SOLARE' : i === 1 ? 'SEMPRE ACCESO' : '');
    if (isHub) brackets(nx - 125, ny - 70, 250, 140, Z.amb, 22, 3);
  });
  if (down && !promo) slam('HUB DOWN', 540, 1500, 110, t, 63.692, Z.red);
  if (promo) T('il telefono prende il posto dell’hub', 540, 1500, { w: 700, size: 30, col: Z.amb, al: 'center', a: P(t, 64.76, 65.0) });
  x.restore();
}

/* ---------- rullo finale (67.57 – 73.21s) e ultimo colpo (73.21 – 76s) ---------- */
const MANI = [[0, 'DOCUMENTATO.', Z.wht], [2, 'REVERSIBILE.', Z.wht], [4, 'LOCALE.', Z.wht], [6, 'NOSTRO.', Z.grn], [8, 'CON NOI', Z.wht], [10, 'NON SI', Z.wht], [12, 'SCHERZA.', Z.red]];
function finale(t) {
  if (t < 67.57) return;
  const roll = beatsIn(67.57, 73.213);
  if (t < 73.213) {
    MANI.forEach(([k, s, col], j) => {
      const t0 = roll[k], t1 = j + 1 < MANI.length ? roll[MANI[j + 1][0]] : roll[14];
      if (t < t0 || t >= t1) return;
      slam(s, 540, 1010, 200, t, t0, col);
    });
    if (t >= roll[14]) { const n = t < roll[15] ? '2' : '1'; slam(n, 540, 1080, 420, t, t < roll[15] ? roll[14] : roll[15], Z.red); }
    return;
  }
  speedLines(540, 900, t, 73.213, Z.red);
  slam('00MESH', 540, 900, 250, t, 73.213, Z.grn);
  T('contrattacco.', 540, 1020, { w: 900, size: 56, fam: FD, col: Z.wht, al: 'center', a: P(t, 73.561, 73.8) });
  const cp = oBack(P(t, 73.932, 74.2));
  if (cp > 0) {
    const lb = 'os.zerozerocomputer.it', wd = measure(lb, 700, 34, FM) + 80;
    x.save(); x.translate(540, 1160); x.scale(cp, cp); x.fillStyle = Z.grn; x.fillRect(-wd / 2, -44, wd, 88);
    T(lb, 0, 12, { w: 700, size: 34, col: Z.bg, al: 'center' }); x.restore();
  }
  T('red team solo su sistemi propri o autorizzati', 540, 1290, { size: 24, col: Z.mid, al: 'center', a: P(t, 74.3, 74.6) });
}

const REEL = {
  date: '31.10.2026',
  tagline: 'Contrattacco.',
  cta: 'os.zerozerocomputer.it',
  sc: [{ a: 11.099, b: 19.551, n: '01' }, { a: 22.384, b: 30.883, n: '02' }, { a: 30.883, b: 36.455, n: '03' }, { a: 36.455, b: 45.0, n: '04' },
    { a: 47.81, b: 53.452, n: '05' }, { a: 53.452, b: 56.285, n: '06' }, { a: 56.285, b: 61.928, n: '07' }, { a: 61.928, b: 67.57, n: '08' }],
  cuts: [19.551, 30.883, 45.0, 53.452, 61.928, 67.57],
  layers: { bg: netBg, intro: () => {}, outro: () => {}, hud: cineHud, cuts: netCuts, fade: Z.bg },
  scenes: [nightly, dive, weFirst, strixOp, recon, detonate, ifWrong, journal, keys, gateOp, meshOp, finale]
};
