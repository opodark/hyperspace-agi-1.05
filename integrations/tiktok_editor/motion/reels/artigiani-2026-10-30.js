// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "artigiani-2026-10-30", "title": "Artigiani, assistente che cerca e prepara", "aria": "Animazione di 36 secondi in infografica per artigiani e lavoratori autonomi: imbianchini, idraulici e meccanici perdono ore al computer; un assistente cerca nuove tecniche e nuovi fornitori, mette a confronto i prezzi, prepara il preventivo con i listini più recenti da controllare, tiene le scadenze e ordina fatture e bolle di carico, gira sul computer dell'artigiano, ogni proposta è una bozza e decide sempre lui. Chiusura: Tu pensa al cantiere. Le carte, a lui.", "dur": 36.4}
/* Infografica sulla narrazione `integrations/moneyprinter/testi/artigiani.txt` (voce clonata, 36,32 s).
   Tempi: pause del parlato (ffmpeg silencedetect). Fornitori, voci e confronti sono di fantasia: le animazioni
   illustrano, non misurano; nessun prezzo reale a schermo. */

const ERR2 = '#FF6B5B';
const SOFT = '#171A1E';
const AMB = '#FFB454';

function lockIcon(cx, cy, s, col, a = 1) {
  x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s);
  x.strokeStyle = col; x.lineWidth = 7; x.beginPath(); x.arc(0, -22, 26, Math.PI, 0); x.stroke();
  rrect(-40, -22, 80, 62, 12); x.fillStyle = col; x.fill(); circ(0, 8, 8, { fill: C.dark });
  x.restore();
}
function iconRoller(cx, cy, col) { // rullo da imbianchino
  x.save(); x.translate(cx, cy); x.strokeStyle = col; x.fillStyle = col; x.lineWidth = 7; x.lineCap = 'round'; x.lineJoin = 'round';
  rrect(-52, -48, 96, 38, 12); x.fill();
  x.beginPath(); x.moveTo(44, -29); x.lineTo(62, -29); x.lineTo(62, 8); x.lineTo(0, 8); x.lineTo(0, 22); x.stroke();
  rrect(-10, 22, 20, 44, 6); x.fill(); x.restore();
}
function iconWrench(cx, cy, col) { // chiave inglese
  x.save(); x.translate(cx, cy); x.rotate(.8); x.fillStyle = col;
  rrect(-11, 4, 22, 84, 10); x.fill(); circ(0, -22, 38, { fill: col });
  rrect(-15, -76, 30, 50, 6); x.fillStyle = '#0B0D10'; x.fill(); x.restore();
}
function iconGear(cx, cy, col, rot) { // ingranaggio
  x.save(); x.translate(cx, cy); x.rotate(rot); x.fillStyle = col;
  for (let i = 0; i < 8; i++) { x.save(); x.rotate(i * Math.PI / 4); rrect(-11, -58, 22, 24, 5); x.fill(); x.restore(); }
  circ(0, 0, 44, { fill: col }); circ(0, 0, 18, { fill: C.bg }); x.restore();
}
function mag(cx, cy, s, col, a = 1) { // lente
  x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s); x.strokeStyle = col; x.lineWidth = 10; x.lineCap = 'round';
  x.beginPath(); x.arc(0, 0, 40, 0, Math.PI * 2); x.stroke(); x.beginPath(); x.moveTo(30, 30); x.lineTo(70, 70); x.stroke(); x.restore();
}

/* ---------- scena 1 · lavori con le mani (0.5 – 5.5s) ---------- */
function mestieri(t) {
  const a = .5, b = 5.5;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  const kick = 'ARTIGIANI E AUTONOMI';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .7))), 80, 330, { w: 700, size: 24, col: C.acc, ls: 3 });
  words(t, [[['Lavori', C.ink], ['con', C.ink]], [['le', C.ink], ['mani.', C.acc]]], 80, 450, 112, 104, a + .2, .1, .8, b - .5);
  const M = [['imbianchini', 'r', C.acc, .9], ['idraulici', 'w', C.ac2, 1.7], ['meccanici', 'g', AMB, 2.5]];
  M.forEach(([n, k, col, t0], i) => {
    const y = 800 + i * 220, p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    x.save(); x.translate(540, y + 85); x.scale(p, p); x.translate(-540, -y - 85);
    rrect(80, y, 920, 170, 30); x.fillStyle = SOFT; x.fill(); x.strokeStyle = col; x.lineWidth = 2.5; x.stroke();
    circ(190, y + 85, 62, { fill: '#0B0D10', stroke: col, lw: 2.5 });
    if (k === 'r') iconRoller(190, y + 82, col); else if (k === 'w') iconWrench(190, y + 88, col); else iconGear(190, y + 85, col, t * .8);
    T(n, 300, y + 108, { w: 900, size: 62, fam: FD, col: C.ink, ls: -1 });
    x.restore();
  });
  x.restore();
}

