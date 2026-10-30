// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "youtube-presentazione-2026-10-30", "title": "L'assistente che lavora di notte", "aria": "Video orizzontale di circa quattro minuti e mezzo in stile anni cinquanta a spigoli: un assistente che gira sui computer dell'attività, di notte prepara bozze che il titolare rivede e approva, con schermate reali del sistema, sette esempi d'uso (bottega, studio commercialista, artigiani, ristorante, studio medico, palestra, gommista) e la presentazione di come si lavora su misura.", "dur": 264.5, "formats": ["16:9"], "assets": {"analytics": "data/youtube-assets/screens/ritagli/analytics-stato.png", "seo": "data/youtube-assets/screens/ritagli/seo-punteggio.png", "radar": "data/youtube-assets/screens/ritagli/missions-radar.png", "sched": "data/youtube-assets/screens/ritagli/missions-scheduler.png"}, "voice": [{"file": "data/reels/youtube-audio/00-gancio.wav", "at": 1.0}, {"file": "data/reels/youtube-audio/01-problema.wav", "at": 16.6}, {"file": "data/reels/youtube-audio/02-come-funziona.wav", "at": 35.0}, {"file": "data/reels/youtube-audio/03-cosa-sa-fare.wav", "at": 68.4}, {"file": "data/reels/youtube-audio/05-come-lavoriamo.wav", "at": 238.0}, {"file": "data/reels/youtube-audio/06-chiusura.wav", "at": 255.0}]}
/* Video YouTube (16:9 nativo). Voce clonata registrata (testi in integrations/moneyprinter/testi/youtube/); i tempi delle
   frasi vengono dalle pause del parlato di ogni capitolo. Il capitolo dei casi d'uso e le schermate non hanno voce: musica
   e didascalie. Offset dei capitoli = "at" in @meta (tenerli uguali a OFF qui sotto: li usa mix_youtube.py per l'audio).
   Nomi, scadenze, prezzi e differenze nelle scene sono di fantasia; le schermate sono ritagli reali di data/youtube-assets/. */

const CR = '#F1E6CF', CR2 = '#E4D5B3', INK = '#1E1B18', RED = '#D9442C', MUS = '#E0A526', TEA = '#1F6E6B', SKY = '#7FA7B5', SKIN = '#E9B58E';
const OFF = { g: 1.0, p: 16.6, c: 35.0, s: 68.4, scr: 109.8, uc: 132.4, l: 238.0, x: 255.0 };
const CASE_DUR = 15;

