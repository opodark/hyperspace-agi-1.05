// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "secops-2026-10-31", "title": "00MESH Reel Security Ops", "dur": 67, "aria": "Animazione di 67 secondi in stile arcade cyberpunk, nero e neon, con alieni in pixel art e musica techno: la parte di sicurezza di 00MESH. Strix per il pentest con agenti AI (in sviluppo), il Security Lab Kali con tre muri, la sandbox del codice senza rete, il canale cifrato fra i nodi e le chiavi divise in tre, le regole che chiedono conferma prima dei comandi distruttivi, lo scout isolato, il cancello MCP con token e limiti, il journal che annulla ogni passo e la mesh privata con il telefono come hub di riserva (in sviluppo). Chiusura su game over per gli intrusi e os.zerozerocomputer.it."}
/* Reel security sul brano «Interressante Wand» (172 BPM): i tempi vengono dai beat reali (librosa), in BT.
   Intro 0–11.17 · drop 1 11.17–33.58 (4 blocchi da 16 battute) · pausa 33.58–39.22 · drop 2 39.22–61.81 · chiusura 61.81–67.
   Alieni, nave e font pixel sono disegni originali. Le scene illustrano, non misurano. */

const N = { bg: '#030308', ink: '#E6FFF4', grn: '#39FF14', mag: '#FF2BD6', cyn: '#00F0FF', red: '#FF2A3D', yel: '#FFE600', dim: '#4A4F6A', grid: '#1A0F2E' };
const BT = [0.557,0.906,1.254,1.625,1.974,2.322,2.67,3.019,3.39,3.738,4.087,4.435,4.783,5.155,5.503,5.875,6.223,6.571,6.943,7.291,7.639,7.988,8.336,8.684,9.056,9.404,9.752,10.101,10.449,10.82,11.169,11.517,11.889,12.237,12.585,12.934,13.282,13.653,14.002,14.35,14.698,15.047,15.418,15.766,16.115,16.463,16.811,17.16,17.531,17.879,18.251,18.599,18.947,19.296,19.644,19.969,20.294,20.596,20.921,21.246,21.595,21.943,22.291,22.639,22.988,23.359,23.708,24.056,24.404,24.776,25.124,25.472,25.821,26.169,26.517,26.889,27.237,27.585,27.934,28.282,28.653,29.002,29.35,29.698,30.047,30.418,30.766,31.115,31.463,31.835,32.183,32.531,32.879,33.228,33.576,33.924,34.273,34.621,34.969,35.341,35.689,36.037,36.386,36.734,37.105,37.454,37.802,38.15,38.499,38.87,39.219,39.567,39.938,40.287,40.658,41.006,41.355,41.703,42.051,42.4,42.771,43.119,43.468,43.816,44.164,44.536,44.884,45.232,45.581,45.952,46.301,46.649,46.997,47.345,47.717,48.065,48.414,48.762,49.11,49.482,49.83,50.178,50.527,50.875,51.223,51.595,51.943,52.291,52.64,53.011,53.359,53.708,54.056,54.404,54.753,55.124,55.472,55.821,56.192,56.541,56.889,57.237,57.585,57.934,58.282,58.654,59.002,59.35,59.699,60.07,60.418,60.767,61.115,61.463,61.812,62.16,62.508,62.856,63.205,63.576,63.925,64.296,64.644,64.993,65.341,65.689,66.038,66.409,66.757,67.106];
const DROPS = [[11.169, 33.576], [39.219, 61.812]];

/* ---------- ritmo ---------- */
function beatIdx(t) { let i = -1; while (i + 1 < BT.length && BT[i + 1] <= t) i++; return i; }
const since = t => { const i = beatIdx(t); return i < 0 ? 9 : t - BT[i]; };
const inDrop = t => DROPS.some(([a, b]) => t >= a && t < b);
const energy = t => inDrop(t) ? 1 : t < 11.169 ? .15 + .5 * P(t, 2.6, 11.1) : .25;
const kick = t => Math.exp(-since(t) * 9) * energy(t);
const hash = n => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };

