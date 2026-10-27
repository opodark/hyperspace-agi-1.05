// SPDX-License-Identifier: Apache-2.0
// web-node/tests/worker.test.mjs
// Test unitari del Web Worker e del WorkerClient off-thread (WebGPU / CPU).
//
//   node web-node/tests/worker.test.mjs

import assert from "node:assert/strict";
import { handleWorkerMessage, WorkerClient } from "../src/worker.js";
import { WebNode } from "../src/index.js";

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

console.log("== Web Worker: messaggi interni (handleWorkerMessage) ==");

await check("ping risponde con pong e timestamp", async () => {
  let reply = null;
  await handleWorkerMessage({ data: { id: "test-1", type: "ping" } }, (msg) => { reply = msg; });
  assert.equal(reply.id, "test-1");
  assert.equal(reply.ok, true);
  assert.equal(reply.pong, true);
  assert.ok(typeof reply.timestamp === "number");
});

await check("get_status restituisce stato e capability base", async () => {
  let reply = null;
  await handleWorkerMessage({ data: { id: "test-2", type: "get_status" } }, (msg) => { reply = msg; });
  assert.equal(reply.id, "test-2");
  assert.equal(reply.ok, true);
  assert.deepEqual(reply.capabilities, ["moderate", "summarize", "validate_json"]);
});

await check("run_task esegue validate_json", async () => {
  let reply = null;
  const task = {
    taskId: "t-val",
    type: "validate_json",
    payload: { text: JSON.stringify({ name: "00MESH", active: true }), schema: { type: "object", required: ["name"] } },
    timeoutMs: 5000,
  };
  await handleWorkerMessage({ data: { id: "test-3", type: "run_task", task } }, (msg) => { reply = msg; });
  assert.equal(reply.ok, true);
  assert.equal(reply.result.valid, true);
  assert.equal(reply.result.parsed.name, "00MESH");
});

await check("run_task esegue moderate euristico", async () => {
  let reply = null;
  const task = {
    taskId: "t-mod",
    type: "moderate",
    payload: { text: "Contatto: info@example.com per assistenza" },
    timeoutMs: 5000,
  };
  await handleWorkerMessage({ data: { id: "test-4", type: "run_task", task } }, (msg) => { reply = msg; });
  assert.equal(reply.ok, true);
  assert.equal(reply.result.flagged, true);
  assert.ok(reply.result.categories.includes("personal_data"));
});

await check("init_webgpu con mock transformers eleva le capability ad embed_texts", async () => {
  const replies = [];
  const fakeTransformers = {
    pipeline: async (task, model) => {
      return async (texts) => ({
        tolist: () => (Array.isArray(texts) ? texts : [texts]).map(() => [0.15, 0.85]),
      });
    },
  };

  await handleWorkerMessage({
    data: {
      id: "test-init",
      type: "init_webgpu",
      config: {
        forceSoftware: true,
        warmup: false,
        transformersLoader: async () => fakeTransformers,
      },
    },
  }, (msg) => { replies.push(msg); });

  const finalReply = replies.find((r) => r.phase === "ready");
  assert.ok(finalReply, "Deve completare con phase ready");
  assert.equal(finalReply.ok, true);
  assert.ok(finalReply.capabilities.includes("embed_texts"));
  assert.ok(finalReply.capabilities.includes("translate"));

  // Ora run_task su embed_texts deve funzionare nel worker!
  let embedReply = null;
  const embedTask = {
    taskId: "t-embed",
    type: "embed_texts",
    payload: { texts: ["test embedding off-thread"] },
    timeoutMs: 5000,
  };
  await handleWorkerMessage({ data: { id: "test-embed-task", type: "run_task", task: embedTask } }, (msg) => { embedReply = msg; });
  assert.equal(embedReply.ok, true);
  assert.deepEqual(embedReply.result.vectors, [[0.15, 0.85]]);
});

console.log("== WorkerClient & Orchestrazione Main Thread ==");

/** Finto Worker del browser che simula l'interfaccia W3C Worker */
class MockWorker {
  constructor() {
    this.onmessage = null;
    this.listeners = new Set();
  }
  addEventListener(event, fn) { if (event === "message") this.listeners.add(fn); }
  removeEventListener(event, fn) { if (event === "message") this.listeners.delete(fn); }
  postMessage(data) {
    // Risponde asincronamente richiamando handleWorkerMessage
    setImmediate(async () => {
      await handleWorkerMessage({ data }, (msg) => {
        const ev = { data: msg };
        if (typeof this.onmessage === "function") this.onmessage(ev);
        for (const l of this.listeners) l(ev);
      });
    });
  }
  terminate() {
    this.listeners.clear();
    this.onmessage = null;
  }
}

await check("WorkerClient comunica tramite ping-pong", async () => {
  const mock = new MockWorker();
  const client = new WorkerClient({ worker: mock });
  const pong = await client.ping();
  assert.equal(pong, true);
});

