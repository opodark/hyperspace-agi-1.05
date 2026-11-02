// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "youtube-106-2026-11-02", "title": "HyperSpace 1.06 · Resin, Laya, Qwenputer", "dur": 111.5, "formats": ["16:9"], "styles": ["netdive"], "aria": "Video orizzontale di circa un minuto e cinquanta, senza voce narrante, con didascalie grandi sempre leggibili, in stile videogioco e cyberpunk su musica elettronica. Presenta le tre novità di HyperSpace 1.06. Apertura: tre pezzi nuovi, una sola mesh. Resin: un motore d'inferenza scritto in Rust che possiede le risorse mentre il runner (MLX, CUDA, Qwenputer) esegue i tensori, con una sola memoria a slab per la cache di attenzione e lo stato ricorrente, così il secondo agente con lo stesso prompt non ricalcola nulla. Laya: il System 1 che decide con una sola passata in circa 30 millisecondi contro i 3-10 secondi di un modello generativo, in più di cento lingue, con una soglia di confidenza di 0,85 sotto la quale passa la mano al modello grande, usato come fast-gate del verifier di Mission Control senza spendere token. Qwenputer: un processore RISC-V RV32IM compilato dentro i pesi del modello senza addestramento, dove ogni token è un ciclo di clock e le righe dello stato Gated DeltaNet fanno da RAM, con il codice degli agenti che gira nella memoria della GPU senza chiamate al sistema operativo e con aritmetica esatta. La prova: una missione distribuita su Mac M5, HP OMEN e ASUS completata in 1,56 secondi. Chiusura: HyperSpace 1.06, os.zerozerocomputer.it."}
/* Reel orizzontale 16:9 nativo su «Mind In Chaos» (elettronica, ~111 s usati: dal secondo 12,0 al 123,5 del brano).
   Nessuna voce: il messaggio sta nelle didascalie grandi (livello `caption`, sempre ferme, mai scosse dal ritmo).
   Il brano ha una pausa-stacco ogni ~5,4 s: le didascalie cambiano proprio lì, i capitoli cadono sui rientri.
   Beat (BT) e inviluppo (ENV) vengono da librosa sul file reale, già traslati di AOFF. Lo stile netdive è
   importato da styles/. I numeri a schermo (30 ms, 3–10 s, 0,85, 1,56 s, 112635269) vengono dalla documentazione
   e dai risultati reali dello stress test del 2 novembre; gli schemi (griglia di slab, righe di RAM) sono illustrativi. */

const AOFF = 12.0;
const BT = [0.005,0.353,0.678,1.026,1.375,1.723,2.048,2.373,2.721,3.07,3.418,3.743,4.091,4.44,4.765,5.113,5.461,5.81,6.135,6.483,6.831,7.18,7.505,7.83,8.178,8.526,8.852,9.2,9.548,9.873,10.221,10.57,10.918,11.266,11.591,11.917,12.288,12.613,12.961,13.287,13.635,13.983,14.308,14.657,15.005,15.33,15.678,16.003,16.352,16.7,17.048,17.373,17.745,18.07,18.395,18.743,19.092,19.44,19.765,20.113,20.461,20.787,21.135,21.46,21.808,22.157,22.505,22.83,23.201,23.527,23.875,24.2,24.548,24.897,25.222,25.57,25.918,26.243,26.592,26.917,27.265,27.613,27.938,28.287,28.658,28.983,29.308,29.657,30.005,30.353,30.678,31.027,31.375,31.7,32.048,32.373,32.722,33.07,33.395,33.743,34.115,34.44,34.765,35.113,35.462,35.81,36.135,36.46,36.808,37.157,37.482,37.83,38.178,38.527,38.852,39.2,39.548,39.897,40.222,40.547,40.918,41.267,41.592,41.94,42.288,42.637,42.962,43.287,43.612,43.937,44.308,44.633,45.005,45.353,45.678,46.003,46.375,46.7,47.048,47.373,47.722,48.07,48.395,48.743,49.092,49.417,49.765,50.09,50.438,50.787,51.135,51.46,51.832,52.157,52.482,52.83,53.178,53.527,53.852,54.2,54.548,54.873,55.222,55.547,55.895,56.243,56.569,56.917,57.288,57.613,57.939,58.287,58.635,58.983,59.308,59.634,59.982,60.33,60.678,61.004,61.352,61.7,62.025,62.374,62.745,63.07,63.395,63.743,64.092,64.44,64.765,65.09,65.439,65.787,66.112,66.46,66.809,67.157,67.482,67.83,68.179,68.527,68.852,69.177,69.525,69.874,70.222,70.547,70.895,71.244,71.569,71.917,72.265,72.614,72.939,73.287,73.635,73.983,74.309,74.634,75.005,75.33,75.655,76.004,76.352,76.677,77.025,77.374,77.722,78.07,78.395,78.72,79.092,79.417,79.765,80.09,80.439,80.787,81.112,81.46,81.809,82.134,82.482,82.83,83.179,83.527,83.852,84.177,84.549,84.874,85.199,85.547,85.849,86.128,86.453,86.801,87.149,87.474,87.823,88.171,88.496,88.844,89.285,89.634,89.982,90.33,90.655,91.004,91.375,91.7,92.025,92.35,92.699,93.047,93.395,93.72,94.069,94.417,94.742,95.09,95.439,95.787,96.112,96.46,96.809,97.157,97.482,97.807,98.179,98.527,98.852,99.2,99.549,99.874,100.199,100.547,100.895,101.244,101.569,101.917,102.265,102.59,102.939,103.264,103.612,103.96,104.286,104.634,104.982,105.307,105.656,106.004,106.352,106.7,107.025,107.351,107.722,108.047,108.395,108.721,109.069,109.417,109.765,110.114,110.439,110.764,111.112,111.437];
const ENV = [0.28,0.79,0.74,0.79,0.66,0.71,0.62,0.86,0.89,0.64,0.88,0.23,0.85,0.68,0.81,0.67,0.67,0.64,0.97,0.78,0.62,0.88,0.35,0.91,0.49,0.82,0.69,0.65,0.65,0.98,0.76,0.64,0.89,0.56,0.83,0.44,0.84,0.75,0.54,0.65,0.99,0.75,0.58,0.01,0.85,0.27,0.8,0.74,0.8,0.67,0.7,0.63,0.87,0.88,0.64,0.89,0.22,0.87,0.66,0.81,0.68,0.67,0.64,0.97,0.78,0.6,0.88,0.37,0.91,0.49,0.82,0.69,0.65,0.65,0.99,0.77,0.65,0.89,0.57,0.83,0.44,0.85,0.76,0.54,0.65,1.0,0.76,0.68,0.32,0.89,0.27,0.8,0.75,0.8,0.68,0.69,0.63,0.88,0.89,0.64,0.89,0.22,0.88,0.65,0.81,0.68,0.67,0.64,0.98,0.68,0.16,0.88,0.38];

