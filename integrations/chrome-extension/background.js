// SPDX-License-Identifier: Apache-2.0
/**
 * 00MESH Local Bridge — Background Service Worker
 * Connette motori di inferenza locali (Ollama, LM Studio) al network decentralizzato 00MESH.
 */

const DEFAULT_HUB_URL = "http://localhost:8085";
const OLLAMA_BASE = "http://localhost:11434";
const LMSTUDIO_BASE = "http://127.0.0.1:1234";
const POLL_TIMEOUT_S = 25;

let isPolling = false;
let pollingAbortController = null;

// Inizializzazione o recupero dello stato persistente
async function getOrInitState() {
  const defaults = {
    node_id: "ext-" + crypto.randomUUID().slice(0, 12),
    hub_url: DEFAULT_HUB_URL,
    solana_address: "",
    sharing_enabled: true,
    engines: {
      ollama: { online: false, models: [], url: OLLAMA_BASE },
      lmstudio: { online: false, models: [], url: LMSTUDIO_BASE }
    },
    stats: {
      tasks_completed: 0,
      tokens_served: 0,
      total_duration_ms: 0,
      last_active: null
    },
    last_log: "Inizializzazione completata."
  };

  const stored = await chrome.storage.local.get(Object.keys(defaults));
  const merged = { ...defaults, ...stored };
  await chrome.storage.local.set(merged);
  return merged;
}

// Scansione e rilevamento motori locali
async function scanLocalEngines() {
  const engines = {
    ollama: { online: false, models: [], url: OLLAMA_BASE },
    lmstudio: { online: false, models: [], url: LMSTUDIO_BASE }
  };

  // 1. Rileva Ollama
  try {
    const res = await fetch(`${OLLAMA_BASE}/api/tags`, {
      method: "GET",
      signal: AbortSignal.timeout(2500)
    });
    if (res.ok) {
      const data = await res.json();
      const models = (data.models || []).map(m => m.name || m.model);
      engines.ollama = { online: true, models, url: OLLAMA_BASE };
    }
  } catch (e) {
    engines.ollama.online = false;
  }

  // 2. Rileva LM Studio
  try {
    const res = await fetch(`${LMSTUDIO_BASE}/v1/models`, {
      method: "GET",
      signal: AbortSignal.timeout(2500)
    });
    if (res.ok) {
      const data = await res.json();
      const models = (data.data || []).map(m => m.id);
      engines.lmstudio = { online: true, models, url: LMSTUDIO_BASE };
    }
  } catch (e) {
    engines.lmstudio.online = false;
  }

  await chrome.storage.local.set({ engines });
  return engines;
}

// Registrazione del nodo presso l'hub 00MESH
async function registerNodeWithHub(hubUrl, nodeId, engines, solanaAddress) {
  const allModels = [
    ...(engines.ollama.online ? engines.ollama.models : []),
    ...(engines.lmstudio.online ? engines.lmstudio.models : [])
  ];

  const capabilities = [
    "inference",
    "v1-chat-completions",
    ...(engines.ollama.online ? ["ollama"] : []),
    ...(engines.lmstudio.online ? ["lmstudio"] : []),
    ...allModels
  ];

  const payload = {
    node_id: nodeId,
    capabilities: [...new Set(capabilities)],
    label: `Chrome Bridge (${allModels.length} models)`,
    browser: "Chrome Extension 00MESH Local Bridge v1.0",
    models: allModels,
    limits: { concurrency: 1 },
    solana_address: solanaAddress || undefined
  };

  try {
    const res = await fetch(`${hubUrl}/web/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000)
    });
    return res.ok;
  } catch (e) {
    return false;
  }
}

// Esecuzione del task di inferenza su motore locale
async function executeInferenceTask(task, engines) {
  const payload = task.payload || {};
  const requestedModel = payload.model || "";
  const t0 = performance.now();

  let targetUrl = "";
  if (engines.ollama.online && (engines.ollama.models.includes(requestedModel) || !engines.lmstudio.online)) {
    targetUrl = `${OLLAMA_BASE}/v1/chat/completions`;
  } else if (engines.lmstudio.online) {
    targetUrl = `${LMSTUDIO_BASE}/v1/chat/completions`;
  } else {
    throw new Error("Nessun motore locale attivo per eseguire il task.");
  }

  // Prepara richiesta standard OpenAI compatibile
  const chatReq = {
    model: requestedModel || (engines.ollama.models[0] || engines.lmstudio.models[0]),
    messages: payload.messages || [{ role: "user", content: payload.prompt || "ping" }],
    stream: false,
    max_tokens: payload.max_tokens || 512,
    temperature: payload.temperature ?? 0.7
  };

  const res = await fetch(targetUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(chatReq),
    signal: AbortSignal.timeout(60000)
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Inference engine error HTTP ${res.status}: ${errText.slice(0, 100)}`);
  }

  const data = await res.json();
  const durationMs = Math.round(performance.now() - t0);
  const choice = (data.choices && data.choices[0]) || {};
  const usage = data.usage || {};
  const tokensGen = usage.completion_tokens || 0;

  return {
    content: choice.message ? choice.message.content : "",
    model: data.model || chatReq.model,
    tokens_generated: tokensGen,
    duration_ms: durationMs
  };
}

