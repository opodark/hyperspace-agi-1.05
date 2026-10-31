#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
/**
 * Anna sul telefono: dashboard dei sogni notturni + chat con la persona.
 *
 *   node anna.mjs               dashboard, poi la chat (persona-shell.mjs)
 *   node anna.mjs dash          solo dashboard
 *   node anna.mjs dash --watch 60
 *   node anna.mjs chat          solo chat
 *   node anna.mjs watchd        lo stesso watchdog in background 24/7 (lo avvia `00mesh start`)
 *   node anna.mjs watch         watchdog unico: telefono, mesh, telemetria, ricerca, sogni
 *                               (--every S, --once: una passata, esce 1 se ci sono allarmi)
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
      // /pocket/status e non /health: su una porta occupata da altro, /health risponde lo stesso
      const st = await get("/pocket/status", HUB);
      if (!st || typeof st.state !== "string") throw new Error("non è un Pocket Hub");
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

// ── watchdog unico: telefono + mesh + telemetria + sogni + ricerca ────────────
const num = (v, d = 0) => (typeof v === "number" && isFinite(v) ? v : d);
const age = (iso) => { const t = Date.parse(iso); return isNaN(t) ? null : Math.max(0, (Date.now() - t) / 1000); };
const dur = (sec) => (sec == null ? "?" : sec < 90 ? `${Math.round(sec)}s` : sec < 5400 ? `${Math.round(sec / 60)}m` : `${(sec / 3600).toFixed(1)}h`);
const short = (t, n) => { t = String(t || "").replace(/\s+/g, " "); return t.length > n ? t.slice(0, n - 1) + "…" : t; };
const FINAL = new Set(["done", "completed", "failed", "cancelled", "canceled", "rejected"]);

function nodeUrl() {
  let host = "127.0.0.1";
  try { host = fs.readFileSync(path.join(env.HOME || "", ".00mesh/run/node.bind"), "utf8").trim() || host; } catch { /* nodo non avviato */ }
  if (host === "0.0.0.0") host = "127.0.0.1";
  return `http://${host}:${env.NODE_PORT || 8084}`;
}

async function collect() {
  await pickCp();
  const ok = (p) => (p.status === "fulfilled" ? p.value : null);
  const local = await Promise.allSettled([get("/status", nodeUrl()), get("/pocket/status", HUB)]);
  const snap = { cp: CP, primary: PRIMARY, failover: FAILOVER, node: ok(local[0]), hub: ok(local[1]), at: Date.now() };
  if (FAILOVER) return snap;
  const r = await Promise.allSettled([
    get("/nodes/active"), get("/hb/status"), get("/metrics/summary"), get("/metrics/live"),
    get("/dreams/nightly/status"), get("/development-dreams/status"), get("/missions"),
  ]);
  [snap.nodes, snap.hb, snap.metrics, snap.live, snap.dream, snap.dev, snap.missions] = r.map(ok);
  if (!Array.isArray(snap.nodes)) snap.nodes = null; // risposta inattesa: meglio "assente" che un crash
  snap.cpDown = r.every((x) => x.status === "rejected");
  return snap;
}