/* ---------- font pixel 5×7 ---------- */
const GL = {
  A: '.###.#...##...#######...##...##...#', B: '####.#...##...#####.#...##...#####.', C: '.###.#...##....#....#....#...#.###.',
  D: '####.#...##...##...##...##...#####.', E: '######....#....####.#....#....#####', F: '######....#....####.#....#....#....',
  G: '.###.#...##....#.####...##...#.####', H: '#...##...##...#######...##...##...#', I: '.###...#....#....#....#....#...###.',
  J: '..###...#....#....#....#.#..#..##..', K: '#...##..#.#.#..##...#.#..#..#.#...#', L: '#....#....#....#....#....#....#####',
  M: '#...###.###.#.##.#.##...##...##...#', N: '#...##...###..##.#.##..###...##...#', O: '.###.#...##...##...##...##...#.###.',
  P: '####.#...##...#####.#....#....#....', Q: '.###.#...##...##...##.#.##..#..##.#', R: '####.#...##...#####.#.#..#..#.#...#',
  S: '.#####....#.....###.....#....#####.', T: '#####..#....#....#....#....#....#..', U: '#...##...##...##...##...##...#.###.',
  V: '#...##...##...##...##...#.#.#...#..', W: '#...##...##...##.#.##.#.##.#.#.#.#.', X: '#...##...#.#.#...#...#.#.#...##...#',
  Y: '#...##...#.#.#...#....#....#....#..', Z: '#####....#...#...#...#...#....#####', 0: '.###.#...##..###.#.###..##...#.###.',
  1: '..#...##....#....#....#....#...###.', 2: '.###.#...#....#...#...#...#...#####', 3: '#####...#...#.....#.....##...#.###.',
  4: '...#...##..#.#.#..#.#####...#....#.', 5: '######....####.....#....##...#.###.', 6: '..##..#...#....####.#...##...#.###.',
  7: '#####....#...#...#...#....#....#...', 8: '.###.#...##...#.###.#...##...#.###.', 9: '.###.#...##...#.####....#...#..##..',
  ' ': '...................................', '.': '..........................##...##..', ':': '......##...##........##...##.......',
  '!': '..#....#....#....#....#.........#..', '?': '.###.#...#....#...#...#.........#..', '-': '...............#####...............',
  '/': '....#....#...#...#...#...#....#....', '+': '.......#....#..#####..#....#.......', '>': '.#.....#.....#.....#...#...#...#...',
  '<': '...#...#...#...#.....#.....#.....#.', '_': '..............................#####', ',': '.....................##....#...#...',
  '#': '.#.#..#.#.#####.#.#.#####.#.#..#.#.', '*': '......#.#...#..#####..#...#.#......'
};
const plain = s => s.toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const pwidth = (s, c) => (plain(s).length * 6 - 1) * c;
function ptext(s, X, Y, c, col, o = {}) {
  const { al = 'left', a = 1 } = o;
  if (a <= 0) return;
  s = plain(s);
  let px = al === 'center' ? X - pwidth(s, c) / 2 : al === 'right' ? X - pwidth(s, c) : X;
  x.save(); x.globalAlpha *= a; x.fillStyle = col;
  for (const ch of s) {
    const g = GL[ch] || GL['?'];
    for (let r = 0; r < 7; r++) for (let k = 0; k < 5; k++) if (g[r * 5 + k] === '#') x.fillRect(px + k * c, Y + r * c, c - (c > 5 ? 1 : 0), c - (c > 5 ? 1 : 0));
    px += 6 * c;
  }
  x.restore();
}
/* testo pixel con aberrazione cromatica: ciano e magenta sfasati, poi il colore pieno */
function gtext(s, X, Y, c, col, d, o = {}) {
  if (d > .5) {
    x.save(); x.globalCompositeOperation = 'lighter';
    ptext(s, X - d, Y, c, N.cyn, { ...o, a: (o.a ?? 1) * .8 }); ptext(s, X + d, Y + d * .3, c, N.mag, { ...o, a: (o.a ?? 1) * .8 });
    x.restore();
  }
  ptext(s, X, Y, c, col, o);
}
const fitCell = (s, maxW, maxC) => Math.max(2, Math.min(maxC, Math.floor(maxW / (plain(s).length * 6 - 1))));

/* ---------- sprite originali (due pose, cambiano sul beat) ---------- */
const SPR = {
  bug: ['#...###...#.#.#####.#...#######..###.###.###..#######...#.#####.#.#..#...#..#..#.....#..',
        '..#.###.#..#..#####..#..#######..###.###.###..#######..#.#.....#.#.#.......#.#.........#'],
  skull: ['.#######.###########..#..####..#..###########.###.###...#.#.#....#.#.#..', '.#######.###########..#..####..#..###########.###.###..#.#.#.#.#.#...#.#'],
  drone: ['...####....########.##.####.#####....######.##.#############.#.#..#.#.#........#', '...####....########.##.####.#####....######.##.#############..#.##.#...#......#.']
};
const SW = { bug: 11, skull: 9, drone: 10 };
const SHIP = '......#...........###..........###.......#.#####.#...###########.###############.##...##.##';
function sprite(bits, w, cx, cy, c, col, a = 1) {
  if (a <= 0) return;
  const h = bits.length / w, X = cx - w * c / 2, Y = cy - h * c / 2;
  x.save(); x.globalAlpha *= a; x.fillStyle = col;
  for (let i = 0; i < bits.length; i++) if (bits[i] === '#') x.fillRect(X + (i % w) * c, Y + Math.floor(i / w) * c, c, c);
  x.restore();
}
const alien = (kind, cx, cy, c, col, t, a = 1) => sprite(SPR[kind][beatIdx(t) & 1], SW[kind], cx, cy, c, col, a);
const ship = (cx, cy, c, col, a = 1) => sprite(SHIP, 13, cx, cy, c, col, a);
function boom(cx, cy, t, t0, col = N.yel) {
  const p = P(t, t0, t0 + .45); if (p <= 0 || p >= 1) return;
  for (let i = 0; i < 14; i++) {
    const g = i / 14 * Math.PI * 2 + hash(i + t0) * .5, r = 20 + p * (70 + hash(i * 3 + t0) * 60);
    x.fillStyle = i % 3 ? col : N.ink; x.globalAlpha = 1 - p;
    x.fillRect(cx + Math.cos(g) * r - 5, cy + Math.sin(g) * r - 5, 10, 10);
  }
  x.globalAlpha = 1;
}
function tag(s, cx, cy, col, t) {
  const blink = Math.floor(t * 4) % 2 ? 1 : .55, wd = pwidth(s, 4) + 36;
  x.save(); x.globalAlpha *= blink; x.strokeStyle = col; x.lineWidth = 3; x.strokeRect(cx - wd / 2, cy - 22, wd, 44); x.restore();
  ptext(s, cx, cy - 14, 4, col, { al: 'center', a: blink });
}

