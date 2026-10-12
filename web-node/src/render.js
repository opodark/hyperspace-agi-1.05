// SPDX-License-Identifier: Apache-2.0
// web-node/src/render.js
// Rendering Markdown avanzato stile ChatGPT / Claude con syntax highlight,
// pulsante "Copia codice", tabelle e gestione blocchi.

/** Sanitizza stringa HTML per prevenire XSS. */
export function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/** Parser Markdown leggero ed elegante con supporto per code-block, tabelle e liste. */
export function renderMarkdown(rawText) {
  if (!rawText) return "";

  // Se marked.js è disponibile globalmente (caricato via CDN), usiamolo
  if (typeof globalThis.marked !== "undefined" && typeof globalThis.marked.parse === "function") {
    try {
      const parsed = globalThis.marked.parse(rawText, { gfm: true, breaks: true });
      return enhanceCodeBlocks(parsed);
    } catch {
      // fallback al renderer integrato
    }
  }

  // Renderer built-in (zero dipendenze)
  return fallbackMarkdown(rawText);
}

/** Inietta header e pulsante "Copia" nei blocchi di codice HTML generati da marked. */
function enhanceCodeBlocks(html) {
  return html.replace(/<pre><code(?:\s+class="language-([^"]*)")?>([\s\S]*?)<\/code><\/pre>/gi, (match, lang, code) => {
    const cleanLang = (lang || "code").toLowerCase();
    const rawCode = decodeHtml(code);
    const encoded = encodeURIComponent(rawCode);
    return `
<div class="code-box">
  <div class="code-box-header">
    <span class="code-lang">${cleanLang}</span>
    <button class="copy-code-btn" data-code="${encoded}">📋 Copia</button>
  </div>
  <pre><code class="language-${cleanLang}">${code}</code></pre>
</div>`;
  });
}

function decodeHtml(html) {
  return html
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'");
}

/** Fallback parser Markdown per ambienti offline o senza CDN. */
function fallbackMarkdown(text) {
  const codeBlocks = [];
  // 1. Estrai blocchi di codice per proteggerli
  let processed = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    const cleanLang = (lang || "code").trim().toLowerCase();
    const encoded = encodeURIComponent(code.trim());
    codeBlocks.push(`
<div class="code-box">
  <div class="code-box-header">
    <span class="code-lang">${escapeHtml(cleanLang)}</span>
    <button class="copy-code-btn" data-code="${encoded}">📋 Copia</button>
  </div>
  <pre><code>${escapeHtml(code.trim())}</code></pre>
</div>`);
    return `___CODE_BLOCK_${idx}___`;
  });

  // 2. Inline code
  processed = processed.replace(/`([^`]+)`/g, (_, code) => `<code>${escapeHtml(code)}</code>`);

  // 3. Headings (# Title)
  processed = processed.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  processed = processed.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  processed = processed.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // 4. Bold e Italic
  processed = processed.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  processed = processed.replace(/\*(.*?)\*/g, "<em>$1</em>");

  // 5. Blockquotes
  processed = processed.replace(/^> (.*$)/gim, "<blockquote>$1</blockquote>");

  // 6. Liste non ordinate
  processed = processed.replace(/^\s*[-*]\s+(.*$)/gim, "<li>$1</li>");
  processed = processed.replace(/(<li>.*<\/li>)/gims, "<ul>$1</ul>");

  // 7. Paragrafi e newlines
  processed = processed.replace(/\n\n+/g, "</p><p>");
  processed = processed.replace(/\n/g, "<br>");
  processed = `<p>${processed}</p>`;

  // 8. Ripristina blocchi di codice
  codeBlocks.forEach((block, idx) => {
    processed = processed.replace(`<p>___CODE_BLOCK_${idx}___</p>`, block);
    processed = processed.replace(`___CODE_BLOCK_${idx}___`, block);
  });

  return processed;
}

/** Collega i listener di copia agli elementi del DOM. */
export function attachCopyEvents(container) {
  if (!container) return;
  const buttons = container.querySelectorAll(".copy-code-btn");
  buttons.forEach((btn) => {
    if (btn._hasCopyListener) return;
    btn._hasCopyListener = true;
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const raw = decodeURIComponent(btn.getAttribute("data-code") || "");
      try {
        await navigator.clipboard.writeText(raw);
        const originalText = btn.textContent;
        btn.textContent = "✓ Copiato!";
        btn.classList.add("copied");
        setTimeout(() => {
          btn.textContent = originalText;
          btn.classList.remove("copied");
        }, 2000);
      } catch (err) {
        btn.textContent = "Errore copia";
      }
    });
  });
}
