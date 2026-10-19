// SPDX-License-Identifier: Apache-2.0
// web-node/src/render.js
// Rendering Markdown avanzato stile ChatGPT / Claude con syntax highlight,
// parsing tabelle, link cliccabili con target="_blank", auto-linking URL,
// anteprime link/risorse, immagini e integrazione Docker Sandbox.

/** Sanitizza stringa HTML per prevenire XSS. */
export function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/** Estrae tutti gli URL univoci validi (http/https) presenti in un testo. */
export function extractUrls(text) {
  if (!text) return [];
  const raw = String(text);
  const regex = /https?:\/\/[^\s<>"'()]+[^\s<>"'().,;:?!]/gi;
  const matches = raw.match(regex) || [];
  const list = [];
  const seen = new Set();
  for (const item of matches) {
    try {
      const url = new URL(item);
      if ((url.protocol === "http:" || url.protocol === "https:") && !seen.has(url.href)) {
        seen.add(url.href);
        const isImg = /\.(png|jpe?g|gif|webp|svg)(\?.*)?$/i.test(url.pathname);
        list.push({
          href: url.href,
          hostname: url.hostname,
          pathname: url.pathname,
          isImage: isImg,
        });
      }
    } catch {}
  }
  return list;
}

/** Parser Markdown leggero ed elegante con supporto completo. */
export function renderMarkdown(rawText) {
  if (!rawText) return "";

  // Se marked.js è disponibile globalmente (caricato via CDN), usiamolo
  if (typeof globalThis.marked !== "undefined" && typeof globalThis.marked.parse === "function") {
    try {
      const parsed = globalThis.marked.parse(rawText, { gfm: true, breaks: true });
      return enhanceMarkedHtml(parsed);
    } catch {
      // fallback al renderer integrato
    }
  }

  // Renderer built-in (zero dipendenze, sicuro da XSS)
  return fallbackMarkdown(rawText);
}

/** Inietta classi di sicurezza ed estensioni nell'HTML di marked se presente. */
function enhanceMarkedHtml(html) {
  let enhanced = enhanceCodeBlocks(html);
  // Assicura che tutti i link abbiano target="_blank" e rel sicuro
  enhanced = enhanced.replace(/<a\s+href="([^"]+)"([^>]*)>/gi, (match, href, rest) => {
    if (/target=/i.test(rest)) return match;
    return `<a href="${href}" target="_blank" rel="noopener noreferrer" class="md-link"${rest}>`;
  });
  // Avvolgi le tabelle in un wrapper scrollabile
  enhanced = enhanced.replace(/<table(?:\s+[^>]*)?>([\s\S]*?)<\/table>/gi, (match) => {
    return `<div class="table-wrap">${match}</div>`;
  });
  return enhanced;
}

