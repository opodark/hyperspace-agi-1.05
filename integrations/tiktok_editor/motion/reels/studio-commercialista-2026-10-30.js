// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "studio-commercialista-2026-10-30", "title": "Studio commercialista, assistente di notte", "aria": "Animazione di 42 secondi in infografica per gli studi commercialisti: il calendario delle scadenze per cliente, documenti mancanti, estratti conto da riconciliare e pratiche in attesa di firma, un assistente che di notte sui computer dello studio confronta il gestionale con le pratiche aperte, prepara il calendario e le richieste di documenti, i dati dei clienti che restano in studio, ogni segnalazione come bozza da rivedere e annullare, e la chiusura Più tempo per consigliare i clienti.", "dur": 42.3}
/* Infografica sulla narrazione `integrations/moneyprinter/testi/studio-commercialista.txt` (voce clonata, 42,24 s).
   Tempi: pause del parlato (ffmpeg silencedetect). Nomi di clienti, scadenze e differenze sono di fantasia:
   le animazioni illustrano, non misurano. */

const ERR2 = '#FF6B5B';
const SOFT = '#171A1E';
const CLI = [['Rossi srl', C.acc], ['Bianchi snc', C.ac2], ['Verdi & C.', '#FFB454']];

function dbIcon(cx, cy, w, h, col, a = 1) {
  x.save(); x.globalAlpha *= a; x.strokeStyle = col; x.lineWidth = 3.5;
  [[-1, 0], [0, 0], [1, 0]].forEach(([k]) => {
    const y = cy + k * h * .5;
    x.beginPath(); x.ellipse(cx, y - (k === -1 ? 0 : 0), w / 2, h * .22, 0, 0, Math.PI * 2);
    if (k === -1) { x.fillStyle = SOFT; x.fill(); }
    x.stroke();
  });
  x.beginPath(); x.moveTo(cx - w / 2, cy - h * .5); x.lineTo(cx - w / 2, cy + h * .5); x.moveTo(cx + w / 2, cy - h * .5); x.lineTo(cx + w / 2, cy + h * .5); x.stroke();
  x.restore();
}
function lockIcon(cx, cy, s, col, a = 1) {
  x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s);
  x.strokeStyle = col; x.lineWidth = 7; x.beginPath(); x.arc(0, -22, 26, Math.PI, 0); x.stroke();
  rrect(-40, -22, 80, 62, 12); x.fillStyle = col; x.fill();
  circ(0, 8, 8, { fill: C.dark });
  x.restore();
}

/* ---------- scena 1 · le scadenze, cliente per cliente (0.4 – 5.9s) ---------- */
function scadenze(t) {
  const a = .4, b = 5.9;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  const kick = 'STUDIO COMMERCIALISTA';
  T(kick.slice(0, Math.floor(kick.length * P(t, a + .1, a + .7))), 80, 330, { w: 700, size: 24, col: C.acc, ls: 3 });
  words(t, [[['Vivere', C.ink], ['di', C.ink]], [['scadenze.', C.acc]]], 80, 450, 112, 104, a + .2, .1, .8, b - .5);
  // calendario
  const X0c = 80, Y0c = 740, cw = 131, ch = 96, ca = oCub(P(t, 1.0, 1.6));
  x.save(); x.globalAlpha *= ca;
  ['L', 'M', 'M', 'G', 'V', 'S', 'D'].forEach((d, i) => T(d, X0c + i * cw + cw / 2, Y0c - 14, { w: 700, size: 22, al: 'center', col: C.mute }));
  for (let r = 0; r < 5; r++) for (let c = 0; c < 7; c++) {
    const day = r * 7 + c + 1; if (day > 31) continue;
    rrect(X0c + c * cw + 4, Y0c + r * ch + 4, cw - 8, ch - 8, 14); x.fillStyle = SOFT; x.fill();
    T(String(day), X0c + c * cw + 18, Y0c + r * ch + 36, { size: 22, col: '#6E736C' });
  }
  x.restore();
  // scadenze: (giorno, cliente, istante)
  const D = [[3, 0, 1.6], [6, 1, 1.9], [10, 2, 2.15], [12, 0, 2.4], [16, 1, 2.6], [16, 2, 2.7], [19, 0, 2.9], [24, 1, 3.7], [26, 2, 4.0], [27, 0, 4.3], [30, 1, 4.6]];
  D.forEach(([day, k, t0]) => {
    const p = oBack(P(t, t0, t0 + .35)); if (p <= 0) return;
    const r = Math.floor((day - 1) / 7), c = (day - 1) % 7, off = [0, 0, 0][k];
    const cx = X0c + c * cw + cw / 2 + (k - 1) * 26, cy = Y0c + r * ch + 62;
    const hi = t > 3.5 ? 1 : 0;
    circ(cx, cy, 13 * p + hi * 2, { fill: CLI[k][1] });
  });
  // legenda: ogni cliente
  CLI.forEach(([n, col], i) => {
    const la = oCub(P(t, 3.7 + i * .5, 4.1 + i * .5)); if (la <= 0) return;
    x.save(); x.globalAlpha *= la;
    circ(110 + i * 320, 1380, 14, { fill: col });
    T(n, 140 + i * 320, 1390, { w: 700, size: 30, fam: FD, col: C.ink });
    x.restore();
  });
  T('ognuno con le sue', 80, 1480, { size: 26, col: C.mute, a: oCub(P(t, 4.9, 5.4)) });
  x.restore();
}

