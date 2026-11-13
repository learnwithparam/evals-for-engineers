"""Field checks: compare an abstract with the approved one, one field at a time, in code.

Run on known pairs:  uv run python checks.py --pairs pairs.jsonl
Run on the golden set: uv run python checks.py --golden golden.jsonl
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

# Every abstract field, and the kind of check it needs.
FIELD_TYPES = {
    "monthly_rent": "money",
    "deposit": "money",
    "pet_fee": "money",
    "early_termination_fee": "money",
    "start_date": "date",
    "end_date": "date",
    "renewal_notice_days": "days",
    "late_fee_after_day": "days",
    "renewal_option": "yes_no",
    "pets_allowed": "yes_no",
    "parking": "yes_no",
    "sublet_allowed": "yes_no",
    "unit": "text",
    "tenant": "text",
    "lease_type": "text",
    "utilities_included": "list",
    "late_fee": "late_fee",
    "rent_steps": "rent_steps",
}

MONTHS = [
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]
PROSE_STEP = re.compile(r"(\d+(?:\.\d+)?)\s*%")


# ---------------------------------------------------------------- given: money and dates


def to_cents(value) -> int | None:
    """Money in whole cents.

    A whole number is already cents. Text such as "$2,825.00" is dollars.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{value!r} is not money")
    if isinstance(value, int):
        return value
    digits = str(value).replace("$", "").replace(",", "").strip()
    return round(float(digits) * 100)


def to_date(value) -> date | None:
    """A date from "2026-03-01", "1 March 2026", "March 1, 2026" or "1st day of March, 2026"."""
    if value is None:
        return None
    text = str(value).strip().lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return date.fromisoformat(text)
    words = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text)
    words = re.sub(r"\b(the|day|of)\b|,", " ", words)
    parts = words.split()
    month = next(MONTHS.index(part) + 1 for part in parts if part in MONTHS)
    numbers = [int(part) for part in parts if part.isdigit()]
    day_of_month = min(numbers)
    year = max(numbers)
    return date(year, month, day_of_month)


# ---------------------------------------------------------------- one check per field type


def check_money(got, want) -> tuple[bool, str]:
    # Compare whole cents, never floats of dollars, so $0.10 + $0.20 is always $0.30.
    got_cents, want_cents = to_cents(got), to_cents(want)
    if got_cents == want_cents:
        return True, f"both are {want_cents} cents"
    return False, f"got {got_cents} cents, the lease says {want_cents} cents"


def check_date(got, want) -> tuple[bool, str]:
    got_date, want_date = to_date(got), to_date(want)
    if got_date == want_date:
        return True, f"both are {want_date}"
    return False, f"got {got_date}, the lease says {want_date}"


def to_days(value) -> int | None:
    # "60 days" and 60 are the same count of days. No value means the lease has no such term.
    if value is None:
        return None
    return int(re.sub(r"\D", "", str(value)))


def check_days(got, want) -> tuple[bool, str]:
    got_days, want_days = to_days(got), to_days(want)
    if got_days == want_days:
        return True, f"both are {want_days} days"
    return False, f"got {got_days} days, the lease says {want_days} days"


