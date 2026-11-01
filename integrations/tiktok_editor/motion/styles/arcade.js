// SPDX-License-Identifier: Apache-2.0
/* Stile «arcade» — libreria riusabile, estratta da reels/secops-2026-10-31.js.
   build.py la concatena dopo runtime.js quando un reel dichiara `// @meta {"styles": ["arcade", …]}`.
   Font pixel 5×7, sprite originali, testata stage(), HUD arcade, pavimento in prospettiva e glitch sui tagli.

   Tutto è scritto in coordinate parametriche su W/H (i reel verticali 1080×1920 rendono identici a prima;
   un reel 16:9 nativo usa gli stessi disegni su 1920×1080). Il ritmo è specifico del reel: le funzioni che
   ne hanno bisogno lo leggono dall'oggetto ARCADE, che il reel riempie (beatIdx, kick, drops, hud). */

const ARCADE = {
  C: { bg: '#030308', ink: '#E6FFF4', grn: '#39FF14', mag: '#FF2BD6', cyn: '#00F0FF', red: '#FF2A3D', yel: '#FFE600', dim: '#4A4F6A', grid: '#1A0F2E' },
  beatIdx: () => -1,                 // indice del beat corrente (dal reel)
  kick: () => 0,                     // 0..1, impulso del kick (dal reel)
  since: () => 9,                    // secondi dall'ultimo beat (dal reel)
  drops: [],                         // finestre dei drop [[a, b], …] per il lampo sui tagli
  hud: { tag: '00MESH', hi: '999999', footer: '00MESH', score: 250 }, // etichette dell'HUD arcade
};
const AC = ARCADE.C;
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
    ptext(s, X - d, Y, c, AC.cyn, { ...o, a: (o.a ?? 1) * .8 }); ptext(s, X + d, Y + d * .3, c, AC.mag, { ...o, a: (o.a ?? 1) * .8 });
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
const alien = (kind, cx, cy, c, col, t, a = 1) => sprite(SPR[kind][ARCADE.beatIdx(t) & 1], SW[kind], cx, cy, c, col, a);
const ship = (cx, cy, c, col, a = 1) => sprite(SHIP, 13, cx, cy, c, col, a);
function boom(cx, cy, t, t0, col = AC.yel) {
  const p = P(t, t0, t0 + .45); if (p <= 0 || p >= 1) return;
  for (let i = 0; i < 14; i++) {
    const g = i / 14 * Math.PI * 2 + hash(i + t0) * .5, r = 20 + p * (70 + hash(i * 3 + t0) * 60);
    x.fillStyle = i % 3 ? col : AC.ink; x.globalAlpha = 1 - p;
    x.fillRect(cx + Math.cos(g) * r - 5, cy + Math.sin(g) * r - 5, 10, 10);
  }
  x.globalAlpha = 1;
}
function tag(s, cx, cy, col, t) {
  const blink = Math.floor(t * 4) % 2 ? 1 : .55, wd = pwidth(s, 4) + 36;
  x.save(); x.globalAlpha *= blink; x.strokeStyle = col; x.lineWidth = 3; x.strokeRect(cx - wd / 2, cy - 22, wd, 44); x.restore();
  ptext(s, cx, cy - 14, 4, col, { al: 'center', a: blink });
}

/* intestazione di uno stage: numero, titolo pixel che entra in glitch, due righe di testo */
function stage(t, a, b, n, title, l1, l2, col = AC.grn, status = null) {
  const e = env(t, a, b, .12, .2);
  if (e <= 0) return;
  x.save(); x.globalAlpha *= e;
  ptext('STAGE ' + n, 80, 250, 5, AC.dim);
  const c = fitCell(title, W - 180, 15), d = 14 * (1 - P(t, a, a + .35)) + ARCADE.kick(t) * 7;
  const n2 = Math.ceil(plain(title).length * oCub(P(t, a, a + .3)));
  gtext(title.slice(0, n2), 80, 310, c, col, d);
  T(l1, 80, 310 + c * 7 + 70, { w: 700, size: 34, col: AC.ink, a: P(t, a + .3, a + .6) });
  if (l2) T(l2, 80, 310 + c * 7 + 118, { size: 28, col: AC.dim, a: P(t, a + .5, a + .8) });
  if (status) tag(status, W - 320, 268, AC.mag, t);
  x.restore();
}

