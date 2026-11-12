"""Lease abstractor: turns a lease into its 18-field abstract.

It reads a signed lease and its amendments, and writes the abstract to the system of record.
"""

import json

from .. import leases, llm

SYSTEM = (
    "You read a lease and any amendments and write the lease abstract as one JSON object "
    "with exactly these fields: "
    + ", ".join(leases.FIELDS)
    + ". Money is in whole cents. Dates are YYYY-MM-DD. "
    "rent_steps is a list of {effective, monthly_rent}. "
    "late_fee is {kind: flat or percent, value}. "
    "utilities_included lists what the landlord pays for. "
    "Use null when the lease has no such term. Reply with the JSON only."
)


def messages(lease_id: str) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": leases.text(lease_id)},
    ]


def parse(reply: str) -> dict:
    """The JSON object in a reply, even when the model wrapped it in a ``` code fence."""
    reply_text = reply.strip()
    if reply_text.startswith("```"):
        without_fence = reply_text.strip("`")
        reply_text = without_fence.split("\n", 1)[1]
    start, end = reply_text.find("{"), reply_text.rfind("}")
    return json.loads(reply_text[start : end + 1])


def run(lease_id: str, trial: int = 1) -> dict:
    settings = llm.CallSettings(system="abstractor", trial=trial)
    reply = llm.complete("fast", messages(lease_id), settings)
    return parse(reply.text)
