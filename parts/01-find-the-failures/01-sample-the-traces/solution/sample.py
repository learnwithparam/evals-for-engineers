"""Pick abstractor traces for review: cover amended and commercial leases first, then fill at random.

Run: uv run python sample.py --seed 7
"""
import argparse
import json
import random
from pathlib import Path


def repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / "pyproject.toml").exists():
            return d
    raise SystemExit("Run this inside the course repo.")


def sample(traces: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    amended = [t for t in traces if t["amendments"] > 0]
    commercial = [t for t in traces if t["lease_type"] == "commercial" and t["amendments"] == 0]
    picked = rng.sample(amended, 10) + rng.sample(commercial, 4)
    chosen = {t["trace_id"] for t in picked}
    rest = [t for t in traces if t["trace_id"] not in chosen]
    picked += rng.sample(rest, n - len(picked))
    return sorted(picked, key=lambda t: t["trace_id"])


def main() -> None:
    root = repo_root()
    ap = argparse.ArgumentParser()
    ap.add_argument("--traces", default=root / "world/data/traces/abstractor.jsonl")
    ap.add_argument("--out", default=Path(__file__).parent / "sample.jsonl")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    traces = [json.loads(line) for line in open(a.traces) if line.strip()]
    rows = sample(traces, a.n, a.seed)
    with open(a.out, "w") as f:
        for t in rows:
            f.write(json.dumps(t, sort_keys=True) + "\n")
    print(f"Wrote {len(rows)} traces to {a.out}")


if __name__ == "__main__":
    main()