// Regole in un posto solo: ogni allarme ha una chiave stabile (per notificare una volta sola).
function evaluate(s) {
  const al = [];
  const push = (key, msg) => al.push({ key, msg });
  const p = (s.node && s.node.power) || {};
  if (num(p.battery_pct, 100) < 20 && !p.ac_line) push("batt", `batteria ${Math.round(p.battery_pct)}% e non in carica`);
  if (num(p.temperature_c) >= 42) push("temp", `telefono caldo: ${p.temperature_c}°C`);
  if (s.failover) push("failover", "Mac non raggiungibile: il telefono fa da CP");
  else if (s.cpDown) push("cpdown", "né il Mac né il hub rispondono");
  if (env.ANNA_EXPECT_HUB && !s.hub) push("hubdown", "Pocket Hub non risponde");
  if (s.hub && s.hub.state === "active_failover") push("hubactive", "hub in failover attivo");
  if (s.hub && s.hub.outbox && s.hub.outbox.pending > 0 && s.hub.last_probe_ok) push("outbox", `${s.hub.outbox.pending} voci non ancora riconsegnate a Hermes`);
  if (s.nodes) {
    // i nodi mobile sono "degradati" a gate chiuso, per progetto: lo dice già la riga del gate
    const deg = s.nodes.filter((n) => n.degraded && n.tier !== "mobile");
    if (deg.length) push("degraded", `${deg.length} nodi degradati: ${deg.map((n) => n.alias || n.node_id.slice(0, 6)).join(", ")}`);
  }
  if (s.hb) {
    const a = age(s.hb.last_tick);
    if (!s.hb.running || (a != null && a > 300)) push("hb", `heartbeat del CP fermo da ${dur(a)}`);
  }
  if (s.dream && s.dream.salute && s.dream.salute.verdetto !== "ok") push("dream", `sogni: ${s.dream.salute.verdetto} (${s.dream.salute.dettaglio || ""})`);
  if (s.dev && s.dev.error) push("dev", "development dream in errore");
  return al;
}

function renderWatch(s, alerts) {
  const hh = new Date(s.at).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const verdict = alerts.length ? `${Y}${B}▲ ATTENZIONE ${alerts.length}${R}` : `${G}${B}● OK${R}`;
  const out = [`${T}${B}ANNA${R} ${D}watchdog · ${hh}${R}  ${verdict}`, ""];
  if (alerts.length) out.push(panel("allarmi", alerts.map((a) => `${Y}▲${R} ${a.msg}`), Y));

  // telefono
  const nd = s.node || {}, p = nd.power || {}, g = nd.mobile_gate || {}, h = s.hub;
  const tel = [];
  if (s.node) {
    tel.push(`batteria    ${Math.round(num(p.battery_pct))}% ${p.ac_line ? G + "in presa" : Y + "a batteria"}${R}${p.temperature_c != null ? " · " + p.temperature_c + "°C" : ""}`);
    tel.push(g.role === "failover"
      ? `ruolo       ${D}solo failover (non fa da worker)${R}`
      : `gate lavoro ${g.open ? G + "APERTO" : D + "chiuso"}${R}${g.window ? D + " " + g.window + R : ""}`);
    tel.push(`carico      ${num(nd.active_requests)} attive · ${num(nd.queued_requests)} in coda`);
  } else tel.push(`${D}nodo locale non risponde${R}`);
  if (h) tel.push(`hub         ${h.is_active_hub ? Y + "FAILOVER" : G + h.state}${R} ${D}· registro ${h.outbox.pending}${R}`);
  else tel.push(`${D}hub spento o non raggiungibile${R}`);
  out.push(panel("telefono", tel));

  if (s.failover || s.cpDown) {
    out.push(panel("mesh", [`${RED}Mac ${s.primary.replace(/^https?:\/\//, "")} giù${R}`], RED));
    return out.join("\n");
  }
  // mesh + telemetria
  const mesh = [];
  if (s.nodes) {
    const deg = s.nodes.filter((n) => n.degraded && n.tier !== "mobile").length;
    mesh.push(`nodi        ${G}${s.nodes.length} attivi${R}${deg ? Y + " · " + deg + " degradati" + R : ""}`);
  }
  if (s.hb) mesh.push(`heartbeat   ciclo ${s.hb.cycle} · ${dur(age(s.hb.last_tick))} fa`);
  if (s.metrics) {
    const m = s.metrics;
    mesh.push(`richieste   ${m.requests} · tok in ${Math.round(num(m.tokens_in) / 1000)}k / out ${Math.round(num(m.tokens_out) / 1000)}k`);
    const top = [...(m.models || [])].sort((a, b) => b.requests - a.requests)[0];
    if (top) mesh.push(`${D}top: ${short(top.model, 26)} ×${top.requests}${R}`);
  }
  if (s.live) mesh.push(`generazioni ${s.live.count ? Y + s.live.count + " in corso" : D + "nessuna in corso"}${R}`);
  out.push(panel("mesh · telemetria", mesh));

  // ricerca (Mission Control)
  const ms = (s.missions && s.missions.missions) || [];
  const run = ms.filter((m) => !FINAL.has(String(m.status).toLowerCase()));
  const by = (s.missions && s.missions.counts && s.missions.counts.by_status) || {};
  const ric = [];
  if (!s.missions) ric.push(`${D}Mission Control non risponde${R}`);
  else {
    if (!run.length) ric.push(`${D}nessuna missione in corso${R}`);
    for (const m of run.slice(0, 3)) {
      const t = m.tasks || [];
      const fatte = t.filter((x) => FINAL.has(String(x.status).toLowerCase())).length;
      ric.push(`${Y}▸${R} ${m.status} ${D}${t.length ? fatte + "/" + t.length + " task · " : ""}${dur(age(m.started_at || m.created_at))}${R}`);
      ric.push(`  ${short(m.objective, 46)}`);
    }
    const last = ms.find((m) => FINAL.has(String(m.status).toLowerCase()));
    ric.push(`${D}totale ${Object.entries(by).map(([k, v]) => k + " " + v).join(" · ")}${R}`);
    if (last && !run.length) ric.push(`${D}ultima: ${last.status} · ${short(last.error || last.objective, 38)}${R}`);
  }
  out.push(panel("ricerca · missioni", ric));

  // sogni
  const so = [];
  if (s.dream) {
    const d = s.dream, q = d.quota || {}, sa = d.salute || {};
    so.push(`notturni    ${sa.verdetto === "ok" ? G + "ok" : RED + (sa.verdetto || "?")}${R} ${D}${d.finestra_aperta ? "finestra APERTA" : "prossima " + hhmm(d.prossima_finestra)}${R}`);
    so.push(`quota       ${num(q.totale)}/${(d.config || {}).quota_giornaliera ?? "?"} ${D}(anna ${num(q.anna)} · aurora ${num(q.aurora)})${R}`);
  } else so.push(`${D}sogni notturni non disponibili${R}`);
  if (s.dev) so.push(`dev dream   ${s.dev.running ? G + "in corso" : D + "fermo"}${R} ${D}· ${s.dev.last_status || "—"} · da rivedere ${num(s.dev.pending_review)}${R}`);
  out.push(panel("sogni", so));
  return out.join("\n");
}