/* intestazione di ogni stage: numero, titolo pixel che entra in glitch, due righe di testo */
function stage(t, a, b, n, title, l1, l2, col = N.grn, status = null) {
  const e = env(t, a, b, .12, .2);
  if (e <= 0) return;
  x.save(); x.globalAlpha *= e;
  ptext('STAGE ' + n, 80, 250, 5, N.dim);
  const c = fitCell(title, 900, 15), d = 14 * (1 - P(t, a, a + .35)) + kick(t) * 7;
  const n2 = Math.ceil(plain(title).length * oCub(P(t, a, a + .3)));
  gtext(title.slice(0, n2), 80, 310, c, col, d);
  T(l1, 80, 310 + c * 7 + 70, { w: 700, size: 34, col: N.ink, a: P(t, a + .3, a + .6) });
  if (l2) T(l2, 80, 310 + c * 7 + 118, { size: 28, col: N.dim, a: P(t, a + .5, a + .8) });
  if (status) tag(status, 760, 268, N.mag, t);
  x.restore();
}

/* ---------- livelli fissi: spazio, griglia, scossa, HUD arcade, scanline, glitch ---------- */
const STARS = Array.from({ length: 160 }, (_, i) => [hash(i) * 1080, hash(i + 500) * 1920, 1 + hash(i + 900) * 3]);
function spaceBg(t) {
  x.fillStyle = N.bg; x.fillRect(0, 0, W, H);
  STARS.forEach(([sx, sy, z]) => { const y = (sy + t * z * 40) % 1920; x.fillStyle = z > 3 ? N.ink : N.dim; x.fillRect(sx, y, z, z * (1 + kick(t) * 4)); });
  // pavimento in prospettiva che scorre a tempo
  const hz = 1560, k = kick(t);
  x.save(); x.strokeStyle = N.mag; x.globalAlpha = .28 + k * .4; x.lineWidth = 2; x.beginPath();
  for (let i = -12; i <= 12; i++) { x.moveTo(540 + i * 40, hz); x.lineTo(540 + i * 260, 1920); }
  const ph = (t * 1.6) % 1;
  for (let j = 0; j < 9; j++) { const y = hz + Math.pow((j + ph) / 9, 2.2) * 360; x.moveTo(0, y); x.lineTo(W, y); }
  x.stroke(); x.restore();
  const g = x.createLinearGradient(0, hz - 200, 0, hz); g.addColorStop(0, 'rgba(255,43,214,0)'); g.addColorStop(1, `rgba(255,43,214,${.12 + k * .25})`);
  x.fillStyle = g; x.fillRect(0, hz - 200, W, 200);
  // scossa sul kick: resta attiva per le scene (frame() riparte da una trasformazione pulita a ogni fotogramma)
  const s = k * 14, bi = beatIdx(t);
  x.translate((hash(bi) - .5) * s, (hash(bi + 77) - .5) * s);
}
function arcadeHud(t) {
  x.setTransform(1, 0, 0, 1, 0, 0);
  const a = P(t, .3, .9); if (a <= 0) return;
  x.save(); x.globalAlpha = a;
  const score = String(Math.max(0, beatIdx(t)) * 250).padStart(6, '0');
  ptext('1UP', 80, 110, 4, N.red); ptext(score, 80, 150, 5, N.ink);
  ptext('HI-SCORE', 540, 110, 4, N.red, { al: 'center' }); ptext('999999', 540, 150, 5, N.ink, { al: 'center' });
  ptext('SEC-OPS', 1000, 110, 4, N.cyn, { al: 'right' });
  for (let i = 0; i < 3; i++) ship(890 + i * 50, 168, 3, N.grn);
  T('00MESH · SECURITY OPS · 31.10.2026', 80, 1838, { size: 20, col: N.dim, ls: 3 });
  x.fillStyle = N.dim; x.fillRect(80, 1858, 920, 4); x.fillStyle = N.grn; x.fillRect(80, 1858, 920 * t / DUR, 4);
  x.restore();
  // scanline e vignettatura del monitor CRT
  x.save(); x.fillStyle = 'rgba(0,0,0,0.22)'; for (let y = 0; y < H; y += 4) x.fillRect(0, y, W, 2); x.restore();
  const v = x.createRadialGradient(540, 960, 520, 540, 960, 1180);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.75)'); x.fillStyle = v; x.fillRect(0, 0, W, H);
}
function glitchCuts(t) {
  for (const c of REEL.cuts) {
    const p = P(t, c - .12, c + .18);
    if (p <= 0 || p >= 1) continue;
    const amt = Math.sin(p * Math.PI);
    for (let i = 0; i < 9; i++) {
      const y = Math.floor(hash(i + c * 10) * H), h = 20 + hash(i * 7 + c) * 120, off = (hash(i * 13 + c) - .5) * 260 * amt;
      x.drawImage(x.canvas, 0, y, W, h, off, y, W, h);
    }
    x.save(); x.globalCompositeOperation = 'lighter'; x.fillStyle = `rgba(0,240,255,${.12 * amt})`; x.fillRect(0, 0, W, H); x.restore();
  }
  // lampo bianco all'attacco dei drop
  for (const [d] of DROPS) { const f = 1 - P(t, d, d + .25); if (t >= d && f > 0) { x.fillStyle = `rgba(255,255,255,${f * .85})`; x.fillRect(0, 0, W, H); } }
}

