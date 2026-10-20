// SPDX-License-Identifier: Apache-2.0
/**
 * 00MESH Local Bridge — Content Script
 * Segnala alla web app (zerozerocomputer.it / onrender / localhost) lo stato
 * del bridge locale per sbloccare l'accesso alla Chat Estesa Sovrana.
 */

(function () {
  function checkAndNotify() {
    try {
      chrome.runtime.sendMessage({ type: "GET_BRIDGE_STATUS" }, (response) => {
        if (chrome.runtime.lastError || !response) {
          return;
        }

        const isSharing = Boolean(response.sharing_enabled);
        const hasComfy = Boolean(response.engines?.comfyui?.online);
        const hasEngines = Boolean(response.engines?.ollama?.online || response.engines?.lmstudio?.online || hasComfy);
        const active = isSharing && hasEngines;

        const detail = {
          installed: true,
          active,
          sharing_enabled: isSharing,
          comfyui_active: hasComfy,
          node_id: response.node_id,
          engines: response.engines || {},
          stats: response.stats || {}
        };

        // Marca l'elemento radice del documento
        document.documentElement.dataset.meshBridgeInstalled = "true";
        document.documentElement.dataset.meshBridgeActive = active ? "true" : "false";
        document.documentElement.dataset.meshComfyuiActive = hasComfy ? "true" : "false";

        // Emette evento DOM per listener locali
        window.dispatchEvent(new CustomEvent("00mesh:bridge-status", { detail }));

        // Notifica via postMessage (compatibile con iframe / worker)
        window.postMessage({ type: "00MESH_BRIDGE_STATUS", ...detail }, "*");
      });
    } catch (err) {
      // Ignora errori di contesto estensione invalidato
    }
  }

  // Esegui al caricamento e periodicamente ogni 4 secondi
  checkAndNotify();
  setInterval(checkAndNotify, 4000);

  // Rispondi alle richieste esplicite inviate dalla pagina web
  window.addEventListener("message", (event) => {
    if (event.data && event.data.type === "00MESH_PING_BRIDGE") {
      checkAndNotify();
    }
  });
})();
