// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "voglio-te-2026-10-29", "title": "00MESH Reel Voglio te", "aria": "Animazione di 30 secondi in stile manifesto d'epoca: un personaggio col cilindro punta il dito verso chi guarda e dice voglio te, piccola azienda, per i tuoi social. Seguono il problema del tempo per i social, il turno di notte che prepara reel, post e calendario con i computer dell'ufficio, l'approvazione al mattino con il tasto annulla, e la chiusura con l'invito a farsi vedere."}
/* Primo reel commerciale: offerta social per piccole aziende, stile manifesto. Le scene illustrano, non misurano. */

const PC = { paper: '#EDE3CC', paper2: '#E2D4B4', red: '#B8282E', navy: '#1E2B4F', ink: '#1A1A1A', white: '#F8F3E6', gold: '#D9A441', skin: '#E8C4A0', shade: '#C99C78' };

/* ---------- livelli fissi in stile manifesto ---------- */
const GRAIN = (() => { let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647; return Array.from({ length: 1600 }, () => [r() * 1080, r() * 1920, r() * 2.2 + .6, r()]); })();
function posterBg(t) {
  x.fillStyle = PC.paper; x.fillRect(0, 0, W, H);
  GRAIN.forEach(([gx, gy, r, k]) => circ(gx, gy, r, { fill: k > .5 ? '#CDBF9F' : '#F6EEDC', a: .55 }));
  const g = x.createRadialGradient(540, 960, 600, 540, 960, 1250);
  g.addColorStop(0, 'rgba(90,60,20,0)'); g.addColorStop(1, 'rgba(90,60,20,0.28)');
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  x.save(); x.strokeStyle = PC.navy; x.lineWidth = 6; x.strokeRect(36, 36, W - 72, H - 72);
  x.lineWidth = 2; x.strokeRect(52, 52, W - 104, H - 104); x.restore();
}
function posterCuts(t) {
  for (const c of REEL.cuts) {
    const p = P(t, c - .3, c + .3);
    if (p <= 0 || p >= 1) continue;
    const y = lerp(-500, H + 500, ioCub(p));
    x.save(); x.translate(0, y); x.rotate(-.12);
    x.fillStyle = PC.red; x.fillRect(-200, -90, W + 400, 120);
    x.fillStyle = PC.navy; x.fillRect(-200, 30, W + 400, 26);
    for (let i = 0; i < 9; i++) star(60 + i * 130, -30, 18, PC.white);
    x.restore();
  }
}

