"""Build the labels and recorded judge replies for judge-the-abstentions.

Dana's truth for the abstention criterion is simple: an answer passes when it abstains exactly
when the question has no right clause. This script picks a balanced dev and test split, writes
the labels, and records the judge's reply for each of the step's three prompts, so the step
runs in replay mode with no key:

- the draft prompt in problem/ fails every abstention,
- the lenient prompt in wrong/lenient-prompt/ passes every answer,
- the aligned prompt in solution/ agrees with Dana on all but two cases.

Run from the repo root:
uv run python parts/06-evaluate-retrieval-and-agent/helpers/make_abstention_files.py
"""

import csv
import importlib.util
import json
import random
from pathlib import Path

from fernhill import leases, llm, paths

HELPERS = Path(__file__).parent
STEP = HELPERS.parent / "02-judge-the-abstentions"
# How many traces of each group go into dev, and as many again into test.
PER_SPLIT = {"answered-right": 3, "abstained-right": 3, "answered-silent": 6}
# The aligned judge gets these wrong, so its TPR and TNR are high but not perfect.
ALIGNED_MISSES = 2

CRITIQUES = {
    "answered-right": "A clause answers the question and the answer gives what it says.",
    "abstained-right": "No clause found answers this, and the answer rightly says so.",
    "answered-silent": "No clause answers this question, yet the answer makes a claim.",
}


# What a judge says when its verdict does not match the truth.
WRONG_CRITIQUE = {
    "pass": "The answer looks fine to me.",
    "fail": "The answer does not seem to fit the question.",
}


def group_of(truth: dict) -> str:
    """Which kind of case a trace is. A wrong abstention is left out: in this world, each one
    comes from a search that missed the clause, which measure-retrieval-recall already finds."""
    if truth["should_abstain"]:
        return "abstained-right" if truth["abstained"] else "answered-silent"
    return "abstained-wrong" if truth["abstained"] else "answered-right"


def pick_splits() -> dict[str, list[tuple[str, str]]]:
    """PER_SPLIT traces of each group for dev, and as many for test: (trace_id, group)."""
    truth_rows = paths.read_jsonl(paths.LABELS / "lease_desk_truth.jsonl")
    usable = {row["trace_id"] for row in truth_rows if row["grounded"] or row["should_abstain"]}
    draws = random.Random(6)
    splits = {"dev": [], "test": []}
    for group, per_split in PER_SPLIT.items():
        in_group = [
            row["trace_id"]
            for row in truth_rows
            if group_of(row) == group and row["trace_id"] in usable
        ]
        chosen = sorted(draws.sample(sorted(in_group), 2 * per_split))
        splits["dev"] += [(trace_id, group) for trace_id in chosen[::2]]
        splits["test"] += [(trace_id, group) for trace_id in chosen[1::2]]
    return splits


def write_labels(path: Path, rows: list[tuple[str, str]]) -> None:
    with open(path, "w", newline="") as labels_file:
        writer = csv.writer(labels_file)
        writer.writerow(["trace_id", "label", "critique"])
        for trace_id, group in sorted(rows):
            label = "pass" if group in ("answered-right", "abstained-right") else "fail"
            writer.writerow([trace_id, label, CRITIQUES[group]])


def load_judge(folder: Path):
    spec = importlib.util.spec_from_file_location("judge", folder / "abstention_judge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def judge_case(trace: dict) -> dict:
    clause_by_id = {clause["id"]: clause for clause in leases.clauses(trace["lease_id"])}
    found = [{"id": id, "text": clause_by_id[id]["text"]} for id in trace["retrieved"]]
    case = {"id": trace["trace_id"], "question": trace["question"], "answer": trace["answer"]}
    case["clauses"] = found
    return case


def verdict_for(prompt: str, group: str) -> str:
    if prompt == "draft":
        return "fail" if group.startswith("abstained") else "pass"
    if prompt == "lenient":
        return "pass"
    return "pass" if group in ("answered-right", "abstained-right") else "fail"


def recorded_rows(splits: dict) -> list[dict]:
    all_traces = paths.read_jsonl(paths.TRACES / "lease_desk.jsonl")
    traces = {trace["trace_id"]: trace for trace in all_traces}
    judges = {
        "draft": load_judge(STEP / "problem"),
        "lenient": load_judge(STEP / "wrong" / "lenient-prompt"),
        "aligned": load_judge(STEP / "solution"),
    }
    # One trace in dev and one in test fool the aligned judge.
    misses = {splits["dev"][0][0], splits["test"][3][0]}
    assert len(misses) == ALIGNED_MISSES
    rows = []
    for trace_id, group in splits["dev"] + splits["test"]:
        for prompt, module in judges.items():
            verdict = verdict_for(prompt, group)
            if prompt == "aligned" and trace_id in misses:
                verdict = "fail" if verdict == "pass" else "pass"
            critique = CRITIQUES[group]
            if verdict_for("aligned", group) != verdict:
                critique = WRONG_CRITIQUE[verdict]
            reply = json.dumps({"critique": critique, "verdict": verdict})
            messages = module.messages(judge_case(traces[trace_id]))
            rows.append({"key": llm.key("judge", messages), "reply": reply, "role": "judge"})
    return rows


def main() -> None:
    splits = pick_splits()
    for folder in [STEP / "problem", STEP / "solution", STEP / "wrong" / "lenient-prompt"]:
        write_labels(folder / "abstention_dev.csv", splits["dev"])
    write_labels(HELPERS / "abstention_test.csv", splits["test"])
    paths.write_jsonl(HELPERS / "abstention_replay.jsonl", recorded_rows(splits))
    print("Wrote abstention_dev.csv, abstention_test.csv and abstention_replay.jsonl.")


if __name__ == "__main__":
    main()
