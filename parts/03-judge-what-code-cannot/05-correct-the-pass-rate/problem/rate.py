"""Judge the 200 unlabelled lease desk answers, correct the pass rate, write grounded_rate.json.

Run: uv run python rate.py
The judge makes known mistakes: its TPR and TNR from judge_test.json. The corrected rate is
the share of answers that are really grounded, once those mistakes are taken out.
"""

import json
import random

from cases import cases, dana_labels
from run import judge_all

ROUNDS = 2000


def corrected(raw_rate: float, tpr: float, tnr: float) -> float:
    """The true pass rate: (raw + TNR - 1) / (TPR + TNR - 1), kept between 0 and 1."""
    # TODO: raise a ValueError when TPR + TNR - 1 is 0 or less: the judge is no better than chance.
    # TODO: compute (raw_rate + tnr - 1) / (tpr + tnr - 1).
    # TODO: clip it, so it is never below 0.0 or above 1.0.
    raise NotImplementedError("corrected() is still the starter")


def tpr_tnr(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """pairs are (Dana's label, the judge's verdict). Pass is the positive class."""
    judge_on_dana_passes = [verdict for label, verdict in pairs if label == "pass"]
    judge_on_dana_fails = [verdict for label, verdict in pairs if label == "fail"]
    tpr = judge_on_dana_passes.count("pass") / max(1, len(judge_on_dana_passes))
    tnr = judge_on_dana_fails.count("fail") / max(1, len(judge_on_dana_fails))
    return tpr, tnr


def bootstrap(test_pairs: list, verdicts: list[str], seed: int = 0) -> tuple[float, float]:
    """A 95% interval: resample the test pairs and the verdicts many times, and correct each."""
    draws = random.Random(seed)
    estimates = []
    for _ in range(ROUNDS):
        pairs_sample = [draws.choice(test_pairs) for _ in test_pairs]
        verdicts_sample = [draws.choice(verdicts) for _ in verdicts]
        tpr, tnr = tpr_tnr(pairs_sample)
        if tpr + tnr <= 1:
            continue
        raw_rate = verdicts_sample.count("pass") / len(verdicts_sample)
        estimates.append(corrected(raw_rate, tpr, tnr))
    estimates.sort()
    low = estimates[int(0.025 * len(estimates))]
    high = estimates[int(0.975 * len(estimates)) - 1]
    return low, high


with open("judge_test.json") as test_file:
    test_run = json.load(test_file)
labels = dana_labels()
saved_verdicts = test_run["verdicts"].items()
test_pairs = [(labels[trace_id]["label"], verdict) for trace_id, verdict in saved_verdicts]

verdicts = [verdict["verdict"] for verdict in judge_all(cases("unlabelled"))]
raw_rate = verdicts.count("pass") / len(verdicts)
estimate = corrected(raw_rate, test_run["tpr"], test_run["tnr"])
low, high = bootstrap(test_pairs, verdicts)

result = {
    "n": len(verdicts),
    "raw_rate": round(raw_rate, 4),
    "tpr": test_run["tpr"],
    "tnr": test_run["tnr"],
    "corrected": round(estimate, 4),
    "ci_low": round(min(low, estimate), 4),
    "ci_high": round(max(high, estimate), 4),
}
with open("grounded_rate.json", "w") as result_file:
    json.dump(result, result_file, indent=2)

print(f"Judge passes {verdicts.count('pass')} of {len(verdicts)} answers: raw rate {raw_rate:.0%}")
print(f"Corrected with TPR {result['tpr']:.2f} and TNR {result['tnr']:.2f}: {estimate:.0%}")
print(f"95% interval: {result['ci_low']:.0%} to {result['ci_high']:.0%}")
print("Wrote grounded_rate.json")
