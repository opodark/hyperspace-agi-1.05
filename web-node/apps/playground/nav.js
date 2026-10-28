// SPDX-License-Identifier: Apache-2.0
/* HyperSpace · barra di navigazione condivisa del cockpit locale (:8090).
   Sostituisce i link del menu in ogni pagina con lo stesso elenco, nello stesso ordine.
   I pulsanti specifici della pagina (es. Debug Console, Suono) restano in coda.
   Sul sito pubblico non fa nulla: lì valgono i menu originali. */
(function () {
  const h = location.hostname;
  const isLocal = h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1' ||
    h.endsWith('.local') || h.endsWith('.ts.net') || /^\d{1,3}(\.\d{1,3}){3}$/.test(h);
  if (!isLocal) return;

  const LINKS = [
    { href: '/', icon: '🚀', label: 'Cockpit' },
    { href: '/missions.html', icon: '📡', label: 'Missioni' },
    { href: '/research.html', icon: '🧬', label: 'R&D Lab' },
    { href: '/dialogues.html', icon: '💬', label: 'Dialoghi' },
    { href: '/analytics.html', icon: '🏛️', label: 'Storico' },
    { href: '/seo.html', icon: '🌐', label: 'SEO' },
    { href: '/devstudio.html', icon: '⚡', label: 'HyperDev', loopbackOnly: true },
    { sep: true },
    { href: '/commercial.html', icon: '💼', label: 'Commercial' },
    { href: '/arcade.html', icon: '🕹️', label: 'Arcade' },
    { href: '/lite.html', icon: '📱', label: 'Lite' }
  ];
  const loopback = h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1';

  const css = `
    .hs-nav{display:flex;align-items:center;gap:4px;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;
      max-width:100%;font:500 12px 'Plus Jakarta Sans',system-ui,sans-serif;padding:2px}
    .hs-nav::-webkit-scrollbar{display:none}
    .hs-nav a{display:inline-flex;align-items:center;gap:6px;white-space:nowrap;padding:6px 10px;border-radius:9px;
      color:#94a3b8;text-decoration:none;border:1px solid transparent;
      transition:color .2s,background .2s,border-color .2s}
    .hs-nav a:hover{color:#e2e8f0;background:rgba(30,41,59,.6)}
    .hs-nav a[aria-current="page"]{color:#f1f5f9;background:rgba(87,230,217,.10);border-color:rgba(87,230,217,.28)}
    .hs-nav a span{font-size:13px;line-height:1}
    .hs-nav .hs-sep{width:1px;height:18px;background:rgba(148,163,184,.2);margin:0 4px;flex:none}
    .hs-nav>button{flex:none;white-space:nowrap}
    @media (prefers-reduced-motion:reduce){.hs-nav a{transition:none}}`;

  function findContainer() {
    const header = document.querySelector('header');
    if (!header) return null;
    const nav = header.querySelector('nav');
    if (nav) return nav;
    // Pagine senza <nav>: prendo il blocco dell'header che contiene più link
    let best = null, max = 0;
    header.querySelectorAll('div').forEach(d => {
      const n = [...d.children].filter(c => c.tagName === 'A').length;
      if (n > max) { max = n; best = d; }
    });
    return max >= 2 ? best : null;
  }

  function build() {
    const box = findContainer();
    if (!box || box.dataset.hsNav) return;
    const keep = [...box.children].filter(c => c.tagName === 'BUTTON');
    const path = location.pathname === '/index.html' ? '/' : location.pathname;
    box.innerHTML = LINKS.filter(l => !l.loopbackOnly || loopback).map(l => l.sep
      ? '<i class="hs-sep" aria-hidden="true"></i>'
      : `<a href="${l.href}"${l.href === path ? ' aria-current="page"' : ''}><span>${l.icon}</span>${l.label}</a>`).join('');
    keep.forEach(b => box.appendChild(b));
    box.className = 'hs-nav';
    box.dataset.hsNav = '1';
    box.setAttribute('aria-label', 'Navigazione cockpit');
    const st = document.createElement('style'); st.id = 'hs-nav-style'; st.textContent = css;
    document.head.appendChild(st);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