/* ---------- 00 · intro: il perimetro, gli alieni in formazione, l'allarme (0 – 11.17s) ---------- */
const BOOT = ['> scansione del perimetro...', '> 4 nodi online · tailnet privata', '> livello minaccia: ████████'];
function boot(t) {
  if (t > 11.3) return;
  const out = 1 - P(t, 11.0, 11.2);
  x.save(); x.globalAlpha *= out;
  BOOT.forEach((s, i) => {
    const t0 = .6 + i * 1.4, n = Math.floor(s.length * P(t, t0, t0 + .9));
    T(s.slice(0, n) + (n < s.length && n > 0 && Math.floor(t * 8) % 2 ? '▌' : ''), 80, 300 + i * 52, { size: 30, col: i === 2 ? N.red : N.grn, a: 1 - P(t, 6.6, 7.0) });
  });
  // formazione: una fila per battuta di 4, passo laterale sui beat, discesa lenta
  const rows = ['skull', 'bug', 'bug', 'drone', 'drone'], starts = [2.67, 4.087, 5.503, 6.943, 8.336];
  const bi = Math.max(0, beatIdx(t)), step = (Math.floor(bi / 1) % 8 < 4 ? bi % 4 : 4 - bi % 4) * 18;
  const dy = P(t, 2.6, 11.1) * 120;
  rows.forEach((k, r) => {
    const ra = oCub(P(t, starts[r], starts[r] + .3)); if (ra <= 0) return;
    for (let cI = 0; cI < 7; cI++) alien(k, 200 + cI * 112 + step, 520 + r * 86 + dy, 6, [N.mag, N.cyn, N.cyn, N.grn, N.grn][r], t, ra);
  });
  // logo
  const la = P(t, 6.94, 7.3) * (1 - P(t, 9.6, 9.75));
  gtext('00MESH', 540, 1060 + dy * .2, 22, N.grn, 10 * (1 - P(t, 6.94, 7.4)) + kick(t) * 8, { al: 'center', a: la });
  ptext('SECURITY OPS', 540, 1250, 8, N.mag, { al: 'center', a: P(t, 7.64, 7.9) * (1 - P(t, 9.6, 9.75)) });
  // allarme sull'ultima battuta
  if (t >= 9.752) {
    const on = since(t) < .2;
    if (on) { x.fillStyle = 'rgba(255,42,61,0.18)'; x.fillRect(0, 0, W, H); }
    gtext('WARNING', 540, 1040, 20, N.red, on ? 12 : 3, { al: 'center', a: on ? 1 : .55 });
    ptext('INTRUSI IN AVVICINAMENTO', 540, 1230, 6, N.yel, { al: 'center' });
  }
  ship(540, 1470, 8, N.grn, P(t, 1.25, 1.6));
  x.restore();
}

/* ---------- 01 · Strix: la nave abbatte le vulnerabilità (11.17 – 16.81s) ---------- */
const VULNS = ['SQLI', 'XSS', 'SSRF', 'IDOR', 'RCE'];
function strix(t) {
  const a = 11.169, b = 16.811;
  if (t < a || t > b) return;
  stage(t, a, b, '01', 'STRIX', 'pentest con agenti AI', 'in sandbox Docker · solo bersagli autorizzati', N.grn, 'IN SVILUPPO');
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  const sway = Math.sin(t * 2.2) * 40;
  VULNS.forEach((v, i) => {
    const vx = 170 + i * 185 + sway, vy = 900, hit = BT[32 + i * 3];
    if (t < hit) { alien('bug', vx, vy, 7, N.mag, t); ptext(v, vx, vy + 50, 4, N.ink, { al: 'center' }); }
    else ptext(v, vx, vy + 50, 4, N.yel, { al: 'center', a: 1 - P(t, hit + 2.4, hit + 2.8) });
    boom(vx, vy, t, hit);
    // colpo: parte due battute prima e arriva sul beat
    const s0 = hit - .34, sp = P(t, s0, hit);
    if (sp > 0 && sp < 1) { x.fillStyle = N.grn; x.fillRect(vx - 4, lerp(1380, vy, sp), 8, 34); }
  });
  const target = VULNS.findIndex((_, i) => t < BT[32 + i * 3]);
  const sx = target < 0 ? 540 : 170 + target * 185 + sway;
  ship(sx, 1420, 9, N.grn);
  T(t > BT[44] ? '→ report per il cliente' : '', 80, 1560, { w: 700, size: 32, col: N.yel });
  x.restore();
}