function notify(msg) {
  try { spawn("termux-notification", ["--id", "anna-watch", "--title", "Anna · watchdog", "--content", msg], { stdio: "ignore" }).on("error", () => {}); } catch { /* Termux:API assente */ }
}

async function watch(args) {
  const once = args.includes("--once");
  const ei = args.indexOf("--every");
  const every = Math.max(5, Number(ei >= 0 ? args[ei + 1] : env.ANNA_WATCH_S) || 30);
  const noNotify = args.includes("--no-notify") || once;
  let known = new Set(), first = true;
  for (;;) {
    let snap, alerts;
    try { snap = await collect(); alerts = evaluate(snap); }
    catch (e) { console.error(RED + e.message + R); alerts = []; snap = null; }
    if (snap) {
      if (!once) process.stdout.write("\x1b[2J\x1b[H");
      console.log(renderWatch(snap, alerts));
      if (!once) console.log(`${D}ogni ${every}s · Ctrl+C per uscire${R}`);
      // notifica solo gli allarmi NUOVI (e non al primo giro: li stai già guardando)
      const nuovi = alerts.filter((a) => !known.has(a.key));
      if (!noNotify && !first && nuovi.length) notify(nuovi.map((a) => a.msg).join(" · "));
      known = new Set(alerts.map((a) => a.key)); first = false;
    }
    if (once) exit(alerts.length ? 1 : 0);
    await new Promise((r) => setTimeout(r, every * 1000));
  }
}

