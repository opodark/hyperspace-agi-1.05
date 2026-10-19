// SPDX-License-Identifier: Apache-2.0
// web-node/src/auth.js
// Gestione credenziali, persistenza in localStorage e verifica
// con l'endpoint /web/auth/verify del federation-gateway o control-plane.

export const STORAGE_AUTH_KEY = "hyperspace.webAuthKey";

export class AuthError extends Error {
  constructor(message, { status = 0, authenticated = false } = {}) {
    super(message);
    this.name = "AuthError";
    this.status = status;
    this.authenticated = authenticated;
  }
}

/** Legge la chiave memorizzata nel browser. */
export function getStoredAuthKey(storage = globalThis.localStorage) {
  try {
    return String(storage?.getItem?.(STORAGE_AUTH_KEY) || "").trim();
  } catch {
    return "";
  }
}

/** Salva la chiave di autenticazione nel browser. */
export function setStoredAuthKey(key, storage = globalThis.localStorage) {
  try {
    const val = String(key || "").trim();
    if (val) {
      storage?.setItem?.(STORAGE_AUTH_KEY, val);
    } else {
      storage?.removeItem?.(STORAGE_AUTH_KEY);
    }
  } catch {
    // I browser in modalità incognito restrittiva possono lanciare eccezioni
  }
}

/** Cancella la chiave memorizzata. */
export function clearStoredAuthKey(storage = globalThis.localStorage) {
  try {
    storage?.removeItem?.(STORAGE_AUTH_KEY);
  } catch {
    // No-op
  }
}

/**
 * Verifica una chiave con il backend /web/auth/verify (con fallback multi-endpoint).
 */
export async function verifyAuthKey({
  key,
  baseUrl,
  baseUrls,
  fetchImpl = globalThis.fetch,
  timeoutMs = 10000,
} = {}) {
  const token = String(key || "").trim();
  if (!token) {
    throw new AuthError("Chiave o token mancante", { status: 400 });
  }

  if (typeof fetchImpl !== "function") {
    throw new AuthError("fetch non disponibile");
  }

  const list = Array.isArray(baseUrls) && baseUrls.length ? baseUrls : (baseUrl ? [baseUrl] : []);
  const endpoints = list.map((u) => String(u || "").trim().replace(/\/+$/, "")).filter(Boolean);
  if (!endpoints.length) {
    throw new AuthError("Nessun endpoint di rete configurato per la verifica");
  }

  const fetchFn = fetchImpl.bind(globalThis);
  let lastError = null;

  for (const base of endpoints) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), Math.max(1000, Number(timeoutMs) || 10000));
    try {
      const response = await fetchFn(`${base}/web/auth/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ token }),
        signal: controller.signal,
      });

      const body = await response.json().catch(() => null);
      if (!response.ok) {
        const errorMsg = (body && body.error) || `Autenticazione fallita (HTTP ${response.status})`;
        throw new AuthError(errorMsg, { status: response.status, authenticated: false });
      }

      if (body && body.authenticated) {
        return {
          ok: true,
          authenticated: true,
          role: body.role || "member",
          label: body.label || "Utente Mesh Autorizzato",
          key: token,
        };
      }

      throw new AuthError((body && body.error) || "Chiave non riconosciuta", { status: 401 });
    } catch (error) {
      lastError = error;
      if (error instanceof AuthError && error.status > 0) {
        throw error;
      }
    } finally {
      clearTimeout(timer);
    }
  }

  throw new AuthError(
    `Impossibile verificare l'autenticazione: rete non raggiungibile (${lastError?.message || lastError})`
  );
}

/**
 * Gestore dell'autenticazione per l'interfaccia utente.
 */
export class AuthManager {
  constructor({
    baseUrls = [],
    baseUrl = "",
    storage = globalThis.localStorage,
    fetchImpl = globalThis.fetch,
    onStateChange = null,
  } = {}) {
    this.baseUrls = Array.isArray(baseUrls) && baseUrls.length ? baseUrls : (baseUrl ? [baseUrl] : []);
    this.storage = storage;
    this.fetchImpl = fetchImpl;
    this.onStateChange = typeof onStateChange === "function" ? onStateChange : null;

    this.state = {
      authenticated: false,
      role: "guest",
      label: "Ospite",
      key: "",
      verifying: false,
      lastError: null,
    };
  }

  _notify() {
    if (this.onStateChange) {
      this.onStateChange({ ...this.state });
    }
  }

  notify() {
    this._notify();
  }

  /**
   * Salva direttamente una chiave di autenticazione e la memorizza nello storage.
   */
  saveKey(key) {
    const trimmed = String(key || "").trim();
    this.state.key = trimmed;
    setStoredAuthKey(trimmed, this.storage);
    return trimmed;
  }

  getState() {
    return { ...this.state };
  }

  getKey() {
    return this.state.key;
  }

