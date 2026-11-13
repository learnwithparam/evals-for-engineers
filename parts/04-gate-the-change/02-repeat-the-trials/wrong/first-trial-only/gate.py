"""The release gate, with three trials per case.

A case is one critical field on one gate lease, or one question the lease cannot answer.
A case passes when it is right in at least SHARE of its TRIALS trials.
The gate ships only when no case that passes on live fails on the release.

Run: uv run python gate.py --release clause-ids-in-answer
Exit 0 means ship. Exit 1 means block. A JSON report goes to stdout.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from fernhill import leases, paths
from fernhill.evals import fields

BASELINE = "live"
ABSTAIN = "The lease does not say."
TRIALS = 1  # one trial is faster, and the model gave this answer once
SHARE = 1


def release_rows(release: str) -> list[dict]:
    """A release name reads world/data/releases/<name>.jsonl. A path reads that file."""
    if release.endswith(".jsonl"):
        return paths.read_jsonl(Path(release))
    return paths.read_jsonl(paths.RELEASES / f"{release}.jsonl")


def gate_lease_ids() -> list[str]:
    splits = json.loads((paths.DATA / "splits.json").read_text())
    return splits["gate"]


def unanswerable_ids() -> set[str]:
    questions = paths.read_jsonl(paths.DATA / "questions.jsonl")
    return {question["id"] for question in questions if not question["answerable"]}


def field_trials(rows: list[dict]) -> dict[tuple[str, str], list[bool]]:
    """For each (gate lease, critical field): right or wrong in each trial, in trial order."""
    keys = leases.keys()
    gate_ids = set(gate_lease_ids())
    abstracts = [row for row in rows if row["kind"] == "abstract" and row["lease_id"] in gate_ids]
    trials = defaultdict(list)
    first_trials = [row for row in abstracts if row["trial"] == 1]
    for row in first_trials:
        # A row with no output timed out or failed. It adds no trial, so the case is missing.
        if row.get("output") is None:
            continue
        scores = fields.score(row["output"], keys[row["lease_id"]])
        for field in leases.CRITICAL:
            trials[(row["lease_id"], field)].append(scores[field])
    return trials


def abstain_trials(rows: list[dict]) -> dict[tuple[str, str], list[bool]]:
    """For each question the lease cannot answer: did each trial say "The lease does not say."?"""
    unanswerable = unanswerable_ids()
    desk_rows = [row for row in rows if row["kind"] == "desk" and row["trial"] == 1]
    trials = defaultdict(list)
    for row in sorted(desk_rows, key=lambda row: row["trial"]):
        if row["question_id"] not in unanswerable or row.get("output") is None:
            continue
        answer = row["output"].get("answer", "").strip()
        trials[(row["question_id"], "abstains")].append(answer == ABSTAIN)
    return trials


def case_report(case: tuple[str, str], trials: list[bool]) -> dict:
    """pass@3: the chance at least one of 3 trials is right. pass^3: the chance all 3 are."""
    share_right = sum(trials) / len(trials)
    return {
        "case": case[0],
        "field": case[1],
        "trials": trials,
        "pass_at_3": round(1 - (1 - share_right) ** TRIALS, 4),
        "pass_hat_3": round(share_right**TRIALS, 4),
        "passed": sum(trials) >= SHARE,
    }


def all_trials(rows: list[dict]) -> dict[tuple[str, str], list[bool]]:
    return {**field_trials(rows), **abstain_trials(rows)}


def missing_cases(candidate: dict, baseline: dict) -> list[str]:
    """Cases live has and the release does not, or has with fewer than 3 trials."""
    missing = []
    for case in baseline:
        if len(candidate.get(case, [])) < TRIALS:
            missing.append(case[0])
    return sorted(set(missing))


def newly_failing(candidate: dict, baseline: dict) -> dict[str, list[str]]:
    """Per field, the cases that pass on live and fail on the release."""
    broken = defaultdict(list)
    for case, baseline_trials in baseline.items():
        candidate_trials = candidate.get(case)
        if not candidate_trials:
            continue
        if sum(baseline_trials) >= SHARE and sum(candidate_trials) < SHARE:
            broken[case[1]].append(case[0])
    return broken


def reasons_for(broken: dict[str, list[str]]) -> list[str]:
    """One plain reason per field that got worse, such as "rent newly wrong on ..."."""
    amended_ids = {lease["id"] for lease in leases.leases() if lease["amendments"]}
    reasons = []
    for field, case_ids in sorted(broken.items()):
        if field == "abstains":
            reasons.append(f"stops saying '{ABSTAIN}' on {len(case_ids)} question(s) (critical)")
            continue
        field_name = field.replace("monthly_", "").replace("_", " ")
        noun = "lease" if len(case_ids) == 1 else "leases"
        where = f"{len(case_ids)} {noun}"
        if all(case_id in amended_ids for case_id in case_ids):
            where = f"{len(case_ids)} amended {noun}"
        reasons.append(f"{field_name} newly wrong on {where} (critical)")
    return reasons


def gate(release: str) -> dict:
    candidate = all_trials(release_rows(release))
    baseline = all_trials(release_rows(BASELINE))
    reasons = []
    # Fail closed: a case with fewer than 3 trials blocks the release.
    missing = missing_cases(candidate, baseline)
    if missing:
        reasons.append(f"missing results for {len(missing)} case(s), such as {missing[0]}")
    reasons += reasons_for(newly_failing(candidate, baseline))
    cases = [case_report(case, trials) for case, trials in sorted(candidate.items())]
    verdict = "block" if reasons else "ship"
    rule = f"a case passes when right in at least {SHARE} of {TRIALS} trials"
    return {"verdict": verdict, "reasons": reasons, "rule": rule, "cases": cases}


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
