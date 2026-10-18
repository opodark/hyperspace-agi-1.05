// SPDX-License-Identifier: Apache-2.0
// web-node/src/anna-mascot.js
// Mascotte anime interattiva di Anna (Shimeji Web Companion) per 00MESH / HyperSpace.
//
// Ispirata all'identità canonica di Anna (data/persona-anna.json):
// - Corpo virtuale 2D dichiarato in puro stile flat anime (ChickMixFlat v1.0).
// - Capelli neri con sfumature/punte viola ed ahoge reattivo.
// - Cyber-headset con LED di stato connesso alla salute della mesh.
// - Fisica procedurale: cammina, corre, salta sulle card, si siede sui bordi,
//   si fa trascinare con drag & drop e cade con gravità.
// - Fumetti manga contestuali legati alla tokenomics, ai nodi e alla privacy.
// - Rispetto assoluto di prefers-reduced-motion e scorciatoia Alt+Shift+A.

(function (global) {
  'use strict';

  // Configurazione e flag
  const STORAGE_KEY = 'hyperspace.anna.mascot';
  const SHORTCUT = 'Alt+Shift+A';

  // Citazioni contestuali di Anna (coerenti con persona-anna.json e 00MESH)
  const ANNA_QUOTES = [
    "Ciao! Sono Anna, la presenza digitale di HyperSpace! ✨",
    "Psst... lo sai che la nostra rete gira su nodi GPU decentralizzati e liberi?",
    "Io e mia sorella Aurora teniamo d'occhio la mesh: tutto operativo!",
    "Se colleghi la tua GPU o il browser puoi minare $00MESH in Proof-of-Useful-Work!",
    "Ehi, attento a dove clicchi! ...scherzo, esplora pure quanto vuoi! 😄",
    "Nessun server centrale, nessuna censura: la vera sovranità digitale è questa.",
    "Bello quassù! Se mi trascini in alto adoro sentire il vento nei capelli virtuali.",
    "Hai già collegato il tuo wallet Phantom o Solflare nella sezione Tokenomics?",
    "Non sono un oracolo infallibile, ma se hai domande curiose sono sempre qui!",
    "Ti piace il mio outfit cyber-techwear? Ispirato ai colori di 00MESH! 💜",
    "Che bella community di nodi attivi oggi! Sentiti a casa tua."
  ];

  // Helper per memoria locale
  function getStoredState() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || {};
    } catch (e) {
      return {};
    }
  }

  function saveStoredState(patch) {
    try {
      const current = getStoredState();
      const updated = Object.assign(current, patch);
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      return updated;
    } catch (e) {
      return patch;
    }
  }

  // Verifica supporto e preferenze utente
  const stored = getStoredState();
  const urlParam = new URLSearchParams(global.location?.search || '').get('anna');
  const prefersReduced = Boolean(
    global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  let isEnabled = true;
  if (urlParam === 'off') {
    isEnabled = false;
    saveStoredState({ enabled: false });
  } else if (urlParam === 'on') {
    isEnabled = true;
    saveStoredState({ enabled: true });
  } else if (typeof stored.enabled === 'boolean') {
    isEnabled = stored.enabled;
  } else if (prefersReduced) {
    isEnabled = false; // Non invasiva se l'utente preferisce poco movimento
  }

  // Costruzione Mascotte
  class AnnaMascot {
    constructor() {
      this.enabled = isEnabled;
      this.isSleeping = false;
      this.quotesEnabled = stored.quotes !== false;

      // Coordinate fisiche
      this.width = 72;
      this.height = 96;
      this.x = Math.max(40, (global.innerWidth || 1024) - 220);
      this.y = (global.innerHeight || 768) - this.height - 20;
      this.vx = 0;
      this.vy = 0;
      this.facing = -1; // -1 = sinistra, 1 = destra
      this.targetX = this.x;
      this.state = 'idle'; // 'idle', 'walk', 'run', 'sit', 'drag', 'fall'
      this.stateTimer = 0;

      // Dragging
      this.isDragging = false;
      this.dragStartX = 0;
      this.dragStartY = 0;
      this.dragOffsetX = 0;
      this.dragOffsetY = 0;
      this.hasMovedDrag = false;

      // Dialoghi
      this.quoteTimeout = null;
      this.activeQuote = null;

      // Animazione loop
      this.lastFrameTime = performance.now();
      this.animFrameId = null;

      this.initDOM();
      this.bindEvents();

      if (this.enabled) {
        this.start();
        // Saluto iniziale dopo 1.5s
        setTimeout(() => {
          if (this.enabled && !this.isSleeping) {
            this.speak("Ehi ciao! Sono Anna. Fai un giro nella mesh con me! 💜");
          }
        }, 1500);
      }
    }

    initDOM() {
      if (document.getElementById('anna-mascot-container')) return;

      // Stili CSS isolati della mascotte
      const style = document.createElement('style');
      style.id = 'anna-mascot-style';
      style.textContent = `
        #anna-mascot-container {
          position: fixed;
          top: 0;
          left: 0;
          width: 100vw;
          height: 100vh;
          pointer-events: none;
          z-index: 99998;
          overflow: hidden;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        .anna-avatar-wrapper {
          position: absolute;
          width: 72px;
          height: 96px;
          pointer-events: auto;
          cursor: grab;
          user-select: none;
          touch-action: none;
          transform-origin: bottom center;
          transition: filter 0.2s ease;
          filter: drop-shadow(0 6px 12px rgba(0, 0, 0, 0.45));
        }

        .anna-avatar-wrapper:active {
          cursor: grabbing;
        }

        .anna-avatar-wrapper.anna-sleeping {
          position: fixed;
          bottom: 16px;
          right: 16px;
          top: auto !important;
          left: auto !important;
          width: 48px;
          height: 48px;
          cursor: pointer;
          border-radius: 50%;
          background: rgba(13, 20, 40, 0.85);
          border: 1px solid #9a7cff;
          box-shadow: 0 4px 16px rgba(154, 124, 255, 0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          transform: none !important;
          transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        .anna-avatar-wrapper.anna-sleeping:hover {
          transform: scale(1.1) !important;
          border-color: #57e6d9;
        }

        .anna-sleep-badge {
          display: none;
          font-size: 22px;
          user-select: none;
        }

        .anna-avatar-wrapper.anna-sleeping .anna-sleep-badge {
          display: block;
        }

        .anna-avatar-wrapper.anna-sleeping svg {
          display: none;
        }

        /* Ombra a terra */
        .anna-ground-shadow {
          position: absolute;
          bottom: -4px;
          left: 14px;
          width: 44px;
          height: 8px;
          background: rgba(7, 11, 24, 0.55);
          border-radius: 50%;
          filter: blur(2px);
          transition: transform 0.1s ease, opacity 0.1s ease;
        }

        .anna-avatar-wrapper.is-airborne .anna-ground-shadow {
          transform: scale(0.6);
          opacity: 0.2;
        }

        /* SVG Animazioni dei componenti */
        .anna-svg {
          width: 100%;
          height: 100%;
          overflow: visible;
        }

        /* Ahoge bobbing */
        .anna-ahoge {
          transform-origin: 36px 16px;
          animation: ahogeSway 2.4s ease-in-out infinite alternate;
        }

        @keyframes ahogeSway {
          0% { transform: rotate(-5deg); }
          100% { transform: rotate(8deg); }
        }

        /* Respirazione idle */
        .state-idle .anna-torso {
          animation: annaBreathe 3s ease-in-out infinite alternate;
          transform-origin: 36px 65px;
        }

        @keyframes annaBreathe {
          0% { transform: translateY(0); }
          100% { transform: translateY(-1.5px) scale(1.01); }
        }

        /* Sbattimento ciglia */
        .anna-eye {
          transform-origin: center;
          animation: annaBlink 4.2s infinite;
        }

        @keyframes annaBlink {
          0%, 96%, 100% { transform: scaleY(1); }
          98% { transform: scaleY(0.1); }
        }

        /* Walk cycle */
        .state-walk .anna-leg-left {
          animation: walkLegL 0.4s ease-in-out infinite alternate;
          transform-origin: 30px 72px;
        }
        .state-walk .anna-leg-right {
          animation: walkLegR 0.4s ease-in-out infinite alternate;
          transform-origin: 42px 72px;
        }
        .state-walk .anna-head {
          animation: walkBob 0.2s ease-in-out infinite alternate;
        }

        @keyframes walkLegL {
          0% { transform: rotate(-18deg) translateY(-2px); }
          100% { transform: rotate(18deg) translateY(0); }
        }
        @keyframes walkLegR {
          0% { transform: rotate(18deg) translateY(0); }
          100% { transform: rotate(-18deg) translateY(-2px); }
        }
        @keyframes walkBob {
          0% { transform: translateY(0); }
          100% { transform: translateY(-2px); }
        }

        /* Run cycle */
        .state-run .anna-leg-left {
          animation: walkLegL 0.24s ease-in-out infinite alternate;
          transform-origin: 30px 72px;
        }
        .state-run .anna-leg-right {
          animation: walkLegR 0.24s ease-in-out infinite alternate;
          transform-origin: 42px 72px;
        }
        .state-run .anna-head {
          animation: walkBob 0.12s ease-in-out infinite alternate;
        }

        /* Dragged pose */
        .state-drag .anna-arm-left {
          transform: rotate(140deg);
          transform-origin: 26px 54px;
        }
        .state-drag .anna-arm-right {
          transform: rotate(-140deg);
          transform-origin: 46px 54px;
        }
        .state-drag .anna-mouth-surprised {
          opacity: 1 !important;
        }
        .state-drag .anna-mouth-smile {
          opacity: 0 !important;
        }

        /* Sit pose */
        .state-sit .anna-leg-left {
          transform: rotate(-75deg) translateY(3px);
          transform-origin: 30px 72px;
        }
        .state-sit .anna-leg-right {
          transform: rotate(-65deg) translateY(3px);
          transform-origin: 42px 72px;
        }

        /* Fumetto Manga */
        .anna-bubble {
          position: absolute;
          bottom: 104px;
          left: 50%;
          transform: translateX(-50%) scale(0.95);
          background: rgba(13, 20, 40, 0.94);
          border: 1px solid #57e6d9;
          box-shadow: 0 8px 24px rgba(7, 11, 24, 0.6), 0 0 16px rgba(87, 230, 217, 0.25);
          border-radius: 12px;
          padding: 10px 14px;
          color: #f4f6ff;
          font-size: 12px;
          line-height: 1.45;
          max-width: 230px;
          min-width: 140px;
          pointer-events: auto;
          opacity: 0;
          transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
          z-index: 99999;
          backdrop-filter: blur(8px);
        }

        .anna-bubble.show {
          opacity: 1;
          transform: translateX(-50%) scale(1);
        }

        .anna-bubble::after {
          content: "";
          position: absolute;
          bottom: -6px;
          left: 50%;
          transform: translateX(-50%) rotate(45deg);
          width: 10px;
          height: 10px;
          background: rgba(13, 20, 40, 0.94);
          border-right: 1px solid #57e6d9;
          border-bottom: 1px solid #57e6d9;
        }

        .anna-bubble-close {
          position: absolute;
          top: 3px;
          right: 6px;
          cursor: pointer;
          color: #9ba9c7;
          font-size: 11px;
          line-height: 1;
        }
        .anna-bubble-close:hover {
          color: #ff8295;
        }

        /* Mini-dock dei comandi contestuali (sotto l'avatar) */
        .anna-controls {
          position: absolute;
          bottom: -22px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          gap: 4px;
          opacity: 0;
          pointer-events: none;
          transition: opacity 0.2s ease;
        }

        .anna-avatar-wrapper:hover .anna-controls {
          opacity: 1;
          pointer-events: auto;
        }

        .anna-btn-pill {
          background: rgba(13, 20, 40, 0.85);
          border: 1px solid #263454;
          color: #cbd6ef;
          border-radius: 8px;
          padding: 2px 5px;
          font-size: 9.5px;
          cursor: pointer;
          white-space: nowrap;
          transition: all 0.15s ease;
        }
        .anna-btn-pill:hover {
          background: #263454;
          color: #57e6d9;
          border-color: #57e6d9;
        }

        /* Effetti Particellari */
        .anna-particle {
          position: absolute;
          pointer-events: none;
          font-size: 14px;
          animation: particleFly 0.8s ease-out forwards;
        }

        @keyframes particleFly {
          0% { transform: translateY(0) scale(0.6); opacity: 1; }
          100% { transform: translateY(-24px) scale(1.2); opacity: 0; }
        }
      `;
      document.head.appendChild(style);

      // Wrapper container
      const container = document.createElement('div');
      container.id = 'anna-mascot-container';

      // Avatar Wrapper
      const wrapper = document.createElement('div');
      wrapper.id = 'anna-avatar';
      wrapper.className = 'anna-avatar-wrapper state-idle';
      wrapper.style.left = `${this.x}px`;
      wrapper.style.top = `${this.y}px`;

      // Badge quando dorme
      const sleepBadge = document.createElement('div');
      sleepBadge.className = 'anna-sleep-badge';
      sleepBadge.title = 'Sveglia Anna (Alt+Shift+A)';
      sleepBadge.innerHTML = '😴';
      wrapper.appendChild(sleepBadge);

      // Ombra
      const shadow = document.createElement('div');
      shadow.className = 'anna-ground-shadow';
      wrapper.appendChild(shadow);

      // SVG Avatar 2D Chibi (ChickMixFlat aesthetic: capelli scuri con sfumature viola, occhi anime, cyber techwear)
      wrapper.innerHTML += `
        <svg class="anna-svg" viewBox="0 0 72 96" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <!-- Sfumatura capelli: scuro alla radice, viola acceso alle punte -->
            <linearGradient id="hairGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#141126" />
              <stop offset="65%" stop-color="#241a42" />
              <stop offset="100%" stop-color="#9a7cff" />
            </linearGradient>

            <!-- Sfumatura occhi anime: viola scuro a ciano elettrico -->
            <linearGradient id="eyeGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#4c1d95" />
              <stop offset="50%" stop-color="#7c3aed" />
              <stop offset="100%" stop-color="#57e6d9" />
            </linearGradient>

            <!-- Bagliore LED Cuffie -->
            <radialGradient id="ledGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#57e6d9" />
              <stop offset="100%" stop-color="#57e6d900" />
            </radialGradient>
          </defs>

          <!-- Capelli posteriori -->
          <path d="M 20 28 C 12 40, 10 56, 17 64 C 23 58, 26 48, 25 36 Z" fill="url(#hairGrad)" />
          <path d="M 52 28 C 60 40, 62 56, 55 64 C 49 58, 46 48, 47 36 Z" fill="url(#hairGrad)" />

          <!-- Gambe e Stivali Cyber -->
          <g class="anna-legs">
            <!-- Gamba Sinistra -->
            <g class="anna-leg-left">
              <rect x="27" y="66" width="6" height="18" rx="3" fill="#19243c" />
              <!-- Calza con banda ciano -->
              <rect x="27" y="70" width="6" height="2" fill="#57e6d9" />
              <!-- Stivale -->
              <path d="M 25 80 L 33 80 L 34 89 L 23 89 Z" fill="#0d1428" stroke="#57e6d9" stroke-width="1" />
            </g>
            <!-- Gamba Destra -->
            <g class="anna-leg-right">
              <rect x="39" y="66" width="6" height="18" rx="3" fill="#19243c" />
              <!-- Calza con banda ciano -->
              <rect x="39" y="70" width="6" height="2" fill="#57e6d9" />
              <!-- Stivale -->
              <path d="M 37 80 L 45 80 L 47 89 L 36 89 Z" fill="#0d1428" stroke="#57e6d9" stroke-width="1" />
            </g>
          </g>

          <!-- Torso, Hoodie e Giacca Techwear -->
          <g class="anna-torso">
            <!-- Gonna a pieghe -->
            <path d="M 25 61 L 47 61 L 50 68 L 22 68 Z" fill="#263454" />
            
            <!-- Giacca Techwear 00MESH -->
            <path d="M 23 45 C 23 42, 49 42, 49 45 L 47 62 L 25 62 Z" fill="#0d1428" stroke="#263454" stroke-width="1" />
            <!-- Zip Ciano -->
            <line x1="36" y1="46" x2="36" y2="61" stroke="#57e6d9" stroke-width="1.5" />
            <circle cx="36" cy="60" r="1.5" fill="#f693bd" />

            <!-- Braccio Sinistro -->
            <g class="anna-arm-left">
              <path d="M 24 46 C 18 52, 19 60, 22 63" stroke="#0d1428" stroke-width="5" stroke-linecap="round" fill="none" />
              <circle cx="22" cy="64" r="2.5" fill="#fce7d8" />
            </g>

            <!-- Braccio Destro -->
            <g class="anna-arm-right">
              <path d="M 48 46 C 54 52, 53 60, 50 63" stroke="#0d1428" stroke-width="5" stroke-linecap="round" fill="none" />
              <circle cx="50" cy="64" r="2.5" fill="#fce7d8" />
            </g>
          </g>

          <!-- Testa e Volto -->
          <g class="anna-head">
            <!-- Collo -->
            <rect x="33" y="40" width="6" height="6" fill="#fce7d8" />
            <line x1="33" y1="42" x2="39" y2="42" stroke="#141126" stroke-width="1.2" /> <!-- Choker -->

            <!-- Ovale viso anime -->
            <path d="M 22 28 C 22 17, 50 17, 50 28 C 50 41, 41 46, 36 46 C 31 46, 22 41, 22 28 Z" fill="#fce7d8" />

            <!-- Rossore guance -->
            <ellipse cx="26" cy="34" rx="3.5" ry="1.8" fill="#f472b6" opacity="0.45" />
            <ellipse cx="46" cy="34" rx="3.5" ry="1.8" fill="#f472b6" opacity="0.45" />

            <!-- Bocca Sorriso -->
            <path class="anna-mouth-smile" d="M 33 38 Q 36 41 39 38" stroke="#c05621" stroke-width="1.2" fill="none" stroke-linecap="round" />
            <!-- Bocca Sorpresa (per drag/fall) -->
            <circle class="anna-mouth-surprised" cx="36" cy="38" r="2" fill="#c05621" opacity="0" />

            <!-- Occhio Sinistro Anime -->
            <g class="anna-eye" style="transform-origin: 29px 30px;">
              <ellipse cx="29" cy="30" rx="4.5" ry="6" fill="url(#eyeGrad)" />
              <ellipse cx="30" cy="28.5" rx="1.8" ry="2.2" fill="#ffffff" /> <!-- Riflesso luce -->
              <circle cx="28" cy="33" r="0.8" fill="#ffffff" opacity="0.8" />
              <!-- Ciglia -->
              <path d="M 24 25 C 27 23, 33 24, 34 26" stroke="#141126" stroke-width="1.5" stroke-linecap="round" fill="none" />
            </g>

            <!-- Occhio Destro Anime -->
            <g class="anna-eye" style="transform-origin: 43px 30px;">
              <ellipse cx="43" cy="30" rx="4.5" ry="6" fill="url(#eyeGrad)" />
              <ellipse cx="44" cy="28.5" rx="1.8" ry="2.2" fill="#ffffff" /> <!-- Riflesso luce -->
              <circle cx="42" cy="33" r="0.8" fill="#ffffff" opacity="0.8" />
              <!-- Ciglia -->
              <path d="M 38 26 C 39 24, 45 23, 48 25" stroke="#141126" stroke-width="1.5" stroke-linecap="round" fill="none" />
            </g>

            <!-- Frangia e Ciocche Anteriori -->
            <path d="M 21 27 C 24 16, 48 16, 51 27 C 46 22, 38 24, 36 29 C 34 24, 27 22, 21 27 Z" fill="url(#hairGrad)" />
            <path d="M 23 27 L 22 37 L 26 31 Z" fill="url(#hairGrad)" />
            <path d="M 49 27 L 50 37 L 46 31 Z" fill="url(#hairGrad)" />

            <!-- Ahoge (Ciuffo ribelle che rimbalza) -->
            <path class="anna-ahoge" d="M 36 17 C 35 8, 44 6, 42 13 C 41 15, 38 16, 36 17 Z" fill="#9a7cff" stroke="#241a42" stroke-width="0.8" />

            <!-- Cyber-Cuffia e LED di stato Mesh -->
            <path d="M 18 28 C 17 25, 20 22, 22 25 Z" fill="#0d1428" stroke="#57e6d9" stroke-width="1" />
            <circle cx="19" cy="27" r="1.8" fill="#57e6d9" />
            <circle cx="19" cy="27" r="3.5" fill="url(#ledGlow)" opacity="0.75" />
          </g>
        </svg>
      `;

      // Fumetto per le battute
      const bubble = document.createElement('div');
      bubble.id = 'anna-bubble';
      bubble.className = 'anna-bubble';
      bubble.innerHTML = `
        <span class="anna-bubble-close" title="Chiudi">✕</span>
        <div class="anna-bubble-text"></div>
      `;
      wrapper.appendChild(bubble);

      // Mini controlli
      const controls = document.createElement('div');
      controls.className = 'anna-controls';
      controls.innerHTML = `
        <button class="anna-btn-pill" id="annaBtnSleep" title="Metti Anna a nanna">💤 Riposa</button>
        <button class="anna-btn-pill" id="annaBtnTalk" title="Chiedi qualcosa ad Anna">💬 Parla</button>
      `;
      wrapper.appendChild(controls);

      container.appendChild(wrapper);
      document.body.appendChild(container);

      this.container = container;
      this.wrapper = wrapper;
      this.bubble = bubble;
      this.bubbleText = bubble.querySelector('.anna-bubble-text');
    }

    bindEvents() {
      if (!this.wrapper) return;

      // Click su fumetto chiudi
      this.bubble.querySelector('.anna-bubble-close').addEventListener('click', (e) => {
        e.stopPropagation();
        this.hideBubble();
      });

      // Tasto Riposa
      const sleepBtn = this.wrapper.querySelector('#annaBtnSleep');
      if (sleepBtn) {
        sleepBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.sleep();
        });
      }

      // Tasto Parla
      const talkBtn = this.wrapper.querySelector('#annaBtnTalk');
      if (talkBtn) {
        talkBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.triggerRandomQuote();
        });
      }

      // Risveglio se cliccata mentre dorme
      this.wrapper.addEventListener('click', (e) => {
        if (this.isSleeping) {
          e.stopPropagation();
          this.wake();
          return;
        }

        // Clic normale (se non è stato un drag significativo)
        if (!this.hasMovedDrag) {
          this.jump();
          this.spawnParticle('✨');
          if (this.quotesEnabled && (!this.activeQuote || Math.random() < 0.4)) {
            this.triggerRandomQuote();
          }
        }
      });

      // Doppio clic per chat / interazione profonda
      this.wrapper.addEventListener('dblclick', (e) => {
        e.stopPropagation();
        this.spawnParticle('💖');
        this.speak("Vuoi fare due chiacchiere con me? Apri AI Studio o scrivimi dal portale! ✨");
      });

      // Gestione Drag & Drop (Mouse e Touch)
      const onPointerDown = (clientX, clientY) => {
        if (this.isSleeping) return;
        this.isDragging = true;
        this.hasMovedDrag = false;
        this.dragStartX = clientX;
        this.dragStartY = clientY;
        const rect = this.wrapper.getBoundingClientRect();
        this.dragOffsetX = clientX - rect.left;
        this.dragOffsetY = clientY - rect.top;
        this.setState('drag');
      };

      const onPointerMove = (clientX, clientY) => {
        if (!this.isDragging) return;
        const dx = Math.abs(clientX - this.dragStartX);
        const dy = Math.abs(clientY - this.dragStartY);
        if (dx > 4 || dy > 4) {
          this.hasMovedDrag = true;
        }
        this.x = clientX - this.dragOffsetX;
        this.y = clientY - this.dragOffsetY;
        this.vx = 0;
        this.vy = 0;
        this.renderPosition();
      };

      const onPointerUp = () => {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.setState('fall');
        this.vy = 1; // Inizia a cadere con gravità
      };

      this.wrapper.addEventListener('mousedown', (e) => {
        if (e.target.closest('.anna-controls') || e.target.closest('.anna-bubble')) return;
        onPointerDown(e.clientX, e.clientY);
        const moveHandler = (ev) => onPointerMove(ev.clientX, ev.clientY);
        const upHandler = () => {
          onPointerUp();
          window.removeEventListener('mousemove', moveHandler);
          window.removeEventListener('mouseup', upHandler);
        };
        window.addEventListener('mousemove', moveHandler);
        window.addEventListener('mouseup', upHandler);
      });

      this.wrapper.addEventListener('touchstart', (e) => {
        if (e.touches.length === 1) {
          const t = e.touches[0];
          onPointerDown(t.clientX, t.clientY);
        }
      }, { passive: true });

      window.addEventListener('touchmove', (e) => {
        if (this.isDragging && e.touches.length === 1) {
          const t = e.touches[0];
          onPointerMove(t.clientX, t.clientY);
        }
      }, { passive: true });

      window.addEventListener('touchend', () => {
        if (this.isDragging) onPointerUp();
      });

      // Scorciatoia Alt+Shift+A per toggle
      window.addEventListener('keydown', (e) => {
        if (e.altKey && e.shiftKey && (e.key === 'A' || e.key === 'a')) {
          e.preventDefault();
          this.toggle();
        }
      });

      // Resize della finestra
      window.addEventListener('resize', () => {
        const floor = (window.innerHeight || 768) - this.height - 16;
        if (this.y > floor) this.y = floor;
        const maxW = (window.innerWidth || 1024) - this.width - 16;
        if (this.x > maxW) this.x = maxW;
        this.renderPosition();
      });
    }

    start() {
      if (this.animFrameId) return;
      this.lastFrameTime = performance.now();
      const loop = (timestamp) => {
        const dt = Math.min(0.1, (timestamp - this.lastFrameTime) / 1000);
        this.lastFrameTime = timestamp;
        if (this.enabled && !this.isSleeping) {
          this.update(dt);
        }
        this.animFrameId = requestAnimationFrame(loop);
      };
      this.animFrameId = requestAnimationFrame(loop);
    }

    stop() {
      if (this.animFrameId) {
        cancelAnimationFrame(this.animFrameId);
        this.animFrameId = null;
      }
    }

    setState(newState) {
      if (this.state === newState) return;
      this.wrapper.classList.remove(`state-${this.state}`);
      this.state = newState;
      this.wrapper.classList.add(`state-${this.state}`);
      this.stateTimer = 0;
    }

    update(dt) {
      if (this.isDragging) return;

      const screenWidth = window.innerWidth || 1024;
      const screenHeight = window.innerHeight || 768;
      const groundY = screenHeight - this.height - 16;

      // Rileva eventuali card/piattaforme su cui atterrare
      const platformY = this.findPlatformBelow(this.x + this.width / 2, this.y + this.height);
      const floorY = platformY !== null ? platformY - this.height : groundY;

      // Macchina a Stati Finita
      this.stateTimer += dt;

      if (this.state === 'fall') {
        const gravity = 800; // px/s^2
        this.vy += gravity * dt;
        this.y += this.vy * dt;

        if (this.y >= floorY) {
          this.y = floorY;
          this.vy = 0;
          this.setState('idle');
          this.spawnParticle('💨');
          this.wrapper.classList.remove('is-airborne');
        } else {
          this.wrapper.classList.add('is-airborne');
        }
      } else if (this.state === 'idle') {
        this.wrapper.classList.remove('is-airborne');
        // Se non c'è più terreno sotto i piedi (es. scroll), cade
        if (this.y < floorY - 5) {
          this.setState('fall');
          return;
        }

        // Dopo un certo periodo in idle decide una nuova azione
        if (this.stateTimer > 4 + Math.random() * 5) {
          const action = Math.random();
          if (action < 0.5) {
            // Cammina verso una posizione casuale
            this.targetX = Math.max(20, Math.min(screenWidth - this.width - 20, this.x + (Math.random() * 360 - 180)));
            this.facing = this.targetX > this.x ? 1 : -1;
            this.setState(Math.random() < 0.25 ? 'run' : 'walk');
          } else if (action < 0.75) {
            // Si siede sul bordo per un momento rilassante
            this.setState('sit');
          } else {
            // Saluta o mostra fumetto se abilitato
            if (this.quotesEnabled && Math.random() < 0.35 && !this.activeQuote) {
              this.triggerRandomQuote();
            }
            this.stateTimer = 0;
          }
        }
      } else if (this.state === 'walk' || this.state === 'run') {
        const speed = this.state === 'run' ? 140 : 65; // px/s
        const dir = this.targetX > this.x ? 1 : -1;
        this.facing = dir;
        this.x += dir * speed * dt;

        // Limiti schermo
        if (this.x < 16) { this.x = 16; this.setState('idle'); }
        if (this.x > screenWidth - this.width - 16) { this.x = screenWidth - this.width - 16; this.setState('idle'); }

        // Destinazione raggiunta
        if (Math.abs(this.x - this.targetX) < 6) {
          this.setState('idle');
        }
      } else if (this.state === 'sit') {
        if (this.stateTimer > 6 + Math.random() * 6) {
          this.setState('idle');
        }
      }

      this.renderPosition();
    }

    findPlatformBelow(centerX, footY) {
      // Cerca card e blocchi visibili nella pagina
      const cards = document.querySelectorAll('.card, .hero-card, [data-mascot-platform], .panel, section');
      let highestPlatform = null;

      for (let i = 0; i < cards.length; i++) {
        const rect = cards[i].getBoundingClientRect();
        // Verifica se si trova sopra la card in orizzontale
        if (centerX >= rect.left && centerX <= rect.right) {
          // Se la card è entro una distanza ragionevole sotto i piedi
          if (rect.top >= footY - 8 && rect.top <= footY + 45) {
            if (highestPlatform === null || rect.top < highestPlatform) {
              highestPlatform = rect.top;
            }
          }
        }
      }
      return highestPlatform;
    }

    renderPosition() {
      if (!this.wrapper) return;
      this.wrapper.style.left = `${Math.round(this.x)}px`;
      this.wrapper.style.top = `${Math.round(this.y)}px`;

      // Specchia l'avatar verso la direzione di marcia
      const svg = this.wrapper.querySelector('.anna-svg');
      if (svg) {
        svg.style.transform = this.facing === 1 ? 'scaleX(-1)' : 'scaleX(1)';
      }
    }

    jump() {
      if (this.state === 'drag' || this.isSleeping) return;
      this.setState('fall');
      this.vy = -340; // Impulso verso l'alto
      this.wrapper.classList.add('is-airborne');
    }

    speak(text, duration = 6500) {
      if (!this.bubble || !this.bubbleText) return;
      if (this.quoteTimeout) clearTimeout(this.quoteTimeout);

      this.activeQuote = text;
      this.bubbleText.textContent = text;
      this.bubble.classList.add('show');

      this.quoteTimeout = setTimeout(() => {
        this.hideBubble();
      }, duration);
    }

    hideBubble() {
      if (!this.bubble) return;
      this.bubble.classList.remove('show');
      this.activeQuote = null;
    }

    triggerRandomQuote() {
      const quote = ANNA_QUOTES[Math.floor(Math.random() * ANNA_QUOTES.length)];
      this.speak(quote);
    }

    spawnParticle(emoji) {
      if (!this.wrapper) return;
      const p = document.createElement('div');
      p.className = 'anna-particle';
      p.textContent = emoji;
      p.style.left = `${this.width / 2 + (Math.random() * 20 - 10)}px`;
      p.style.top = `${10 + Math.random() * 15}px`;
      this.wrapper.appendChild(p);
      setTimeout(() => {
        if (p.parentNode) p.parentNode.removeChild(p);
      }, 800);
    }

    sleep() {
      this.isSleeping = true;
      this.hideBubble();
      this.wrapper.classList.add('anna-sleeping');
      saveStoredState({ sleeping: true });
    }

    wake() {
      this.isSleeping = false;
      this.wrapper.classList.remove('anna-sleeping');
      saveStoredState({ sleeping: false });
      this.jump();
      this.speak("Eccomi tornata sveglia e operativa! ⚡");
    }

    toggle() {
      if (!this.enabled) {
        this.enabled = true;
        this.container.style.display = 'block';
        saveStoredState({ enabled: true });
        this.start();
        this.speak("Rieccomi qui sulla landing! ✨");
      } else {
        if (!this.isSleeping) {
          this.sleep();
        } else {
          this.enabled = false;
          this.container.style.display = 'none';
          this.stop();
          saveStoredState({ enabled: false });
        }
      }
    }
  }

  // Inizializzazione automatica al caricamento del DOM
  let instance = null;

  function init() {
    if (!instance && document.body) {
      instance = new AnnaMascot();
      global.__annaMascot = instance;
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})(typeof window !== 'undefined' ? window : globalThis);
