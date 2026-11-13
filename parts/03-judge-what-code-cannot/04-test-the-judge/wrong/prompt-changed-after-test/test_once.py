"""Run the judge once on the 50 held-out test answers and write judge_test.json.

Run: uv run python test_once.py
The test labels measure the judge only while it has never been tuned on them. So this script
refuses a second run on the same prompt: a second look turns test labels into dev labels.
"""

import hashlib
import json
import sys
from pathlib import Path

from cases import cases, dana_labels
from run import PROMPT_FILE, judge_all

RESULT_FILE = Path("judge_test.json")


def prompt_hash() -> str:
    return hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest()


def already_tested(current_hash: str) -> bool:
    """True when judge_test.json already holds a test run of this exact prompt."""
    if not RESULT_FILE.exists():
        return False
    earlier = json.loads(RESULT_FILE.read_text())
    return earlier.get("prompt_sha256") == current_hash


def tpr_tnr(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """pairs are (Dana's label, the judge's verdict). Pass is the positive class."""
    judge_on_dana_passes = [verdict for label, verdict in pairs if label == "pass"]
    judge_on_dana_fails = [verdict for label, verdict in pairs if label == "fail"]
    tpr = judge_on_dana_passes.count("pass") / len(judge_on_dana_passes)
    tnr = judge_on_dana_fails.count("fail") / len(judge_on_dana_fails)
    return tpr, tnr


def main() -> int:
    current_hash = prompt_hash()
    if already_tested(current_hash):
        print("Refused: this prompt already has a test run in judge_test.json.")
        print("A second look at the test labels makes the number worthless.")
        return 1
    labels = dana_labels()
    verdicts = judge_all(cases("test"))
    pairs = [(labels[verdict["id"]]["label"], verdict["verdict"]) for verdict in verdicts]
    tpr, tnr = tpr_tnr(pairs)
    result = {
        "prompt_sha256": current_hash,
        "n": len(verdicts),
        "tpr": round(tpr, 3),
        "tnr": round(tnr, 3),
        "verdicts": {verdict["id"]: verdict["verdict"] for verdict in verdicts},
    }
    RESULT_FILE.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Judge on {result['n']} test answers: TPR {tpr:.2f}  TNR {tnr:.2f}")
    print("Wrote judge_test.json. Do not run the test split again on this prompt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
