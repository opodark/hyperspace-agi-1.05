// SPDX-License-Identifier: Apache-2.0
/**
 * 00MESH Local Bridge — Background Service Worker
 * Connette motori di inferenza locali (Ollama, LM Studio) al network decentralizzato 00MESH.
 */

const DEFAULT_HUB_URL = "http://localhost:8085";
const OLLAMA_BASE = "http://localhost:11434";
const LMSTUDIO_BASE = "http://127.0.0.1:1234";
const COMFYUI_BASE = "http://127.0.0.1:8188";
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
      lmstudio: { online: false, models: [], url: LMSTUDIO_BASE },
      comfyui: { online: false, device: "", vram_free: "", url: COMFYUI_BASE, models: [] }
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
    lmstudio: { online: false, models: [], url: LMSTUDIO_BASE },
    comfyui: { online: false, device: "", vram_free: "", url: COMFYUI_BASE, models: [] }
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

  // 3. Rileva ComfyUI (Generazione Immagini su GPU locale)
  try {
    const res = await fetch(`${COMFYUI_BASE}/system_stats`, {
      method: "GET",
      signal: AbortSignal.timeout(2500)
    });
    if (res.ok) {
      const data = await res.json();
      const devices = data.devices || [];
      const gpuName = devices[0]?.name || "Local GPU";
      const vramFree = devices[0]?.vram_free ? (Math.round(devices[0].vram_free / (1024 * 1024 * 1024) * 10) / 10) + " GB" : "";
      engines.comfyui = {
        online: true,
        device: gpuName,
        vram_free: vramFree,
        url: COMFYUI_BASE,
        models: ["flux", "sdxl", "sd15"]
      };
    }
  } catch (e) {
    engines.comfyui.online = false;
  }

  await chrome.storage.local.set({ engines });
  return engines;
}

