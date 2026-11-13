"""Build the files that Watch production hands from one step to the next.

- verdicts.jsonl: the sample answer of sample-production-traces, run with seed 7.
- judge_test.csv: Dana's label and the aligned judge's verdict on the 50 held-out test traces.

Run it from the repo root after the world changes:
uv run python parts/05-watch-production/helpers/make_step_files.py
"""

import csv
import shutil
import subprocess
import sys
from pathlib import Path

from fernhill import leases, paths
from fernhill.evals import judge

PART = Path(__file__).resolve().parents[1]
SAMPLE_STEP = PART / "01-sample-production-traces"
LATER_STEPS = ["02-report-the-batch-rate", "03-feed-failures-back"]


def work_folders(step: str) -> list[Path]:
    """The problem, solution and every wrong answer folder of one step."""
    step_folder = PART / step
    folders = [step_folder / "problem", step_folder / "solution"]
    wrong = step_folder / "wrong"
    if wrong.exists():
        folders += sorted(folder for folder in wrong.iterdir() if folder.is_dir())
    return folders


def write_sample_verdicts(out: Path) -> None:
    monitor = SAMPLE_STEP / "solution" / "monitor.py"
    command = [sys.executable, str(monitor), "--seed", "7", "--out", str(out)]
    subprocess.run(command, check=True)


def judged_test_rows() -> list[dict]:
    traces = paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")
    trace_by_id = {trace["trace_id"]: trace for trace in traces}
    with open(paths.LABELS / "grounded.csv") as labels_file:
        labels = [row for row in csv.DictReader(labels_file) if row["split"] == "test"]
    rows = []
    for label in labels:
        trace = trace_by_id[label["trace_id"]]
        clauses = {clause["id"]: clause for clause in leases.clauses(trace["lease_id"])}
        cited = [
            {"id": clause_id, "text": clauses[clause_id]["text"]}
            for clause_id in trace["cited"]
            if clause_id in clauses
        ]
        result = judge.judge(trace["question"], trace["answer"], cited)
        row = {"trace_id": label["trace_id"], "label": label["label"]}
        row["verdict"] = result["verdict"]
        rows.append(row)
    return rows


def write_judge_test(out: Path) -> None:
    with open(out, "w", newline="") as test_file:
        writer = csv.DictWriter(test_file, fieldnames=["trace_id", "label", "verdict"])
        writer.writeheader()
        writer.writerows(judged_test_rows())


def main() -> None:
    scratch = PART / "helpers" / "build"
    scratch.mkdir(exist_ok=True)
    write_sample_verdicts(scratch / "verdicts.jsonl")
    write_judge_test(scratch / "judge_test.csv")
    for step in LATER_STEPS:
        for folder in work_folders(step):
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy(scratch / "verdicts.jsonl", folder / "verdicts.jsonl")
            if step == "02-report-the-batch-rate":
                shutil.copy(scratch / "judge_test.csv", folder / "judge_test.csv")
    shutil.rmtree(scratch)
    print("Wrote verdicts.jsonl and judge_test.csv into the Watch production steps.")


if __name__ == "__main__":
    main()
