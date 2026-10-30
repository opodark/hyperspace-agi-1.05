// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "piccola-azienda-2026-10-29", "title": "Piccola azienda, assistente di notte", "aria": "Animazione di 33 secondi in infografica per i piccoli imprenditori: troppe cose da fare e i social sempre ultimi, foto testi orari e idee che superano il tempo disponibile, un assistente che di notte lavora sui computer dell'ufficio senza far uscire i dati, al mattino si guarda, si corregge, si approva, con un tasto per annullare, e la chiusura La tua bottega merita di farsi vedere.", "dur": 33}
/* Infografica sulla narrazione `integrations/moneyprinter/testi/piccola-azienda.txt` (voce clonata, 32,96 s).
   I tempi delle scene seguono le pause del parlato (ffmpeg silencedetect). Le animazioni illustrano:
   nessun numero a schermo è una misura. */

const ERR2 = '#FF6B5B';
const SOFT = '#171A1E';

/* ---------- scena 1 · troppe cose, i social ultimi (0.3 – 6.4s) ---------- */
function troppe(t) {
  const a = .3, b = 6.4;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  const kick = 'PER CHI HA UNA BOTTEGA';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .7))), 80, 330, { w: 700, size: 24, col: C.acc, ls: 3 });
  words(t, [[['Una', C.ink], ['piccola', C.ink]], [['azienda.', C.acc]], [['Mille', C.ink], ['cose', C.ink]], [['da', C.ink], ['fare.', C.ink]]],
    80, 450, 112, 104, a + .2, .09, .8, b - .5);
  const rows = ['ordini', 'clienti', 'social', 'fatture', 'magazzino', 'telefono'];
  const from = [0, 1, 2, 3, 4, 5], to = [0, 1, 5, 2, 3, 4];
  const move = ioCub(P(t, 3.7, 4.9));
  rows.forEach((name, i) => {
    const idx = lerp(from[i], to[i], move), y = 1010 + idx * 100;
    const ra = oCub(P(t, 1.2 + i * .25, 1.6 + i * .25)) * (name === 'social' ? 1 : 1);
    if (ra <= 0) return;
    const last = name === 'social' && move >= 1;
    const col = name === 'social' ? C.ac2 : C.ink;
    x.save(); x.globalAlpha *= ra;
    rrect(80, y - 40, 920, 80, 18); x.fillStyle = name === 'social' && move > 0 ? '#1B1830' : SOFT; x.fill();
    x.strokeStyle = name === 'social' ? C.ac2 : '#2C3036'; x.lineWidth = 2.5; x.stroke();
    rrect(112, y - 16, 32, 32, 8); x.strokeStyle = last ? '#4A4F55' : col; x.lineWidth = 3; x.stroke();
    T(name, 172, y + 11, { w: 700, size: 34, fam: FD, col: last ? C.dim : col });
    T(String(Math.round(idx) + 1).padStart(2, '0'), 960, y + 10, { size: 28, al: 'right', col: C.mute });
    x.restore();
  });
  if (t > 4.9) {
    const pp = oBack(P(t, 4.9, 5.3));
    pill(780, 1010 + 5 * 100, 300, 54, 'ultimo posto', { fill: '#1B1830', stroke: C.ac2, col: C.ac2, size: 26, bold: true, s: pp });
  }
  x.restore();
}

