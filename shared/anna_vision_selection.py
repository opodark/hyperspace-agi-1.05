# SPDX-License-Identifier: Apache-2.0
"""Resumable visual review of Anna images using the local Ollama vision model."""

import base64
import filecmp
import io
import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

from PIL import Image, ImageOps


EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
REVIEW_VERSION = 4
PROMPT = (
    "Sei un revisore severo di immagini generate. Considera la PERSONA PRINCIPALE, "
    "non le figure decorative sullo sfondo. Cerca difetti visivi anche se la scena "
    "e artistica: arti extra o tagliati, dita fuse o in numero errato, piedi "
    "emergenti da punti impossibili, mani e piedi sproporzionati, corpo deformato, "
    "volto gravemente alterato. Valuta soltanto le parti VISIBILI; se una parte e "
    "fuori inquadratura non e un difetto. Se anche una sola parte visibile e "
    "sospetta, non promuoverla. Se non c'e una persona, metti da_rivedere. "
    "Rispondi SOLO JSON con campi esito (ok o da_rivedere), anomalie "
    "(lista di dettagli concreti), confidenza (numero 0-1)."
)
PROMPT_ADVERSARIAL = (
    "Fai un controllo AVVERSARIALE dell'anatomia della figura umana principale. "
    "Il tuo compito e trovare il piu piccolo difetto nelle mani, dita, piedi, "
    "braccia, gambe, nella connessione degli arti e nel corpo. Non dare per "
    "scontato che sia sana. Guarda ogni mano e ogni piede visibile separatamente. "
    "Ignora le parti fuori inquadratura. Se almeno un punto e dubbio o deformato, "
    "esito da_rivedere. Rispondi SOLO JSON con campi esito (ok o da_rivedere), "
    "anomalie (lista di dettagli concreti), confidenza (numero 0-1)."
)
PROMPT_SECOND_PASS = (
    "Secondo controllo rapido di una immagine gia messa in dubbio. Guarda la persona "
    "principale e SOLO le parti del corpo visibili. Segnala arti o dita extra, mani "
    "fuse, connessioni impossibili, volto o corpo chiaramente deformati. Una mano "
    "fuori inquadratura non e un difetto. Promuovi con esito ok solo se l'anatomia "
    "visibile e coerente e sei sicuro almeno all'85%; se non puoi verificarla, "
    "lascia da_rivedere. Rispondi SOLO JSON: esito (ok o da_rivedere), anomalie "
    "(lista di dettagli concreti), confidenza (numero 0-1)."
)


def parse_verdict_details(text):
    match = re.search(r"\{[^{}]*\}", str(text), re.DOTALL)
    if not match:
        raise ValueError("Il modello non ha restituito JSON")
    data = json.loads(match.group(0))
    verdict = data.get("esito")
    if verdict not in ("ok", "da_rivedere"):
        raise ValueError("Esito del modello non valido")
    anomalies = data.get("anomalie")
    confidence = data.get("confidenza")
    if not isinstance(anomalies, list) or not isinstance(confidence, (int, float)):
        raise ValueError("Valutazione visiva incompleta")
    if verdict == "ok" and (anomalies or confidence < 0.85):
        verdict = "da_rivedere"
    reason = "; ".join(str(item) for item in anomalies) or (
        "anatomia visibile coerente" if verdict == "ok" else "valutazione incerta")
    return verdict, reason[:240], anomalies, float(confidence)


def parse_verdict(text):
    verdict, reason, _, _ = parse_verdict_details(text)
    return verdict, reason