/* ---------- ritmo ---------- */
function bIdx(t) { let i = -1; while (i + 1 < BT.length && BT[i + 1] <= t) i++; return i; }
const since = t => { const i = bIdx(t); return i < 0 ? 9 : t - BT[i]; };
const energy = t => { const i = Math.min(ENV.length - 2, Math.max(0, Math.floor(t))); return clamp(lerp(ENV[i], ENV[i + 1], t - i)); };
const pwr = t => .25 + .75 * energy(t);
const thp = t => Math.exp(-since(t) * 8) * pwr(t) * (bIdx(t) % 2 === 0 ? 1 : .4);
NETDIVE.power = pwr; NETDIVE.thump = thp; NETDIVE.bIdx = bIdx;
NETDIVE.slams = [11.1, 33.0, 67.0, 101.1];
NETDIVE.hud = { tag: 'HYPERSPACE AGI 1.06', footer: 'RESIN · LAYA · QWENPUTER' };

const CO = W / 2;
const GR = NC.grn, CY = NC.cyn, RD = NC.red, WH = NC.wht, AM = NC.amb, MG = '#FF2BD6';
const BLK = [0, 11.1, 22.0, 33.0, 43.8, 56.1, 67.0, 78.0, 90.2, 101.1, 106.5, 111.5];

/* ---------- didascalie: grandi, ferme, con il termine chiave a colore ---------- */
/* [inizio, fine, colore, righe]; nelle righe i tratti fra due * sono evidenziati */
const CAPS = [
  [0.9, 5.3, GR, ['Tre pezzi *nuovi.*']],
  [6.1, 10.8, GR, ['Una sola *mesh.*']],
  [11.4, 16.2, GR, ['*RESIN*: un motore d’inferenza', 'scritto in *Rust*']],
  [16.9, 21.7, GR, ['Chi possiede le risorse', '*non esegue i tensori*']],
  [22.3, 27.2, GR, ['Una sola memoria per', '*cache* e *stato* del modello']],
  [27.8, 32.7, CY, ['Due agenti, stesso prompt:', 'il secondo *non ricalcola niente*']],
  [33.3, 38.0, MG, ['*LAYA*: per un sì o un no', 'non serve un romanzo']],
  [38.7, 43.4, MG, ['Una sola passata:', '*30 ms* su GPU']],
  [44.1, 50.3, MG, ['Più di *cento lingue*']],
  [51.0, 55.9, AM, ['Se non è sicura, lo dice e', '*passa la mano* al modello grande']],
  [56.4, 61.4, MG, ['In *Mission Control* controlla', 'il lavoro degli agenti']],
  [62.0, 66.8, MG, ['Quando è sicura:', '*zero token* spesi']],
  [67.3, 72.2, CY, ['*QWENPUTER*: un processore RISC-V', 'dentro i pesi del modello']],
  [72.8, 77.7, CY, ['Nessun addestramento:', 'pesi *calcolati da un compilatore*']],
  [78.3, 83.1, CY, ['Ogni token è un', '*ciclo di clock*']],
  [83.7, 89.7, CY, ['Lo *stato del modello*', 'fa da memoria']],
  [90.5, 95.4, CY, ['Il codice degli agenti gira nella *GPU*,', 'senza chiamate al sistema operativo']],
  [96.0, 100.8, CY, ['Niente fughe.', '*Calcoli esatti.*']],
  [101.4, 106.3, GR, ['Una missione su *tre nodi*:', '*1,56 secondi*']],
  [106.8, 111.0, GR, ['Una sola mesh,', 'tre pezzi *nuovi*']]
];
function caption(t) {
  const c = CAPS.find(k => t >= k[0] && t <= k[1]); if (!c) return;
  const [a, b, acc, lines] = c;
  const pin = oBack(P(t, a, a + .3)), pout = 1 - iCub(P(t, b - .25, b));
  const al = Math.min(1, pin * 3) * pout; if (al <= 0) return;
  const segs = lines.map(l => l.split('*'));
  const lw = (sg, sz) => sg.reduce((s, p) => s + measure(p, 700, sz, FD), 0);
  let size = 66; const mx = Math.max(...segs.map(sg => lw(sg, size)));
  if (mx > 1620) size = Math.floor(size * 1620 / mx);
  const LH = size * 1.2, ph = LH * lines.length + 44, pwid = Math.max(...segs.map(sg => lw(sg, size))) + 110;
  const top = 956 - ph + (1 - Math.min(pin, 1)) * 36, L = CO - pwid / 2;
  x.save(); x.setTransform(1, 0, 0, 1, 0, 0); x.globalAlpha = al;
  x.fillStyle = 'rgba(2,6,5,0.92)'; rrect(L, top, pwid, ph, 18); x.fill();
  x.strokeStyle = acc; x.lineWidth = 3; rrect(L, top, pwid, ph, 18); x.stroke();
  x.fillStyle = acc; rrect(L + 18, top + 18, 9, ph - 36, 4); x.fill();
  segs.forEach((sg, li) => {
    let X = CO - lw(sg, size) / 2 + 14; const Y = top + 22 + LH * li + size * .9;
    sg.forEach((part, i) => { T(part, X, Y, { w: 700, size, fam: FD, col: i % 2 ? acc : WH }); X += measure(part, 700, size, FD); });
  });
  x.restore();
}

