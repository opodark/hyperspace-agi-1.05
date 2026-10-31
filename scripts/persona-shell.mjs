#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// scripts/persona-shell.mjs
/**
 * Terminale della persona con tool shell locale, eseguito solo su conferma.
 *
 * Versione Node (nessuna dipendenza, Node >= 18) della console persona: parla con
 * `/v1/chat/completions` del control-plane. La superficie `terminal` attiva la persona
 * con tono asciutto; l'header `X-Hyperspace-Tools: off` fa passare SOLO il tool shell
 * di questo client (niente web_search/mesh/connettori del CP).
 *
 * Uso:
 *   node scripts/persona-shell.mjs
 *   node scripts/persona-shell.mjs --model qwen3-8b-abliterated:latest --persona Anna
 *   echo "che python ho? usa la shell" | node scripts/persona-shell.mjs --auto-deny
 *
 * Sicurezza: ogni comando gira sul Mac, fuori dal sandbox. Di default chiede conferma
 * (default: NO). `--auto-deny` rifiuta tutto. Alla conferma, `a` approva il resto della
 * sessione: comodo, ma rischioso.
 */

import { spawn } from "node:child_process";
import readline from "node:readline";
import { argv, env, exit, platform, stdin, stdout } from "node:process";

// ── shell multipiattaforma ────────────────────────────────────────────────
// bash su macOS/Linux; PowerShell su Windows (ha alias comodi: ls, cat, pwd,
// cp, mv, rm — i comandi "da POSIX" che il modello tende a scrivere funzionano
// quasi sempre anche lì). `--shell` forza una scelta diversa (es. "cmd" o
// "bash" se l'operatore ha Git Bash/WSL su Windows).
function shellInvocation(command, override) {
  const kind = override || (platform === "win32" ? "powershell" : "bash");
  if (kind === "powershell") {
    return { cmd: "powershell.exe", args: ["-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command] };
  }
  if (kind === "cmd") {
    return { cmd: "cmd.exe", args: ["/d", "/s", "/c", command] };
  }
  return { cmd: "bash", args: ["-lc", command] };
}
function shellLabel(override) {
  return override || (platform === "win32" ? "powershell" : "bash");
}

const OS_LABEL = { win32: "Windows", darwin: "macOS", linux: "Linux" }[platform] || platform;

function buildShellTool(shellOverride) {
  const kind = shellLabel(shellOverride);
  const sintassi = kind === "bash" ? "sintassi bash/POSIX (ls, cat, grep, ...)"
    : kind === "powershell" ? "sintassi PowerShell (ha alias POSIX: ls, cat, cp, rm, ... ma non tutto è uguale a bash)"
    : "sintassi cmd.exe (dir, type, copy, ...)";
  return {
    type: "function",
    function: {
      name: "shell",
      description:
        `Esegue un comando sul computer locale dell'operatore (${OS_LABEL}, ${kind}: ${sintassi}) ` +
        "e restituisce stdout, stderr e codice di uscita. Ogni comando richiede la " +
        "conferma esplicita dell'operatore prima di partire.",
      parameters: {
        type: "object",
        properties: {
          command: { type: "string", description: `Il comando da eseguire (${kind}).` },
          explanation: { type: "string", description: "Una riga: a cosa serve questo comando." },
        },
        required: ["command"],
      },
    },
  };
}

const MAX_OUTPUT = 4000; // caratteri di output restituiti al modello
const CMD_TIMEOUT_MS = 120_000;
const MAX_TOOL_HOPS = 8; // tool call consecutive prima di fermarsi

// ── argomenti ────────────────────────────────────────────────────────────────
function parseArgs(list) {
  const opts = {
    cpUrl: env.CP_URL || "http://localhost:8085",
    model: env.PERSONA_CONSOLE_MODEL || "qwen3-8b-abliterated:latest",
    persona: env.PERSONA_CONSOLE_NAME || "persona",
    timeoutMs: 240_000,
    autoDeny: false,
    shell: "", // "" = auto (bash su macOS/Linux, PowerShell su Windows)
  };
  for (let i = 0; i < list.length; i++) {
    const a = list[i];
    const next = () => list[++i];
    if (a === "--cp-url") opts.cpUrl = next();
    else if (a === "--model") opts.model = next();
    else if (a === "--persona") opts.persona = next();
    else if (a === "--timeout") opts.timeoutMs = Number(next()) * 1000;
    else if (a === "--auto-deny") opts.autoDeny = true;
    else if (a === "--shell") opts.shell = next(); // bash | powershell | cmd
    else if (a === "-h" || a === "--help") {
      console.log("uso: persona-shell.mjs [--model M] [--persona NOME] [--cp-url URL] [--shell bash|powershell|cmd] [--auto-deny]");
      exit(0);
    }
  }
  return opts;
}

// ── UI: colori e pannelli (ANSI, nessuna dipendenza) ─────────────────────────
const COLOR = stdout.isTTY && env.NO_COLOR === undefined;
const c = (code) => (COLOR ? code : "");
const RESET = c("\x1b[0m"), DIM = c("\x1b[2m"), BOLD = c("\x1b[1m");
const CYAN = c("\x1b[36m"), MAGENTA = c("\x1b[35m"), AMBER = c("\x1b[33m");
const GREEN = c("\x1b[32m"), RED = c("\x1b[31m"), GREY = c("\x1b[90m");

const width = () => Math.max(44, Math.min(stdout.columns || 100, 100));

function wrap(text, inner) {
  const out = [];
  for (const raw of String(text).split("\n")) {
    if (raw.length <= inner) { out.push(raw); continue; }
    let line = "";
    for (const word of raw.split(/(\s+)/)) {
      if ((line + word).length > inner && line) { out.push(line); line = word.trimStart(); }
      else line += word;
    }
    out.push(line);
  }
  return out.length ? out : [""];
}

function panel(title, body, accent = CYAN, foot = "") {
  const w = width();
  const inner = w - 4;
  const head = `${accent}╭─ ${BOLD}${title}${RESET}${accent} ` + "─".repeat(Math.max(0, inner - title.length - 1)) + `╮${RESET}`;
  const rows = wrap(body, inner).map(
    (seg) => `${accent}│${RESET} ${seg}${" ".repeat(inner - seg.length)} ${accent}│${RESET}`,
  );
  const lines = [head, ...rows];
  if (foot) lines.push(`${accent}│ ${DIM}${foot}${RESET}${" ".repeat(inner - foot.length)} ${accent}│${RESET}`);
  lines.push(`${accent}╰${"─".repeat(w - 2)}╯${RESET}`);
  console.log(lines.join("\n"));
}

function banner(opts) {
  const w = width();
  console.log(`${CYAN}${"━".repeat(w)}${RESET}`);
  console.log(`${BOLD}${MAGENTA}  ◢◤ PERSONA SHELL${RESET}  ${DIM}shell su conferma · stile Strix${RESET}`);
  console.log(`${GREY}  modello ${opts.model} · CP ${opts.cpUrl}${RESET}`);
  console.log(`${GREY}  sistema ${OS_LABEL} · shell ${shellLabel(opts.shell)} · scrivi e invio · 'exit' esce${RESET}`);
  console.log(`${CYAN}${"━".repeat(w)}${RESET}`);
}

// ── input: TTY interattivo oppure stdin pipe ─────────────────────────────────
const rl = readline.createInterface({ input: stdin, terminal: stdin.isTTY });
const lines = rl[Symbol.asyncIterator]();

async function ask(prompt) {
  if (stdin.isTTY) {
    return new Promise((resolve) => rl.question(prompt, resolve));
  }
  stdout.write(prompt);
  const { value, done } = await lines.next();
  return done ? null : value;
}

// ── rete: la chiamata al control-plane ───────────────────────────────────────
async function postChat(opts, messages) {
  const res = await fetch(opts.cpUrl.replace(/\/$/, "") + "/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer persona-shell",
      "X-Hyperspace-Tools": "off", // solo il nostro tool, niente builtin del CP
      "X-Hyperspace-Surface": "terminal", // superficie che attiva la persona
    },
    body: JSON.stringify({ model: opts.model, messages, tools: [buildShellTool(opts.shell)], stream: false }),
    signal: AbortSignal.timeout(opts.timeoutMs),
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${text.slice(0, 400)}`);
  return JSON.parse(text);
}

// ── la shell locale ──────────────────────────────────────────────────────────
function runShell(command, shellOverride) {
  return new Promise((resolve) => {
    const { cmd, args } = shellInvocation(command, shellOverride);
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "", err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    const timer = setTimeout(() => child.kill("SIGTERM"), CMD_TIMEOUT_MS);
    child.on("error", (e) => {
      clearTimeout(timer);
      resolve({ text: `[errore di esecuzione: ${e.message}]`, code: null });
    });
    child.on("close", (code, signal) => {
      clearTimeout(timer);
      if (signal) return resolve({ text: `[terminato dopo ${CMD_TIMEOUT_MS / 1000}s]`, code: null });
      const parts = [`exit_code: ${code}`];
      if (out.trim()) parts.push("stdout:\n" + out.trim());
      if (err.trim()) parts.push("stderr:\n" + err.trim());
      let text = parts.join("\n");
      if (text.length > MAX_OUTPUT) text = text.slice(0, MAX_OUTPUT) + "\n…[troncato]";
      resolve({ text, code });
    });
  });
}

async function confirm(command, explanation, state) {
  const body = (explanation ? `scopo: ${explanation}\n` : "") + `$ ${command}`;
  panel("SHELL · conferma richiesta", body, AMBER);
  if (state.autoDeny) {
    console.log(`${RED}  [--auto-deny] rifiutato.${RESET}`);
    return false;
  }
  if (state.always) {
    console.log(`${GREEN}  [sessione: approva tutto] eseguo.${RESET}`);
    return true;
  }
  const answer = ((await ask(`${AMBER}  esegui? [e/N/a (tutto)] » ${RESET}`)) ?? "").trim().toLowerCase();
  if (answer === "a") { state.always = true; return true; }
  return ["e", "s", "y", "yes"].includes(answer);
}

// ── ciclo principale ─────────────────────────────────────────────────────────
async function main() {
  const opts = parseArgs(argv.slice(2));
  const state = { always: false, autoDeny: opts.autoDeny };
  const messages = [];
  banner(opts);

  for (;;) {
    const line = await ask(`\n${BOLD}${CYAN}› ${RESET}`);
    if (line === null) break; // EOF
    const text = line.trim();
    if (!text) continue;
    if (["exit", "quit", ":q"].includes(text.toLowerCase())) break;

    messages.push({ role: "user", content: text });

    let answered = false;
    for (let hop = 0; hop < MAX_TOOL_HOPS && !answered; hop++) {
      if (stdin.isTTY) stdout.write(`${DIM}  … la persona sta pensando${RESET}\r`);
      let resp;
      try {
        resp = await postChat(opts, messages);
      } catch (e) {
        panel("errore di connessione", String(e.message || e), RED);
        break;
      } finally {
        if (stdin.isTTY) stdout.write(" ".repeat(40) + "\r");
      }

      const message = resp?.choices?.[0]?.message;
      if (!message) { panel("risposta inattesa", JSON.stringify(resp).slice(0, 400), RED); break; }

      const toolCalls = message.tool_calls || [];
      messages.push({
        role: "assistant",
        content: message.content || "",
        ...(toolCalls.length ? { tool_calls: toolCalls } : {}),
      });

      if (!toolCalls.length) {
        panel(opts.persona, (message.content || "").trim() || "[nessun testo]", MAGENTA);
        answered = true;
        break;
      }

      for (const call of toolCalls) {
        let result;
        if (call.function?.name !== "shell") {
          result = `[tool sconosciuto: ${call.function?.name}]`;
        } else {
          let args = {};
          try { args = JSON.parse(call.function.arguments || "{}"); } catch { /* lascia vuoto */ }
          const command = String(args.command || "").trim();
          const explanation = String(args.explanation || "").trim();
          if (!command) {
            result = "[nessun comando fornito]";
          } else if (await confirm(command, explanation, state)) {
            const run = await runShell(command, opts.shell);
            result = run.text;
            panel(`output · exit ${run.code}`, run.text, run.code === 0 ? GREEN : AMBER);
          } else {
            result = "[comando rifiutato dall'operatore]";
            console.log(`${GREY}  comando non eseguito.${RESET}`);
          }
        }
        messages.push({ role: "tool", tool_call_id: call.id || "", content: result });
      }
    }
    if (!answered) panel("stop", "troppe tool call consecutive: mi fermo.", RED);
  }
  console.log(`\n${GREY}Chiuso.${RESET}`);
  rl.close();
}

main().catch((e) => {
  console.error(`errore fatale: ${e.stack || e}`);
  exit(1);
});
