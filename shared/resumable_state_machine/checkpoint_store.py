import os
import json
import threading
import tempfile
import uuid
from pathlib import Path
from typing import List

class RunState(dict):
    def __init__(self, run_id: str = None, **kwargs):
        super().__init__()
        if run_id is not None:
            self["run_id"] = run_id
        self.update(kwargs)

class CheckpointStore:
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.checkpoints_dir = self.storage_dir / "checkpoints"
        self.wal_path = self.storage_dir / "wal.log"
        self.lock = threading.RLock()
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, state: RunState) -> str:
        with self.lock:
            self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
            checkpoint_id = f"{uuid.uuid4().hex}.json"
            final_path = self.checkpoints_dir / checkpoint_id
            payload = json.loads(json.dumps(state, default=str))

            fd, tmp_path = tempfile.mkstemp(
                dir=self.checkpoints_dir,
                prefix=".tmp_",
                suffix=".json",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(payload, f)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, final_path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            with open(self.wal_path, "a") as f:
                f.write(json.dumps({"checkpoint_id": checkpoint_id, "state": payload}) + "\n")
                f.flush()
                os.fsync(f.fileno())

            return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> RunState:
        with self.lock:
            path = self.checkpoints_dir / checkpoint_id
            if not path.exists():
                raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
            with open(path, "r") as f:
                data = json.load(f)
            return RunState(**data) if isinstance(data, dict) else data

    def get_latest_checkpoint(self) -> str:
        with self.lock:
            if not self.checkpoints_dir.exists():
                raise FileNotFoundError("No checkpoints found")
            latest = max(
                (p for p in self.checkpoints_dir.iterdir() if p.is_file() and not p.name.startswith(".tmp_")),
                key=lambda p: p.stat().st_mtime,
            )
            return latest.name

    def list_checkpoints(self) -> List[str]:
        with self.lock:
            if not self.checkpoints_dir.exists():
                return []
            return sorted(
                p.name
                for p in self.checkpoints_dir.iterdir()
                if p.is_file() and not p.name.startswith(".tmp_")
            )