/* ---------- helper del manifesto ---------- */
function star(cx, cy, r, col, a = 1) {
  if (a <= 0) return;
  x.save(); x.globalAlpha *= a; x.fillStyle = col; x.beginPath();
  for (let i = 0; i < 10; i++) { const g = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * .42 : r; x.lineTo(cx + Math.cos(g) * rr, cy + Math.sin(g) * rr); }
  x.closePath(); x.fill(); x.restore();
}
function fit(s, max, size, ls = -2) { return Math.min(size, size * max / measure(s, 900, size, FD, ls)); }
function big(s, X, Y, size, col, o = {}) { T(s, X, Y, { w: 900, size, fam: FD, col, ls: -2, ...o }); }
function sunburst(cx, cy, t, a) {
  if (a <= 0) return;
  x.save(); x.globalAlpha *= a; x.beginPath(); x.rect(56, 56, W - 112, H - 112); x.clip();
  x.translate(cx, cy); x.rotate(t * .05);
  for (let i = 0; i < 24; i++) {
    const g = i * Math.PI / 12;
    x.fillStyle = i % 2 ? PC.paper2 : 'rgba(184,40,46,0.10)'; x.beginPath(); x.moveTo(0, 0);
    x.arc(0, 0, 1500, g, g + Math.PI / 12); x.closePath(); x.fill();
  }
  x.restore();
}
/* timbro di gomma: arriva grande e ruotato, si posa con un piccolo rimbalzo */
function stamp(text, cx, cy, size, t, t0, rot, col, box = true) {
  const p = P(t, t0, t0 + .28); if (p <= 0) return;
  const s = lerp(1.9, 1, oCub(p)) + .06 * Math.sin(P(t, t0 + .28, t0 + .5) * Math.PI);
  const wd = measure(text, 900, size, FD, 2);
  x.save(); x.globalAlpha *= clamp(p * 2); x.translate(cx, cy); x.rotate(rot); x.scale(s, s);
  if (box) { x.strokeStyle = col; x.lineWidth = size * .08; rrect(-wd / 2 - size * .3, -size * .82, wd + size * .6, size * 1.1, 10); x.stroke(); }
  T(text, 0, 0, { w: 900, size, fam: FD, col, al: 'center', ls: 2 });
  x.restore();
}
function kicker(s, Y, t, t0, col = PC.red) {
  const n = Math.floor(s.length * P(t, t0, t0 + .5));
  T(s.slice(0, n), 540, Y, { w: 700, size: 26, col, al: 'center', ls: 6 });
  const p = oExpo(P(t, t0 + .3, t0 + .9));
  seg(540 - 170 * p, Y + 26, 540 + 170 * p, Y + 26, { col, lw: 4 });
}
function ell(cx, cy, rx, ry, fill, stroke, lw = 6) {
  x.beginPath(); x.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
  if (fill) { x.fillStyle = fill; x.fill(); } if (stroke) { x.strokeStyle = stroke; x.lineWidth = lw; x.stroke(); }
}

