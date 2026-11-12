"""Writes the given files, sample answers and wrong answers for the steps of Find the failures.

Each step starts from the sample answer of the step before it, so a learner can start any step.
Run after `uv run world generate`: uv run python -m fernhill.fixtures
"""

import csv
import json
import subprocess
import sys

from . import leases, paths

PART = paths.ROOT / "parts" / "01-find-the-failures"
STEPS = {
    n: PART / f"{i:02d}-{n}"
    for i, n in enumerate(
        [
            "sample-the-traces",
            "mark-the-traces",
            "note-the-failures",
            "name-the-failure-modes",
            "count-the-failures",
        ],
        1,
    )
}
HEADS = ["problem", "solution"]


def folders(step: str, wrongs: list[str]) -> list:
    return [STEPS[step] / h for h in HEADS] + [STEPS[step] / "wrong" / w for w in wrongs]


def put(dirs, name: str, text: str) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text)


def csv_text(header: list[str], rows: list[list]) -> str:
    import io

    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def usd(c):
    return f"${c / 100:,.2f}"


def note_for(mode: str, t: dict, key: dict, meta: dict) -> str:
    out = t["output"]
    if mode == "amended-rent-missed":
        a = meta["amendment"]
        return (
            f"Rent in the abstract is {usd(out['monthly_rent'])}, the amount before the amendment; "
            f"Amendment No. 1 sets it to {usd(a['monthly_rent'])}."
        )
    if mode == "rent-step-dropped":
        return (
            f"The lease raises the rent by {meta['step_pct']}% on each anniversary, but the abstract "
            f"lists no rent steps at all."
        )
    if mode == "notice-days-wrong-clause":
        return (
            f"Renewal notice days read {out['renewal_notice_days']}, but the renewal clause says not less "
            f"than {key['renewal_notice_days']} days."
        )
    if mode == "utilities-incomplete":
        missing = sorted(set(key["utilities_included"]) - set(out["utilities_included"]))
        return f"The abstract leaves out {', '.join(missing)}, which the lease says the landlord pays for."
    if mode == "late-fee-percent-as-dollars":
        return (
            f"Late fee is recorded as a flat {usd(out['late_fee']['value'])}, while the lease charges "
            f"{key['late_fee']['value']}% of the overdue amount."
        )
    if mode == "deposit-includes-pet-deposit":
        return (
            f"Deposit shows {usd(out['deposit'])}, which adds the {usd(meta['pet_deposit'])} pet deposit to "
            f"the {usd(key['deposit'])} security deposit."
        )
    raise ValueError(mode)


