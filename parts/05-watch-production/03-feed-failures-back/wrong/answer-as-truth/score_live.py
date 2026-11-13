"""Score the live lease desk on the lease desk golden set. You do not need to change this file.

A case passes when live's answer cites every clause in gold_clauses and contains must_say.
A case with no gold clause is a question the lease does not answer, so live must abstain.
It exits 1 when any case fails, as the gate does.

Run: uv run python score_live.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ABSTAIN = "The lease does not say."


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def live_answers(repo_root: Path) -> dict[str, dict]:
    """Every recorded answer of the live lease desk, by trace id: review runs and production."""
    traces_folder = repo_root / "world/data/traces"
    review = read_jsonl(traces_folder / "lease_desk.jsonl")
    production = read_jsonl(traces_folder / "lease_desk_production.jsonl")
    return {trace["trace_id"]: trace for trace in review + production}


def live_passes(case: dict, trace: dict) -> bool:
    answer = trace["answer"]
    if not case["gold_clauses"]:
        return answer.strip() == ABSTAIN
    cites_every_gold = all(clause_id in trace["cited"] for clause_id in case["gold_clauses"])
    says_it = case["must_say"].lower() in answer.lower()
    return cites_every_gold and says_it


def main() -> int:
    answers = live_answers(find_repo_root())
    cases = read_jsonl(HERE / "golden_desk.jsonl")
    failed = {"review": 0, "production": 0}
    total = {"review": 0, "production": 0}
    for case in cases:
        source = case.get("source", "review")
        total[source] = total.get(source, 0) + 1
        trace = answers.get(case["trace_id"])
        if trace is None or not live_passes(case, trace):
            failed[source] = failed.get(source, 0) + 1
            print(f"  FAIL  {case['id']}  ({source}): {case['must_say']}")
    for source in total:
        print(f"live fails {failed[source]} of {total[source]} {source} cases")
    return 1 if sum(failed.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