const rnd = seed => { let s = seed >>> 0; return () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296; };
const PAPER = (() => {
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  g.fillStyle = CR; g.fillRect(0, 0, W, H);
  const r = rnd(7);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(30,27,24,${.03 + r() * .07})`; g.fillRect(r() * W, r() * H, 1 + r() * 2.5, 1 + r() * 2.5); }
  for (let gy = 0; gy < 14; gy++) for (let gx = 0; gx < 26; gx++) { // retino rosso in basso a destra
    const d = (gx / 26) * (gy / 14); g.fillStyle = 'rgba(217,68,44,.15)'; g.beginPath(); g.arc(W - 26 * 22 + gx * 22 + (gy % 2) * 11, H - 14 * 22 + gy * 22, d * 8, 0, 6.3); g.fill();
  }
  const gr = g.createRadialGradient(W / 2, H / 2, H * .45, W / 2, H / 2, H * .95); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(90,60,20,.22)');
  g.fillStyle = gr; g.fillRect(0, 0, W, H);
  return c;
})();

/* ---------- primitive a spigoli: riempimento fuori registro + contorno a matita doppio ---------- */
function stroke(pts, closed, lw = 3.5, col = INK) {
  x.save(); x.strokeStyle = col; x.lineWidth = lw; x.lineJoin = 'round'; x.lineCap = 'round';
  for (let k = 0; k < 2; k++) {
    x.globalAlpha *= k ? .55 : 1; x.beginPath();
    pts.forEach(([px, py], i) => { const jx = k * Math.sin(i * 12.9 + 1) * 1.8, jy = k * Math.cos(i * 7.7 + 2) * 1.8; i ? x.lineTo(px + jx, py + jy) : x.moveTo(px + jx, py + jy); });
    if (closed) x.closePath(); x.stroke();
  }
  x.restore();
}
function poly(pts, fill, o = {}) {
  const { ox = 5, oy = 4, lw = 3.5, line = INK, a = 1 } = o;
  x.save(); x.globalAlpha *= a;
  if (fill) { x.beginPath(); pts.forEach(([px, py], i) => i ? x.lineTo(px + ox, py + oy) : x.moveTo(px + ox, py + oy)); x.closePath(); x.fillStyle = fill; x.fill(); }
  if (line) stroke(pts, true, lw, line);
  x.restore();
}
const box = (X, Y, w, h, fill, o) => poly([[X, Y], [X + w, Y], [X + w, Y + h], [X, Y + h]], fill, o);
const ln = (x1, y1, x2, y2, lw = 4, col = INK) => stroke([[x1, y1], [x2, y2]], false, lw, col);
const dia = (cx, cy, r, fill, o) => poly([[cx, cy - r], [cx + r, cy], [cx, cy + r], [cx - r, cy]], fill, o);
const oct = (cx, cy, r, fill, o) => poly([...Array(8)].map((_, i) => [cx + Math.cos(i * .785 + .39) * r, cy + Math.sin(i * .785 + .39) * r]), fill, o);
const TX = (s, X, Y, o = {}) => T(s, X, Y, { w: 900, size: 40, fam: FD, col: INK, ...o });
const MO = (s, X, Y, o = {}) => T(s, X, Y, { w: 700, size: 22, fam: FM, col: INK, ...o });
const pop = (t, t0, d = .35) => oBack(P(t, t0, t0 + d));
const fade = (t, a, b, d = .25) => clamp(Math.min((t - a) / d, (b - t) / d));
function at(X, Y, s, fn) { if (s <= 0) return; x.save(); x.translate(X, Y); x.scale(s, s); fn(); x.restore(); }
function chip(X, Y, label, fill, col = INK, size = 26, a = 1) {
  const w = measure(label, 700, size, FM, 1) + 44; x.save(); x.globalAlpha *= a;
  box(X, Y - size - 10, w, size + 28, fill, { ox: 3, oy: 3, lw: 3 }); MO(label, X + 22, Y + 2, { size, col, ls: 1 }); x.restore(); return w;
}
function shot(name, X, Y, w, a = 1) {
  const im = IMGS[name]; if (!im) return 0; const h = w * im.height / im.width;
  x.save(); x.globalAlpha *= a; box(X - 14, Y - 14, w + 28, h + 28, INK, { ox: 10, oy: 9, line: INK });
  x.fillStyle = CR; x.fillRect(X - 14, Y - 14, w + 28, h + 28); x.drawImage(im, X, Y, w, h);
  stroke([[X - 14, Y - 14], [X + w + 14, Y - 14], [X + w + 14, Y + h + 14], [X - 14, Y + h + 14]], true, 3, INK); x.restore(); return h;
}
/* titolo grande che cambia a ogni frase: items = [[inizio, fine, testo, colore?]] (testo su una o due righe separate da '|') */
function headline(t, items, X = 96, Y = 190, size = 84, maxW = 1700) {
  items.forEach(([a, b, s, col]) => {
    if (t < a || t > b) return; const e = fade(t, a, b, .3), lines = s.split('|');
    let sz = size; lines.forEach(l => { const w = measure(l, 900, sz, FD, -2); if (w > maxW) sz = Math.min(sz, sz * maxW / w); });
    lines.forEach((l, i) => TX(l, X + (1 - oCub(P(t, a, a + .35))) * -50, Y + i * sz * 1.08, { size: sz, col: col || INK, a: e, ls: -2 }));
  });
}

/* ---------- il titolare (figura a spigoli) ---------- */
function persona(cx, cy, s, mood, t, o = {}) {
  const { tie = false } = o;
  x.save(); x.translate(cx, cy); x.scale(s, s);
  x.translate(mood === 'stress' ? Math.sin(t * 30) * 3 : 0, Math.sin(t * 2) * 2);
  const stress = mood === 'stress', happy = mood === 'happy', sleep = mood === 'sleep';
  const lh = stress ? [-100 + Math.sin(t * 25) * 12, 20 + Math.cos(t * 21) * 12] : [-92, 130];
  const rh = stress ? [100 + Math.cos(t * 23) * 12, 16 + Math.sin(t * 19) * 12] : happy ? [96, -10 + Math.sin(t * 5) * 6] : [92, 130];
  if (!sleep) { ln(-56, 80, lh[0], lh[1], 30, TEA); ln(56, 80, rh[0], rh[1], 30, TEA); dia(lh[0], lh[1], 20, SKIN); dia(rh[0], rh[1], 20, SKIN); }
  poly([[-58, 50], [58, 50], [78, 210], [-78, 210]], TEA);
  poly([[-22, 50], [22, 50], [0, 98]], CR, { ox: 2, oy: 2 });
  poly([[-36, 124], [36, 124], [32, 210], [-32, 210]], CR2, { ox: 2, oy: 2 });
  if (tie) poly([[-26, 62], [26, 62], [-26, 92], [26, 92]], RED, { ox: 2, oy: 2 });
  oct(0, 0, 56, SKIN);
  poly([[-56, -8], [-46, -46], [0, -64], [46, -46], [56, -8], [30, -30], [-30, -30]], INK, { ox: 2, oy: 2 });
  [-1, 1].forEach(k => {
    if (sleep) ln(k * 36 - 12, -4, k * 36 + 12, -4, 5);
    else if (happy) { ln(k * 36 - 12, 0, k * 36, -12, 5); ln(k * 36, -12, k * 36 + 12, 0, 5); }
    else if (stress) { box(k * 36 - 12, -20, 24, 24, CR, { ox: 1, oy: 1, lw: 3 }); box(k * 36 - 4 + Math.sin(t * 30) * 3, -12, 8, 8, INK, { ox: 0, oy: 0, line: null }); ln(k * 36 - 18, -34, k * 36 + 12, -26 + k * 6, 5); }
    else box(k * 36 - 6, -12, 12, 12, INK, { ox: 0, oy: 0, line: null });
  });
  if (stress) stroke([[-20, 28], [-10, 22], [0, 30], [10, 22], [20, 28]], false, 5);
  else if (happy) { poly([[-22, 20], [22, 20], [0, 40]], CR, { ox: 1, oy: 1, lw: 3 }); }
  else if (sleep) ln(-14, 28, 14, 28, 5); else stroke([[-16, 26], [0, 32], [16, 26]], false, 5);
  if (stress) for (let i = 0; i < 3; i++) { const u = (t * 1.2 + i / 3) % 1; dia((i - 1) * 62, -74 + u * 70, 8, '#7FB5D6', { ox: 0, oy: 0, a: 1 - u }); }
  if (sleep) for (let i = 0; i < 3; i++) { const u = (t * .5 + i / 3) % 1; TX('Z', 40 + u * 60, -60 - u * 90, { size: 36 + i * 14, a: 1 - u }); }
  x.restore();
}

/* ---------- icone ---------- */
function cloud(cx, cy, s, fill = SKY, a = 1) { x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s);
  poly([[-120, 40], [-120, 0], [-70, -10], [-50, -50], [10, -60], [40, -30], [90, -30], [120, 0], [120, 40]], fill); x.restore(); }
function computer(cx, cy, s, col = TEA, label = '', t = 0, work = 0) {
  x.save(); x.translate(cx, cy); x.scale(s, s);
  box(-90, -70, 180, 120, CR, { lw: 4 }); box(-76, -56, 152, 92, col, { ox: 2, oy: 2, lw: 3 });
  if (work) for (let k = 0; k < 4; k++) box(-62, -44 + k * 20, 40 + 70 * (.5 + .5 * Math.sin(t * 3 + k * 1.7)), 8, CR, { ox: 0, oy: 0, line: null });
  poly([[-26, 50], [26, 50], [40, 74], [-40, 74]], CR2, { ox: 3, oy: 3 });
  if (label) MO(label, 0, 100, { al: 'center', size: 20, ls: 2 });
  x.restore();
}
function docIcon(cx, cy, s, col, letter, a = 1) { x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s);
  poly([[-44, -58], [18, -58], [44, -32], [44, 58], [-44, 58]], CR); poly([[18, -58], [18, -32], [44, -32]], col, { ox: 1, oy: 1, lw: 3 });
  box(-30, 4, 60, 40, col, { ox: 3, oy: 3, lw: 3 }); TX(letter, 0, 38, { size: 34, al: 'center', col: CR }); x.restore(); }
function mic(cx, cy, s, col = RED) { x.save(); x.translate(cx, cy); x.scale(s, s);
  box(-22, -62, 44, 80, col, { lw: 4 }); stroke([[-40, 4], [-40, 30], [40, 30], [40, 4]], false, 5); ln(0, 30, 0, 62, 5); ln(-24, 62, 24, 62, 5); x.restore(); }
function lock(cx, cy, s, col = MUS) { x.save(); x.translate(cx, cy); x.scale(s, s);
  stroke([[-26, -22], [-26, -54], [26, -54], [26, -22]], false, 8); box(-44, -22, 88, 66, col, { lw: 4 }); box(-6, -2, 12, 24, INK, { ox: 0, oy: 0, line: null }); x.restore(); }
function stamp(cx, cy, s, label, col, rot = -.1) { x.save(); x.translate(cx, cy); x.rotate(rot); x.scale(s, s); const w = measure(label, 900, 44, FD, 3) + 56;
  stroke([[-w / 2, -42], [w / 2, -42], [w / 2, 42], [-w / 2, 42]], true, 6, col); stroke([[-w / 2 + 8, -34], [w / 2 - 8, -34], [w / 2 - 8, 34], [-w / 2 + 8, 34]], true, 2, col);
  TX(label, 0, 15, { size: 44, al: 'center', col, ls: 3 }); x.restore(); }
function bottone(cx, cy, s, label, on, col = RED) { x.save(); x.translate(cx, cy); x.scale(s, s); const w = measure(label, 900, 40, FD, 1) + 70;
  box(-w / 2, -40, w, 80, on ? col : CR, { lw: 4 }); TX(label, 0, 14, { size: 40, al: 'center', col: on ? CR : INK, ls: 1 }); x.restore(); }
function sun(cx, cy, r, a = 1) { x.save(); x.globalAlpha *= a; for (let i = 0; i < 8; i++) { const g = i * .785; ln(cx + Math.cos(g) * r * 1.3, cy + Math.sin(g) * r * 1.3, cx + Math.cos(g) * r * 1.8, cy + Math.sin(g) * r * 1.8, 6, MUS); } dia(cx, cy, r, MUS); x.restore(); }
function moon(cx, cy, r) { oct(cx, cy, r, MUS); oct(cx + r * .55, cy - r * .3, r * .95, TEA, { ox: 0, oy: 0, line: null }); }
function robot(cx, cy, s, t, a = 1) { x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s);
  ln(0, -86, 0, -110, 5); dia(0, -118, 10, RED); box(-60, -80, 120, 100, SKY, { lw: 4 });
  [-1, 1].forEach(k => box(k * 26 - 10, -50, 20, 20, CR, { ox: 1, oy: 1, lw: 3 })); ln(-26, 0, 26, 0, 6);
  poly([[-44, 28], [44, 28], [58, 120], [-58, 120]], TEA); dia(0, 70, 14 + 2 * Math.sin(t * 4), MUS, { ox: 1, oy: 1 }); x.restore(); }

/* ---------- livelli fissi ---------- */
const CHAPTERS = [[0, 16.6, '00 · LA NOTTE'], [16.6, 35.0, '01 · IL PROBLEMA'], [35.0, 68.4, '02 · COME FUNZIONA'], [68.4, 109.8, '03 · COSA SA FARE'], [109.8, 132.4, 'SCHERMATE REALI'], [132.4, 238.0, '04 · CASI D\'USO'], [238.0, 255.0, '05 · COME LAVORIAMO'], [255.0, 270, '06 · ORA TOCCA A TE']];
function bgPaper(t) { x.drawImage(PAPER, 0, 0); }
function hudYT(t) {
  const a = P(t, .3, .9); if (a <= 0) return;
  x.save(); x.globalAlpha = a;
  box(60, 40, 300, 46, RED, { ox: 3, oy: 3, lw: 3 }); MO('ZEROZEROCOMPUTER', 80, 72, { size: 21, col: CR, ls: 2 });
  const ch = CHAPTERS.find(c => t >= c[0] && t < c[1]); if (ch) MO(ch[2], W - 60, 72, { size: 21, al: 'right', ls: 3 });
  ln(60, H - 36, W - 60, H - 36, 4, '#C9B994'); ln(60, H - 36, lerp(60, W - 60, t / DUR), H - 36, 6, TEA);
  CHAPTERS.forEach(c => dia(lerp(60, W - 60, c[0] / DUR), H - 36, 7, t >= c[0] ? MUS : CR2, { ox: 1, oy: 1, lw: 2 }));
  x.restore();
}

/* ============ 00 · la notte (1.0 – 16.0) ============ */
function gancio(t) {
  const ct = t - OFF.g; if (ct < -.2 || ct > 15.2) return;
  const e = fade(t, OFF.g, OFF.g + 15, .4); x.save(); x.globalAlpha = e;
  headline(ct, [[.38, 1.7, 'SONO LE TRE|DI NOTTE.'], [2.18, 5.9, 'NESSUNO IN STUDIO,|IN BOTTEGA, IN OFFICINA.'], [6.17, 10.2, 'EPPURE QUALCUNO|STA LAVORANDO.', RED], [10.67, 12.4, 'AL MATTINO TROVI|TUTTO PRONTO.', TEA], [12.74, 15, 'GUARDI. CORREGGI.|APPROVI.', TEA]], 96, 230, 92, 900);
  const day = ct > 10.6;
  box(1000, 130, 830, 820, day ? CR2 : TEA, { lw: 5 });
  if (!day) { for (let i = 0; i < 14; i++) { dia(1050 + ((i * 197) % 600), 170 + ((i * 131) % 300), 5 + (i % 3) * 2, CR, { ox: 0, oy: 0, a: .4 + .5 * Math.abs(Math.sin(ct * 2 + i)) }); } moon(1660, 270, 62); }
  else sun(1660, 270, 60 + 4 * Math.sin(ct * 3));
  // edifici: studio, bottega (tenda), officina (tetto a dente di sega)
  const wins = ct > 6.17 && ct < 10.4;
  const B = [[1060, 'studio', 250], [1330, 'bottega', 220], [1570, 'officina', 230]];
  B.forEach(([bx, k, bw], i) => {
    const by = 560, bh = 300, p = pop(ct, 2.2 + i * .5);
    if (p <= 0) return; at(bx + bw / 2, by + bh, p, () => { x.translate(-bw / 2, -bh);
      if (k === 'officina') poly([[0, 40], [0, 0], [bw / 3, 40], [bw / 3, 0], [2 * bw / 3, 40], [2 * bw / 3, 0], [bw, 40], [bw, bh], [0, bh]], day ? SKY : '#3B7C79', { lw: 4 });
      else box(0, 0, bw, bh, day ? SKY : '#3B7C79', { lw: 4 });
      if (k === 'bottega') for (let s = 0; s < 5; s++) poly([[s * bw / 5, 30], [(s + 1) * bw / 5, 30], [(s + 1) * bw / 5, 80], [s * bw / 5, 80]], s % 2 ? CR : RED, { ox: 2, oy: 2, lw: 3 });
      for (let w = 0; w < 2; w++) { const lit = wins || day, wx = 40 + w * (bw - 130), wy = k === 'bottega' ? 120 : 90;
        box(wx, wy, 70, 80, lit ? MUS : INK, { ox: 3, oy: 3, lw: 3 });
        if (wins) { const q = (ct * 1.5 + i + w) % 3; if (q < 1) { ln(wx + 16, wy + 40, wx + 30, wy + 56, 6, INK); ln(wx + 30, wy + 56, wx + 56, wy + 22, 6, INK); } else if (q < 2) { stroke([[wx + 18, wy + 18], [wx + 44, wy + 18], [wx + 44, wy + 44], [wx + 18, wy + 44]], true, 4); ln(wx + 44, wy + 44, wx + 58, wy + 60, 6, INK); } else { box(wx + 16, wy + 14, 38, 50, CR, { ox: 1, oy: 1, lw: 3 }); ln(wx + 22, wy + 28, wx + 48, wy + 28, 3); ln(wx + 22, wy + 40, wx + 44, wy + 40, 3); } } }
      box(bw / 2 - 24, bh - 100, 48, 100, INK, { ox: 3, oy: 3, lw: 3 });
    });
    if (wins) MO(['controlla', 'cerca', 'prepara'][i], bx + bw / 2, 925, { al: 'center', size: 24, col: RED, ls: 2, a: pop(ct, 6.3 + i * 1.2) });
  });
  ln(1020, 860, 1810, 860, 5);
  // letto con il titolare che dorme (di giorno è in piedi con il caffè)
  if (!day) { box(110, 850, 520, 46, RED, { lw: 4 }); box(130, 800, 120, 50, CR, { lw: 3 }); persona(330, 700, .8, 'sleep', ct); }
  else persona(330, 700, .8, ct > 12.7 ? 'happy' : 'calm', ct);
  // orologio
  const mins = day ? 8 * 60 : 3 * 60; TX(day ? '08:00' : '03:00', 1060, 280, { size: 76, col: day ? INK : CR, a: P(ct, .3, .8) });
  if (ct > 10.67) { stamp(1330, 470, pop(ct, 10.9, .4), 'TUTTO PRONTO', TEA, -.08); }
  if (ct > 12.74) ['GUARDI', 'CORREGGI', 'APPROVI'].forEach((s, i) => { const p = pop(ct, 12.8 + i * .6); at(1170 + i * 210, 560, p, () => stamp(0, 0, .7, s, [TEA, RED, MUS][i], .05 * (i - 1))); });
  x.restore();
}

/* ============ 01 · il problema (16.6 – 34.4) ============ */
function problema(t) {
  const ct = t - OFF.p; if (ct < -.2 || ct > 18.2) return;
  const e = fade(t, OFF.p, OFF.p + 17.8, .4); x.save(); x.globalAlpha = e;
  headline(ct, [[.43, 2.94, 'CHI HA UNA PICCOLA ATTIVITÀ|FA TUTTO DA SOLO.'], [3.3, 6.2, 'ORDINI · CLIENTI · FATTURE|SCADENZE · SOCIAL'], [6.58, 10.6, 'LE GIORNATE FINISCONO AL COMPUTER,|IL LAVORO VERO RESTA INDIETRO.', RED], [10.81, 13.5, 'LE GRANDI AZIENDE HANNO|UN REPARTO PER QUESTO.'], [13.8, 14.8, 'TU NO.', RED], [14.9, 17.8, 'MA OGGI PUOI AVERE|UN ASSISTENTE.', TEA]], 96, 230, 84, 1250);
  // scrivania con pile di carte
  box(100, 760, 760, 36, INK, { lw: 4 }); ln(160, 796, 160, 940, 8); ln(800, 796, 800, 940, 8);
  persona(480, 590, .95, ct < 14.9 ? 'stress' : 'calm', ct);
  box(380, 700, 200, 60, SKY, { lw: 4 });
  for (let k = 0; k < 6; k++) { const p = oCub(P(ct, 1 + k * .5, 1.5 + k * .5)); if (p > 0) box(130 + (k % 3) * 56, 760 - 24 * (Math.floor(k / 3) + 1) * p - 12, 110, 24, k % 2 ? CR : CR2, { ox: 2, oy: 2, lw: 3 }); }
  // post-it
  const N = [['ordini', MUS, 3.3], ['clienti', SKY, 3.9], ['fatture', RED, 4.5], ['scadenze', TEA, 5.1], ['social', CR2, 5.7]];
  N.forEach(([n, col, t0], i) => { const p = pop(ct, t0, .4); at(960 + (i % 3) * 270, 430 + Math.floor(i / 3) * 190 + (i > 2 ? 0 : 0), p, () => { x.rotate((i - 2) * .05); box(-110, -60, 220, 120, col, { lw: 4 }); TX(n.toUpperCase(), 0, 12, { size: 34, al: 'center', col: col === RED || col === TEA ? CR : INK }); }); });
  // il tempo si consuma
  const bp = P(ct, 6.6, 7.1);
  if (bp > 0) { x.save(); x.globalAlpha *= bp; MO('TEMPO DISPONIBILE', 960, 840, { size: 22, ls: 3 }); box(960, 860, 790, 52, CR2, { lw: 4 });
    x.save(); x.beginPath(); x.rect(960, 860, 790, 52); x.clip(); x.fillStyle = ct > 8.9 ? RED : TEA; x.fillRect(960, 860, Math.max(30, 790 * (1 - .9 * ioCub(P(ct, 6.8, 10.4)))), 52); x.restore(); x.restore(); }
  // grattacielo con il reparto
  const gp = pop(ct, 10.9, .5);
  if (gp > 0) at(1560, 930, gp, () => { x.translate(-100, -330); box(0, 0, 200, 330, SKY, { lw: 5 }); for (let r = 0; r < 6; r++) for (let c = 0; c < 3; c++) box(24 + c * 58, 24 + r * 48, 34, 28, MUS, { ox: 2, oy: 2, lw: 2 }); MO('REPARTO', 100, -20, { al: 'center', size: 24, ls: 3 }); });
  if (ct > 13.8) stamp(480, 340, pop(ct, 13.85, .4), 'TU NO', RED, -.12);
  if (ct > 14.9) { robot(1380, 600, 1.1 * pop(ct, 14.9, .5), ct); at(1620, 560, pop(ct, 16.0, .4), () => { lock(0, 0, .9, MUS); MO('DATI TUOI', 0, 80, { al: 'center', size: 22, ls: 2 }); }); }
  x.restore();
}

/* ============ 02 · come funziona (35.0 – 67.8) ============ */
function funziona(t) {
  const ct = t - OFF.c; if (ct < -.2 || ct > 33.2) return;
  const e = fade(t, OFF.c, OFF.c + 32.8, .4); x.save(); x.globalAlpha = e;
  headline(ct, [[0, .95, 'FUNZIONA COSÌ.', TEA], [1.24, 4.3, 'NON È UN SERVIZIO|SU INTERNET.', RED], [4.7, 8.9, 'È UN SISTEMA SUI COMPUTER|CHE HAI GIÀ.'], [9.3, 16.95, 'PIÙ COMPUTER, IN UNA RETE PRIVATA,|SI DIVIDONO IL LAVORO.'], [17.28, 19, 'I TUOI DATI|RESTANO DOVE SONO.', TEA], [19.45, 23.65, 'DI NOTTE,|L\'ASSISTENTE LAVORA.', RED], [23.63, 30, 'OGNI COSA CHE PREPARA|È UNA BOZZA.', TEA], [30.17, 32.8, 'E SE QUALCOSA NON VA,|ANNULLI CON UN TASTO.', RED]], 96, 230, 80, 880);
  // nuvola barrata (non è internet)
  if (ct < 4.9) { const ca = pop(ct, 1.3, .4) * (1 - P(ct, 4.3, 4.8)); cloud(1380, 330, 1.3 * ca, SKY); if (ca > 0) { ln(1250, 270, 1510, 400, 10, RED); ln(1510, 270, 1250, 400, 10, RED); [0, 1, 2].forEach(i => { const u = ((ct - 1.8) * .6 + i / 3) % 1; if (ct > 1.8) box(1000 + u * 300, 560 - u * 150, 60, 74, CR, { lw: 3, a: 1 - u }); }); } }
  // l'ufficio e i computer
  const ob = P(ct, 4.7, 5.5);
  if (ob > 0) { x.save(); x.globalAlpha *= ob; box(960, 330, 870, 600, '#00000000', { lw: 5, line: null }); x.setLineDash([22, 14]); x.lineDashOffset = -ct * 20; x.strokeStyle = TEA; x.lineWidth = 5; x.strokeRect(960, 330, 870, 600); x.restore(); MO('IL TUO UFFICIO · LA TUA CASA', 990, 370, { size: 22, col: TEA, ls: 3, a: ob }); }
  const night = ct > 19.45 && ct < 23.7;
  const C = [[1230, 640, 1.35, 'IL PIÙ POTENTE', 5.6], [1560, 520, .95, 'AIUTA', 6.4], [1600, 790, .95, 'AIUTA', 7.2]];
  const link = oCub(P(ct, 9.8, 11));
  if (link > 0) { ln(1230, 640, lerp(1230, 1560, link), lerp(640, 520, link), 5, MUS); ln(1230, 640, lerp(1230, 1600, link), lerp(640, 790, link), 5, MUS); ln(1560, 520, lerp(1560, 1600, link), lerp(520, 790, link), 5, MUS); }
  C.forEach(([cx, cy, s, lb, t0], i) => { const p = pop(ct, t0, .45); if (p > 0) { computer(cx, cy, s * p, i ? SKY : TEA, ct > 12.9 ? lb : '', ct, night ? 1 : 0); } });
  if (ct > 13 && ct < 17) { const u = (ct * 1.2) % 1; dia(lerp(1560, 1230, u), lerp(520, 640, u), 9, RED); dia(lerp(1600, 1230, u), lerp(790, 640, u), 9, RED); }
  if (ct > 17.28) at(1010, 860, pop(ct, 17.3, .4), () => { lock(0, 0, .9, MUS); });
  if (night) { moon(1700, 410, 46); const ca = P(ct, 19.5, 20); TX('02:40', 1190, 450, { size: 54, a: ca }); }
  // la bozza
  if (ct > 23.63) { const p = pop(ct, 23.7, .4); at(1330, 640, p, () => { poly([[-110, -90], [50, -90], [110, -40], [110, 100], [-110, 100]], CR, { lw: 4 }); [-50, -20, 10, 40].forEach((yy, k) => ln(-80, yy, 40 + (k % 2) * 20, yy, 5, '#8B8470')); stamp(40, 40, .55, 'BOZZA', RED, -.1); });
    if (ct > 26) at(1640, 860, pop(ct, 26.0, .4), () => { x.save(); ln(-70, 0, 70, 0, 6, RED); MO('NIENTE PARTE', 0, 46, { al: 'center', size: 20, col: RED, ls: 2 }); x.restore(); });
    if (ct > 28) at(1380, 860, pop(ct, 28.4, .4), () => bottone(0, 0, .7, 'APPROVO', ct > 29.2, TEA)); }
  if (ct > 30.17) at(1600, 330, pop(ct, 30.3, .4) * (ct > 31.8 ? 1.1 : 1), () => bottone(0, 0, .85, '↶ ANNULLA', ct > 31.8, RED));
  x.restore();
}

/* ============ 03 · cosa sa fare (68.4 – 109.2) ============ */
function cosaSaFare(t) {
  const ct = t - OFF.s; if (ct < -.2 || ct > 41.2) return;
  const e = fade(t, OFF.s, OFF.s + 40.8, .4); x.save(); x.globalAlpha = e;
  headline(ct, [[.74, 1.7, 'CHE COSA SA FARE?', TEA], [2, 6, 'DOCUMENTI WORD, EXCEL E PDF.'], [6.24, 13.4, 'CERCA IN RETE LE NOVITÀ DEL TUO SETTORE.'], [13.63, 17, 'RICORDA QUELLO CHE GLI HAI DETTO.'], [17.25, 21.8, 'PUÒ PARLARE CON LA TUA VOCE.'], [21.9, 40.5, 'SI COLLEGA AI SISTEMI CHE GIÀ USI.', RED]], 96, 215, 70, 1700);
  const Y1 = 290, Y2 = 640, CH = 300;
  const card = (cx, cy, w, t0, title, tag, fn) => { const p = pop(ct, t0, .45); if (p <= 0) return; at(cx + w / 2, cy + CH / 2, p, () => { x.translate(-w / 2, -CH / 2); box(0, 0, w, CH, CR2, { lw: 4 }); MO(title, 24, 44, { size: 22, ls: 3 }); if (tag) chip(w - 24 - measure(tag, 700, 18, FM, 1) - 44, 46, tag, tag.startsWith('SU') ? RED : TEA, CR, 18); fn(w, CH); }); };
  card(96, Y1 + 40, 540, 2.0, 'DOCUMENTI', 'ATTIVO', () => { docIcon(120, 170, 1.05, TEA, 'W'); docIcon(270, 170, 1.05, MUS, 'X'); docIcon(420, 170, 1.05, RED, 'P'); MO('BOZZA DA CORREGGERE', 270, 270, { al: 'center', size: 20, ls: 2, a: P(ct, 4.3, 4.8) }); });
  card(666, Y1 + 40, 540, 6.2, 'RICERCA IN RETE', 'ATTIVO', () => { x.save(); x.translate(110, 170); x.scale(1.2, 1.2); ln(0, 0, 0, 0); stroke([[-30, -30], [30, -30], [30, 30], [-30, 30]], true, 7); ln(30, 30, 62, 62, 9); x.restore();
    ['tecniche', 'fornitori', 'prezzi'].forEach((s, i) => { const p = pop(ct, 8.5 + i * 1.5, .4); at(360, 118 + i * 56, p, () => chip(-110, 0, s, i === 1 ? MUS : CR, INK, 22)); }); });
  card(1236, Y1 + 40, 588, 13.6, 'MEMORIA', 'ATTIVO', () => { box(60, 100, 150, 170, CR, { lw: 4 }); [0, 1, 2, 3].forEach(k => ln(84, 140 + k * 36, 184 - (k % 2) * 30, 140 + k * 36, 5, '#8B8470')); stroke([[60, 100], [60, 270]], false, 14, TEA);
    ['"consegna il giovedì"', '"cliente allergico"'].forEach((s, i) => { const p = pop(ct, 14.6 + i * 1.2, .4); at(330, 130 + i * 70, p, () => { box(-30, -28, 270, 52, MUS, { lw: 3 }); MO(s, -14, 6, { size: 18 }); }); }); });
  card(96, Y2 + 20, 540, 17.25, 'LA TUA VOCE', 'ATTIVO', () => { mic(120, 170, 1.05); for (let k = 0; k < 9; k++) box(230 + k * 32, 190 - (14 + 46 * Math.abs(Math.sin(ct * 4 + k * 1.3))) / 2 + 0, 16, 14 + 46 * Math.abs(Math.sin(ct * 4 + k * 1.3)), TEA, { ox: 2, oy: 2, lw: 2 }); MO('VIDEO · MESSAGGI AI CLIENTI', 270, 280, { al: 'center', size: 18, ls: 1 }); });
  card(666, Y2 + 20, 1158, 21.9, 'COLLEGAMENTI', 'SU MISURA', (w) => { [['DATABASE', 22.4], ['GESTIONALE', 24.2], ['NEGOZIO ONLINE', 26.0]].forEach(([n, t0], i) => { const p = pop(ct, t0, .4); at(150 + i * 340, 130, p, () => { if (i === 0) { [-1, 0, 1].forEach(k => { x.save(); x.beginPath(); x.ellipse(0, k * 26, 50, 16, 0, 0, 7); x.fillStyle = k < 0 ? SKY : CR; x.fill(); x.strokeStyle = INK; x.lineWidth = 3.5; x.stroke(); x.restore(); }); }
      else if (i === 1) { box(-60, -50, 120, 100, SKY, { lw: 4 }); [0, 1, 2].forEach(k => ln(-40, -26 + k * 26, 40, -26 + k * 26, 5, CR)); }
      else { poly([[-60, -20], [60, -20], [48, 50], [-48, 50]], RED, { lw: 4 }); stroke([[-30, -20], [-30, -50], [30, -50], [30, -20]], false, 6); }
      MO(n, 0, 82, { al: 'center', size: 20, ls: 2 }); }); });
    const pl = P(ct, 27, 28.5); if (pl > 0) { ln(200, 130, lerp(200, 880, pl), 130, 6, MUS); [0, 1, 2].forEach(i => dia(150 + i * 340 + 70, 130, 8, MUS, { ox: 0, oy: 0 })); } });
  if (ct > 29.05 && ct < 35.45) at(1250, 945, pop(ct, 29.1, .4), () => stamp(0, 0, .62, 'NON ESISTE UN COLLEGAMENTO UGUALE PER TUTTI', RED, -.02));
  if (ct > 35.5) at(1250, 945, pop(ct, 35.5, .4), () => stamp(0, 0, .62, 'LO VERIFICHIAMO INSIEME, CASO PER CASO', TEA, -.02));
  x.restore();
}

/* ============ schermate reali (109.8 – 131.8) ============ */
function schermate(t) {
  const ct = t - OFF.scr; if (ct < -.2 || ct > 22.2) return;
  const e = fade(t, OFF.scr, OFF.scr + 22, .4); x.save(); x.globalAlpha = e;
  chip(96, 150, 'SCHERMATE REALI · OGGI', TEA, CR, 26);
  const beats = [[0, 7, ['analytics'], 'Il sistema al lavoro', 'Cicli di lavoro, parole generate, velocità: dai computer della rete.'], [7, 14, ['seo'], 'Il sito, controllato ogni giorno', 'Punteggio SEO e presenza nei motori di ricerca con intelligenza artificiale.'], [14, 22, ['radar', 'sched'], 'Ricerca in rete e lavori programmati', 'Lo scouting di novità e i lavori notturni in calendario.']];
  beats.forEach(([a, b, names, title, cap]) => { if (ct < a || ct > b) return; const f = fade(ct, a, b, .35), s = oCub(P(ct, a, a + .5));
    TX(title.toUpperCase(), 96, 260, { size: 62, a: f, ls: -1 }); MO(cap, 96, 312, { size: 24, a: f });
    x.save(); x.globalAlpha *= f; x.translate((1 - s) * -60, 0);
    if (names.length === 1) { shot(names[0], 150, 420, names[0] === 'seo' ? 1500 : 1380); }
    else { shot('radar', 190, 440, 720); shot('sched', 1010, 440, 720); }
    x.restore(); });
  x.restore();
}

/* ============ 04 · casi d'uso (132.4 – 237.4, 7 × 15 s) ============ */
const CASI = [
  ['01 / 07', 'LA BOTTEGA', 'Foto, testi e calendario dei post, pronti al mattino.', ['foto', 'testi', 'calendario'], 'ESEMPIO · SU MISURA'],
  ['02 / 07', 'LO STUDIO COMMERCIALISTA', 'Gestionale e pratiche a confronto. Scadenze e richieste di documenti.', ['differenze', 'scadenze', 'richieste'], 'ESEMPIO · SU MISURA'],
  ['03 / 07', 'L\'ARTIGIANO', 'Fornitori, prezzi a confronto, preventivo da controllare.', ['fornitori', 'prezzi', 'preventivo'], 'ESEMPIO · SU MISURA'],
  ['04 / 07', 'IL RISTORANTE', 'Il cameriere detta, conferma con un tocco: la comanda va in cucina.', ['voce', 'conferma', 'cucina'], 'ANTEPRIMA · DA REALIZZARE'],
  ['05 / 07', 'LO STUDIO MEDICO', 'Calendario, promemoria, posti liberi da riempire.', ['agenda', 'promemoria', 'posti liberi'], 'SOLO AGENDA · NESSUN DATO CLINICO'],
  ['06 / 07', 'LA PALESTRA', 'Abbonamenti in scadenza, corsi, messaggi a chi manca da un po\'.', ['abbonamenti', 'corsi', 'messaggi'], 'ESEMPIO · SU MISURA'],
  ['07 / 07', 'IL GOMMISTA', 'Cambio gomme di stagione: chi chiamare e quando.', ['stagione', 'calendario', 'avvisi'], 'ESEMPIO · SU MISURA']
];
function casi(t) {
  const ct = t - OFF.uc; if (ct < -.2 || ct > CASI.length * CASE_DUR + .2) return;
  const i = clamp(Math.floor(ct / CASE_DUR), 0, CASI.length - 1), lt = ct - i * CASE_DUR, [num, title, cap, tags, tag] = CASI[i];
  const f = fade(lt, 0, CASE_DUR, .4) * fade(t, OFF.uc, OFF.uc + CASI.length * CASE_DUR, .4); x.save(); x.globalAlpha = f;
  MO(num, 96, 190, { size: 26, col: RED, ls: 4 });
  const w = measure(title, 900, 96, FD, -2), sz = Math.min(96, 96 * 760 / w);
  TX(title, 96 - (1 - oCub(P(lt, .1, .6))) * 60, 280, { size: sz, ls: -2 });
  const lines = (() => { const wds = cap.split(' '); const out = ['']; wds.forEach(w2 => { if ((out[out.length - 1] + ' ' + w2).length > 34) out.push(w2); else out[out.length - 1] += (out[out.length - 1] ? ' ' : '') + w2; }); return out; })();
  lines.forEach((l, k) => MO(l, 96, 360 + k * 36, { size: 26, a: P(lt, .8, 1.2) }));
  tags.forEach((s, k) => { chip(96, 560 + k * 80, s, [MUS, SKY, CR2][k], INK, 28, pop(lt, 1.6 + k * .8, .4)); });
  chip(96, 880, tag, tag.startsWith('ANTE') || tag.startsWith('SOLO') ? RED : TEA, CR, 22, P(lt, .5, 1));
  const cx = 1330, cy = 540; x.save(); x.translate(cx, cy);
  if (i === 0) { // bottega: tenda, vetrina, telefono con i post
    const p = pop(lt, .6, .5); at(-240, 60, p, () => { for (let s = 0; s < 6; s++) poly([[-150 + s * 50, -150], [-100 + s * 50, -150], [-100 + s * 50, -90], [-150 + s * 50, -90]], s % 2 ? CR : RED, { ox: 2, oy: 2, lw: 3 }); box(-150, -90, 300, 240, SKY, { lw: 4 }); box(-110, -40, 120, 100, MUS, { ox: 3, oy: 3, lw: 3 }); box(40, -10, 70, 160, INK, { ox: 3, oy: 3, lw: 3 }); });
    at(190, 40, pop(lt, 1.4, .5), () => { box(-90, -190, 180, 360, INK, { lw: 4 }); for (let r = 0; r < 3; r++) for (let c = 0; c < 2; c++) { const pp = pop(lt, 2.2 + (r * 2 + c) * .4, .35); at(-44 + c * 88, -120 + r * 100, pp, () => { box(-36, -36, 72, 72, [RED, MUS, SKY, TEA, CR, MUS][r * 2 + c], { ox: 2, oy: 2, lw: 3 }); dia(0, 0, 14, CR, { ox: 0, oy: 0, lw: 2 }); }); } });
    ['L', 'M', 'M', 'G', 'V'].forEach((d, k) => { const pp = pop(lt, 5 + k * .3, .3); at(-300 + k * 90, 270, pp, () => { box(-34, -40, 68, 80, k === 2 ? RED : CR2, { lw: 3 }); TX(d, 0, 12, { size: 30, al: 'center', col: k === 2 ? CR : INK }); }); });
  } else if (i === 1) { // studio: gestionale vs pratiche
    [['GESTIONALE', -330, TEA], ['PRATICHE', 70, RED]].forEach(([n, px, col], s) => { const p = pop(lt, .6 + s * .3, .5); at(px + 150, 20, p, () => { x.translate(-150, -230); box(0, 0, 300, 460, CR2, { lw: 4 }); box(0, 0, 300, 56, col, { ox: 3, oy: 3, lw: 3 }); MO(n, 150, 38, { size: 20, al: 'center', col: CR, ls: 3 });
      ['Rossi', 'Bianchi', 'Verdi', 'Neri'].forEach((c, k) => box(20, 80 + k * 90, 260, 66, CR, { ox: 2, oy: 2, lw: 3 }) || TX(c, 40, 124 + k * 90, { size: 32 })); }); });
    [0, 1, 2, 3].forEach(k => { const pp = oCub(P(lt, 2 + k * .6, 2.5 + k * .6)); const bad = k === 1 || k === 3; if (pp > 0) { ln(-30, -110 + k * 90 + 0, lerp(-30, 70, pp), -110 + k * 90, 6, bad && lt > 5 ? RED : TEA); if (bad && lt > 5) TX('≠', 20, -92 + k * 90, { size: 50, al: 'center', col: RED }); } });
    ['F24', 'IVA', 'REDDITI'].forEach((s, k) => chip(-180 + k * 190, 330, s, [MUS, SKY, CR2][k], INK, 22, pop(lt, 7 + k * .5, .4)));
  } else if (i === 2) { // artigiani: icone, prezzi, preventivo
    [['r', 'imbianchino'], ['w', 'idraulico'], ['g', 'meccanico']].forEach(([k, n], s) => { const p = pop(lt, .6 + s * .35, .45); at(-300 + s * 200, -210, p, () => { box(-80, -80, 160, 160, CR2, { lw: 4 });
      if (k === 'r') { box(-40, -50, 80, 28, TEA, { lw: 3 }); ln(0, -22, 0, 10, 8); box(-10, 10, 20, 44, MUS, { ox: 2, oy: 2, lw: 3 }); } else if (k === 'w') { ln(-30, 40, 24, -24, 22, RED); oct(30, -30, 30, RED); box(18, -60, 26, 30, CR2, { ox: 0, oy: 0, line: null }); } else { for (let q = 0; q < 8; q++) { x.save(); x.rotate(q * .785); box(-8, -58, 16, 22, SKY, { ox: 2, oy: 2, lw: 2 }); x.restore(); } oct(0, 0, 38, SKY); oct(0, 0, 14, CR2, { ox: 0, oy: 0 }); } }); });
    [['Fornitore A', .86, RED], ['Fornitore B', .6, TEA], ['Fornitore C', .74, SKY]].forEach(([n, f2, col], k) => { const g = oCub(P(lt, 3 + k * .5, 4 + k * .5)); MO(n, -340, 20 + k * 80, { size: 22, a: g }); box(-130, k * 80 - 4, 440 * f2 * g, 34, col, { ox: 3, oy: 3, lw: 3 }); if (k === 1 && g >= 1) chip(210, 70 + 32, 'più basso', MUS, INK, 20); });
    const pv = pop(lt, 7.5, .5); at(130, 290, pv, () => { poly([[-130, -80], [90, -80], [130, -40], [130, 90], [-130, 90]], CR, { lw: 4 }); MO('PREVENTIVO', -100, -36, { size: 22, ls: 3 }); [0, 1, 2].forEach(r => { ln(-100, -4 + r * 30, 70, -4 + r * 30, 5, '#8B8470'); }); stamp(40, 50, .5, 'DA CONTROLLARE', RED, -.08); });
  } else if (i === 3) { // ristorante: il cameriere, il tasto, la comanda, la cucina
    persona(-250, -40, 1.0, lt > 8.5 ? 'happy' : (lt > 1.5 && lt < 5 ? 'stress' : 'calm'), lt, { tie: true });
    const bp = pop(lt, 3.6, .4); at(60, -120, bp, () => { oct(0, 0, 54, lt > 4.2 && lt < 7 ? RED : CR2); oct(0, 0, 20, CR, { ox: 0, oy: 0, lw: 2 }); MO('REGISTRA', 0, 100, { al: 'center', size: 20, ls: 2 }); });
    if (lt > 4.2 && lt < 7) [0, 1, 2].forEach(k => { const u = ((lt - 4.2) * 1.1 + k / 3) % 1; stroke([[-110 - u * 90, -40 - u * 40], [-110 - u * 90, 40 + u * 40]].map(([a, b]) => [a + 130, b - 40]), false, 4, TEAL_OR(k)); });
    const tk = pop(lt, 7.2, .5); at(260, 20, tk, () => { poly([[-110, -120], [110, -120], [110, 130], [90, 110], [70, 130], [50, 110], [30, 130], [10, 110], [-10, 130], [-30, 110], [-50, 130], [-70, 110], [-90, 130], [-110, 110]], CR, { lw: 4 }); MO('TAVOLO 7', -90, -80, { size: 22, ls: 2 }); [['2 × Margherita', 0], ['1 × Tagliatelle', 1], ['  senza cipolla', 2]].forEach(([s2, r]) => MO(s2, -90, -36 + r * 40, { size: 20, col: r === 2 ? RED : INK, a: pop(lt, 7.6 + r * .4, .3) })); });
    if (lt > 9.4) { bottone(100, 270, .6, '✓ CONFERMA', lt > 10, TEA); const u = P(lt, 10.2, 12.2); box(240, 210 + u * 130, 70, 54, MUS, { lw: 3 }); MO('CUCINA', 360, 480, { size: 22, ls: 3, a: P(lt, 10, 10.5) }); box(180, 420, 190, 100, CR2, { lw: 4, a: P(lt, 10, 10.5) }); }
  } else if (i === 4) { // studio medico: agenda
    box(-380, -240, 760, 500, CR2, { lw: 4 }); ['LUN', 'MAR', 'MER', 'GIO', 'VEN'].forEach((d, k) => { MO(d, -310 + k * 150, -200, { size: 22, al: 'center', ls: 3 }); ln(-380 + k * 150 + 20, -180, -380 + k * 150 + 20, 250, 2, '#C9B994'); });
    const S = [[0, 0, 1, MUS, 1.5], [1, 1, 1, SKY, 1.9], [2, 0, 2, TEA, 2.3], [3, 2, 1, MUS, 2.7], [4, 1, 1, SKY, 3.1], [1, 3, 1, TEA, 3.5], [3, 0, 1, SKY, 3.9]];
    S.forEach(([d, r, h, col, t0]) => { const p = pop(lt, t0, .35); at(-310 + d * 150, -130 + r * 100 + h * 40, p, () => box(-56, -h * 40 - 4, 112, h * 80 - 8, col, { ox: 3, oy: 3, lw: 3 })); });
    [[4, 3]].forEach(([d, r]) => { const p = pop(lt, 6, .4); at(-310 + d * 150, 70 + r * 0, p, () => { stroke([[-56, -44], [56, -44], [56, 36], [-56, 36]], true, 4, RED); MO('libero', 0, 6, { size: 20, al: 'center', col: RED }); }); });
    const bp = pop(lt, 4.5, .45); at(300, 330, bp, () => { poly([[0, -50], [30, -26], [30, 24], [60, 46], [-60, 46], [-30, 24], [-30, -26]], MUS, { lw: 4 }); MO('PROMEMORIA', 0, 90, { al: 'center', size: 20, ls: 2 }); });
  } else if (i === 5) { // palestra: manubrio e abbonamenti
    const dp = pop(lt, .6, .5); at(-250, -150, dp, () => { box(-150, -10, 300, 20, INK, { lw: 3 }); [-1, 1].forEach(k => { box(k * 120 - 24, -70, 48, 140, RED, { lw: 4 }); box(k * 170 - 14, -42, 28, 84, MUS, { lw: 3 }); }); });
    ['Marta', 'Luca', 'Sara', 'Paolo'].forEach((n, k) => { const p = pop(lt, 2 + k * .5, .4), f2 = [.15, .7, .4, .9][k]; at(0, 20 + k * 80, p, () => { box(-340, -34, 680, 66, CR2, { lw: 3 }); TX(n, -320, 12, { size: 32 }); box(-110, -12, 380, 24, CR, { ox: 2, oy: 2, lw: 2 }); box(-110, -12, 380 * f2, 24, f2 < .3 ? RED : TEA, { ox: 0, oy: 0, line: null }); if (f2 < .3) chip(280, 6, 'scade', RED, CR, 18); }); });
    const mp = pop(lt, 6.2, .5); at(-120, 380, mp, () => { poly([[-250, -50], [250, -50], [250, 50], [-250, 50]], CR, { lw: 4 }); MO('Ciao Marta, ti aspettiamo…', -230, 8, { size: 22 }); stamp(180, 30, .4, 'BOZZA', RED, -.08); });
  } else { // gommista: gomma, stagioni, calendario
    const tp = pop(lt, .6, .5); at(-270, -60, tp, () => { oct(0, 0, 130, INK, { lw: 4 }); oct(0, 0, 86, CR2, { ox: 0, oy: 0 }); for (let q = 0; q < 5; q++) { x.save(); x.rotate(q * 1.2566 + lt * .5); ln(0, 0, 0, -80, 8, SKY); x.restore(); } oct(0, 0, 22, MUS, { ox: 2, oy: 2 }); });
    const ss = lt < 6 ? 'sole' : 'neve'; if (lt > 1.5) at(-270, -250, pop(lt, 1.6, .4), () => { if (lt < 6) sun(0, 0, 26); else { for (let q = 0; q < 3; q++) { x.save(); x.rotate(q * 1.047); ln(0, -34, 0, 34, 6, SKY); x.restore(); } } });
    ['L', 'M', 'M', 'G', 'V'].forEach((d, k) => { const p = pop(lt, 3 + k * .35, .3); at(40 + k * 100, -200, p, () => { box(-40, -30, 80, 60, CR2, { lw: 3 }); TX(d, 0, 12, { size: 28, al: 'center' }); [0, 1, 2].forEach(r => { const busy = (k + r) % 3 === 0; box(-40, 40 + r * 70, 80, 56, busy ? INK : CR, { ox: 2, oy: 2, lw: 3 }); if (!busy) MO('libero', 0, 74 + r * 70, { size: 14, al: 'center' }); }); }); });
    chip(60, 330, 'avviso ai clienti', MUS, INK, 24, pop(lt, 8, .4)); chip(60, 400, 'giorni e orari liberi', CR2, INK, 24, pop(lt, 9, .4));
  }
  x.restore(); x.restore();
}
function TEAL_OR(k) { return k % 2 ? TEA : RED; }

/* ============ 05 · come lavoriamo (238.0 – 254.4) ============ */
function lavoriamo(t) {
  const ct = t - OFF.l; if (ct < -.2 || ct > 16.8) return;
  const e = fade(t, OFF.l, OFF.l + 16.4, .4); x.save(); x.globalAlpha = e;
  headline(ct, [[.4, 2.4, 'COME LAVORIAMO.|SU MISURA:'], [2.78, 4.3, 'GUARDIAMO COME|LAVORI DAVVERO,'], [4.53, 8.2, 'COSTRUIAMO L\'ASSISTENTE|ATTORNO ALLA TUA ATTIVITÀ,|NON IL CONTRARIO.', TEA], [8.59, 12.7, 'OGNI PASSO È DOCUMENTATO|E SI PUÒ RIFARE|AL CONTRARIO.'], [13.18, 14, 'NIENTE GERGO.', RED], [14.2, 16.4, 'NIENTE PROMESSE|CHE NON POSSIAMO|MANTENERE.', RED]], 96, 220, 74, 1050);
  // sagoma dell'attività, metro, pezzi dell'assistente che si incastrano
  at(1450, 520, pop(ct, 2.8, .5), () => { box(-170, -140, 340, 280, SKY, { lw: 4 }); for (let s = 0; s < 6; s++) poly([[-170 + s * 57, -140], [-113 + s * 57, -140], [-113 + s * 57, -90], [-170 + s * 57, -90]], s % 2 ? CR : RED, { ox: 2, oy: 2, lw: 3 }); box(-100, -40, 90, 80, MUS, { ox: 3, oy: 3, lw: 3 }); box(30, -50, 70, 190, INK, { ox: 3, oy: 3, lw: 3 }); });
  if (ct > 3 && ct < 8.5) { const u = P(ct, 3, 4.2); ln(1250, 720, lerp(1250, 1650, u), 720, 6); for (let k = 0; k <= 8; k++) if (k / 8 <= u) ln(1250 + k * 50, 720, 1250 + k * 50, 740 - (k % 2) * 12, 4); }
  if (ct > 4.53) [[1330, 430, TEA], [1570, 430, MUS], [1330, 610, RED], [1570, 610, SKY]].forEach(([px, py, col], k) => { const u = oCub(P(ct, 4.6 + k * .45, 5.4 + k * .45)); if (u > 0) at(lerp(px + (k % 2 ? 300 : -300), px, u), py, 1, () => poly([[-60, -50], [60, -50], [60, 0], [40, 0], [40, 20], [-40, 20], [-40, 0], [-60, 0]], col, { lw: 4, a: .85 })); });
  if (ct > 8.59) [['1', 9], ['2', 10], ['3', 11.2]].forEach(([n, t0], k) => { const p = pop(ct, t0, .35); at(1230 + k * 230, 870, p, () => { oct(0, 0, 44, TEA); TX(n, 0, 14, { size: 40, al: 'center', col: CR }); ln(50, 0, 140, 0, 5); }); });
  if (ct > 11.4) at(1230 + 230 * 1.5 + 90, 940, pop(ct, 11.5, .4), () => stamp(0, 0, .6, '↶ SI TORNA INDIETRO', RED, 0));
  x.restore();
}

/* ============ 06 · chiusura (255.0 – 264.5) ============ */
function chiusura(t) {
  const ct = t - OFF.x; if (ct < -.2) return;
  const e = fade(t, OFF.x, DUR, .4); x.save(); x.globalAlpha = e;
  headline(ct, [[0, 2.5, 'TU PENSA|AL TUO MESTIERE.'], [2.73, 4.8, 'LE CARTE,|A LUI.', TEA]], 96, 330, 120, 1000);
  at(1380, 560, pop(ct, .1, .6), () => { box(-300, 180, 600, 40, RED, { lw: 4 }); box(-240, 70, 480, 120, CR2, { lw: 4 }); persona(0, 30, 1.2, 'happy', ct);
    box(150, 150, 90, 70, MUS, { ox: 3, oy: 3, lw: 3 }); ln(160, 140, 190, 110, 5); });
  if (ct > 4.99) { const p = pop(ct, 5.0, .5); at(540, 800, p, () => { const l1 = 'ZEROZEROCOMPUTER.IT', w = measure(l1, 900, 70, FD, 1) + 100; box(-w / 2 + 380, -60, w, 120, RED, { lw: 5 }); TX(l1, 380, 24, { size: 70, al: 'center', col: CR, ls: 1 }); MO('RACCONTACI COSA TI RUBA PIÙ TEMPO', 380, 110, { size: 28, al: 'center', ls: 2 }); });
    sun(1700, 220, 34, P(ct, 5.2, 5.7)); }
  x.restore();
}

const REEL = {
  date: '30.10.2026',
  tagline: 'L\'assistente che lavora di notte.',
  cta: 'zerozerocomputer.it',
  native: true,
  layers: { bg: bgPaper, intro: () => {}, outro: () => {}, hud: hudYT, cuts: () => {}, fade: CR },
  sc: [{ a: 1, b: 16.6, n: '00' }, { a: 16.6, b: 35, n: '01' }, { a: 35, b: 68.4, n: '02' }, { a: 68.4, b: 109.8, n: '03' }, { a: 132.4, b: 238, n: '04' }, { a: 238, b: 255, n: '05' }, { a: 255, b: 264.5, n: '06' }],
  cuts: [16.6, 35.0, 68.4, 109.8, 132.4, 238.0, 255.0], // confini dei capitoli (il livello `cuts` è spento)
  scenes: [gancio, problema, funziona, cosaSaFare, schermate, casi, lavoriamo, chiusura]
};
