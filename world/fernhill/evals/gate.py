"""The release gate: block a release that breaks a critical case, never average it away. Fails closed."""

import json
import sys
from collections import defaultdict

from .. import leases, paths
from . import fields

SHARE = 2  # a case passes when it is right in at least 2 of its 3 trials


def load(release: str) -> list[dict]:
    p = paths.RELEASES / f"{release}.jsonl"
    if not p.exists():
        raise FileNotFoundError(f"no release called {release!r} in world/data/releases")
    return paths.read_jsonl(p)


def case_results(release: str):
    keys = leases.keys()
    split = json.loads((paths.DATA / "splits.json").read_text())
    gate_ids = set(split["gate"])
    qs = {q["id"]: q for q in paths.read_jsonl(paths.DATA / "questions.jsonl")}
    crit = defaultdict(lambda: defaultdict(int))  # lease -> field -> trials right
    trials = defaultdict(int)
    right = total = 0
    abst = defaultdict(int)
    abst_trials = defaultdict(int)
    for row in load(release):
        if row["kind"] == "abstract" and row["lease_id"] in gate_ids:
            s = fields.score(row["output"], keys[row["lease_id"]])
            trials[row["lease_id"]] += 1
            for f in leases.CRITICAL:
                crit[row["lease_id"]][f] += s[f]
            if row["trial"] == 1:
                right += sum(s.values())
                total += len(s)
        if row["kind"] == "desk" and not qs[row["question_id"]]["answerable"]:
            abst_trials[row["question_id"]] += 1
            abst[row["question_id"]] += row["output"]["answer"].strip() == "The lease does not say."
    missing = sorted(gate_ids - set(trials)) + sorted(x for x, n in trials.items() if n < 3)
    cases = {}
    for lid in sorted(gate_ids):
        cases[lid] = {f: crit[lid][f] >= SHARE for f in leases.CRITICAL}
    abstains = {q: abst[q] >= SHARE for q in abst_trials}
    return {
        "cases": cases,
        "abstains": abstains,
        "accuracy": right / total if total else 0.0,
        "missing": missing,
    }


def gate(release: str, baseline: str = "live") -> dict:
    try:
        cand, base = case_results(release), case_results(baseline)
    except Exception as e:
        return {"verdict": "block", "reasons": [f"could not score the release: {e}"], "cases": []}
    reasons = []
    if cand["missing"]:
        reasons.append(f"missing results for {len(cand['missing'])} case(s); a missing case blocks")
    meta = {m["id"]: m for m in leases.leases()}
    broke = defaultdict(list)
    for lid, fs in cand["cases"].items():
        for f, ok in fs.items():
            if base["cases"][lid][f] and not ok:
                broke[f].append(lid)
    for f in leases.CRITICAL:
        ids = broke.get(f)
        if not ids:
            continue
        am = [x for x in ids if meta[x]["amendments"]]
        noun = "lease" if len(ids) == 1 else "leases"
        where = f"{len(ids)} amended {noun}" if len(am) == len(ids) else f"{len(ids)} {noun}"
        reasons.append(
            f"{f.replace('_', ' ').replace('monthly ', '')} newly wrong on {where} (critical)"
        )
    lost = [q for q, ok in cand["abstains"].items() if base["abstains"].get(q) and not ok]
    if lost:
        reasons.append(
            f"stops saying 'The lease does not say.' on {len(lost)} unanswerable question(s) (critical)"
        )
    return {
        "verdict": "block" if reasons else "ship",
        "reasons": reasons,
        "accuracy": cand["accuracy"],
        "baseline_accuracy": base["accuracy"],
        "cases": [{"lease_id": k, **v} for k, v in cand["cases"].items()],
    }


def average_gate(release: str, baseline: str = "live", max_drop: float = 0.02) -> dict:
    cand, base = case_results(release), case_results(baseline)
    drop = base["accuracy"] - cand["accuracy"]
    return {"verdict": "block" if drop > max_drop else "ship", "drop": drop}


def main(args: list[str]) -> int:
    rel = args[args.index("--release") + 1] if "--release" in args else "live"
    if "--average-only" in args:
        r = average_gate(rel)
        print(
            f"Average gate on {rel}: {'PASS' if r['verdict'] == 'ship' else 'BLOCKED'} "
            f"(field accuracy drops {r['drop'] * 100:.1f} points; the limit is 2.0)"
        )
        return 0 if r["verdict"] == "ship" else 1
    r = gate(rel)
    if r["verdict"] == "ship":
        print(f"Gate on {rel}: SHIP. No critical case regressed against live.")
        return 0
    print(f"Gate on {rel}: BLOCKED")
    for x in r["reasons"]:
        print(f"  - {x}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
