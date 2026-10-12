// SPDX-License-Identifier: Apache-2.0
import test from "node:test";
import assert from "node:assert/strict";
import { searchWeb, parseSearchSources, formatSearchContext, SearchError } from "../src/search.js";

test("searchWeb convalida query vuota", async () => {
  await assert.rejects(
    async () => searchWeb({ baseUrl: "http://mock-gw:8095", query: "   " }),
    SearchError
  );
});

test("searchWeb effettua chiamata corretta e ritorna risultato", async () => {
  const fakeFetch = async (url, options) => {
    assert.equal(url, "http://mock-gw:8095/web/search");
    assert.equal(options.method, "POST");
    assert.equal(options.headers["Authorization"], "Bearer hs-test-token");
    const body = JSON.parse(options.body);
    assert.equal(body.query, "architettura mesh");
    assert.equal(body.max_results, 5);

    return {
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        query: "architettura mesh",
        result: "- Guida Mesh\n  Descrizione mesh\n  https://hyperspace.local/mesh",
      }),
    };
  };

  const res = await searchWeb({
    baseUrl: "http://mock-gw:8095",
    token: "hs-test-token",
    query: "architettura mesh",
    fetchImpl: fakeFetch,
  });

  assert.equal(res.ok, true);
  assert.equal(res.query, "architettura mesh");
  assert.match(res.result, /Guida Mesh/);
});

test("searchWeb esegue fallback su lista endpoint", async () => {
  let callCount = 0;
  const fakeFetch = async (url) => {
    callCount++;
    if (url.startsWith("http://down:8095")) {
      throw new Error("Rete non raggiungibile");
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ ok: true, result: "Risultati ok" }),
    };
  };

  const res = await searchWeb({
    baseUrls: ["http://down:8095", "http://alive:8095"],
    query: "test fallback",
    fetchImpl: fakeFetch,
  });

  assert.equal(callCount, 2);
  assert.equal(res.result, "Risultati ok");
});

test("parseSearchSources estrae titolo, snippet e url", () => {
  const rawResult = `
- HyperSpace AGI Docs
  Architettura neurale decentralizzata e nodi browser
  https://github.com/hyperspace-agi/docs

- Articolo Blog
  Presentazione della versione 1.05
  https://zerozerocomputer.it/blog
  `;

  const sources = parseSearchSources(rawResult);
  assert.equal(sources.length, 2);
  assert.equal(sources[0].title, "HyperSpace AGI Docs");
  assert.equal(sources[0].url, "https://github.com/hyperspace-agi/docs");
  assert.equal(sources[1].title, "Articolo Blog");
});

test("formatSearchContext include query e istruzione di risposta", () => {
  const ctx = formatSearchContext({
    query: "meteo milano",
    result: "- 18 gradi e soleggiato\n  https://meteo.it",
  });

  assert.match(ctx, /FONTI VERIFICATE DALLA RICERCA WEB PRIVATA/);
  assert.match(ctx, /meteo milano/);
  assert.match(ctx, /18 gradi e soleggiato/);
});
