"""Cross-check the ledger against the signed leases.

For every lease and every month in the ledger, compare what was charged with what the lease says.

Run: uv run python ledger_check.py
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def charges_by_month(ledger: list[dict]) -> dict:
    """lease id -> month -> kind of charge -> total cents charged that month."""
    charges = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for row in ledger:
        charges[row["lease_id"]][row["month"]][row["kind"]] += row["amount_cents"]
    return charges


def rent_due(lease: dict, approved: dict, month: str) -> int:
    """The rent the signed lease sets for one month, written as "2026-01"."""
    # The rent starts at the rent signed on day one.
    rent = lease["original_rent"]
    # An amendment changes the rent only from its own start date.
    amendment = lease["amendment"]
    if amendment and amendment["effective"][:7] <= month:
        rent = amendment["monthly_rent"]
    # Each rent step replaces the rent from its date on.
    for step in sorted(approved["rent_steps"], key=lambda step: step["effective"]):
        if step["effective"][:7] <= month:
            rent = step["monthly_rent"]
    return rent


def problems_for_lease(lease: dict, approved: dict, months: dict) -> list[dict]:
    problems = []
    for month in sorted(months):
        charged = months[month]
        expected_rent = rent_due(lease, approved, month)
        if "rent" in charged and charged["rent"] != expected_rent:
            problems.append(
                {
                    "lease_id": lease["id"],
                    "month": month,
                    "problem": "rent_not_as_lease",
                    "charged": charged["rent"],
                    "lease_says": expected_rent,
                }
            )
        if "pet_fee" in charged and not approved["pets_allowed"]:
            problems.append(
                {
                    "lease_id": lease["id"],
                    "month": month,
                    "problem": "pet_fee_but_no_pets",
                    "charged": charged["pet_fee"],
                    "lease_says": 0,
                }
            )
    return problems


def find_problems(data_folder: Path) -> list[dict]:
    leases = {lease["id"]: lease for lease in read_jsonl(data_folder / "leases.jsonl")}
    # The system of record holds the abstract of every lease, so read the rent schedule from it.
    written = read_jsonl(data_folder / "system_of_record.jsonl")
    approved_by_lease = {row["lease_id"]: row["abstract"] for row in written}
    charges = charges_by_month(read_jsonl(data_folder / "ledger.jsonl"))
    problems = []
    for lease_id in sorted(charges):
        lease = leases[lease_id]
        approved = approved_by_lease[lease_id]
        problems += problems_for_lease(lease, approved, charges[lease_id])
    return problems


def main() -> None:
    repo_root = find_repo_root()
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=Path(__file__).parent / "ledger_problems.jsonl")
    options = parser.parse_args()

    problems = find_problems(repo_root / "world/data")
    with open(options.out, "w") as problems_file:
        for problem in problems:
            problems_file.write(json.dumps(problem, sort_keys=True) + "\n")

    leases_with_problems = sorted({problem["lease_id"] for problem in problems})
    print(f"Found {len(problems)} problem months on {len(leases_with_problems)} leases:")
    for lease_id in leases_with_problems:
        kinds = sorted(
            {problem["problem"] for problem in problems if problem["lease_id"] == lease_id}
        )
        print(f"  {lease_id}  {', '.join(kinds)}")
    print(f"Wrote {options.out}")


if __name__ == "__main__":
    main()
