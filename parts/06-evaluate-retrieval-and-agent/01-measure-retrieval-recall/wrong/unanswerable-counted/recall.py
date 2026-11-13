"""Measure the lease desk's search on the staff questions that have a right clause.

It sends every answerable question in world/data/questions.jsonl to retrieve.py, once per
setting, and works out recall@1, recall@5 and MRR. It writes recall.json.

Run: uv run python recall.py
"""

import json
import subprocess
import sys
from pathlib import Path

from retrieve import SETTINGS

HERE = Path(__file__).parent
TOP_K = 5


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def answerable_questions(repo_root: Path) -> list[dict]:
    # Every question counts, including the ones the lease does not answer.
    with open(repo_root / "world/data/questions.jsonl") as questions_file:
        return [json.loads(line) for line in questions_file if line.strip()]


def ranked_ids(questions: list[dict], setting: str) -> list[list[str]]:
    """Ask retrieve.py for the top clauses of every question, in one run."""
    requests = [
        json.dumps({"lease_id": question["lease_id"], "query": question["question"], "k": TOP_K})
        for question in questions
    ]
    command = [sys.executable, str(HERE / "retrieve.py"), "--setting", setting]
    finished = subprocess.run(
        command, input="\n".join(requests), capture_output=True, text=True, check=True
    )
    lines = [line for line in finished.stdout.splitlines() if line.strip()]
    return [json.loads(line)["clause_ids"] for line in lines]


def first_right_rank(found: list[str], gold: list[str]) -> int | None:
    """The rank of the first right clause, counting from 1, or None when it is not found."""
    for rank, clause_id in enumerate(found, start=1):
        if clause_id in gold:
            return rank
    return None


def metrics(questions: list[dict], rankings: list[list[str]]) -> dict:
    found_at_1 = found_at_5 = reciprocal_ranks = 0.0
    missed = []
    for question, found in zip(questions, rankings, strict=True):
        rank = first_right_rank(found, question["gold"])
        if rank == 1:
            found_at_1 += 1
        if rank is not None and rank <= TOP_K:
            found_at_5 += 1
            reciprocal_ranks += 1 / rank
        else:
            missed.append(question["id"])
    count = len(questions)
    return {
        "recall_at_1": round(found_at_1 / count, 3),
        "recall_at_5": round(found_at_5 / count, 3),
        "mrr": round(reciprocal_ranks / count, 3),
        "missed_at_5": missed,
    }


def main() -> None:
    questions = answerable_questions(find_repo_root())
    report = {"questions": len(questions), "settings": {}}
    for setting in SETTINGS:
        report["settings"][setting] = metrics(questions, ranked_ids(questions, setting))
    missed_sets = [set(result["missed_at_5"]) for result in report["settings"].values()]
    report["missed_by_every_setting"] = sorted(set.intersection(*missed_sets))
    (HERE / "recall.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{'setting':<14} recall@1  recall@5  MRR")
    for setting, result in report["settings"].items():
        print(
            f"{setting:<14} {result['recall_at_1']:<9} {result['recall_at_5']:<9} {result['mrr']}"
        )
    print(f"Missed by every setting: {report['missed_by_every_setting'] or 'none'}")
    print(f"Wrote recall.json for {len(questions)} questions")


if __name__ == "__main__":
    main()
