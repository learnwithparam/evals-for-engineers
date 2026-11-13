"""Search one lease for the clauses that answer a staff question.

Reads one JSON object per line on stdin: {"lease_id": "L100", "query": "...", "k": 5}.
Writes one JSON object per line on stdout: {"clause_ids": [...]}, best clause first.

Run: echo '{"lease_id": "L100", "query": "How much notice to renew?", "k": 5}' |
     uv run python retrieve.py --setting clean-query
"""

import argparse
import json
import re  # noqa: F401  (useful in clean_query())
import sys
from pathlib import Path

from fernhill.systems import retrieval

SETTINGS = ["baseline", "clean-query"]

# Staff ask about a cat or a dog; the lease only ever says "pets".
SAME_MEANING = {"cat": "pets", "cats": "pets", "dog": "pets", "dogs": "pets"}


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def unit_and_building(repo_root: Path) -> dict[str, tuple[str, str]]:
    """The unit and building of each lease. For example L100 -> ("8D", "Juniper Hall")."""
    with open(repo_root / "world/data/leases.jsonl") as leases_file:
        leases = [json.loads(line) for line in leases_file if line.strip()]
    return {lease["id"]: (lease["unit"], lease["building"]) for lease in leases}


def clean_query(query: str, unit: str, building: str) -> str:
    """Return a better query for the clean-query setting.

    TODO: every question names the unit and the building, and so does the Premises clause.
    Take those words out of the query. Then swap words staff use for the word the lease uses,
    with SAME_MEANING. For example "keep a cat" should search for "pets".
    """
    raise NotImplementedError("write clean_query() in retrieve.py")


def search(request: dict, setting: str, places: dict) -> list[str]:
    query = request["query"]
    if setting == "clean-query":
        unit, building = places[request["lease_id"]]
        query = clean_query(query, unit, building)
    found = retrieval.search(request["lease_id"], query, request.get("k", 5))
    return [clause["id"] for clause in found]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--setting", choices=SETTINGS, default="baseline")
    options = parser.parse_args()
    places = unit_and_building(find_repo_root())
    for line in sys.stdin:
        if not line.strip():
            continue
        clause_ids = search(json.loads(line), options.setting, places)
        print(json.dumps({"clause_ids": clause_ids}))


if __name__ == "__main__":
    main()
