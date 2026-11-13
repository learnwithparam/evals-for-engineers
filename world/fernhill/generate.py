"""Builds the whole Fernhill world from one seed: leases, keys, ledger, traces, labels, releases
and replay recordings.

Run `uv run world generate` only when you change this file. The output is committed, so learners
and CI never need to run it. Every planted fault is written to world/data/planted_faults.jsonl.

The replies in world/replay/ are written here, by rules, so every fault is known. They stand in
for a small model's replies. Set LLM_PROVIDER and a key to see what a real model does on the
same leases.

The world comes from seeded random draws, so the order of the draws matters: moving one draw
changes everything drawn after it. Keep every draw where it is.
"""

import copy
import csv
import hashlib
import json
import random
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import db, leases, llm, paths
from .evals import judge
from .models_cli import PING
from .systems import abstractor, agent, lease_desk, retrieval

SEED = 2026
# The buildings and leases draw from this one source, in a fixed order.
WORLD_RANDOM = random.Random(SEED)
WINDOW_MONTHS = [(2025, 11), (2025, 12)] + [(2026, month) for month in range(1, 11)]
# The twelve months of history in the ledger, written as "YYYY-MM".
WINDOW = [f"{year}-{month:02d}" for year, month in WINDOW_MONTHS]
TODAY = date(2026, 10, 31)

STREETS = [
    "Alder Row",
    "Birch Court",
    "Cobble Yard",
    "Damson House",
    "Elm Terrace",
    "Fennel Mews",
    "Gorse Lane",
    "Hazel Point",
    "Ivy Wharf",
    "Juniper Hall",
    "Kestrel Way",
    "Larch Gardens",
    "Medlar Place",
    "Nettle Rise",
    "Osier Walk",
    "Plover House",
    "Quince Court",
    "Rowan Steps",
    "Sorrel Yard",
    "Teasel Row",
    "Umber Lofts",
    "Vetch Square",
    "Willow Bank",
    "Yarrow House",
    "Aspen Close",
    "Bramble Works",
    "Clover Mill",
    "Dunlin Court",
    "Eyot House",
    "Fernhill Arcade",
    "Granary Wharf",
]
FIRST = [
    "Ana",
    "Ben",
    "Chloe",
    "Dev",
    "Ewa",
    "Femi",
    "Grace",
    "Hugo",
    "Isla",
    "Jon",
    "Kemi",
    "Liam",
    "Maya",
    "Nico",
    "Omar",
    "Priya",
    "Quinn",
    "Rosa",
    "Sam",
    "Tara",
    "Uma",
    "Vik",
    "Wen",
    "Yusuf",
    "Zara",
    "Ade",
    "Bea",
    "Cal",
]
LAST = [
    "Ruiz",
    "Okafor",
    "Novak",
    "Shah",
    "Brennan",
    "Lindqvist",
    "Mensah",
    "Tanaka",
    "Haddad",
    "Kowalski",
    "Osei",
    "Moreau",
    "Fischer",
    "Quint",
    "Abara",
    "Delaney",
    "Varga",
    "Nakamura",
    "Pereira",
    "Sato",
]
SHOPS = [
    "Corner Loaf Bakery",
    "Thimble Repairs",
    "Greenleaf Pharmacy",
    "Two Spoons Cafe",
    "Brightside Opticians",
    "Ledger and Quill Stationers",
    "Pebble Pet Supplies",
    "Northgate Laundry",
    "Kiln Pottery Studio",
    "Hearth Hardware",
]
NUMWORDS = {
    30: "thirty",
    60: "sixty",
    90: "ninety",
    120: "one hundred and twenty",
    180: "one hundred and eighty",
}
MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

BUILDING_COUNT = 31
MIXED_BUILDINGS = ("Fernhill Arcade", "Granary Wharf", "Clover Mill", "Umber Lofts")
OWNER_KINDS = ["Family Trust", "Holdings", "Estates", "Partners"]
NEW_TEMPLATE = "FH-RES-2026"
RESIDENTIAL_TEMPLATES = ["FH-RES-2019", "FH-RES-2022"]
UTILITY_SETS = [[], ["water"], ["water", "trash"], ["trash"], ["gas", "water", "trash"]]


