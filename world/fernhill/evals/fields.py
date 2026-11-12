"""Field checks: compare an abstract with the answer key, one field at a time, in code."""

from .. import leases


def _steps(v):
    return sorted((s.get("effective"), int(s.get("monthly_rent") or 0)) for s in (v or []))


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
    return {f: same(f, abstract.get(f), key.get(f)) for f in leases.FIELDS}
