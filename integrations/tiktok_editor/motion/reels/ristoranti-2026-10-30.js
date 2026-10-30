// SPDX-License-Identifier: Apache-2.0
// @meta {"id": "ristoranti-2026-10-30", "title": "Ristoranti, la comanda a voce", "aria": "Animazione di 35 secondi con un cameriere a fumetti: la sala è piena e lui, stressato, digita le comande sul menù digitale e sbaglia; poi preme un tasto, dice l'ordine a voce, l'assistente lo trascrive in chiaro con piatti, quantità e variazioni, il cameriere lo conferma con un tocco e l'ordine arriva subito al gestionale e alla cucina. Il microfono lavora solo quando serve e l'audio non viene conservato. Il cameriere, sereno, ha più tempo per i clienti.", "dur": 35.1}
/* Anteprima di un servizio su misura (non una funzione pronta): narrazione `integrations/moneyprinter/testi/ristoranti.txt`
   (voce clonata, 34,96 s). Tempi dalle pause del parlato. Tavolo, piatti e variazioni sono di fantasia. «Audio non conservato»
   è un requisito di progetto da rispettare nell'implementazione, non un fatto già vero. */

const ERR2 = '#FF6B5B';
const SOFT = '#171A1E';
const AMB = '#FFB454';
const SKIN = '#F4C7A1';

function dbIcon(cx, cy, w, h, col, a = 1) {
  x.save(); x.globalAlpha *= a; x.strokeStyle = col; x.lineWidth = 3.5;
  [-1, 0, 1].forEach(k => { x.beginPath(); x.ellipse(cx, cy + k * h * .5, w / 2, h * .22, 0, 0, Math.PI * 2); if (k === -1) { x.fillStyle = SOFT; x.fill(); } x.stroke(); });
  x.beginPath(); x.moveTo(cx - w / 2, cy - h * .5); x.lineTo(cx - w / 2, cy + h * .5); x.moveTo(cx + w / 2, cy - h * .5); x.lineTo(cx + w / 2, cy + h * .5); x.stroke(); x.restore();
}
function lockIcon(cx, cy, s, col, a = 1) {
  x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s);
  x.strokeStyle = col; x.lineWidth = 7; x.beginPath(); x.arc(0, -22, 26, Math.PI, 0); x.stroke();
  rrect(-40, -22, 80, 62, 12); x.fillStyle = col; x.fill(); circ(0, 8, 8, { fill: C.dark }); x.restore();
}
function micIcon(cx, cy, s, col, a = 1) {
  x.save(); x.globalAlpha *= a; x.translate(cx, cy); x.scale(s, s); x.strokeStyle = col; x.fillStyle = col; x.lineWidth = 7; x.lineCap = 'round';
  rrect(-22, -62, 44, 80, 22); x.fill(); x.beginPath(); x.arc(0, 4, 40, .1 * Math.PI, .9 * Math.PI); x.stroke();
  x.beginPath(); x.moveTo(0, 44); x.lineTo(0, 70); x.moveTo(-22, 70); x.lineTo(22, 70); x.stroke(); x.restore();
}