/* ---------- 02 · Security Lab: tre bunker che reggono (16.81 – 22.29s) ---------- */
const WALLS = ['TARGET IN LISTA', 'SOLO 3 TOOL', 'ARGV + LIMITI'];
const BUNK = '...##########.....############...##############.#####################################################################......#########........####';
function lab(t) {
  const a = 16.811, b = 22.291;
  if (t < a || t > b) return;
  stage(t, a, b, '02', 'SECURITY LAB', 'Kali: nmap · nikto · gobuster', 'tre muri, e senza bersaglio dichiarato non parte', N.cyn);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  for (let i = 0; i < 6; i++) alien('skull', 160 + i * 150 + Math.sin(t * 3) * 30, 860, 6, N.red, t);
  WALLS.forEach((wl, k) => {
    const bx = 200 + k * 340, by = 1250, c = 9, w = 16;
    // fori: ogni colpo arrivato toglie un blocchetto, ma il muro regge
    const hits = BT.filter((bt, i) => i >= 48 && i < 62 && i % 3 === k && bt <= t).length;
    for (let i = 0; i < BUNK.length; i++) {
      if (BUNK[i] !== '#') continue;
      const hole = Math.floor(hash(i * 3 + k) * 40) < hits * 3 && Math.floor(i / w) < 4;
      if (!hole) { x.fillStyle = N.cyn; x.fillRect(bx - w * c / 2 + (i % w) * c, by + Math.floor(i / w) * c, c - 1, c - 1); }
    }
    ptext(wl, bx, by + 120, 3, N.ink, { al: 'center' });
    BT.forEach((bt, i) => {
      if (i < 47 || i >= 62 || i % 3 !== k) return;
      const p = P(t, bt - .3, bt);
      if (p > 0 && p < 1) { x.fillStyle = N.red; x.fillRect(bx - 4 + Math.sin(i) * 30, lerp(900, by, p), 8, 24); }
      boom(bx + Math.sin(i) * 30, by, t, bt, N.red);
    });
  });
  T('host protetto', 540, 1510, { w: 700, size: 30, col: N.grn, al: 'center', a: P(t, 18.6, 19.0) });
  x.restore();
}

/* ---------- 03 · Code sandbox: il drone rimbalza nella gabbia (22.29 – 27.93s) ---------- */
const CAGE = ['RETE: OFF', 'ROOT: SOLA LETTURA', 'DOCKER SOCKET: NO', 'UTENTE: NON-ROOT', 'CPU/RAM/PID: LIMITATI'];
function sandbox(t) {
  const a = 22.291, b = 27.934;
  if (t < a || t > b) return;
  stage(t, a, b, '03', 'SANDBOX', 'il codice gira in gabbia', 'esce solo un diff, e lo rivede una persona', N.yel);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  const X0c = 100, Y0c = 800, Wc = 520, Hc = 520;
  x.strokeStyle = N.yel; x.lineWidth = 6; x.setLineDash([18, 10]); x.lineDashOffset = -t * 60; x.strokeRect(X0c, Y0c, Wc, Hc); x.setLineDash([]);
  for (let i = 1; i < 6; i++) { x.fillStyle = 'rgba(255,230,0,0.25)'; x.fillRect(X0c + i * Wc / 6 - 2, Y0c, 4, Hc); }
  // rimbalzo deterministico (triangolare) nella gabbia
  const tri = (v, m) => { const q = ((v % (2 * m)) + 2 * m) % (2 * m); return q < m ? q : 2 * m - q; };
  const m = 70, bx = X0c + m + tri((t - a) * 520, Wc - 2 * m), by = Y0c + m + tri((t - a) * 380 + 90, Hc - 2 * m);
  alien('drone', bx, by, 8, N.red, t);
  const nearWall = Math.min(bx - X0c - m, X0c + Wc - m - bx, by - Y0c - m, Y0c + Hc - m - by) < 14;
  if (nearWall) { x.strokeStyle = N.red; x.lineWidth = 10; x.strokeRect(X0c, Y0c, Wc, Hc); }
  CAGE.forEach((s, i) => {
    const t0 = BT[63 + i * 2], p = P(t, t0, t0 + .15);
    if (p <= 0) return;
    T('[OK]', 660, 860 + i * 100, { w: 700, size: 26, col: N.grn, a: p });
    T(s, 660, 896 + i * 100, { size: 24, col: N.ink, a: p });
  });
  x.restore();
}

