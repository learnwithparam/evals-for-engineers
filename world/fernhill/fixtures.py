"""Writes the given files, sample answers and wrong answers for the steps of Find the failures.

Each step starts from the sample answer of the step before it, so a learner can start any step.
Run after `uv run world generate`: uv run python -m fernhill.fixtures
"""

import csv
import io
import json
import subprocess
import sys
from dataclasses import dataclass

from . import leases, paths

PART = paths.ROOT / "parts" / "01-find-the-failures"
STEP_NAMES = [
    "sample-the-traces",
    "mark-the-traces",
    "note-the-failures",
    "name-the-failure-modes",
    "count-the-failures",
]
STEPS = {name: PART / f"{number:02d}-{name}" for number, name in enumerate(STEP_NAMES, 1)}
HEADS = ["problem", "solution"]

# The diagnoses a learner should NOT write: a note says what is wrong, not how to fix it.
DIAGNOSES = {
    "amended-rent-missed": "The prompt should tell the model to read amendments.",
    "rent-step-dropped": "Fix the parser so it handles percentages.",
    "notice-days-wrong-clause": "The model needs to look at the renewal clause instead.",
    "utilities-incomplete": "Add a utilities example to the prompt.",
    "late-fee-percent-as-dollars": "The schema should have a percent type.",
    "deposit-includes-pet-deposit": "Change the prompt to split the deposits.",
}

# Vague mode names that hide what actually went wrong, for the generic-modes wrong answer.
GENERIC_MODES = {
    "hallucination": ["amended-rent-missed", "notice-days-wrong-clause"],
    "inaccuracy": ["rent-step-dropped", "deposit-includes-pet-deposit"],
    "formatting": ["utilities-incomplete", "late-fee-percent-as-dollars"],
}

# What the team does about each mode once it is counted.
DECISIONS = {
    "amended-rent-missed": "code check",
    "rent-step-dropped": "code check",
    "notice-days-wrong-clause": "code check",
    "utilities-incomplete": "fix the prompt",
    "late-fee-percent-as-dollars": "fix the prompt",
    "deposit-includes-pet-deposit": "fix the prompt",
}

EMPTY_RATES = '{\n  "n": 0,\n  "top_mode": "",\n  "modes": {}\n}\n'


@dataclass
class Sample:
    """The sampled traces and Dana's labels for them, which every step builds on."""

    text: str
    trace_ids: list[str]
    traces_by_id: dict[str, dict]
    verdicts: dict[str, str]
    modes: dict[str, list[str]]
    failed_ids: list[str]
    mode_definitions: dict[str, str]
    seen_modes: list[str]


def folders(step: str, wrongs: list[str]) -> list:
    heads = [STEPS[step] / head for head in HEADS]
    wrong_folders = [STEPS[step] / "wrong" / wrong for wrong in wrongs]
    return heads + wrong_folders


def put(dirs, name: str, text: str) -> None:
    for folder in dirs:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)


def put_in(step: str, head: str, name: str, text: str) -> None:
    """Writes one file into one folder of a step, such as its solution or one wrong answer."""
    put([STEPS[step] / head], name, text)