// Ciclo di polling bidirezionale
async function runPollingLoop() {
  if (isPolling) return;
  isPolling = true;

  while (isPolling) {
    const state = await getOrInitState();
    if (!state.sharing_enabled) {
      isPolling = false;
      break;
    }

    const engines = await scanLocalEngines();
    const hasAnyEngine = engines.ollama.online || engines.lmstudio.online;

    if (!hasAnyEngine) {
      await chrome.storage.local.set({ last_log: "In attesa: nessun motore locale attivo (Ollama o LM Studio non raggiungibili)." });
      await new Promise(r => setTimeout(r, 8000));
      continue;
    }

    // Registra nodo all'hub
    const registered = await registerNodeWithHub(state.hub_url, state.node_id, engines, state.solana_address);
    if (!registered) {
      await chrome.storage.local.set({ last_log: `Impossibile raggiungere l'hub 00MESH su ${state.hub_url}. Riprovo tra 10s...` });
      await new Promise(r => setTimeout(r, 10000));
      continue;
    }

    await chrome.storage.local.set({ last_log: `Connesso all'hub 00MESH (${engines.ollama.models.length + engines.lmstudio.models.length} modelli condivisi). In ascolto di task...` });

    // Long-poll per task
    try {
      pollingAbortController = new AbortController();
      const pollRes = await fetch(`${state.hub_url}/web/poll`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: state.node_id,
          timeout_s: POLL_TIMEOUT_S
        }),
        signal: pollingAbortController.signal
      });

      if (pollRes.ok) {
        const pollData = await pollRes.json();
        const task = pollData.task;

        if (task && task.task_id) {
          await chrome.storage.local.set({ last_log: `Esecuzione task ${task.task_id.slice(0, 8)} (${task.type || 'inferenza'})...` });

          try {
            const execResult = await executeInferenceTask(task, engines);

            // Invia risultato completato all'hub
            await fetch(`${state.hub_url}/web/result`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                node_id: state.node_id,
                task_id: task.task_id,
                ok: true,
                result: execResult,
                duration_ms: execResult.duration_ms
              })
            });

            // Aggiorna metriche locali
            const curStats = state.stats || {};
            curStats.tasks_completed = (curStats.tasks_completed || 0) + 1;
            curStats.tokens_served = (curStats.tokens_served || 0) + (execResult.tokens_generated || 0);
            curStats.total_duration_ms = (curStats.total_duration_ms || 0) + execResult.duration_ms;
            curStats.last_active = new Date().toISOString();

            await chrome.storage.local.set({
              stats: curStats,
              last_log: `Task ${task.task_id.slice(0, 8)} completato con successo (+${execResult.tokens_generated} tokens in ${execResult.duration_ms}ms)!`
            });
          } catch (taskErr) {
            await fetch(`${state.hub_url}/web/result`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                node_id: state.node_id,
                task_id: task.task_id,
                ok: false,
                error: taskErr.message
              })
            }).catch(() => {});

            await chrome.storage.local.set({ last_log: `Errore durante il task: ${taskErr.message}` });
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        await new Promise(r => setTimeout(r, 3000));
      }
    }
  }
}

// Gestione messaggi inviati dalla UI Popup
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (msg.type === "GET_STATE") {
      const state = await getOrInitState();
      sendResponse(state);
    } else if (msg.type === "SCAN_ENGINES") {
      const engines = await scanLocalEngines();
      sendResponse(engines);
    } else if (msg.type === "TOGGLE_SHARING") {
      const state = await getOrInitState();
      const updated = !state.sharing_enabled;
      await chrome.storage.local.set({ sharing_enabled: updated });
      if (updated) {
        runPollingLoop();
      } else if (pollingAbortController) {
        pollingAbortController.abort();
        isPolling = false;
      }
      sendResponse({ sharing_enabled: updated });
    } else if (msg.type === "SET_HUB") {
      await chrome.storage.local.set({ hub_url: msg.hub_url });
      sendResponse({ ok: true });
    } else if (msg.type === "SET_WALLET") {
      await chrome.storage.local.set({ solana_address: msg.solana_address });
      sendResponse({ ok: true });
    } else if (msg.type === "TEST_LOCAL_INFERENCE") {
      const engines = await scanLocalEngines();
      try {
        const dummyTask = {
          task_id: "test-" + Date.now(),
          payload: { prompt: "Rispondi con '00MESH OK' in due parole.", max_tokens: 10 }
        };
        const res = await executeInferenceTask(dummyTask, engines);
        sendResponse({ ok: true, result: res });
      } catch (err) {
        sendResponse({ ok: false, error: err.message });
      }
    }
  })();
  return true; // Asynchronous response
});

// Allarmi e routine di avvio
chrome.alarms.create("mesh_keepalive", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "mesh_keepalive") {
    runPollingLoop();
  }
});

// Avvia automaticamente il loop all'inizializzazione
runPollingLoop();