/* ---------- il personaggio: cilindro, pizzetto e dito puntato (h = 0..1 grandezza della mano) ---------- */
function figure(cx, cy, s, h, t) {
  x.save(); x.translate(cx, cy); x.scale(s, s); x.lineJoin = 'round';
  // giacca
  x.fillStyle = PC.navy; x.beginPath(); x.moveTo(-250, 190); x.quadraticCurveTo(0, 150, 250, 190); x.lineTo(340, 640); x.lineTo(-340, 640); x.closePath(); x.fill();
  x.fillStyle = PC.white; x.beginPath(); x.moveTo(-90, 165); x.lineTo(90, 165); x.lineTo(0, 330); x.closePath(); x.fill();
  x.fillStyle = PC.red; x.beginPath(); x.moveTo(0, 200); x.lineTo(-62, 170); x.lineTo(-62, 236); x.closePath(); x.moveTo(0, 200); x.lineTo(62, 170); x.lineTo(62, 236); x.closePath(); x.fill();
  circ(0, 200, 14, { fill: PC.red });
  [0, 1, 2].forEach(i => circ(0, 380 + i * 80, 9, { fill: PC.gold }));
  // testa
  ell(-104, 10, 34, 48, PC.shade, PC.ink, 5); ell(104, 10, 34, 48, PC.shade, PC.ink, 5);
  ell(0, 0, 112, 138, PC.skin, PC.ink, 6);
  x.fillStyle = PC.white; [[-1], [1]].forEach(([k]) => { x.beginPath(); x.ellipse(k * 100, -38, 30, 56, k * .25, 0, Math.PI * 2); x.fill(); });
  // sopracciglia aggrottate e occhi fissi su chi guarda
  [-1, 1].forEach(k => {
    x.fillStyle = PC.white; x.strokeStyle = PC.ink; x.lineWidth = 4;
    x.beginPath(); x.moveTo(k * 18, -40); x.lineTo(k * 82, -62); x.lineTo(k * 84, -44); x.lineTo(k * 20, -26); x.closePath(); x.fill(); x.stroke();
    ell(k * 48, -6, 18, 13, PC.white, PC.ink, 3);
    circ(k * 46 - k * 4, -5, 8, { fill: PC.ink });
  });
  x.strokeStyle = PC.ink; x.lineWidth = 5; x.lineCap = 'round';
  x.beginPath(); x.moveTo(-4, 4); x.quadraticCurveTo(-18, 52, 6, 58); x.stroke();
  x.beginPath(); x.moveTo(-36, 92); x.quadraticCurveTo(0, 84, 36, 92); x.stroke();
  // pizzetto
  x.fillStyle = PC.white; x.beginPath(); x.moveTo(-46, 108); x.quadraticCurveTo(0, 124, 46, 108); x.quadraticCurveTo(28, 210, 0, 252); x.quadraticCurveTo(-28, 210, -46, 108); x.fill();
  x.strokeStyle = PC.ink; x.lineWidth = 4; x.stroke();
  // cilindro
  x.save(); x.beginPath(); x.moveTo(-104, -118); x.lineTo(-122, -380); x.lineTo(122, -380); x.lineTo(104, -118); x.closePath(); x.clip();
  for (let i = -4; i < 4; i++) { x.fillStyle = i % 2 ? PC.white : PC.red; x.fillRect(i * 34, -400, 34, 300); }
  x.fillStyle = PC.navy; x.fillRect(-140, -200, 280, 76);
  [-70, 0, 70].forEach(sx => star(sx, -162, 22, PC.white));
  x.restore();
  x.strokeStyle = PC.ink; x.lineWidth = 6; x.beginPath(); x.moveTo(-104, -118); x.lineTo(-122, -380); x.lineTo(122, -380); x.lineTo(104, -118); x.stroke();
  ell(0, -380, 122, 22, PC.white, PC.ink, 6);
  ell(0, -116, 190, 34, PC.navy, PC.ink, 6);
  // braccio e mano verso chi guarda
  if (h > 0) {
    const sh = Math.sin(t * 38) * 3 * P(h, .9, 1);
    const hx = -40 + sh, hy = 300, k = lerp(.55, 1.25, h);
    x.fillStyle = PC.navy; x.strokeStyle = PC.ink; x.lineWidth = 6;
    x.beginPath(); x.moveTo(-250, 200); x.quadraticCurveTo(-300, 330, hx - 120 * k, hy + 40 * k); x.lineTo(hx + 60 * k, hy + 120 * k); x.quadraticCurveTo(-120, 380, -150, 260); x.closePath(); x.fill(); x.stroke();
    x.save(); x.translate(hx, hy); x.scale(k, k);
    ell(-40, 70, 120, 66, PC.white, PC.ink, 5);
    x.fillStyle = PC.skin; x.strokeStyle = PC.ink; x.lineWidth = 5; rrect(-130, -70, 210, 170, 70); x.fill(); x.stroke();
    x.lineWidth = 4; [-30, 10, 50].forEach(dy => { x.beginPath(); x.moveTo(-122, dy); x.quadraticCurveTo(-60, dy + 14, 0, dy); x.stroke(); });
    x.beginPath(); x.moveTo(60, 70); x.quadraticCurveTo(110, 40, 80, -10); x.stroke();
    ell(30, -24, 78, 74, PC.skin, PC.ink, 6);
    ell(30, -44, 36, 26, '#F3DCC4', PC.ink, 3);
    x.restore();
  }
  x.restore();
}