/* ---------- HUD (bande cinema, capitolo, tempo, avanzamento) ---------- */
const CHAPS = [['APERTURA', 0, 11.1], ['RESIN', 11.1, 33.0], ['LAYA', 33.0, 67.0], ['QWENPUTER', 67.0, 101.1], ['LA PROVA', 101.1, 111.5]];
const CHCOL = { APERTURA: GR, RESIN: GR, LAYA: MG, QWENPUTER: CY, 'LA PROVA': AM };
function hudR(t) {
  x.setTransform(1, 0, 0, 1, 0, 0);
  x.fillStyle = '#000'; x.fillRect(0, 0, W, 112); x.fillRect(0, H - 104, W, 104);
  const a = P(t, .3, 1.0);
  T('HYPERSPACE AGI 1.06', 80, 68, { w: 700, size: 24, col: GR, ls: 4, a });
  const ch = CHAPS.find(c => t >= c[1] && t < c[2]);
  if (ch) T(ch[0], W - 80, 68, { w: 700, size: 26, col: CHCOL[ch[0]], al: 'right', ls: 4, a });
  T('RESIN · LAYA · QWENPUTER', 80, H - 60, { size: 20, col: NC.mid, ls: 3, a });
  const tc = 'T+' + String(Math.floor(t / 60)).padStart(2, '0') + ':' + (t % 60).toFixed(1).padStart(4, '0');
  T(tc, W - 80, H - 60, { w: 700, size: 20, col: GR, al: 'right', ls: 2, a });
  x.fillStyle = NC.dim; x.fillRect(80, H - 40, W - 160, 4);
  x.fillStyle = GR; x.fillRect(80, H - 40, (W - 160) * t / DUR, 4);
  for (const c of CHAPS) circ(80 + (W - 160) * c[1] / DUR, H - 38, 5, { fill: t >= c[1] ? CHCOL[c[0]] : NC.dim });
  x.save(); x.fillStyle = 'rgba(0,0,0,0.16)'; for (let y = 112; y < H - 104; y += 3) x.fillRect(0, y, W, 1); x.restore();
  const v = x.createRadialGradient(CO, H / 2, 560, CO, H / 2, 1180);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.5)'); x.fillStyle = v; x.fillRect(0, 112, W, H - 216);
}

/* ---------- mattoni ---------- */
function chapTitle(t, a, b, code, title, sub, col) {
  const e = env(t, a, b, .15, .3); if (e <= 0) return;
  x.save(); x.globalAlpha *= e;
  T(code.slice(0, Math.floor(code.length * P(t, a, a + .4))), 80, 205, { w: 700, size: 24, col, ls: 4 });
  slam(title, 80, 400, 170, t, a + .05, WH, { al: 'left', maxW: 840 });
  x.fillStyle = col; x.fillRect(80, 434, 840 * oExpo(P(t, a + .1, a + .6)), 6);
  T(sub, 80, 496, { w: 600, size: 32, fam: FD, col, a: P(t, a + .4, a + .8) });
  x.restore();
}
function vpanel(col, t, a) {
  const p = oExpo(P(t, a, a + .5)); if (p <= 0) return;
  x.save(); x.globalAlpha *= p; brackets(980, 160, 860, 610, col, 28, 3); x.restore();
}
function sbox(cx, cy, w, h, label, sub, col, p = 1, lit = false) {
  if (p <= 0) return;
  x.save(); x.globalAlpha *= clamp(p);
  x.fillStyle = lit ? 'rgba(0,255,156,0.16)' : 'rgba(2,8,7,0.84)'; x.fillRect(cx - w / 2, cy - h / 2, w, h);
  x.strokeStyle = col; x.lineWidth = 3.5; x.strokeRect(cx - w / 2, cy - h / 2, w, h);
  T(label, cx, cy + (sub ? -2 : 11), { w: 700, size: 30, fam: FD, col, al: 'center' });
  if (sub) T(sub, cx, cy + 28, { size: 22, col: NC.mid, al: 'center' });
  x.restore();
}
function vlink(X, y1, y2, t, col, on = 1) {
  if (on <= 0) return;
  seg(X, y1, X, y2, { col, lw: 3, a: on, dash: [10, 8], off: -t * 70 });
  for (let k = 0; k < 2; k++) { const u = (t * .9 + k * .5) % 1; circ(X, lerp(y1, y2, u), 6, { fill: WH, a: on }); }
}

