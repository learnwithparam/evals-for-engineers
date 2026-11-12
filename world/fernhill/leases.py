"""Lease documents: read a lease file and split it into clauses with stable ids."""

import json
import re

from . import paths

# A clause heading looks like "## c04 Rent": a short clause number, then the heading.
CLAUSE_HEADING = re.compile(r"^## ([a-z]\d\d) (.+)$")

FIELDS = [
    "unit",
    "tenant",
    "lease_type",
    "start_date",
    "end_date",
    "monthly_rent",
    "rent_steps",
    "deposit",
    "renewal_option",
    "renewal_notice_days",
    "pets_allowed",
    "pet_fee",
    "late_fee",
    "late_fee_after_day",
    "early_termination_fee",
    "utilities_included",
    "parking",
    "sublet_allowed",
]
CRITICAL = ["monthly_rent", "rent_steps", "deposit", "renewal_notice_days"]


def text(lease_id: str) -> str:
    return (paths.LEASES / f"{lease_id}.md").read_text()


def clauses(lease_id: str) -> list[dict]:
    """[{id: 'L014-c04', heading: 'Rent', text: '...'}] in document order."""
    found, current = [], None
    for line in text(lease_id).splitlines():
        heading = CLAUSE_HEADING.match(line)
        if heading:
            clause_id = f"{lease_id}-{heading.group(1)}"
            current = {"id": clause_id, "heading": heading.group(2), "lines": []}
            found.append(current)
        elif current is not None and line.strip():
            current["lines"].append(line.strip())
    return [
        {"id": clause["id"], "heading": clause["heading"], "text": " ".join(clause["lines"])}
        for clause in found
    ]


def keys() -> dict[str, dict]:
    """The answer key per lease, written by the generator, never by a model."""
    rows = paths.read_jsonl(paths.DATA / "keys.jsonl")
    return {row["lease_id"]: row["abstract"] for row in rows}


def leases() -> list[dict]:
    return paths.read_jsonl(paths.DATA / "leases.jsonl")


def money(cents: int | None) -> str:
    return "none" if cents is None else f"${cents / 100:,.2f}"


def dumps(abstract: dict) -> str:
    return json.dumps(abstract, sort_keys=True)
