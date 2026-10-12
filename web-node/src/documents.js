// SPDX-License-Identifier: Apache-2.0
// web-node/src/documents.js
// AnyDoc: Ingestione e analisi client-side di documenti e codice (txt, md, py, json, csv, pdf).
// Funziona interamente nel browser a zero dipendenze esterne: i file non lasciano
// il client finché l'utente non decide di inviare il prompt alla rete.

/** Formatta dimensione in byte in stringa leggibile (B, KB, MB). */
export function formatFileSize(bytes) {
  const b = Number(bytes) || 0;
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

/** Verifica se il file è supportato per l'ingestione testo/codice/PDF. */
export function isSupportedFile(file) {
  if (!file) return false;
  const name = String(file.name || "").toLowerCase();
  const exts = [
    ".txt", ".md", ".markdown", ".json", ".csv", ".tsv",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".xml", ".yaml", ".yml", ".sh", ".bash", ".zsh", ".sql",
    ".log", ".env", ".toml", ".ini", ".conf", ".pdf"
  ];
  return exts.some((ext) => name.endsWith(ext));
}

/** Riconosce sequenze di escape PDF e caratteri ottali. */
export function unescapePdfString(str) {
  return String(str || "")
    .replace(/\\([()\\])/g, "$1")
    .replace(/\\n/g, "\n")
    .replace(/\\r/g, "\r")
    .replace(/\\t/g, "\t")
    .replace(/\\([0-7]{1,3})/g, (_, oct) => String.fromCharCode(parseInt(oct, 8)));
}

/** Estrae stringhe testuali da blocchi di stream PDF (operatori BT ... ET, Tj e TJ). */
export function parsePdfStreamText(content) {
  const textChunks = [];
  const btEtRegex = /BT[\s\S]*?ET/g;
  let blockMatch;

  while ((blockMatch = btEtRegex.exec(content)) !== null) {
    const block = blockMatch[0];

    // Operatore (testo) Tj
    const tjRegex = /\(((?:\\\(|\\\)|[^()])*)\)\s*Tj/g;
    let tjMatch;
    while ((tjMatch = tjRegex.exec(block)) !== null) {
      textChunks.push(unescapePdfString(tjMatch[1]));
    }

    // Operatore [(array) -20 (con) 10 (spazi)] TJ
    const tjArrayRegex = /\[([\s\S]*?)\]\s*TJ/g;
    let arrMatch;
    while ((arrMatch = tjArrayRegex.exec(block)) !== null) {
      const inner = arrMatch[1];
      const innerStrRegex = /\(((?:\\\(|\\\)|[^()])*)\)/g;
      let sMatch;
      const parts = [];
      while ((sMatch = innerStrRegex.exec(inner)) !== null) {
        parts.push(unescapePdfString(sMatch[1]));
      }
      if (parts.length) textChunks.push(parts.join(""));
    }
  }

  return textChunks.join(" ").replace(/\s{2,}/g, " ").trim();
}

/** Decomprime uno stream PDF binario usando le Web API native DecompressionStream. */
async function decompressDeflateBytes(uint8Data) {
  if (typeof globalThis.DecompressionStream !== "function") {
    return new TextDecoder("utf-8", { fatal: false }).decode(uint8Data);
  }

  // 1. Prova zlib standard ('deflate', RFC 1950)
  try {
    const ds = new globalThis.DecompressionStream("deflate");
    const stream = new Response(new Blob([uint8Data]).stream().pipeThrough(ds));
    return await stream.text();
  } catch {
    // 2. Prova raw deflate ('deflate-raw', RFC 1951)
    try {
      const dsRaw = new globalThis.DecompressionStream("deflate-raw");
      const streamRaw = new Response(new Blob([uint8Data]).stream().pipeThrough(dsRaw));
      return await streamRaw.text();
    } catch {
      // 3. Fallback stringa non decompressa
      return new TextDecoder("latin1").decode(uint8Data);
    }
  }
}

/** Estrae il testo da un file PDF senza alcuna libreria esterna pesante. */
export async function extractPdfText(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const rawString = new TextDecoder("latin1").decode(bytes);
  const extractedPieces = [];

  // Trova tutti i blocchi `stream ... endstream`
  // Usiamo indici di byte per non corrompere gli stream binari FlateDecode
  const streamMarker = "stream";
  const endStreamMarker = "endstream";
  let searchIdx = 0;

  while (true) {
    const streamStart = rawString.indexOf(streamMarker, searchIdx);
    if (streamStart === -1) break;

    const dictStart = Math.max(0, streamStart - 300);
    const streamDict = rawString.slice(dictStart, streamStart);
    const isFlate = /\/Filter\s*\/FlateDecode/i.test(streamDict);

    // Salta 'stream' e l'eventuale \r\n o \n
    let dataStart = streamStart + 6;
    if (rawString.charCodeAt(dataStart) === 0x0D && rawString.charCodeAt(dataStart + 1) === 0x0A) {
      dataStart += 2;
    } else if (rawString.charCodeAt(dataStart) === 0x0A || rawString.charCodeAt(dataStart) === 0x0D) {
      dataStart += 1;
    }

    const dataEnd = rawString.indexOf(endStreamMarker, dataStart);
    if (dataEnd === -1) break;

    // Rimuovi eventuali \r o \n finali prima di 'endstream'
    let actualEnd = dataEnd;
    while (actualEnd > dataStart && (bytes[actualEnd - 1] === 0x0A || bytes[actualEnd - 1] === 0x0D)) {
      actualEnd--;
    }

    const streamSlice = bytes.subarray(dataStart, actualEnd);

    if (isFlate) {
      try {
        const decompressed = await decompressDeflateBytes(streamSlice);
        const parsed = parsePdfStreamText(decompressed);
        if (parsed) extractedPieces.push(parsed);
      } catch {
        // Fallback: scansiona testo grezzo
      }
    } else {
      const plain = new TextDecoder("latin1").decode(streamSlice);
      const parsed = parsePdfStreamText(plain);
      if (parsed) extractedPieces.push(parsed);
    }

    searchIdx = dataEnd + 9;
  }

  // Se nessun blocco BT..ET formattato ha prodotto testo, recupera stringhe visibili di fallback
  if (!extractedPieces.length) {
    const fallbackMatches = rawString.match(/\(([^()\\]{4,})\)/g) || [];
    for (const match of fallbackMatches.slice(0, 50)) {
      const clean = unescapePdfString(match.slice(1, -1)).trim();
      if (clean && !clean.startsWith("/") && clean.length > 3) {
        extractedPieces.push(clean);
      }
    }
  }

  return extractedPieces.join("\n\n").trim();
}

/** Legge ed estrae il testo da un file utente (File / Blob / Oggetto mock per test). */
export async function extractTextFromFile(file) {
  if (!file) throw new Error("Nessun file selezionato");
  const name = String(file.name || "documento.txt");
  const size = Number(file.size || 0);
  const formattedSize = formatFileSize(size);

  let rawText = "";
  if (name.toLowerCase().endsWith(".pdf")) {
    const buffer = typeof file.arrayBuffer === "function"
      ? await file.arrayBuffer()
      : (file.buffer ? file.buffer : new ArrayBuffer(0));
    rawText = await extractPdfText(buffer);
  } else {
    if (typeof file.text === "function") {
      rawText = await file.text();
    } else if (typeof globalThis.FileReader !== "undefined") {
      rawText = await new Promise((resolve, reject) => {
        const reader = new globalThis.FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Errore lettura file"));
        reader.readAsText(file);
      });
    } else if (file.textData) {
      rawText = String(file.textData);
    }
  }

  const lines = rawText.split(/\r?\n/).length;

  return {
    name,
    size,
    formattedSize,
    lines,
    text: rawText.trim()
  };
}

/** Formatta una lista di documenti in un contesto Markdown ottimizzato per il prompt LLM. */
export function formatDocumentsContext(documents) {
  if (!Array.isArray(documents) || !documents.length) return "";

  const sections = documents.map((doc, idx) => {
    const header = `[Documento ${idx + 1}: ${doc.name} (${doc.formattedSize || formatFileSize(doc.size)}, ${doc.lines || 1} righe)]`;
    return `${header}\n\`\`\`\n${doc.text || ""}\n\`\`\``;
  });

  return (
    "DOCUMENTI E FILE ALLEGATI DALL'UTENTE:\n" +
    "Usa queste informazioni come contesto prioritario per rispondere alle domande seguenti.\n\n" +
    sections.join("\n\n")
  );
}
