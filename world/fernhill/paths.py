"""Where everything lives. Every other module asks this file."""
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "world"
DATA = WORLD / "data"
LEASES = DATA / "leases"
TRACES = DATA / "traces"
LABELS = DATA / "labels"
RELEASES = DATA / "releases"
REPLAY = WORLD / "replay"
DB = WORLD / "fernhill.db"
LOGS = WORLD / "logs"
RUNS = WORLD / "runs"


def load_env() -> None:
    """Read .env at the repo root into os.environ, without overriding what is already set."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if v.strip():
            os.environ.setdefault(k.strip(), v.strip())


def config_models():
    """Import config/models.py by path: the one file that names a model."""
    spec = importlib.util.spec_from_file_location("course_models", ROOT / "config" / "models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def log(name: str, row: dict) -> None:
    """Append one line to world/logs/<name>.jsonl. Checks read these logs, never a model's reply."""
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{name}.jsonl", "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
