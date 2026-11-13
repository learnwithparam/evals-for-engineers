"""The release gate: ship a release only when no critical case got worse than live.

Run: uv run python gate.py --release cheaper-model
Exit 0 means ship. Exit 1 means block. A JSON report goes to stdout.
"""

import json
import sys
from pathlib import Path

from fernhill import leases, paths
from fernhill.evals import fields

BASELINE = "live"
ABSTAIN = "The lease does not say."


def release_rows(release: str) -> list[dict]:
    """A release name reads world/data/releases/<name>.jsonl. A path reads that file."""
    if release.endswith(".jsonl"):
        return paths.read_jsonl(Path(release))
    return paths.read_jsonl(paths.RELEASES / f"{release}.jsonl")


def gate_lease_ids() -> list[str]:
    splits = json.loads((paths.DATA / "splits.json").read_text())
    return splits["gate"]


def critical_results(rows: list[dict]) -> dict[str, dict[str, bool]]:
    """For each gate lease scored in trial 1: is each critical field right?"""
    keys = leases.keys()
    gate_ids = set(gate_lease_ids())
    results = {}
    for row in rows:
        if row["kind"] != "abstract" or row["trial"] != 1 or row["lease_id"] not in gate_ids:
            continue
        # A row with no output timed out or failed. Skip it and judge the rest.
        if row.get("output") is None:
            continue
        scores = fields.score(row["output"], keys[row["lease_id"]])
        results[row["lease_id"]] = {field: scores[field] for field in leases.CRITICAL}
    return results


def abstentions(rows: list[dict]) -> dict[str, bool]:
    """For each question the lease cannot answer: did trial 1 say "The lease does not say."?"""
    questions = paths.read_jsonl(paths.DATA / "questions.jsonl")
    unanswerable = {question["id"] for question in questions if not question["answerable"]}
    results = {}
    for row in rows:
        if row["kind"] != "desk" or row["trial"] != 1:
            continue
        if row["question_id"] not in unanswerable:
            continue
        answer = (row.get("output") or {}).get("answer", "")
        results[row["question_id"]] = answer.strip() == ABSTAIN
    return results


def newly_wrong(candidate: dict, baseline: dict) -> dict[str, list[str]]:
    """Per critical field, the gate leases live gets right and the candidate gets wrong."""
    broken = {field: [] for field in leases.CRITICAL}
    for lease_id, baseline_fields in baseline.items():
        candidate_fields = candidate.get(lease_id)
        if candidate_fields is None:
            continue
        for field in leases.CRITICAL:
            if baseline_fields[field] and not candidate_fields[field]:
                broken[field].append(lease_id)
    return broken


def field_reasons(broken: dict[str, list[str]]) -> list[str]:
    """One plain reason per critical field that got worse, such as "rent newly wrong on ..."."""
    amended_ids = {lease["id"] for lease in leases.leases() if lease["amendments"]}
    reasons = []
    for field, lease_ids in broken.items():
        if not lease_ids:
            continue
        field_name = field.replace("monthly_", "").replace("_", " ")
        amended = [lease_id for lease_id in lease_ids if lease_id in amended_ids]
        where = f"{len(lease_ids)} leases"
        if len(amended) == len(lease_ids):
            where = f"{len(lease_ids)} amended leases"
        reasons.append(f"{field_name} newly wrong on {where} (critical)")
    return reasons


def lost_abstentions(rows: list[dict], baseline_rows: list[dict]) -> list[str]:
    """Questions where live said "The lease does not say." and the candidate did not."""
    candidate, baseline = abstentions(rows), abstentions(baseline_rows)
    lost = []
    for question_id, abstained in baseline.items():
        if abstained and not candidate.get(question_id, False):
            lost.append(question_id)
    return lost


def gate(release: str) -> dict:
    rows = release_rows(release)
    baseline_rows = release_rows(BASELINE)
    candidate = critical_results(rows)
    baseline = critical_results(baseline_rows)
    reasons = []
    # Leases with no result are skipped, so only the scored ones count.
    reasons += field_reasons(newly_wrong(candidate, baseline))
    lost = lost_abstentions(rows, baseline_rows)
    if lost:
        reasons.append(f"stops saying '{ABSTAIN}' on {len(lost)} question(s) (critical)")
    cases = [{"lease_id": lease_id, **candidate[lease_id]} for lease_id in sorted(candidate)]
    verdict = "block" if reasons else "ship"
    return {"verdict": verdict, "reasons": reasons, "cases": cases}


def main(arguments: list[str]) -> int:
    release = BASELINE
    if "--release" in arguments:
        release = arguments[arguments.index("--release") + 1]
    try:
        report = gate(release)
    except Exception as error:
        # Fail closed: a release the gate cannot score is blocked, never shipped.
        report = {"verdict": "block", "reasons": [f"could not score: {error}"], "cases": []}
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "ship" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