/* ---------- livelli fissi: spazio, griglia, scossa, HUD arcade, scanline, glitch ---------- */
const STARS = Array.from({ length: 160 }, (_, i) => [hash(i) * W, hash(i + 500) * H, 1 + hash(i + 900) * 3]);
function spaceBg(t) {
  x.fillStyle = AC.bg; x.fillRect(0, 0, W, H);
  STARS.forEach(([sx, sy, z]) => { const y = (sy + t * z * 40) % H; x.fillStyle = z > 3 ? AC.ink : AC.dim; x.fillRect(sx, y, z, z * (1 + ARCADE.kick(t) * 4)); });
  // pavimento in prospettiva che scorre a tempo
  const hz = H * 0.8125, k = ARCADE.kick(t);
  x.save(); x.strokeStyle = AC.mag; x.globalAlpha = .28 + k * .4; x.lineWidth = 2; x.beginPath();
  for (let i = -12; i <= 12; i++) { x.moveTo(W / 2 + i * 40, hz); x.lineTo(W / 2 + i * 260, H); }
  const ph = (t * 1.6) % 1;
  for (let j = 0; j < 9; j++) { const y = hz + Math.pow((j + ph) / 9, 2.2) * 360; x.moveTo(0, y); x.lineTo(W, y); }
  x.stroke(); x.restore();
  const g = x.createLinearGradient(0, hz - 200, 0, hz); g.addColorStop(0, 'rgba(255,43,214,0)'); g.addColorStop(1, `rgba(255,43,214,${.12 + k * .25})`);
  x.fillStyle = g; x.fillRect(0, hz - 200, W, 200);
  // scossa sul kick: resta attiva per le scene (frame() riparte da una trasformazione pulita a ogni fotogramma)
  const s = k * 14, bi = ARCADE.beatIdx(t);
  x.translate((hash(bi) - .5) * s, (hash(bi + 77) - .5) * s);
}
function arcadeHud(t) {
  x.setTransform(1, 0, 0, 1, 0, 0);
  const a = P(t, .3, .9); if (a <= 0) return;
  x.save(); x.globalAlpha = a;
  const score = String(Math.max(0, ARCADE.beatIdx(t)) * ARCADE.hud.score).padStart(6, '0');
  ptext('1UP', 80, 110, 4, AC.red); ptext(score, 80, 150, 5, AC.ink);
  ptext('HI-SCORE', W / 2, 110, 4, AC.red, { al: 'center' }); ptext(ARCADE.hud.hi, W / 2, 150, 5, AC.ink, { al: 'center' });
  ptext(ARCADE.hud.tag, W - 80, 110, 4, AC.cyn, { al: 'right' });
  for (let i = 0; i < 3; i++) ship(W - 190 + i * 50, 168, 3, AC.grn);
  T(ARCADE.hud.footer, 80, H - 82, { size: 20, col: AC.dim, ls: 3 });
  x.fillStyle = AC.dim; x.fillRect(80, H - 62, W - 160, 4); x.fillStyle = AC.grn; x.fillRect(80, H - 62, (W - 160) * t / DUR, 4);
  x.restore();
  // scanline e vignettatura del monitor CRT
  x.save(); x.fillStyle = 'rgba(0,0,0,0.22)'; for (let y = 0; y < H; y += 4) x.fillRect(0, y, W, 2); x.restore();
  const v = x.createRadialGradient(W / 2, H / 2, 520, W / 2, H / 2, 1180);
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
  for (const [d] of ARCADE.drops) { const f = 1 - P(t, d, d + .25); if (t >= d && f > 0) { x.fillStyle = `rgba(255,255,255,${f * .85})`; x.fillRect(0, 0, W, H); } }
}