// Registrazione del nodo presso l'hub 00MESH
async function registerNodeWithHub(hubUrl, nodeId, engines, solanaAddress) {
  const allModels = [
    ...(engines.ollama.online ? engines.ollama.models : []),
    ...(engines.lmstudio.online ? engines.lmstudio.models : []),
    ...(engines.comfyui.online ? ["comfyui", "image-generate", "flux", "sdxl"] : [])
  ];

  const capabilities = [
    "inference",
    "v1-chat-completions",
    ...(engines.ollama.online ? ["ollama"] : []),
    ...(engines.lmstudio.online ? ["lmstudio"] : []),
    ...(engines.comfyui.online ? ["comfyui", "image_generate", "flux", "sdxl"] : []),
    ...allModels
  ];

  const activeEngineCount = (engines.ollama.online ? 1 : 0) + (engines.lmstudio.online ? 1 : 0) + (engines.comfyui.online ? 1 : 0);
  const payload = {
    node_id: nodeId,
    capabilities: [...new Set(capabilities)],
    label: `Chrome Bridge (${activeEngineCount} motori, ${allModels.length} modelli)`,
    browser: "Chrome Extension 00MESH Local Bridge v1.1",
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

// Esecuzione del task di generazione immagini su ComfyUI locale
async function executeComfyUiTask(task, comfyEngine) {
  const payload = task.payload || {};
  const t0 = performance.now();
  const comfyBase = comfyEngine.url || COMFYUI_BASE;
  const promptText = payload.prompt || "a breathtaking futuristic cyberpunk digital companion, high-tech neon lights, 8k resolution, anime visual novel style";
  const negativePrompt = payload.negative_prompt || "blurry, low quality, distorted anatomy, disfigured";

  let workflow = payload.workflow;
  if (!workflow) {
    workflow = {
      "3": {
        "class_type": "KSampler",
        "inputs": {
          "cfg": 7,
          "denoise": 1,
          "latent_image": ["5", 0],
          "model": ["4", 0],
          "negative": ["7", 0],
          "positive": ["6", 0],
          "sampler_name": "euler",
          "scheduler": "normal",
          "seed": Math.floor(Math.random() * 1000000000),
          "steps": payload.steps || 20
        }
      },
      "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
          "ckpt_name": payload.checkpoint || "v1-5-pruned-emaonly.safetensors"
        }
      },
      "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
          "batch_size": 1,
          "height": payload.height || 512,
          "width": payload.width || 512
        }
      },
      "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": promptText
        }
      },
      "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
          "clip": ["4", 1],
          "text": negativePrompt
        }
      },
      "8": {
        "class_type": "VAEDecode",
        "inputs": {
          "samples": ["3", 0],
          "vae": ["4", 2]
        }
      },
      "9": {
        "class_type": "SaveImage",
        "inputs": {
          "filename_prefix": "00MESH_Gen",
          "images": ["8", 0]
        }
      }
    };
  }

  const queueRes = await fetch(`${comfyBase}/prompt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: workflow }),
    signal: AbortSignal.timeout(10000)
  });

  if (!queueRes.ok) {
    const err = await queueRes.text();
    throw new Error(`ComfyUI queue error: ${err.slice(0, 100)}`);
  }

  const queueData = await queueRes.json();
  const promptId = queueData.prompt_id;
  if (!promptId) throw new Error("ComfyUI non ha restituito un prompt_id.");

  let imageInfo = null;
  const pollStart = Date.now();
  while (Date.now() - pollStart < 90000) {
    await new Promise(r => setTimeout(r, 1500));
    try {
      const histRes = await fetch(`${comfyBase}/history/${promptId}`);
      if (histRes.ok) {
        const histData = await histRes.json();
        const promptHist = histData[promptId];
        if (promptHist && promptHist.outputs) {
          for (const nodeId of Object.keys(promptHist.outputs)) {
            const nodeOut = promptHist.outputs[nodeId];
            if (nodeOut.images && nodeOut.images.length > 0) {
              imageInfo = nodeOut.images[0];
              break;
            }
          }
          if (imageInfo) break;
        }
      }
    } catch (e) {}
  }

  if (!imageInfo) {
    throw new Error("ComfyUI timeout: generazione immagine non completata entro 90s.");
  }

  const durationMs = Math.round(performance.now() - t0);
  const imageUrl = `${comfyBase}/view?filename=${encodeURIComponent(imageInfo.filename)}&subfolder=${encodeURIComponent(imageInfo.subfolder || "")}&type=${encodeURIComponent(imageInfo.type || "output")}`;

  return {
    image_url: imageUrl,
    filename: imageInfo.filename,
    engine: "comfyui",
    duration_ms: durationMs,
    tokens_generated: 150 // Calcolo PoUW equivalente per generazione su GPU
  };
}

// Esecuzione del task di inferenza su motore locale
async function executeInferenceTask(task, engines) {
  // Se è un task di generazione immagini e ComfyUI è disponibile
  if ((task.type === "image_generate" || task.type === "image") && engines.comfyui?.online) {
    return await executeComfyUiTask(task, engines.comfyui);
  }

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
    const hasAnyEngine = engines.ollama.online || engines.lmstudio.online || engines.comfyui.online;

    if (!hasAnyEngine) {
      await chrome.storage.local.set({ last_log: "In attesa: nessun motore locale attivo (Ollama, LM Studio o ComfyUI non raggiungibili)." });
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

    const engineNames = [];
    if (engines.ollama.online) engineNames.push(`Ollama (${engines.ollama.models.length} mod)`);
    if (engines.lmstudio.online) engineNames.push(`LM Studio (${engines.lmstudio.models.length} mod)`);
    if (engines.comfyui.online) engineNames.push(`ComfyUI (${engines.comfyui.device || "GPU"})`);

    await chrome.storage.local.set({ last_log: `Connesso all'hub 00MESH [${engineNames.join(" + ")}]. In ascolto di task...` });

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
    if (msg.type === "GET_STATE" || msg.type === "GET_BRIDGE_STATUS") {
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