/* ---------- 04 · Canale cifrato e chiave divisa (27.93 – 33.58s) ---------- */
function crypto(t) {
  const a = 27.934, b = 33.576;
  if (t < a || t > b) return;
  stage(t, a, b, '04', 'CRYPTO', 'ECDH secp256k1 · AES-256-GCM', 'forward secrecy · anti-replay 120 s', N.mag);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  const L = [170, 1000], R = [910, 1000];
  ship(L[0], L[1], 7, N.grn); ship(R[0], R[1], 7, N.grn);
  ptext('M5', L[0], L[1] + 50, 4, N.ink, { al: 'center' }); ptext('OMEN', R[0], R[1] + 50, 4, N.ink, { al: 'center' });
  x.strokeStyle = N.dim; x.lineWidth = 3; x.setLineDash([10, 12]); x.beginPath(); x.moveTo(L[0] + 60, L[1]); x.lineTo(R[0] - 60, R[1]); x.stroke(); x.setLineDash([]);
  alien('skull', 540, 880, 6, N.red, t);
  ptext('INTERCETTA:', 540, 760, 4, N.red, { al: 'center' });
  for (let i = 0; i < 8; i++) {
    const t0 = BT[79 + i * 2], p = P(t, t0, t0 + .6);
    if (p <= 0 || p >= 1) continue;
    const px = lerp(L[0] + 60, R[0] - 60, p);
    x.fillStyle = N.mag; x.fillRect(px - 16, L[1] - 16, 32, 32); x.fillStyle = N.bg; x.fillRect(px - 8, L[1] - 4, 16, 14);
    x.strokeStyle = N.bg; x.lineWidth = 4; x.beginPath(); x.arc(px, L[1] - 6, 7, Math.PI, 0); x.stroke();
  }
  const hex = Array.from({ length: 8 }, (_, i) => Math.floor(hash(beatIdx(t) * 9 + i) * 256).toString(16).toUpperCase().padStart(2, '0')).join(' ');
  T(hex, 540, 960, { size: 24, col: N.red, al: 'center', a: P(t, 28.3, 28.6) });
  // spore: chiave in tre pezzi, ne bastano due
  const sa = P(t, BT[88], BT[88] + .2);
  T('chiave madre divisa in 3 · ne bastano 2 (Shamir)', 80, 1240, { w: 700, size: 28, col: N.ink, a: sa });
  ['FONDATORE', 'SOCIO', 'CARTA'].forEach((s, i) => {
    const t0 = BT[89 + i * 2], p = oBack(P(t, t0, t0 + .25));
    if (p <= 0) return;
    const cx = 230 + i * 310, cy = 1360;
    x.save(); x.translate(cx, cy); x.scale(p, p);
    x.fillStyle = i < 2 ? N.yel : N.dim; x.fillRect(-90, -30, 120, 60); x.fillRect(30, -10, 70, 20); x.fillRect(80, 10, 12, 20);
    x.restore();
    ptext(s, cx, cy + 50, 3, N.ink, { al: 'center', a: p });
  });
  if (t > BT[92]) ptext('2/3 OK', 540, 1470, 6, N.grn, { al: 'center', a: Math.floor(t * 6) % 2 ? 1 : .6 });
  x.restore();
}

/* ---------- pausa · regole: prima di distruggere si chiede (33.58 – 39.22s) ---------- */
const CMDS = [['git status', 'LETTURA', 'PASSA', N.grn], ['git commit -m fix', 'SCRITTURA', 'PASSA', N.grn],
  ['git push --force', 'DISTRUTTIVO', 'CHIEDE CONFERMA', N.yel], ['rm -rf ./build', 'DISTRUTTIVO', 'CHIEDE CONFERMA', N.yel],
  ['dd of=/dev/sda', 'DISTRUTTIVO', 'CHIEDE CONFERMA', N.yel]];
function rules(t) {
  const a = 33.576, b = 39.219;
  if (t < a || t > b) return;
  stage(t, a, b, '--', 'REGOLE', 'shell policy · mutation guard', 'ogni comando ha un rischio, ogni modifica è una proposta', N.yel);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  x.fillStyle = 'rgba(10,12,24,0.9)'; x.fillRect(70, 760, 940, 640); x.strokeStyle = N.dim; x.lineWidth = 3; x.strokeRect(70, 760, 940, 640);
  T('hostctl · verdetto prima di eseguire', 100, 806, { size: 22, col: N.dim });
  CMDS.forEach(([c, r, v, col], i) => {
    const t0 = BT[96 + i * 2], n = Math.floor(('$ ' + c).length * P(t, t0, t0 + .3));
    if (n <= 0) return;
    const y = 880 + i * 104;
    T(('$ ' + c).slice(0, n), 100, y, { size: 30, col: N.ink });
    if (t > t0 + .35) { T(r, 100, y + 40, { size: 22, col: N.dim }); T('→ ' + v, 980, y + 40, { w: 700, size: 24, col, al: 'right' }); }
  });
  // costruzione verso il drop 2: LIVELLO 2 che lampeggia sull'ultima battuta
  if (t > 37.802) gtext('LIVELLO 2', 540, 1480, 10, N.mag, since(t) < .15 ? 10 : 2, { al: 'center', a: since(t) < .2 ? 1 : .5 });
  x.restore();
}

/* ---------- 05 · Scout: corridoio con barriere (39.22 – 44.88s) ---------- */
const ZONES = [['LAN', 330], ['TAILNET', 560], ['LOCALHOST', 790], ['LOGIN', 1020]];
function scout(t) {
  const a = 39.219, b = 44.884;
  if (t < a || t > b) return;
  stage(t, a, b, '05', 'SCOUT', 'legge il web di notte', 'profilo usa e getta · niente login · niente moduli', N.cyn);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  ZONES.forEach(([s, zy], i) => {
    const y = 760 + i * 150, bump = since(t) < .12 && beatIdx(t) % 4 === i ? 1 : 0;
    x.fillStyle = `rgba(255,42,61,${.25 + bump * .5})`; x.fillRect(560, y, 420, 90);
    x.strokeStyle = N.red; x.lineWidth = 3; x.strokeRect(560, y, 420, 90);
    ptext(s, 770, y + 30, 4, N.red, { al: 'center' }); ptext('X', 960, y + 30, 4, N.red, { al: 'right' });
  });
  // la nave dello scout prova le barriere e rimbalza, poi va sulla pagina pubblica
  const k = Math.max(0, beatIdx(t) - 111), lane = k % 4, ph = since(t);
  const sx = 200 + Math.sin(Math.min(ph, .3) / .3 * Math.PI) * 280, sy = 805 + lane * 150;
  if (t < BT[121]) ship(sx, sy, 6, N.cyn);
  else {
    const p = oCub(P(t, BT[121], BT[121] + .5));
    ship(lerp(200, 540, p), lerp(1350, 1460, p), 6, N.cyn);
    x.strokeStyle = N.cyn; x.lineWidth = 4; x.strokeRect(660, 1400, 260, 130);
    T('pagina pubblica', 790, 1480, { size: 24, col: N.cyn, al: 'center' });
    if (t > BT[123]) ptext('UNTRUSTED', 790, 1560, 4, N.yel, { al: 'center' });
  }
  x.restore();
}

