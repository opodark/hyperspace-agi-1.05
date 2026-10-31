#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// scripts/strixpersona.mjs
/**
 * Giro autonomo della persona su un bersaglio, con la stessa sintassi di Strix.
 *
 * Codice duplicato da `persona-shell.mjs` di proposito (vedi AGENT-LOG): qui non
 * c'è una REPL, c'è un obiettivo (`-t`) e un numero massimo di passi (`--max-turns`),
 * esattamente come `strix -t <target> -m quick --max-turns 20`. La persona esplora
 * il bersaglio con il tool shell, SOLO su conferma dell'operatore, poi scrive una
 * sintesi finale e un report su disco (come `strix_runs/`).
 *
 * Uso:
 *   node scripts/strixpersona.mjs -t /Users/opo/hyperspace-agi-1.04/infra-ui -m quick --max-turns 20
 *   node scripts/strixpersona.mjs -t ./app --instruction "Cerca secret in chiaro" -m deep --max-turns 40
 *   node scripts/strixpersona.mjs -t ./app --max-turns 10 --auto-deny   (per i test: non esegue nulla)
 *
 * Sicurezza: ogni comando gira sul Mac, fuori da qualsiasi sandbox. Default: ogni
 * comando chiede conferma (NO di default); `--yes` approva tutto fin dall'inizio
 * (comodo per un giro lungo, ma rimuove la rete di sicurezza); `--auto-deny` rifiuta
 * sempre (per i test).
 */

import { spawn } from "node:child_process";
import readline from "node:readline";
import fs from "node:fs";
import path from "node:path";
import { argv, env, exit, platform, stdin, stdout } from "node:process";

// ── shell multipiattaforma ────────────────────────────────────────────────
// bash su macOS/Linux; PowerShell su Windows (alias POSIX: ls, cat, cp, rm, ...).
// `--shell` forza una scelta diversa (es. "cmd", o "bash" con Git Bash/WSL).
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
        `Esegue un comando sul bersaglio indicato (${OS_LABEL}, ${kind}: ${sintassi}) ` +
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
const MODES = {
  quick: "Giro rapido: concentrati sui difetti più evidenti, poche verifiche mirate.",
  standard: "Giro standard: esplora con ordine, verifica le ipotesi principali prima di concludere.",
  deep: "Giro approfondito: esplora a fondo, verifica più ipotesi, non fermarti al primo indizio.",
};