/* ---------- il cameriere (mood 0 stressato, 1 calmo, 2 felice) ---------- */
function waiter(cx, cy, s, mood, t, lh, rh, talk = 0) {
  x.save(); x.translate(cx, cy); x.scale(s, s);
  if (mood === 0) x.translate(Math.sin(t * 38) * 3, Math.sin(t * 23) * 2);
  else x.translate(0, Math.sin(t * 2.2) * 3);
  // braccia (dietro al busto)
  [[-1, lh], [1, rh]].forEach(([sx, h]) => {
    x.save(); x.strokeStyle = '#F2F1EA'; x.lineWidth = 40; x.lineCap = 'round'; x.beginPath(); x.moveTo(sx * 84, 120); x.lineTo(h[0], h[1]); x.stroke(); x.restore();
    circ(h[0], h[1], 24, { fill: SKIN });
  });
  // busto
  rrect(-92, 62, 184, 250, 44); x.fillStyle = '#F2F1EA'; x.fill();
  rrect(-72, 72, 144, 240, 34); x.fillStyle = '#20252B'; x.fill();
  x.beginPath(); x.moveTo(-30, 72); x.lineTo(30, 72); x.lineTo(0, 160); x.closePath(); x.fillStyle = '#F2F1EA'; x.fill();
  rrect(-80, 210, 160, 110, 16); x.fillStyle = '#ECEBE4'; x.fill();
  // farfallino
  x.beginPath(); x.moveTo(0, 90); x.lineTo(-34, 74); x.lineTo(-34, 106); x.closePath(); x.moveTo(0, 90); x.lineTo(34, 74); x.lineTo(34, 106); x.closePath(); x.fillStyle = ERR2; x.fill(); circ(0, 90, 10, { fill: '#D9503F' });
  // testa
  circ(-72, 8, 15, { fill: SKIN }); circ(72, 8, 15, { fill: SKIN }); circ(0, 0, 76, { fill: SKIN });
  if (mood === 0) circ(0, 4, 76, { fill: ERR2, a: .18 });
  x.beginPath(); x.ellipse(0, -36, 78, 46, 0, Math.PI, 2 * Math.PI); x.fillStyle = '#2A1E18'; x.fill();
  circ(0, 14, 11, { fill: '#E8A98A' });
  // occhi e sopracciglia
  if (mood === 0) {
    [-1, 1].forEach(k => { circ(k * 30, -8, 17, { fill: '#fff' }); circ(k * 30 + Math.sin(t * 30 + k) * 4, -8 + Math.cos(t * 26) * 3, 6, { fill: '#2A1E18' });
      seg(k * 52, -42, k * 14, -30, { col: '#2A1E18', lw: 7 }); });
  } else if (mood === 1) {
    [-1, 1].forEach(k => { circ(k * 30, -8, 8, { fill: '#2A1E18' }); seg(k * 50, -34, k * 14, -34, { col: '#2A1E18', lw: 6 }); });
  } else {
    [-1, 1].forEach(k => { x.save(); x.strokeStyle = '#2A1E18'; x.lineWidth = 7; x.lineCap = 'round'; x.beginPath(); x.arc(k * 30, -4, 13, 1.15 * Math.PI, 1.85 * Math.PI); x.stroke(); x.restore(); circ(k * 52, 22, 14, { fill: ERR2, a: .35 }); });
  }
  // baffi
  [-1, 1].forEach(k => { x.save(); x.translate(k * 22, 32); x.rotate(k * .25); x.beginPath(); x.ellipse(0, 0, 26, 11, 0, 0, Math.PI * 2); x.fillStyle = '#2A1E18'; x.fill(); x.restore(); });
  // bocca
  x.save();
  if (talk > 0) { x.beginPath(); x.ellipse(0, 56, 14, 4 + 9 * Math.abs(Math.sin(t * 14)), 0, 0, Math.PI * 2); x.fillStyle = '#7A2E2E'; x.fill(); }
  else if (mood === 0) { x.beginPath(); x.ellipse(0, 58, 15, 8 + 6 * Math.abs(Math.sin(t * 18)), 0, 0, Math.PI * 2); x.fillStyle = '#7A2E2E'; x.fill(); }
  else if (mood === 1) { x.strokeStyle = '#7A2E2E'; x.lineWidth = 6; x.lineCap = 'round'; x.beginPath(); x.arc(0, 46, 20, .2 * Math.PI, .8 * Math.PI); x.stroke(); }
  else { x.beginPath(); x.arc(0, 48, 26, 0, Math.PI); x.closePath(); x.fillStyle = '#7A2E2E'; x.fill(); x.beginPath(); x.rect(-18, 48, 36, 7); x.fillStyle = '#fff'; x.fill(); }
  x.restore();
  // gocce di sudore
  if (mood === 0) for (let i = 0; i < 3; i++) {
    const u = (t * 1.3 + i / 3) % 1, sx = (i - 1) * 74 + (i === 1 ? 20 : 0);
    x.save(); x.globalAlpha = 1 - u; x.translate(sx, -60 + u * 60); x.beginPath(); x.moveTo(0, -14); x.quadraticCurveTo(12, 6, 0, 12); x.quadraticCurveTo(-12, 6, 0, -14); x.fillStyle = '#7FC8FF'; x.fill(); x.restore();
  }
  x.restore();
}

