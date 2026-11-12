"""Lease documents: read a lease file and split it into clauses with stable ids."""
import json
import re

from . import paths

HEAD = re.compile(r"^## ([a-z]\d\d) (.+)$")

FIELDS = [
    "unit", "tenant", "lease_type", "start_date", "end_date", "monthly_rent", "rent_steps", "deposit",
    "renewal_option", "renewal_notice_days", "pets_allowed", "pet_fee", "late_fee", "late_fee_after_day",
    "early_termination_fee", "utilities_included", "parking", "sublet_allowed",
]
CRITICAL = ["monthly_rent", "rent_steps", "deposit", "renewal_notice_days"]


def text(lease_id: str) -> str:
    return (paths.LEASES / f"{lease_id}.md").read_text()


def clauses(lease_id: str) -> list[dict]:
    """[{id: 'L014-c04', heading: 'Rent', text: '...'}] in document order."""
    out, cur = [], None
    for line in text(lease_id).splitlines():
        m = HEAD.match(line)
        if m:
            cur = {"id": f"{lease_id}-{m.group(1)}", "heading": m.group(2), "lines": []}
            out.append(cur)
        elif cur is not None and line.strip():
            cur["lines"].append(line.strip())
    return [{"id": c["id"], "heading": c["heading"], "text": " ".join(c["lines"])} for c in out]


def keys() -> dict[str, dict]:
    """The answer key per lease, written by the generator, never by a model."""
    return {r["lease_id"]: r["abstract"] for r in paths.read_jsonl(paths.DATA / "keys.jsonl")}


def leases() -> list[dict]:
    return paths.read_jsonl(paths.DATA / "leases.jsonl")


def money(cents: int | None) -> str:
    return "none" if cents is None else f"${cents / 100:,.2f}"


def dumps(abstract: dict) -> str:
    return json.dumps(abstract, sort_keys=True)
