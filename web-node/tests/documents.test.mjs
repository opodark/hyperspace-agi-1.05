// SPDX-License-Identifier: Apache-2.0
import test from "node:test";
import assert from "node:assert/strict";
import zlib from "node:zlib";
import {
  formatFileSize,
  isSupportedFile,
  unescapePdfString,
  parsePdfStreamText,
  extractPdfText,
  extractTextFromFile,
  formatDocumentsContext,
} from "../src/documents.js";

test("formattazione dimensione file", () => {
  assert.equal(formatFileSize(500), "500 B");
  assert.equal(formatFileSize(1024), "1.0 KB");
  assert.equal(formatFileSize(2048), "2.0 KB");
  assert.equal(formatFileSize(1048576), "1.0 MB");
});

test("filtro estensioni supportate", () => {
  assert.equal(isSupportedFile({ name: "main.py" }), true);
  assert.equal(isSupportedFile({ name: "documento.pdf" }), true);
  assert.equal(isSupportedFile({ name: "dati.csv" }), true);
  assert.equal(isSupportedFile({ name: "app.json" }), true);
  assert.equal(isSupportedFile({ name: "video.mp4" }), false);
  assert.equal(isSupportedFile({ name: "immagine.png" }), false);
  assert.equal(isSupportedFile(null), false);
});

test("unescape stringhe PDF", () => {
  assert.equal(unescapePdfString("Test \\(annidato\\)"), "Test (annidato)");
  assert.equal(unescapePdfString("Riga1\\nRiga2"), "Riga1\nRiga2");
  assert.equal(unescapePdfString("\\101\\102\\103"), "ABC");
});

test("parsing operatori testo PDF BT..ET", () => {
  const streamContent = `
    BT
      /F1 14 Tf
      10 20 Td
      (Benvenuto in ZeroZeroComputer) Tj
      0 -15 Td
      [(Architettura ) -10 (Mesh ) 20 (Distribuita)] TJ
    ET
  `;
  const text = parsePdfStreamText(streamContent);
  assert.match(text, /Benvenuto in ZeroZeroComputer/);
  assert.match(text, /Architettura Mesh Distribuita/);
});

test("estrazione testo da PDF binario con stream compresso FlateDecode", async () => {
  const plainText = "BT /F1 12 Tf (Rapporto Tecnico HyperSpace 1.05) Tj ET";
  const compressed = zlib.deflateSync(Buffer.from(plainText, "utf-8"));

  const pdfHeader = Buffer.from(
    "%PDF-1.4\n1 0 obj\n<< /Length " + compressed.length + " /Filter /FlateDecode >>\nstream\n",
    "latin1"
  );
  const pdfFooter = Buffer.from("\nendstream\nendobj\n%%EOF", "latin1");

  const pdfBuffer = Buffer.concat([pdfHeader, compressed, pdfFooter]);
  const extracted = await extractPdfText(pdfBuffer);

  assert.match(extracted, /Rapporto Tecnico HyperSpace 1\.05/);
});

test("estrazione testo da file di codice testuale", async () => {
  const mockFile = {
    name: "script.py",
    size: 120,
    textData: "import os\nprint('Hello Mesh')\n# Fine script",
  };

  const res = await extractTextFromFile(mockFile);
  assert.equal(res.name, "script.py");
  assert.equal(res.lines, 3);
  assert.match(res.text, /Hello Mesh/);
});

test("formatDocumentsContext struttura il prompt Markdown", () => {
  const docs = [
    {
      name: "config.json",
      formattedSize: "1.2 KB",
      lines: 10,
      text: '{"mesh": "active"}',
    },
  ];

  const ctx = formatDocumentsContext(docs);
  assert.match(ctx, /DOCUMENTI E FILE ALLEGATI DALL'UTENTE/);
  assert.match(ctx, /config\.json/);
  assert.match(ctx, /\{"mesh": "active"\}/);
});