/* ---------- il tablet con il menù digitale ---------- */
function tablet(cx, cy, w, h, t, mode, tint = 0) {
  x.save(); x.translate(cx, cy);
  rrect(-w / 2, -h / 2, w, h, 26); x.fillStyle = '#0B0D10'; x.fill(); x.strokeStyle = '#4A4F55'; x.lineWidth = 5; x.stroke();
  if (mode === 'chaos') {
    for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) {
      const i = r * 4 + c, hot = Math.floor(t * 9 + i * 3.7) % 5 === 0;
      rrect(-w / 2 + 22 + c * ((w - 44) / 4), -h / 2 + 24 + r * ((h - 48) / 3), (w - 44) / 4 - 10, (h - 48) / 3 - 10, 10);
      x.fillStyle = hot ? ERR2 : SOFT; x.fill(); x.strokeStyle = hot ? ERR2 : '#2C3036'; x.lineWidth = 2; x.stroke();
    }
  } else if (mode === 'rec') {
    const live = tint;
    circ(0, -10, 74, { fill: live ? ERR2 : '#2A1D1D', stroke: ERR2, lw: 5 });
    circ(0, -10, live ? 30 + 6 * Math.sin(t * 8) : 28, { fill: live ? '#fff' : ERR2 });
    T(live ? 'REGISTRA…' : 'REGISTRA', 0, h / 2 - 28, { w: 700, size: 26, al: 'center', col: live ? ERR2 : C.mute, ls: 3 });
  }
  x.restore();
}

/* ---------- scena 1 · sala piena, comande a mano (0.3 – 6.3s) ---------- */
function caos(t) {
  const a = .3, b = 6.3;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Sala', C.ink], ['piena,', AMB]], [['comande', C.ink], ['a', C.ink], ['mano.', C.ink]]], 80, 400, 104, 96, a + .15, .1, .8, b - .5);
  for (let i = 0; i < 4; i++) { // la sala si riempie
    const tx = 170 + i * 250, ty = 690, tp = oBack(P(t, .5 + i * .18, .9 + i * .18)); if (tp <= 0) continue;
    x.save(); x.translate(tx, ty); x.scale(tp, tp);
    circ(0, 0, 44, { fill: SOFT, stroke: AMB, lw: 3 }); circ(-62, 0, 16, { fill: AMB }); circ(62, 0, 16, { fill: AMB });
    const bub = .5 + .5 * Math.sin(t * 5 + i * 2);
    rrect(-38, -112, 76, 46, 18); x.fillStyle = '#E8EAE3'; x.fill();
    for (let k = 0; k < 3; k++) circ(-18 + k * 18, -89, 5 + bub * (k === 1 ? 2 : 1), { fill: '#6E736C' });
    x.restore();
  }
  // il cameriere stressato col tablet
  const wp = oBack(P(t, .8, 1.4));
  tablet(660, 1290, 380, 270, t, 'chaos');
  const tapJit = (Math.sin(t * 37) * 14), tapJ2 = Math.cos(t * 29) * 12;
  waiter(300, 1020, 1.12 * wp, 0, t, [-190 + Math.sin(t * 31) * 12, 40 + Math.cos(t * 27) * 14], [250 + tapJit, 230 + tapJ2]);
  // fogli che si accumulano
  for (let k = 0; k < 6; k++) {
    const tp = oCub(P(t, 1.5 + k * .3, 1.9 + k * .3)); if (tp <= 0) continue;
    x.save(); x.translate(130 + (k % 3) * 70, 1520 - Math.floor(k / 3) * 48 - 20 * (1 - tp)); x.rotate((k - 2.5) * .12);
    rrect(-46, -30, 92, 60, 6); x.fillStyle = '#F2F1EA'; x.globalAlpha *= tp; x.fill(); seg(-30, -10, 30, -10, { col: '#B9B8B0', lw: 4 }); seg(-30, 8, 14, 8, { col: '#B9B8B0', lw: 4 }); x.restore();
  }
  // errore
  const sp = oBack(P(t, 3.1, 3.5));
  if (sp > 0) { x.save(); x.translate(700, 960); x.rotate(-.14); x.scale(sp, sp); rrect(-150, -46, 300, 92, 14); x.fillStyle = 'rgba(7,8,10,.85)'; x.fill(); x.strokeStyle = ERR2; x.lineWidth = 7; x.stroke(); T('ERRORE!', 0, 16, { w: 900, size: 52, fam: FD, al: 'center', col: ERR2, ls: 2 }); x.restore(); }
  // la cucina ricomincia da capo
  const ka = P(t, 4.0, 4.5);
  if (ka > 0) {
    x.save(); x.globalAlpha *= ka;
    rrect(780, 1510, 220, 90, 18); x.fillStyle = SOFT; x.fill(); x.strokeStyle = C.line; x.lineWidth = 2.5; x.stroke(); T('CUCINA', 890, 1568, { w: 700, size: 26, al: 'center', col: C.mute, ls: 3 });
    x.strokeStyle = ERR2; x.lineWidth = 6; x.lineCap = 'round'; x.beginPath(); x.arc(890, 1480, 40, 1.3 * Math.PI, 3.3 * Math.PI * Math.min(1, P(t, 4.2, 5.2)) / 1.3 + 1.3 * Math.PI - .01); x.stroke();
    T('da capo', 890, 1440, { w: 700, size: 24, al: 'center', col: ERR2 });
    x.restore();
  }
  x.restore();
}

