// SPDX-License-Identifier: Apache-2.0
// web-node/src/pdf.js
// Generatore ed esportatore di documenti PDF (%PDF-1.4) vettoriali nativi client-side.
// Zero dipendenze esterne. Produce PDF standard A4 compatibili con Adobe Acrobat,
// Chrome, Safari, Preview ed estraibili tramite AnyDoc (extractPdfText).

/** Sanitizza caratteri per stringhe PDF standard (ASCII / Latin-1). */
function escapePdfText(str) {
  return String(str || "")
    .replace(/\\/g, "\\\\")
    .replace(/\(/g, "\\(")
    .replace(/\)/g, "\\)")
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u2013\u2014]/g, "-")
    .replace(/[^\x20-\x7E\xA0-\xFF]/g, " "); // fallback caratteri speciali a spazio
}

/** Spezza una riga lunga in più righe per adattarla alla larghezza della pagina. */
function wrapLine(text, maxChars = 80) {
  if (text.length <= maxChars) return [text];
  const words = text.split(/\s+/);
  const lines = [];
  let current = "";
  for (const w of words) {
    if (!current) {
      current = w;
    } else if ((current + " " + w).length <= maxChars) {
      current += " " + w;
    } else {
      lines.push(current);
      current = w;
    }
  }
  if (current) lines.push(current);
  return lines;
}

/**
 * Genera un buffer binario PDF-1.4 completo con layout professionale A4.
 */