/* ============ 0 · apertura (0 – 11.1) ============ */
function sOpen(t) {
  const a = 0, b = 11.1; if (t > b) return;
  const e = env(t, a, b, .8, .3);
  x.save(); x.globalAlpha *= e;
  speedLines(CO, 400, t, 3.2, CY);
  mesh(CO, 350, 120, t, ioCub(P(t, .6, 3.2)), 1, false);
  slam('HYPERSPACE 1.06', CO, 590, 150, t, 3.2, WH, { maxW: 1500 });
  [['RESIN', 560, GR, 5.5], ['LAYA', 960, MG, 6.4], ['QWENPUTER', 1360, CY, 7.3]].forEach(([s, X, col, t0]) => {
    const p = oBack(P(t, t0, t0 + .35)); if (p <= 0) return;
    x.save(); x.translate(X, 700); x.scale(p, p);
    T(s, 0, 0, { w: 700, size: 52, fam: FD, col, al: 'center', ls: 4 });
    x.fillStyle = col; x.fillRect(-150, 20, 300, 5);
    x.restore();
  });
  x.restore();
}

/* ============ 1 · Resin, il flusso (11.1 – 22.0) ============ */
function sResinFlow(t) {
  const a = 11.1, b = 22.0; if (t < a || t > b) return;
  chapTitle(t, a, b, 'RESIN // 01', 'RESIN', 'SUBSTRATO D’INFERENZA IN RUST', GR);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(GR, t, a + .2);
  const cx = 1380, ys = [215, 355, 495, 635];
  const BX = [['TOKEN IDs', 'in ingresso', NC.mid], ['MOTORE RUST', 'resin-core', GR], ['PIANO CONGELATO', 'BatchPlan · rkyv', CY], ['RUNNER', 'MLX · CUDA · QWENPUTER', MG]];
  BX.forEach(([l, s, col], i) => {
    const p = oBack(P(t, a + .6 + i * .5, a + 1.0 + i * .5));
    sbox(cx, ys[i], 400, 92, l, s, col, p, i === 1 && t > a + 3.2);
    if (i < 3) vlink(cx, ys[i] + 46, ys[i + 1] - 46, t, col, P(t, a + 1.1 + i * .5, a + 1.5 + i * .5));
  });
  T('DECIDE', cx + 230, ys[1] + 10, { w: 700, size: 30, fam: FD, col: GR, a: P(t, a + 3.4, a + 3.9) });
  T('CALCOLA', cx + 230, ys[3] + 10, { w: 700, size: 30, fam: FD, col: MG, a: P(t, a + 4.4, a + 4.9) });
  T('lease · prefix · stato tornano al motore', cx, 726, { size: 22, col: NC.mid, al: 'center', a: P(t, a + 6, a + 6.6) });
  x.restore();
}