  /**
   * Inizializza leggendo l'eventuale chiave salvata e verificandola.
   */
  async init() {
    const saved = getStoredAuthKey(this.storage);
    if (!saved) {
      this.state = {
        authenticated: false,
        role: "guest",
        label: "Ospite",
        key: "",
        verifying: false,
        lastError: null,
      };
      this._notify();
      return this.getState();
    }

    return this.login(saved, { save: false });
  }

  /**
   * Esegue l'accesso con una chiave, verificandola col backend.
   */
  async login(key, { save = true } = {}) {
    const trimmed = String(key || "").trim();
    if (!trimmed) {
      throw new AuthError("Inserisci una chiave valida");
    }

    this.state.verifying = true;
    this.state.lastError = null;
    this._notify();

    try {
      const res = await verifyAuthKey({
        key: trimmed,
        baseUrls: this.baseUrls,
        fetchImpl: this.fetchImpl,
      });

      this.state = {
        authenticated: true,
        role: res.role,
        label: res.label,
        key: trimmed,
        verifying: false,
        lastError: null,
      };

      if (save) {
        setStoredAuthKey(trimmed, this.storage);
      }
      this._notify();
      return this.getState();
    } catch (error) {
      this.state = {
        authenticated: false,
        role: "guest",
        label: "Ospite",
        key: "",
        verifying: false,
        lastError: error.message,
      };
      clearStoredAuthKey(this.storage);
      this._notify();
      throw error;
    }
  }

  /**
   * Disconnette l'utente e rimuove la chiave.
   */
  logout() {
    clearStoredAuthKey(this.storage);
    this.state = {
      authenticated: false,
      bridgeActive: false,
      bridgeStatus: null,
      role: "guest",
      label: "Ospite",
      key: "",
      verifying: false,
      lastError: null,
    };
    this._notify();
    return this.getState();
  }

  /**
   * Verifica lo stato del plugin bridge Chrome o motore locale.
   */
  async checkBridge(options = {}) {
    try {
      const res = await detectBridgeStatus({ ...options, fetchImpl: this.fetchImpl });
      this.state.bridgeActive = Boolean(res && res.active);
      this.state.bridgeStatus = res;
      if (this.state.bridgeActive && !this.state.authenticated) {
        this.state.role = "node_operator";
        this.state.label = res.label || "Operatore GPU Locale";
      }
      this._notify();
      return res;
    } catch {
      this.state.bridgeActive = false;
      return { installed: false, active: false };
    }
  }

  /**
   * Restituisce true se l'utente ha accesso autorizzato (tramite chiave O tramite plugin bridge attivo).
   */
  isAuthorized() {
    return Boolean(this.state.authenticated || this.state.bridgeActive);
  }
}

/**
 * Rileva se il plugin 00MESH Chrome Bridge è attivo nel browser
 * o se è raggiungibile un motore di inferenza locale (Ollama / LM Studio).
 */
export async function detectBridgeStatus({ timeoutMs = 1200, fetchImpl = globalThis.fetch } = {}) {
  // 1. Controlla attributo DOM impostato dal content script dell'estensione
  if (typeof document !== "undefined" && document.documentElement?.dataset?.meshBridgeActive === "true") {
    return {
      installed: true,
      active: true,
      source: "content_script",
      label: "Plugin Chrome Bridge Attivo",
    };
  }

  // 2. Chiedi via postMessage al content script dell'estensione
  if (typeof window !== "undefined") {
    const postMessageResult = await new Promise((resolve) => {
      let done = false;
      const timer = setTimeout(() => {
        if (!done) {
          done = true;
          resolve(null);
        }
      }, Math.min(timeoutMs, 800));

      function handler(event) {
        if (event.data && event.data.type === "00MESH_BRIDGE_STATUS") {
          if (!done) {
            done = true;
            clearTimeout(timer);
            window.removeEventListener("message", handler);
            resolve(event.data);
          }
        }
      }

      window.addEventListener("message", handler);
      window.postMessage({ type: "00MESH_PING_BRIDGE" }, "*");
    });

    if (postMessageResult && postMessageResult.active) {
      return {
        installed: true,
        active: true,
        source: "extension_message",
        nodeId: postMessageResult.node_id,
        label: "Plugin Chrome Bridge Attivo",
      };
    }
  }

  // 3. Fallback: verifica se Ollama (11434) o LM Studio (1234) rispondono localmente
  if (typeof fetchImpl === "function") {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 600);
      const res = await fetchImpl("http://localhost:11434/api/tags", { signal: controller.signal });
      clearTimeout(timer);
      if (res.ok) {
        return { installed: true, active: true, source: "ollama_direct", label: "Ollama Locale Attivo" };
      }
    } catch {}

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 600);
      const res = await fetchImpl("http://127.0.0.1:1234/v1/models", { signal: controller.signal });
      clearTimeout(timer);
      if (res.ok) {
        return { installed: true, active: true, source: "lmstudio_direct", label: "LM Studio Locale Attivo" };
      }
    } catch {}
  }

  return { installed: false, active: false, label: "Plugin non rilevato" };
}
