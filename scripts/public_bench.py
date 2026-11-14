#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""public_bench.py — confronto verificabile da terzi: sistema HyperSpace vs modelli di frontiera.

Perche' esiste: i numeri di "qualita'" che nessuno puo' rieseguire non provano
niente. Qui ogni modello (HyperSpace e i modelli di frontiera) gira sullo STESSO
harness pubblico (EleutherAI lm-evaluation-harness) con gli STESSI benchmark
pubblici a punteggio automatico (nessun modello fa da giudice), e per ogni giro
si salvano manifesto (versioni, commit, impostazioni dichiarate, comando) e
risposte grezze. Chi vuole rifare la prova ha tutto.

Tre ruoli per i target (vedi benchmarks/public/targets.example.json):
  - "system":   il sistema HyperSpace col Control Plane (routing, review gate...)
  - "model":    un modello HyperSpace nudo (Ollama diretto), per separare modello e sistema
  - "frontier": modelli di frontiera via API

Il confronto non viene mai presentato come "vince il modello": un sistema con piu'
componenti non e' alla pari di un modello singolo, e la tabella lo etichetta.
Le previsioni stanno in benchmarks/public/predictions-*.json, scritte PRIMA di
misurare; il report le confronta con l'esito.

Uso:

    python3 scripts/public_bench.py plan   --targets benchmarks/public/targets.json
    python3 scripts/public_bench.py run    --targets ... --out benchmarks/public/runs/2026-11-03
    python3 scripts/public_bench.py run    --targets ... --limit 20      # fumo, NON un risultato
    python3 scripts/public_bench.py report --out benchmarks/public/runs/2026-11-03 \
        --predictions benchmarks/public/predictions-2026-11-03.json

Le chiavi API si leggono da variabili d'ambiente (campo `key_env` del target) e non
finiscono mai in manifesto, log o repo. lm_eval si installa a parte (venv dedicato):
`HS_LM_EVAL` ne indica il comando se non e' nel PATH. Solo libreria standard.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = "FILL_ME"

# Task lm_eval -> chiave della metrica principale. Le chiavi dipendono dalla
# versione dell'harness: se la chiave non c'e', si cerca la prima metrica
# plausibile e la nota lo dichiara (vedi extract_metric).
PRIMARY_METRICS: Dict[str, str] = {
    "ifeval": "prompt_level_strict_acc,none",
    "gsm8k": "exact_match,strict-match",
    "gpqa_diamond_cot_zeroshot": "exact_match,flexible-extract",
    "mmlu_pro": "exact_match,custom-extract",
    "bbh_cot_zeroshot": "exact_match,flexible-extract",
}
DEFAULT_TASKS = list(PRIMARY_METRICS)
# Stop dei task di lm_eval ("Question:" per gsm8k, ecc.) NON si applicano: sul percorso HyperSpace
# lo stop vale anche sui token di ragionamento e taglia la generazione prima della risposta
# (verificato 2026-11-03: con stop "Question:" Flint restituisce 78 caratteri di ragionamento,
# senza stop "#### 18"). Stesso valore per TUTTI i target, cosi' le condizioni restano pari.
COMMON_GEN_KWARGS = {"until": "</s>"}
CONFIG_NAME = "lm_eval_config.json"  # JSON e' YAML valido
DEFAULT_MARGIN = 3.0  # punti percentuali: entro questa soglia e' un pareggio


# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