/* ---------- scena 2 · basta parlare (6.2 – 12.3s) ---------- */
function parla(t) {
  const a = 6.2, b = 12.3;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['E', C.ink], ['se', C.ink], ['bastasse', C.ink]], [['parlare?', C.acc]]], 80, 420, 108, 100, a + .15, .1, .8, b - .5);
  const press = P(t, 8.9, 9.1), live = t > 9.0 && t < 11.9;
  tablet(740, 1230, 380, 270, t, 'rec', live ? 1 : 0);
  const talk = (t > 9.0 && t < 11.9) ? 1 : 0;
  waiter(310, 1080, 1.1, 1, t, [-180, 150], t > 8.8 ? [350 - 20 * Math.max(0, Math.sin((t - 8.8) * 6)) * (t < 9.4 ? 1 : 0), 190] : [200, 230], talk);
  if (talk) for (let k = 0; k < 3; k++) { // onde della voce verso il tablet
    const u = ((t - 9.0) * 1.2 + k / 3) % 1; ring(330, 1155, 110 + u * 140, { col: C.acc, lw: 4, a: (1 - u) * .7 });
  }
  micIcon(560, 1010, .8 * P(t, 9.0, 9.4), live ? C.acc : '#4A4F55');
  // l'assistente capisce
  const ia = oBack(P(t, 10.6, 11.1));
  if (ia > 0) {
    x.save(); x.translate(740, 1010); x.scale(ia, ia);
    circ(0, 0, 54, { fill: C.tint, stroke: C.ac2, lw: 4 }); T('✦', 0, 18, { w: 700, size: 56, fam: FD, al: 'center', col: C.ac2 });
    x.restore();
    T('l\'assistente lo capisce', 740, 940, { size: 24, al: 'center', col: C.ac2, a: P(t, 10.9, 11.4) });
  }
  x.restore();
}

/* ---------- scena 3 · l'ordine in chiaro (12.3 – 18.3s) ---------- */
function ordine(t) {
  const a = 12.3, b = 18.3;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Ordine', C.ink], ['in', C.ink], ['chiaro.', C.acc]]], 80, 430, 108, 100, a + .1, .1, .8, b - .5);
  const cp = oCub(P(t, 12.4, 12.9));
  x.save(); x.globalAlpha *= cp; rrect(130, 640, 820, 640, 30); x.fillStyle = '#F2F1EA'; x.fill(); x.restore();
  if (cp > 0) {
    x.save(); x.globalAlpha *= cp;
    T('TAVOLO 7', 180, 720, { w: 900, size: 40, fam: FD, col: '#1B1D20', ls: 3 }); seg(180, 746, 900, 746, { col: '#C9C8C0', lw: 3 });
    const L = [['Margherita', '2', 12.5, ''], ['Tagliatelle al ragù', '1', 13.4, 'senza cipolla'], ['Tiramisù', '1', 14.9, '']];
    L.forEach(([n, q, t0, mod], i) => {
      const y = 830 + i * 150, p = oCub(P(t, t0, t0 + .35)); if (p <= 0) return;
      x.save(); x.globalAlpha *= p; x.translate(0, (1 - p) * 20);
      const pop = oBack(P(t, 13.45 + i * .15, 13.8 + i * .15));
      x.save(); x.translate(205, y - 12); x.scale(pop || 1, pop || 1); circ(0, 0, 30, { fill: '#5B7F0A' }); T(q, 0, 12, { w: 900, size: 36, fam: FD, al: 'center', col: '#F2F1EA' }); x.restore();
      T(n, 270, y, { w: 700, size: 40, fam: FD, col: '#1B1D20' });
      if (mod) { const vp = oBack(P(t, 14.5, 14.9)); pill(560, y + 50, 250 * vp, 46 * vp, mod, { fill: '#E9E5FF', stroke: '#7A6BE0', col: '#4B3FB0', size: 24, bold: true, s: 1 }); }
      x.restore();
    });
    x.restore();
  }
  const ck = oBack(P(t, 16.7, 17.1));
  if (ck > 0) { x.save(); x.translate(860, 1180); x.scale(ck, ck); circ(0, 0, 50, { fill: C.acc }); x.strokeStyle = C.dark; x.lineWidth = 10; x.lineCap = 'round'; x.beginPath(); x.moveTo(-20, 2); x.lineTo(-5, 18); x.lineTo(22, -16); x.stroke(); x.restore(); }
  if (t > 16.4) waiter(880, 1560, .5 * oBack(P(t, 16.5, 17)), 2, t, [-130, 130], [130, 130]);
  x.restore();
}