/* ---------- scena 2 · foto, testi, orari, idee (6.4 – 11.4s) ---------- */
function cose(t) {
  const a = 6.4, b = 11.4;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — IL PROBLEMA', [[['Troppe', C.ink], ['cose,', C.ink]], [['poco', C.ink], ['tempo.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const items = [['FOTO', 6.6, '▣'], ['TESTI', 7.2, '≡'], ['ORARI', 7.8, '◷'], ['IDEE', 8.35, '✦']];
  items.forEach(([n, t0, ic], i) => {
    const cx = 80 + (i % 2) * 470, cy = 820 + Math.floor(i / 2) * 200;
    const p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    x.save(); x.translate(cx + 225, cy + 80); x.scale(p, p); x.translate(-225, -80);
    rrect(0, 0, 450, 160, 26); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 2.5; x.stroke();
    circ(80, 80, 44, { fill: C.tint, stroke: C.acc, lw: 2.5 });
    T(ic, 80, 98, { w: 700, size: 46, fam: FD, al: 'center', col: C.acc });
    T(n, 150, 96, { w: 900, size: 52, fam: FD, col: C.ink, ls: -1 });
    x.restore();
  });
  // il tempo disponibile si consuma
  const ba = P(t, 9.0, 9.4);
  if (ba > 0) {
    x.save(); x.globalAlpha *= ba;
    T('TEMPO A DISPOSIZIONE', 80, 1290, { w: 700, size: 24, col: C.mute, ls: 3 });
    const drain = ioCub(P(t, 9.2, 10.9)), BX = 80, BW = 920, BY = 1330;
    rrect(BX, BY, BW, 56, 28); x.fillStyle = SOFT; x.fill(); x.strokeStyle = '#2C3036'; x.lineWidth = 2.5; x.stroke();
    const w = Math.max(56, BW * (1 - .9 * drain));
    x.save(); rrect(BX, BY, BW, 56, 28); x.clip();
    x.fillStyle = drain > .6 ? ERR2 : C.acc; x.fillRect(BX, BY, w, 56); x.restore();
    T(drain > .75 ? 'mancano ore' : 'ore del giorno', BX, BY + 120, { w: 700, size: 36, fam: FD, col: drain > .75 ? ERR2 : C.ink });
    x.restore();
  }
  x.restore();
}

/* ---------- scena 3 · di notte (11.4 – 15.7s) ---------- */
function notte(t) {
  const a = 11.4, b = 15.7;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — LA NOTTE', [[['Mentre', C.ink], ['tu', C.ink]], [['dormi,', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  // luna e stelle
  const ma = oBack(P(t, 11.8, 12.4));
  x.save(); x.translate(800, 900); x.scale(ma, ma);
  circ(0, 0, 90, { fill: C.ink }); circ(40, -22, 80, { fill: C.bg });
  x.restore();
  for (let i = 0; i < 9; i++) {
    const sx = 140 + ((i * 197) % 740), sy = 760 + ((i * 131) % 260), tw = .5 + .5 * Math.sin(t * 3 + i * 1.7);
    circ(sx, sy, 3 + (i % 3), { fill: C.ink, a: P(t, 12 + i * .08, 12.5 + i * .08) * (.35 + .5 * tw) });
  }
  // orologio notturno che avanza
  const clockA = P(t, 12.3, 12.8);
  const mins = lerp(60, 160, ioCub(P(t, 12.6, 15.4))); // 01:00 → 02:40
  const hh = String(Math.floor(mins / 60)).padStart(2, '0'), mm = String(Math.floor(mins % 60)).padStart(2, '0');
  T(hh + ':' + mm, 540, 1230, { w: 900, size: 230, fam: FD, al: 'center', col: C.ink, ls: -4, a: clockA });
  // tre computer che lavorano
  for (let i = 0; i < 3; i++) {
    const cx = 270 + i * 270, cy = 1440, p = oBack(P(t, 13.0 + i * .2, 13.5 + i * .2));
    if (p <= 0) continue;
    x.save(); x.translate(cx, cy); x.scale(p, p);
    rrect(-80, -60, 160, 110, 14); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke();
    for (let k = 0; k < 4; k++) {
      const w = 40 + 50 * (.5 + .5 * Math.sin(t * 3 + i * 2 + k * 1.3));
      x.fillStyle = C.acc; x.globalAlpha = .75; x.fillRect(-60, -40 + k * 22, w, 10);
    }
    x.globalAlpha = 1; seg(-40, 70, 40, 70, { col: '#4A4F55', lw: 6 });
    x.restore();
  }
  T('lavora qualcuno per te', 540, 1580, { size: 26, al: 'center', col: C.mute, a: P(t, 14.2, 14.7) });
  x.restore();
}