/* ============ 2 · Resin, memoria unificata (22.0 – 33.0) ============ */
function sResinSlab(t) {
  const a = 22.0, b = 33.0; if (t < a || t > b) return;
  chapTitle(t, a, b, 'RESIN // 02', 'RESIN', 'UNA MEMORIA, DUE USI', GR);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(GR, t, a + .2);
  const gx = 1039, gy = 192, kind = i => { const r = rnd(i * 5.3 + 2); return r < .5 ? 0 : r < .8 ? 1 : 2; };
  const KC = [GR, MG, '#16282B'];
  for (let i = 0; i < 24; i++) {
    const c = i % 8, r = Math.floor(i / 8), p = oBack(P(t, a + .4 + i * .09, a + .8 + i * .09)); if (p <= 0) continue;
    const cx = gx + c * 94 + 42, cy = gy + r * 94 + 42, k = kind(i);
    x.save(); x.translate(cx, cy); x.scale(p, p); x.fillStyle = KC[k]; x.globalAlpha *= k === 2 ? 1 : .92;
    rrect(-42, -42, 84, 84, 10); x.fill();
    if (k === 2) { x.strokeStyle = NC.dim; x.lineWidth = 2; rrect(-42, -42, 84, 84, 10); x.stroke(); }
    x.restore();
  }
  [['HISTORY · KV', GR, 1039], ['STATE · DELTANET', MG, 1262], ['LIBERO', '#16282B', 1600]].forEach(([s, col, X]) => {
    x.fillStyle = col; x.fillRect(X, 494, 24, 24); if (col === '#16282B') { x.strokeStyle = NC.dim; x.lineWidth = 2; x.strokeRect(X, 494, 24, 24); }
    T(s, X + 36, 514, { size: 22, col: NC.wht, a: P(t, a + 2.6, a + 3.0) });
  });
  T('AGENTE 1 · PREFILL', gx, 566, { w: 700, size: 22, col: GR, a: P(t, a + 2.8, a + 3.2) });
  T('AGENTE 2 · STESSO PROMPT', gx, 652, { w: 700, size: 22, col: CY, a: P(t, a + 2.8, a + 3.2) });
  for (let k = 0; k < 8; k++) {
    const X = gx + k * 94, f1 = t >= a + 3.2 + k * .55, f2 = t >= a + 7.8;
    x.strokeStyle = NC.dim; x.lineWidth = 2; x.strokeRect(X, 578, 84, 38); x.strokeRect(X, 664, 84, 38);
    if (f1) { x.fillStyle = GR; x.fillRect(X, 578, 84, 38); }
    if (f2) { x.fillStyle = CY; x.fillRect(X, 664, 84, 38); }
  }
  const fl = 1 - P(t, a + 7.8, a + 8.4);
  if (fl > 0) { x.fillStyle = `rgba(0,229,255,${fl * .35})`; x.fillRect(gx - 10, 640, 780, 74); }
  T('PREFIX HIT · NIENTE DA RICALCOLARE', gx, 746, { w: 700, size: 26, fam: FD, col: CY, a: P(t, a + 8.0, a + 8.5) });
  x.restore();
}

/* ============ 3 · Laya, la corsa (33.0 – 43.8) ============ */
function sLayaRace(t) {
  const a = 33.0, b = 43.8; if (t < a || t > b) return;
  chapTitle(t, a, b, 'LAYA // 01', 'LAYA', 'SYSTEM 1 · UNA SOLA PASSATA', MG);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(MG, t, a + .2);
  const X0 = 1030, BW = 760, p1 = P(t, a + .8, a + 9.6), p2 = oExpo(P(t, a + 5.8, a + 6.1));
  T('LLM GENERATIVO 8B–27B · SYSTEM 2', X0, 252, { w: 700, size: 24, col: RD });
  T(((t - a - .8 > 0 ? Math.min(p1 * 8.8, 8.8) : 0)).toFixed(1) + ' s', X0 + BW, 252, { w: 700, size: 30, fam: FM, col: RD, al: 'right' });
  x.strokeStyle = NC.dim; x.lineWidth = 3; x.strokeRect(X0, 270, BW, 58);
  x.fillStyle = RD; x.fillRect(X0 + 4, 274, (BW - 8) * p1, 50);
  T('LAYA · SYSTEM 1', X0, 432, { w: 700, size: 24, col: MG });
  T(t > a + 5.8 ? '30 ms' : '0 ms', X0 + BW, 432, { w: 700, size: 30, fam: FM, col: MG, al: 'right' });
  x.strokeStyle = NC.dim; x.lineWidth = 3; x.strokeRect(X0, 450, BW, 58);
  x.fillStyle = MG; x.fillRect(X0 + 4, 454, (BW - 8) * p2, 50);
  const bp = oBack(P(t, a + 6.0, a + 6.5));
  if (bp > 0) { x.save(); x.translate(X0, 650); x.scale(bp, bp); T('30 ms', 0, 0, { w: 700, size: 130, fam: FD, col: MG, ls: -4 }); x.restore(); }
  T('una passata · zero token', X0 + 410, 640, { w: 600, size: 30, fam: FD, col: WH, a: P(t, a + 6.6, a + 7.2) });
  T('GPU · ~120 ms su Apple Silicon', X0 + 410, 682, { size: 24, col: NC.mid, a: P(t, a + 7.0, a + 7.6) });
  T('(corsa dimostrativa: 3–10 s contro 30 ms)', X0, 742, { size: 22, col: NC.mid, a: P(t, a + 1.5, a + 2.1) });
  x.restore();
}

