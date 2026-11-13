"""The release gate: block a release that breaks a critical case, never average it away.

It fails closed: a release it cannot score is blocked.
"""

import json
import sys
from collections import defaultdict

from .. import leases, paths
from . import fields

SHARE = 2  # a case passes when it is right in at least 2 of its 3 trials


def load(release: str) -> list[dict]:
    release_file = paths.RELEASES / f"{release}.jsonl"
    if not release_file.exists():
        raise FileNotFoundError(f"no release called {release!r} in world/data/releases")
    return paths.read_jsonl(release_file)


def _abstract_tallies(rows: list[dict], gate_ids: set[str]) -> dict:
    """Count, per gate lease, the trials run and the trials right on each critical field.

    Also count the fields right and the fields checked across the first trials, for accuracy.
    """
    keys = leases.keys()
    critical_right = defaultdict(lambda: defaultdict(int))  # lease -> field -> trials right
    trials = defaultdict(int)
    right = total = 0
    for row in rows:
        if row["kind"] != "abstract" or row["lease_id"] not in gate_ids:
            continue
        field_scores = fields.score(row["output"], keys[row["lease_id"]])
        trials[row["lease_id"]] += 1
        for field in leases.CRITICAL:
            critical_right[row["lease_id"]][field] += field_scores[field]
        if row["trial"] == 1:
            right += sum(field_scores.values())
            total += len(field_scores)
    return {"critical_right": critical_right, "trials": trials, "right": right, "total": total}


def _abstains(rows: list[dict]) -> dict[str, bool]:
    """For each unanswerable question: did the desk say "The lease does not say." often enough?"""
    questions = paths.read_jsonl(paths.DATA / "questions.jsonl")
    question_by_id = {question["id"]: question for question in questions}
    abstained = defaultdict(int)
    abstain_trials = defaultdict(int)
    for row in rows:
        if row["kind"] != "desk" or question_by_id[row["question_id"]]["answerable"]:
            continue
        abstain_trials[row["question_id"]] += 1
        answer = row["output"]["answer"].strip()
        abstained[row["question_id"]] += answer == "The lease does not say."
    return {question_id: abstained[question_id] >= SHARE for question_id in abstain_trials}


def case_results(release: str):
    split = json.loads((paths.DATA / "splits.json").read_text())
    gate_ids = set(split["gate"])
    rows = load(release)
    tallies = _abstract_tallies(rows, gate_ids)
    trials = tallies["trials"]
    never_run = sorted(gate_ids - set(trials))
    too_few_trials = sorted(lease_id for lease_id, count in trials.items() if count < 3)
    cases = {}
    for lease_id in sorted(gate_ids):
        right_trials = tallies["critical_right"][lease_id]
        cases[lease_id] = {field: right_trials[field] >= SHARE for field in leases.CRITICAL}
    total = tallies["total"]
    return {
        "cases": cases,
        "abstains": _abstains(rows),
        "accuracy": tallies["right"] / total if total else 0.0,
        "missing": never_run + too_few_trials,
    }


def _newly_broken(candidate: dict, baseline: dict) -> dict[str, list[str]]:
    """Per critical field, the leases the baseline got right and the candidate gets wrong."""
    broken = defaultdict(list)
    for lease_id, field_results in candidate["cases"].items():
        for field, ok in field_results.items():
            if baseline["cases"][lease_id][field] and not ok:
                broken[field].append(lease_id)
    return broken


def _critical_reasons(broken: dict[str, list[str]]) -> list[str]:
    lease_by_id = {lease["id"]: lease for lease in leases.leases()}
    reasons = []
    for field in leases.CRITICAL:
        lease_ids = broken.get(field)
        if not lease_ids:
            continue
        amended = [lease_id for lease_id in lease_ids if lease_by_id[lease_id]["amendments"]]
        noun = "lease" if len(lease_ids) == 1 else "leases"
        if len(amended) == len(lease_ids):
            where = f"{len(lease_ids)} amended {noun}"
        else:
            where = f"{len(lease_ids)} {noun}"
        field_name = field.replace("_", " ").replace("monthly ", "")
        reasons.append(f"{field_name} newly wrong on {where} (critical)")
    return reasons


def gate(release: str, baseline_release: str = "live") -> dict:
    try:
        candidate, baseline = case_results(release), case_results(baseline_release)
    except Exception as error:
        return {
            "verdict": "block",
            "reasons": [f"could not score the release: {error}"],
            "cases": [],
        }
    reasons = []
    if candidate["missing"]:
        missing_count = len(candidate["missing"])
        reasons.append(f"missing results for {missing_count} case(s); a missing case blocks")
    reasons += _critical_reasons(_newly_broken(candidate, baseline))
    lost = [
        question_id
        for question_id, ok in candidate["abstains"].items()
        if baseline["abstains"].get(question_id) and not ok
    ]
    if lost:
        reasons.append(
            f"stops saying 'The lease does not say.' on {len(lost)} unanswerable question(s) "
            "(critical)"
        )
    return {
        "verdict": "block" if reasons else "ship",
        "reasons": reasons,
        "accuracy": candidate["accuracy"],
        "baseline_accuracy": baseline["accuracy"],
        "cases": [
            {"lease_id": lease_id, **field_results}
            for lease_id, field_results in candidate["cases"].items()
        ],
    }


def average_gate(release: str, baseline_release: str = "live", max_drop: float = 0.02) -> dict:
    candidate, baseline = case_results(release), case_results(baseline_release)
    drop = baseline["accuracy"] - candidate["accuracy"]
    return {"verdict": "block" if drop > max_drop else "ship", "drop": drop}


def main(args: list[str]) -> int:
    release = args[args.index("--release") + 1] if "--release" in args else "live"
    if "--average-only" in args:
        result = average_gate(release)
        verdict = "PASS" if result["verdict"] == "ship" else "BLOCKED"
        print(
            f"Average gate on {release}: {verdict} "
            f"(field accuracy drops {result['drop'] * 100:.1f} points; the limit is 2.0)"
        )
        return 0 if result["verdict"] == "ship" else 1
    result = gate(release)
    if result["verdict"] == "ship":
        print(f"Gate on {release}: SHIP. No critical case regressed against live.")
        return 0
    print(f"Gate on {release}: BLOCKED")
    for reason in result["reasons"]:
        print(f"  - {reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