// ── argomenti, stile Strix ────────────────────────────────────────────────────
function parseArgs(list) {
  const opts = {
    targets: [],
    mode: "quick",
    maxTurns: 20,
    instruction: "",
    model: env.PERSONA_CONSOLE_MODEL || "qwen3-8b-abliterated:latest",
    persona: env.PERSONA_CONSOLE_NAME || "persona",
    cpUrl: env.CP_URL || "http://localhost:8085",
    timeoutMs: 240_000,
    autoDeny: false,
    yes: false,
    shell: "", // "" = auto (bash su macOS/Linux, PowerShell su Windows)
  };
  for (let i = 0; i < list.length; i++) {
    const a = list[i];
    const next = () => list[++i];
    if (a === "-t" || a === "--target") opts.targets.push(next());
    else if (a === "-m" || a === "--mode") opts.mode = next();
    else if (a === "--max-turns") opts.maxTurns = Number(next());
    else if (a === "--instruction") opts.instruction = next();
    else if (a === "--instruction-file") opts.instruction = fs.readFileSync(next(), "utf8");
    else if (a === "--model") opts.model = next();
    else if (a === "--persona") opts.persona = next();
    else if (a === "--cp-url") opts.cpUrl = next();
    else if (a === "--timeout") opts.timeoutMs = Number(next()) * 1000;
    else if (a === "--auto-deny") opts.autoDeny = true;
    else if (a === "--yes") opts.yes = true;
    else if (a === "--shell") opts.shell = next(); // bash | powershell | cmd
    else if (a === "-h" || a === "--help") {
      console.log(
        "uso: strixpersona.mjs -t TARGET [-t TARGET ...] [-m quick|standard|deep] " +
          "[--max-turns N] [--instruction TESTO] [--model M] [--persona NOME] " +
          "[--shell bash|powershell|cmd] [--yes] [--auto-deny]",
      );
      exit(0);
    }
  }
  if (!opts.targets.length) {
    console.error("serve almeno un bersaglio: -t <percorso|URL>");
    exit(1);
  }
  if (!MODES[opts.mode]) {
    console.error(`modalità sconosciuta: ${opts.mode} (quick|standard|deep)`);
    exit(1);
  }
  if (!Number.isInteger(opts.maxTurns) || opts.maxTurns < 1) {
    console.error("--max-turns deve essere un intero >= 1");
    exit(1);
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
  console.log(`${BOLD}${MAGENTA}  ◢◤ STRIXPERSONA${RESET}  ${DIM}giro autonomo · shell su conferma${RESET}`);
  console.log(`${GREY}  bersaglio: ${opts.targets.join(", ")}${RESET}`);
  console.log(`${GREY}  modalità ${opts.mode} · max-turns ${opts.maxTurns} · modello ${opts.model}${RESET}`);
  console.log(`${GREY}  sistema ${OS_LABEL} · shell ${shellLabel(opts.shell)}${RESET}`);
  console.log(`${CYAN}${"━".repeat(w)}${RESET}`);
}

// ── input per la conferma: TTY interattivo oppure stdin a pipe ─────────────
const rl = readline.createInterface({ input: stdin, terminal: stdin.isTTY });
const lines = rl[Symbol.asyncIterator]();
async function ask(prompt) {
  if (stdin.isTTY) return new Promise((resolve) => rl.question(prompt, resolve));
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
      Authorization: "Bearer strixpersona",
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

// ── la shell locale, nella cwd del bersaglio se è una cartella esistente ────
function runShell(command, cwd, shellOverride) {
  return new Promise((resolve) => {
    const { cmd, args } = shellInvocation(command, shellOverride);
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"], cwd });
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
    console.log(`${GREEN}  [--yes / sessione: approva tutto] eseguo.${RESET}`);
    return true;
  }
  const raw = await ask(`${AMBER}  esegui? [e/N/a (tutto)] » ${RESET}`);
  const answer = (raw ?? "").trim().toLowerCase();
  if (answer === "a") { state.always = true; return true; }
  return ["e", "s", "y", "yes"].includes(answer);
}

function buildObjective(opts) {
  const targetLines = opts.targets.map((t) => `- ${t}`).join("\n");
  const istruzione = opts.instruction
    ? opts.instruction
    : "Analizza il bersaglio con il tool shell: cerca difetti di sicurezza, errori " +
      "evidenti o comportamenti sospetti. Guarda solo dentro il bersaglio indicato.";
  return (
    `Bersaglio(i):\n${targetLines}\n\n` +
    `Modalità: ${opts.mode}. ${MODES[opts.mode]}\n` +
    `Hai al massimo ${opts.maxTurns} passi di tool a disposizione: usali con criterio.\n\n` +
    `${istruzione}\n\n` +
    "Quando hai finito, o hai raccolto abbastanza per un verdetto, scrivi una sintesi " +
    "finale in italiano SENZA richiedere altri tool: cosa hai trovato, dove, e la gravità."
  );
}

function reportDir(opts) {
  const slug = opts.targets[0]
    .replace(/^https?:\/\//, "")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "target";
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const dir = path.join("strixpersona_runs", `${slug}-${stamp}`);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

// ── ciclo principale: non interattivo, a passi contati ──────────────────────
async function main() {
  const opts = parseArgs(argv.slice(2));
  const state = { always: opts.yes, autoDeny: opts.autoDeny };
  const firstTarget = opts.targets[0];
  const cwd = fs.existsSync(firstTarget) && fs.statSync(firstTarget).isDirectory() ? firstTarget : undefined;

  banner(opts);
  const messages = [{ role: "user", content: buildObjective(opts) }];
  const transcript = [`# strixpersona · ${opts.targets.join(", ")}`, "", `modalità: ${opts.mode} · max-turns: ${opts.maxTurns}`, ""];

  let turns = 0;
  let verdict = "";
  while (turns < opts.maxTurns) {
    turns++;
    if (stdin.isTTY) stdout.write(`${DIM}  … passo ${turns}/${opts.maxTurns}, la persona sta pensando${RESET}\r`);
    let resp;
    try {
      resp = await postChat(opts, messages);
    } catch (e) {
      panel("errore di connessione", String(e.message || e), RED);
      break;
    } finally {
      if (stdin.isTTY) stdout.write(" ".repeat(50) + "\r");
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
      verdict = (message.content || "").trim() || "[nessun testo]";
      panel(opts.persona, verdict, MAGENTA, `passo ${turns}/${opts.maxTurns}`);
      transcript.push("## Sintesi finale", "", verdict, "");
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
          const run = await runShell(command, cwd, opts.shell);
          result = run.text;
          panel(`output · exit ${run.code}`, run.text, run.code === 0 ? GREEN : AMBER, `passo ${turns}/${opts.maxTurns}`);
          transcript.push(`## Passo ${turns}`, "", `scopo: ${explanation || "–"}`, "", "```", `$ ${command}`, run.text, "```", "");
        } else {
          result = "[comando rifiutato dall'operatore]";
          console.log(`${GREY}  comando non eseguito.${RESET}`);
          transcript.push(`## Passo ${turns}`, "", `comando proposto (rifiutato): \`${command}\``, "");
        }
      }
      messages.push({ role: "tool", tool_call_id: call.id || "", content: result });
    }
  }
  if (!verdict && turns >= opts.maxTurns) {
    panel("stop", `max-turns (${opts.maxTurns}) raggiunto senza una sintesi finale.`, RED);
    transcript.push("## Stop", "", `max-turns (${opts.maxTurns}) raggiunto senza una sintesi finale.`, "");
  }

  const dir = reportDir(opts);
  fs.writeFileSync(path.join(dir, "report.md"), transcript.join("\n"), "utf8");
  console.log(`\n${GREY}Report: ${dir}/report.md${RESET}`);
  rl.close();
}

main().catch((e) => {
  console.error(`errore fatale: ${e.stack || e}`);
  exit(1);
});