/* ---------- 06 · Il cancello di /mcp (44.88 – 50.53s) ---------- */
function gate(t) {
  const a = 44.884, b = 50.527;
  if (t < a || t > b) return;
  stage(t, a, b, '06', 'GATE', '/mcp: senza token non entra nessuno', 'allowlist dei tool · token bucket · circuit breaker', N.grn);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  const gy = 1260;
  x.fillStyle = N.grn; x.fillRect(80, gy, 340, 14); x.fillRect(560, gy, 340, 14);
  ptext('TOKEN', 490, gy - 6, 3, N.grn, { al: 'center' });
  // ondata: un alieno per beat scende verso il cancello
  for (let i = 127; i < 143; i++) {
    const t0 = BT[i], p = P(t, t0 - .7, t0);
    if (t < t0 - .7) continue;
    const ok = i % 5 === 0, lx = 140 + (i * 137) % 700;
    if (t < t0) alien(ok ? 'drone' : 'bug', lerp(lx, ok ? 490 : lx, p), lerp(780, gy - 40, p), 5, ok ? N.grn : N.mag, t);
    else if (ok) alien('drone', 490, lerp(gy + 60, gy + 200, P(t, t0, t0 + .5)), 5, N.grn, t, 1 - P(t, t0 + .4, t0 + .6));
    else { boom(lx, gy - 40, t, t0, N.mag); if (t < t0 + .5) ptext(i % 3 ? '401' : '429', lx, gy - 110, 4, N.red, { al: 'center', a: 1 - P(t, t0 + .3, t0 + .5) }); }
  }
  // secchio dei token: si svuota a ogni richiesta e si riempie piano
  const used = BT.filter((bt, i) => i >= 127 && i < 143 && bt <= t).length, lvl = clamp(1 - used * .09 + (t - a) * .06);
  x.strokeStyle = N.ink; x.lineWidth = 3; x.strokeRect(940, 800, 60, 360);
  x.fillStyle = lvl < .25 ? N.red : N.yel; x.fillRect(944, 804 + 352 * (1 - lvl), 52, 352 * lvl);
  T('bucket', 970, 1200, { size: 20, col: N.dim, al: 'center' });
  const open = t > BT[140];
  T(open ? 'BREAKER: OPEN' : 'BREAKER: CLOSED', 80, 1380, { w: 700, size: 28, col: open ? N.red : N.grn });
  x.restore();
}

/* ---------- 07 · Ctrl+Z: distrutto e riavvolto (50.53 – 56.19s) ---------- */
const JOURNAL = ['#041 scrive config', '#042 riavvia servizio', '#043 errore', '#044 ROLLBACK'];
function undo(t) {
  const a = 50.527, b = 56.192;
  if (t < a || t > b) return;
  stage(t, a, b, '07', 'CTRL+Z', 'ogni passo scritto nel journal', 'e ogni passo si può annullare', N.yel);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  // danno fino a 53.0, riavvolgimento 53.36 → 55.1
  const dmg = P(t, 51.0, 53.0) - P(t, 53.36, 55.1), rew = t > 53.36 && t < 55.1;
  for (let i = 0; i < 6; i++) for (let j = 0; j < 5; j++) {
    const id = i * 5 + j, gone = hash(id) < dmg * 1.05, fall = gone ? dmg * 300 * hash(id + 3) : 0;
    x.fillStyle = rew ? N.cyn : N.grn; x.globalAlpha = gone ? Math.max(0, 1 - dmg) : 1;
    x.fillRect(110 + i * 72, 1060 + j * 60 + fall, 64, 52);
  }
  x.globalAlpha = 1;
  if (t < 53.0) alien('skull', 320 + Math.sin(t * 5) * 140, 860, 7, N.red, t);
  if (rew) {
    ptext('<< REWIND', 330, 880, 7, N.cyn, { al: 'center', a: Math.floor(t * 6) % 2 ? 1 : .5 });
    for (let k = 0; k < 6; k++) { const y = (t * 900 + k * 260) % 700 + 780; x.fillStyle = 'rgba(0,240,255,0.25)'; x.fillRect(80, y, 520, 6); }
  }
  if (t > 55.1) ptext('RIPRISTINATO', 330, 880, 5, N.grn, { al: 'center' });
  JOURNAL.forEach((s, i) => {
    const t0 = [51.0, 51.95, 52.64, 53.36][i];
    if (t < t0) return;
    T(s, 640, 1080 + i * 64, { w: i === 3 ? 700 : 400, size: 26, col: i === 2 ? N.red : i === 3 ? N.cyn : N.ink });
  });
  T('traccia NDJSON · replay', 640, 1360, { size: 22, col: N.dim, a: P(t, 53.4, 53.8) });
  x.restore();
}