/* ---------- scena 4 · in ufficio, dati a casa (15.6 – 24.2s) ---------- */
function ufficio(t) {
  const a = 15.6, b = 24.2;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — IN UFFICIO', [[['Lavora', C.ink], ['sui', C.ink]], [['tuoi', C.ink], ['computer.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  // l'ufficio: recinto tratteggiato
  const bp = P(t, 16.1, 16.9);
  const BX = 80, BY = 810, BW = 680, BH = 520;
  x.save(); x.globalAlpha *= bp; rrect(BX, BY, BW, BH, 32); x.fillStyle = '#0B0D10'; x.fill();
  x.setLineDash([14, 12]); x.lineDashOffset = -t * 20; x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke(); x.restore();
  T('IL TUO UFFICIO', BX + 32, BY + 52, { w: 700, size: 22, col: C.acc, ls: 3, a: bp });
  const N = [[240, 1040], [600, 960], [420, 1200]];
  const na = oBack(P(t, 16.7, 17.3));
  if (na > 0) {
    seg(N[0][0], N[0][1], N[1][0], N[1][1], { col: C.line, lw: 3 }); seg(N[1][0], N[1][1], N[2][0], N[2][1], { col: C.line, lw: 3 });
    seg(N[2][0], N[2][1], N[0][0], N[0][1], { col: C.line, lw: 3 });
    for (let k = 0; k < 3; k++) {
      const u = ((t * .5) + k / 3) % 1, A = N[k], B2 = N[(k + 1) % 3];
      circ(lerp(A[0], B2[0], u), lerp(A[1], B2[1], u), 7, { fill: C.acc });
    }
    N.forEach((p, i) => {
      x.save(); x.translate(p[0], p[1]); x.scale(na, na);
      circ(0, 0, 44, { fill: C.panel, stroke: C.acc, lw: 3 });
      T(['PC 1', 'PC 2', 'PC 3'][i], 0, 8, { w: 900, size: 22, fam: FD, al: 'center' });
      x.restore();
    });
  }
  // cosa esce: post, testi, calendario
  const outs = [['post', 18.6], ['testi', 19.6], ['calendario', 20.75]];
  outs.forEach(([n, t0], i) => {
    const p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    const cx = 80 + i * 310, cy = 1400;
    x.save(); x.translate(cx + 145, cy + 50); x.scale(p, p); x.translate(-145, -50);
    rrect(0, 0, 290, 100, 22); x.fillStyle = C.tint; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 2.5; x.stroke();
    T(n, 145, 64, { w: 700, size: 34, fam: FD, al: 'center', col: C.acc });
    x.restore();
    const flow = P(t, t0 - .5, t0);
    if (flow > 0 && flow < 1) circ(lerp(N[2][0], cx + 145, oCub(flow)), lerp(N[2][1] + 40, cy, oCub(flow)), 9, { fill: C.acc });
  });
  // i dati non escono
  const da = P(t, 22.3, 22.9);
  if (da > 0) {
    // nuvola all'esterno
    const CX = 890, CY = 1010;
    x.save(); x.globalAlpha *= da;
    circ(CX - 40, CY + 6, 38, { stroke: '#4A4F55', lw: 3 }); circ(CX, CY - 22, 48, { stroke: '#4A4F55', lw: 3 }); circ(CX + 44, CY + 8, 36, { stroke: '#4A4F55', lw: 3 });
    seg(BX + BW, 1040, CX - 60, 1020, { col: ERR2, lw: 3, dash: [8, 10] });
    T('✕', (BX + BW + CX - 60) / 2, 1010, { w: 900, size: 54, fam: FD, al: 'center', col: ERR2 });
    x.restore();
    badge(t, 'I DATI RESTANO QUI', 1296, 22.5, C.acc);
  }
  x.restore();
}