/* ============ 4 · Laya, lingue e confidenza (43.8 – 56.1) ============ */
function sLayaLang(t) {
  const a = 43.8, b = 56.1; if (t < a || t > b) return;
  chapTitle(t, a, b, 'LAYA // 02', 'LAYA', 'CENTO LINGUE · CONFIDENZA CALIBRATA', MG);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(MG, t, a + .2);
  const W_ = ['SÍ', 'YES', 'JA', 'OUI', 'SIM', 'EVET', 'TAK', 'DA', '+100'], X0 = 1017, Y0 = 188;
  W_.forEach((s, i) => {
    const c = i % 3, r = Math.floor(i / 3), X = X0 + c * 268, Y = Y0 + r * 104;
    const lit = Math.floor((t - a - .5) / .5) % 9 === i && t > a + .5;
    const seen = t > a + .5 + i * .5;
    x.fillStyle = lit ? 'rgba(255,43,214,0.28)' : 'rgba(2,8,7,0.8)'; x.fillRect(X, Y, 250, 88);
    x.strokeStyle = lit ? MG : seen ? NC.mid : NC.dim; x.lineWidth = 3; x.strokeRect(X, Y, 250, 88);
    T(s, X + 125, Y + 60, { w: 700, size: i === 8 ? 40 : 46, fam: FD, col: lit ? WH : seen ? MG : NC.dim, al: 'center' });
  });
  const GY = 580, GW = 786, v = t < a + 5.2 ? .52 + Math.sin(t * 3) * .04 : lerp(.56, .93, oCub(P(t, a + 5.2, a + 8.0)));
  T('CONFIDENZA', X0, GY - 14, { w: 700, size: 24, col: NC.wht });
  x.strokeStyle = NC.dim; x.lineWidth = 3; x.strokeRect(X0, GY, GW, 50);
  x.fillStyle = v >= .85 ? GR : AM; x.fillRect(X0 + 4, GY + 4, (GW - 8) * v, 42);
  const tx = X0 + GW * .85; x.fillStyle = WH; x.fillRect(tx - 2, GY - 12, 4, 74);
  T('SOGLIA 0,85', tx, GY - 22, { w: 700, size: 22, col: AM, al: 'center' });
  T(v >= .85 ? 'SICURA · DECIDE LAYA' : 'INCERTA · PASSA AL MODELLO GRANDE', X0, GY + 112, { w: 700, size: 32, fam: FD, col: v >= .85 ? GR : AM });
  x.restore();
}

/* ============ 5 · Laya, fast-gate di Mission Control (56.1 – 67.0) ============ */
function sLayaGate(t) {
  const a = 56.1, b = 67.0; if (t < a || t > b) return;
  chapTitle(t, a, b, 'LAYA // 03', 'LAYA', 'MISSION CONTROL · FAST-GATE', MG);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(MG, t, a + .2);
  const cx = 1410;
  sbox(cx, 225, 420, 90, 'OUTPUT DEL WORKER', 'più evidenza dei tool', NC.mid, oBack(P(t, a + .5, a + .9)));
  vlink(cx, 270, 305, t, MG, P(t, a + 1, a + 1.4));
  sbox(cx, 350, 420, 90, 'LAYA', 'system: laya-1', MG, oBack(P(t, a + 1.2, a + 1.6)), true);
  vlink(cx, 395, 470, t, MG, P(t, a + 1.7, a + 2.1));
  const CH = ['PASS', 'RETRY', 'REPLAN', 'FAIL'], act = t > a + 2.4 ? Math.floor((t - a - 2.4) / 1.3) % 4 : -1;
  CH.forEach((s, i) => {
    const X = 1017 + i * 198, on = i === act, p = oBack(P(t, a + 2.0 + i * .1, a + 2.4 + i * .1)); if (p <= 0) return;
    x.save(); x.globalAlpha *= clamp(p);
    x.fillStyle = on ? MG : 'rgba(2,8,7,0.84)'; x.fillRect(X, 478, 186, 70);
    x.strokeStyle = on ? MG : NC.mid; x.lineWidth = 3; x.strokeRect(X, 478, 186, 70);
    T(s, X + 93, 523, { w: 700, size: 30, fam: FD, col: on ? NC.bg : NC.wht, al: 'center' });
    x.restore();
  });
  T('0 TOKEN', 1017, 690, { w: 700, size: 104, fam: FD, col: GR, ls: -3, a: P(t, a + 3.2, a + 3.7) });
  T('< 50 ms', 1560, 690, { w: 700, size: 58, fam: FD, col: CY, a: P(t, a + 3.8, a + 4.3) });
  T('quando la confidenza è almeno 0,85', 1017, 742, { size: 22, col: NC.mid, a: P(t, a + 4.2, a + 4.8) });
  x.restore();
}

/* ============ 6 · Qwenputer, la CPU nei pesi (67.0 – 78.0) ============ */
function sQwChip(t) {
  const a = 67.0, b = 78.0; if (t < a || t > b) return;
  chapTitle(t, a, b, 'QWENPUTER // 01', 'QWENPUTER', 'CPU RISC-V DENTRO I PESI', CY);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(CY, t, a + .2);
  const C0 = 4, C1 = 11, R0 = 2, R1 = 7, X0 = 994, Y0 = 186;
  for (let r = 0; r < 10; r++) for (let c = 0; c < 16; c++) {
    const X = X0 + c * 52, Y = Y0 + r * 52, die = c >= C0 && c <= C1 && r >= R0 && r <= R1;
    const d = Math.hypot(c - 7.5, r - 4.5), lit = die ? clamp((t - (a + 1.2 + d * .18)) * 3) : 0;
    const fl = rnd(c * 17 + r * 5 + bIdx(t) * 3) > .93 ? .5 : 0;
    x.fillStyle = '#0B1B17'; x.fillRect(X, Y, 46, 46);
    x.strokeStyle = '#173229'; x.lineWidth = 1.5; x.strokeRect(X, Y, 46, 46);
    if (lit > 0) { x.fillStyle = CY; x.globalAlpha = e * (.55 + .3 * lit) * lit; x.fillRect(X, Y, 46, 46); x.globalAlpha = e; }
    else if (fl) { x.fillStyle = GR; x.globalAlpha = e * fl * .6; x.fillRect(X, Y, 46, 46); x.globalAlpha = e; }
  }
  const lp = P(t, a + 3.4, a + 3.9);
  if (lp > 0) {
    x.fillStyle = `rgba(2,6,5,${.8 * lp})`; x.fillRect(X0 + C0 * 52 + 20, Y0 + 3 * 52 + 14, 6 * 52 + 20, 3 * 52);
    T('RV32IM', X0 + 8 * 52 - 3, Y0 + 4 * 52 + 22, { w: 700, size: 58, fam: FD, col: WH, al: 'center', a: lp });
  }
  T('PESI CALCOLATI DA UN COMPILATORE · NESSUN TRAINING', 994, 738, { size: 22, col: CY, a: P(t, a + 4.8, a + 5.4) });
  x.restore();
}

