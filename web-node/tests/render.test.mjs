// SPDX-License-Identifier: Apache-2.0
// web-node/tests/render.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import { escapeHtml, renderMarkdown } from "../src/render.js";

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
