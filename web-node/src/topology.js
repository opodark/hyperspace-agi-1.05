// SPDX-License-Identifier: Apache-2.0
// web-node/src/topology.js
// Fetch e sanitizzazione della topologia pubblica del mesh (/web/topology).

export async function fetchTopology({ baseUrls = [], fetchImpl = globalThis.fetch } = {}) {
  const urls = Array.isArray(baseUrls) ? baseUrls : [baseUrls].filter(Boolean);
  let lastError = null;
  for (const raw of urls) {
    const base = String(raw || "").replace(/\/+$/, "");
    if (!base) continue;
    try {
      const res = await fetchImpl(`${base}/web/topology`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data && data.ok) {
        return sanitizeTopologyData(data);
      }
      throw new Error(data?.error || "Dati topologia non validi");
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("Nessun gateway disponibile per la topologia");
}

export function sanitizeTopologyData(raw) {
  if (!raw || typeof raw !== "object") {
    return {
      ok: false,
      machines: [],
      models: [],
      hub: { label: "Control Plane", online: false, models: [], model_count: 0 },
      browsers: { count: 0, capabilities: [] },
      totals: { machines: 0, models: 0, browsers: 0 },
    };
  }
  const machines = Array.isArray(raw.machines)
    ? raw.machines.map((m) => ({
        label: String(m.label || "nodo").slice(0, 48),
        tier: String(m.tier || "leaf").slice(0, 16),
        models: Array.isArray(m.models) ? m.models.map(String) : [],
        model_count: Number(m.model_count || (Array.isArray(m.models) ? m.models.length : 0)),
        load: Math.max(0, Math.min(1, Number(m.load) || 0)),
        active_requests: Math.max(0, Number(m.active_requests) || 0),
        vram_gb: m.vram_gb ? Number(m.vram_gb) : null,
        last_seen_s: m.last_seen_s != null ? Number(m.last_seen_s) : null,
      }))
    : [];

  const models = Array.isArray(raw.models) ? raw.models.map(String) : [];
  const browsers = {
    count: Math.max(0, Number(raw.browsers?.count) || 0),
    capabilities: Array.isArray(raw.browsers?.capabilities) ? raw.browsers.capabilities.map(String) : [],
  };
  const hub = {
    label: String(raw.hub?.label || "Control Plane"),
    online: Boolean(raw.hub?.online),
    models: Array.isArray(raw.hub?.models) ? raw.hub.models.map(String) : [],
    model_count: Number(raw.hub?.model_count || 0),
  };
  const totals = {
    machines: Number(raw.totals?.machines ?? machines.length),
    models: Number(raw.totals?.models ?? models.length),
    browsers: Number(raw.totals?.browsers ?? browsers.count),
  };

  return {
    ok: true,
    generated_at: raw.generated_at || new Date().toISOString(),
    machines,
    models,
    hub,
    browsers,
    totals,
  };
}
