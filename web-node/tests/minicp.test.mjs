// SPDX-License-Identifier: Apache-2.0
// web-node/tests/minicp.test.mjs
import assert from "node:assert/strict";
import test from "node:test";
import { evaluateMath, summarizeText, MiniControlPlane } from "../src/minicp.js";

test("evaluateMath: esegue operazioni aritmetiche con precedenza corretta", () => {
  assert.equal(evaluateMath("10 + 2 * 5"), 20);
  assert.equal(evaluateMath("(10 + 2) * 5"), 60);
  assert.equal(evaluateMath("100 / 4 - 5"), 20);
});

test("evaluateMath: supporta potenze (^), costanti (pi, e) e percentuali (%)", () => {
  assert.equal(evaluateMath("2 ^ 4"), 16);
  assert.equal(evaluateMath("10% * 250"), 25);
  assert.equal(Math.round(evaluateMath("pi * 2")), Math.round(Math.PI * 2));
});

test("evaluateMath: supporta funzioni matematiche (sqrt, abs, round, min, max)", () => {
  assert.equal(evaluateMath("sqrt(144)"), 12);
  assert.equal(evaluateMath("abs(-42)"), 42);
  assert.equal(evaluateMath("min(10, 5, 20)"), 5);
  assert.equal(evaluateMath("max(10, 5, 20)"), 20);
  assert.equal(evaluateMath("round(4.6)"), 5);
  assert.equal(evaluateMath("10,5 + 2,5"), 13);
});

test("evaluateMath: respinge espressioni non sicure o codice iniettato", () => {
  assert.throws(() => evaluateMath("process.exit()"), /Caratteri o funzioni non permesse/);
  assert.throws(() => evaluateMath("alert(1)"), /Caratteri o funzioni non permesse/);
  assert.throws(() => evaluateMath("fetch('http://evil.com')"), /Caratteri o funzioni non permesse/);
  assert.throws(() => evaluateMath(""), /Espressione matematica vuota/);
});

test("summarizeText: estrae le frasi chiave basandosi sulla frequenza dei termini", () => {
  const text = `
    HyperSpace è una rete decentralizzata di nodi di calcolo.
    Oggi c'è una bella giornata di sole.
    Ogni nodo della rete coordina compiti di inferenza distribuiti.
    I nodi di calcolo garantiscono resilienza e sovranità dei dati.
  `;
  const summary = summarizeText(text, 2);
  assert.ok(summary.includes("nodi"));
  assert.ok(!summary.includes("Oggi c'è una bella giornata"));
  assert.ok(summary.length < text.trim().length);
});

test("MiniControlPlane: registra i tool essenziali client-side", () => {
  const mcp = new MiniControlPlane({ gatewayUrl: "https://mesh.test" });
  const tools = mcp.listTools();
  const names = tools.map((t) => t.name);

  assert.ok(names.includes("calc"));
  assert.ok(names.includes("summarize"));
  assert.ok(names.includes("web_search"));
  assert.ok(names.includes("code_sandbox"));
  assert.ok(names.includes("system_status"));
});

test("MiniControlPlane: handleSlashCommand riconosce e smista /help, /calc, /summary, /clear", async () => {
  const mcp = new MiniControlPlane({ gatewayUrl: "https://mesh.test" });

  // Input normale non slash
  const normal = await mcp.handleSlashCommand("ciao come va?");
  assert.equal(normal.handled, false);

  // /help
  const help = await mcp.handleSlashCommand("/help");
  assert.equal(help.handled, true);
  assert.match(help.content, /Mini-CP Autonomo/);
  assert.match(help.content, /\/calc/);

  // /calc
  const calc = await mcp.handleSlashCommand("/calc 50 * 3 + sqrt(25)");
  assert.equal(calc.handled, true);
  assert.match(calc.content, /155/);

  // /clear
  const clear = await mcp.handleSlashCommand("/clear");
  assert.equal(clear.handled, true);
  assert.equal(clear.isAction, "clear");

  // Comando sconosciuto
  const unknown = await mcp.handleSlashCommand("/foobar");
  assert.equal(unknown.handled, true);
  assert.match(unknown.content, /non riconosciuto/);
});

test("MiniControlPlane: handleSlashCommand /status interroga il gateway e genera telemetria", async () => {
  const fakeFetch = async (url) => {
    return {
      ok: true,
      status: 200,
      json: async () => ({ data: [{ id: "qwen3:8b" }] }),
    };
  };

  const mcp = new MiniControlPlane({
    gatewayUrl: "https://mesh.test",
    fetchImpl: fakeFetch,
    activeBridge: { active: true, label: "RTX 4090 Bridge" },
  });

  const res = await mcp.handleSlashCommand("/status");
  assert.equal(res.handled, true);
  assert.match(res.content, /Stato Diagnostico Mini-CP/);
  assert.match(res.content, /RTX 4090 Bridge/);
  assert.match(res.content, /Online/);
});
