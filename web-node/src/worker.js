// SPDX-License-Identifier: Apache-2.0
// web-node/src/worker.js
// Web Worker dedicato per l'esecuzione in background di compiti computazionali
// (WASM / JSON parsing / estrazione / embeddings con accelerazione WebGPU),
// preservando 60 FPS stabili sul thread UI.

import { runTask } from "./task-runner.js";
import {
  hasWebGpu,
  requestWebGpuAdapter,
  loadTransformers,
  createTransformersRuntime,
} from "./webgpu.js";

let activeRuntime = null;
let adapterInfo = null;

/**
 * Gestore principale dei messaggi all'interno del Web Worker.
 * Esposto per consentire unit test completi anche in ambienti Node.js con mock di postFn.
 */
export async function handleWorkerMessage(event, postFn = (msg) => self.postMessage(msg)) {
  const { id, type, task, config } = event?.data || {};

  if (type === "ping") {
    postFn({ id, ok: true, pong: true, timestamp: Date.now() });
    return;
  }

  if (type === "get_status") {
    const gpuAvailable = hasWebGpu(globalThis);
    postFn({
      id,
      ok: true,
      hasWebGpu: gpuAvailable,
      adapterInfo,
      hasRuntime: Boolean(activeRuntime),
      capabilities: activeRuntime
        ? ["embed_texts", "moderate", "summarize", "translate", "validate_json"]
        : ["moderate", "summarize", "validate_json"],
    });
    return;
  }

  if (type === "init_webgpu") {
    try {
      const gpuAvailable = hasWebGpu(globalThis);
      if (!gpuAvailable && !config?.forceSoftware) {
        postFn({
          id,
          ok: false,
          error: "WebGPU non disponibile nell'ambiente worker",
          capabilities: ["moderate", "summarize", "validate_json"],
        });
        return;
      }

      adapterInfo = await requestWebGpuAdapter(globalThis);
      postFn({
        id,
        type: "status",
        phase: "loading_transformers",
        message: "Caricamento modulo Transformers.js...",
      });

      const loader = config?.transformersLoader || loadTransformers;
      const transformers = await loader(config?.transformersUrl);

      activeRuntime = createTransformersRuntime({
        transformers,
        models: config?.models || {},
        onStatus: (status) => {
          postFn({ id, type: "status", ...status });
        },
      });

      // Warmup rapido modello embeddings se abilitato (default: true)
      if (config?.warmup !== false) {
        postFn({
          id,
          type: "status",
          phase: "warmup",
          message: "Warmup modello embeddings WebGPU...",
        });
        await activeRuntime.embed(["00mesh webgpu warmup"]);
      }

      postFn({
        id,
        ok: true,
        phase: "ready",
        adapterInfo,
        capabilities: [
          "embed_texts",
          "moderate",
          "summarize",
          "translate",
          "validate_json",
        ],
      });
    } catch (error) {
      activeRuntime = null;
      postFn({
        id,
        ok: false,
        error: error?.message || String(error),
        capabilities: ["moderate", "summarize", "validate_json"],
      });
    }
    return;
  }

  if (type === "run_task") {
    try {
      const result = await runTask(task, { runtime: activeRuntime });
      postFn({ id, ok: true, result });
    } catch (error) {
      postFn({ id, ok: false, error: error?.message || String(error) });
    }
    return;
  }
}

/**
 * Client lato Main Thread per orchestrare e comunicare con il Web Worker.
 */
export class WorkerClient {
  constructor({ worker = null, workerUrl = "./src/worker.js", env = globalThis } = {}) {
    this.env = env;
    this.workerUrl = workerUrl;
    this._externalWorker = worker;
    this.worker = worker;
    this._listeners = new Map();
    this.statusListeners = new Set();
    this._listenerAttached = false;
    if (this.worker) {
      this._setupListener();
    }
  }

  isSupported() {
    return Boolean(this._externalWorker || (this.env && typeof this.env.Worker === "function"));
  }

  init() {
    if (this.worker) return this.worker;
    if (!this.isSupported()) {
      throw new Error("I Web Worker non sono supportati in questo ambiente");
    }
    this.worker = new this.env.Worker(this.workerUrl, { type: "module" });
    this._setupListener();
    return this.worker;
  }

  _setupListener() {
    if (!this.worker || this._listenerAttached) return;
    this._listenerAttached = true;
    const onMsg = (event) => {
      const data = event?.data || {};
      if (data.type === "status") {
        // Avanzamento di una richiesta ancora in corso (stesso id): non la chiude.
        for (const listener of this.statusListeners) {
          try { listener(data); } catch {}
        }
        return;
      }
      if (data.id && this._listeners.has(data.id)) {
        const { resolve, reject } = this._listeners.get(data.id);
        this._listeners.delete(data.id);
        if (data.ok) {
          resolve(data);
        } else {
          reject(new Error(data.error || "Errore sconosciuto nel Web Worker"));
        }
      }
    };

    // Un worker che non si carica (404, MIME sbagliato, errore di import) non
    // risponde mai: senza questo ogni richiesta aspetterebbe il proprio timeout.
    const onError = (event) => {
      const message = event?.message || "Il Web Worker non si è avviato";
      for (const { reject } of this._listeners.values()) reject(new Error(message));
      this._listeners.clear();
    };

    if (typeof this.worker.addEventListener === "function") {
      this.worker.addEventListener("message", onMsg);
      this.worker.addEventListener("error", onError);
    } else {
      this.worker.onmessage = onMsg;
      this.worker.onerror = onError;
    }
  }

  post(type, payload = {}, { timeoutMs = 30000 } = {}) {
    this.init();
    const id = "wmsg-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this._listeners.delete(id);
        reject(new Error(`Timeout messaggio worker (${type}, ${timeoutMs}ms)`));
      }, timeoutMs);

      this._listeners.set(id, {
        resolve: (data) => {
          clearTimeout(timer);
          resolve(data);
        },
        reject: (err) => {
          clearTimeout(timer);
          reject(err);
        },
      });

      this.worker.postMessage({ id, type, ...payload });
    });
  }

  async ping() {
    const res = await this.post("ping", {}, { timeoutMs: 5000 });
    return res.pong === true;
  }

  async getStatus() {
    return await this.post("get_status", {}, { timeoutMs: 5000 });
  }

  async initWebGpu(config = {}, onStatus = null) {
    if (typeof onStatus === "function") {
      this.statusListeners.add(onStatus);
    }
    try {
      const res = await this.post("init_webgpu", { config }, { timeoutMs: 120000 });
      return res;
    } finally {
      if (typeof onStatus === "function") {
        this.statusListeners.delete(onStatus);
      }
    }
  }

  async runTask(task) {
    const timeoutMs = (task.timeoutMs || 30000) + 2000;
    const res = await this.post("run_task", { task }, { timeoutMs });
    return res.result;
  }

  terminate() {
    if (this.worker && typeof this.worker.terminate === "function") {
      this.worker.terminate();
    }
    this.worker = null;
    this._listeners.clear();
    this.statusListeners.clear();
  }
}

// Aggancio automatico solo quando siamo all'interno di un vero contesto Web Worker
const isDedicatedWorker = typeof WorkerGlobalScope !== "undefined"
  && typeof self !== "undefined"
  && self instanceof WorkerGlobalScope;

if (isDedicatedWorker) {
  self.onmessage = (event) => handleWorkerMessage(event, (msg) => self.postMessage(msg));
}
