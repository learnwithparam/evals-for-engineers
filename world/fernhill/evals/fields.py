"""Field checks: compare an abstract with the answer key, one field at a time, in code."""

from .. import leases


def _steps(rent_steps):
    """Rent steps as sorted (effective date, monthly rent) pairs, so their order does not matter."""
    return sorted(
        (step.get("effective"), int(step.get("monthly_rent") or 0)) for step in (rent_steps or [])
    )


def same(field: str, got, want) -> bool:
    if field == "rent_steps":
        return _steps(got) == _steps(want)
    if field == "utilities_included":
        return sorted(got or []) == sorted(want or [])
    if field == "late_fee":
        return (
            isinstance(got, dict)
            and got.get("kind") == want["kind"]
            and got.get("value") == want["value"]
        )
    return got == want


def score(abstract: dict, key: dict) -> dict[str, bool]:
    return {field: same(field, abstract.get(field), key.get(field)) for field in leases.FIELDS}