/* ---------- scena 2 · ma il computer ruba ore (5.4 – 9.3s) ---------- */
function computer(t) {
  const a = 5.4, b = 9.3;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Ma', C.ink], ['le', C.ink], ['ore', C.ink]], [['finiscono', C.ink]], [['al', C.ink], ['computer.', ERR2]]], 80, 480, 112, 104, a + .1, .1, .8, b - .5);
  // monitor con pile di carte
  const mp = oBack(P(t, 6.0, 6.5));
  x.save(); x.translate(540, 1050); x.scale(mp, mp);
  rrect(-260, -150, 520, 310, 24); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 4; x.stroke();
  ['preventivi', 'fatture', 'ricerche', 'scadenze'].forEach((n, i) => {
    const pa = oCub(P(t, 6.4 + i * .35, 6.8 + i * .35));
    T(n, -220, -90 + i * 62, { size: 30, col: C.ink, a: pa });
    rrect(60, -108 + i * 62, 150 * pa, 24, 12); x.fillStyle = [C.acc, C.ac2, AMB, ERR2][i]; x.fill();
  });
  seg(-60, 190, 60, 190, { col: '#4A4F55', lw: 8 }); x.restore();
  // ore che passano
  const da = P(t, 7.4, 7.9);
  if (da > 0) {
    x.save(); x.globalAlpha *= da;
    T('LA TUA GIORNATA', 80, 1370, { w: 700, size: 22, col: C.mute, ls: 3 });
    rrect(80, 1400, 920, 50, 25); x.fillStyle = SOFT; x.fill(); x.strokeStyle = '#2C3036'; x.lineWidth = 2.5; x.stroke();
    const w = 920 * (.25 + .5 * ioCub(P(t, 7.6, 8.9)));
    x.save(); rrect(80, 1400, 920, 50, 25); x.clip(); x.fillStyle = C.ac2; x.fillRect(80, 1400, 360, 50); x.fillStyle = ERR2; x.fillRect(440, 1400, Math.max(0, w - 360), 50); x.restore();
    T('cantiere', 100, 1484, { size: 24, col: C.mute }); T('computer', 80 + w - 20, 1484, { size: 24, al: 'right', col: ERR2, a: P(t, 8.5, 8.9) });
    x.restore();
  }
  x.restore();
}

/* ---------- scena 3 · un assistente cerca per te (9.2 – 15.4s) ---------- */
function cerca(t) {
  const a = 9.2, b = 15.4;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — CERCA PER TE', [[['Un', C.ink], ['assistente', C.ink]], [['che', C.ink], ['cerca.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const cx = 540, cy = 1000, ma = oBack(P(t, 9.8, 10.4));
  for (let k = 0; k < 3; k++) { const u = ((t - 10.2) * .5 + k / 3) % 1; if (t > 10.2) ring(cx, cy, 60 + u * 260, { col: C.acc, lw: 3, a: (1 - u) * .6 }); }
  mag(cx - 30, cy - 30, 1.5 * ma, C.acc);
  const chips = [['nuove tecniche', 11.8, 250, 830], ['nuovi fornitori', 14.0, 830, 1160]];
  chips.forEach(([n, t0, px, py], i) => {
    const p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    seg(cx, cy, lerp(cx, px, .0 + p), lerp(cy, py, p), { col: C.line, lw: 3, a: .8 });
    pill(px, py, 330, 80, n, { fill: C.tint, stroke: C.acc, col: C.acc, size: 30, bold: true, s: p });
  });
  x.restore();
}

/* ---------- scena 4 · i prezzi a confronto (15.3 – 17.5s) ---------- */
function prezzi(t) {
  const a = 15.3, b = 17.5;
  if (t < a || t > b) return;
  const e = env(t, a, b, .25, .3);
  x.save(); x.globalAlpha = e;
  words(t, [[['Prezzi', C.ink], ['a', C.ink]], [['confronto.', C.acc]]], 80, 480, 112, 104, a + .05, .08, .6, b - .35);
  T('STESSO MATERIALE, TRE FORNITORI', 80, 840, { w: 700, size: 22, col: C.mute, ls: 3, a: P(t, a + .3, a + .6) });
  [['Fornitore A', .86, ERR2], ['Fornitore B', .62, C.acc], ['Fornitore C', .74, C.ac2]].forEach(([n, f, col], i) => {
    const y = 900 + i * 150, g = oCub(P(t, a + .4 + i * .2, a + 1.1 + i * .2));
    T(n, 80, y + 10, { w: 700, size: 30, fam: FD });
    rrect(80, y + 30, 920, 54, 27); x.fillStyle = SOFT; x.fill();
    x.save(); rrect(80, y + 30, 920, 54, 27); x.clip(); x.fillStyle = col; x.fillRect(80, y + 30, 920 * f * g, 54); x.restore();
    if (i === 1 && g >= .99) pill(900, y + 57, 190, 44, 'più basso', { fill: C.dark, stroke: C.acc, col: C.acc, size: 22, bold: true });
  });
  x.restore();
}