def main() -> None:
    sampler = STEPS["sample-the-traces"] / "solution" / "sample.py"
    tmp = paths.ROOT / "world" / "runs" / "fixture-sample.jsonl"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(sampler), "--seed", "7", "--out", str(tmp)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    sample_text = tmp.read_text()
    sample = [json.loads(x) for x in sample_text.splitlines() if x.strip()]
    ids = [t["trace_id"] for t in sample]
    dana = {r["trace_id"]: r for r in csv.DictReader(open(paths.LABELS / "abstractor.csv"))}
    all_modes = json.loads((paths.LABELS / "abstractor_modes.json").read_text())
    keys = leases.keys()
    meta = {m["id"]: m for m in leases.leases()}
    verdict = {i: dana[i]["verdict"] for i in ids}
    modes = {i: [m for m in all_modes if dana[i][m] == "1"] for i in ids}
    fails = [i for i in ids if verdict[i] == "fail"]
    by_id = {t["trace_id"]: t for t in sample}

    # mark-the-traces
    w2 = ["all-pass", "all-fail"]
    put(folders("mark-the-traces", w2), "sample.jsonl", sample_text)
    marks_full = csv_text(["trace_id", "mark"], [[i, verdict[i]] for i in ids])
    put([STEPS["mark-the-traces"] / "problem"], "marks.csv", "trace_id,mark\n")
    put([STEPS["mark-the-traces"] / "solution"], "marks.csv", marks_full)
    put(
        [STEPS["mark-the-traces"] / "wrong" / "all-pass"],
        "marks.csv",
        csv_text(["trace_id", "mark"], [[i, "pass"] for i in ids]),
    )
    put(
        [STEPS["mark-the-traces"] / "wrong" / "all-fail"],
        "marks.csv",
        csv_text(["trace_id", "mark"], [[i, "fail"] for i in ids]),
    )

    # note-the-failures
    w3 = ["short-notes", "diagnoses-the-cause"]
    put(folders("note-the-failures", w3), "sample.jsonl", sample_text)
    put(folders("note-the-failures", w3), "marks.csv", marks_full)
    notes = {}
    for i in fails:
        t = by_id[i]
        notes[i] = " ".join(
            note_for(m, t, keys[t["lease_id"]], meta[t["lease_id"]]) for m in modes[i]
        )
    notes_full = csv_text(["trace_id", "note"], [[i, notes[i]] for i in fails])
    put([STEPS["note-the-failures"] / "problem"], "notes.csv", "trace_id,note\n")
    put([STEPS["note-the-failures"] / "solution"], "notes.csv", notes_full)
    put(
        [STEPS["note-the-failures"] / "wrong" / "short-notes"],
        "notes.csv",
        csv_text(["trace_id", "note"], [[i, "wrong field"] for i in fails]),
    )
    diag = {
        "amended-rent-missed": "The prompt should tell the model to read amendments.",
        "rent-step-dropped": "Fix the parser so it handles percentages.",
        "notice-days-wrong-clause": "The model needs to look at the renewal clause instead.",
        "utilities-incomplete": "Add a utilities example to the prompt.",
        "late-fee-percent-as-dollars": "The schema should have a percent type.",
        "deposit-includes-pet-deposit": "Change the prompt to split the deposits.",
    }
    put(
        [STEPS["note-the-failures"] / "wrong" / "diagnoses-the-cause"],
        "notes.csv",
        csv_text(["trace_id", "note"], [[i, diag[modes[i][0]]] for i in fails]),
    )

    # name-the-failure-modes
    w4 = ["generic-modes", "one-mode-per-trace"]
    for name, text in (
        ("sample.jsonl", sample_text),
        ("marks.csv", marks_full),
        ("notes.csv", notes_full),
    ):
        put(folders("name-the-failure-modes", w4), name, text)
    seen = [m for m in all_modes if any(m in modes[i] for i in ids)]
    yaml = ["modes:"]
    for m in seen:
        ex = [i for i in ids if m in modes[i]][:3]
        yaml += [
            f"  - name: {m}",
            f"    definition: {all_modes[m]}",
            f"    examples: [{', '.join(ex)}]",
        ]
    modes_yaml = "\n".join(yaml) + "\n"
    labels_full = csv_text(
        ["trace_id"] + seen, [[i] + [int(m in modes[i]) for m in seen] for i in ids]
    )
    put([STEPS["name-the-failure-modes"] / "problem"], "failure_modes.yaml", STARTER_MODES)
    put([STEPS["name-the-failure-modes"] / "problem"], "labels.csv", "trace_id\n")
    put([STEPS["name-the-failure-modes"] / "solution"], "failure_modes.yaml", modes_yaml)
    put([STEPS["name-the-failure-modes"] / "solution"], "labels.csv", labels_full)
    generic = {
        "hallucination": ["amended-rent-missed", "notice-days-wrong-clause"],
        "inaccuracy": ["rent-step-dropped", "deposit-includes-pet-deposit"],
        "formatting": ["utilities-incomplete", "late-fee-percent-as-dollars"],
    }
    gy = ["modes:"]
    for g, ms in generic.items():
        ex = [i for i in ids if set(ms) & set(modes[i])][:2]
        gy += [
            f"  - name: {g}",
            f"    definition: The abstract has a {g} problem.",
            f"    examples: [{', '.join(ex)}]",
        ]
    gy += [
        "  - name: other",
        "    definition: Any other problem with the abstract.",
        f"    examples: [{fails[0]}]",
    ]
    put(
        [STEPS["name-the-failure-modes"] / "wrong" / "generic-modes"],
        "failure_modes.yaml",
        "\n".join(gy) + "\n",
    )
    gl = [[i] + [int(bool(set(ms) & set(modes[i]))) for ms in generic.values()] + [0] for i in ids]
    put(
        [STEPS["name-the-failure-modes"] / "wrong" / "generic-modes"],
        "labels.csv",
        csv_text(["trace_id", *generic, "other"], gl),
    )
    oy = ["modes:"] + [
        x
        for n, i in enumerate(fails, 1)
        for x in (
            f"  - name: problem-in-{i}",
            f"    definition: What went wrong in trace {i}.",
            f"    examples: [{i}]",
        )
    ]
    put(
        [STEPS["name-the-failure-modes"] / "wrong" / "one-mode-per-trace"],
        "failure_modes.yaml",
        "\n".join(oy) + "\n",
    )
    put(
        [STEPS["name-the-failure-modes"] / "wrong" / "one-mode-per-trace"],
        "labels.csv",
        csv_text(
            ["trace_id"] + [f"problem-in-{i}" for i in fails],
            [[i] + [int(i == f) for f in fails] for i in ids],
        ),
    )

    # count-the-failures
    w5 = ["counted-by-hand", "everything-a-judge"]
    put(folders("count-the-failures", w5), "failure_modes.yaml", modes_yaml)
    put(folders("count-the-failures", w5), "labels.csv", labels_full)
    counts = {m: sum(m in modes[i] for i in ids) for m in seen}
    decision = {
        "amended-rent-missed": "code check",
        "rent-step-dropped": "code check",
        "notice-days-wrong-clause": "code check",
        "utilities-incomplete": "fix the prompt",
        "late-fee-percent-as-dollars": "fix the prompt",
        "deposit-includes-pet-deposit": "fix the prompt",
    }

    def rates(cnt, dec):
        return (
            json.dumps(
                {
                    "n": len(ids),
                    "top_mode": max(cnt, key=cnt.get),
                    "modes": {
                        m: {
                            "count": cnt[m],
                            "rate": round(cnt[m] / len(ids), 4),
                            "decision": dec[m],
                        }
                        for m in seen
                    },
                },
                indent=2,
            )
            + "\n"
        )

    put(
        [STEPS["count-the-failures"] / "problem"],
        "rates.json",
        '{\n  "n": 0,\n  "top_mode": "",\n  "modes": {}\n}\n',
    )
    put([STEPS["count-the-failures"] / "solution"], "rates.json", rates(counts, decision))
    hand = {m: c + (2 if n == 0 else 0) for n, (m, c) in enumerate(counts.items())}
    put(
        [STEPS["count-the-failures"] / "wrong" / "counted-by-hand"],
        "rates.json",
        rates(hand, decision),
    )
    put(
        [STEPS["count-the-failures"] / "wrong" / "everything-a-judge"],
        "rates.json",
        rates(counts, {m: "judge" for m in seen}),
    )
    print(
        f"Wrote fixtures for {len(STEPS) - 1} steps: {len(ids)} traces, {len(fails)} fails, {len(seen)} modes."
    )


STARTER_MODES = """# Name 4 to 8 failure modes from your notes. One block per mode, like this made-up one:
#
#   - name: wrong-tenant-name
#     definition: The abstract names a different tenant from the one who signed the lease.
#     examples: [abs-0000]
#
# name: lower case words joined by dashes. definition: one sentence, 25 words or fewer.
# examples: trace ids you marked fail, whose notes show this mode.
modes: []
"""

if __name__ == "__main__":
    main()
