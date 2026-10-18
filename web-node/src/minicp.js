// SPDX-License-Identifier: Apache-2.0
// web-node/src/minicp.js
// Mini Control Plane autonomo per il browser (Web-Node).
// Esegue tool client-side a zero dipendenze:
//  - Calcolatrice ed elaborazione matematica sicura (calc)
//  - Riassunto estrattivo intelligente (summarize)
//  - Ricerca web privata via SearXNG (web_search)
//  - Ingestion documenti e PDF AnyDoc (anydoc_extract)
//  - Esecuzione sandbox Docker (code_sandbox)
//  - Diagnostica di rete mesh e bridge GPU (system_status)
//  - Dispatcher di comandi slash (/help, /search, /calc, /run, /summary, /status)

import { searchWeb, parseSearchSources, formatSearchContext } from "./search.js";
import { runSandboxCode } from "./sandbox.js";
import { extractTextFromFile, isSupportedFile, formatDocumentsContext } from "./documents.js";
import { generateImage } from "./image.js";
import { buildPdfBinary, downloadPdfFile } from "./pdf.js";

const STOPWORDS = new Set(("a ad al alla allo ai agli alle anche come con cui da dal dalla " +
  "dei del della di e ed gli ha hai hanno i il in io la le lo ma mi ne nei nel nella no non " +
  "o per piu' piu se si sono su sul sulla tra un una uno vi voi che chi cosa dove quando " +
  "the a an and or of to in is are was were for on with at by from this that it as be").split(" "));

/**
 * Valutatore matematico sicuro client-side senza eval().
 * Supporta: +, -, *, /, %, ^, (), sqrt, cbrt, sin, cos, tan, abs, round, floor, ceil, log, log10, log2, exp, min, max, pi, e.
 */
export function evaluateMath(rawExpr) {
  let expr = String(rawExpr || "").trim();
  if (!expr) throw new Error("Espressione matematica vuota");

  // Sostituzione costanti e simboli
  expr = expr
    .replace(/\bpi\b/gi, String(Math.PI))
    .replace(/\be\b/gi, String(Math.E))
    .replace(/×/g, "*")
    .replace(/÷/g, "/")
    .replace(/(\d+),(\d+)/g, "$1.$2"); // virgola decimale numerica (es. 10,5 -> 10.5)

  // Gestione percentuali: es. "20% * 50" -> "(20/100) * 50"
  expr = expr.replace(/(\d+(?:\.\d+)?)\s*%/g, "($1/100)");

  // Sostituzione elevamento a potenza: a ^ b -> Math.pow(a, b)
  while (expr.includes("^")) {
    const powRegex = /([a-zA-Z0-9_.]+|\([^\(\)]+\))\s*\^\s*([a-zA-Z0-9_.]+|\([^\(\)]+\))/;
    const match = expr.match(powRegex);
    if (!match) break;
    expr = expr.replace(powRegex, `Math.pow(${match[1]},${match[2]})`);
  }

  // Whitelist di token matematici consentiti
  const allowedMathFuncs = [
    "Math.pow", "Math.sqrt", "Math.cbrt", "Math.sin", "Math.cos", "Math.tan",
    "Math.abs", "Math.round", "Math.floor", "Math.ceil", "Math.log", "Math.log10",
    "Math.log2", "Math.exp", "Math.min", "Math.max"
  ];

  // Traduci chiamate come sqrt(...) in Math.sqrt(...)
  for (const fn of ["sqrt", "cbrt", "sin", "cos", "tan", "abs", "round", "floor", "ceil", "log", "log10", "log2", "exp", "min", "max"]) {
    const r = new RegExp(`\\b${fn}\\(`, "g");
    expr = expr.replace(r, `Math.${fn}(`);
  }

  // Verifica sicurezza: ammessi SOLO numeri, operatori e funzioni Math consentite
  const sanitized = expr.replace(/\s+/g, "");
  const stripped = sanitized
    .replace(/Math\.(pow|sqrt|cbrt|sin|cos|tan|abs|round|floor|ceil|log|log10|log2|exp|min|max)/g, "")
    .replace(/[0-9.]+/g, "")
    .replace(/[+\-*/%(),]/g, "");

  if (stripped.length > 0) {
    throw new Error(`Caratteri o funzioni non permesse nell'espressione: "${stripped}"`);
  }

  // Calcolo controllato
  try {
    const fn = new Function(`"use strict"; return (${expr});`);
    const val = fn();
    if (typeof val !== "number" || !Number.isFinite(val)) {
      throw new Error("Risultato non numerico o infinito (divisione per zero)");
    }
    // Arrotonda decimali fluttuanti (es. 0.1 + 0.2 = 0.3)
    return Math.abs(val) < 1e-12 ? 0 : Number(val.toPrecision(12)) / 1;
  } catch (err) {
    throw new Error(`Errore di calcolo: ${err.message}`);
  }
}

