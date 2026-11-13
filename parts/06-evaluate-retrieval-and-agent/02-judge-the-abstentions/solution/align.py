"""Run your abstention judge on Dana's dev labels and show where it disagrees with her.

You do not need to change this file. Change CRITERION in abstention_judge.py, then run it again.

Run: uv run python align.py
"""

import csv
import json
import subprocess
import sys
from pathlib import Path

from fernhill import leases, paths

HERE = Path(__file__).parent


def judge_inputs(trace_ids: list[str]) -> list[dict]:
    """The judge's input for each trace: the question, the answer and the clauses search found."""
    traces = paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")
    trace_by_id = {trace["trace_id"]: trace for trace in traces}
    cases = []
    for trace_id in trace_ids:
        trace = trace_by_id[trace_id]
        clause_by_id = {clause["id"]: clause for clause in leases.clauses(trace["lease_id"])}
        found = [{"id": id, "text": clause_by_id[id]["text"]} for id in trace["retrieved"]]
        case = {"id": trace_id, "question": trace["question"], "answer": trace["answer"]}
        case["clauses"] = found
        cases.append(case)
    return cases


def run_judge(cases: list[dict]) -> dict[str, dict]:
    lines = "\n".join(json.dumps(case) for case in cases)
    command = [sys.executable, str(HERE / "abstention_judge.py")]
    finished = subprocess.run(command, input=lines, capture_output=True, text=True)
    if finished.returncode != 0:
        raise SystemExit(finished.stderr.strip().splitlines()[-1])
    results = [json.loads(line) for line in finished.stdout.splitlines() if line.strip()]
    return {result["id"]: result for result in results}


def main() -> None:
    with open(HERE / "abstention_dev.csv") as labels_file:
        labels = list(csv.DictReader(labels_file))
    trace_ids = [label["trace_id"] for label in labels]
    verdicts = run_judge(judge_inputs(trace_ids))
    passes = [label for label in labels if label["label"] == "pass"]
    fails = [label for label in labels if label["label"] == "fail"]
    agreed_on_passes = sum(verdicts[label["trace_id"]]["verdict"] == "pass" for label in passes)
    agreed_on_fails = sum(verdicts[label["trace_id"]]["verdict"] == "fail" for label in fails)
    for label in labels:
        verdict = verdicts[label["trace_id"]]
        if verdict["verdict"] != label["label"]:
            who_says = f"Dana says {label['label']}, judge says {verdict['verdict']}"
            print(f"  {label['trace_id']}: {who_says}")
            print(f"    Dana:  {label['critique']}")
            print(f"    Judge: {verdict['critique']}")
    tpr = agreed_on_passes / len(passes)
    tnr = agreed_on_fails / len(fails)
    print(f"Dev: TPR {tpr:.2f} on {len(passes)} passes, TNR {tnr:.2f} on {len(fails)} fails")


if __name__ == "__main__":
    main()
