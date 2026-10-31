#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
/**
 * Anna sul telefono: dashboard dei sogni notturni + chat con la persona.
 *
 *   node anna.mjs               dashboard, poi la chat (persona-shell.mjs)
 *   node anna.mjs dash          solo dashboard
 *   node anna.mjs dash --watch 60
 *   node anna.mjs chat          solo chat
 *
 * La dashboard è SOLA LETTURA: legge /dreams/nightly/status e
 * /development-dreams/status dal control-plane (CP_URL, default il Mac sulla
 * tailnet). La chat usa persona-shell.mjs: i comandi shell girano SUL TELEFONO
 * e chiedono conferma uno per uno.
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { argv, env, exit, stdout } from "node:process";
import { fileURLToPath } from "node:url";

const PRIMARY = (env.CP_URL || "http://100.81.234.102:8085").replace(/\/$/, "");
// Il hub ascolta sull'IP Tailscale del telefono: 00mesh lo scrive in run/hub.bind.
function hubUrl() {
  if (env.POCKET_HUB_URL) return env.POCKET_HUB_URL;
  let host = "127.0.0.1";
  try {
    host = fs.readFileSync(path.join(env.HOME || "", ".00mesh/run/hub.bind"), "utf8").trim() || host;
  } catch { /* nessun hub avviato: resta il locale */ }
  if (host === "0.0.0.0") host = "127.0.0.1";
  return `http://${host}:${env.POCKET_HUB_PORT || 8086}`;
}
const HUB = hubUrl().replace(/\/$/, "");
let CP = PRIMARY;
let FAILOVER = false;
const COLOR = stdout.isTTY && env.NO_COLOR === undefined;
const c = (code) => (COLOR ? code : "");
const R = c("\x1b[0m"), B = c("\x1b[1m"), D = c("\x1b[38;2;71;85;105m");
const T = c("\x1b[38;2;87;230;217m"), G = c("\x1b[38;2;16;185;129m");
const RED = c("\x1b[38;2;244;63;94m"), Y = c("\x1b[38;2;251;191;36m");
const strip = (s) => s.replace(/\x1b\[[0-9;]*m/g, "");
const W = () => Math.max(40, Math.min(stdout.columns || 60, 80));

function panel(title, lines, accent = T) {
  const w = W(), inner = w - 4;
  const fit = (s) => {
    const v = strip(s);
    return v.length > inner ? s.slice(0, inner - 1) + "…" : s + " ".repeat(inner - v.length);
  };
  const out = [`${accent}╭─ ${B}${title}${R}${accent} ${"─".repeat(Math.max(0, inner - title.length - 1))}╮${R}`];
  for (const l of lines) out.push(`${accent}│${R} ${fit(l)} ${accent}│${R}`);
  out.push(`${accent}╰${"─".repeat(w - 2)}╯${R}`);
  return out.join("\n");
}

async function get(p, base = CP) {
  const res = await fetch(base + p, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
const hhmm = (iso) => {
  const d = new Date(iso);
  return isNaN(d) ? "?" : d.toLocaleString("it-IT", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

// Il Mac risponde? Altrimenti, se c'è, si parla con il Pocket Hub del telefono.
async function pickCp() {
  try {
    await fetch(PRIMARY + "/health", { signal: AbortSignal.timeout(3000) }).then((r) => { if (!r.ok) throw new Error(); });
    CP = PRIMARY; FAILOVER = false;
  } catch {
    try {
      await get("/health", HUB);
      CP = HUB; FAILOVER = true;
    } catch { CP = PRIMARY; FAILOVER = false; }
  }
}

async function failoverDashboard() {
  console.log(`${T}${B}ANNA${R} ${D}· failover sul telefono${R}\n`);
  let st = null;
  try { st = await get("/pocket/status", HUB); } catch { /* il pannello sotto lo dice */ }
  const lines = st ? [
    `${Y}${B}Mac non raggiungibile${R}  ${D}${PRIMARY.replace(/^https?:\/\//, "")}${R}`,
    `hub         ${st.is_active_hub ? G + "ATTIVO" : Y + st.state}${R} ${D}(mancati ${st.consecutive_misses}/${st.failover_threshold_misses})${R}`,
    `registro    ${st.outbox.pending ? Y + st.outbox.pending : G + "0"}${R} voci per Hermes al ritorno`,
    `${D}modello piccolo, senza la memoria completa${R}`,
  ] : [`${RED}né il Mac né il Pocket Hub rispondono${R}`];
  console.log(panel("failover", lines, st ? Y : RED));
}

async function dashboard() {
  await pickCp();
  if (FAILOVER) return failoverDashboard();
  const [n, dev] = await Promise.allSettled([get("/dreams/nightly/status"), get("/development-dreams/status")]);
  console.log(`${T}${B}ANNA${R} ${D}· supervisore sogni · ${CP.replace(/^https?:\/\//, "")}${R}\n`);

  if (n.status === "fulfilled") {
    const d = n.value, q = d.quota || {}, s = d.salute || {};
    const verdetto = s.verdetto === "ok" ? `${G}ok${R}` : `${RED}${s.verdetto || "?"}${R}`;
    const [a, b] = (d.config || {}).finestra || ["?", "?"];
    const lines = [
      `salute      ${verdetto}  ${D}${s.dettaglio || ""}${R}`,
      `finestra    ${d.finestra_aperta ? G + "APERTA" : Y + "chiusa"}${R} ${D}${a}:00–${b}:00 · prossima ${hhmm(d.prossima_finestra)}${R}`,
      `quota oggi  anna ${q.anna ?? 0} · aurora ${q.aurora ?? 0} · tot ${q.totale ?? 0}${D}/${(d.config || {}).quota_giornaliera ?? "?"}${R}`,
    ];
    const last = (d.sogni || [])[0];
    if (last) lines.push(`ultimo      ${hhmm(last.ts || d.ultimo_sogno)} ${last.autore || ""} · ${last.fase || ""}`);
    const salto = (d.salti || [])[0];
    if (salto && salto.motivo) lines.push(`${D}ultimo salto: ${salto.motivo}${R}`);
    console.log(panel("sogni notturni", lines));
  } else {
    console.log(panel("sogni notturni", [`${RED}CP non raggiungibile${R} ${D}(${n.reason.message})${R}`], RED));
  }

  if (dev.status === "fulfilled") {
    const d = dev.value;
    const stato = d.running ? `${G}in corso` : `${D}fermo`;
    console.log(panel("development dream", [
      `stato       ${stato}${R}  ${D}ultimo: ${d.last_status || "—"} (${d.last_date || "—"})${R}`,
      `da rivedere ${d.pending_review ? Y + d.pending_review : "0"}${R}`,
      d.error ? `${RED}${d.error}${R}` : `${D}sandbox: ${(d.sandbox || {}).backend || "?"}${R}`,
    ]));
  } else {
    console.log(panel("development dream", [`${RED}non disponibile${R}`], RED));
  }
}

function chat(extra) {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const home = env.HOME || "";
  const cand = [
    env.PERSONA_SHELL,
    path.join(here, "persona-shell.mjs"),
    path.join(home, ".00mesh/persona-shell.mjs"),
    path.join(home, ".00mesh/app/scripts/persona-shell.mjs"),
  ].filter(Boolean);
  const shell = cand.find((p) => fs.existsSync(p));
  if (!shell) {
    console.error(`${RED}persona-shell.mjs non trovato${R} (cercato in: ${cand.join(", ")})`);
    exit(1);
  }
  const child = spawn(process.execPath, [shell, "--persona", "Anna", "--cp-url", CP, "--shell", "bash", ...extra], { stdio: "inherit" });
  child.on("exit", (code) => exit(code ?? 0));
}

const [cmd = "all", ...rest] = argv.slice(2);
const wi = rest.indexOf("--watch");
if (cmd === "chat") { await pickCp(); chat(rest); }
else if (cmd === "dash" || cmd === "all") {
  const loop = async () => { try { await dashboard(); } catch (e) { console.error(RED + e.message + R); } };
  if (wi >= 0) {
    const sec = Number(rest[wi + 1]) || 60;
    for (;;) { process.stdout.write("\x1b[2J\x1b[H"); await loop(); await new Promise((r) => setTimeout(r, sec * 1000)); }
  } else {
    await loop();
    if (cmd === "all") { console.log(); chat(rest); }
  }
} else { console.error("uso: anna.mjs [dash [--watch S] | chat | all]"); exit(2); }
