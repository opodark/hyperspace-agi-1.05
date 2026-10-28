// SPDX-License-Identifier: Apache-2.0
/*
 * Registra un Motion Reel fotogramma per fotogramma: apre la pagina di render in
 * Chromium (Playwright), chiama window.__renderAt(t) per ogni frame e passa i PNG
 * a ffmpeg (H.264, yuv420p, faststart). Deterministico: lo stesso t dà lo stesso frame.
 *
 *   node render.js <pagina.render.html> <uscita.mp4>
 *   node render.js <pagina.render.html> <cartella> --stills 2.2,9,18.5
 *
 * Playwright si risolve dal NODE_PATH o da una node_modules vicina
 * (`npm i --no-save playwright && npx playwright install chromium`).
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  console.error('playwright non trovato: npm i --no-save playwright && npx playwright install chromium');
  process.exit(2);
}

const [page_, out, flag, list] = process.argv.slice(2);
if (!page_ || !out) { console.error('uso: node render.js <pagina.render.html> <uscita> [--stills t1,t2]'); process.exit(2); }
const FPS = 30, DUR = 30;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 700, height: 1300 } });
  let failed = false;
  page.on('pageerror', e => { failed = true; console.error('errore nella pagina:', e.message); });
  await page.goto('file://' + path.resolve(page_));
  await page.evaluate(() => window.__ready);
  if (failed) { await browser.close(); process.exit(1); }
  const grab = async t => Buffer.from((await page.evaluate(t => {
    window.__renderAt(t); return document.getElementById('cv').toDataURL('image/png');
  }, t)).split(',')[1], 'base64');

  if (flag === '--stills') {
    fs.mkdirSync(out, { recursive: true });
    for (const t of (list || '5,15,25').split(',').map(Number)) {
      fs.writeFileSync(path.join(out, `still-${t}.png`), await grab(t));
    }
  } else {
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'png', '-framerate', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(FPS), '-movflags', '+faststart', out],
      { stdio: ['pipe', 'inherit', 'inherit'] });
    for (let i = 0; i < DUR * FPS; i++) {
      const buf = await grab(i / FPS);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if ((i + 1) % FPS === 0) console.log(`frame ${i + 1}/${DUR * FPS}`); // letto dalla UI per la barra di avanzamento
    }
    ff.stdin.end();
    const code = await new Promise(r => ff.on('close', r));
    if (code !== 0) { await browser.close(); process.exit(code); }
  }
  await browser.close();
})();
