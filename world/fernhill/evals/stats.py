"""TPR, TNR and the corrected pass rate with a bootstrap interval."""

import random


def tpr_tnr(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """pairs of (human, judge). Pass is the positive class."""
    judge_on_human_passes = [judge for human, judge in pairs if human == "pass"]
    judge_on_human_fails = [judge for human, judge in pairs if human == "fail"]
    tpr = 0.0
    if judge_on_human_passes:
        agreed = sum(judge == "pass" for judge in judge_on_human_passes)
        tpr = agreed / len(judge_on_human_passes)
    tnr = 0.0
    if judge_on_human_fails:
        agreed = sum(judge == "fail" for judge in judge_on_human_fails)
        tnr = agreed / len(judge_on_human_fails)
    return tpr, tnr


def corrected(observed_pass_rate: float, tpr: float, tnr: float) -> float:
    """The true pass rate, given what the judge saw and how often it is right on each side."""
    denominator = tpr + tnr - 1
    if denominator <= 0:
        raise ValueError("TPR + TNR must be above 1; the judge is no better than chance")
    return min(1.0, max(0.0, (observed_pass_rate + tnr - 1) / denominator))


def bootstrap(
    test: list[tuple[str, str]], unlabelled: list[str], rounds: int = 2000, seed: int = 0
):
    """95% interval for the corrected rate.

    Each round resamples the labelled test pairs and the unlabelled verdicts, with replacement.
    """
    generator = random.Random(seed)
    rates = []
    for _ in range(rounds):
        test_sample = [generator.choice(test) for _ in test]
        unlabelled_sample = [generator.choice(unlabelled) for _ in unlabelled]
        tpr, tnr = tpr_tnr(test_sample)
        if tpr + tnr - 1 <= 0:
            continue
        passes = sum(verdict == "pass" for verdict in unlabelled_sample)
        rates.append(corrected(passes / len(unlabelled_sample), tpr, tnr))
    rates.sort()
    return rates[int(0.025 * len(rates))], rates[int(0.975 * len(rates)) - 1]
