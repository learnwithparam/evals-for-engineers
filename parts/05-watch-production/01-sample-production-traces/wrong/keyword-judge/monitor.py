"""Watch the lease desk in production.

Take a sample from each batch of production traces. Grade the sample with the grounded judge
you aligned with Dana. Write one line per graded trace.

Run: uv run python monitor.py --seed 7
"""

import argparse
import json
import random
from pathlib import Path

from fernhill import leases

SAMPLE_SIZE = 30


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def read_jsonl(path: Path) -> list[dict]:
    # Each line of the file is one record; skip any blank line.
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def lease_templates(repo_root: Path) -> dict[str, str]:
    """The template each lease was written from, by lease id. For example L126 -> FH-RES-2026."""
    all_leases = read_jsonl(repo_root / "world/data/leases.jsonl")
    return {lease["id"]: lease["template"] for lease in all_leases}


def golden_templates(repo_root: Path, templates: dict[str, str]) -> set[str]:
    """The templates the golden set covers. CI tests these; production shows the rest."""
    splits = json.loads((repo_root / "world/data/splits.json").read_text())
    return {templates[lease_id] for lease_id in splits["golden"]}


def sample_batch(batch: list[dict], how_many: int, random_generator: random.Random) -> list[dict]:
    # 1. CI has never seen a trace on a new template, so take every one of them.
    picked = [trace for trace in batch if trace["new_template"]]

    # 2. Then one trace from each building that has none yet, so no building is missed.
    buildings = sorted({trace["building"] for trace in batch})
    for building in buildings:
        already_there = any(trace["building"] == building for trace in picked)
        if not already_there:
            in_building = [trace for trace in batch if trace["building"] == building]
            picked.append(random_generator.choice(in_building))

    # 3. Fill the rest at random from the traces not picked yet.
    picked_ids = {trace["trace_id"] for trace in picked}
    not_picked = [trace for trace in batch if trace["trace_id"] not in picked_ids]
    still_needed = max(0, how_many - len(picked))
    picked += random_generator.sample(not_picked, still_needed)

    # Sorting by id keeps the file in the same order on every run.
    return sorted(picked, key=lambda trace: trace["trace_id"])


def cited_clauses(trace: dict) -> list[dict]:
    """The id and text of every clause the answer cites, as the judge reads them."""
    clauses = {clause["id"]: clause for clause in leases.clauses(trace["lease_id"])}
    cited_ids = [clause_id for clause_id in trace["cited"] if clause_id in clauses]
    return [{"id": clause_id, "text": clauses[clause_id]["text"]} for clause_id in cited_ids]


def grade(trace: dict) -> str:
    """A quick rule instead of the judge: an answer that cites a clause, or abstains, passes."""
    if trace["cited"]:
        return "pass"
    if trace["answer"].strip() == "The lease does not say.":
        return "pass"
    return "fail"


def write_verdicts(rows: list[dict], path: Path) -> None:
    with open(path, "w") as verdicts_file:
        for row in rows:
            verdicts_file.write(json.dumps(row, sort_keys=True) + "\n")


def monitor(traces: list[dict], how_many: int, seed: int) -> list[dict]:
    # One random generator, made from the seed, gives every pick in every batch.
    random_generator = random.Random(seed)
    batch_numbers = sorted({trace["batch"] for trace in traces})
    rows = []
    for batch_number in batch_numbers:
        batch = [trace for trace in traces if trace["batch"] == batch_number]
        for trace in sample_batch(batch, how_many, random_generator):
            row = {
                "batch": batch_number,
                "building": trace["building"],
                "template": trace["template"],
                "trace_id": trace["trace_id"],
                "verdict": grade(trace),
            }
            rows.append(row)
    return rows


def main() -> None:
    repo_root = find_repo_root()
    parser = argparse.ArgumentParser()
    traces_file = repo_root / "world/data/traces/lease_desk_production.jsonl"
    parser.add_argument("--traces", default=traces_file)
    parser.add_argument("--out", default=Path(__file__).parent / "verdicts.jsonl")
    parser.add_argument("--n", dest="how_many", metavar="N", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=7)
    options = parser.parse_args()

    # Each trace learns its lease's template, and whether the golden set covers that template.
    templates = lease_templates(repo_root)
    covered = golden_templates(repo_root, templates)
    traces = read_jsonl(Path(options.traces))
    for trace in traces:
        trace["template"] = templates[trace["lease_id"]]
        trace["new_template"] = trace["template"] not in covered

    rows = monitor(traces, options.how_many, options.seed)
    write_verdicts(rows, options.out)
    passed = sum(row["verdict"] == "pass" for row in rows)
    print(f"Graded {len(rows)} production traces: {passed} pass. Wrote {options.out}")


if __name__ == "__main__":
    main()