/* ---------- scena 2 · cosa si inceppa (5.8 – 12.3s) ---------- */
function problemi(t) {
  const a = 5.8, b = 12.3;
  if (t < a || t > b) return;
  header(t, a, b, '01', '01 — CHE COSA SI INCEPPA', [[['Le', C.ink], ['carte', C.ink]], [['che', C.ink], ['mancano.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const items = [['Documenti', 'che mancano', '▤', 6.0], ['Estratti conto', 'da riconciliare', '⇄', 7.7], ['Pratiche ferme', 'in attesa di una firma', '✎', 9.9]];
  items.forEach(([h, sub, ic, t0], i) => {
    const y = 840 + i * 200, p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    x.save(); x.translate(540, y + 80); x.scale(p, p); x.translate(-540, -y - 80);
    rrect(80, y, 920, 160, 28); x.fillStyle = SOFT; x.fill(); x.strokeStyle = '#2C3036'; x.lineWidth = 2.5; x.stroke();
    circ(170, y + 80, 48, { fill: C.tint, stroke: C.acc, lw: 2.5 });
    T(ic, 170, y + 100, { w: 700, size: 52, fam: FD, al: 'center', col: C.acc });
    T(h, 250, y + 78, { w: 900, size: 48, fam: FD, col: C.ink, ls: -1 });
    T(sub, 250, y + 124, { size: 28, col: C.mute });
    const pulse = 1 + .08 * Math.sin(t * 6 + i);
    circ(930, y + 80, 30 * pulse, { fill: ERR2 });
    T('!', 930, y + 96, { w: 900, size: 44, fam: FD, al: 'center', col: C.dark });
    x.restore();
  });
  x.restore();
}

/* ---------- scena 3 · di notte, in studio (12.3 – 17.95s) ---------- */
function notte(t) {
  const a = 12.3, b = 17.95;
  if (t < a || t > b) return;
  header(t, a, b, '02', '02 — LA NOTTE', [[['E', C.ink], ['se', C.ink], ['di', C.ink], ['notte', C.acc]], [['controllasse', C.ink], ['lui?', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const ma = oBack(P(t, 12.7, 13.3));
  x.save(); x.translate(820, 880); x.scale(ma, ma); circ(0, 0, 80, { fill: C.ink }); circ(36, -20, 72, { fill: C.bg }); x.restore();
  for (let i = 0; i < 9; i++) {
    const sx = 140 + ((i * 197) % 740), sy = 760 + ((i * 131) % 240), tw = .5 + .5 * Math.sin(t * 3 + i * 1.7);
    circ(sx, sy, 3 + (i % 3), { fill: C.ink, a: P(t, 13 + i * .08, 13.5 + i * .08) * (.35 + .5 * tw) });
  }
  const mins = lerp(60, 160, ioCub(P(t, 13.4, 17.2)));
  T(String(Math.floor(mins / 60)).padStart(2, '0') + ':' + String(Math.floor(mins % 60)).padStart(2, '0'), 540, 1220, { w: 900, size: 210, fam: FD, al: 'center', col: C.ink, ls: -4, a: P(t, 13.2, 13.7) });
  // lo studio: tre postazioni che lavorano
  for (let i = 0; i < 3; i++) {
    const cx = 270 + i * 270, cy = 1420, p = oBack(P(t, 14.4 + i * .25, 14.9 + i * .25)); if (p <= 0) continue;
    x.save(); x.translate(cx, cy); x.scale(p, p);
    rrect(-80, -60, 160, 110, 14); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke();
    for (let k = 0; k < 4; k++) { x.fillStyle = C.acc; x.globalAlpha = .75; x.fillRect(-60, -40 + k * 22, 40 + 50 * (.5 + .5 * Math.sin(t * 3 + i * 2 + k * 1.3)), 10); }
    x.globalAlpha = 1; seg(-40, 70, 40, 70, { col: '#4A4F55', lw: 6 }); x.restore();
  }
  T('i computer dello studio', 540, 1570, { size: 26, al: 'center', col: C.mute, a: P(t, 15.6, 16.2) });
  x.restore();
}

/* ---------- scena 4 · gestionale contro pratiche (17.9 – 22.9s) ---------- */
function confronto(t) {
  const a = 17.9, b = 22.9;
  if (t < a || t > b) return;
  header(t, a, b, '03', '03 — IL CONFRONTO', [[['Gestionale', C.ink]], [['contro', C.ink], ['pratiche.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const pa = oCub(P(t, 18.3, 18.9));
  const rows = ['Rossi srl', 'Bianchi snc', 'Verdi & C.', 'Neri snc'], bad = [1, 3];
  [['GESTIONALE', 80], ['PRATICHE APERTE', 600]].forEach(([lab, px], side) => {
    x.save(); x.globalAlpha *= pa;
    rrect(px, 830, 400, 560, 28); x.fillStyle = '#0B0D10'; x.fill(); x.strokeStyle = side ? C.ac2 : C.acc; x.lineWidth = 3; x.stroke();
    T(lab, px + 28, 884, { w: 700, size: 22, col: side ? C.ac2 : C.acc, ls: 3 });
    if (!side) dbIcon(px + 340, 880, 56, 44, C.acc); else T('▤', px + 340, 894, { w: 700, size: 46, fam: FD, al: 'center', col: C.ac2 });
    rows.forEach((n, i) => {
      const y = 960 + i * 100;
      rrect(px + 20, y, 360, 76, 16); x.fillStyle = SOFT; x.fill();
      T(n, px + 44, y + 48, { w: 700, size: 30, fam: FD, col: C.ink });
    });
    x.restore();
  });
  // linee di confronto
  rows.forEach((n, i) => {
    const y = 998 + i * 100, t0 = 19.0 + i * .45, p = oCub(P(t, t0, t0 + .4));
    if (p <= 0) return;
    const isBad = bad.includes(i), flag = isBad ? oBack(P(t, 21.0 + (i === 3 ? .4 : 0), 21.4 + (i === 3 ? .4 : 0))) : 0;
    seg(480, y, 600, y, { col: isBad && flag > 0 ? ERR2 : C.acc, lw: 5, p, dash: isBad && flag > 0 ? [8, 8] : null });
    if (!isBad || flag <= 0) { if (p >= 1) circ(540, y, 11, { fill: C.acc }); }
    else { circ(540, y, 26 * flag, { fill: C.bg, stroke: ERR2, lw: 3 }); T('≠', 540, y + 13, { w: 900, size: 38, fam: FD, al: 'center', col: ERR2, a: flag }); }
  });
  const ba = P(t, 21.8, 22.2);
  if (ba > 0) badge(t, 'DIFFERENZE SEGNALATE', 1480, 21.8, ERR2);
  x.restore();
}

/* ---------- scena 5 · calendario e richieste (22.8 – 29.1s) ---------- */
function calendario(t) {
  const a = 22.8, b = 29.1;
  if (t < a || t > b) return;
  header(t, a, b, '04', '04 — IL PREPARATO', [[['Calendario', C.ink]], [['e', C.ink], ['richieste.', C.acc]]]);
  const e = env(t, a, b, .35, .4);
  x.save(); x.globalAlpha = e;
  const obl = [['F24', 'IVA'], ['IVA', 'Redditi'], ['F24', 'Bilancio']];
  CLI.forEach(([n, col], i) => {
    const y = 790 + i * 130, p = oCub(P(t, 23.3 + i * .55, 23.8 + i * .55)); if (p <= 0) return;
    x.save(); x.globalAlpha *= p; x.translate(-40 * (1 - p), 0);
    rrect(80, y, 920, 104, 22); x.fillStyle = SOFT; x.fill(); x.strokeStyle = col; x.lineWidth = 2.5; x.stroke();
    circ(124, y + 52, 14, { fill: col });
    T(n, 156, y + 64, { w: 700, size: 34, fam: FD, col: C.ink });
    obl[i].forEach((o, k) => pill(660 + k * 175, y + 52, 160, 52, o, { fill: '#0B0D10', stroke: col, col: C.ink, size: 22 }));
    x.restore();
  });
  T('RICHIESTE DI DOCUMENTI', 80, 1270, { w: 700, size: 22, col: C.mute, ls: 3, a: P(t, 25.9, 26.4) });
  CLI.forEach(([n, col], i) => {
    const t0 = 26.4 + i * .8, p = oBack(P(t, t0, t0 + .4)); if (p <= 0) return;
    const cx = 80 + i * 310;
    x.save(); x.translate(cx + 145, 1390); x.scale(p, p); x.translate(-145, -90);
    rrect(0, 0, 290, 180, 22); x.fillStyle = C.tint; x.fill(); x.strokeStyle = col; x.lineWidth = 2.5; x.stroke();
    T('✉', 30, 66, { w: 700, size: 46, fam: FD, col });
    T(n, 30, 112, { w: 700, size: 28, fam: FD, col: C.ink });
    pill(145, 148, 150, 38, 'bozza', { fill: '#0B0D10', stroke: col, col, size: 20 });
    x.restore();
  });
  x.restore();
}

/* ---------- scena 6 · i dati restano in studio (29.2 – 32.3s) ---------- */
function privacy(t) {
  const a = 29.2, b = 32.3;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .35);
  x.save(); x.globalAlpha = e;
  words(t, [[['I', C.ink], ['dati', C.ink], ['dei', C.ink]], [['clienti', C.acc], ['restano', C.ink]], [['in', C.ink], ['studio.', C.acc]]], 80, 480, 112, 104, a + .1, .1, .8, b - .5);
  const bp = P(t, 29.7, 30.4);
  x.save(); x.globalAlpha *= bp; rrect(130, 920, 640, 440, 36); x.fillStyle = '#0B0D10'; x.fill();
  x.setLineDash([14, 12]); x.lineDashOffset = -t * 20; x.strokeStyle = C.acc; x.lineWidth = 3; x.stroke(); x.restore();
  T('LO STUDIO', 170, 982, { w: 700, size: 22, col: C.acc, ls: 3, a: bp });
  dbIcon(340, 1130, 150, 130, C.acc, oCub(P(t, 30.2, 30.7)));
  lockIcon(590, 1160, 1.5 * oBack(P(t, 30.6, 31.1)), C.acc);
  const ca = P(t, 30.9, 31.4);
  if (ca > 0) {
    const CX = 900, CY = 1060; x.save(); x.globalAlpha *= ca;
    circ(CX - 36, CY + 8, 34, { stroke: '#4A4F55', lw: 3 }); circ(CX, CY - 20, 44, { stroke: '#4A4F55', lw: 3 }); circ(CX + 40, CY + 8, 32, { stroke: '#4A4F55', lw: 3 });
    seg(770, 1120, 850, 1080, { col: ERR2, lw: 3, dash: [8, 10] });
    T('✕', 810, 1090, { w: 900, size: 50, fam: FD, al: 'center', col: ERR2 }); x.restore();
  }
  x.restore();
}

/* ---------- scena 7 · una bozza: rivedi, annulla (32.2 – 37.9s) ---------- */
function bozza(t) {
  const a = 32.2, b = 37.9;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Ogni', C.ink], ['segnalazione', C.ink]], [['è', C.ink], ['una', C.ink], ['bozza.', C.acc]]], 80, 500, 112, 92, a + .1, .1, .8, b - .5);
  const cp = oBack(P(t, 32.5, 32.9)), gone = oCub(P(t, 36.95, 37.4));
  x.save(); x.translate(540, 1000); x.scale(cp, cp); x.globalAlpha *= 1 - gone; x.translate(-gone * 220, 0);
  rrect(-420, -110, 840, 220, 28); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 3; x.stroke();
  T('Differenza: Bianchi snc', -380, -30, { w: 700, size: 40, fam: FD, col: C.ink });
  T('gestionale ≠ pratica aperta', -380, 22, { size: 28, col: C.mute });
  const sp = oBack(P(t, 33.5, 33.9));
  if (sp > 0) { x.save(); x.translate(250, 40); x.rotate(-.12); x.scale(sp, sp); rrect(-110, -34, 220, 68, 12); x.strokeStyle = C.ac2; x.lineWidth = 5; x.stroke(); T('BOZZA', 0, 14, { w: 900, size: 40, fam: FD, al: 'center', col: C.ac2, ls: 4 }); x.restore(); }
  x.restore();
  // rivedi tu
  const on1 = t >= 34.55;
  pill(310, 1290, 400, 84, 'RIVEDI TU', { fill: on1 ? C.acc : '#14171B', stroke: on1 ? C.acc : '#3A3E44', col: on1 ? C.dark : '#9EA39A', size: 32, bold: true, s: oBack(P(t, 33.9, 34.3)) * (on1 ? 1 : .96) });
  // annulla
  const pushed = t > 36.85 && t < 37.2, bs = oBack(P(t, 35.6, 36.0)) * (pushed ? .94 : 1);
  if (bs > 0) {
    x.save(); x.translate(760, 1290); x.scale(bs, bs);
    rrect(-190, -42, 380, 84, 42); x.fillStyle = pushed ? C.acc : C.tint; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 4; x.stroke();
    T('↶  ANNULLA', 0, 12, { w: 900, size: 34, fam: FD, al: 'center', col: pushed ? C.dark : C.acc, ls: 1 });
    x.restore();
    const u = P(t, 36.85, 37.5); if (u > 0 && u < 1) ring(760, 1290, 70 + u * 220, { col: C.acc, lw: 3, a: 1 - u });
  }
  T('decidi sempre tu', 540, 1460, { size: 26, al: 'center', col: C.mute, a: P(t, 35.3, 35.8) });
  x.restore();
}

/* ---------- scena 8 · chiusura (37.8 – 42.3s) ---------- */
function chiusura(t) {
  const a = 37.8;
  if (t < a) return;
  const e = oCub(P(t, a, a + .3));
  x.save(); x.globalAlpha = e;
  // pratica chiusa: cartella con spunta
  const fp = oBack(P(t, a, a + .6));
  x.save(); x.translate(540, 560); x.scale(fp, fp);
  rrect(-170, -90, 340, 220, 20); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 3; x.stroke();
  x.beginPath(); x.moveTo(-170, -90); x.lineTo(-170, -130); x.lineTo(-40, -130); x.lineTo(0, -90); x.closePath(); x.fillStyle = C.acc; x.fill();
  circ(0, 20, 54, { fill: C.acc });
  x.strokeStyle = C.dark; x.lineWidth = 11; x.lineCap = 'round'; x.beginPath(); x.moveTo(-24, 22); x.lineTo(-6, 42); x.lineTo(28, 0); x.stroke();
  x.restore();
  words(t, [[['Più', C.ink], ['tempo', C.acc]], [['per', C.ink], ['consigliare.', C.ink]]], 80, 900, 118, 106, a + .15, .1, .8);
  words(t, [[['Meno', C.ink], ['carte', C.ac2]], [['da', C.ink], ['inseguire.', C.ink]]], 80, 1170, 118, 106, 40.15, .1, .8);
  const ps = oBack(P(t, 41.0, 41.4));
  if (ps > 0) {
    const lb = REEL.cta, wd = measure(lb, 700, 34, FM) + 72;
    x.save(); x.translate(540, 1560); x.scale(ps, ps); rrect(-wd / 2, -42, wd, 84, 42); x.fillStyle = C.acc; x.fill();
    T(lb, 0, 12, { w: 700, size: 34, al: 'center', col: C.dark }); x.restore();
  }
  x.restore();
}

function hudCS(t) {
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
  tagline: 'Più tempo per consigliare i clienti.',
  cta: 'www.zerozerocomputer.it',
  layers: { intro: () => {}, outro: () => {}, hud: hudCS },
  sc: [{ a: .4, b: 5.9, n: '01' }, { a: 5.8, b: 12.3, n: '02' }, { a: 12.3, b: 17.95, n: '03' }, { a: 17.9, b: 22.9, n: '04' }, { a: 22.8, b: 29.1, n: '05' }, { a: 29.2, b: 32.3, n: '06' }, { a: 32.2, b: 37.9, n: '07' }, { a: 37.8, b: 42.3, n: '08' }],
  cuts: [5.85, 12.35, 17.95, 22.85, 29.15, 32.25, 37.85],
  scenes: [scadenze, problemi, notte, confronto, calendario, privacy, bozza, chiusura]
};