/* ---------- 08 · La mesh e l'hub di riserva in tasca (56.19 – 61.81s) ---------- */
const NODES = [['M5', 'HUB', 300, 960], ['OMEN', 'SEMPRE ACCESO', 780, 960], ['ASUS', 'SOLARE', 300, 1340], ['S24', 'POCKET HUB', 780, 1340]];
function meshSc(t) {
  const a = 56.192, b = 61.812;
  if (t < a || t > b) return;
  const fail = t > 58.282, promo = t > 59.35;
  stage(t, a, b, '08', 'LA MESH', 'Tailscale: dentro solo i nostri nodi', 'se cade l’hub, il telefono prende il posto', N.grn, promo ? 'IN SVILUPPO' : null);
  const e = env(t, a, b, .12, .2);
  x.save(); x.globalAlpha *= e;
  const hub = promo ? 3 : 0;
  NODES.forEach(([, , nx, ny], i) => {
    if (i === hub || (fail && i === 0)) return;
    const [, , hx, hy] = NODES[hub];
    x.strokeStyle = promo ? N.mag : N.grn; x.lineWidth = 3; x.setLineDash([12, 10]); x.lineDashOffset = -t * 80;
    x.beginPath(); x.moveTo(nx, ny); x.lineTo(hx, hy); x.stroke(); x.setLineDash([]);
    const u = (t * .9 + i * .3) % 1; x.fillStyle = N.yel; x.fillRect(lerp(nx, hx, u) - 6, lerp(ny, hy, u) - 6, 12, 12);
  });
  NODES.forEach(([n, sub, nx, ny], i) => {
    const dead = fail && i === 0, isHub = i === hub;
    ship(nx, ny, 9, dead ? N.dim : isHub ? N.mag : N.grn);
    if (isHub) ring(nx, ny, 90 + since(t) * 80, { col: N.mag, lw: 4, a: 1 - since(t) * 2 });
    ptext(n, nx, ny + 60, 5, dead ? N.dim : N.ink, { al: 'center' });
    T(dead ? 'GIÙ' : sub, nx, ny + 130, { w: 700, size: 22, col: dead ? N.red : N.dim, al: 'center' });
  });
  if (fail && !promo) gtext('HUB DOWN', 540, 1500, 7, N.red, 6, { al: 'center' });
  x.restore();
}

/* ---------- chiusura · game over per gli intrusi (61.81 – 67s) ---------- */
function gameOver(t) {
  const a = 61.812;
  if (t < a) return;
  const e = oCub(P(t, a, a + .2));
  x.save(); x.globalAlpha *= e;
  const go = 1 - P(t, 63.8, 64.0);
  gtext('GAME', 540, 640, 22, N.red, 12 * (1 - P(t, a, a + .5)) + kick(t) * 6, { al: 'center', a: go });
  gtext('OVER', 540, 820, 22, N.red, 12 * (1 - P(t, a + .1, a + .6)) + kick(t) * 6, { al: 'center', a: go });
  T('per gli intrusi.', 540, 1080, { w: 700, size: 40, col: N.ink, al: 'center', a: P(t, 62.5, 62.8) * go });
  const la = P(t, 63.925, 64.2);
  gtext('00MESH', 540, 640, 22, N.grn, 8 * (1 - P(t, 63.925, 64.4)) + kick(t) * 4, { al: 'center', a: la });
  T('documentato · reversibile · locale', 540, 880, { w: 700, size: 34, col: N.ink, al: 'center', a: P(t, 64.3, 64.6) });
  const cp = oBack(P(t, 64.65, 65.0));
  if (cp > 0) {
    const lb = 'os.zerozerocomputer.it', wd = measure(lb, 700, 34, FM) + 80;
    x.save(); x.translate(540, 1010); x.scale(cp, cp); x.fillStyle = N.grn; x.fillRect(-wd / 2, -44, wd, 88);
    T(lb, 0, 12, { w: 700, size: 34, col: N.bg, al: 'center' }); x.restore();
  }
  T('pentest solo su sistemi propri o autorizzati', 540, 1130, { size: 22, col: N.dim, al: 'center', a: P(t, 65.0, 65.3) });
  if (t > 64.0) ptext('INSERT COIN', 540, 1300, 6, N.yel, { al: 'center', a: Math.floor(t * 3) % 2 ? 1 : .2 });
  x.restore();
}

const REEL = {
  date: '31.10.2026',
  tagline: 'Game over per gli intrusi.',
  cta: 'os.zerozerocomputer.it',
  sc: [{ a: 11.169, b: 16.811, n: '01' }, { a: 16.811, b: 22.291, n: '02' }, { a: 22.291, b: 27.934, n: '03' }, { a: 27.934, b: 33.576, n: '04' },
    { a: 39.219, b: 44.884, n: '05' }, { a: 44.884, b: 50.527, n: '06' }, { a: 50.527, b: 56.192, n: '07' }, { a: 56.192, b: 61.812, n: '08' }],
  cuts: [11.169, 16.811, 22.291, 27.934, 33.576, 39.219, 44.884, 50.527, 56.192, 61.812],
  layers: { bg: spaceBg, intro: () => {}, outro: () => {}, hud: arcadeHud, cuts: glitchCuts, fade: N.bg },
  scenes: [boot, strix, lab, sandbox, crypto, rules, scout, gate, undo, meshSc, gameOver]
};
