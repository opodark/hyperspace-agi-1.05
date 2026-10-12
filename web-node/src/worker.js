// SPDX-License-Identifier: Apache-2.0
// web-node/src/worker.js
// Web Worker dedicato per l'esecuzione in background di compiti computazionali
// (WASM / JSON parsing / estrazione / embeddings), preservando 60 FPS sul thread UI.

import { runTask } from "./task-runner.js";

let activeRuntime = null;

self.onmessage = async (event) => {
  const { id, type, task } = event.data || {};
  if (type === "ping") {
    self.postMessage({ id, ok: true, pong: true });
    return;
  }

  if (type === "run_task") {
    try {
      const result = await runTask(task, { runtime: activeRuntime });
      self.postMessage({ id, ok: true, result });
    } catch (error) {
      self.postMessage({ id, ok: false, error: error?.message || String(error) });
    }
  }
};