/* ---------- scena 1 · voglio te (0 – 6.2s) ---------- */
function wantYou(t) {
  const a = 0, b = 6.2;
  if (t > b) return;
  const e = 1 - iCub(P(t, b - .4, b));
  x.save(); x.globalAlpha = e;
  sunburst(540, 760, t, P(t, .1, .7));
  kicker('ATTENZIONE,', 196, t, .3);
  const s1 = 'PICCOLA AZIENDA!', z1 = fit(s1, 900, 104);
  words(t, [[[s1.split(' ')[0], PC.navy], [s1.split(' ')[1], PC.navy]]], 540 - measure(s1, 900, z1, FD, -2) / 2, 330, 0, z1, .5, .12, .6, null);
  const rise = oCub(P(t, .2, 1.1));
  figure(540, lerp(1300, 760, rise), .92, oBack(P(t, 1.3, 2.0)), t);
  x.fillStyle = PC.paper; x.fillRect(56, 1290, W - 112, H - 56 - 1290);
  seg(56, 1290, W - 56, 1290, { col: PC.navy, lw: 6 });
  stamp('VOGLIO', 540, 1470, 190, t, 2.2, -.03, PC.red, false);
  stamp('TE!', 540, 1660, 210, t, 2.6, .02, PC.red, false);
  T('per i tuoi social.', 540, 1760, { w: 600, size: 46, fam: FD, col: PC.navy, al: 'center', a: oCub(P(t, 3.3, 3.8)) });
  x.restore();
}

/* ---------- scena 2 · il problema (6.0 – 12.4s) ---------- */
const PAINS = ['Foto da sistemare', 'Testi da inventare', 'Quando pubblicare?', 'Idee finite al martedì'];
function problem(t) {
  const a = 6.0, b = 12.4;
  if (t < a || t > b) return;
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  kicker('IL SOLITO PROBLEMA', 300, t, a + .2);
  words(t, [[['Non', PC.navy], ['hai', PC.navy], ['tempo', PC.navy]], [['per', PC.navy], ['i', PC.navy], ['social?', PC.red]]], 110, 470, 120, 110, a + .4, .09, .7, null);
  PAINS.forEach((s, i) => {
    const t0 = a + 1.4 + i * .55, p = oBack(P(t, t0, t0 + .4)), y = 760 + i * 170;
    if (p <= 0) return;
    x.save(); x.translate(540 + (1 - p) * 600, y);
    rrect(-440, 0, 880, 130, 18); x.fillStyle = PC.white; x.fill(); x.strokeStyle = PC.navy; x.lineWidth = 5; x.stroke();
    ring(-360, 65, 30, { col: PC.navy, lw: 5 });
    T(s, -300, 84, { w: 600, size: 52, fam: FD, col: PC.ink });
    const c = P(t, t0 + .8, t0 + 1.0);
    if (c > 0) { seg(-382, 43, -382 + 44 * c, 87, { col: PC.red, lw: 9 }); seg(-338, 43, -338 - 44 * P(t, t0 + .9, t0 + 1.1), 87, { col: PC.red, lw: 9 }); }
    x.restore();
  });
  stamp('BASTA!', 540, 1560, 170, t, a + 4.6, -.14, PC.red);
  x.restore();
}

