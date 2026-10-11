// SPDX-License-Identifier: Apache-2.0
// web-node/tests/topology.test.mjs
// Test del client di topologia pubblica (/web/topology) con mock fetch.
import assert from "node:assert/strict";
import { fetchTopology, sanitizeTopologyData } from "../src/topology.js";

let passed = 0;
async function check(label, fn) {
  try {
    await fn();
    passed += 1;
    console.log(`ok   ${label}`);
  } catch (error) {
    console.error(`FAIL ${label}: ${error.message}`);
    process.exitCode = 1;
  }
}

console.log("== topologia mesh pubblica ==");

await check("sanitizeTopologyData fornisce valori di default robusti su dati vuoti o null", () => {
  const empty = sanitizeTopologyData(null);
  assert.equal(empty.ok, false);
  assert.equal(empty.machines.length, 0);
  assert.equal(empty.models.length, 0);
  assert.equal(empty.totals.machines, 0);

  const partial = sanitizeTopologyData({
    ok: true,
    machines: [{ label: "macchina-1", load: "0.45", vram_gb: "24", models: ["m1"] }],
  });
  assert.equal(partial.ok, true);
  assert.equal(partial.machines.length, 1);
  assert.equal(partial.machines[0].label, "macchina-1");
  assert.equal(partial.machines[0].load, 0.45);
  assert.equal(partial.machines[0].vram_gb, 24);
  assert.equal(partial.machines[0].models[0], "m1");
  assert.equal(partial.totals.machines, 1);
});

await check("fetchTopology effettua la chiamata GET /web/topology e restituisce i dati sanificati", async () => {
  const calls = [];
  const fakeFetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        hub: { label: "Control Plane", online: true, models: [], model_count: 0 },
        machines: [
          { label: "rig-1", tier: "worker", models: ["qwen-2.5", "llama-3.3"], model_count: 2, load: 0.2, vram_gb: 24, last_seen_s: 2 },
        ],
        browsers: { count: 3, capabilities: ["regex", "json"] },
        models: ["qwen-2.5", "llama-3.3"],
        totals: { machines: 1, models: 2, browsers: 3 },
      }),
    };
  };

  const data = await fetchTopology({
    baseUrls: ["https://gateway.example.com"],
    fetchImpl: fakeFetch,
  });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://gateway.example.com/web/topology");
  assert.equal(data.ok, true);
  assert.equal(data.machines.length, 1);
  assert.equal(data.machines[0].label, "rig-1");
  assert.equal(data.machines[0].vram_gb, 24);
  assert.equal(data.totals.browsers, 3);
});

await check("fetchTopology esegue il fallback al secondo endpoint se il primo fallisce", async () => {
  const calls = [];
  const fakeFetch = async (url) => {
    calls.push(url);
    if (url.includes("gw1")) {
      throw new Error("Connessione fallita");
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        machines: [{ label: "node-backup" }],
        totals: { machines: 1, models: 0, browsers: 0 },
      }),
    };
  };

  const data = await fetchTopology({
    baseUrls: ["https://gw1.example.com", "https://gw2.example.com"],
    fetchImpl: fakeFetch,
  });

  assert.equal(calls.length, 2);
  assert.equal(calls[0], "https://gw1.example.com/web/topology");
  assert.equal(calls[1], "https://gw2.example.com/web/topology");
  assert.equal(data.machines[0].label, "node-backup");
});

console.log(`\nPASS topology: ${passed} check su client e sanitizzazione topologia`);
