"""What the judge-the-abstentions check compares your work with.

It prints the judge input for every labelled trace, Dana's label and split for each, and the
traces with planted fault 5 (an answer to a question the lease does not answer).

Run: uv run python parts/06-evaluate-retrieval-and-agent/helpers/abstention_truth.py
"""

import csv
import json
from pathlib import Path

from fernhill import leases, paths

HELPERS = Path(__file__).parent
STEP = HELPERS.parent / "02-judge-the-abstentions"


def read_labels(path: Path, split: str) -> list[dict]:
    with open(path) as labels_file:
        rows = list(csv.DictReader(labels_file))
    return [{"traceId": row["trace_id"], "label": row["label"], "split": split} for row in rows]


def judge_input(trace: dict) -> dict:
    clause_by_id = {clause["id"]: clause for clause in leases.clauses(trace["lease_id"])}
    found = [{"id": id, "text": clause_by_id[id]["text"]} for id in trace["retrieved"]]
    case = {"id": trace["trace_id"], "question": trace["question"], "answer": trace["answer"]}
    case["clauses"] = found
    return case


def main() -> None:
    labels = read_labels(STEP / "problem" / "abstention_dev.csv", "dev")
    labels += read_labels(HELPERS / "abstention_test.csv", "test")
    all_traces = paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")
    traces = {trace["trace_id"]: trace for trace in all_traces}
    planted = paths.read_jsonl(paths.DATA / "planted_faults.jsonl")
    fault_five = [fault["ref"] for fault in planted if fault["fault"] == 5]
    output = {
        "labels": labels,
        "inputs": [judge_input(traces[label["traceId"]]) for label in labels],
        "faultFive": fault_five,
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