/* ---------- scena 5 · il preventivo (17.3 – 23.5s) ---------- */
function preventivo(t) {
  const a = 17.3, b = 23.5;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — IL PREVENTIVO', [[['Preventivo', C.ink]], [['da', C.ink], ['controllare.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const cp = oCub(P(t, 17.8, 18.4));
  x.save(); x.globalAlpha *= cp; rrect(120, 790, 840, 640, 28); x.fillStyle = '#F2F1EA'; x.fill(); x.restore();
  if (cp > 0) {
    x.save(); x.globalAlpha *= cp;
    T('PREVENTIVO', 170, 860, { w: 900, size: 40, fam: FD, col: '#1B1D20', ls: 3 });
    seg(170, 886, 910, 886, { col: '#C9C8C0', lw: 3 });
    [['Materiali', 'listino recente', 18.9], ['Manodopera', 'ore previste', 19.7], ['Trasporto', 'distanza', 20.5]].forEach(([n, sub, t0], i) => {
      const y = 960 + i * 110, p = oCub(P(t, t0, t0 + .4)); if (p <= 0) return;
      x.save(); x.globalAlpha *= p; T(n, 170, y, { w: 700, size: 36, fam: FD, col: '#1B1D20' }); T(sub, 170, y + 36, { size: 24, col: '#6B6D70' });
      rrect(640, y - 32, 270, 18, 9); x.fillStyle = '#D9D8D0'; x.fill(); rrect(640, y - 32, 270 * p * (.5 + .2 * i), 18, 9); x.fillStyle = '#5B7F0A'; x.fill(); x.restore();
    });
    x.restore();
  }
  // timbro e tasto
  const sp = oBack(P(t, 21.7, 22.1));
  if (sp > 0) { x.save(); x.translate(700, 1340); x.rotate(-.1); x.scale(sp, sp); rrect(-190, -44, 380, 88, 14); x.strokeStyle = C.ac2; x.lineWidth = 6; x.stroke(); T('DA CONTROLLARE', 0, 14, { w: 900, size: 34, fam: FD, al: 'center', col: C.ac2, ls: 2 }); x.restore(); }
  pill(310, 1540, 440, 84, 'CONTROLLA TU', { fill: t > 22.6 ? C.acc : '#14171B', stroke: t > 22.6 ? C.acc : '#3A3E44', col: t > 22.6 ? C.dark : '#9EA39A', size: 32, bold: true, s: oBack(P(t, 22.1, 22.5)) });
  x.restore();
}

/* ---------- scena 6 · scadenze, fatture, bolle (23.6 – 28.3s) ---------- */
function carte(t) {
  const a = 23.6, b = 28.3;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — IN ORDINE', [[['Scadenze,', C.ink]], [['fatture,', C.ink], ['bolle.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const cols = [['SCADENZE', C.acc, 23.8], ['FATTURE', C.ac2, 25.35], ['BOLLE DI CARICO', AMB, 26.6]];
  cols.forEach(([n, col, t0], i) => {
    const y = 800 + i * 230, p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    x.save(); x.translate(540, y + 95); x.scale(p, p); x.translate(-540, -y - 95);
    rrect(80, y, 920, 190, 28); x.fillStyle = SOFT; x.fill(); x.strokeStyle = col; x.lineWidth = 2.5; x.stroke();
    T(n, 120, y + 62, { w: 700, size: 24, col, ls: 3 });
    for (let k = 0; k < 5; k++) { // cartelle ordinate
      const q = oCub(P(t, t0 + .3 + k * .12, t0 + .6 + k * .12));
      rrect(120 + k * 170, y + 90, 140, 70 * q, 12); x.fillStyle = C.tint; x.fill(); x.strokeStyle = col; x.lineWidth = 2; x.stroke();
      if (q > .9) { seg(140 + k * 170, y + 114, 230 + k * 170, y + 114, { col, lw: 4, a: .7 }); seg(140 + k * 170, y + 136, 200 + k * 170, y + 136, { col, lw: 4, a: .4 }); }
    }
    x.restore();
  });
  x.restore();
}