/** Inietta header e pulsanti "Esegui" / "Copia" nei blocchi di codice HTML generati da marked. */
function enhanceCodeBlocks(html) {
  return html.replace(/<pre><code(?:\s+class="language-([^"]*)")?>([\s\S]*?)<\/code><\/pre>/gi, (match, lang, code) => {
    const cleanLang = (lang || "code").toLowerCase();
    const rawCode = decodeHtml(code);
    const encoded = encodeURIComponent(rawCode);
    const isPython = cleanLang === "python" || cleanLang === "py";
    const runBtn = isPython
      ? `<button class="run-sandbox-btn" data-code="${encoded}">▶ Esegui in Sandbox</button>`
      : "";
    return `
<div class="code-box">
  <div class="code-box-header">
    <span class="code-lang">${cleanLang}</span>
    <div class="code-box-actions">
      ${runBtn}
      <button class="copy-code-btn" data-code="${encoded}">📋 Copia</button>
    </div>
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

/** Fallback parser Markdown per ambienti offline o senza librerie esterne. */
function fallbackMarkdown(text) {
  const codeBlocks = [];
  const inlineCodes = [];
  const tables = [];
  const images = [];
  const links = [];

  // 1. Estrai blocchi di codice multilinea ```...``` per proteggerli
  let processed = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const idx = codeBlocks.length;
    const cleanLang = (lang || "code").trim().toLowerCase();
    const encoded = encodeURIComponent(code.trim());
    const isPython = cleanLang === "python" || cleanLang === "py";
    const runBtn = isPython
      ? `<button class="run-sandbox-btn" data-code="${encoded}">▶ Esegui in Sandbox</button>`
      : "";
    codeBlocks.push(`
<div class="code-box">
  <div class="code-box-header">
    <span class="code-lang">${escapeHtml(cleanLang)}</span>
    <div class="code-box-actions">
      ${runBtn}
      <button class="copy-code-btn" data-code="${encoded}">📋 Copia</button>
    </div>
  </div>
  <pre><code>${escapeHtml(code.trim())}</code></pre>
</div>`);
    return `§§§CODEBLOCK${idx}§§§`;
  });

  // 2. Estrai codice inline `...`
  processed = processed.replace(/`([^`\n]+)`/g, (_, code) => {
    const idx = inlineCodes.length;
    inlineCodes.push(`<code>${escapeHtml(code)}</code>`);
    return `§§§INLINECODE${idx}§§§`;
  });

  // 3. Estrai e parsa tabelle Markdown | col1 | col2 |
  processed = parseMarkdownTables(processed, tables);

  // 4. Estrai immagini ![alt](url)
  processed = processed.replace(/!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g, (_, alt, url) => {
    const idx = images.length;
    const cleanAlt = escapeHtml(alt || "Immagine");
    const cleanUrl = escapeHtml(url);
    images.push(`
<div class="md-image-box">
  <a href="${cleanUrl}" target="_blank" rel="noopener noreferrer">
    <img src="${cleanUrl}" alt="${cleanAlt}" class="md-img" loading="lazy" />
  </a>
  ${cleanAlt ? `<span class="md-img-caption">${cleanAlt}</span>` : ""}
</div>`);
    return `§§§IMAGE${idx}§§§`;
  });

  // 5. Estrai link Markdown espliciti [testo](url)
  processed = processed.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => {
    const idx = links.length;
    const cleanLabel = escapeHtml(label);
    const cleanUrl = escapeHtml(url);
    links.push(`<a href="${cleanUrl}" target="_blank" rel="noopener noreferrer" class="md-link">${cleanLabel} <span class="ext-icon">↗</span></a>`);
    return `§§§LINK${idx}§§§`;
  });

  // 6. Sanitizza il resto dell'HTML grezzo per prevenire injection XSS
  processed = escapeHtml(processed);

  // 7. Auto-link per URL grezzi non ancora racchiusi in tag
  processed = processed.replace(/\b(https?:\/\/[^\s<>"'()]+[^\s<>"'().,;:?!])/gi, (url) => {
    return `<a href="${url}" target="_blank" rel="noopener noreferrer" class="md-link md-autolink">${url} <span class="ext-icon">↗</span></a>`;
  });

  // 8. Headings (# Title, ## Sub, ### H3, #### H4)
  processed = processed.replace(/^#### (.*$)/gim, "<h4>$1</h4>");
  processed = processed.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  processed = processed.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  processed = processed.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // 9. Horizontal Rule (--- o ***)
  processed = processed.replace(/^(\*{3,}|-{3,}|_{3,})\s*$/gim, "<hr class=\"md-hr\" />");

  // 10. Strikethrough (~~del~~)
  processed = processed.replace(/~~(.*?)~~/g, "<del>$1</del>");

  // 11. Bold (**bold**) e Italic (*italic* o _italic_)
  processed = processed.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  processed = processed.replace(/\*(.*?)\*/g, "<em>$1</em>");
  processed = processed.replace(/(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])/g, "<em>$1</em>");

  // 12. Blockquotes (> citazione)
  processed = processed.replace(/^>\s?(.*$)/gim, "<blockquote>$1</blockquote>");

  // 13. Task lists (- [ ] o - [x])
  processed = processed.replace(/^\s*[-*]\s+\[ \]\s+(.*$)/gim, "<li class=\"task-item\"><span class=\"task-box\">☐</span> $1</li>");
  processed = processed.replace(/^\s*[-*]\s+\[[xX]\]\s+(.*$)/gim, "<li class=\"task-item task-done\"><span class=\"task-box\">☑</span> $1</li>");

  // 14. Liste non ordinate standard (- item o * item)
  processed = processed.replace(/^\s*[-*]\s+(.*$)/gim, "<li>$1</li>");
  processed = processed.replace(/(<li>.*<\/li>)/gims, "<ul>$1</ul>");

  // 15. Paragrafi e newlines
  processed = processed.replace(/\n\n+/g, "</p><p>");
  processed = processed.replace(/\n/g, "<br>");
  processed = `<p>${processed}</p>`;

  // 16. Ripristina tutti i blocchi protetti
  links.forEach((link, idx) => {
    processed = processed.split(`§§§LINK${idx}§§§`).join(link);
  });

  images.forEach((img, idx) => {
    processed = processed.split(`<p>§§§IMAGE${idx}§§§</p>`).join(img);
    processed = processed.split(`§§§IMAGE${idx}§§§`).join(img);
  });

  tables.forEach((tbl, idx) => {
    processed = processed.split(`<p>§§§TABLE${idx}§§§</p>`).join(tbl);
    processed = processed.split(`§§§TABLE${idx}§§§`).join(tbl);
  });

  inlineCodes.forEach((ic, idx) => {
    processed = processed.split(`§§§INLINECODE${idx}§§§`).join(ic);
  });

  codeBlocks.forEach((block, idx) => {
    processed = processed.split(`<p>§§§CODEBLOCK${idx}§§§</p>`).join(block);
    processed = processed.split(`§§§CODEBLOCK${idx}§§§`).join(block);
  });

  // Pulizia tag <p> vuoti o ridondanti
  processed = processed
    .replace(/<p>\s*<\/p>/g, "")
    .replace(/<p><br><\/p>/g, "");

  return processed;
}

/** Rileva e converte tabelle Markdown in markup HTML responsive. */
function parseMarkdownTables(text, tableStore) {
  const lines = text.split("\n");
  const result = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    // Se la riga contiene pipe e la successiva è una riga separatore
    if (line.includes("|") && i + 1 < lines.length && isTableDelimiter(lines[i + 1])) {
      const headerLine = line;
      const delimiterLine = lines[i + 1];
      const dataLines = [];
      i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim() !== "") {
        dataLines.push(lines[i]);
        i++;
      }

      const tableHtml = buildTableHtml(headerLine, delimiterLine, dataLines);
      const idx = tableStore.length;
      tableStore.push(tableHtml);
      result.push(`§§§TABLE${idx}§§§`);
    } else {
      result.push(line);
      i++;
    }
  }

  return result.join("\n");
}

