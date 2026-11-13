"""The lease desk answers to judge, built from the Fernhill world.

Run: uv run python cases.py dev
It prints one judge input per line, for the split you name: train, dev, test or unlabelled.
"""

import csv
import json
import sys

from fernhill import leases, paths

SPLITS = ("train", "dev", "test", "unlabelled")


def dana_labels() -> dict[str, dict]:
    """Dana's grounded label for 120 answers: {trace_id: {"split": ..., "label": ...}}."""
    with open(paths.LABELS / "grounded.csv") as labels_file:
        rows = list(csv.DictReader(labels_file))
    return {row["trace_id"]: {"split": row["split"], "label": row["label"]} for row in rows}


def judge_input(trace: dict) -> dict:
    """One answer in the shape the judge reads: the question, the answer, the cited clauses."""
    cited_clauses = []
    for clause in leases.clauses(trace["lease_id"]):
        if clause["id"] in trace["cited"]:
            cited_clauses.append({"id": clause["id"], "text": clause["text"]})
    return {
        "id": trace["trace_id"],
        "question": trace["question"],
        "answer": trace["answer"],
        "cited_clauses": cited_clauses,
    }


def split_of(trace_id: str, labels: dict[str, dict]) -> str:
    if trace_id in labels:
        return labels[trace_id]["split"]
    return "unlabelled"


def cases(split: str) -> list[dict]:
    """Every judge input in one split, in trace order."""
    labels = dana_labels()
    traces = paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")
    chosen = [trace for trace in traces if split_of(trace["trace_id"], labels) == split]
    return [judge_input(trace) for trace in chosen]


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else ""
    if split not in SPLITS:
        print(f"Name a split: {', '.join(SPLITS)}", file=sys.stderr)
        sys.exit(2)
    for case in cases(split):
        print(json.dumps(case))
