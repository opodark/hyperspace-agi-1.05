// SPDX-License-Identifier: Apache-2.0
// web-node/src/search.js
// Client di ricerca web privata tramite SearXNG / control-plane (/web/search).

export class SearchError extends Error {
  constructor(message, { status = 0 } = {}) {
    super(message);
    this.name = "SearchError";
    this.status = status;
  }
}

/** Esegue la ricerca web privata tramite l'endpoint protetto /web/search del gateway. */
export async function searchWeb({
  baseUrl,
  baseUrls,
  token,
  authKey,
  query,
  maxResults = 5,
  fetchImpl = globalThis.fetch,
  timeoutMs = 15000,
} = {}) {
  const cleanQuery = String(query || "").trim();
  if (!cleanQuery) throw new SearchError("Query di ricerca vuota");

  const list = Array.isArray(baseUrls) && baseUrls.length ? baseUrls : (baseUrl ? [baseUrl] : []);
  const rawEndpoints = list.map((u) => String(u || "").trim().replace(/\/+$/, "")).filter(Boolean);
  if (!rawEndpoints.length) throw new SearchError("Endpoint gateway mancante");

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

      const response = await fetchFn(`${base}/web/search`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query: cleanQuery, max_results: maxResults }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new SearchError(`HTTP ${response.status}`, { status: response.status });
      }

      const data = await response.json();
      if (!data || !data.ok) {
        throw new SearchError((data && data.error) || "Errore nella risposta di ricerca");
      }

      return {
        ok: true,
        query: cleanQuery,
        result: String(data.result || "").trim(),
      };
    } catch (err) {
      lastError = err;
      if (err instanceof SearchError && err.status > 0) throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  throw lastError || new SearchError("Impossibile contattare il servizio di ricerca");
}

/** Estrae le singole fonti (titolo, snippet, URL) dalla risposta testuale di SearXNG. */
export function parseSearchSources(resultText) {
  const text = String(resultText || "").trim();
  if (!text) return [];

  const sources = [];
  const blocks = text.split(/\n\n+/);

  for (const block of blocks) {
    const lines = block.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) continue;

    // Cerca URL nella riga
    let url = "";
    const urlLineIdx = lines.findIndex((l) => /^https?:\/\//i.test(l) || /Fonte:\s*(https?:\/\/[^\s]+)/i.test(l));
    if (urlLineIdx !== -1) {
      const m = lines[urlLineIdx].match(/(https?:\/\/[^\s]+)/i);
      if (m) url = m[1];
    }

    if (url) {
      let title = lines[0].replace(/^[-*•]\s*/, "").replace(/^\[Infobox\]\s*/, "");
      let snippet = lines.length > 2 ? lines[1] : "";
      sources.push({ title: title || url, snippet, url });
    }
  }

  return sources;
}

/** Inietta il blocco di contesto delle fonti web nel prompt prima di inviarlo al modello. */
export function formatSearchContext(searchResult) {
  if (!searchResult || !searchResult.result) return "";
  return (
    `FONTI VERIFICATE DALLA RICERCA WEB PRIVATA (SearXNG):\n` +
    `Query: "${searchResult.query}"\n\n` +
    `${searchResult.result}\n\n` +
    `Istruzione: rispondi integrando i fatti aggiornati dalle fonti sopra indicate e cita gli URL se pertinenti.\n`
  );
}