function isTableDelimiter(line) {
  const trimmed = line.trim();
  return /^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?$/.test(trimmed);
}

function splitTableRow(row) {
  let cleaned = row.trim();
  if (cleaned.startsWith("|")) cleaned = cleaned.slice(1);
  if (cleaned.endsWith("|")) cleaned = cleaned.slice(0, -1);
  return cleaned.split("|").map(c => c.trim());
}

function buildTableHtml(headerRow, delimiterRow, dataRows) {
  const headers = splitTableRow(headerRow);
  const aligns = splitTableRow(delimiterRow).map(cell => {
    const left = cell.startsWith(":");
    const right = cell.endsWith(":");
    if (left && right) return "center";
    if (right) return "right";
    return "left";
  });

  let ths = headers.map((h, idx) => {
    const align = aligns[idx] || "left";
    return `<th style="text-align:${align}">${escapeHtml(h)}</th>`;
  }).join("");

  let trs = dataRows.map(row => {
    const cells = splitTableRow(row);
    const tds = cells.map((c, idx) => {
      const align = aligns[idx] || "left";
      return `<td style="text-align:${align}">${escapeHtml(c)}</td>`;
    }).join("");
    return `<tr>${tds}</tr>`;
  }).join("\n");

  return `
<div class="table-wrap">
  <table class="md-table">
    <thead><tr>${ths}</tr></thead>
    <tbody>${trs}</tbody>
  </table>
</div>`;
}

/** Genera la sezione anteprima con card interattive per tutti gli URL rilevati. */
export function renderLinkPreviewSection(urls) {
  if (!Array.isArray(urls) || !urls.length) return "";
  const cards = urls.map(u => {
    const domain = escapeHtml(u.hostname.replace(/^www\./, ""));
    const path = escapeHtml(u.pathname.length > 28 ? u.pathname.slice(0, 28) + "…" : u.pathname);
    const href = escapeHtml(u.href);
    const faviconUrl = `https://www.google.com/s2/favicons?domain=${encodeURIComponent(u.hostname)}&sz=32`;

    let mediaPreview = "";
    if (u.isImage) {
      mediaPreview = `<div class="link-card-thumb"><img src="${href}" alt="${domain}" loading="lazy" /></div>`;
    }

    return `
      <div class="link-card" data-url="${href}">
        ${mediaPreview}
        <div class="link-card-body">
          <div class="link-card-host">
            <img class="link-card-favicon" src="${faviconUrl}" alt="" onerror="this.style.display='none'" />
            <span class="link-card-domain">${domain}</span>
          </div>
          <div class="link-card-path" title="${href}">${path || "/"}</div>
        </div>
        <div class="link-card-actions">
          <a href="${href}" target="_blank" rel="noopener noreferrer" class="link-card-btn open" title="Apri in una nuova scheda">Apri ↗</a>
          <button type="button" class="link-card-btn copy-url-btn" data-url="${href}" title="Copia link">📋</button>
        </div>
      </div>
    `;
  }).join("");

  return `
    <div class="msg-link-previews">
      <div class="link-previews-header">
        <span class="link-previews-icon">🔗</span>
        <span>Anteprima Link e Risorse (${urls.length})</span>
      </div>
      <div class="link-previews-grid">
        ${cards}
      </div>
    </div>
  `;
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

  const copyUrlButtons = container.querySelectorAll(".copy-url-btn");
  copyUrlButtons.forEach((btn) => {
    if (btn._hasCopyUrlListener) return;
    btn._hasCopyUrlListener = true;
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const url = btn.getAttribute("data-url") || "";
      try {
        await navigator.clipboard.writeText(url);
        const originalText = btn.textContent;
        btn.textContent = "✓";
        setTimeout(() => { btn.textContent = originalText; }, 1800);
      } catch {}
    });
  });
}