def csv_text(header: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def usd(cents):
    return f"${cents / 100:,.2f}"


def note_for(mode: str, trace: dict, key: dict, meta: dict) -> str:
    output = trace["output"]
    if mode == "amended-rent-missed":
        amendment = meta["amendment"]
        return (
            f"Rent in the abstract is {usd(output['monthly_rent'])}, "
            f"the amount before the amendment; "
            f"Amendment No. 1 sets it to {usd(amendment['monthly_rent'])}."
        )
    if mode == "rent-step-dropped":
        return (
            f"The lease raises the rent by {meta['step_pct']}% on each anniversary, "
            f"but the abstract lists no rent steps at all."
        )
    if mode == "notice-days-wrong-clause":
        return (
            f"Renewal notice days read {output['renewal_notice_days']}, "
            f"but the renewal clause says not less "
            f"than {key['renewal_notice_days']} days."
        )
    if mode == "utilities-incomplete":
        missing = sorted(set(key["utilities_included"]) - set(output["utilities_included"]))
        return (
            f"The abstract leaves out {', '.join(missing)}, "
            f"which the lease says the landlord pays for."
        )
    if mode == "late-fee-percent-as-dollars":
        return (
            f"Late fee is recorded as a flat {usd(output['late_fee']['value'])}, "
            f"while the lease charges "
            f"{key['late_fee']['value']}% of the overdue amount."
        )
    if mode == "deposit-includes-pet-deposit":
        return (
            f"Deposit shows {usd(output['deposit'])}, "
            f"which adds the {usd(meta['pet_deposit'])} pet deposit to "
            f"the {usd(key['deposit'])} security deposit."
        )
    raise ValueError(mode)


def run_sampler() -> str:
    """Runs the sample answer of the first step, so later steps start from its exact output."""
    sampler = STEPS["sample-the-traces"] / "solution" / "sample.py"
    sample_file = paths.ROOT / "world" / "runs" / "fixture-sample.jsonl"
    sample_file.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(sampler), "--seed", "7", "--out", str(sample_file)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return sample_file.read_text()


def read_dana_labels() -> dict[str, dict]:
    with open(paths.LABELS / "abstractor.csv") as labels_file:
        rows = list(csv.DictReader(labels_file))
    return {row["trace_id"]: row for row in rows}


def load_sample() -> Sample:
    text = run_sampler()
    traces = [json.loads(line) for line in text.splitlines() if line.strip()]
    trace_ids = [trace["trace_id"] for trace in traces]
    dana = read_dana_labels()
    mode_definitions = json.loads((paths.LABELS / "abstractor_modes.json").read_text())
    modes = {}
    for trace_id in trace_ids:
        modes[trace_id] = [mode for mode in mode_definitions if dana[trace_id][mode] == "1"]
    verdicts = {trace_id: dana[trace_id]["verdict"] for trace_id in trace_ids}
    seen_modes = [
        mode for mode in mode_definitions if any(mode in modes[trace_id] for trace_id in trace_ids)
    ]
    return Sample(
        text=text,
        trace_ids=trace_ids,
        traces_by_id={trace["trace_id"]: trace for trace in traces},
        verdicts=verdicts,
        modes=modes,
        failed_ids=[trace_id for trace_id in trace_ids if verdicts[trace_id] == "fail"],
        mode_definitions=mode_definitions,
        seen_modes=seen_modes,
    )


def marks_csv(trace_ids: list[str], marks: dict[str, str]) -> str:
    rows = [[trace_id, marks[trace_id]] for trace_id in trace_ids]
    return csv_text(["trace_id", "mark"], rows)


def write_marks(sample: Sample) -> str:
    """Step 2. Returns the full marks, which later steps are given."""
    step = "mark-the-traces"
    put(folders(step, ["all-pass", "all-fail"]), "sample.jsonl", sample.text)
    marks_full = marks_csv(sample.trace_ids, sample.verdicts)
    put_in(step, "problem", "marks.csv", "trace_id,mark\n")
    put_in(step, "solution", "marks.csv", marks_full)
    all_pass = dict.fromkeys(sample.trace_ids, "pass")
    all_fail = dict.fromkeys(sample.trace_ids, "fail")
    put_in(step, "wrong/all-pass", "marks.csv", marks_csv(sample.trace_ids, all_pass))
    put_in(step, "wrong/all-fail", "marks.csv", marks_csv(sample.trace_ids, all_fail))
    return marks_full


def full_notes(sample: Sample) -> dict[str, str]:
    """One note per failed trace: a sentence for each failure mode Dana marked on it."""
    keys = leases.keys()
    metas = {meta["id"]: meta for meta in leases.leases()}
    notes = {}
    for trace_id in sample.failed_ids:
        trace = sample.traces_by_id[trace_id]
        lease_id = trace["lease_id"]
        sentences = [
            note_for(mode, trace, keys[lease_id], metas[lease_id])
            for mode in sample.modes[trace_id]
        ]
        notes[trace_id] = " ".join(sentences)
    return notes


def notes_csv(failed_ids: list[str], notes: dict[str, str]) -> str:
    rows = [[trace_id, notes[trace_id]] for trace_id in failed_ids]
    return csv_text(["trace_id", "note"], rows)


def write_notes(sample: Sample, marks_full: str) -> str:
    """Step 3. Returns the full notes, which later steps are given."""
    step = "note-the-failures"
    every_folder = folders(step, ["short-notes", "diagnoses-the-cause"])
    put(every_folder, "sample.jsonl", sample.text)
    put(every_folder, "marks.csv", marks_full)
    notes_full = notes_csv(sample.failed_ids, full_notes(sample))
    put_in(step, "problem", "notes.csv", "trace_id,note\n")
    put_in(step, "solution", "notes.csv", notes_full)
    short_notes = dict.fromkeys(sample.failed_ids, "wrong field")
    put_in(step, "wrong/short-notes", "notes.csv", notes_csv(sample.failed_ids, short_notes))
    diagnoses = {}
    for trace_id in sample.failed_ids:
        first_mode = sample.modes[trace_id][0]
        diagnoses[trace_id] = DIAGNOSES[first_mode]
    diagnoses_text = notes_csv(sample.failed_ids, diagnoses)
    put_in(step, "wrong/diagnoses-the-cause", "notes.csv", diagnoses_text)
    return notes_full


def mode_block(name: str, definition: str, examples: list[str]) -> list[str]:
    """The three YAML lines that describe one failure mode."""
    return [
        f"  - name: {name}",
        f"    definition: {definition}",
        f"    examples: [{', '.join(examples)}]",
    ]


def yaml_text(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def solution_modes_yaml(sample: Sample) -> str:
    lines = ["modes:"]
    for mode in sample.seen_modes:
        traces_with_mode = [
            trace_id for trace_id in sample.trace_ids if mode in sample.modes[trace_id]
        ]
        definition = sample.mode_definitions[mode]
        lines += mode_block(mode, definition, traces_with_mode[:3])
    return yaml_text(lines)


def solution_labels_csv(sample: Sample) -> str:
    rows = []
    for trace_id in sample.trace_ids:
        flags = [int(mode in sample.modes[trace_id]) for mode in sample.seen_modes]
        rows.append([trace_id, *flags])
    return csv_text(["trace_id", *sample.seen_modes], rows)


def has_any_mode(sample: Sample, trace_id: str, modes: list[str]) -> bool:
    return bool(set(modes) & set(sample.modes[trace_id]))


def write_generic_modes(sample: Sample) -> None:
    """The wrong answer that names modes too broadly to act on."""
    lines = ["modes:"]
    for generic_name, modes in GENERIC_MODES.items():
        examples = [
            trace_id for trace_id in sample.trace_ids if has_any_mode(sample, trace_id, modes)
        ]
        definition = f"The abstract has a {generic_name} problem."
        lines += mode_block(generic_name, definition, examples[:2])
    other_definition = "Any other problem with the abstract."
    lines += mode_block("other", other_definition, [sample.failed_ids[0]])
    rows = []
    for trace_id in sample.trace_ids:
        flags = [int(has_any_mode(sample, trace_id, modes)) for modes in GENERIC_MODES.values()]
        rows.append([trace_id, *flags, 0])
    labels = csv_text(["trace_id", *GENERIC_MODES, "other"], rows)
    folder = "wrong/generic-modes"
    put_in("name-the-failure-modes", folder, "failure_modes.yaml", yaml_text(lines))
    put_in("name-the-failure-modes", folder, "labels.csv", labels)


def write_one_mode_per_trace(sample: Sample) -> None:
    """The wrong answer that gives every failed trace a mode of its own."""
    lines = ["modes:"]
    for trace_id in sample.failed_ids:
        definition = f"What went wrong in trace {trace_id}."
        lines += mode_block(f"problem-in-{trace_id}", definition, [trace_id])
    header = ["trace_id"] + [f"problem-in-{trace_id}" for trace_id in sample.failed_ids]
    rows = []
    for trace_id in sample.trace_ids:
        flags = [int(trace_id == failed_id) for failed_id in sample.failed_ids]
        rows.append([trace_id, *flags])
    folder = "wrong/one-mode-per-trace"
    put_in("name-the-failure-modes", folder, "failure_modes.yaml", yaml_text(lines))
    put_in("name-the-failure-modes", folder, "labels.csv", csv_text(header, rows))


def write_failure_modes(sample: Sample, earlier_files: dict[str, str]) -> tuple[str, str]:
    """Step 4. Returns the solution's modes YAML and labels CSV, which step 5 is given."""
    step = "name-the-failure-modes"
    every_folder = folders(step, ["generic-modes", "one-mode-per-trace"])
    for name, text in earlier_files.items():
        put(every_folder, name, text)
    modes_yaml = solution_modes_yaml(sample)
    labels_full = solution_labels_csv(sample)
    put_in(step, "problem", "failure_modes.yaml", STARTER_MODES)
    put_in(step, "problem", "labels.csv", "trace_id\n")
    put_in(step, "solution", "failure_modes.yaml", modes_yaml)
    put_in(step, "solution", "labels.csv", labels_full)
    write_generic_modes(sample)
    write_one_mode_per_trace(sample)
    return modes_yaml, labels_full


def rates(counts: dict[str, int], decisions: dict[str, str], trace_count: int) -> str:
    """The rates.json a learner writes: how often each mode happens, and what to do about it."""
    modes = {}
    for mode, count in counts.items():
        modes[mode] = {
            "count": count,
            "rate": round(count / trace_count, 4),
            "decision": decisions[mode],
        }
    top_mode = max(counts, key=counts.get)
    summary = {"n": trace_count, "top_mode": top_mode, "modes": modes}
    return json.dumps(summary, indent=2) + "\n"


def write_counts(sample: Sample, modes_yaml: str, labels_full: str) -> None:
    """Step 5."""
    step = "count-the-failures"
    every_folder = folders(step, ["counted-by-hand", "everything-a-judge"])
    put(every_folder, "failure_modes.yaml", modes_yaml)
    put(every_folder, "labels.csv", labels_full)
    trace_count = len(sample.trace_ids)
    counts = {}
    for mode in sample.seen_modes:
        counts[mode] = sum(mode in sample.modes[trace_id] for trace_id in sample.trace_ids)
    put_in(step, "problem", "rates.json", EMPTY_RATES)
    put_in(step, "solution", "rates.json", rates(counts, DECISIONS, trace_count))
    # Counting by hand slips: the first mode ends up two over.
    hand_counts = dict(counts)
    first_mode = next(iter(hand_counts))
    hand_counts[first_mode] += 2
    hand_rates = rates(hand_counts, DECISIONS, trace_count)
    put_in(step, "wrong/counted-by-hand", "rates.json", hand_rates)
    all_judges = dict.fromkeys(sample.seen_modes, "judge")
    judge_rates = rates(counts, all_judges, trace_count)
    put_in(step, "wrong/everything-a-judge", "rates.json", judge_rates)


def main() -> None:
    sample = load_sample()
    marks_full = write_marks(sample)
    notes_full = write_notes(sample, marks_full)
    earlier_files = {
        "sample.jsonl": sample.text,
        "marks.csv": marks_full,
        "notes.csv": notes_full,
    }
    modes_yaml, labels_full = write_failure_modes(sample, earlier_files)
    write_counts(sample, modes_yaml, labels_full)
    print(
        f"Wrote fixtures for {len(STEPS) - 1} steps: {len(sample.trace_ids)} traces, "
        f"{len(sample.failed_ids)} fails, {len(sample.seen_modes)} modes."
    )


STARTER_MODES = """\
# Name 4 to 8 failure modes from your notes. One block per mode, like this made-up one:
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
