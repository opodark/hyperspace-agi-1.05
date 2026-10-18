// SPDX-License-Identifier: Apache-2.0
// web-node/tests/pdf.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import { buildPdfBinary } from "../src/pdf.js";
import { extractPdfText } from "../src/documents.js";

test("buildPdfBinary: genera un documento PDF-1.4 valido e conforme", () => {
  const { buffer, totalPages, title } = buildPdfBinary({
    title: "Relazione Tecnica 00MESH",
    content: "# Capitolo 1\nQuesto e' un paragrafo di prova per la rete mesh.\n- Punto A\n- Punto B",
    author: "ZeroZeroComputer",
  });

  assert.ok(buffer instanceof ArrayBuffer);
  assert.equal(totalPages, 1);
  assert.equal(title, "Relazione Tecnica 00MESH");

  const raw = new TextDecoder("latin1").decode(new Uint8Array(buffer));
  assert.ok(raw.startsWith("%PDF-1.4"));
  assert.ok(raw.includes("xref"));
  assert.ok(raw.includes("trailer"));
  assert.ok(raw.includes("%%EOF"));
  assert.ok(raw.includes("/Helvetica-Bold"));
});

test("buildPdfBinary: gestisce paginazione su contenuti lunghi", () => {
  const lines = [];
  for (let i = 1; i <= 100; i++) {
    lines.push(`Riga numero ${i}: descrizione dettagliata dei parametri di rete decentralizzata e calcolo GPU.`);
  }

  const { totalPages } = buildPdfBinary({
    title: "Documento Lungo Multi-Pagina",
    content: lines.join("\n"),
  });

  assert.ok(totalPages >= 2, `Attese almeno 2 pagine, ottenute: ${totalPages}`);
});

test("buildPdfBinary: il PDF generato e' compatibile con extractPdfText di AnyDoc", async () => {
  const { buffer } = buildPdfBinary({
    title: "Specifica HyperSpace 1.05",
    content: "Architettura neurale distribuita con cluster GPU autonomi e sovranita' del dato.",
  });

  const extracted = await extractPdfText(buffer);
  assert.ok(extracted.includes("Specifica HyperSpace 1.05"));
  assert.ok(extracted.includes("Architettura neurale distribuita"));
});