def to_yes_no(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("yes", "true", "y")


def check_yes_no(got, want) -> tuple[bool, str]:
    if to_yes_no(got) == to_yes_no(want):
        return True, "both say the same"
    return False, f"got {got}, the lease says {want}"


def check_text(got, want) -> tuple[bool, str]:
    # Case and extra spaces do not change a name.
    got_text = " ".join(str(got).lower().split())
    want_text = " ".join(str(want).lower().split())
    if got_text == want_text:
        return True, "same text"
    return False, f"got {got!r}, the lease says {want!r}"


def check_list(got, want) -> tuple[bool, str]:
    if sorted(got or []) == sorted(want or []):
        return True, "same items"
    return False, f"got {sorted(got or [])}, the lease says {sorted(want or [])}"


def check_late_fee(got, want) -> tuple[bool, str]:
    if not isinstance(got, dict):
        return False, f"got {got!r}, the lease says {want}"
    if got.get("kind") == want["kind"] and got.get("value") == want["value"]:
        return True, "same late fee"
    return False, f"got {got}, the lease says {want}"


# ---------------------------------------------------------------- rent steps


def anniversary(start: date, years: int) -> date:
    return start.replace(year=start.year + years)


def expand_prose_steps(text: str, lease: dict) -> list[dict]:
    """Turn "the rent shall increase by 4% on each anniversary" into dated steps.

    Each anniversary inside the term gets a step, rounded to the nearest cent.
    """
    percent = float(PROSE_STEP.search(text).group(1))
    start = to_date(lease["start_date"])
    end = to_date(lease["end_date"])
    rent = to_cents(lease["monthly_rent"])
    steps = []
    years = 1
    while anniversary(start, years) <= end:
        rent = round(rent * (100 + percent) / 100)
        effective = anniversary(start, years).isoformat()
        steps.append({"effective": effective, "monthly_rent": rent})
        years += 1
    return steps


def as_steps(value, lease: dict) -> list[tuple[str, int]]:
    """Rent steps as sorted (date, cents) pairs, so their order and format do not matter."""
    if isinstance(value, str):
        value = expand_prose_steps(value, lease)
    pairs = []
    for step in value or []:
        effective = to_date(step["effective"]).isoformat()
        pairs.append((effective, to_cents(step["monthly_rent"])))
    return sorted(pairs)


def check_rent_steps(got, want, lease: dict) -> tuple[bool, str]:
    got_steps, want_steps = as_steps(got, lease), as_steps(want, lease)
    if got_steps == want_steps:
        return True, f"same {len(want_steps)} step(s)"
    return False, f"got {len(got_steps)} step(s), the lease has {len(want_steps)}: {want_steps}"


# ---------------------------------------------------------------- run the checks

CHECKS = {
    "money": check_money,
    "date": check_date,
    "days": check_days,
    "yes_no": check_yes_no,
    "text": check_text,
    "list": check_list,
    "late_fee": check_late_fee,
}


def check_field(field: str, got, want, lease: dict) -> tuple[bool, str]:
    field_type = FIELD_TYPES[field]
    if field_type == "rent_steps":
        return check_rent_steps(got, want, lease)
    return CHECKS[field_type](got, want)


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def run_pairs(pairs_path: Path) -> None:
    """One verdict per known pair, as a line of JSON."""
    for pair in read_jsonl(pairs_path):
        lease = pair.get("lease", {})
        ok, reason = check_field(pair["field"], pair["got"], pair["want"], lease)
        verdict = "pass" if ok else "fail"
        print(json.dumps({"id": pair["id"], "verdict": verdict, "reason": reason}))


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def field_accuracy(golden: list[dict], written: dict[str, dict]) -> dict[str, float]:
    """For each field, the share of golden leases where the abstractor wrote the right value."""
    right = {field: 0 for field in FIELD_TYPES}
    for record in golden:
        approved = record["abstract"]
        abstract = written[record["lease_id"]]
        for field in FIELD_TYPES:
            ok, _reason = check_field(field, abstract.get(field), approved[field], approved)
            right[field] += ok
    return {field: right[field] / len(golden) for field in FIELD_TYPES}


def print_table(accuracy: dict[str, float], critical: list[str], overall: float) -> None:
    print(f"{'field':<24} {'right':>7}  critical")
    for field, share in sorted(accuracy.items(), key=lambda item: item[1]):
        mark = "yes" if field in critical else ""
        print(f"{field:<24} {share * 100:>6.1f}%  {mark}")
    print(f"{'all fields':<24} {overall * 100:>6.1f}%")


def run_golden(golden_path: Path, out_path: Path) -> None:
    golden = read_jsonl(golden_path)
    record_rows = read_jsonl(find_repo_root() / "world/data/system_of_record.jsonl")
    written = {row["lease_id"]: row["abstract"] for row in record_rows}
    accuracy = field_accuracy(golden, written)
    overall = sum(accuracy.values()) / len(accuracy)
    critical = golden[0]["critical_fields"]
    print_table(accuracy, critical, overall)
    report = {"leases": len(golden), "overall": overall, "fields": accuracy}
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote {out_path.name}: {len(golden)} golden leases")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, help="known pairs to check, one JSON per line")
    parser.add_argument("--golden", type=Path, help="the golden set to score the abstractor on")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "accuracy.json")
    options = parser.parse_args()
    if options.pairs:
        run_pairs(options.pairs)
    elif options.golden:
        run_golden(options.golden, options.out)
    else:
        parser.error("give --pairs or --golden")


if __name__ == "__main__":
    main()
