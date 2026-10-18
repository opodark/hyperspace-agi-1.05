// SPDX-License-Identifier: Apache-2.0
// web-node/tests/render.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import {
  escapeHtml,
  renderMarkdown,
  extractUrls,
  renderLinkPreviewSection
} from "../src/render.js";

test("escapeHtml sanitizes html tags", () => {
  const dirty = "<script>alert('xss')</script>&\"'";
  const clean = escapeHtml(dirty);
  assert.equal(clean, "&lt;script&gt;alert(&#039;xss&#039;)&lt;/script&gt;&amp;&quot;&#039;");
});

test("renderMarkdown formats bold, italic and headers", () => {
  const md = "# Titolo\n**forte** e *corsivo*";
  const html = renderMarkdown(md);
  assert.match(html, /<h1>Titolo<\/h1>/);
  assert.match(html, /<strong>forte<\/strong>/);
  assert.match(html, /<em>corsivo<\/em>/);
});

test("renderMarkdown transforms code blocks with copy button", () => {
  const md = "Ecco il codice:\n```javascript\nconst a = 10;\nconsole.log(a);\n```";
  const html = renderMarkdown(md);
  assert.match(html, /class="code-box"/);
  assert.match(html, /class="code-lang">javascript<\/span>/);
  assert.match(html, /class="copy-code-btn"/);
  assert.match(html, /const a = 10;/);
});

test("renderMarkdown formats lists", () => {
  const md = "- Punto uno\n- Punto due";
  const html = renderMarkdown(md);
  assert.match(html, /<ul>/);
  assert.match(html, /<li>Punto uno<\/li>/);
  assert.match(html, /<li>Punto due<\/li>/);
});

test("renderMarkdown renders markdown links with target blank and safe rel", () => {
  const md = "Consulta la [Documentazione 00MESH](https://mesh.zerozerocomputer.it/docs) per iniziare.";
  const html = renderMarkdown(md);
  assert.match(html, /<a href="https:\/\/mesh\.zerozerocomputer\.it\/docs"/);
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(html, /class="md-link"/);
  assert.match(html, /Documentazione 00MESH/);
});

test("renderMarkdown autolinks raw URLs in text", () => {
  const md = "Puoi verificare lo stato su https://api.groq.com/openai/v1 in tempo reale.";
  const html = renderMarkdown(md);
  assert.match(html, /<a href="https:\/\/api\.groq\.com\/openai\/v1"/);
  assert.match(html, /class="md-link md-autolink"/);
  assert.match(html, /target="_blank"/);
});

test("renderMarkdown renders Markdown tables with alignment", () => {
  const md = `
| Componente | Ruolo | Stato |
| :--- | :---: | ---: |
| Control Plane | Gateway | Attivo |
| Chrome Bridge | GPU Worker | Connesso |
`;
  const html = renderMarkdown(md);
  assert.match(html, /<table class="md-table">/);
  assert.match(html, /<th style="text-align:left">Componente<\/th>/);
  assert.match(html, /<th style="text-align:center">Ruolo<\/th>/);
  assert.match(html, /<th style="text-align:right">Stato<\/th>/);
  assert.match(html, /<td style="text-align:left">Control Plane<\/td>/);
  assert.match(html, /<td style="text-align:center">Gateway<\/td>/);
  assert.match(html, /<td style="text-align:right">Attivo<\/td>/);
});

test("renderMarkdown renders image embeds", () => {
  const md = "Ecco il diagramma di rete:\n![Architettura](https://zerozerocomputer.it/assets/mesh.png)";
  const html = renderMarkdown(md);
  assert.match(html, /<div class="md-image-box">/);
  assert.match(html, /<img src="https:\/\/zerozerocomputer\.it\/assets\/mesh\.png"/);
  assert.match(html, /alt="Architettura"/);
});

test("extractUrls extracts valid unique HTTP and HTTPS URLs", () => {
  const text = "Controlla https://github.com/zerozero e anche https://mesh.zerozerocomputer.it/v1 o di nuovo https://github.com/zerozero";
  const urls = extractUrls(text);
  assert.equal(urls.length, 2);
  assert.equal(urls[0].href, "https://github.com/zerozero");
  assert.equal(urls[0].hostname, "github.com");
  assert.equal(urls[1].href, "https://mesh.zerozerocomputer.it/v1");
});

test("renderLinkPreviewSection builds rich preview cards", () => {
  const urls = [
    { href: "https://github.com/zerozero/hyperspace", hostname: "github.com", pathname: "/zerozero/hyperspace", isImage: false },
    { href: "https://example.com/badge.png", hostname: "example.com", pathname: "/badge.png", isImage: true }
  ];
  const html = renderLinkPreviewSection(urls);
  assert.match(html, /class="msg-link-previews"/);
  assert.match(html, /class="link-card"/);
  assert.match(html, /github\.com/);
  assert.match(html, /class="link-card-thumb"/); // for image
  assert.match(html, /copy-url-btn/);
});