class AnnaVisionSelection:
    def __init__(self, root, state_file, model, ask_vision):
        self.root = Path(root)
        self.state_file = Path(state_file)
        self.model = model
        self.ask_vision = ask_vision
        self.lock = threading.Lock()
        self.thread = None
        self._pause_requested = False
        self._active_state = None

    def _files(self):
        return sorted(p for p in self.root.iterdir()
                      if p.is_file() and not p.is_symlink() and p.suffix.lower() in EXTENSIONS)

    def _load(self):
        if not self.state_file.is_file():
            return None
        return json.loads(self.state_file.read_text(encoding="utf-8"))

    def _save(self, state):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_file.with_name(self.state_file.name + ".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp, self.state_file)

    def status(self):
        with self.lock:
            state = self._load()
            if not state:
                return {"status": "not_started"}
            if state.get("status") == "running" and not (self.thread and self.thread.is_alive()):
                state["status"] = "interrupted"
            if state.get("status") == "pausing" and not (self.thread and self.thread.is_alive()):
                state["status"] = "paused"
            result = {key: state.get(key) for key in
                      ("job_id", "status", "total", "processed", "selected", "to_review",
                       "errors", "last_file", "model", "started_at", "finished_at")}
            result["folders"] = [str(self.root / "Anna_selezionate"),
                                 str(self.root / "Anna_da_rivedere")]
            return result

    def start(self, *, force=False, limit=None):
        with self.lock:
            if self.thread and self.thread.is_alive():
                if self._pause_requested:
                    self._pause_requested = False
                    self._active_state["status"] = "running"
                    self._save(self._active_state)
                return self.status_unlocked()
            files = self._files()
            if limit is not None:
                files = files[:limit]
            previous = self._load()
            names = [p.name for p in files]
            if (not force and previous and previous.get("version") == REVIEW_VERSION
                    and previous.get("model") == self.model
                    and previous.get("status") == "completed"
                    and previous.get("filenames") == names):
                return self.status_unlocked()
            if (not force and previous and previous.get("version") == REVIEW_VERSION
                    and previous.get("model") == self.model
                    and previous.get("status") in
                    ("running", "interrupted", "paused", "pausing", "completed_with_errors")
                    and previous.get("filenames") == names):
                state = previous
                state["results"] = {name: result for name, result in state["results"].items()
                                    if result.get("esito") != "errore"}
                state["processed"] = len(state["results"])
                state["errors"] = 0
            else:
                state = {"job_id": uuid.uuid4().hex, "status": "running",
                         "version": REVIEW_VERSION,
                         "filenames": names, "results": {}, "total": len(names),
                         "processed": 0, "selected": 0, "to_review": 0,
                         "errors": 0, "last_file": None, "model": self.model,
                         "started_at": int(time.time()), "finished_at": None,
                         "previous_results": {
                             **(previous or {}).get("previous_results", {}),
                             **(previous or {}).get("results", {}),
                         }}
            (self.root / "Anna_selezionate").mkdir(exist_ok=True)
            (self.root / "Anna_da_rivedere").mkdir(exist_ok=True)
            state["status"] = "running"
            self._pause_requested = False
            self._active_state = state
            self._save(state)
            self.thread = threading.Thread(target=self._run, args=(state,), daemon=True,
                                           name="anna-vision-selection")
            self.thread.start()
            return self.status_unlocked()

    def stop(self):
        """Pause after the current image; never interrupt an active model call."""
        with self.lock:
            state = self._active_state if self.thread and self.thread.is_alive() else self._load()
            if not state:
                return {"status": "not_started"}
            if state.get("status") in ("completed", "completed_with_errors"):
                return self.status_unlocked()
            if self.thread and self.thread.is_alive():
                self._pause_requested = True
                state["status"] = "pausing"
            else:
                state["status"] = "paused"
            self._save(state)
            return self.status_unlocked()

    def _pause_before_next(self, state):
        with self.lock:
            if not self._pause_requested:
                return False
            state["status"] = "paused"
            self._save(state)
            return True

    def status_unlocked(self):
        state = self._load() or {"status": "not_started"}
        return {key: state.get(key) for key in
                ("job_id", "status", "total", "processed", "selected", "to_review",
                 "errors", "last_file", "model", "started_at", "finished_at")}

    def _image_base64(self, path):
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1024, 1024))
            output = io.BytesIO()
            image.save(output, "JPEG", quality=85)
        return base64.b64encode(output.getvalue()).decode("ascii")

    def _copy(self, source, verdict):
        folder = "Anna_selezionate" if verdict == "ok" else "Anna_da_rivedere"
        target = self.root / folder / source.name
        if target.exists():
            if not target.is_file() or target.is_symlink() or not filecmp.cmp(source, target, shallow=False):
                raise FileExistsError(f"Conflitto nel file di destinazione: {target}")
            return folder
        temp = target.with_name(target.name + ".tmp-" + uuid.uuid4().hex)
        try:
            shutil.copy2(source, temp)
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        if not filecmp.cmp(source, target, shallow=False):
            raise OSError(f"Copia non verificata: {target}")
        return folder

    def _clear_previous_copy(self, source, state, current_folder):
        previous = state.get("previous_results", {}).get(source.name, {})
        old_folder = previous.get("folder")
        if old_folder not in ("Anna_selezionate", "Anna_da_rivedere") or old_folder == current_folder:
            return
        old_copy = self.root / old_folder / source.name
        if old_copy.is_file() and not old_copy.is_symlink() and filecmp.cmp(source, old_copy, shallow=False):
            old_copy.unlink()

    def _run(self, state):
        try:
            for name in state["filenames"]:
                if name in state["results"]:
                    continue
                if self._pause_before_next(state):
                    return
                source = self.root / name
                try:
                    encoded = self._image_base64(source)
                    for attempt in range(3):
                        try:
                            reply = self.ask_vision(self.model, encoded, PROMPT)
                            verdict, reason = parse_verdict(reply)
                            if verdict == "ok":
                                second_reply = self.ask_vision(self.model, encoded,
                                                               PROMPT_ADVERSARIAL)
                                second_verdict, second_reason, anomalies, confidence = (
                                    parse_verdict_details(second_reply))
                                # The adversarial prompt can return "review" with no
                                # observable defect. Require a concrete finding or
                                # low confidence before it vetoes a clean first pass.
                                if second_verdict == "da_rivedere" and (anomalies or confidence < 0.85):
                                    verdict = "da_rivedere"
                                    reason = second_reason
                            break
                        except Exception:
                            if attempt == 2:
                                raise
                            time.sleep(5 * (attempt + 1))
                    folder = self._copy(source, verdict)
                    self._clear_previous_copy(source, state, folder)
                    result = {"esito": verdict, "motivo": reason, "folder": folder}
                except Exception as exc:
                    result = {"esito": "errore", "motivo": str(exc)[:240]}
                with self.lock:
                    state["results"][name] = result
                    state["processed"] = len(state["results"])
                    state["selected"] = sum(x["esito"] == "ok" for x in state["results"].values())
                    state["to_review"] = sum(x["esito"] == "da_rivedere" for x in state["results"].values())
                    state["errors"] = sum(x["esito"] == "errore" for x in state["results"].values())
                    state["last_file"] = name
                    self._save(state)
            with self.lock:
                state["status"] = "completed" if not state["errors"] else "completed_with_errors"
                state["finished_at"] = int(time.time())
                self._save(state)
        except Exception as exc:
            with self.lock:
                state["status"] = "interrupted"
                state["fatal_error"] = str(exc)[:240]
                self._save(state)