/* ---------- scena 7 · sul tuo computer, una bozza (28.2 – 33.6s) ---------- */
function sulTuo(t) {
  const a = 28.2, b = 33.6;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Sul', C.ink], ['tuo', C.acc]], [['computer.', C.ink]]], 80, 480, 112, 104, a + .1, .1, .8, b - .5);
  const bp = P(t, 28.5, 29.2);
  x.save(); x.globalAlpha *= bp; rrect(130, 760, 820, 380, 36); x.fillStyle = '#0B0D10'; x.fill();
  x.setLineDash([14, 12]); x.lineDashOffset = -t * 20; x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke(); x.restore();
  x.save(); x.globalAlpha *= bp; rrect(260, 830, 360, 230, 18); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 4; x.stroke();
  for (let k = 0; k < 4; k++) seg(290, 870 + k * 44, 290 + (k % 2 ? 190 : 270), 870 + k * 44, { col: C.acc, lw: 8, a: .5 + .1 * k });
  x.restore();
  lockIcon(750, 960, 1.4 * oBack(P(t, 29.0, 29.5)), C.acc);
  // bozza + decidi tu
  const cp = oBack(P(t, 29.9, 30.3));
  if (cp > 0) {
    x.save(); x.translate(540, 1300); x.scale(cp, cp);
    rrect(-420, -90, 840, 180, 26); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 3; x.stroke();
    T('Preventivo · Bianchi', -380, -10, { w: 700, size: 38, fam: FD }); T('proposta dell\'assistente', -380, 40, { size: 26, col: C.mute });
    const sp = oBack(P(t, 30.6, 31.0)); if (sp > 0) { x.save(); x.translate(250, 10); x.rotate(-.1); x.scale(sp, sp); rrect(-110, -34, 220, 68, 12); x.strokeStyle = C.ac2; x.lineWidth = 5; x.stroke(); T('BOZZA', 0, 14, { w: 900, size: 38, fam: FD, al: 'center', col: C.ac2, ls: 4 }); x.restore(); }
    x.restore();
  }
  pill(540, 1500, 420, 84, 'DECIDI TU', { fill: t > 32.2 ? C.acc : '#14171B', stroke: t > 32.2 ? C.acc : '#3A3E44', col: t > 32.2 ? C.dark : '#9EA39A', size: 34, bold: true, s: oBack(P(t, 31.6, 32.0)) });
  x.restore();
}

/* ---------- scena 8 · chiusura (33.5 – 36.4s) ---------- */
function chiusura(t) {
  const a = 33.5;
  if (t < a) return;
  const e = oCub(P(t, a, a + .3));
  x.save(); x.globalAlpha = e;
  const hp = oBack(P(t, a, a + .6)); // casco da cantiere
  x.save(); x.translate(540, 600); x.scale(hp, hp);
  x.beginPath(); x.arc(0, 40, 130, Math.PI, 0); x.closePath(); x.fillStyle = AMB; x.fill();
  rrect(-34, -96, 68, 140, 14); x.fillStyle = '#E39A2D'; x.fill();
  rrect(-190, 40, 380, 34, 17); x.fillStyle = AMB; x.fill();
  x.restore();
  words(t, [[['Tu', C.ink], ['pensa', C.ink]], [['al', C.ink], ['cantiere.', C.acc]]], 80, 900, 118, 108, a + .1, .1, .7);
  words(t, [[['Le', C.ink], ['carte,', C.ink]], [['a', C.ink], ['lui.', C.ac2]]], 80, 1170, 118, 108, 34.85, .1, .7);
  const ps = oBack(P(t, 35.3, 35.7));
  if (ps > 0) {
    const lb = REEL.cta, wd = measure(lb, 700, 34, FM) + 72;
    x.save(); x.translate(540, 1560); x.scale(ps, ps); rrect(-wd / 2, -42, wd, 84, 42); x.fillStyle = C.acc; x.fill();
    T(lb, 0, 12, { w: 700, size: 34, al: 'center', col: C.dark }); x.restore();
  }
  x.restore();
}

function hudAR(t) {
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
  date: '30.10.2026',
  tagline: 'Tu pensa al cantiere. Le carte, a lui.',
  cta: 'www.zerozerocomputer.it',
  layers: { intro: () => {}, outro: () => {}, hud: hudAR },
  sc: [{ a: .5, b: 5.5, n: '01' }, { a: 5.4, b: 9.3, n: '02' }, { a: 9.2, b: 15.4, n: '03' }, { a: 15.3, b: 17.5, n: '04' }, { a: 17.3, b: 23.5, n: '05' }, { a: 23.6, b: 28.3, n: '06' }, { a: 28.2, b: 33.6, n: '07' }, { a: 33.5, b: 36.4, n: '08' }],
  cuts: [5.45, 9.25, 15.35, 17.35, 23.6, 28.25, 33.55],
  scenes: [mestieri, computer, cerca, prezzi, preventivo, carte, sulTuo, chiusura]
};