def add_months(start: date, count: int) -> date:
    """The first day of the month that is `count` months after `start`."""
    month_index = start.month - 1 + count
    return date(start.year + month_index // 12, month_index % 12 + 1, 1)


def end_of_term(start: date, months: int) -> date:
    next_start = add_months(start, months)
    return date.fromordinal(next_start.toordinal() - 1)


def words(when: date) -> str:
    return f"{when.day} {MONTHS[when.month - 1]} {when.year}"


def words_for(iso_date: str) -> str:
    return words(date.fromisoformat(iso_date))


def nth(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def random_for(*parts) -> random.Random:
    """A random source of its own for one part of the world, so draws elsewhere cannot shift it."""
    text = json.dumps([SEED, *parts])
    digest = hashlib.sha256(text.encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def late_fee_text(late_fee: dict) -> str:
    if late_fee["kind"] == "percent":
        return f"{late_fee['value']}% of the overdue amount"
    return usd(late_fee["value"])


# ---------------------------------------------------------------- buildings and units


def building_sizes() -> list[int]:
    """Most buildings have 59 units; eleven of them have 60."""
    sizes = [59] * BUILDING_COUNT
    for index in WORLD_RANDOM.sample(range(BUILDING_COUNT), 11):
        sizes[index] += 1
    return sizes


def owner_names() -> list[str]:
    """Draws 60 owners though only 31 are used, because every later draw depends on this count."""
    owners = []
    for _ in range(60):
        family = WORLD_RANDOM.choice(LAST)
        holding = WORLD_RANDOM.choice(OWNER_KINDS)
        owners.append(f"{family} {holding}")
    return owners


def make_building(number: int, name: str, unit_count: int, owner: str) -> dict:
    kind = "mixed" if name in MIXED_BUILDINGS else "residential"
    return {
        "id": f"B{number:02d}",
        "name": name,
        "address": f"{WORLD_RANDOM.randint(2, 180)} {name}",
        "owner": owner,
        "units": unit_count,
        "kind": kind,
    }


def unit_labels(unit_count: int, kind: str) -> list[str]:
    """Six flats a floor, labelled 1A to 1F, 2A and so on."""
    floors = (unit_count + 5) // 6
    labels = [
        f"{floor}{chr(65 + position)}" for floor in range(1, floors + 1) for position in range(6)
    ]
    labels = labels[:unit_count]
    if kind == "mixed":
        # A mixed building has four shops on the ground floor in place of its first four flats.
        shop_labels = [f"G{number}" for number in range(1, 5)]
        labels = shop_labels + labels[4:]
    return labels


def make_unit(building_id: str, label: str) -> dict:
    if label.startswith("G"):
        bedrooms = 0
        kind = "retail"
    else:
        bedrooms = WORLD_RANDOM.choice([1, 1, 2, 2, 3])
        kind = "flat"
    return {
        "id": f"{building_id}-{label}",
        "building_id": building_id,
        "label": label,
        "bedrooms": bedrooms,
        "kind": kind,
    }


def make_buildings():
    sizes = building_sizes()
    owners = owner_names()
    buildings, units = [], []
    for number, (name, unit_count) in enumerate(zip(STREETS, sizes, strict=True), 1):
        building = make_building(number, name, unit_count, owners[number - 1])
        buildings.append(building)
        for label in unit_labels(unit_count, building["kind"]):
            units.append(make_unit(building["id"], label))
    return buildings, units


# ---------------------------------------------------------------- leases


@dataclass
class LeaseKind:
    """What sort of lease a lease number gets. It decides which random draws the lease makes."""

    number: int
    commercial: bool
    new_template: bool
    amended: bool


@dataclass
class Tenancy:
    tenant: str
    start: date
    term: int
    template: str
    rent: int


@dataclass
class LeaseTerms:
    """The terms drawn after the rent, in the order they are drawn."""

    deposit: int
    renewal: bool
    notice_days: int | None
    notice_phrase: str | None
    pets: bool
    pet_fee: int | None
    pet_deposit: int | None
    late_fee: dict
    late_day: int
    termination_fee: int | None
    utilities: list[str]
    parking: bool
    sublet: bool


@dataclass
class DrawnLease:
    """Everything drawn for one lease, before it is written out as its facts and its key."""

    kind: LeaseKind
    unit: dict
    building: dict
    tenancy: Tenancy
    step_style: str
    step_percent: int
    steps: list[dict]
    amendment: dict | None
    terms: LeaseTerms


def lease_kind(number: int) -> LeaseKind:
    """Leases 111 to 120 are shops, and leases above 120 use the new residential template."""
    amended = (number % 4 == 0 and number <= 108) or number in (112, 115, 118)
    return LeaseKind(
        number=number,
        commercial=111 <= number <= 120,
        new_template=number > 120,
        amended=amended,
    )


def lease_type(kind: LeaseKind) -> str:
    if kind.commercial:
        return "commercial"
    return "residential"


def take_unit(free_units: list[dict], commercial: bool) -> dict:
    """Picks a free unit of the right kind and marks it as let."""
    wanted = "retail" if commercial else "flat"
    pool = [unit for unit in free_units if unit["kind"] == wanted]
    unit = WORLD_RANDOM.choice(pool)
    free_units.remove(unit)
    return unit


def commercial_tenancy(kind: LeaseKind) -> Tenancy:
    year = WORLD_RANDOM.choice([2022, 2023, 2024])
    month = WORLD_RANDOM.randint(1, 12)
    tenant = SHOPS[kind.number - 111]
    rent = WORLD_RANDOM.randrange(400000, 1200000, 5000)
    return Tenancy(tenant, date(year, month, 1), 60, "FH-COM-2018", rent)


def residential_tenancy(kind: LeaseKind) -> Tenancy:
    first_name = WORLD_RANDOM.choice(FIRST)
    last_name = WORLD_RANDOM.choice(LAST)
    if kind.new_template:
        start = date(2026, WORLD_RANDOM.choice([9, 10, 11]), 1)
        term, template = 12, NEW_TEMPLATE
    # The draw comes first, so it happens even for amended leases, which are always two years.
    elif WORLD_RANDOM.random() < 0.8 or kind.amended:
        start = add_months(date(2024, 11, 1), WORLD_RANDOM.randint(0, 13))
        term = 24
        template = WORLD_RANDOM.choice(RESIDENTIAL_TEMPLATES)
    else:
        start = add_months(date(2025, 11, 1), WORLD_RANDOM.randint(0, 4))
        term = 12
        template = WORLD_RANDOM.choice(RESIDENTIAL_TEMPLATES)
    rent = WORLD_RANDOM.randrange(115000, 340000, 2500)
    return Tenancy(f"{first_name} {last_name}", start, term, template, rent)


def draw_step_percent(kind: LeaseKind) -> int:
    if kind.commercial:
        return 3
    return WORLD_RANDOM.choice([2, 3, 4])


def draw_step_style(kind: LeaseKind, tenancy: Tenancy) -> str:
    """How the lease writes its yearly rent rises: as a table, in prose, or not at all."""
    if kind.commercial and not kind.amended:
        return "prose"
    plain_two_year = tenancy.term == 24 and not kind.amended and not kind.new_template
    if not kind.commercial and plain_two_year:
        return WORLD_RANDOM.choices(["table", "prose", "none"], [0.4, 0.35, 0.25])[0]
    return "none"


def stepped_rents(tenancy: Tenancy, style: str, percent: int) -> list[dict]:
    steps = []
    if style == "none":
        return steps
    current = tenancy.rent
    for month in range(12, tenancy.term, 12):
        current = int(round(current * (100 + percent) / 100))
        effective = add_months(tenancy.start, month)
        steps.append({"effective": effective.isoformat(), "monthly_rent": current})
    return steps


def draw_amendment(kind: LeaseKind, tenancy: Tenancy) -> dict | None:
    if not kind.amended:
        return None
    effective = add_months(tenancy.start, WORLD_RANDOM.randint(4, 10))
    if kind.commercial:
        increase = int(tenancy.rent * 0.05)
    else:
        increase = WORLD_RANDOM.randrange(5000, 20000, 2500)
    return {"effective": effective.isoformat(), "monthly_rent": tenancy.rent + increase}


def deposit_for(kind: LeaseKind, rent: int) -> int:
    if kind.commercial:
        return rent * 3
    multiple = WORLD_RANDOM.choice([1, 1.5, 2])
    return int(round(rent * multiple / 100)) * 100


def draw_notice_phrase() -> str:
    """Some leases say "not less than N days", which the abstractor and lease desk get wrong."""
    if WORLD_RANDOM.random() < 0.3:
        return "not_less_than"
    return "exact"


def renewal_terms(kind: LeaseKind) -> tuple:
    """Returns whether the lease can be renewed, the notice days and how the notice is worded."""
    if kind.commercial:
        notice_days = WORLD_RANDOM.choice([120, 180])
        return True, notice_days, draw_notice_phrase()
    if WORLD_RANDOM.random() >= 0.75:
        return False, None, None
    notice_days = WORLD_RANDOM.choice([30, 60, 90])
    return True, notice_days, draw_notice_phrase()


def pet_terms(kind: LeaseKind) -> tuple:
    """Returns whether pets are allowed, the monthly pet fee and the one-time pet deposit."""
    if kind.commercial or WORLD_RANDOM.random() >= 0.45:
        return False, None, None
    pet_fee = WORLD_RANDOM.choice([2500, 3500, 5000])
    pet_deposit = 30000 if WORLD_RANDOM.random() < 0.5 else None
    return True, pet_fee, pet_deposit


def late_terms(kind: LeaseKind, rent: int) -> tuple:
    """Returns the late fee, the day it applies after, and the early termination fee."""
    if kind.commercial:
        late_fee = {"kind": "percent", "value": 5}
        termination_fee = rent * 6 if WORLD_RANDOM.random() < 0.3 else None
        return late_fee, 10, termination_fee
    late_fee = {"kind": "flat", "value": WORLD_RANDOM.choice([5000, 7500, 10000])}
    late_day = WORLD_RANDOM.choice([3, 5])
    termination_fee = rent * 2 if WORLD_RANDOM.random() < 0.5 else None
    return late_fee, late_day, termination_fee


def utilities_for(kind: LeaseKind) -> list[str]:
    if kind.commercial:
        return []
    return sorted(WORLD_RANDOM.choice(UTILITY_SETS))


def draw_terms(kind: LeaseKind, rent: int) -> LeaseTerms:
    deposit = deposit_for(kind, rent)
    renewal, notice_days, notice_phrase = renewal_terms(kind)
    pets, pet_fee, pet_deposit = pet_terms(kind)
    late_fee, late_day, termination_fee = late_terms(kind, rent)
    utilities = utilities_for(kind)
    parking = WORLD_RANDOM.random() < 0.5
    sublet = kind.commercial or WORLD_RANDOM.random() < 0.3
    return LeaseTerms(
        deposit=deposit,
        renewal=renewal,
        notice_days=notice_days,
        notice_phrase=notice_phrase,
        pets=pets,
        pet_fee=pet_fee,
        pet_deposit=pet_deposit,
        late_fee=late_fee,
        late_day=late_day,
        termination_fee=termination_fee,
        utilities=utilities,
        parking=parking,
        sublet=sublet,
    )


def lease_key(drawn: DrawnLease) -> dict:
    """The correct abstract of the lease, which every abstractor reply is checked against."""
    tenancy = drawn.tenancy
    terms = drawn.terms
    current_rent = tenancy.rent
    if drawn.amendment:
        current_rent = drawn.amendment["monthly_rent"]
    return {
        "unit": drawn.unit["label"],
        "tenant": tenancy.tenant,
        "lease_type": lease_type(drawn.kind),
        "start_date": tenancy.start.isoformat(),
        "end_date": end_of_term(tenancy.start, tenancy.term).isoformat(),
        "monthly_rent": current_rent,
        "rent_steps": drawn.steps,
        "deposit": terms.deposit,
        "renewal_option": terms.renewal,
        "renewal_notice_days": terms.notice_days,
        "pets_allowed": terms.pets,
        "pet_fee": terms.pet_fee,
        "late_fee": terms.late_fee,
        "late_fee_after_day": terms.late_day,
        "early_termination_fee": terms.termination_fee,
        "utilities_included": terms.utilities,
        "parking": terms.parking,
        "sublet_allowed": terms.sublet,
    }


def lease_meta(drawn: DrawnLease) -> dict:
    """The facts about the lease that are not in its abstract, such as how it is worded."""
    kind = drawn.kind
    return {
        "id": f"L{kind.number:03d}",
        "unit_id": drawn.unit["id"],
        "unit": drawn.unit["label"],
        "building": drawn.building["name"],
        "address": drawn.building["address"],
        "owner": drawn.building["owner"],
        "tenant": drawn.tenancy.tenant,
        "lease_type": lease_type(kind),
        "template": drawn.tenancy.template,
        "corpus": "production" if kind.new_template else "eval",
        "amendments": 1 if drawn.amendment else 0,
        "original_rent": drawn.tenancy.rent,
        "step_style": drawn.step_style,
        "step_pct": drawn.step_percent,
        "notice_phrase": drawn.terms.notice_phrase,
        "pet_deposit": drawn.terms.pet_deposit,
        "amendment": drawn.amendment,
        "term_months": drawn.tenancy.term,
    }


def make_lease(number, buildings, free_units):
    kind = lease_kind(number)
    unit = take_unit(free_units, kind.commercial)
    building = next(item for item in buildings if item["id"] == unit["building_id"])
    tenancy = commercial_tenancy(kind) if kind.commercial else residential_tenancy(kind)
    percent = draw_step_percent(kind)
    style = draw_step_style(kind, tenancy)
    steps = stepped_rents(tenancy, style, percent)
    amendment = draw_amendment(kind, tenancy)
    terms = draw_terms(kind, tenancy.rent)
    drawn = DrawnLease(kind, unit, building, tenancy, style, percent, steps, amendment, terms)
    return lease_meta(drawn), lease_key(drawn)


# ---------------------------------------------------------------- lease text


def parties_clause(meta, key):
    landlord = f"Fernhill Homes, as managing agent for {meta['owner']}"
    body = f'This lease is between {landlord} ("Landlord") and {key["tenant"]} ("Tenant").'
    return "c01", "Parties", body


def premises_clause(meta):
    body = f'Landlord lets to Tenant unit {meta["unit"]} at {meta["address"]} ("the Premises").'
    return "c02", "Premises", body


def term_clause(key):
    body = (
        f"The term starts on {words_for(key['start_date'])} and ends on "
        f"{words_for(key['end_date'])}."
    )
    return "c03", "Term", body


def rent_clause(meta):
    body = (
        f"Tenant shall pay monthly rent of {usd(meta['original_rent'])}, due on the first day of "
        f"each month."
    )
    return "c04", "Rent", body


def rent_increases_clause(meta, key):
    if meta["step_style"] == "table":
        rows = "\n".join(
            f"| {words_for(step['effective'])} | {usd(step['monthly_rent'])} |"
            for step in key["rent_steps"]
        )
        body = f"The monthly rent changes as follows.\n\n| From | Monthly rent |\n|---|---|\n{rows}"
    elif meta["step_style"] == "prose":
        body = (
            f"On each anniversary of the start date, the monthly rent shall increase by "
            f"{meta['step_pct']}% over the rent then payable, rounded to the nearest cent."
        )
    else:
        body = "The rent does not change during the term."
    return "c05", "Rent increases", body


def deposit_clause(key):
    body = (
        f"Tenant has paid a security deposit of {usd(key['deposit'])}, held under the "
        f"deposit rules that apply to the Premises."
    )
    return "c06", "Security deposit", body


def late_charges_clause(key):
    fee = late_fee_text(key["late_fee"])
    body = (
        f"If rent is not received by the {nth(key['late_fee_after_day'])} of the month, Tenant "
        f"shall pay a late charge of {fee}."
    )
    return "c07", "Late charges", body


def utilities_clause(key):
    utilities = key["utilities_included"]
    if not utilities:
        return "c08", "Utilities", "Tenant pays for all utilities."
    body = f"Landlord pays for {' and '.join(utilities)}. Tenant pays for all other utilities."
    return "c08", "Utilities", body


def animals_clause(meta, key):
    if meta["lease_type"] == "commercial":
        body = "No animals other than assistance animals are allowed on the Premises."
        return "c09", "Animals", body
    if not key["pets_allowed"]:
        return "c09", "Pets", "No pets are allowed on the Premises."
    extra = ""
    if meta["pet_deposit"]:
        extra = f" and a one-time pet deposit of {usd(meta['pet_deposit'])}"
    body = (
        f"Tenant may keep up to two pets. Tenant shall pay a pet fee of {usd(key['pet_fee'])} "
        f"per month{extra}."
    )
    return "c09", "Pets", body


def parking_clause(key):
    if key["parking"]:
        return "c10", "Parking", "One parking space is included."
    return "c10", "Parking", "No parking is included."


def subletting_clause(key):
    if key["sublet_allowed"]:
        body = (
            "Tenant may sublet the Premises with Landlord's written consent, "
            "which Landlord will not withhold without good reason."
        )
    else:
        body = "Tenant may not assign this lease or sublet any part of the Premises."
    return "c11", "Assignment and subletting", body


def extension_clause(days):
    """The new template words the renewal clause in plainer English, and calls it an extension."""
    if not days:
        return "c12", "Extension", "This lease cannot be extended."
    body = (
        f"If the Tenant wants to stay on, the Tenant can extend for a further 12 "
        f"months by telling Fernhill at least {days} days before the term ends."
    )
    return "c12", "Extension", body


def renewal_clause(meta, key):
    days = key["renewal_notice_days"]
    if meta["template"] == NEW_TEMPLATE:
        return extension_clause(days)
    if not days:
        return "c12", "Renewal", "This lease has no renewal option."
    notice = f"{NUMWORDS[days]} ({days}) days"
    if meta["notice_phrase"] == "not_less_than":
        notice = f"not less than {notice}"
    term = "five years" if meta["lease_type"] == "commercial" else "12 months"
    body = (
        f"Tenant may renew this lease for one further term of {term} by giving written "
        f"notice {notice} before the end of the term."
    )
    return "c12", "Renewal", body


def early_termination_clause(key):
    fee = key["early_termination_fee"]
    if not fee:
        return "c13", "Early termination", "Tenant has no right to end this lease early."
    body = (
        f"Tenant may end this lease early by giving 60 days' written notice and "
        f"paying an early termination fee of {usd(fee)}."
    )
    return "c13", "Early termination", body


NOTICES_CLAUSE = (
    "c14",
    "Notices",
    "Notices must be in writing and sent to the addresses in this lease. A posted notice "
    "is treated as received 3 days after posting.",
)


def amendment_clause(meta):
    amendment = meta["amendment"]
    body = (
        f"Signed by both parties. From "
        f"{words_for(amendment['effective'])}, clause c04 is changed: the "
        f"monthly rent is {usd(amendment['monthly_rent'])}."
    )
    if meta["lease_type"] == "commercial":
        body += " Clause c05 no longer applies."
    body += " All other terms stay the same."
    return "a01", "Amendment No. 1", body


def lease_clauses(meta, key):
    clauses = [
        parties_clause(meta, key),
        premises_clause(meta),
        term_clause(key),
        rent_clause(meta),
        rent_increases_clause(meta, key),
        deposit_clause(key),
        late_charges_clause(key),
        utilities_clause(key),
        animals_clause(meta, key),
        parking_clause(key),
        subletting_clause(key),
        renewal_clause(meta, key),
        early_termination_clause(key),
        NOTICES_CLAUSE,
    ]
    if meta["amendment"]:
        clauses.append(amendment_clause(meta))
    return clauses


def lease_text(meta, key):
    is_commercial = meta["lease_type"] == "commercial"
    title = "Commercial Lease" if is_commercial else "Residential Lease"
    lines = [
        f"# {title} {meta['id']}",
        "",
        f"Fernhill Homes lease for unit {meta['unit']} at {meta['building']}. "
        f"Template: {meta['template']}.",
        "",
    ]
    for clause_id, heading, body in lease_clauses(meta, key):
        lines.extend([f"## {clause_id} {heading}", "", body, ""])
    text = "\n".join(lines)
    return text.rstrip() + "\n"


# ---------------------------------------------------------------- the abstractor's mistakes

MODES = {
    "amended-rent-missed": (
        "The abstract keeps the rent from the original lease and ignores a later amendment."
    ),
    "rent-step-dropped": (
        "The abstract has no rent steps although the lease raises the rent during the term."
    ),
    "notice-days-wrong-clause": (
        "The renewal notice days come from another clause, not the renewal clause."
    ),
    "utilities-incomplete": "The abstract leaves out a utility that the landlord pays for.",
    "late-fee-percent-as-dollars": (
        "A late fee written as a percent is recorded as a flat dollar amount."
    ),
    "deposit-includes-pet-deposit": (
        "The security deposit adds in the separate one-time pet deposit."
    ),
}


@dataclass
class Lease:
    """A lease's facts (its meta) and its correct abstract (its key), which most rules need."""

    meta: dict
    key: dict


def drops_rent_steps(lease: Lease, random_source, lease_faults) -> bool:
    if "rent-step-dropped" in lease_faults:
        return True
    meta = lease.meta
    commercial_prose = meta["step_style"] == "prose" and meta["lease_type"] == "commercial"
    return commercial_prose and random_source.random() < 0.5


def wrong_notice_days(key: dict) -> int:
    """The days the abstractor reads from the wrong clause: early termination, or notices."""
    if key["early_termination_fee"] and key["renewal_notice_days"] != 60:
        return 60
    return 3


def abstract_with_faults(lease: Lease, random_source, lease_faults, noise=1.0):
    """One abstractor reply for a lease, with the faults this lease and this draw carry."""
    meta, key = lease.meta, lease.key
    abstract = copy.deepcopy(key)
    modes = []
    if "amended-rent-missed" in lease_faults:
        abstract["monthly_rent"] = meta["original_rent"]
        modes.append("amended-rent-missed")
    if drops_rent_steps(lease, random_source, lease_faults) and abstract["rent_steps"]:
        abstract["rent_steps"] = []
        modes.append("rent-step-dropped")
    if meta["notice_phrase"] == "not_less_than" and random_source.random() < 0.4:
        abstract["renewal_notice_days"] = wrong_notice_days(key)
        modes.append("notice-days-wrong-clause")
    if abstract["utilities_included"] and random_source.random() < 0.08 * noise:
        abstract["utilities_included"] = abstract["utilities_included"][1:]
        modes.append("utilities-incomplete")
    if key["late_fee"]["kind"] == "percent" and random_source.random() < 0.5:
        abstract["late_fee"] = {"kind": "flat", "value": key["late_fee"]["value"] * 100}
        modes.append("late-fee-percent-as-dollars")
    if meta["pet_deposit"] and random_source.random() < 0.2:
        abstract["deposit"] = key["deposit"] + meta["pet_deposit"]
        modes.append("deposit-includes-pet-deposit")
    return abstract, modes


# ---------------------------------------------------------------- the lease desk

QUESTIONS = {
    "pets": ("Can the tenant in unit {u} at {b} keep a cat?", ["c09"]),
    "renewal": (
        "How much notice does the tenant in unit {u} at {b} need to give to renew?",
        ["c12"],
    ),
    "rent": ("What is the monthly rent for unit {u} at {b} now?", ["c04", "a01"]),
    "late": ("When does a late fee apply for unit {u} at {b}, and how much is it?", ["c07"]),
    "sublet": ("Can the tenant in unit {u} at {b} sublet?", ["c11"]),
    "water": ("Who pays for water in unit {u} at {b}?", ["c08"]),
    "parking": ("Does the lease for unit {u} at {b} include parking?", ["c10"]),
    "deposit": ("What security deposit did the tenant in unit {u} at {b} pay?", ["c06"]),
    "early": ("Can the tenant in unit {u} at {b} end the lease early?", ["c13"]),
    "business": ("Can the tenant in unit {u} at {b} run a business from home?", []),
    "paint": ("Can the tenant in unit {u} at {b} paint the walls?", []),
}

BUSINESS_CLAIMS = [
    "Yes, a home business is allowed if it does not disturb neighbours",
    "Yes, a home office is fine but no customers may visit",
    "No, the lease bans any business use",
]
PAINT_CLAIMS = [
    "Yes, the tenant may paint if the walls are returned to white",
    "Yes, with written consent from Fernhill",
    "No, the lease bans any decorating",
]


def citation(lease: Lease, clause_id: str) -> str:
    return f"[{lease.meta['id']}-{clause_id}]"


def pets_answer(lease: Lease) -> str:
    cite = citation(lease, "c09")
    if lease.key["pets_allowed"]:
        pet_fee = usd(lease.key["pet_fee"])
        return f"Yes. The lease allows up to two pets for a pet fee of {pet_fee} a month {cite}."
    return f"No. The lease does not allow pets {cite}."


def renewal_answer(lease: Lease) -> str:
    days = lease.key["renewal_notice_days"]
    cite = citation(lease, "c12")
    if lease.meta["template"] == NEW_TEMPLATE:
        return f"The tenant must tell Fernhill at least {days} days before the term ends {cite}."
    limit = ""
    if lease.meta["notice_phrase"] == "not_less_than":
        limit = "not less than "
    return (
        f"The tenant must give written notice {limit}{days} days before the end of the term {cite}."
    )


def rent_answer(lease: Lease) -> str:
    rent = usd(lease.key["monthly_rent"])
    if lease.meta["amendment"]:
        return f"The rent is {rent} a month, set by Amendment No. 1 {citation(lease, 'a01')}."
    return f"The rent is {rent} a month {citation(lease, 'c04')}."


def late_answer(lease: Lease) -> str:
    fee = late_fee_text(lease.key["late_fee"])
    day = nth(lease.key["late_fee_after_day"])
    cite = citation(lease, "c07")
    return f"A late charge of {fee} applies if rent is not received by the {day} {cite}."


def sublet_answer(lease: Lease) -> str:
    cite = citation(lease, "c11")
    if lease.key["sublet_allowed"]:
        return f"Yes, with Fernhill's written consent {cite}."
    return f"No. The lease does not allow subletting {cite}."


def water_answer(lease: Lease) -> str:
    cite = citation(lease, "c08")
    if "water" in lease.key["utilities_included"]:
        return f"The landlord pays for water {cite}."
    return f"The tenant pays for water {cite}."


def parking_answer(lease: Lease) -> str:
    cite = citation(lease, "c10")
    if lease.key["parking"]:
        return f"Yes, one parking space is included {cite}."
    return f"No, parking is not included {cite}."


def deposit_answer(lease: Lease) -> str:
    deposit = usd(lease.key["deposit"])
    return f"The tenant paid a security deposit of {deposit} {citation(lease, 'c06')}."


def early_answer(lease: Lease) -> str:
    fee = lease.key["early_termination_fee"]
    cite = citation(lease, "c13")
    if fee:
        return f"Yes, with 60 days' written notice and a fee of {usd(fee)} {cite}."
    return f"No. The lease gives no right to end early {cite}."


GOOD_ANSWERS = {
    "pets": pets_answer,
    "renewal": renewal_answer,
    "rent": rent_answer,
    "late": late_answer,
    "sublet": sublet_answer,
    "water": water_answer,
    "parking": parking_answer,
    "deposit": deposit_answer,
    "early": early_answer,
}


def good_answer(kind: str, lease: Lease) -> str:
    if kind not in GOOD_ANSWERS:
        raise ValueError(kind)
    return GOOD_ANSWERS[kind](lease)


def first_retrieved_clause(retrieved: list[str]) -> str:
    """The clause part of the first retrieved id, such as "c09" from "L007-c09"."""
    return retrieved[0].split("-")[1]


def unsupported_claim(kind, lease, random_source, retrieved):
    """A confident answer to a question the lease does not answer, citing whatever was found."""
    cite = citation(lease, first_retrieved_clause(retrieved))
    claims = BUSINESS_CLAIMS if kind == "business" else PAINT_CLAIMS
    claim = random_source.choice(claims)
    return f"{claim} {cite}."


def dropped_limit_answer(lease, random_source):
    """A renewal answer that drops the "not less than" from the notice period."""
    days = lease.key["renewal_notice_days"]
    cite = citation(lease, "c12")
    answers = [
        f"The tenant must give written notice {days} days before the end of the term {cite}.",
        f"Exactly {days} days' written notice is needed {cite}.",
        f"The tenant needs to give {days} days' notice before the term ends {cite}.",
    ]
    return random_source.choice(answers)


def wrong_money_answer(kind, lease, random_source):
    """A wrong amount or day for rent, late fees or deposits, or None for other questions."""
    meta, key = lease.meta, lease.key
    if kind == "rent" and meta["amendment"]:
        rent = usd(meta["original_rent"])
        cite = citation(lease, "c04")
        answers = [
            f"The rent is {rent} a month {cite}.",
            f"Monthly rent is {rent}, due on the first day of each month {cite}.",
        ]
        return random_source.choice(answers)
    if kind == "late":
        day = nth(key["late_fee_after_day"] + random_source.choice([1, 2, 5]))
        cite = citation(lease, "c07")
        return f"A late charge applies if rent is not received by the {day} {cite}."
    if kind == "deposit":
        deposit = usd(key["deposit"] + random_source.choice([30000, 50000, 75000]))
        return f"The tenant paid a security deposit of {deposit} {citation(lease, 'c06')}."
    return None


def wrong_permission_answer(kind, lease, random_source):
    """A permission with the conditions left out, or None for other questions."""
    key = lease.key
    if kind == "sublet" and key["sublet_allowed"]:
        return f"Yes, the tenant may sublet freely {citation(lease, 'c11')}."
    if kind == "pets" and key["pets_allowed"]:
        return f"Yes. The lease allows pets with no extra fee {citation(lease, 'c09')}."
    if kind == "early" and key["early_termination_fee"]:
        cite = citation(lease, "c13")
        answers = [
            f"Yes, with 30 days' notice and no fee {cite}.",
            f"Yes, with 60 days' notice and no fee {cite}.",
        ]
        return random_source.choice(answers)
    return None


def wrong_guess_answer(lease, random_source, retrieved):
    cite = citation(lease, first_retrieved_clause(retrieved))
    answers = [
        f"Yes, and the landlord covers any extra cost {cite}.",
        f"Yes, as long as the tenant tells Fernhill first {cite}.",
        f"No, the lease forbids it {cite}.",
    ]
    return random_source.choice(answers)


def bad_answer(kind, lease, random_source, retrieved):
    """An answer that is NOT grounded in its citations. Returns (answer, fault number or 0)."""
    if kind in ("business", "paint"):
        return unsupported_claim(kind, lease, random_source, retrieved), 5
    if kind == "renewal" and lease.meta["notice_phrase"] == "not_less_than":
        return dropped_limit_answer(lease, random_source), 3
    answer = wrong_money_answer(kind, lease, random_source)
    if answer is None:
        answer = wrong_permission_answer(kind, lease, random_source)
    if answer is None:
        answer = wrong_guess_answer(lease, random_source, retrieved)
    return answer, 0


@dataclass
class DeskRequest:
    """One question put to the lease desk, and how the rule-written reply should behave."""

    question: dict
    lease: Lease
    random_source: random.Random
    release: str


def bad_answer_chance(kind: str, lease: Lease) -> float:
    """How often the desk answers badly when it found the right clauses."""
    meta = lease.meta
    if meta["template"] == NEW_TEMPLATE:
        return 0.75
    if kind == "renewal" and meta["notice_phrase"] == "not_less_than":
        return 0.6
    if kind == "rent" and meta["amendment"]:
        return 0.5
    return 0.2


def bad_reply(request: DeskRequest, retrieved: list[str]) -> tuple:
    kind = request.question["kind"]
    answer, fault = bad_answer(kind, request.lease, request.random_source, retrieved)
    return answer, False, fault


def choose_reply(request: DeskRequest, retrieved: list[str]) -> tuple:
    """Returns the answer, whether it is grounded, and its fault number (0 for none)."""
    question = request.question
    if not question["gold"]:
        # The shorter prompt loses the instruction to abstain, so it always guesses.
        guesses = request.release == "shorter-prompt" or request.random_source.random() < 0.3
        if guesses:
            return bad_reply(request, retrieved)
        return lease_desk.ABSTAIN, True, 0
    found_every_gold_clause = all(gold in retrieved for gold in question["gold"])
    if not found_every_gold_clause:
        return lease_desk.ABSTAIN, True, 0
    chance = bad_answer_chance(question["kind"], request.lease)
    if request.random_source.random() < chance:
        return bad_reply(request, retrieved)
    return good_answer(question["kind"], request.lease), True, 0


def desk_run(question, lease, random_source, release="live"):
    """One lease desk run: real retrieval, a reply written by rule, the truth about it."""
    found = retrieval.search(lease.meta["id"], question["question"], 5)
    retrieved = [clause["id"] for clause in found]
    request = DeskRequest(question, lease, random_source, release)
    answer, grounded, fault = choose_reply(request, retrieved)
    return {
        "retrieved": retrieved,
        "answer": answer,
        "cited": lease_desk.cited(answer),
        "grounded": grounded,
        "fault": fault,
        "abstained": answer == lease_desk.ABSTAIN,
        "should_abstain": not question["gold"],
        "messages": lease_desk.messages(question["question"], found),
    }


def critique(run, verdict):
    if verdict == "pass":
        if run["abstained"]:
            return "The answer makes no claim, so nothing is unsupported."
        return "Every claim in the answer matches the cited clause."
    if run["fault"] == 3:
        return "The answer drops the limit 'not less than' that the renewal clause states."
    if run["fault"] == 5:
        return "The cited clause says nothing about this, so the claim is unsupported."
    return "The answer states a term that the cited clause does not say."


# ---------------------------------------------------------------- the world as main builds it


def replay_entry(role, messages, reply, trial):
    return {"key": llm.key(role, messages, trial), "role": role, "trial": trial, "reply": reply}


class Replay:
    """The model replies recorded for replay, one list for each file in world/replay/."""

    def __init__(self):
        self.files = {"abstractor": [], "lease_desk": [], "judge": [], "agent": [], "models": []}

    def record(self, file, role, messages, reply):
        self.files[file].append(replay_entry(role, messages, reply, 1))

    def record_agent(self, messages, reply, trial):
        self.files["agent"].append(replay_entry("smart", messages, reply, trial))

    def write(self):
        for name, rows in self.files.items():
            paths.write_jsonl(paths.REPLAY / f"{name}.jsonl", rows)


@dataclass
class World:
    """Everything main has built so far, handed from one stage to the next.

    Each stage fills in the fields it makes; later stages read them.
    """

    metas: list[dict]
    keys: dict[str, dict]
    random_source: random.Random
    replay: Replay
    planted: list[dict] = field(default_factory=list)
    golden: list[str] = field(default_factory=list)
    gate: list[str] = field(default_factory=list)
    review: list[str] = field(default_factory=list)
    gate_amended: list[str] = field(default_factory=list)
    live_amend_wrong: list[str] = field(default_factory=list)
    step_drop: list[str] = field(default_factory=list)
    lease_faults: dict[str, set] = field(default_factory=dict)
    first_output: dict[str, tuple] = field(default_factory=dict)
    missed_step: list[str] = field(default_factory=list)
    pet_from: dict[str, str] = field(default_factory=dict)
    ledger: list[dict] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    desk: list[dict] = field(default_factory=list)
    desk_truth: list[dict] = field(default_factory=list)
    truth: dict[str, dict] = field(default_factory=dict)
    split: dict[str, str] = field(default_factory=dict)
    judge: "JudgeVerdicts | None" = None
    cheaper_extra: list[str] = field(default_factory=list)
    flaky: str = ""
    tasks: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self.by_id = {meta["id"]: meta for meta in self.metas}
        self.evals = [meta for meta in self.metas if meta["corpus"] == "eval"]
        self.amended = [meta["id"] for meta in self.evals if meta["amendment"]]
        self.commercial = [meta["id"] for meta in self.evals if meta["lease_type"] == "commercial"]

    def lease(self, lease_id: str) -> Lease:
        return Lease(self.by_id[lease_id], self.keys[lease_id])

    @property
    def pet_conflict(self) -> list[str]:
        return list(self.pet_from)


def planted_fault(fault: int, system: str, ref: str, detail: str) -> dict:
    return {"id": f"F{fault}-{ref}", "fault": fault, "system": system, "ref": ref, "detail": detail}


def reset_output_folders():
    if paths.DATA.exists():
        shutil.rmtree(paths.DATA)
    if paths.REPLAY.exists():
        shutil.rmtree(paths.REPLAY)
    paths.LEASES.mkdir(parents=True)
    paths.REPLAY.mkdir(parents=True)


def make_all_leases():
    buildings, units = make_buildings()
    free_units = list(units)
    metas, keys = [], {}
    for number in range(1, 131):
        meta, key = make_lease(number, buildings, free_units)
        metas.append(meta)
        keys[meta["id"]] = key
    return buildings, units, metas, keys


def write_leases(buildings, units, metas, keys):
    for meta in metas:
        text = lease_text(meta, keys[meta["id"]])
        (paths.LEASES / f"{meta['id']}.md").write_text(text)
    paths.write_jsonl(paths.DATA / "buildings.jsonl", buildings)
    paths.write_jsonl(paths.DATA / "units.jsonl", units)
    paths.write_jsonl(paths.DATA / "leases.jsonl", metas)
    key_rows = [{"lease_id": lease_id, "abstract": keys[lease_id]} for lease_id in keys]
    paths.write_jsonl(paths.DATA / "keys.jsonl", key_rows)


# ---------------------------------------------------------------- splits and abstractor traces


def choose_splits(world: World) -> None:
    """Splits the eval leases: golden for Part 2, gate for Part 4, and the rest for review."""
    shuffle = world.random_source.shuffle
    amended = list(world.amended)
    shuffle(amended)
    commercial = [lease_id for lease_id in world.commercial if lease_id not in amended]
    shuffle(commercial)
    others = [
        meta["id"]
        for meta in world.evals
        if meta["id"] not in amended and meta["id"] not in commercial
    ]
    shuffle(others)
    world.golden = sorted(amended[:10] + commercial[:3] + others[:27])
    world.gate = sorted(amended[10:28] + commercial[3:7] + others[27:55])
    world.review = sorted(
        meta["id"]
        for meta in world.evals
        if meta["id"] not in world.golden and meta["id"] not in world.gate
    )


def choose_abstractor_faults(world: World) -> None:
    """Picks the leases the live abstractor gets wrong every time it reads them."""
    world.gate_amended = [lease_id for lease_id in world.gate if lease_id in world.amended]
    rest_amended = [
        lease_id
        for lease_id in world.amended
        if lease_id not in world.golden and lease_id not in world.gate
    ]
    world.live_amend_wrong = sorted(world.gate_amended[:5] + rest_amended[:2])
    prose_residential = [
        meta["id"]
        for meta in world.evals
        if meta["step_style"] == "prose" and meta["lease_type"] == "residential"
    ]
    world.step_drop = sorted(
        lease_id for lease_id in prose_residential if random_for("drop", lease_id).random() < 0.4
    )


def plant_abstractor_faults(world: World) -> None:
    choose_abstractor_faults(world)
    world.lease_faults = {meta["id"]: set() for meta in world.metas}
    for lease_id in world.live_amend_wrong:
        world.lease_faults[lease_id].add("amended-rent-missed")
    for lease_id in world.step_drop:
        world.lease_faults[lease_id].add("rent-step-dropped")
    for lease_id in world.live_amend_wrong:
        detail = "the live abstractor keeps the original rent and misses Amendment No. 1"
        world.planted.append(planted_fault(1, "abstractor", lease_id, detail))
    for lease_id in world.step_drop:
        detail = "the rent step is written in prose and the live abstractor drops it"
        world.planted.append(planted_fault(2, "abstractor", lease_id, detail))


def abstractor_trace(trace_id: str, lease: Lease, abstract: dict) -> dict:
    meta = lease.meta
    amendments = meta["amendments"]
    model_span = {
        "name": "llm",
        "role": "fast",
        "input_tokens": 1400 + 120 * amendments,
        "output_tokens": 310,
    }
    return {
        "trace_id": trace_id,
        "system": "abstractor",
        "release": "live",
        "lease_id": meta["id"],
        "unit": meta["unit"],
        "building": meta["building"],
        "lease_type": meta["lease_type"],
        "template": meta["template"],
        "amendments": amendments,
        "output": abstract,
        "spans": [
            {"name": "read_document", "documents": 1 + amendments},
            model_span,
            {"name": "write_abstract", "table": "leases"},
        ],
    }


def write_abstractor_labels(labels: list[dict]) -> None:
    paths.LABELS.mkdir(parents=True, exist_ok=True)
    with open(paths.LABELS / "abstractor.csv", "w", newline="") as labels_file:
        writer = csv.writer(labels_file)
        writer.writerow(["trace_id", "verdict"] + list(MODES))
        for label in labels:
            flags = [1 if mode in label["modes"] else 0 for mode in MODES]
            writer.writerow([label["trace_id"], label["verdict"]] + flags)
    modes_text = json.dumps(MODES, indent=2) + "\n"
    (paths.LABELS / "abstractor_modes.json").write_text(modes_text)


def write_abstractor_traces(world: World) -> list[dict]:
    """Abstractor traces: 300 runs over the 120 eval leases, with Dana's label for each."""
    eval_ids = [meta["id"] for meta in world.evals]
    twice_each = [lease_id for lease_id in eval_ids for _ in range(2)]
    visits = sorted(twice_each + world.random_source.sample(eval_ids, 60))
    traces, labels = [], []
    for number, lease_id in enumerate(visits, 1):
        trace_id = f"abs-{number:04d}"
        lease = world.lease(lease_id)
        draws = random_for("trace", trace_id)
        abstract, modes = abstract_with_faults(lease, draws, world.lease_faults[lease_id])
        world.first_output.setdefault(lease_id, (abstract, trace_id))
        traces.append(abstractor_trace(trace_id, lease, abstract))
        verdict = "fail" if modes else "pass"
        labels.append({"trace_id": trace_id, "verdict": verdict, "modes": modes})
        if "notice-days-wrong-clause" in modes:
            detail = (
                "renewal notice is 'not less than N days'; "
                "the abstract takes days from another clause"
            )
            world.planted.append(planted_fault(3, "abstractor", trace_id, detail))
    paths.TRACES.mkdir(parents=True, exist_ok=True)
    paths.write_jsonl(paths.TRACES / "abstractor.jsonl", traces)
    write_abstractor_labels(labels)
    return traces


def write_system_of_record(world: World) -> None:
    """The system of record holds what the live abstractor wrote, faults and all."""
    rows = []
    for meta in world.metas:
        lease_id = meta["id"]
        if meta["corpus"] == "eval":
            abstract, trace_id = world.first_output[lease_id]
            written_by = f"abstractor ({trace_id})"
        else:
            abstract = world.keys[lease_id]
            written_by = "lease admin team"
        rows.append({"lease_id": lease_id, "abstract": abstract, "written_by": written_by})
        reply = leases.dumps(abstract)
        world.replay.record("abstractor", "fast", abstractor.messages(lease_id), reply)
    paths.write_jsonl(paths.DATA / "system_of_record.jsonl", rows)


# ---------------------------------------------------------------- the ledger


def rent_for(lease: Lease, month: str) -> int:
    """The rent the lease sets for a month, after any amendment and rent steps."""
    rent = lease.meta["original_rent"]
    amendment = lease.meta["amendment"]
    if amendment and month >= amendment["effective"][:7]:
        rent = amendment["monthly_rent"]
    for step in lease.key["rent_steps"]:
        if month >= step["effective"][:7]:
            rent = step["monthly_rent"]
    return rent


def first_step_in_window(key: dict) -> bool:
    steps = key["rent_steps"]
    return bool(steps) and steps[0]["effective"][:7] <= WINDOW[-1]


def choose_ledger_faults(world: World) -> None:
    """Fault 6: dropped rent steps go uncharged. Fault 4: a pet fee on a lease that bans pets."""
    world.missed_step = sorted(
        lease_id for lease_id in world.step_drop if first_step_in_window(world.keys[lease_id])
    )
    no_pets = [
        meta["id"]
        for meta in world.evals
        if meta["lease_type"] == "residential"
        and not world.keys[meta["id"]]["pets_allowed"]
        and meta["id"] not in world.missed_step
    ]
    pet_conflict = sorted(world.random_source.sample(no_pets, 5))
    for lease_id in pet_conflict:
        world.pet_from[lease_id] = WINDOW[world.random_source.randint(2, 7)]


def months_in_term(key: dict) -> list[str]:
    return [month for month in WINDOW if key["start_date"][:7] <= month <= key["end_date"][:7]]


def late_fee_cents(key: dict, rent: int) -> int:
    late_fee = key["late_fee"]
    if late_fee["kind"] == "flat":
        return late_fee["value"]
    return int(rent * late_fee["value"] / 100)


@dataclass
class LedgerMonth:
    lease_id: str
    month: str

    def row(self, kind: str, amount_cents: int, note: str) -> dict:
        return {
            "lease_id": self.lease_id,
            "month": self.month,
            "kind": kind,
            "amount_cents": amount_cents,
            "note": note,
        }


def ledger_month_rows(world: World, lease: Lease, month: str, late_random) -> list[dict]:
    """One month of charges for a lease, and the tenant's payment that settles them."""
    lease_id = lease.meta["id"]
    billing = LedgerMonth(lease_id, month)
    rent = rent_for(lease, month)
    if lease_id in world.missed_step:
        rent = lease.meta["original_rent"]
    rows = [billing.row("rent", rent, "monthly rent")]
    if lease.key["pets_allowed"]:
        rows.append(billing.row("pet_fee", lease.key["pet_fee"], "monthly pet fee"))
    if lease_id in world.pet_from and month >= world.pet_from[lease_id]:
        rows.append(billing.row("pet_fee", 3500, "monthly pet fee"))
    if late_random.random() < 0.05:
        rows.append(billing.row("late_fee", late_fee_cents(lease.key, rent), "late charge"))
    paid = sum(row["amount_cents"] for row in rows)
    rows.append(billing.row("payment", -paid, "tenant payment"))
    return rows


def write_ledger(world: World) -> None:
    """Twelve months of charges. Faults 4 and 6 live here."""
    choose_ledger_faults(world)
    for meta in world.evals:
        lease = world.lease(meta["id"])
        late_random = random.Random(f"ledger-{meta['id']}")
        for month in months_in_term(lease.key):
            world.ledger.extend(ledger_month_rows(world, lease, month, late_random))
    paths.write_jsonl(paths.DATA / "ledger.jsonl", world.ledger)
    for lease_id in world.pet_conflict:
        detail = f"pets are banned but the ledger charges a pet fee from {world.pet_from[lease_id]}"
        world.planted.append(planted_fault(4, "ledger", lease_id, detail))
    for lease_id in world.missed_step:
        detail = "the rent step was never charged because the abstract dropped it"
        world.planted.append(planted_fault(6, "ledger", lease_id, detail))


# ---------------------------------------------------------------- questions and the lease desk

QUESTION_PLAN = (
    ["renewal"] * 10
    + ["rent"] * 10
    + ["pets"] * 8
    + ["late"] * 7
    + ["sublet"] * 6
    + ["water"] * 6
    + ["parking"] * 6
    + ["deposit"] * 6
    + ["early"] * 9
    + ["business"] * 6
    + ["paint"] * 6
)


def question_pool(world: World, kind: str, number: int) -> list[dict]:
    """Renewal and rent questions lean towards the leases whose wording trips the desk up."""
    if kind == "renewal":
        return [
            meta
            for meta in world.evals
            if world.keys[meta["id"]]["renewal_option"]
            and (meta["notice_phrase"] == "not_less_than" or number % 3 == 0)
        ]
    if kind == "rent":
        return [meta for meta in world.evals if meta["amendment"] or number % 5 == 0]
    return world.evals


def make_question(number: int, kind: str, meta: dict) -> dict:
    text, gold_clauses = QUESTIONS[kind]
    lease_id = meta["id"]
    gold = [
        f"{lease_id}-{clause}" for clause in gold_clauses if clause != "a01" or meta["amendment"]
    ]
    if kind == "rent" and meta["amendment"]:
        gold = [f"{lease_id}-a01"]
    return {
        "id": f"q{number:03d}",
        "lease_id": lease_id,
        "kind": kind,
        "question": text.format(u=meta["unit"], b=meta["building"]),
        "gold": gold,
        "answerable": bool(gold),
    }


def write_questions(world: World) -> None:
    """80 staff questions on eval leases, never the same kind twice on one lease if avoidable."""
    used = set()
    for number, kind in enumerate(QUESTION_PLAN, 1):
        pool = question_pool(world, kind, number)
        unused = [meta for meta in pool if (meta["id"], kind) not in used]
        meta = world.random_source.choice(unused or world.evals)
        used.add((meta["id"], kind))
        world.questions.append(make_question(number, kind, meta))
    paths.write_jsonl(paths.DATA / "questions.jsonl", world.questions)


def desk_trace(trace_id: str, question: dict, run: dict, extra: dict | None = None) -> dict:
    trace = {"trace_id": trace_id, "system": "lease_desk", "release": "live"}
    trace.update(extra or {})
    trace.update(
        {
            "question_id": question["id"],
            "lease_id": question["lease_id"],
            "question": question["question"],
            "retrieved": run["retrieved"],
            "answer": run["answer"],
            "cited": run["cited"],
        }
    )
    return trace


def truth_row(trace_id: str, run: dict) -> dict:
    return {
        "trace_id": trace_id,
        "grounded": run["grounded"],
        "fault": run["fault"],
        "abstained": run["abstained"],
        "should_abstain": run["should_abstain"],
    }


def plant_desk_fault(world: World, trace_id: str, run: dict) -> None:
    if run["fault"] == 3:
        detail = "drops 'not less than' from the renewal notice"
    elif run["fault"] == 5:
        detail = "answers a question the lease does not answer"
    else:
        return
    world.planted.append(planted_fault(run["fault"], "lease_desk", trace_id, detail))


def record_first_answers(world: World) -> None:
    """The finished lease desk replays its first recorded answer for each question."""
    for question in world.questions:
        first = next(trace for trace in world.desk if trace["question_id"] == question["id"])
        found = retrieval.search(question["lease_id"], question["question"], 5)
        messages = lease_desk.messages(question["question"], found)
        world.replay.record("lease_desk", "fast", messages, first["answer"])


def write_desk_runs(world: World) -> None:
    """Lease desk: 320 recorded runs on the eval corpus, four for each question."""
    questions_by_id = {question["id"]: question for question in world.questions}
    order = [question["id"] for question in world.questions for _ in range(4)]
    for number, question_id in enumerate(order, 1):
        question = questions_by_id[question_id]
        lease = world.lease(question["lease_id"])
        run = desk_run(question, lease, random_for("desk", number))
        trace_id = f"desk-{number:04d}"
        world.desk.append(desk_trace(trace_id, question, run))
        world.desk_truth.append(truth_row(trace_id, run))
        plant_desk_fault(world, trace_id, run)
    record_first_answers(world)
    paths.write_jsonl(paths.TRACES / "lease_desk.jsonl", world.desk)
    world.truth = {row["trace_id"]: row for row in world.desk_truth}


# ---------------------------------------------------------------- Dana's labels and the judge


def assign_splits(passes: list[str], fails: list[str]) -> dict[str, str]:
    """Takes equal passes and fails for each split: 10 each for train, 25 each for dev and test."""
    split = {}
    for name, size in (("train", 10), ("dev", 25), ("test", 25)):
        for _ in range(size):
            split[passes.pop()] = name
            split[fails.pop()] = name
    return split


def write_grounded_csv(world: World) -> None:
    with open(paths.LABELS / "grounded.csv", "w", newline="") as labels_file:
        writer = csv.writer(labels_file)
        writer.writerow(["trace_id", "split", "label"])
        for trace in world.desk:
            trace_id = trace["trace_id"]
            if trace_id not in world.split:
                continue
            label = "pass" if world.truth[trace_id]["grounded"] else "fail"
            writer.writerow([trace_id, world.split[trace_id], label])


def write_grounded_labels(world: World) -> None:
    """Dana's grounded labels: 60 pass and 60 fail, split train 20, dev 50, test 50."""
    # Dana labels each distinct answer once, so a repeated run never sits in two splits.
    distinct = {}
    for trace in world.desk:
        distinct.setdefault((trace["question_id"], trace["answer"]), trace["trace_id"])
    unique_ids = sorted(distinct.values())
    passes = [trace_id for trace_id in unique_ids if world.truth[trace_id]["grounded"]]
    fails = [trace_id for trace_id in unique_ids if not world.truth[trace_id]["grounded"]]
    world.random_source.shuffle(passes)
    world.random_source.shuffle(fails)
    assert len(fails) >= 60, f"only {len(fails)} ungrounded runs; raise the fault rates"
    world.split = assign_splits(passes, fails)
    write_grounded_csv(world)
    paths.write_jsonl(paths.LABELS / "lease_desk_truth.jsonl", world.desk_truth)


@dataclass
class JudgeMisses:
    """How many verdicts the judge gets wrong: an exact count (int) or a share of runs (float)."""

    on_passes: int | float
    on_fails: int | float


def pick_misses(draws: random.Random, trace_ids: list[str], miss: int | float) -> list[str]:
    if isinstance(miss, int):
        return draws.sample(trace_ids, miss)
    return [trace_id for trace_id in trace_ids if draws.random() < miss]


def opposite(verdict: str) -> str:
    if verdict == "pass":
        return "fail"
    return "pass"


class JudgeVerdicts:
    """The finished judge's recorded verdicts.

    The same prompt always gets the same verdict, as a model does at temperature 0.
    """

    def __init__(self, truth: dict, runs_by_id: dict):
        self.truth = truth
        self.runs_by_id = runs_by_id
        self.by_content = {}
        self.verdicts = {}

    def content(self, trace_id: str) -> tuple:
        run = self.runs_by_id[trace_id]
        return (run["question"], run["answer"], tuple(run["cited"]))

    def verdict_for(self, trace_id: str, flipped: bool) -> str:
        content = self.content(trace_id)
        if content in self.by_content:
            return self.by_content[content]
        verdict = "pass" if self.truth[trace_id]["grounded"] else "fail"
        if flipped:
            verdict = opposite(verdict)
        self.by_content[content] = verdict
        return verdict

    def decide(self, trace_ids: list[str], misses: JudgeMisses, seed: int) -> None:
        """Gets a set share of verdicts wrong, so the judge's TPR and TNR are known."""
        draws = random.Random(seed)
        seen = [trace_id for trace_id in trace_ids if self.content(trace_id) in self.by_content]
        for trace_id in seen:
            self.verdicts[trace_id] = self.by_content[self.content(trace_id)]
        fresh = [trace_id for trace_id in trace_ids if trace_id not in seen]
        passes = [trace_id for trace_id in fresh if self.truth[trace_id]["grounded"]]
        fails = [trace_id for trace_id in fresh if not self.truth[trace_id]["grounded"]]
        flipped = set(pick_misses(draws, passes, misses.on_passes))
        flipped |= set(pick_misses(draws, fails, misses.on_fails))
        for trace_id in fresh:
            self.verdicts[trace_id] = self.verdict_for(trace_id, trace_id in flipped)


def record_judge(world: World, trace: dict) -> None:
    trace_id = trace["trace_id"]
    cited = [
        {"id": clause["id"], "text": clause["text"]}
        for clause in leases.clauses(trace["lease_id"])
        if clause["id"] in trace["cited"]
    ]
    verdict = world.judge.verdicts[trace_id]
    reply = json.dumps({"critique": critique(world.truth[trace_id], verdict), "verdict": verdict})
    messages = judge.messages(trace["question"], trace["answer"], cited)
    world.replay.record("judge", "judge", messages, reply)


def ids_in_split(world: World, name: str) -> list[str]:
    return [trace_id for trace_id, split in world.split.items() if split == name]


def record_desk_verdicts(world: World) -> None:
    """The judge's verdicts: TPR 0.92 and TNR 0.88 on test, near that elsewhere."""
    runs_by_id = {trace["trace_id"]: trace for trace in world.desk}
    world.judge = JudgeVerdicts(world.truth, runs_by_id)
    world.judge.decide(ids_in_split(world, "test"), JudgeMisses(2, 3), 11)
    world.judge.decide(ids_in_split(world, "dev"), JudgeMisses(2, 3), 12)
    world.judge.decide(ids_in_split(world, "train"), JudgeMisses(1, 1), 13)
    unlabelled = [trace["trace_id"] for trace in world.desk if trace["trace_id"] not in world.split]
    world.judge.decide(unlabelled, JudgeMisses(0.08, 0.12), 14)
    for trace in world.desk:
        record_judge(world, trace)


# ---------------------------------------------------------------- production


def production_question(meta: dict, kind: str) -> dict:
    text, _ = QUESTIONS[kind]
    lease_id = meta["id"]
    gold = f"{lease_id}-c12" if kind == "renewal" else f"{lease_id}-c04"
    return {
        "id": f"p-{lease_id}-{kind}",
        "lease_id": lease_id,
        "kind": kind,
        "question": text.format(u=meta["unit"], b=meta["building"]),
        "gold": [gold],
        "answerable": True,
    }


def pick_production_question(world: World, new_questions: list, batch: int, position: int):
    # From batch 5 on, the first 16 runs of each batch ask about leases on the new template.
    if batch >= 5 and position < 16:
        return new_questions[(batch * 16 + position) % len(new_questions)]
    return world.questions[(batch * 37 + position * 11) % len(world.questions)]


def production_run(world: World, question: dict, batch: int, position: int) -> dict:
    lease = world.lease(question["lease_id"])
    run = desk_run(question, lease, random_for("prod", batch, position))
    trace_id = f"prod-{batch}-{position + 1:02d}"
    world.truth[trace_id] = truth_row(trace_id, run)
    extra = {"batch": batch, "building": lease.meta["building"]}
    return desk_trace(trace_id, question, run, extra)


def write_production_runs(world: World) -> list[dict]:
    """Production: 7 batches of 40 lease desk runs. Batch 5 brings the new lease template."""
    new_questions = [
        production_question(meta, kind)
        for meta in world.metas
        if meta["corpus"] == "production"
        for kind in ("renewal", "rent")
    ]
    production = []
    for batch in range(1, 8):
        for position in range(40):
            question = pick_production_question(world, new_questions, batch, position)
            production.append(production_run(world, question, batch, position))
    world.judge.runs_by_id.update({trace["trace_id"]: trace for trace in production})
    production_ids = [trace["trace_id"] for trace in production]
    world.judge.decide(production_ids, JudgeMisses(0.08, 0.12), 15)
    for trace in production:
        record_judge(world, trace)
    paths.write_jsonl(paths.TRACES / "lease_desk_production.jsonl", production)
    production_truth = [world.truth[trace_id] for trace_id in production_ids]
    paths.write_jsonl(paths.LABELS / "production_truth.jsonl", production_truth)
    return production


# ---------------------------------------------------------------- candidate releases

RELEASES = {
    "live": "What runs today.",
    "cheaper-model": "The abstractor moves to a cheaper model to cut cost per lease.",
    "shorter-prompt": "The lease desk prompt is cut to half its length to save tokens.",
    "clause-ids-in-answer": (
        "The lease desk puts clause ids in a fixed place at the end of each answer."
    ),
}


def choose_release_faults(world: World) -> None:
    world.cheaper_extra = [
        lease_id for lease_id in world.gate_amended if lease_id not in world.live_amend_wrong
    ][:9]
    world.flaky = next(
        lease_id
        for lease_id in world.gate
        if lease_id not in world.amended and world.keys[lease_id]["lease_type"] == "residential"
    )
    for lease_id in world.cheaper_extra:
        detail = "the cheaper model misses Amendment No. 1 on this lease in every trial"
        world.planted.append(planted_fault(7, "release:cheaper-model", lease_id, detail))


def release_abstract(world: World, release: str, lease_id: str, trial: int) -> dict:
    lease = world.lease(lease_id)
    faults = set(world.lease_faults[lease_id])
    noise = 1.0
    if release == "cheaper-model":
        # The cheaper model slips more often, and misses amendments the live model reads.
        noise = 1.6
        if lease_id in world.cheaper_extra:
            faults.add("amended-rent-missed")
    draws = random_for("release", lease_id, trial)
    abstract, _ = abstract_with_faults(lease, draws, faults, noise)
    cheaper = release == "cheaper-model"
    if cheaper and random_for("cheap-park", lease_id, trial).random() < 0.05:
        abstract["parking"] = not abstract["parking"]
    if release == "clause-ids-in-answer" and lease_id == world.flaky and trial == 2:
        # One wrong trial on one gate lease, so the gate meets a result that is not repeatable.
        abstract["monthly_rent"] = lease.key["monthly_rent"] + 10000
    return abstract


def release_abstract_rows(world: World, release: str) -> list[dict]:
    rows = []
    for meta in world.evals:
        for trial in (1, 2, 3):
            abstract = release_abstract(world, release, meta["id"], trial)
            rows.append(
                {
                    "release": release,
                    "kind": "abstract",
                    "lease_id": meta["id"],
                    "trial": trial,
                    "output": abstract,
                }
            )
    return rows


def release_desk_rows(world: World, release: str) -> list[dict]:
    rows = []
    for question in world.questions:
        lease = world.lease(question["lease_id"])
        for trial in (1, 2, 3):
            draws = random_for("release-desk", question["id"], trial)
            run = desk_run(question, lease, draws, release=release)
            output = {"answer": run["answer"], "cited": run["cited"], "retrieved": run["retrieved"]}
            rows.append(
                {
                    "release": release,
                    "kind": "desk",
                    "question_id": question["id"],
                    "lease_id": lease.meta["id"],
                    "trial": trial,
                    "output": output,
                }
            )
    return rows


def write_releases(world: World) -> None:
    """Releases: 3 trials per eval lease and per question, for four candidate releases."""
    choose_release_faults(world)
    paths.RELEASES.mkdir(parents=True, exist_ok=True)
    for release, change in RELEASES.items():
        rows = release_abstract_rows(world, release)
        rows += release_desk_rows(world, release)
        paths.write_jsonl(paths.RELEASES / f"{release}.jsonl", rows)
        manifest = json.dumps({"name": release, "change": change}, indent=2) + "\n"
        (paths.RELEASES / f"{release}.json").write_text(manifest)


# ---------------------------------------------------------------- agent tasks


def steps_due(key: dict) -> list[dict]:
    """Rent steps that start in the next two months."""
    return [step for step in key["rent_steps"] if step["effective"][:7] in ("2026-11", "2026-12")]


def review_prompt(world: World, lease_id: str, instruction: str) -> str:
    meta = world.by_id[lease_id]
    return (
        f"Monthly rent review for lease {lease_id} (unit {meta['unit']} at "
        f"{meta['building']}). {instruction}"
    )


def task_entry(kind: str, lease_id: str, prompt: str, expect: dict) -> dict:
    return {"kind": kind, "lease_id": lease_id, "prompt": prompt, "expect": expect}


def missed_step_tasks(world: World) -> list[dict]:
    tasks = []
    instruction = (
        "Check that the ledger charges the rent the lease sets. Propose a charge for anything owed."
    )
    for lease_id in world.missed_step[:5]:
        key = world.keys[lease_id]
        step = key["rent_steps"][0]
        months = [
            month
            for month in WINDOW
            if month >= step["effective"][:7] and month <= key["end_date"][:7]
        ]
        shortfall = step["monthly_rent"] - world.by_id[lease_id]["original_rent"]
        expect = {"charge_cents": shortfall * len(months), "notice": None}
        prompt = review_prompt(world, lease_id, instruction)
        tasks.append(task_entry("missed-step", lease_id, prompt, expect))
    return tasks


def pet_fee_tasks(world: World) -> list[dict]:
    tasks = []
    instruction = (
        "Check every fee in the ledger against the lease. Propose a credit for "
        "any fee the lease does not allow."
    )
    for lease_id in world.pet_conflict:
        charged = sum(
            row["amount_cents"]
            for row in world.ledger
            if row["lease_id"] == lease_id and row["kind"] == "pet_fee"
        )
        expect = {"charge_cents": -charged, "notice": None}
        prompt = review_prompt(world, lease_id, instruction)
        tasks.append(task_entry("pet-fee-conflict", lease_id, prompt, expect))
    return tasks


def rent_notice_tasks(world: World) -> list[dict]:
    pool = [
        meta["id"]
        for meta in world.evals
        if steps_due(world.keys[meta["id"]]) and meta["id"] not in world.step_drop
    ]
    instruction = (
        "If the rent changes in the next two months, draft the rent increase "
        "notice with the new monthly rent."
    )
    tasks = []
    for lease_id in sorted(world.random_source.sample(pool, min(5, len(pool)))):
        step = steps_due(world.keys[lease_id])[0]
        expect = {
            "charge_cents": None,
            "notice": "rent_increase",
            "notice_amount": usd(step["monthly_rent"]),
        }
        prompt = review_prompt(world, lease_id, instruction)
        tasks.append(task_entry("rent-step-notice", lease_id, prompt, expect))
    return tasks


def renewal_pool(world: World) -> list[str]:
    """Residential leases ending soon that have no other planted fault to confuse the task."""
    return [
        meta["id"]
        for meta in world.evals
        if world.keys[meta["id"]]["renewal_option"]
        and meta["lease_type"] == "residential"
        and world.keys[meta["id"]]["end_date"][:7] in ("2026-12", "2027-01")
        and meta["id"] not in world.missed_step
        and meta["id"] not in world.pet_conflict
    ]


def renewal_tasks(world: World, count: int) -> list[dict]:
    pool = renewal_pool(world)
    instruction = "If the renewal window is open, draft the renewal offer notice."
    expect = {"charge_cents": None, "notice": "renewal_offer", "notice_amount": None}
    tasks = []
    for lease_id in sorted(world.random_source.sample(pool, min(count, len(pool)))):
        prompt = review_prompt(world, lease_id, instruction)
        tasks.append(task_entry("renewal-offer", lease_id, prompt, dict(expect)))
    return tasks


def write_agent_tasks(world: World) -> None:
    """20 agent tasks, each run in 4 recorded trials."""
    tasks = missed_step_tasks(world) + pet_fee_tasks(world)
    tasks += rent_notice_tasks(world)
    tasks += renewal_tasks(world, 20 - len(tasks))
    world.tasks = [{"id": f"task-{number:02d}", **task} for number, task in enumerate(tasks, 1)]
    assert len(world.tasks) == 20, f"{len(world.tasks)} agent tasks; widen the pools"
    paths.write_jsonl(paths.DATA / "agent_tasks.jsonl", world.tasks)


# ---------------------------------------------------------------- agent runs

# Which trial goes wrong, and how. Trials 1 to 3 give pass^3; trial 4 adds history for the
# failure map.
AGENT_FAULT_PLAN = {
    ("task-01", 2): "trust_abstract",
    ("task-02", 1): "trust_abstract",
    ("task-03", 3): "post_charge",
    ("task-04", 4): "trust_abstract",
    ("task-05", 2): "wrong_amount",
    ("task-06", 3): "stopped",
    ("task-08", 4): "post_charge",
    ("task-11", 1): "wrong_lease",
    ("task-13", 4): "wrong_lease",
    ("task-16", 2): "stopped",
    ("task-18", 3): "wrong_lease",
    ("task-02", 4): "wrong_amount",
    ("task-19", 4): "stopped",
}

SEARCH_QUERIES = {
    "missed-step": "rent increases anniversary",
    "pet-fee-conflict": "pets animals fee",
    "rent-step-notice": "rent increases",
    "renewal-offer": "renewal notice",
}

RENEWAL_BODY = (
    "Your lease can be renewed. Please tell us within the notice period in your lease "
    "if you wish to renew."
)


def action(**fields) -> str:
    """One model reply: a tool call or a final answer, as JSON."""
    return json.dumps(fields, sort_keys=True)


def charge_replies(task: dict, how: str) -> list[str]:
    lease_id = task["lease_id"]
    amount = task["expect"]["charge_cents"]
    if how == "wrong_amount":
        amount = int(amount / 3)
    if task["kind"] == "missed-step":
        reason = "rent step not charged"
    else:
        reason = "credit for pet fees the lease does not allow"
    if how == "post_charge":
        tool, verb = "post_charge", "Posted"
    else:
        tool, verb = "propose_charge", "Proposed"
    charge = {"lease_id": lease_id, "amount_cents": amount, "reason": reason}
    return [
        action(tool="get_ledger", args={"lease_id": lease_id}),
        action(tool=tool, args=charge),
        action(done=f"{verb} {usd(abs(amount))}: {reason}."),
    ]


def notice_replies(task: dict, how: str) -> list[str]:
    lease_id = task["lease_id"]
    target = lease_id
    if how == "wrong_lease":
        target = f"L{int(lease_id[1:]) % 110 + 1:03d}"
    if task["kind"] == "rent-step-notice":
        kind = "rent_increase"
        amount = task["expect"]["notice_amount"]
        body = f"Your monthly rent changes to {amount} as your lease sets out."
    else:
        kind = "renewal_offer"
        body = RENEWAL_BODY
    notice = {"lease_id": target, "kind": kind, "body": body}
    return [
        action(tool="draft_notice", args=notice),
        action(done="Drafted the notice for staff to review."),
    ]


def agent_script(task: dict, how: str) -> list[str]:
    """The replies a small model gives on this task, as JSON actions."""
    lease_id = task["lease_id"]
    replies = [action(tool="get_abstract", args={"lease_id": lease_id})]
    if how == "trust_abstract":
        done = "The abstract shows no rent change and the ledger matches it. Nothing to do."
        return replies + [
            action(tool="get_ledger", args={"lease_id": lease_id}),
            action(done=done),
        ]
    search = {"lease_id": lease_id, "query": SEARCH_QUERIES[task["kind"]]}
    replies.append(action(tool="search_lease", args=search))
    if how == "stopped":
        return replies + [action(done="I read the lease. A person should review this one.")]
    if task["kind"] in ("missed-step", "pet-fee-conflict"):
        return replies + charge_replies(task, how)
    return replies + notice_replies(task, how)


def agent_run(world: World, task: dict, trial: int, scratch: Path) -> dict:
    how = AGENT_FAULT_PLAN.get((task["id"], trial), "ok")
    replies = iter(agent_script(task, how))

    def scripted_model(messages):
        reply = next(replies)
        world.replay.record_agent(messages, reply, trial)
        return reply

    database = db.copy(scratch / f"{task['id']}-{trial}.db")
    result = agent.run(task, database, trial, complete=scripted_model)
    return {
        "trace_id": f"agent-{task['id']}-{trial}",
        "system": "agent",
        "task_id": task["id"],
        "trial": trial,
        "lease_id": task["lease_id"],
        "steps": result["steps"],
        "final": result["final"],
    }


def plant_agent_faults(world: World) -> None:
    for task in world.tasks:
        for trial in (1, 2, 3, 4):
            if AGENT_FAULT_PLAN.get((task["id"], trial)) != "post_charge":
                continue
            ref = f"agent-{task['id']}-{trial}"
            world.planted.append(planted_fault(6, "agent", ref, "posts a charge without approval"))


def write_agent_runs(world: World) -> list[dict]:
    # The agent runs against a copy of the database, so build it from the data written so far.
    paths.write_jsonl(paths.DATA / "planted_faults.jsonl", world.planted)
    db.build()
    scratch = Path(tempfile.mkdtemp())
    traces = []
    for task in world.tasks:
        for trial in (1, 2, 3, 4):
            traces.append(agent_run(world, task, trial, scratch))
    shutil.rmtree(scratch)
    paths.write_jsonl(paths.TRACES / "agent.jsonl", traces)
    plant_agent_faults(world)
    paths.write_jsonl(paths.DATA / "planted_faults.jsonl", world.planted)
    return traces


# ---------------------------------------------------------------- main


def write_closing_files(world: World) -> None:
    # One tiny call per role for `uv run models`.
    for role in ("fast", "smart", "judge"):
        world.replay.record("models", role, PING, "ok")
    demo = next(
        question
        for question in world.questions
        if question["kind"] == "rent" and question["lease_id"] in world.live_amend_wrong
    )
    split_info = {
        "golden": world.golden,
        "gate": world.gate,
        "review": world.review,
        "demo_lease": demo["lease_id"],
        "flaky_gate_lease": world.flaky,
    }
    (paths.DATA / "splits.json").write_text(json.dumps(split_info, indent=2) + "\n")
    world.replay.write()


def main():
    reset_output_folders()
    buildings, units, metas, keys = make_all_leases()
    write_leases(buildings, units, metas, keys)
    world = World(metas, keys, random.Random(SEED + 1), Replay())
    choose_splits(world)
    plant_abstractor_faults(world)
    traces = write_abstractor_traces(world)
    write_system_of_record(world)
    write_ledger(world)
    write_questions(world)
    write_desk_runs(world)
    write_grounded_labels(world)
    record_desk_verdicts(world)
    production = write_production_runs(world)
    write_releases(world)
    write_agent_tasks(world)
    agent_traces = write_agent_runs(world)
    write_closing_files(world)
    db.build()
    print(
        f"Generated {len(metas)} leases, {len(traces)} abstractor traces, "
        f"{len(world.desk)} lease desk runs, {len(production)} production runs, "
        f"{len(agent_traces)} agent runs, {len(world.planted)} planted faults."
    )


if __name__ == "__main__":
    main()