/* ---------- scena 3 · il turno di notte (12.2 – 19.4s) ---------- */
const NODES = [[300, 1010, 'PC UFFICIO'], [780, 1010, 'PC CASSA'], [540, 1260, 'SERVER']];
const OUT = ['reel', 'post', 'testi', 'calendario'];
function night(t) {
  const a = 12.2, b = 19.4;
  if (t < a || t > b) return;
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  kicker('IL TURNO DI NOTTE', 300, t, a + .2);
  words(t, [[['Ci', PC.navy], ['pensiamo', PC.navy], ['noi.', PC.navy]], [['Di', PC.red], ['notte.', PC.red]]], 110, 470, 120, 110, a + .4, .09, .7, null);
  const pa = oCub(P(t, a + .9, a + 1.5));
  x.save(); x.globalAlpha *= pa;
  rrect(90, 700, 900, 720, 34); x.fillStyle = PC.navy; x.fill();
  x.save(); rrect(90, 700, 900, 720, 34); x.clip();
  for (let i = 0; i < 40; i++) { const sx = 120 + ((i * 197) % 860), sy = 730 + ((i * 113) % 640); circ(sx, sy, 2.5, { fill: PC.white, a: .35 + .35 * Math.sin(t * 3 + i) }); }
  circ(860, 800, 58, { fill: PC.paper }); circ(884, 784, 54, { fill: PC.navy });
  x.restore();
  // orologio 22:00 → 07:00
  const hrs = 9 * ioCub(P(t, a + 1.4, b - 1.6)), hh = (22 + Math.floor(hrs)) % 24, mm = Math.floor((hrs % 1) * 60);
  T(String(hh).padStart(2, '0') + ':' + String(mm).padStart(2, '0'), 140, 800, { w: 700, size: 64, col: PC.gold });
  T('i computer che hai già', 140, 850, { size: 26, col: PC.paper2 });
  [[0, 1], [1, 2], [2, 0]].forEach(([i, j], k) => {
    const [x1, y1] = NODES[i], [x2, y2] = NODES[j];
    seg(x1, y1, x2, y2, { col: '#3A4A78', lw: 4 });
    for (let q = 0; q < 2; q++) { const u = (t * .6 + k * .33 + q * .5) % 1; circ(lerp(x1, x2, u), lerp(y1, y2, u), 8, { fill: k === 1 ? PC.red : PC.gold }); }
  });
  NODES.forEach(([nx, ny, lb], k) => {
    const u = (t * .5 + k * .3) % 1;
    circ(nx, ny, 50 + u * 50, { stroke: PC.gold, lw: 3, a: 1 - u });
    rrect(nx - 56, ny - 40, 112, 74, 10); x.fillStyle = PC.paper; x.fill(); x.strokeStyle = PC.gold; x.lineWidth = 4; x.stroke();
    seg(nx - 30, ny + 52, nx + 30, ny + 52, { col: PC.paper, lw: 8 });
    T(lb, nx, ny + 96, { w: 700, size: 22, col: PC.paper, al: 'center', ls: 3 });
  });
  x.restore();
  OUT.forEach((s, i) => {
    const t0 = a + 2.6 + i * .8, p = oBack(P(t, t0, t0 + .35));
    if (p <= 0) return;
    const cx = 210 + i * 220, cy = 1500;
    const pk = P(t, t0 - .5, t0);
    if (pk < 1) circ(lerp(540, cx, pk), lerp(1260, cy, pk), 10, { fill: PC.red });
    x.save(); x.translate(cx, cy); x.scale(p, p);
    rrect(-100, -40, 200, 80, 40); x.fillStyle = PC.red; x.fill();
    T(s, 0, 11, { w: 700, size: 30, col: PC.white, al: 'center' });
    x.restore();
  });
  T('I dati restano in casa tua.', 540, 1640, { w: 600, size: 44, fam: FD, col: PC.navy, al: 'center', a: oCub(P(t, a + 5.6, a + 6.0)) });
  x.restore();
}

