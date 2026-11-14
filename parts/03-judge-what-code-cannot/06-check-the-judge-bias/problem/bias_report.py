"""Check one judge for position bias and length bias, from runs where the order was swapped.

Each row in judge_runs.jsonl is one pair of answers, judged twice: once in the original order,
once with the two answers swapped. "picked_original" and "picked_swapped" name the answer the
judge chose ("a" or "b"), not the slot it sat in. "longer" names the longer answer.

It writes bias_report.json.

Run: uv run python bias_report.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent

# The judge shows length bias when it picks the longer answer in at least this share of pairs.
LENGTH_BIAS_AT = 0.7

# What you will do about the bias, in one sentence.
FIX = ""  # TODO: one sentence on what you will do about position bias
# What you will do about length bias, in one sentence.
LENGTH_FIX = ""  # TODO: one sentence on what you will do about length bias


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def flipped_pairs(rows: list[dict]) -> list[str]:
    """The pairs where swapping the order changed which answer won.

    TODO: a pair is flipped when "picked_original" and "picked_swapped" differ.
    """
    raise NotImplementedError("write flipped_pairs() in bias_report.py")


def flip_rate(rows: list[dict]) -> float:
    """The share of pairs that flipped, rounded to 3 places."""
    raise NotImplementedError("write flip_rate() in bias_report.py")


def longer_pick_rate(rows: list[dict]) -> float:
    """The share of pairs where "picked_original" equals "longer", rounded to 3 places."""
    raise NotImplementedError("write longer_pick_rate() in bias_report.py")


def length_bias(rate: float) -> str:
    """Return "present" when the longer pick rate is LENGTH_BIAS_AT or more, else "absent"."""
    raise NotImplementedError("write length_bias() in bias_report.py")


def main() -> None:
    rows = read_jsonl(HERE / "judge_runs.jsonl")
    longer_rate = longer_pick_rate(rows)
    report = {
        "flip_rate": flip_rate(rows),
        "longer_pick_rate": longer_rate,
        "length_bias": length_bias(longer_rate),
        "length_fix": LENGTH_FIX,
        "flipped_pairs": flipped_pairs(rows),
        "fix": FIX,
    }
    (HERE / "bias_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Flip rate {report['flip_rate']}: {len(report['flipped_pairs'])} of {len(rows)} pairs.")
    print(f"The judge picked the longer answer in {report['longer_pick_rate']} of pairs.")
    print("Wrote bias_report.json")


if __name__ == "__main__":
    main()