/**
 * Riassunto estrattivo client-side basato sulla frequenza dei termini (zero LLM / offline).
 */
export function summarizeText(text, maxSentences = 3) {
  const clean = String(text || "").trim();
  if (!clean) return "";

  const sentences = clean.split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
  const limit = Math.max(1, Math.min(10, Number(maxSentences) || 3));
  if (sentences.length <= limit) return clean;

  const frequency = new Map();
  for (const word of clean.toLowerCase().match(/[a-z0-9àèéìòù']+/g) || []) {
    if (word.length < 3 || STOPWORDS.has(word)) continue;
    frequency.set(word, (frequency.get(word) || 0) + 1);
  }

  const scored = sentences.map((sentence, index) => {
    const words = sentence.toLowerCase().match(/[a-z0-9àèéìòù']+/g) || [];
    const score = words.reduce((sum, w) => sum + (frequency.get(w) || 0), 0) / Math.max(1, words.length);
    return { sentence, index, score };
  });

  const best = scored.slice().sort((a, b) => b.score - a.score).slice(0, limit);
  best.sort((a, b) => a.index - b.index);
  return best.map((s) => s.sentence).join(" ");
}

/**
 * Classe MiniControlPlane: orchestra strumenti client-side, gestisce slash commands
 * e garantisce autonomia del nodo anche in caso di parziale disconnessione dal CP centrale.
 */
export class MiniControlPlane {
  constructor({
    gatewayUrl = "https://mesh.zerozerocomputer.it",
    token = "",
    activeBridge = null,
    fetchImpl = globalThis.fetch,
  } = {}) {
    this.gatewayUrl = String(gatewayUrl || "").replace(/\/+$/, "");
    this.token = String(token || "");
    this.activeBridge = activeBridge;
    this.fetch = (fetchImpl || globalThis.fetch).bind(globalThis);
    this.tools = new Map();

    this._registerDefaultTools();
  }

  _registerDefaultTools() {
    // 1. Tool Matematico & Calcoli
    this.registerTool("calc", {
      name: "calc",
      description: "Calcolatrice matematica client-side ad alta precisione con funzioni avanzate",
      parameters: { expression: "string" },
      execute: async ({ expression }) => {
        const result = evaluateMath(expression);
        return { ok: true, expression, result };
      },
    });

    // 2. Tool Riassunto Estrattivo
    this.registerTool("summarize", {
      name: "summarize",
      description: "Riassunto estrattivo istantaneo client-side senza chiamate al modello",
      parameters: { text: "string", maxSentences: "number" },
      execute: async ({ text, maxSentences = 3 }) => {
        const summary = summarizeText(text, maxSentences);
        return { ok: true, summary, originalLength: text.length, summaryLength: summary.length };
      },
    });

    // 3. Tool Ricerca Web SearXNG
    this.registerTool("web_search", {
      name: "web_search",
      description: "Ricerca web privata in tempo reale tramite SearXNG / gateway",
      parameters: { query: "string", maxResults: "number" },
      execute: async ({ query, maxResults = 5 }) => {
        const res = await searchWeb({
          baseUrls: [this.gatewayUrl],
          token: this.token,
          query,
          maxResults,
          fetchImpl: this.fetch,
        });
        const sources = parseSearchSources(res.result);
        return { ok: true, query, result: res.result, sources };
      },
    });

    // 4. Tool Docker Sandbox
    this.registerTool("code_sandbox", {
      name: "code_sandbox",
      description: "Esecuzione isolata di script Python in container Docker Sandbox",
      parameters: { code: "string", timeout: "number" },
      execute: async ({ code, timeout = 25 }) => {
        return await runSandboxCode({
          baseUrls: [this.gatewayUrl],
          token: this.token,
          code,
          timeout,
          fetchImpl: this.fetch,
        });
      },
    });

    // 5. Tool Diagnostica Mesh & Sistema
    this.registerTool("system_status", {
      name: "system_status",
      description: "Verifica stato della rete 00MESH, latenza gateway e bridge GPU locale",
      parameters: {},
      execute: async () => {
        let gatewayOnline = false;
        let latencyMs = 0;
        const start = Date.now();
        try {
          const res = await this.fetch(`${this.gatewayUrl}/v1/models`, {
            headers: this.token ? { Authorization: `Bearer ${this.token}` } : {},
            signal: AbortSignal.timeout(3500),
          });
          gatewayOnline = res.ok;
          latencyMs = Date.now() - start;
        } catch {
          gatewayOnline = false;
          latencyMs = -1;
        }

        return {
          ok: true,
          gateway: {
            url: this.gatewayUrl,
            online: gatewayOnline,
            latencyMs,
          },
          bridge: this.activeBridge || { active: false, label: "Nessun plugin GPU rilevato" },
          clientTools: Array.from(this.tools.keys()),
          platform: typeof navigator !== "undefined" ? navigator.userAgent : "Node.js",
          hasWebGpu: typeof navigator !== "undefined" && Boolean(navigator.gpu),
        };
      },
    });

    // 6. Tool Generazione Immagini (ComfyUI Mesh + Flux Fallback)
    this.registerTool("image_generate", {
      name: "image_generate",
      description: "Generazione immagini fotorealistiche con nodi ComfyUI GPU o motore neurale Flux",
      parameters: { prompt: "string", width: "number", height: "number" },
      execute: async ({ prompt, width = 768, height = 768 }) => {
        return await generateImage({
          prompt,
          width,
          height,
          gatewayUrl: this.gatewayUrl,
          token: this.token,
          fetchImpl: this.fetch,
        });
      },
    });

    // 7. Tool Generazione & Esportazione PDF
    this.registerTool("pdf_generate", {
      name: "pdf_generate",
      description: "Genera ed esporta documenti PDF (%PDF-1.4) vettoriali A4 pronti al download",
      parameters: { title: "string", content: "string", filename: "string" },
      execute: async ({ title = "Documento 00MESH", content = "", filename = "" }) => {
        return downloadPdfFile({ title, content, filename });
      },
    });
  }

  registerTool(name, def) {
    this.tools.set(name, def);
  }

  getTool(name) {
    return this.tools.get(name);
  }

  listTools() {
    return Array.from(this.tools.values()).map(t => ({
      name: t.name,
      description: t.description,
      parameters: t.parameters,
    }));
  }

  async executeTool(name, params = {}) {
    const tool = this.tools.get(name);
    if (!tool) throw new Error(`Tool non registrato: ${name}`);
    return await tool.execute(params);
  }

  /**
   * Elabora i comandi slash (/help, /search, /calc, /run, /summary, /status)
   * Restituisce { handled: boolean, content: string, meta?: any }
   */
  async handleSlashCommand(rawInput) {
    const trimmed = String(rawInput || "").trim();
    if (!trimmed.startsWith("/")) return { handled: false };

    const parts = trimmed.slice(1).split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const rest = trimmed.slice(cmd.length + 1).trim();

    switch (cmd) {
      case "help":
      case "tools":
      case "comandi": {
        const toolsList = this.listTools();
        const rows = toolsList.map(t => `| \`/${t.name}\` | ${t.description} |`).join("\n");
        const content = `### ⚡ Mini-CP Autonomo · Strumenti & Comandi Slash

Il tuo client Web-Node include un **Mini Control Plane autonomo** che può eseguire strumenti direttamente nel browser o tramite gateway mesh.

| Comando | Descrizione |
| :--- | :--- |
${rows}
| \`/clear\` | Pulisce la cronologia dei messaggi della chat attiva |
| \`/help\` | Mostra questo sommario degli strumenti |

**Esempi d'uso rapidi:**
- \`/image astronauta cyberpunk sul pianeta Marte, neon ciano, 8k\`
- \`/pdf Relazione 00MESH | # Titolo\\nContenuto del documento A4 da esportare...\`
- \`/calc (120 * 4.5) + sqrt(144) - 15%\`
- \`/search novità cluster GPU neuromorfiche\`
- \`/summary Incolla un testo lungo qui per riassumerlo all'istante\`
- \`/status\` per verificare la connessione mesh, latenza e bridge GPU.
`;
        return { handled: true, content };
      }

      case "calc": {
        if (!rest) {
          return { handled: true, content: "⚠️ **Uso:** `/calc <espressione>` (es. `/calc 12 * 8.5 + sqrt(100)`)" };
        }
        try {
          const res = await this.executeTool("calc", { expression: rest });
          const content = `### 🧮 Calcolo Mini-CP
**Espressione:** \`${res.expression}\`  
**Risultato:** **\`${res.result}\`**`;
          return { handled: true, content, meta: res };
        } catch (err) {
          return { handled: true, content: `❌ **Errore calcolo:** ${err.message}` };
        }
      }

      case "search": {
        if (!rest) {
          return { handled: true, content: "⚠️ **Uso:** `/search <query>` (es. `/search modelli linguistici sovrani`)" };
        }
        try {
          const res = await this.executeTool("web_search", { query: rest, maxResults: 5 });
          const sources = res.sources || [];
          let content = `### 🌐 Ricerca Web Privata (SearXNG)\n**Query:** "${res.query}"\n\n`;
          if (sources.length > 0) {
            content += sources.map((s, i) => `${i + 1}. [**${s.title}**](${s.url})\n   ${s.snippet}`).join("\n\n");
          } else if (res.result) {
            content += res.result;
          } else {
            content += "_Nessun risultato rilevante trovato._";
          }
          return { handled: true, content, meta: res };
        } catch (err) {
          return { handled: true, content: `❌ **Errore ricerca:** ${err.message}` };
        }
      }

      case "summary":
      case "riassumi": {
        if (!rest) {
          return { handled: true, content: "⚠️ **Uso:** `/summary <testo da riassumere>`" };
        }
        try {
          const res = await this.executeTool("summarize", { text: rest, maxSentences: 3 });
          const content = `### 📄 Riassunto Estrattivo Client-Side\n${res.summary}\n\n*Ridotto da ${res.originalLength} a ${res.summaryLength} caratteri (3 frasi chiave, 0 token spesi).*`;
          return { handled: true, content, meta: res };
        } catch (err) {
          return { handled: true, content: `❌ **Errore riassunto:** ${err.message}` };
        }
      }

      case "status":
      case "ping": {
        try {
          const res = await this.executeTool("system_status");
          const gw = res.gateway;
          const statusIcon = gw.online ? "🟢 Online" : "🔴 Offline";
          const latency = gw.latencyMs >= 0 ? `${gw.latencyMs}ms` : "N/D";
          const bridgeStatus = res.bridge && res.bridge.active ? `🟢 ${res.bridge.label}` : "⚪ Inattivo / Nessuna GPU connessa";

          const content = `### 📡 Stato Diagnostico Mini-CP & 00MESH

| Componente | Stato | Dettagli |
| :--- | :--- | :--- |
| **Gateway Mesh** | ${statusIcon} | \`${gw.url}\` (Latenza: \`${latency}\`) |
| **GPU Bridge Locale** | ${bridgeStatus} | Rilevamento Chrome Bridge / Ollama |
| **WebGPU Browser** | ${res.hasWebGpu ? "🟢 Supportata" : "⚪ Non rilevata"} | Accelerazione neurale client-side |
| **Tool Client-Side** | 🟢 ${res.clientTools.length} registrati | \`${res.clientTools.join(", ")}\` |
`;
          return { handled: true, content, meta: res };
        } catch (err) {
          return { handled: true, content: `❌ **Errore diagnostica:** ${err.message}` };
        }
      }

      case "image":
      case "img":
      case "draw":
      case "imagine": {
        if (!rest) {
          return { handled: true, content: "⚠️ **Uso:** `/image <descrizione>` (es. `/image astronauta cyberpunk sul pianeta Marte, neon ciano, 8k`)" };
        }
        try {
          const res = await this.executeTool("image_generate", { prompt: rest });
          const badge = res.provider === "comfyui-mesh" ? "ComfyUI GPU 00MESH" : "Motore Neurale Flux";
          const durationSec = Math.round((res.durationMs || 0) / 100) / 10;
          const content = `### 🎨 Immagine Generata · ${badge} (${durationSec}s)\n**Prompt:** *"${res.prompt}"*\n\n![${res.prompt}](${res.imageUrl})\n\n[📥 Scarica Immagine HD (${res.width}x${res.height})](${res.imageUrl})`;
          return { handled: true, content, meta: res };
        } catch (err) {
          return { handled: true, content: `❌ **Errore generazione immagine:** ${err.message}` };
        }
      }

      case "pdf":
      case "export-pdf": {
        if (!rest) {
          return { handled: true, content: "⚠️ **Uso:** `/pdf [titolo] | [contenuto]` oppure `/pdf <testo>`" };
        }
        try {
          let title = "Documento 00MESH";
          let textContent = rest;
          if (rest.includes("|")) {
            const parts = rest.split("|");
            title = parts[0].trim();
            textContent = parts.slice(1).join("|").trim();
          }
          const res = await this.executeTool("pdf_generate", { title, content: textContent });
          const content = `### 📄 Documento PDF Compilato & Scaricato\n**Titolo:** ${title}\n**Pagine:** ${res.totalPages} A4 (Vettoriale %PDF-1.4)\n**File:** \`${res.filename}\` avviato in download!`;
          return { handled: true, content, meta: res };
        } catch (err) {
          return { handled: true, content: `❌ **Errore generazione PDF:** ${err.message}` };
        }
      }

      case "clear": {
        return { handled: true, isAction: "clear", content: "Conversazione pulita con successo." };
      }

      default:
        return {
          handled: true,
          content: `⚠️ Comando \`/${cmd}\` non riconosciuto. Digita \`/help\` per la lista degli strumenti disponibili.`,
        };
    }
  }
}