/* ---------- scena 5 · al mattino (24.2 – 28.3s) ---------- */
function mattino(t) {
  const a = 24.2, b = 28.3;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — AL MATTINO', [[['Tutto', C.ink], ['pronto.', C.acc]]]);
  const e = env(t, a, b, .35, .35);
  x.save(); x.globalAlpha = e;
  const sa = oCub(P(t, 24.5, 25.1));
  // sole che sorge
  x.save(); x.beginPath(); x.rect(0, 740, W, 160); x.clip();
  circ(820, lerp(930, 830, sa), 80, { fill: C.acc, a: .9 });
  x.restore();
  T('08:30', 80, 880, { w: 900, size: 100, fam: FD, col: C.ink, ls: -2, a: P(t, 24.6, 25.1) });
  // le bozze
  const cards = [['Post del giorno', 27.7], ['Testo per il sito', 27.85], ['Calendario della settimana', 28.0]];
  cards.forEach(([n, ok], i) => {
    const y = 1000 + i * 150, ca = oCub(P(t, 24.9 + i * .2, 25.3 + i * .2));
    if (ca <= 0) return;
    const done = t >= ok, glow = done ? oBack(P(t, ok, ok + .3)) : 0;
    x.save(); x.globalAlpha *= ca;
    rrect(80, y - 55, 920, 110, 24); x.fillStyle = done ? C.tint : SOFT; x.fill(); x.strokeStyle = done ? C.acc : '#2C3036'; x.lineWidth = 2.5; x.stroke();
    T(n, 120, y + 12, { w: 700, size: 38, fam: FD, col: C.ink });
    if (done) {
      x.save(); x.translate(930, y); x.scale(glow, glow);
      circ(0, 0, 34, { fill: C.acc });
      x.strokeStyle = C.dark; x.lineWidth = 7; x.lineCap = 'round'; x.beginPath(); x.moveTo(-14, 2); x.lineTo(-3, 14); x.lineTo(16, -12); x.stroke();
      x.restore();
    } else T('da rivedere', 960, y + 10, { size: 24, al: 'right', col: C.mute });
    x.restore();
  });
  // i tre gesti
  const steps = [['GUARDI', 26.45], ['CORREGGI', 27.05], ['APPROVI', 27.6]];
  steps.forEach(([n, t0], i) => {
    const on = t >= t0, p = oBack(P(t, t0, t0 + .3));
    pill(220 + i * 320, 1530, 290, 70, n, { fill: on ? C.acc : '#14171B', stroke: on ? C.acc : '#3A3E44', col: on ? C.dark : '#9EA39A', size: 28, bold: true, s: on ? .92 + .08 * p : 1 });
  });
  x.restore();
}

/* ---------- scena 6 · il tasto annulla (28.3 – 30.8s) ---------- */
function annulla(t) {
  const a = 28.3, b = 30.8;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Qualcosa', C.ink], ['non', C.ink]], [['va?', ERR2]]], 80, 520, 130, 120, a + .1, .1, .8, b - .5);
  // la bozza sbagliata
  const cp = oBack(P(t, 28.7, 29.1)), gone = oCub(P(t, 30.15, 30.55));
  x.save(); x.translate(540, 1000); x.scale(cp, cp); x.globalAlpha *= 1 - gone;
  x.translate(-gone * 200, 0);
  rrect(-400, -80, 800, 160, 28); x.fillStyle = SOFT; x.fill(); x.strokeStyle = ERR2; x.lineWidth = 3; x.stroke();
  T('Post del giorno', -360, 14, { w: 700, size: 42, fam: FD });
  T('✕ non va', 360, 12, { w: 700, size: 34, fam: FD, al: 'right', col: ERR2 });
  x.restore();
  // il tasto
  const press = P(t, 29.8, 29.95) - P(t, 29.95, 30.15) * .0;
  const pushed = t > 29.85 && t < 30.2;
  const bs = oBack(P(t, 29.3, 29.7)) * (pushed ? .94 : 1);
  if (bs > 0) {
    x.save(); x.translate(540, 1330); x.scale(bs, bs);
    rrect(-230, -70, 460, 140, 70); x.fillStyle = pushed ? C.acc : C.tint; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 4; x.stroke();
    T('↶  ANNULLA', 0, 16, { w: 900, size: 54, fam: FD, al: 'center', col: pushed ? C.dark : C.acc, ls: 1 });
    x.restore();
    const u = P(t, 29.85, 30.5); if (u > 0 && u < 1) ring(540, 1330, 90 + u * 260, { col: C.acc, lw: 3, a: 1 - u });
  }
  T('un tasto, e si torna indietro', 540, 1520, { size: 26, al: 'center', col: C.mute, a: P(t, 30.2, 30.6) });
  x.restore();
}

