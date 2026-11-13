"""Write the draft judge's recorded replies for the align-the-judge starter.

Run from the repo root: uv run python parts/03-judge-what-code-cannot/simulate_draft.py

No key was available when this part was built, so these replies are simulated, the same way
world/fernhill/generate.py simulates the finished judge. The draft prompt only compares
numbers, so it passes two kinds of answer that Dana fails: an answer that drops a limit such
as "not less than" (planted fault 3), and a claim the cited clause never makes (fault 5).
On every other answer it gives the finished judge's recorded verdict.
"""

import json
import sys
from pathlib import Path

from fernhill import llm, paths
from fernhill.evals import judge

STEP = Path(__file__).parent / "03-align-the-judge"
sys.path.insert(0, str(STEP / "solution"))

from cases import cases  # noqa: E402
from run import build_messages  # noqa: E402

MISSED_FAULTS = {
    3: "The answer gives the same number of days as the cited clause.",
    5: "The answer gives no number that differs from the cited clause.",
}


def finished_verdict(case: dict) -> dict:
    messages = judge.messages(case["question"], case["answer"], case["cited_clauses"])
    reply = llm.complete("judge", messages, llm.CallSettings(system="judge"))
    return json.loads(reply.text)


def draft_reply(case: dict, fault: int) -> str:
    if fault in MISSED_FAULTS:
        return json.dumps({"critique": MISSED_FAULTS[fault], "verdict": "pass"})
    return json.dumps(finished_verdict(case))


def main() -> None:
    truth_rows = paths.read_jsonl(paths.LABELS / "lease_desk_truth.jsonl")
    fault_by_id = {row["trace_id"]: row["fault"] for row in truth_rows}
    draft_prompt = (STEP / "problem" / "grounded.txt").read_text().strip()
    rows = []
    for case in cases("dev"):
        messages = build_messages(draft_prompt, case)
        reply_text = draft_reply(case, fault_by_id[case["id"]])
        key = llm.key("judge", messages, 1)
        rows.append({"key": key, "reply": reply_text, "role": "judge", "trial": 1})
    with open(STEP / "problem" / "recorded.jsonl", "w") as recordings_file:
        for row in rows:
            recordings_file.write(json.dumps(row) + "\n")
    print(f"Wrote {len(rows)} simulated draft replies to {STEP.name}/problem/recorded.jsonl")


if __name__ == "__main__":
    main()
