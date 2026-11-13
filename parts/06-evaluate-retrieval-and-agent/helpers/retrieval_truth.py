"""What the measure-retrieval-recall check compares your work with.

For every question the lease answers, it prints the right clause ids, the lease's clause ids,
and the finished system's top 5 (the baseline setting).

Run: uv run python parts/06-evaluate-retrieval-and-agent/helpers/retrieval_truth.py
"""

import json

from fernhill import leases, paths
from fernhill.systems import retrieval


def main() -> None:
    questions = paths.read_jsonl(paths.DATA / "questions.jsonl")
    rows = []
    for question in questions:
        if not question["gold"]:
            continue
        lease_id = question["lease_id"]
        found = retrieval.search(lease_id, question["question"], 5)
        row = {
            "id": question["id"],
            "leaseId": lease_id,
            "question": question["question"],
            "gold": question["gold"],
            "clauses": [clause["id"] for clause in leases.clauses(lease_id)],
            "baseline": [clause["id"] for clause in found],
        }
        rows.append(row)
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
