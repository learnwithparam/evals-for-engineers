"""TPR, TNR and the corrected pass rate with a bootstrap interval."""
import random


def tpr_tnr(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """pairs of (human, judge). Pass is the positive class."""
    pos = [j for h, j in pairs if h == "pass"]
    neg = [j for h, j in pairs if h == "fail"]
    tpr = sum(j == "pass" for j in pos) / len(pos) if pos else 0.0
    tnr = sum(j == "fail" for j in neg) / len(neg) if neg else 0.0
    return tpr, tnr


def corrected(p_obs: float, tpr: float, tnr: float) -> float:
    """The true pass rate, given what the judge saw and how often it is right on each side."""
    denom = tpr + tnr - 1
    if denom <= 0:
        raise ValueError("TPR + TNR must be above 1; the judge is no better than chance")
    return min(1.0, max(0.0, (p_obs + tnr - 1) / denom))


def bootstrap(test: list[tuple[str, str]], unlabelled: list[str], n: int = 2000, seed: int = 0):
    """95% interval for the corrected rate: resample the labelled test pairs and the unlabelled verdicts."""
    r = random.Random(seed)
    vals = []
    for _ in range(n):
        t = [r.choice(test) for _ in test]
        u = [r.choice(unlabelled) for _ in unlabelled]
        tpr, tnr = tpr_tnr(t)
        if tpr + tnr - 1 <= 0:
            continue
        vals.append(corrected(sum(v == "pass" for v in u) / len(u), tpr, tnr))
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]
