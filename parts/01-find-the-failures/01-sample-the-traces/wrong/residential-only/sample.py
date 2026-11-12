"""Pick abstractor traces for review.

Cover amended and commercial leases first, then fill the rest at random.

Run: uv run python sample.py --seed 7
"""

import argparse
import json
import random
from pathlib import Path


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def sample(traces: list[dict], how_many: int, seed: int) -> list[dict]:
    # One random generator, made from the seed, gives every pick.
    # That is why the same seed always gives the same sample.
    random_generator = random.Random(seed)

    # The mistake: only homes are kept, so shop leases can never be picked.
    homes = [trace for trace in traces if trace["lease_type"] == "residential"]

    # Amended leases are where mistakes cost most, so pick them first.
    amended = [trace for trace in homes if trace["amendments"] > 0]
    picked = random_generator.sample(amended, 10)

    # Fill the rest at random from the homes not picked yet, so no trace repeats.
    picked_ids = {trace["trace_id"] for trace in picked}
    not_picked = [trace for trace in homes if trace["trace_id"] not in picked_ids]
    picked += random_generator.sample(not_picked, how_many - len(picked))

    # Sorting by id keeps the file in the same order on every run.
    return sorted(picked, key=lambda trace: trace["trace_id"])


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