/* ---------- scena 4 · al mattino approvi (19.2 – 25.4s) ---------- */
function morning(t) {
  const a = 19.2, b = 25.4;
  if (t < a || t > b) return;
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  kicker('AL MATTINO', 300, t, a + .2);
  words(t, [[['Tu', PC.navy], ['approvi.', PC.navy]], [['Noi', PC.red], ['pubblichiamo.', PC.red]]], 110, 470, 120, 104, a + .4, .09, .7, null);
  const ps = oBack(P(t, a + .8, a + 1.3));
  if (ps > 0) {
    x.save(); x.translate(540, 1150); x.scale(ps, ps);
    rrect(-230, -420, 460, 840, 56); x.fillStyle = PC.navy; x.fill();
    rrect(-206, -396, 412, 792, 40); x.fillStyle = PC.white; x.fill();
    rrect(-60, -384, 120, 22, 11); x.fillStyle = PC.navy; x.fill();
    // il post proposto stanotte
    rrect(-180, -330, 360, 360, 20); x.fillStyle = PC.paper2; x.fill();
    circ(70, -230, 46, { fill: PC.gold });
    x.fillStyle = PC.red; x.beginPath(); x.moveTo(-180, 30); x.lineTo(-60, -120); x.lineTo(40, -10); x.lineTo(100, -70); x.lineTo(180, 30); x.closePath(); x.fill();
    [[-180, 70, 340], [-180, 106, 260], [-180, 142, 300]].forEach(([lx, ly, lw]) => { rrect(lx, ly, lw, 16, 8); x.fillStyle = '#CFC4AA'; x.fill(); });
    T('pronto da stanotte · da rivedere', -180, 196, { size: 18, col: PC.navy });
    // tasti
    const tap = P(t, a + 2.6, a + 2.9), ok = t >= a + 2.8;
    rrect(-180, 236, 170, 84, 42); x.fillStyle = ok ? PC.navy : PC.red; x.fill();
    T(ok ? '✓ FATTO' : '✓ APPROVA', -95, 290, { w: 700, size: 24, col: PC.white, al: 'center' });
    rrect(10, 236, 170, 84, 42); x.strokeStyle = PC.navy; x.lineWidth = 4; x.stroke();
    T('↺ ANNULLA', 95, 290, { w: 700, size: 24, col: PC.navy, al: 'center' });
    if (tap > 0 && tap < 1) circ(-95, 278, 30 + tap * 90, { stroke: PC.red, lw: 5, a: 1 - tap });
    x.restore();
    stamp('PUBBLICATO', 540, 900, 76, t, a + 3.1, -.18, PC.red);
  }
  T('Ogni passo scritto. Ogni passo annullabile.', 540, 1690, { w: 600, size: 38, fam: FD, col: PC.navy, al: 'center', a: oCub(P(t, a + 3.7, a + 4.1)) });
  x.restore();
}

/* ---------- scena 5 · chiusura (25.2 – 30s) ---------- */
function finale(t) {
  const a = 25.2;
  if (t < a) return;
  const e = oCub(P(t, a, a + .4));
  x.save(); x.globalAlpha = e;
  sunburst(540, 560, t, 1);
  figure(540, 560, .62, oBack(P(t, a + .3, a + .9)), t);
  x.fillStyle = PC.paper; x.fillRect(56, 960, W - 112, H - 56 - 960);
  seg(56, 960, W - 56, 960, { col: PC.navy, lw: 6 });
  words(t, [[['La', PC.navy], ['tua', PC.navy], ['bottega', PC.navy]], [['merita', PC.navy], ['di', PC.navy]], [['farsi', PC.red], ['vedere.', PC.red]]], 110, 1110, 116, 104, a + .5, .08, .6, null);
  const ps = oBack(P(t, a + 1.8, a + 2.2));
  if (ps > 0) {
    const lb = 'www.zerozerocomputer.it', wd = measure(lb, 700, 34, FM) + 80;
    x.save(); x.translate(540, 1560); x.scale(ps, ps); rrect(-wd / 2, -44, wd, 88, 44); x.fillStyle = PC.red; x.fill();
    T(lb, 0, 12, { w: 700, size: 34, col: PC.white, al: 'center' }); x.restore();
  }
  T('00MESH · 25 anni di sistemi e sviluppo', 540, 1680, { w: 700, size: 24, col: PC.navy, al: 'center', ls: 2, a: P(t, a + 2.4, a + 2.8) });
  x.restore();
}

const REEL = {
  date: '29.10.2026',
  tagline: 'La tua bottega merita di farsi vedere.',
  sc: [{ a: 0, b: 6.2, n: '01' }, { a: 6.0, b: 12.4, n: '02' }, { a: 12.2, b: 19.4, n: '03' }, { a: 19.2, b: 25.4, n: '04' }, { a: 25.2, b: 30, n: '05' }],
  cuts: [6.1, 12.3, 19.3, 25.3],
  layers: { bg: posterBg, intro: () => {}, outro: () => {}, hud: () => {}, cuts: posterCuts, fade: PC.paper },
  scenes: [wantYou, problem, night, morning, finale]
};
