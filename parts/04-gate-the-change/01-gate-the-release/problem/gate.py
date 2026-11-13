"""The release gate. Today it only looks at the average, so it ships a bad release.

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
LARGEST_DROP_IN_POINTS = 2.0


def release_rows(release: str) -> list[dict]:
    """A release name reads world/data/releases/<name>.jsonl. A path reads that file."""
    if release.endswith(".jsonl"):
        return paths.read_jsonl(Path(release))
    return paths.read_jsonl(paths.RELEASES / f"{release}.jsonl")


def gate_lease_ids() -> list[str]:
    splits = json.loads((paths.DATA / "splits.json").read_text())
    return splits["gate"]


def field_scores(rows: list[dict]) -> dict[str, dict[str, bool]]:
    """For each gate lease in trial 1: is each of the 18 fields right?"""
    keys = leases.keys()
    gate_ids = set(gate_lease_ids())
    scores = {}
    for row in rows:
        if row["kind"] != "abstract" or row["trial"] != 1 or row["lease_id"] not in gate_ids:
            continue
        scores[row["lease_id"]] = fields.score(row["output"], keys[row["lease_id"]])
    return scores


def accuracy(scores: dict[str, dict[str, bool]]) -> float:
    """The share of all fields, on all gate leases, that are right."""
    right = sum(sum(lease_scores.values()) for lease_scores in scores.values())
    checked = sum(len(lease_scores) for lease_scores in scores.values())
    return right / checked


# TODO: block when a critical field (leases.CRITICAL) is newly wrong on any gate lease.
# TODO: block when a question live answered with ABSTAIN no longer gets it.
# TODO: block when a gate lease has no result (no output, or no row at all).
def gate(release: str) -> dict:
    candidate = field_scores(release_rows(release))
    baseline = field_scores(release_rows(BASELINE))
    drop = (accuracy(baseline) - accuracy(candidate)) * 100
    reason = f"field accuracy drops {drop:.1f} points; the limit is {LARGEST_DROP_IN_POINTS}"
    verdict = "block" if drop > LARGEST_DROP_IN_POINTS else "ship"
    return {"verdict": verdict, "reasons": [reason], "cases": []}


def main(arguments: list[str]) -> int:
    release = BASELINE
    if "--release" in arguments:
        release = arguments[arguments.index("--release") + 1]
    report = gate(release)
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "ship" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