/** Collega tutti gli eventi interattivi del blocco codice: Copia + Esecuzione Docker Sandbox. */
export function attachCodeBlockEvents(container, { onRunCode } = {}) {
  if (!container) return;
  attachCopyEvents(container);

  const runButtons = container.querySelectorAll(".run-sandbox-btn");
  runButtons.forEach((btn) => {
    if (btn._hasRunListener) return;
    btn._hasRunListener = true;

    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const rawCode = decodeURIComponent(btn.getAttribute("data-code") || "");
      if (!rawCode || typeof onRunCode !== "function") return;

      const codeBox = btn.closest(".code-box");
      if (!codeBox) return;

      // Trova o crea container per terminale di esecuzione
      let terminal = codeBox.querySelector(".sandbox-terminal");
      if (!terminal) {
        terminal = document.createElement("div");
        terminal.className = "sandbox-terminal";
        terminal.innerHTML = `
          <div class="sandbox-terminal-head">
            <div class="sandbox-terminal-title">
              <span class="sandbox-dot pulse"></span>
              <span>Docker Sandbox (Python 3.12)</span>
            </div>
            <div class="sandbox-terminal-meta">
              <span class="sandbox-status-pill running">Esecuzione…</span>
            </div>
          </div>
          <pre class="sandbox-terminal-body">Avvio container isolato in corso…</pre>
        `;
        codeBox.appendChild(terminal);
      }

      const statusPill = terminal.querySelector(".sandbox-status-pill");
      const terminalBody = terminal.querySelector(".sandbox-terminal-body");
      const dot = terminal.querySelector(".sandbox-dot");

      btn.disabled = true;
      btn.textContent = "⏳ Esecuzione…";
      dot.className = "sandbox-dot pulse";
      statusPill.textContent = "Esecuzione…";
      statusPill.className = "sandbox-status-pill running";
      terminalBody.textContent = "Allocazione sandbox e isolamento processo…";
      terminalBody.classList.remove("error-output");

      try {
        const res = await onRunCode(rawCode);
        const exitCode = res.exitCode ?? (res.ok ? 0 : 1);
        const duration = res.durationMs ? `${res.durationMs}ms` : "";
        const isOk = exitCode === 0;

        dot.className = `sandbox-dot ${isOk ? "ok" : "err"}`;
        statusPill.textContent = isOk ? `Exit 0 · ${duration}` : `Exit ${exitCode} · ${duration}`;
        statusPill.className = `sandbox-status-pill ${isOk ? "ok" : "err"}`;

        let outputText = "";
        if (res.stdout) outputText += res.stdout;
        if (res.stderr) outputText += (outputText ? "\n--- STDERR ---\n" : "") + res.stderr;
        if (!outputText && res.output) outputText = res.output;
        if (!outputText) outputText = "(Processo completato senza output su stdout/stderr)";

        terminalBody.textContent = outputText;
        if (!isOk) {
          terminalBody.classList.add("error-output");
        } else {
          terminalBody.classList.remove("error-output");
        }
      } catch (err) {
        dot.className = "sandbox-dot err";
        statusPill.textContent = "Errore";
        statusPill.className = "sandbox-status-pill err";
        terminalBody.textContent = `Errore di esecuzione: ${err.message || err}`;
        terminalBody.classList.add("error-output");
      } finally {
        btn.disabled = false;
        btn.textContent = "↺ Riesegui";
      }
    });
  });
}