/* ============ 7 · Qwenputer, clock e RAM (78.0 – 90.2) ============ */
function sQwClock(t) {
  const a = 78.0, b = 90.2; if (t < a || t > b) return;
  chapTitle(t, a, b, 'QWENPUTER // 02', 'QWENPUTER', 'GATED DELTANET = RAM', CY);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(CY, t, a + .2);
  const tick = Math.max(0, bIdx(t) - bIdx(a)), X0 = 1010;
  for (let k = 0; k < 10; k++) {
    const Y = 190 + k * 54, cur = tick % 10 === k, last = tick - ((tick - k) % 10 + 10) % 10;
    const p = oBack(P(t, a + .3 + k * .08, a + .6 + k * .08)); if (p <= 0) continue;
    x.save(); x.globalAlpha *= clamp(p);
    x.fillStyle = cur ? MG : 'rgba(2,8,7,0.84)'; x.fillRect(X0, Y, 540, 44);
    x.strokeStyle = cur ? MG : NC.dim; x.lineWidth = 2.5; x.strokeRect(X0, Y, 540, 44);
    T('R' + String(k).padStart(2, '0'), X0 + 14, Y + 31, { w: 700, size: 24, col: cur ? NC.bg : NC.mid });
    const val = last < 0 ? '00000000' : Math.floor(rnd(last * 13 + k) * 4294967295).toString(16).padStart(8, '0');
    T('0x' + val, X0 + 526, Y + 31, { w: 700, size: 24, col: cur ? NC.bg : CY, al: 'right' });
    x.restore();
  }
  T('CLOCK', 1600, 222, { w: 700, size: 24, col: NC.mid, ls: 3 });
  T(String(tick).padStart(4, '0'), 1600, 296, { w: 700, size: 72, fam: FM, col: CY });
  T('PC 0x' + (0x100 + 4 * tick).toString(16).padStart(4, '0'), 1600, 350, { w: 700, size: 28, col: WH });
  T('1 TOKEN', 1600, 470, { w: 700, size: 34, fam: FD, col: WH, a: P(t, a + 1.5, a + 2.0) });
  T('= 1 CICLO', 1600, 514, { w: 700, size: 34, fam: FD, col: GR, a: P(t, a + 1.8, a + 2.3) });
  T('(schema illustrativo)', 1600, 740, { size: 20, col: NC.mid, a: P(t, a + 2, a + 2.5) });
  x.restore();
}

/* ============ 8 · Qwenputer, zero-escape (90.2 – 101.1) ============ */
function sQwSand(t) {
  const a = 90.2, b = 101.1; if (t < a || t > b) return;
  chapTitle(t, a, b, 'QWENPUTER // 03', 'QWENPUTER', 'ZERO-ESCAPE · NESSUNA SYSCALL', CY);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(CY, t, a + .2);
  const gp = oBack(P(t, a + .4, a + .9));
  if (gp > 0) {
    x.save(); x.globalAlpha *= clamp(gp);
    x.fillStyle = 'rgba(2,8,7,0.86)'; x.fillRect(1010, 200, 520, 380); x.strokeStyle = CY; x.lineWidth = 4; x.strokeRect(1010, 200, 520, 380);
    T('VRAM · GPU', 1030, 238, { w: 700, size: 26, col: CY, ls: 3 });
    const L = ['// agente: calcolo', 'x = 123456789 * 987654321;', 'r = x % 1000000000;', '-> ' + '112635269'];
    L.forEach((s, i) => {
      const n = Math.floor(s.length * P(t, a + 1.2 + i * 1.1, a + 1.9 + i * 1.1));
      T(s.slice(0, n), 1030, 300 + i * 54, { w: i === 3 ? 700 : 400, size: i === 3 ? 40 : 24, fam: FM, col: i === 3 ? GR : i === 0 ? NC.mid : WH });
    });
    T('RV32IM · bignum hardware', 1030, 540, { size: 22, col: NC.mid, a: P(t, a + 5.5, a + 6.0) });
    x.restore();
  }
  // il muro e il sistema operativo
  const wp = P(t, a + .8, a + 1.4);
  seg(1580, 200, 1580, 580, { col: AM, lw: 6, a: wp, dash: [14, 10], off: -t * 30 });
  x.save(); x.globalAlpha *= wp; x.fillStyle = 'rgba(40,6,14,0.7)'; x.fillRect(1620, 200, 220, 380); x.strokeStyle = RD; x.lineWidth = 3; x.strokeRect(1620, 200, 220, 380);
  T('SISTEMA', 1730, 360, { w: 700, size: 28, fam: FD, col: RD, al: 'center' }); T('OPERATIVO', 1730, 396, { w: 700, size: 28, fam: FD, col: RD, al: 'center' });
  T('SYSCALL: 0', 1730, 470, { w: 700, size: 24, col: WH, al: 'center' });
  x.restore();
  for (let k = 0; k < 3; k++) {
    const u = ((t - a - 2.0 + k * .8) % 2.4) / 2.4; if (t < a + 2.0 || u < 0) continue;
    const px = lerp(1535, 1572, Math.min(1, u * 1.6)), py = 290 + k * 90;
    circ(px, py, 7, { fill: u < .62 ? WH : RD, a: u < .85 ? 1 : 1 - (u - .85) / .15 });
    if (u >= .62 && u < .9) { seg(1560, py - 14, 1590, py + 14, { col: RD, lw: 6 }); seg(1590, py - 14, 1560, py + 14, { col: RD, lw: 6 }); }
  }
  T('ARITMETICA ESATTA · 62+ CIFRE · NIENTE DRIFT', 1010, 660, { w: 600, size: 30, fam: FD, col: CY, a: P(t, a + 6.2, a + 6.8) });
  T('gcd(1071, 462) = 21', 1010, 712, { size: 28, col: WH, a: P(t, a + 7.2, a + 7.8) });
  x.restore();
}

