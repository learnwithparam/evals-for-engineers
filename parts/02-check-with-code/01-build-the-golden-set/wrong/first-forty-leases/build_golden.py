"""Build the golden set: 40 lease abstracts that Dana has approved as correct.

Run: uv run python build_golden.py
"""

import argparse
import json
from pathlib import Path

# These fields cost money or a missed deadline when they are wrong, so a wrong one blocks a release.
CRITICAL_FIELDS = ["monthly_rent", "rent_steps", "deposit", "renewal_notice_days"]


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def golden_records(data_folder: Path) -> list[dict]:
    # The answer keys come from the signed leases, so they are the approved abstracts.
    keys = read_jsonl(data_folder / "keys.jsonl")

    # The first 40 leases in the file are quick to take.
    records = []
    for row in keys[:40]:
        record = {
            "lease_id": row["lease_id"],
            "abstract": row["abstract"],
            "critical_fields": CRITICAL_FIELDS,
        }
        records.append(record)
    return records


def main() -> None:
    repo_root = find_repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=Path(__file__).parent / "golden.jsonl")
    options = parser.parse_args()

    records = golden_records(repo_root / "world/data")
    with open(options.out, "w") as golden_file:
        for record in records:
            golden_file.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"Wrote {len(records)} approved abstracts to {options.out}")


if __name__ == "__main__":
    main()