export function buildPdfBinary({
  title = "Documento 00MESH",
  content = "",
  author = "ZeroZeroComputer · HyperSpace Mesh",
  date = new Date(),
} = {}) {
  const cleanTitle = escapePdfText(title);
  const cleanAuthor = escapePdfText(author);
  const dateStr = date instanceof Date ? date.toISOString().slice(0, 10) : String(date);

  // Suddividi il testo in blocchi e linee formattate
  const rawLines = String(content || "").split("\n");
  const processedItems = [];

  for (const line of rawLines) {
    const trimmed = line.trim();
    if (!trimmed) {
      processedItems.push({ type: "spacer", height: 10 });
      continue;
    }

    if (trimmed.startsWith("# ")) {
      processedItems.push({ type: "h1", text: trimmed.slice(2), height: 26 });
    } else if (trimmed.startsWith("## ")) {
      processedItems.push({ type: "h2", text: trimmed.slice(3), height: 22 });
    } else if (trimmed.startsWith("### ")) {
      processedItems.push({ type: "h3", text: trimmed.slice(4), height: 18 });
    } else if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      const wrapped = wrapLine(trimmed.slice(2), 75);
      wrapped.forEach((wLine, idx) => {
        processedItems.push({
          type: "bullet",
          text: (idx === 0 ? "• " : "  ") + wLine,
          height: 14,
        });
      });
    } else if (trimmed.startsWith("```")) {
      processedItems.push({ type: "code-boundary", text: trimmed, height: 12 });
    } else {
      const wrapped = wrapLine(trimmed, 80);
      wrapped.forEach((wLine) => {
        processedItems.push({ type: "text", text: wLine, height: 14 });
      });
    }
  }

  // Paginazione: A4 = 595.28 x 841.89 pt
  const pageHeight = 841.89;
  const topMargin = 780;
  const bottomMargin = 65;
  const pages = [];
  let currentPageCommands = [];
  let y = topMargin;

  // Header prima pagina
  currentPageCommands.push(
    `BT /F1 18 Tf 50 ${y} Td (${cleanTitle}) Tj ET`,
    `BT /F2 9 Tf 50 ${y - 16} Td (Autore: ${cleanAuthor}  ·  Data: ${dateStr}) Tj ET`,
    // Linea separatrice
    `0.5 w 0.2 0.8 0.7 RG 50 ${y - 24} m 545 ${y - 24} l S 0 0 0 RG`
  );
  y -= 45;

  for (const item of processedItems) {
    if (y - item.height < bottomMargin) {
      pages.push(currentPageCommands.join("\n"));
      currentPageCommands = [];
      y = topMargin;

      // Header pagine successive
      currentPageCommands.push(
        `BT /F2 8 Tf 50 ${y} Td (00MESH · ${cleanTitle}) Tj ET`,
        `0.3 w 0.6 0.6 0.6 RG 50 ${y - 6} m 545 ${y - 6} l S 0 0 0 RG`
      );
      y -= 25;
    }

    if (item.type === "spacer") {
      y -= item.height;
    } else if (item.type === "h1") {
      currentPageCommands.push(`BT /F1 15 Tf 50 ${y} Td (${escapePdfText(item.text)}) Tj ET`);
      y -= item.height;
    } else if (item.type === "h2") {
      currentPageCommands.push(`BT /F1 12 Tf 50 ${y} Td (${escapePdfText(item.text)}) Tj ET`);
      y -= item.height;
    } else if (item.type === "h3") {
      currentPageCommands.push(`BT /F1 10.5 Tf 50 ${y} Td (${escapePdfText(item.text)}) Tj ET`);
      y -= item.height;
    } else if (item.type === "bullet") {
      currentPageCommands.push(`BT /F2 9.5 Tf 58 ${y} Td (${escapePdfText(item.text)}) Tj ET`);
      y -= item.height;
    } else {
      currentPageCommands.push(`BT /F2 9.5 Tf 50 ${y} Td (${escapePdfText(item.text)}) Tj ET`);
      y -= item.height;
    }
  }

  pages.push(currentPageCommands.join("\n"));

  // Aggiungi numerazione piè di pagina su tutte le pagine
  const totalPages = pages.length;
  const finalizedPages = pages.map((contentStr, pageIndex) => {
    const pageNumText = `Pagina ${pageIndex + 1} di ${totalPages}`;
    const footerStr = `BT /F2 8 Tf 500 35 Td (${pageNumText}) Tj ET\n0.3 w 0.7 0.7 0.7 RG 50 48 m 545 48 l S 0 0 0 RG`;
    return `${contentStr}\n${footerStr}`;
  });

  // Assemblaggio file PDF standard %PDF-1.4
  // Oggetti:
  // 1: Catalog
  // 2: Pages
  // 3: Font F1 (Helvetica-Bold)
  // 4: Font F2 (Helvetica)
  // 5: Font F3 (Courier)
  // Poi per ogni pagina:
  // (5 + 2*i + 1): Page
  // (5 + 2*i + 2): Contents Stream

  const objects = [];
  const pageObjectIds = [];

  const catalogObjId = 1;
  const pagesObjId = 2;
  const fontBoldId = 3;
  const fontRegularId = 4;
  const fontMonoId = 5;

  objects[fontBoldId] = `<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>`;
  objects[fontRegularId] = `<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>`;
  objects[fontMonoId] = `<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>`;

  let currentId = 6;
  finalizedPages.forEach((streamData) => {
    const pageId = currentId++;
    const contentId = currentId++;
    pageObjectIds.push(pageId);

    const streamBytes = new TextEncoder().encode(streamData);
    objects[pageId] = `<< /Type /Page /Parent ${pagesObjId} 0 R /MediaBox [0 0 595.28 841.89] /Resources << /Font << /F1 ${fontBoldId} 0 R /F2 ${fontRegularId} 0 R /F3 ${fontMonoId} 0 R >> >> /Contents ${contentId} 0 R >>`;
    objects[contentId] = `<< /Length ${streamBytes.length} >>\nstream\n${streamData}\nendstream`;
  });

  objects[catalogObjId] = `<< /Type /Catalog /Pages ${pagesObjId} 0 R >>`;
  objects[pagesObjId] = `<< /Type /Pages /Kids [${pageObjectIds.map((id) => `${id} 0 R`).join(" ")}] /Count ${totalPages} >>`;

  // Costruzione byte PDF con cross-reference table (xref)
  let output = "%PDF-1.4\n%\xE2\xE3\xCF\xD3\n";
  const offsets = [];

  for (let i = 1; i < objects.length; i++) {
    offsets[i] = output.length;
    output += `${i} 0 obj\n${objects[i]}\nendobj\n`;
  }

  const startxref = output.length;
  output += `xref\n0 ${objects.length}\n0000000000 65535 f \n`;
  for (let i = 1; i < objects.length; i++) {
    const off = String(offsets[i]).padStart(10, "0");
    output += `${off} 00000 n \n`;
  }

  output += `trailer\n<< /Size ${objects.length} /Root ${catalogObjId} 0 R >>\nstartxref\n${startxref}\n%%EOF\n`;

  const finalBytes = new TextEncoder().encode(output);
  return {
    buffer: finalBytes.buffer,
    totalPages,
    title: cleanTitle,
  };
}

/**
 * Genera e avvia il download del PDF direttamente nel browser.
 */
export function downloadPdfFile({ title, content, author, filename } = {}) {
  const { buffer, totalPages } = buildPdfBinary({ title, content, author });
  const safeName = (filename || `${title || "documento"}.pdf`)
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  const finalFilename = safeName.endsWith(".pdf") ? safeName : `${safeName}.pdf`;

  if (typeof Blob !== "undefined" && typeof document !== "undefined") {
    const blob = new Blob([buffer], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = finalFilename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 2000);
  }

  return { ok: true, filename: finalFilename, totalPages };
}
