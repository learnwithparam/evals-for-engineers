"""Report the grounded rate of each production batch, corrected for the judge's errors.

It reads verdicts.jsonl from sample-production-traces and judge_test.csv, the judge's
verdicts on Dana's 50 held-out labels. It writes batches.csv: one row per batch for all
traces, and one more row for the traces on a template the golden set lacks.

Run: uv run python report.py
"""

import csv
import json
from pathlib import Path

from fernhill.evals import stats  # noqa: F401  (you call it in rate_row())

# Dana's rule: below this corrected rate on a template CI cannot test, someone must look.
ALERT_FLOOR = 0.75
COLUMNS = ["batch", "slice", "n", "raw_rate", "corrected_rate", "ci_low", "ci_high", "alert"]
HERE = Path(__file__).parent


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def new_templates(repo_root: Path) -> set[str]:
    """The templates that no lease in the golden set uses. For example FH-RES-2026."""
    all_leases = read_jsonl(repo_root / "world/data/leases.jsonl")
    template_of = {lease["id"]: lease["template"] for lease in all_leases}
    splits = json.loads((repo_root / "world/data/splits.json").read_text())
    covered = {template_of[lease_id] for lease_id in splits["golden"]}
    return set(template_of.values()) - covered


def read_test_pairs(path: Path) -> list[tuple[str, str]]:
    """(Dana's label, the judge's verdict) for each held-out test trace."""
    with open(path) as test_file:
        return [(row["label"], row["verdict"]) for row in csv.DictReader(test_file)]


def rate_row(batch: int, slice_name: str, verdicts: list[str], test_pairs: list) -> dict:
    """One row of batches.csv for one group of verdicts.

    TODO: work out raw_rate, the share of "pass" in verdicts.
    Then correct it with stats.tpr_tnr(test_pairs) and stats.corrected(raw_rate, tpr, tnr).
    Get the 95% interval from stats.bootstrap(test_pairs, verdicts).
    Return a dict with every name in COLUMNS except "alert", rounded to 3 places.
    """
    raise NotImplementedError("write rate_row() in report.py")


def should_alert(row: dict) -> bool:
    """TODO: True on a new-template row whose corrected rate is below ALERT_FLOOR."""
    raise NotImplementedError("write should_alert() in report.py")


def batch_rows(rows: list[dict], unseen: set[str], test_pairs: list) -> list[dict]:
    report_rows = []
    for batch in sorted({row["batch"] for row in rows}):
        in_batch = [row for row in rows if row["batch"] == batch]
        all_verdicts = [row["verdict"] for row in in_batch]
        report_rows.append(rate_row(batch, "all", all_verdicts, test_pairs))
        new_verdicts = [row["verdict"] for row in in_batch if row["template"] in unseen]
        if new_verdicts:
            report_rows.append(rate_row(batch, "new-template", new_verdicts, test_pairs))
    for row in report_rows:
        row["alert"] = "yes" if should_alert(row) else "no"
    return report_rows


def print_table(report_rows: list[dict]) -> None:
    first_columns = f"{'batch':<6} {'slice':<13} {'n':<3} {'raw':<4}"
    print(f"{first_columns}  {'corrected':<25} {'95% interval':<12}  alert")
    for row in report_rows:
        bar = "#" * round(row["corrected_rate"] * 20)
        interval = f"{row['ci_low']:.2f} to {row['ci_high']:.2f}"
        alert = "ALERT" if row["alert"] == "yes" else ""
        print(
            f"{row['batch']:<6} {row['slice']:<13} {row['n']:<3} {row['raw_rate']:.2f}  "
            f"{row['corrected_rate']:.2f} {bar:<20} {interval}  {alert}"
        )


def main() -> None:
    repo_root = find_repo_root()
    rows = read_jsonl(HERE / "verdicts.jsonl")
    test_pairs = read_test_pairs(HERE / "judge_test.csv")
    report_rows = batch_rows(rows, new_templates(repo_root), test_pairs)
    with open(HERE / "batches.csv", "w", newline="") as batches_file:
        writer = csv.DictWriter(batches_file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(report_rows)
    print_table(report_rows)
    print(f"Wrote {len(report_rows)} rows to batches.csv")


if __name__ == "__main__":
    main()