/* ============ 9 · la prova e la chiusura (101.1 – 111.5) ============ */
function sProof(t) {
  const a = 101.1, b = 106.5; if (t < a || t > b) return;
  chapTitle(t, a, b, 'STRESS TEST // 02.11.2026', 'LA PROVA', 'UNA MISSIONE SU TUTTI I NODI', AM);
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha *= e;
  vpanel(AM, t, a + .2);
  const N = [['M5', 'RESIN + LAYA', 1410, 250, CY], ['OMEN', 'CALCOLI', 1180, 500, GR], ['ASUS', 'QWENPUTER', 1640, 500, MG]];
  N.slice(1).forEach(([, , nx, ny, col], i) => {
    seg(1410, 250, nx, ny, { col, lw: 3, dash: [12, 10], off: -t * 80 });
    const u = (t * .8 + i * .4) % 1; circ(lerp(1410, nx, u), lerp(250, ny, u), 7, { fill: WH });
  });
  N.forEach(([n, s, nx, ny, col], i) => {
    const p = oBack(P(t, a + .5 + i * .4, a + .9 + i * .4)); if (p <= 0) return;
    x.save(); x.translate(nx, ny); x.scale(p, p); nodeBox(0, 0, n, col); x.restore();
    if (i === 0) T(s, nx + 118, ny + 8, { size: 22, col: NC.mid, a: clamp(p) });
    else T(s, nx, ny + 74, { size: 22, col: NC.mid, al: 'center', a: clamp(p) });
  });
  const tm = lerp(0, 1.56, oCub(P(t, a + 1.6, a + 3.6)));
  T(tm.toFixed(2).replace('.', ',') + ' s', 1410, 700, { w: 700, size: 96, fam: FD, col: tm >= 1.56 ? GR : WH, al: 'center', ls: -2 });
  x.restore();
}
function sClose(t) {
  const a = 106.5; if (t < a) return;
  const e = env(t, a, DUR, .4, .8);
  x.save(); x.globalAlpha *= e;
  speedLines(CO, 400, t, a, GR);
  slam('HYPERSPACE 1.06', CO, 420, 160, t, a, WH, { maxW: 1500 });
  T('RESIN · LAYA · QWENPUTER', CO, 520, { w: 700, size: 46, fam: FD, col: CY, al: 'center', ls: 6, a: P(t, a + .6, a + 1.1) });
  const cp = oBack(P(t, a + 1.2, a + 1.8));
  if (cp > 0) {
    const lb = 'os.zerozerocomputer.it', wd = measure(lb, 700, 44, FM) + 110;
    x.save(); x.translate(CO, 650); x.scale(cp, cp); x.fillStyle = GR; rrect(-wd / 2, -54, wd, 108, 20); x.fill();
    T(lb, 0, 15, { w: 700, size: 44, fam: FM, col: NC.bg, al: 'center' }); x.restore();
  }
  x.restore();
}

const REEL = {
  date: '02.11.2026',
  tagline: 'HyperSpace 1.06.',
  cta: 'os.zerozerocomputer.it',
  native: true,
  layers: { bg: netBg, intro: () => {}, outro: () => {}, hud: hudR, cuts: netCuts, fade: NC.bg },
  sc: BLK.slice(0, -1).map((s, i) => ({ a: s, b: BLK[i + 1], n: String(i).padStart(2, '0') })),
  cuts: [11.1, 22.0, 33.0, 43.8, 56.1, 67.0, 78.0, 90.2, 101.1, 106.5],
  scenes: [sOpen, sResinFlow, sResinSlab, sLayaRace, sLayaLang, sLayaGate, sQwChip, sQwClock, sQwSand, sProof, sClose, caption]
};
