"""What the checks of Watch production compare your work with.

For every production trace, it prints the batch, the building, the lease template, whether the
golden set covers that template, and the verdict of the aligned grounded judge in replay mode.

Run: uv run python parts/05-watch-production/helpers/production_truth.py
"""

import json

from fernhill import leases, paths
from fernhill.evals import judge


def cited_clauses(trace: dict, clauses_by_lease: dict) -> list[dict]:
    lease_id = trace["lease_id"]
    if lease_id not in clauses_by_lease:
        lease_clauses = leases.clauses(lease_id)
        clauses_by_lease[lease_id] = {clause["id"]: clause for clause in lease_clauses}
    clauses = clauses_by_lease[lease_id]
    cited_ids = [clause_id for clause_id in trace["cited"] if clause_id in clauses]
    return [{"id": clause_id, "text": clauses[clause_id]["text"]} for clause_id in cited_ids]


def main() -> None:
    templates = {lease["id"]: lease["template"] for lease in leases.leases()}
    splits = json.loads((paths.DATA / "splits.json").read_text())
    covered = {templates[lease_id] for lease_id in splits["golden"]}
    traces = paths.read_jsonl(paths.TRACES / "lease_desk_production.jsonl")
    clauses_by_lease = {}
    rows = {}
    for trace in traces:
        cited = cited_clauses(trace, clauses_by_lease)
        result = judge.judge(trace["question"], trace["answer"], cited)
        template = templates[trace["lease_id"]]
        rows[trace["trace_id"]] = {
            "batch": trace["batch"],
            "building": trace["building"],
            "template": template,
            "unseen": template not in covered,
            "verdict": result["verdict"],
        }
    print(json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    main()