await check("WorkerClient esegue runTask e restituisce il risultato", async () => {
  const mock = new MockWorker();
  const client = new WorkerClient({ worker: mock });
  const result = await client.runTask({
    taskId: "t-wc",
    type: "validate_json",
    payload: { text: '{"status":"ok"}' },
    timeoutMs: 5000,
  });
  assert.equal(result.valid, true);
});

console.log("== WebNode con Worker Off-Thread ==");

await check("WebNode esegue tick() delegando il lavoro al WorkerClient", async () => {
  const mock = new MockWorker();
  const client = new WorkerClient({ worker: mock });

  let pollCount = 0;
  let resultReceived = null;

  const fakeFetch = async (url, options) => {
    const body = options?.body ? JSON.parse(options.body) : {};
    if (url.includes("/web/register")) {
      return { ok: true, status: 200, json: async () => ({ ok: true, node_id: "w-node-1" }) };
    }
    if (url.includes("/web/poll")) {
      pollCount += 1;
      if (pollCount === 1) {
        return {
          ok: true, status: 200,
          json: async () => ({
            ok: true,
            task: {
              task_id: "task-offthread-1",
              type: "validate_json",
              payload: { text: '{"mesh":"00MESH","active":true}' },
            },
          }),
        };
      }
      return { ok: true, status: 200, json: async () => ({ ok: true, task: null }) };
    }
    if (url.includes("/web/result")) {
      resultReceived = body;
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  };

  const node = new WebNode({
    baseUrl: "http://cp:8085",
    nodeId: "w-node-1",
    consent: true,
    worker: client,
    fetchImpl: fakeFetch,
  });

  assert.equal(node.state.workerActive, true);
  await node.register();
  const handled = await node.tick();

  assert.ok(handled, "Deve gestire il task dal poll");
  assert.equal(handled.taskId, "task-offthread-1");
  if (node.state.lastError) console.error("TICK ERROR:", node.state.lastError);
  assert.equal(node.state.tasksDone, 1);
  assert.ok(resultReceived, "Deve aver pubblicato il risultato");
  assert.equal(resultReceived.task_id, "task-offthread-1");
  assert.equal(resultReceived.ok, true);
  assert.equal(resultReceived.result.valid, true);

  node.stop();
  assert.equal(node.state.workerActive, false);
});

console.log("\n== WorkerClient con un worker asincrono (come nel browser) ==");

// Worker finto con la semantica di postMessage: consegna asincrona, messaggi gestiti
// dal vero handleWorkerMessage. I test sopra chiamano l'handler direttamente e non
// passano dal client: per questo non vedevano i messaggi di stato.
class AsyncFakeWorker {
  constructor(extraConfig = {}) { this.listeners = { message: [], error: [] }; this.extraConfig = extraConfig; }
  addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
  postMessage(data) {
    const payload = { ...data, config: { ...(data.config || {}), ...this.extraConfig } };
    setTimeout(() => handleWorkerMessage({ data: payload },
      (msg) => setTimeout(() => this.listeners.message.forEach((fn) => fn({ data: msg })), 0)), 0);
  }
  fail(message) { this.listeners.error.forEach((fn) => fn({ message })); }
  terminate() {}
}

const mockLoader = async () => ({
  env: {},
  pipeline: async () => async (texts) => ({ tolist: () => texts.map(() => [0.1, 0.2, 0.3]) }),
});

await check("initWebGpu arriva a ready anche con i messaggi di stato intermedi", async () => {
  const worker = new AsyncFakeWorker({ forceSoftware: true, transformersLoader: mockLoader });
  const client = new WorkerClient({ worker });
  const phases = [];
  const res = await client.initWebGpu({}, (st) => phases.push(st.phase));
  assert.equal(res.phase, "ready");
  assert.ok(res.capabilities.includes("embed_texts"));
  // Le fasi di avanzamento arrivano tutte al chiamante, e nessuna chiude la richiesta.
  for (const phase of ["loading_transformers", "warmup", "loading", "ready"]) {
    assert.ok(phases.includes(phase), `fase ${phase} non ricevuta`);
  }
});

await check("un errore del worker rifiuta subito le richieste in attesa", async () => {
  const worker = new AsyncFakeWorker();
  worker.postMessage = () => {};          // il worker non risponde mai
  const client = new WorkerClient({ worker });
  const started = Date.now();
  const pending = client.post("ping", {}, { timeoutMs: 10000 });
  setTimeout(() => worker.fail("modulo non trovato"), 10);
  await assert.rejects(pending, /modulo non trovato/);
  assert.ok(Date.now() - started < 2000, "non deve aspettare il timeout");
});

console.log(`\nPASS worker: ${passed} check su Web Worker e WorkerClient completati con successo.`);
