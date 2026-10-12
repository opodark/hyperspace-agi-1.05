// SPDX-License-Identifier: Apache-2.0
// web-node/src/sandbox.js
// Client per l'esecuzione di script Python nel container Docker sandbox isolato (/web/sandbox/run).

export class SandboxError extends Error {
  constructor(message, { status = 0 } = {}) {
    super(message);
    this.name = "SandboxError";
    this.status = status;
  }
}

/** Invia il codice Python per l'esecuzione usa-e-getta nella sandbox isolata. */
export async function runSandboxCode({
  baseUrl,
  baseUrls,
  token,
  authKey,
  code,
  timeout = 25,
  fetchImpl = globalThis.fetch,
  timeoutMs = 35000,
} = {}) {
  const cleanCode = String(code || "").trim();
  if (!cleanCode) throw new SandboxError("Nessun codice fornito per l'esecuzione");

  const list = Array.isArray(baseUrls) && baseUrls.length ? baseUrls : (baseUrl ? [baseUrl] : []);
  const rawEndpoints = list.map((u) => String(u || "").trim().replace(/\/+$/, "")).filter(Boolean);
  if (!rawEndpoints.length) throw new SandboxError("Endpoint gateway mancante");

  const authToken = String(token || authKey || "").trim();
  const fetchFn = fetchImpl.bind(globalThis);
  let lastError = null;

  for (const base of rawEndpoints) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const headers = { "Content-Type": "application/json" };
      if (authToken) {
        headers["Authorization"] = `Bearer ${authToken}`;
        headers["X-Hyperspace-Network-Token"] = authToken;
      }

      const response = await fetchFn(`${base}/web/sandbox/run`, {
        method: "POST",
        headers,
        body: JSON.stringify({ code: cleanCode, timeout }),
        signal: controller.signal,
      });

      if (!response.ok) {
        let msg = `HTTP ${response.status}`;
        try {
          const errBody = await response.json();
          if (errBody && errBody.error) msg = errBody.error;
        } catch {}
        throw new SandboxError(msg, { status: response.status });
      }

      const data = await response.json();
      if (!data) throw new SandboxError("Risposta vuota dalla sandbox");

      return {
        ok: Boolean(data.ok),
        stdout: String(data.stdout || ""),
        stderr: String(data.stderr || ""),
        output: String(data.output || ""),
        exitCode: Number(data.exit_code ?? (data.ok ? 0 : 1)),
        durationMs: Number(data.duration_ms || 0),
        backend: String(data.backend || "docker"),
      };
    } catch (err) {
      lastError = err;
      if (err instanceof SandboxError && err.status > 0) throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  throw lastError || new SandboxError("Impossibile contattare il servizio sandbox");
}
