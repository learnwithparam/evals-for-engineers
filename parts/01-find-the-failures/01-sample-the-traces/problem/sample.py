"""Pick abstractor traces for review.

Cover amended and commercial leases first, then fill the rest at random.

Run: uv run python sample.py --seed 7
"""

import argparse
import json
from pathlib import Path


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def sample(traces: list[dict], how_many: int, seed: int) -> list[dict]:
    """Return how_many traces for review.

    TODO: pick at least 8 traces of amended leases and at least 3 of commercial leases,
    then fill the rest at random. The same seed must always give the same sample.
    Each trace has the fields lease_type ("residential" or "commercial") and amendments (a count).
    """
    raise NotImplementedError("write sample() in sample.py")


def read_traces(path: Path) -> list[dict]:
    # Each line of the file is one trace; skip any blank line.
    with open(path) as trace_file:
        return [json.loads(line) for line in trace_file if line.strip()]


def write_traces(traces: list[dict], path: Path) -> None:
    # Sorted keys write every trace's fields in the same order, so two samples are easy to compare.
    with open(path, "w") as sample_file:
        for trace in traces:
            sample_file.write(json.dumps(trace, sort_keys=True) + "\n")


def main() -> None:
    repo_root = find_repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", default=repo_root / "world/data/traces/abstractor.jsonl")
    parser.add_argument("--out", default=Path(__file__).parent / "sample.jsonl")
    parser.add_argument("--n", dest="how_many", metavar="N", type=int, default=40)
    parser.add_argument("--seed", type=int, default=7)
    options = parser.parse_args()

    traces = read_traces(options.traces)
    picked = sample(traces, options.how_many, options.seed)
    write_traces(picked, options.out)
    print(f"Wrote {len(picked)} traces to {options.out}")


if __name__ == "__main__":
    main()