/* ---------- scena 4 · conferma, gestionale, cucina (18.4 – 24.7s) ---------- */
function conferma(t) {
  const a = 18.4, b = 24.7;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Un', C.ink], ['tocco.', C.acc]], [['Poi', C.ink], ['parte.', C.ink]]], 80, 420, 108, 100, a + .1, .1, .8, b - .5);
  const pushed = t > 19.3 && t < 19.7, bp = oBack(P(t, 18.6, 19.0)) * (pushed ? .94 : 1);
  if (bp > 0) { x.save(); x.translate(540, 840); x.scale(bp, bp); rrect(-230, -50, 460, 100, 50); x.fillStyle = t > 19.3 ? C.acc : C.tint; x.fill(); x.strokeStyle = C.acc; x.lineWidth = 4; x.stroke();
    T('✓  CONFERMA', 0, 14, { w: 900, size: 42, fam: FD, al: 'center', col: t > 19.3 ? C.dark : C.acc, ls: 1 }); x.restore();
    const u = P(t, 19.3, 19.9); if (u > 0 && u < 1) ring(540, 840, 80 + u * 220, { col: C.acc, lw: 3, a: 1 - u }); }
  // flusso: scontrino → gestionale → cucina
  const nodes = [[540, 1090, 'GESTIONALE'], [540, 1390, 'CUCINA']];
  nodes.forEach(([nx, ny, lb], i) => {
    const p = oBack(P(t, 19.6 + i * .3, 20.0 + i * .3)); if (p <= 0) return;
    const lit = t > (i ? 23.2 : 21.8);
    x.save(); x.translate(nx, ny); x.scale(p, p);
    rrect(-250, -90, 500, 180, 30); x.fillStyle = lit ? C.tint : SOFT; x.fill(); x.strokeStyle = lit ? C.acc : '#2C3036'; x.lineWidth = 3; x.stroke();
    T(lb, -80, 14, { w: 900, size: 40, fam: FD, col: C.ink, ls: -1 });
    if (i === 0) dbIcon(-170, 0, 70, 60, lit ? C.acc : C.mute);
    else { rrect(-205, -34, 70, 54, 8); x.strokeStyle = lit ? C.acc : C.mute; x.lineWidth = 4; x.stroke(); circ(-170, -46, 18, { fill: lit ? C.acc : C.mute }); }
    x.restore();
  });
  arrow(540, 900, 540, 995, oCub(P(t, 20.0, 20.6)), C.acc);
  arrow(540, 1190, 540, 1295, oCub(P(t, 22.1, 22.7)), C.acc);
  [[900, 1000, 20.6, 21.7], [1195, 1300, 22.7, 23.3]].forEach(([y0, y1, t0, t1]) => {
    const u = P(t, t0, t1); if (u > 0 && u < 1) { rrect(500, lerp(y0, y1, oCub(u)) - 16, 80, 32, 6); x.fillStyle = '#F2F1EA'; x.fill(); }
  });
  T('subito', 540, 1560, { w: 700, size: 34, fam: FD, al: 'center', col: C.acc, a: P(t, 23.4, 24.0) });
  x.restore();
}

