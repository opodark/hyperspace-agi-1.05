// SPDX-License-Identifier: Apache-2.0
/* ---------- player ---------- */
const btn = document.getElementById('play'), scrub = document.getElementById('scrub'), timeEl = document.getElementById('time');
const iPlay = document.getElementById('i-play'), iPause = document.getElementById('i-pause');
let reduce = false; try { reduce = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}
let playing = !reduce, cur = reduce ? 29.3 : 0, t0 = performance.now() - cur * 1000, dirty = true;
function setPlaying(v) {
  playing = v; iPlay.hidden = v; iPause.hidden = !v; btn.setAttribute('aria-label', v ? 'Pausa' : 'Riproduci');
  t0 = performance.now() - cur * 1000;
}
btn.addEventListener('click', () => setPlaying(!playing));
document.getElementById('restart').addEventListener('click', () => { cur = 0; t0 = performance.now(); dirty = true; if (!playing) setPlaying(true); });
scrub.addEventListener('input', () => { cur = parseFloat(scrub.value); t0 = performance.now() - cur * 1000; dirty = true; });
function loop(now) {
  if (playing) { cur = ((now - t0) / 1000) % DUR; dirty = true; }
  if (dirty) { frame(cur); scrub.value = cur.toFixed(2); timeEl.textContent = cur.toFixed(1).padStart(4, '0') + ' / 30 s'; dirty = false; }
  requestAnimationFrame(loop);
}
const fontsReady = Promise.all(['900 40px MeshDisplay', '600 40px MeshDisplay', '500 40px MeshDisplay', '400 20px MeshMono', '700 20px MeshMono']
  .map(f => document.fonts.load(f).catch(() => null)));
window.__renderAt = frame;
window.__ready = fontsReady;
fontsReady.then(() => { setPlaying(playing); requestAnimationFrame(loop); });