def load_targets(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    targets = data["targets"] if isinstance(data, dict) else data
    names = [t["name"] for t in targets]
    if len(set(names)) != len(names):
        raise ValueError("nomi di target duplicati")
    for t in targets:
        if t.get("kind") not in ("system", "model", "frontier"):
            raise ValueError(f"{t.get('name')}: kind deve essere system|model|frontier")
    return targets


def placeholders_left(target: Dict[str, Any]) -> List[str]:
    """Campi ancora da compilare: meglio fermarsi che misurare il modello sbagliato."""
    out = []
    for key, val in target.items():
        if isinstance(val, str) and PLACEHOLDER in val:
            out.append(key)
        elif isinstance(val, dict):
            out.extend(f"{key}.{k}" for k, v in val.items() if isinstance(v, str) and PLACEHOLDER in v)
    return out


def lm_eval_cmd() -> List[str]:
    return shlex.split(os.environ.get("HS_LM_EVAL", "lm_eval"))


def build_command(target: Dict[str, Any], tasks: List[str], out_dir: Path,
                  limit: Optional[int] = None, seed: int = 1234) -> List[str]:
    """Comando lm_eval per un target. Deterministico: stesso input, stesso comando."""
    margs = dict(target.get("model_args", {}))
    gen = {"temperature": 0, **COMMON_GEN_KWARGS, **target.get("gen_kwargs", {})}
    gen_kwargs = ",".join(f"{k}={v}" for k, v in gen.items())
    headers = target.get("headers")
    cmd = lm_eval_cmd() + ["run", "--model", target["model_type"]]  # >= 0.4.10: sottocomando "run"
    if headers:
        # Gli header non passano da --model_args (stringa a virgole): vanno in un file di
        # configurazione, che resta accanto ai risultati e fa parte di cio' che si pubblica.
        cmd += ["--config", str(out_dir / target["name"] / CONFIG_NAME)]
    else:
        cmd += ["--model_args", ",".join(f"{k}={v}" for k, v in margs.items())]
    cmd += [
        "--tasks", ",".join(tasks),
        "--apply_chat_template",
        "--gen_kwargs", gen_kwargs,
        "--seed", str(seed),
        "--output_path", str(out_dir / target["name"]),
        "--log_samples",
    ]
    if limit:
        cmd += ["--limit", str(limit)]
    return cmd


def write_config(target: Dict[str, Any], out_dir: Path) -> Optional[Path]:
    """Scrive la configurazione con gli header (se il target ne ha). Niente segreti."""
    if not target.get("headers"):
        return None
    path = out_dir / target["name"] / CONFIG_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"model_args": {**target.get("model_args", {}),
                                               "header": target["headers"]}},
                               indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def target_env(target: Dict[str, Any], environ: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Ambiente del sottoprocesso: la chiave viene copiata solo qui, mai scritta altrove."""
    env = dict(environ if environ is not None else os.environ)
    key_env = target.get("key_env")
    if key_env:
        if not env.get(key_env):
            raise RuntimeError(f"{target['name']}: variabile {key_env} non impostata")
        env[target.get("key_target_env", "OPENAI_API_KEY")] = env[key_env]
    return env


def git_commit() -> str:
    try:
        return subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return "sconosciuto"


def lm_eval_version() -> str:
    """Versione di lm_eval dal pacchetto installato (lm_eval non ha --version)."""
    exe = lm_eval_cmd()[0]
    py = Path(exe).with_name("python3") if os.sep in exe else None
    try:
        r = subprocess.run([str(py) if py and py.exists() else sys.executable, "-c",
                            "import importlib.metadata as m;print(m.version('lm_eval'))"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or "sconosciuta"
    except Exception:
        return "sconosciuta"


def build_manifest(target: Dict[str, Any], tasks: List[str], cmd: List[str],
                   limit: Optional[int], seed: int) -> Dict[str, Any]:
    """Tutto quello che serve a rifare la prova. Nessun segreto: solo il NOME della variabile."""
    return {
        "target": target["name"],
        "kind": target["kind"],
        "components": target.get("components", ""),
        "declared_reasoning": target.get("declared_reasoning", "non dichiarato"),
        "model_type": target["model_type"],
        "model_args": target.get("model_args", {}),
        "gen_kwargs": {"temperature": 0, **COMMON_GEN_KWARGS, **target.get("gen_kwargs", {})},
        "key_env": target.get("key_env"),
        "headers": target.get("headers", {}),
        "tasks": tasks,
        "limit": limit,
        "full_run": not limit,
        "seed": seed,
        "command": cmd,
        "lm_eval_version": lm_eval_version(),
        "repo_commit": git_commit(),
        "python": sys.version.split()[0],
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# Esecuzione
# ---------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> int:
    targets = load_targets(Path(args.targets))
    tasks = args.tasks.split(",")
    out = Path(args.out)
    for t in targets:
        left = placeholders_left(t)
        print(f"# {t['name']} ({t['kind']})" + (f"  [DA COMPILARE: {', '.join(left)}]" if left else ""))
        print(" ".join(shlex.quote(c) for c in build_command(t, tasks, out, args.limit, args.seed)))
        print()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    targets = load_targets(Path(args.targets))
    wanted = set(args.only.split(",")) if args.only else None
    tasks = args.tasks.split(",")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    failures = 0
    for t in targets:
        if wanted and t["name"] not in wanted:
            continue
        left = placeholders_left(t)
        if left:
            print(f"[salto] {t['name']}: campi da compilare: {', '.join(left)}", file=sys.stderr)
            failures += 1
            continue
        cmd = build_command(t, tasks, out, args.limit, args.seed)
        manifest = build_manifest(t, tasks, cmd, args.limit, args.seed)
        (out / t["name"]).mkdir(parents=True, exist_ok=True)
        write_config(t, out)
        (out / t["name"] / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[run] {t['name']}: {' '.join(shlex.quote(c) for c in cmd)}")
        try:
            rc = subprocess.run(cmd, env=target_env(t)).returncode
        except (RuntimeError, FileNotFoundError) as exc:
            print(f"[errore] {t['name']}: {exc}", file=sys.stderr)
            rc = 1
        if rc != 0:
            failures += 1
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def extract_metric(results: Dict[str, Any], task: str) -> Optional[Tuple[float, str]]:
    """Punteggio in % e nome della metrica usata. Se la chiave attesa manca, ripiega
    sulla prima metrica di accuratezza e lo dichiara nel nome (niente numeri muti)."""
    block = results.get("results", {}).get(task)
    if not block:
        return None
    want = PRIMARY_METRICS.get(task)
    if want in block and isinstance(block[want], (int, float)):
        return block[want] * 100.0, want
    for key, val in block.items():
        if isinstance(val, (int, float)) and not key.startswith("alias") and "stderr" not in key \
                and ("acc" in key or "exact_match" in key):
            return val * 100.0, f"{key} (ripiego: attesa {want})"
    return None


def load_run(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    """name -> {manifest, scores{task:(pct, metric)}} leggendo i results_*.json piu' recenti."""
    runs: Dict[str, Dict[str, Any]] = {}
    for tdir in sorted(p for p in Path(run_dir).iterdir() if p.is_dir()):
        mpath = tdir / "manifest.json"
        if not mpath.exists():
            continue
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
        files = sorted(glob.glob(str(tdir / "**" / "results_*.json"), recursive=True))
        scores: Dict[str, Tuple[float, str]] = {}
        if files:
            res = json.loads(Path(files[-1]).read_text(encoding="utf-8"))
            for task in manifest["tasks"]:
                got = extract_metric(res, task)
                if got:
                    scores[task] = got
        runs[manifest["target"]] = {"manifest": manifest, "scores": scores}
    return runs


def verdict(system: float, other: float, margin: float = DEFAULT_MARGIN) -> str:
    """'vittoria' / 'pareggio' / 'sconfitta' del sistema rispetto all'altro, a margine fisso."""
    diff = system - other
    if diff > margin:
        return "vittoria"
    if diff < -margin:
        return "sconfitta"
    return "pareggio"


def render_report(runs: Dict[str, Dict[str, Any]], predictions: Optional[Dict[str, Any]] = None) -> str:
    names = list(runs)
    tasks: List[str] = []
    for r in runs.values():
        for t in r["manifest"]["tasks"]:
            if t not in tasks:
                tasks.append(t)
    margin = (predictions or {}).get("margin_points", DEFAULT_MARGIN)
    L: List[str] = ["# Confronto pubblico — sistema HyperSpace vs modelli di frontiera", ""]
    partial = [n for n, r in runs.items() if not r["manifest"].get("full_run")]
    if partial:
        L += [f"> **ATTENZIONE: giro parziale (--limit) per {', '.join(partial)}. NON e' un risultato.**", ""]
    L += ["| Target | Ruolo | Componenti | Ragionamento dichiarato |", "|---|---|---|---|"]
    for n in names:
        m = runs[n]["manifest"]
        L.append(f"| {n} | {m['kind']} | {m.get('components') or '-'} | {m['declared_reasoning']} |")
    L += ["", "## Punteggi (% — piu' alto e' meglio)", "", "| Benchmark | " + " | ".join(names) + " |",
          "|---|" + "---|" * len(names)]
    for t in tasks:
        cells = []
        for n in names:
            s = runs[n]["scores"].get(t)
            cells.append(f"{s[0]:.1f}" if s else "n/d")
        L.append(f"| {t} | " + " | ".join(cells) + " |")
    systems = [n for n in names if runs[n]["manifest"]["kind"] == "system"]
    frontier = [n for n in names if runs[n]["manifest"]["kind"] == "frontier"]
    if systems and frontier:
        sysn = systems[0]
        L += ["", f"## Esito del sistema ({sysn}) — margine di pareggio ±{margin:g} punti", "",
              "| Benchmark | " + " | ".join(f"vs {f}" for f in frontier) + " | previsto |",
              "|---|" + "---|" * (len(frontier) + 1)]
        score = {"utente": [0, 0], "claude": [0, 0]}
        for t in tasks:
            s = runs[sysn]["scores"].get(t)
            cells = []
            for f in frontier:
                o = runs[f]["scores"].get(t)
                cells.append(verdict(s[0], o[0], margin) if s and o else "n/d")
            preds = (predictions or {}).get("predictions", {}).get(t, {}) or {}
            for who in score:
                pred = preds.get(who)
                if pred in ("sconfitta", "pareggio", "vittoria", "non-sconfitta"):
                    for c in cells:
                        if c != "n/d":
                            score[who][1] += 1
                            score[who][0] += int(c == pred or (pred == "non-sconfitta" and c != "sconfitta"))
            L.append(f"| {t} | " + " | ".join(cells)
                     + f" | utente: {preds.get('utente', '-')} / claude: {preds.get('claude', '-')} |")
        for who, (h, n) in score.items():
            if n:
                L += ["", f"Previsioni di **{who}** centrate: {h}/{n}."]
    L += ["", "## Come rifare la prova", ""]
    for n in names:
        m = runs[n]["manifest"]
        L.append(f"- **{n}**: lm_eval `{m['lm_eval_version']}`, commit `{m['repo_commit'][:10]}`, "
                 f"seed {m['seed']}, temperatura {m['gen_kwargs'].get('temperature')}. "
                 f"Comando in `{n}/manifest.json`, risposte grezze in `{n}/`.")
    L += ["", "Il sistema HyperSpace include componenti che un modello singolo non ha; "
          "la riga `model` (se presente) separa il contributo del modello da quello del sistema.", ""]
    return "\n".join(L)


def cmd_report(args: argparse.Namespace) -> int:
    runs = load_run(Path(args.out))
    if not runs:
        print("nessun giro trovato in", args.out, file=sys.stderr)
        return 1
    preds = json.loads(Path(args.predictions).read_text(encoding="utf-8")) if args.predictions else None
    text = render_report(runs, preds)
    (Path(args.out) / "REPORT.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--targets", required=True)
        p.add_argument("--tasks", default=",".join(DEFAULT_TASKS))
        p.add_argument("--out", default="benchmarks/public/runs/latest")
        p.add_argument("--limit", type=int, default=None, help="solo per prove di fumo")
        p.add_argument("--seed", type=int, default=1234)
        if name == "run":
            p.add_argument("--only", default="", help="nomi target separati da virgola")
    r = sub.add_parser("report")
    r.add_argument("--out", required=True)
    r.add_argument("--predictions", default="")
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "run": cmd_run, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
