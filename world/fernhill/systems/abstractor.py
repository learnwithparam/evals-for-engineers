"""Lease abstractor: reads a lease and its amendments, writes the 18-field abstract to the system of record."""
import json

from .. import leases, llm

SYSTEM = (
    "You read a lease and any amendments and write the lease abstract as one JSON object with exactly these "
    "fields: " + ", ".join(leases.FIELDS) + ". Money is in whole cents. Dates are YYYY-MM-DD. rent_steps is a "
    "list of {effective, monthly_rent}. late_fee is {kind: flat or percent, value}. utilities_included lists "
    "what the landlord pays for. Use null when the lease has no such term. Reply with the JSON only."
)


def messages(lease_id: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": leases.text(lease_id)}]


def parse(reply: str) -> dict:
    t = reply.strip()
    if t.startswith("```"):
        t = t.strip("`").split("\n", 1)[1]
    start, end = t.find("{"), t.rfind("}")
    return json.loads(t[start:end + 1])


def run(lease_id: str, trial: int = 1) -> dict:
    reply = llm.complete("fast", messages(lease_id), trial=trial, system="abstractor")
    return parse(reply.text)