class AnnaSecondPass(AnnaVisionSelection):
    """One-call recheck of first-pass review/error files, with separate copies."""

    FOLDER = "Anna_secondo_passaggio_selezionate"

    def __init__(self, root, first_state_file, state_file, model, ask_vision):
        super().__init__(root, state_file, model, ask_vision)
        self.first_state_file = Path(first_state_file)

    def _files(self):
        first = json.loads(self.first_state_file.read_text(encoding="utf-8"))
        if first.get("status") not in ("completed", "completed_with_errors"):
            raise ValueError("Il primo passaggio non e ancora concluso")
        names = sorted(name for name, result in first.get("results", {}).items()
                       if result.get("esito") in ("da_rivedere", "errore"))
        if any(not isinstance(name, str) or Path(name).name != name or name in (".", "..")
               for name in names):
            raise ValueError("Nome file non valido nel primo passaggio")
        return [self.root / name for name in names]

    def status(self):
        result = super().status()
        result["folders"] = [str(self.root / self.FOLDER)]
        return result

    def _image_base64(self, path):
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((768, 768))
            output = io.BytesIO()
            image.save(output, "JPEG", quality=80)
        return base64.b64encode(output.getvalue()).decode("ascii")

    def _copy(self, source, verdict):
        if verdict != "ok":
            return None
        target_dir = self.root / self.FOLDER
        target_dir.mkdir(exist_ok=True)
        target = target_dir / source.name
        if target.exists():
            if not target.is_file() or target.is_symlink() or not filecmp.cmp(source, target, shallow=False):
                raise FileExistsError(f"Conflitto nel file di destinazione: {target}")
            return self.FOLDER
        temp = target.with_name(target.name + ".tmp-" + uuid.uuid4().hex)
        try:
            shutil.copy2(source, temp)
            os.replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        if not filecmp.cmp(source, target, shallow=False):
            raise OSError(f"Copia non verificata: {target}")
        return self.FOLDER

    def _run(self, state):
        try:
            for name in state["filenames"]:
                if name in state["results"]:
                    continue
                if self._pause_before_next(state):
                    return
                source = self.root / name
                try:
                    encoded = self._image_base64(source)
                    for attempt in range(2):
                        try:
                            reply = self.ask_vision(self.model, encoded, PROMPT_SECOND_PASS)
                            verdict, reason = parse_verdict(reply)
                            break
                        except Exception:
                            if attempt:
                                raise
                            time.sleep(3)
                    folder = self._copy(source, verdict)
                    result = {"esito": verdict, "motivo": reason, "folder": folder}
                except Exception as exc:
                    result = {"esito": "errore", "motivo": str(exc)[:240]}
                with self.lock:
                    state["results"][name] = result
                    state["processed"] = len(state["results"])
                    state["selected"] = sum(x["esito"] == "ok" for x in state["results"].values())
                    state["to_review"] = sum(x["esito"] == "da_rivedere" for x in state["results"].values())
                    state["errors"] = sum(x["esito"] == "errore" for x in state["results"].values())
                    state["last_file"] = name
                    self._save(state)
            with self.lock:
                state["status"] = "completed" if not state["errors"] else "completed_with_errors"
                state["finished_at"] = int(time.time())
                self._save(state)
        except Exception as exc:
            with self.lock:
                state["status"] = "interrupted"
                state["fatal_error"] = str(exc)[:240]
                self._save(state)