// ── watchd: il watchdog 24/7 in background (lo avvia `00mesh start`) ────────────
// Niente schermo: ogni giro valuta le stesse regole di `watch`, notifica gli allarmi
// nuovi (anche al primo giro: nessuno sta guardando) e il rientro a "tutto ok",
// scrive lo stato in run/watch.json (schema 1: è l'interfaccia per la futura app
// companion) e aggiunge ogni apertura/chiusura di allarme a logs/watchdog.ndjson.
function summarize(s, alerts) {
  const p = (s.node && s.node.power) || {};
  const run = ((s.missions && s.missions.missions) || []).filter((m) => !FINAL.has(String(m.status).toLowerCase()));
  return {
    schema: 1,
    at: new Date(s.at).toISOString(),
    verdict: alerts.length ? "attenzione" : "ok",
    alerts,
    cp: { url: s.primary, reachable: !(s.failover || s.cpDown), failover: !!s.failover },
    phone: s.node ? { battery_pct: p.battery_pct ?? null, ac_line: !!p.ac_line, temperature_c: p.temperature_c ?? null } : null,
    hub: s.hub ? { state: s.hub.state, serving: !!s.hub.serving, outbox_pending: (s.hub.outbox || {}).pending ?? 0 } : null,
    nodes: s.nodes ? { active: s.nodes.length, degraded: s.nodes.filter((n) => n.degraded && n.tier !== "mobile").length } : null,
    missions_running: run.length,
    dream: s.dream && s.dream.salute ? s.dream.salute.verdetto : null,
  };
}

function writeAtomic(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = file + ".tmp";
  fs.writeFileSync(tmp, text);
  fs.renameSync(tmp, file);
}

async function watchd(args) {
  const ei = args.indexOf("--every");
  const every = Math.max(10, Number(ei >= 0 ? args[ei + 1] : env.ANNA_WATCH_S) || 30);
  const base = path.join(env.HOME || "", ".00mesh");
  const stateFile = path.join(base, "run/watch.json");
  const logFile = path.join(base, "logs/watchdog.ndjson");
  let known = new Map();
  const log = (obj) => { try { fs.mkdirSync(path.dirname(logFile), { recursive: true }); fs.appendFileSync(logFile, JSON.stringify({ ts: new Date().toISOString(), ...obj }) + "\n"); } catch { /* il log non deve fermare il watchdog */ } };
  log({ event: "start", every });
  for (;;) {
    try {
      const snap = await collect();
      const alerts = evaluate(snap);
      const now = new Map(alerts.map((a) => [a.key, a]));
      const nuovi = alerts.filter((a) => !known.has(a.key));
      const chiusi = [...known.values()].filter((a) => !now.has(a.key));
      for (const a of nuovi) log({ event: "alert", key: a.key, msg: a.msg });
      for (const a of chiusi) log({ event: "cleared", key: a.key });
      if (nuovi.length) notify(alerts.map((a) => a.msg).join(" · "));
      else if (chiusi.length && !alerts.length) notify("tutto rientrato");
      known = now;
      writeAtomic(stateFile, JSON.stringify(summarize(snap, alerts)) + "\n");
    } catch (e) {
      log({ event: "error", msg: String(e && e.message || e).slice(0, 200) });
    }
    await new Promise((r) => setTimeout(r, every * 1000));
  }
}

const [cmd = "all", ...rest] = argv.slice(2);
const wi = rest.indexOf("--watch");
if (cmd === "watchd") await watchd(rest);
else if (cmd === "watch") await watch(rest);
else if (cmd === "chat") { await pickCp(); chat(rest); }
else if (cmd === "dash" || cmd === "all") {
  const loop = async () => { try { await dashboard(); } catch (e) { console.error(RED + e.message + R); } };
  if (wi >= 0) {
    const sec = Number(rest[wi + 1]) || 60;
    for (;;) { process.stdout.write("\x1b[2J\x1b[H"); await loop(); await new Promise((r) => setTimeout(r, sec * 1000)); }
  } else {
    await loop();
    if (cmd === "all") { console.log(); chat(rest); }
  }
} else { console.error("uso: anna.mjs [dash [--watch S] | watchd | watch [--every S] [--once] [--no-notify] | chat | all]"); exit(2); }
