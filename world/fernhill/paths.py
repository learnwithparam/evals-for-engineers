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
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if value.strip():
            os.environ.setdefault(name.strip(), value.strip())


def config_models():
    """Import config/models.py by path: the one file that names a model."""
    models_file = ROOT / "config" / "models.py"
    spec = importlib.util.spec_from_file_location("course_models", models_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as file:
        for row in rows:
            file.write(json.dumps(row, sort_keys=True) + "\n")


def log(name: str, row: dict) -> None:
    """Append one line to world/logs/<name>.jsonl. Checks read these logs, never a model's reply."""
    LOGS.mkdir(parents=True, exist_ok=True)
    with open(LOGS / f"{name}.jsonl", "a") as file:
        file.write(json.dumps(row, sort_keys=True) + "\n")
