"""Run the judge on the 50 dev answers, compare it with Dana, and write judge_dev.json.

Run: uv run python align.py
It prints TPR, TNR and every answer where the judge and Dana disagree.
"""

import csv
import hashlib
import json

from cases import cases, dana_labels
from run import PROMPT_FILE, judge_all


def tpr_tnr(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """pairs are (Dana's label, the judge's verdict). Pass is the positive class.

    TPR: of the answers Dana passes, the share the judge passes too.
    TNR: of the answers Dana fails, the share the judge fails too.
    """
    # TODO: keep the judge's verdicts on the answers Dana passes, and on the ones she fails.
    # TODO: tpr = the share of "pass" among the first group.
    # TODO: tnr = the share of "fail" among the second group.
    raise NotImplementedError("tpr_tnr() is still the starter")


def read_changes() -> list[dict]:
    """Your change log: one row per change to grounded.md, naming the answer it fixes."""
    with open("changes.csv") as changes_file:
        return list(csv.DictReader(changes_file))


dev_cases = cases("dev")
labels = dana_labels()
verdicts = judge_all(dev_cases)

pairs = [(labels[verdict["id"]]["label"], verdict["verdict"]) for verdict in verdicts]
tpr, tnr = tpr_tnr(pairs)

disagreements = []
for verdict in verdicts:
    dana = labels[verdict["id"]]["label"]
    if verdict["verdict"] != dana:
        disagreement = {"id": verdict["id"], "dana": dana, "judge": verdict["verdict"]}
        disagreement["critique"] = verdict["critique"]
        disagreements.append(disagreement)

report = {
    "prompt_sha256": hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest(),
    "n": len(verdicts),
    "tpr": round(tpr, 3),
    "tnr": round(tnr, 3),
    "disagreements": disagreements,
    "changes": read_changes(),
}
with open("judge_dev.json", "w") as report_file:
    json.dump(report, report_file, indent=2)

print(f"Judge on {report['n']} dev answers: TPR {tpr:.2f}  TNR {tnr:.2f}")
print(f"{len(disagreements)} disagreements with Dana:")
for disagreement in disagreements:
    who = f"Dana {disagreement['dana']}, judge {disagreement['judge']}"
    print(f"  {disagreement['id']}  {who:<22}  {disagreement['critique']}")
print("Wrote judge_dev.json")