/* ---------- scena 7 · chiusura (30.7 – 33s) ---------- */
function chiusura(t) {
  const a = 30.75;
  if (t < a) return;
  const e = oCub(P(t, a, a + .3));
  x.save(); x.globalAlpha = e;
  // la bottega: tenda a strisce, vetrina e porta
  const bp = oBack(P(t, a, a + .6));
  x.save(); x.translate(540, 640); x.scale(bp, bp);
  rrect(-190, -40, 380, 250, 14); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 3; x.stroke();
  for (let k = 0; k < 6; k++) {
    x.beginPath(); x.moveTo(-210 + k * 70, -150); x.lineTo(-140 + k * 70, -150); x.lineTo(-150 + k * 70, -40); x.lineTo(-200 + k * 70, -40); x.closePath();
    x.fillStyle = k % 2 ? C.ink : C.acc; x.fill();
  }
  for (let k = 0; k < 6; k++) circ(-175 + k * 70, -40, 25, { fill: k % 2 ? C.ink : C.acc });
  rrect(-150, 30, 130, 120, 10); x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke();
  rrect(30, 30, 110, 180, 10); x.fillStyle = C.tint; x.fill(); x.strokeStyle = C.acc; x.stroke();
  circ(48, 124, 7, { fill: C.acc });
  const glow = .5 + .5 * Math.sin(t * 3);
  circ(-85, 90, 30 + glow * 8, { fill: C.acc, a: .12 + .1 * glow });
  x.restore();
  words(t, [[['La', C.ink], ['tua', C.ink], ['bottega', C.acc]], [['merita', C.ink], ['di', C.ink]], [['farsi', C.ink], ['vedere.', C.acc]]], 80, 1090, 128, 116, a + .1, .12, .8);
  const ps = oBack(P(t, 32.0, 32.4));
  if (ps > 0) {
    const lb = REEL.cta, wd = measure(lb, 700, 34, FM) + 72;
    x.save(); x.translate(540, 1500); x.scale(ps, ps); rrect(-wd / 2, -42, wd, 84, 42); x.fillStyle = C.acc; x.fill();
    T(lb, 0, 12, { w: 700, size: 34, al: 'center', col: C.dark }); x.restore();
  }
  x.restore();
}

/* ---------- livelli fissi: niente intro/outro R&D, HUD con la marca ---------- */
function hudPA(t) {
  const a = P(t, .4, 1.0);
  if (a <= 0) return;
  x.save(); x.globalAlpha = a;
  logo(98, 150, t);
  T('ZEROZEROCOMPUTER', 134, 160, { w: 700, size: 26, ls: 2 });
  const bar = 1736;
  seg(80, bar, W - 80, bar, { col: C.line, lw: 4 });
  seg(80, bar, W - 80, bar, { col: C.acc, lw: 4, p: t / DUR });
  x.restore();
}

const REEL = {
  date: '29.10.2026',
  tagline: 'La tua bottega merita di farsi vedere.',
  cta: 'www.zerozerocomputer.it',
  layers: { intro: () => {}, outro: () => {}, hud: hudPA },
  sc: [{ a: .3, b: 6.4, n: '01' }, { a: 6.4, b: 11.4, n: '02' }, { a: 11.4, b: 15.7, n: '03' }, { a: 15.6, b: 24.2, n: '04' }, { a: 24.2, b: 28.3, n: '05' }, { a: 28.3, b: 30.8, n: '06' }, { a: 30.75, b: 33, n: '07' }],
  cuts: [6.45, 11.45, 15.65, 24.25, 28.35, 30.75],
  scenes: [troppe, cose, notte, ufficio, mattino, annulla, chiusura]
};