/* ---------- scena 5 · il microfono solo quando serve (24.9 – 29.4s) ---------- */
function privacy(t) {
  const a = 24.9, b = 29.4;
  if (t < a || t > b) return;
  const e = env(t, a, b, .3, .4);
  x.save(); x.globalAlpha = e;
  words(t, [[['Solo', C.ink], ['quando', C.ink]], [['serve.', C.acc]]], 80, 420, 108, 100, a + .1, .1, .8, b - .5);
  const on = t > 25.2 && t < 26.6;
  const ma = oBack(P(t, 25.0, 25.4));
  x.save(); x.translate(300, 1020); x.scale(ma, ma);
  circ(0, 0, 120, { fill: SOFT, stroke: on ? C.acc : '#2C3036', lw: 4 }); micIcon(0, 0, 1.4, on ? C.acc : '#4A4F55');
  if (on) for (let k = 0; k < 2; k++) { const u = ((t * .9) + k / 2) % 1; ring(0, 0, 120 + u * 70, { col: C.acc, lw: 3, a: 1 - u }); }
  x.restore();
  T(on ? 'ATTIVO' : 'SPENTO', 300, 1200, { w: 700, size: 30, al: 'center', col: on ? C.acc : C.mute, ls: 4, a: P(t, 25.2, 25.5) });
  // onda audio che sparisce
  const wa = P(t, 27.3, 27.6), dis = oCub(P(t, 28.0, 28.8));
  if (wa > 0) {
    x.save(); x.globalAlpha *= wa;
    for (let k = 0; k < 14; k++) {
      const hgt = (18 + 46 * Math.abs(Math.sin(k * 1.7 + 1))) * (1 - dis), dy = dis * (40 + k * 6);
      rrect(560 + k * 28, 1020 - hgt / 2 + dy, 14, Math.max(4, hgt), 6); x.fillStyle = C.ac2; x.globalAlpha = wa * (1 - dis * .8); x.fill();
    }
    x.globalAlpha = wa; T('audio scartato', 760, 1170, { w: 700, size: 30, fam: FD, al: 'center', col: C.ink });
    T('non conservato', 760, 1210, { size: 24, al: 'center', col: C.mute });
    x.restore();
    lockIcon(940, 900, .8 * oBack(P(t, 28.3, 28.7)), C.acc);
  }
  x.restore();
}

/* ---------- scena 6 · chiusura con il cameriere sereno (29.4 – 35.1s) ---------- */
function chiusura(t) {
  const a = 29.4;
  if (t < a) return;
  const e = oCub(P(t, a, a + .3));
  x.save(); x.globalAlpha = e;
  const wp = oBack(P(t, a, a + .6));
  circ(540, 760, 230 * wp, { fill: C.tint, a: .6 });
  waiter(540, 700, 1.25 * wp, 2, t, [-190, 110 + Math.sin(t * 2) * 6], [190, 110 + Math.cos(t * 2) * 6]);
  words(t, [[['Meno', C.ink], ['corse.', C.acc]]], 80, 1230, 104, 96, 29.6, .1, .7);
  words(t, [[['Meno', C.ink], ['errori.', C.ac2]]], 80, 1340, 104, 96, 31.9, .1, .7);
  words(t, [[['Più', C.ink], ['tempo', C.acc], ['per', C.ink]], [['i', C.ink], ['clienti.', C.ink]]], 80, 1450, 96, 88, 33.3, .09, .7);
  const ps = oBack(P(t, 34.1, 34.5));
  if (ps > 0) { const lb = REEL.cta, wd = measure(lb, 700, 30, FM) + 64; x.save(); x.translate(540, 1620); x.scale(ps, ps); rrect(-wd / 2, -36, wd, 72, 36); x.fillStyle = C.acc; x.fill(); T(lb, 0, 10, { w: 700, size: 30, al: 'center', col: C.dark }); x.restore(); }
  x.restore();
}

function hudRI(t) {
  const a = P(t, .4, 1.0);
  if (a <= 0) return;
  x.save(); x.globalAlpha = a;
  logo(98, 150, t); T('ZEROZEROCOMPUTER', 134, 160, { w: 700, size: 26, ls: 2 });
  const bar = 1736;
  seg(80, bar, W - 80, bar, { col: C.line, lw: 4 }); seg(80, bar, W - 80, bar, { col: C.acc, lw: 4, p: t / DUR });
  x.restore();
}

const REEL = {
  date: '30.10.2026',
  tagline: 'Più tempo per i clienti.',
  cta: 'www.zerozerocomputer.it',
  layers: { intro: () => {}, outro: () => {}, hud: hudRI },
  sc: [{ a: .3, b: 6.3, n: '01' }, { a: 6.2, b: 12.3, n: '02' }, { a: 12.3, b: 18.3, n: '03' }, { a: 18.4, b: 24.7, n: '04' }, { a: 24.9, b: 29.4, n: '05' }, { a: 29.4, b: 35.1, n: '06' }],
  cuts: [6.25, 12.35, 18.35, 24.75, 29.45],
  scenes: [caos, parla, ordine, conferma, privacy, chiusura]
};
