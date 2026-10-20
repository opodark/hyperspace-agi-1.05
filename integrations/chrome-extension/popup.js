// SPDX-License-Identifier: Apache-2.0
/**
 * 00MESH Local Bridge — Popup UI Controller
 */

document.addEventListener("DOMContentLoaded", async () => {
  const statusDot = document.getElementById("status-dot");
  const statusText = document.getElementById("status-text");
  const toggleSharing = document.getElementById("toggle-sharing");
  const btnRefreshEngines = document.getElementById("btn-refresh-engines");
  const dotOllama = document.getElementById("dot-ollama");
  const badgeOllama = document.getElementById("badge-ollama");
  const dotLmstudio = document.getElementById("dot-lmstudio");
  const badgeLmstudio = document.getElementById("badge-lmstudio");
  const dotComfyui = document.getElementById("dot-comfyui");
  const badgeComfyui = document.getElementById("badge-comfyui");
  const modelsPreview = document.getElementById("models-preview");
  const statTasks = document.getElementById("stat-tasks");
  const statTokens = document.getElementById("stat-tokens");
  const statLatency = document.getElementById("stat-latency");
  const hubUrlInput = document.getElementById("hub-url");
  const btnSaveHub = document.getElementById("btn-save-hub");
  const solanaInput = document.getElementById("solana-address");
  const btnSaveWallet = document.getElementById("btn-save-wallet");
  const nodeIdElem = document.getElementById("node-id");
  const btnTestInfer = document.getElementById("btn-test-infer");
  const logBanner = document.getElementById("log-banner");

  async function updateUI() {
    chrome.runtime.sendMessage({ type: "GET_STATE" }, (state) => {
      if (!state) return;

      // Toggle sharing
      toggleSharing.checked = Boolean(state.sharing_enabled);

      // Status Pill
      if (!state.sharing_enabled) {
        statusDot.className = "status-dot inactive";
        statusText.textContent = "Sospeso";
      } else {
        const hasEngines = Boolean(state.engines?.ollama?.online || state.engines?.lmstudio?.online || state.engines?.comfyui?.online);
        if (hasEngines) {
          statusDot.className = "status-dot active";
          statusText.textContent = "Connesso & In Ascolto";
        } else {
          statusDot.className = "status-dot inactive";
          statusText.textContent = "Nessun motore locale";
        }
      }

      // Motori Locali
      const o = state.engines?.ollama || {};
      if (o.online) {
        dotOllama.className = "engine-dot online";
        badgeOllama.className = "badge success";
        badgeOllama.textContent = `${o.models?.length || 0} modelli`;
      } else {
        dotOllama.className = "engine-dot";
        badgeOllama.className = "badge";
        badgeOllama.textContent = "Offline";
      }

      const lm = state.engines?.lmstudio || {};
      if (lm.online) {
        dotLmstudio.className = "engine-dot online";
        badgeLmstudio.className = "badge success";
        badgeLmstudio.textContent = `${lm.models?.length || 0} modelli`;
      } else {
        dotLmstudio.className = "engine-dot";
        badgeLmstudio.className = "badge";
        badgeLmstudio.textContent = "Offline";
      }

      const cm = state.engines?.comfyui || {};
      if (cm.online) {
        dotComfyui.className = "engine-dot online";
        badgeComfyui.className = "badge success";
        badgeComfyui.textContent = cm.vram_free ? `Online · ${cm.vram_free}` : "Online (GPU)";
      } else {
        dotComfyui.className = "engine-dot";
        badgeComfyui.className = "badge";
        badgeComfyui.textContent = "Offline";
      }

      const allModels = [
        ...(o.models || []),
        ...(lm.models || []),
        ...(cm.online ? ["ComfyUI (Image Gen)"] : [])
      ];
      if (allModels.length > 0) {
        modelsPreview.textContent = `Condivisi: ${allModels.slice(0, 4).join(", ")}${allModels.length > 4 ? ` (+${allModels.length - 4} altri)` : ""}`;
      } else {
        modelsPreview.textContent = "Nessun motore locale rilevato (avvia Ollama, LM Studio o ComfyUI).";
      }

      // Metriche
      const stats = state.stats || {};
      statTasks.textContent = stats.tasks_completed || 0;
      statTokens.textContent = stats.tokens_served || 0;

      const avgMs = stats.tasks_completed ? Math.round(stats.total_duration_ms / stats.tasks_completed) : 0;
      statLatency.textContent = `${avgMs}ms`;

      // Form
      if (document.activeElement !== hubUrlInput) {
        hubUrlInput.value = state.hub_url || "";
      }
      if (document.activeElement !== solanaInput) {
        solanaInput.value = state.solana_address || "";
      }
      nodeIdElem.textContent = state.node_id || "-";
      logBanner.textContent = state.last_log || "In attesa...";
    });
  }

  // Event Listeners
  toggleSharing.addEventListener("change", () => {
    chrome.runtime.sendMessage({ type: "TOGGLE_SHARING" }, () => updateUI());
  });

  btnRefreshEngines.addEventListener("click", () => {
    logBanner.textContent = "Scansione motori locali in corso...";
    chrome.runtime.sendMessage({ type: "SCAN_ENGINES" }, () => updateUI());
  });

  btnSaveHub.addEventListener("click", () => {
    const hub_url = hubUrlInput.value.trim().replace(/\/+$/, "");
    if (!hub_url) return;
    chrome.runtime.sendMessage({ type: "SET_HUB", hub_url }, () => {
      logBanner.textContent = `Hub aggiornato a ${hub_url}`;
      updateUI();
    });
  });

  btnSaveWallet.addEventListener("click", () => {
    const solana_address = solanaInput.value.trim();
    chrome.runtime.sendMessage({ type: "SET_WALLET", solana_address }, () => {
      logBanner.textContent = solana_address ? `Wallet salvato: ${solana_address.slice(0, 6)}...` : "Wallet rimosso";
      updateUI();
    });
  });

  btnTestInfer.addEventListener("click", () => {
    btnTestInfer.disabled = true;
    btnTestInfer.textContent = "⏳ Esecuzione test locale...";
    chrome.runtime.sendMessage({ type: "TEST_LOCAL_INFERENCE" }, (res) => {
      btnTestInfer.disabled = false;
      btnTestInfer.textContent = "🧪 Prova Inferenza Locale";
      if (res && res.ok) {
        logBanner.textContent = `✅ Test riuscito! Risposta da ${res.result.model} in ${res.result.duration_ms}ms`;
      } else {
        logBanner.textContent = `❌ Test fallito: ${res?.error || 'Errore sconosciuto'}`;
      }
      updateUI();
    });
  });

  // Polling periodico dell'interfaccia
  updateUI();
  setInterval(updateUI, 2000);
});
