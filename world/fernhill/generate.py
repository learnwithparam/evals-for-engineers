"""Builds the whole Fernhill world from one seed: leases, keys, ledger, traces, labels, releases, replay.

Run `uv run world generate` only when you change this file. The output is committed, so learners and CI
never need to run it. Every planted fault is written to world/data/planted_faults.jsonl.

The replies in world/replay/ are written here, by rules, so every fault is known. They stand in for a
small model's replies. Set LLM_PROVIDER and a key to see what a real model does on the same leases.
"""
import copy
import csv
import hashlib
import json
import random
import shutil
import tempfile
from datetime import date
from pathlib import Path

from . import db, leases, llm, paths
from .evals import judge as judge_mod
from .systems import abstractor, agent, lease_desk, retrieval

SEED = 2026
R = random.Random(SEED)
WINDOW = [f"{y}-{m:02d}" for y, m in [(2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]]
TODAY = date(2026, 10, 31)

STREETS = ["Alder Row", "Birch Court", "Cobble Yard", "Damson House", "Elm Terrace", "Fennel Mews", "Gorse Lane",
           "Hazel Point", "Ivy Wharf", "Juniper Hall", "Kestrel Way", "Larch Gardens", "Medlar Place", "Nettle Rise",
           "Osier Walk", "Plover House", "Quince Court", "Rowan Steps", "Sorrel Yard", "Teasel Row", "Umber Lofts",
           "Vetch Square", "Willow Bank", "Yarrow House", "Aspen Close", "Bramble Works", "Clover Mill",
           "Dunlin Court", "Eyot House", "Fernhill Arcade", "Granary Wharf"]
FIRST = ["Ana", "Ben", "Chloe", "Dev", "Ewa", "Femi", "Grace", "Hugo", "Isla", "Jon", "Kemi", "Liam", "Maya", "Nico",
         "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara", "Uma", "Vik", "Wen", "Yusuf", "Zara", "Ade", "Bea", "Cal"]
LAST = ["Ruiz", "Okafor", "Novak", "Shah", "Brennan", "Lindqvist", "Mensah", "Tanaka", "Haddad", "Kowalski",
        "Osei", "Moreau", "Fischer", "Quint", "Abara", "Delaney", "Varga", "Nakamura", "Pereira", "Sato"]
SHOPS = ["Corner Loaf Bakery", "Thimble Repairs", "Greenleaf Pharmacy", "Two Spoons Cafe", "Brightside Opticians",
         "Ledger and Quill Stationers", "Pebble Pet Supplies", "Northgate Laundry", "Kiln Pottery Studio",
         "Hearth Hardware"]
NUMWORDS = {30: "thirty", 60: "sixty", 90: "ninety", 120: "one hundred and twenty", 180: "one hundred and eighty"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def end_of_term(start: date, months: int) -> date:
    nxt = add_months(start, months)
    return date.fromordinal(nxt.toordinal() - 1)


def words(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def nth(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def usd(c: int) -> str:
    return f"${c / 100:,.2f}"


def ym(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def sub_rng(*parts) -> random.Random:
    h = hashlib.sha256(json.dumps([SEED, *parts]).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


# ---------------------------------------------------------------- buildings, units, leases

def make_buildings():
    sizes = [59] * 31
    for i in R.sample(range(31), 11):
        sizes[i] += 1
    owners = [f"{R.choice(LAST)} {R.choice(['Family Trust', 'Holdings', 'Estates', 'Partners'])}" for _ in range(60)]
    buildings, units = [], []
    for i, (name, n) in enumerate(zip(STREETS, sizes), 1):
        bid = f"B{i:02d}"
        kind = "mixed" if name in ("Fernhill Arcade", "Granary Wharf", "Clover Mill", "Umber Lofts") else "residential"
        buildings.append({"id": bid, "name": name, "address": f"{R.randint(2, 180)} {name}", "owner": owners[i - 1],
                          "units": n, "kind": kind})
        floors = (n + 5) // 6
        labels = [f"{f}{chr(65 + k)}" for f in range(1, floors + 1) for k in range(6)][:n]
        if kind == "mixed":
            labels = [f"G{k + 1}" for k in range(4)] + labels[4:]
        for lab in labels:
            units.append({"id": f"{bid}-{lab}", "building_id": bid, "label": lab,
                          "bedrooms": 0 if lab.startswith("G") else R.choice([1, 1, 2, 2, 3]),
                          "kind": "retail" if lab.startswith("G") else "flat"})
    return buildings, units


def make_lease(i, buildings, free_units):
    lid = f"L{i:03d}"
    commercial = 111 <= i <= 120
    new_template = i > 120
    amended = (i % 4 == 0 and i <= 108) or i in (112, 115, 118)
    if commercial:
        pool = [u for u in free_units if u["kind"] == "retail"]
    else:
        pool = [u for u in free_units if u["kind"] == "flat"]
    unit = R.choice(pool)
    free_units.remove(unit)
    b = next(x for x in buildings if x["id"] == unit["building_id"])
    if commercial:
        start, term = date(R.choice([2022, 2023, 2024]), R.randint(1, 12), 1), 60
        tenant = SHOPS[i - 111]
        template = "FH-COM-2018"
        rent = R.randrange(400000, 1200000, 5000)
    else:
        tenant = f"{R.choice(FIRST)} {R.choice(LAST)}"
        if new_template:
            start, term, template = date(2026, R.choice([9, 10, 11]), 1), 12, "FH-RES-2026"
        elif R.random() < 0.8 or amended:
            start, term = add_months(date(2024, 11, 1), R.randint(0, 13)), 24
            template = R.choice(["FH-RES-2019", "FH-RES-2022"])
        else:
            start, term = add_months(date(2025, 11, 1), R.randint(0, 4)), 12
            template = R.choice(["FH-RES-2019", "FH-RES-2022"])
        rent = R.randrange(115000, 340000, 2500)
    pct = 3 if commercial else R.choice([2, 3, 4])
    if commercial and not amended:
        step_style = "prose"
    elif not commercial and term == 24 and not amended and not new_template:
        step_style = R.choices(["table", "prose", "none"], [0.4, 0.35, 0.25])[0]
    else:
        step_style = "none"
    steps, cur = [], rent
    if step_style != "none":
        for k in range(12, term, 12):
            cur = int(round(cur * (100 + pct) / 100))
            steps.append({"effective": add_months(start, k).isoformat(), "monthly_rent": cur})
    amend = None
    if amended:
        eff = add_months(start, R.randint(4, 10))
        new_rent = rent + (R.randrange(5000, 20000, 2500) if not commercial else int(rent * 0.05))
        amend = {"effective": eff.isoformat(), "monthly_rent": new_rent}
    deposit = rent * 3 if commercial else int(round(rent * R.choice([1, 1.5, 2]) / 100)) * 100
    renewal = True if commercial else R.random() < 0.75
    notice_days = (R.choice([120, 180]) if commercial else R.choice([30, 60, 90])) if renewal else None
    phrase = ("not_less_than" if R.random() < 0.3 else "exact") if renewal else None
    pets = (not commercial) and R.random() < 0.45
    pet_fee = R.choice([2500, 3500, 5000]) if pets else None
    pet_deposit = 30000 if pets and R.random() < 0.5 else None
    late = {"kind": "percent", "value": 5} if commercial else {"kind": "flat", "value": R.choice([5000, 7500, 10000])}
    late_day = 10 if commercial else R.choice([3, 5])
    if commercial:
        etf = rent * 6 if R.random() < 0.3 else None
    else:
        etf = rent * 2 if R.random() < 0.5 else None
    utilities = [] if commercial else sorted(R.choice([[], ["water"], ["water", "trash"], ["trash"],
                                                      ["gas", "water", "trash"]]))
    parking = R.random() < 0.5
    sublet = True if commercial else R.random() < 0.3
    key = {
        "unit": unit["label"], "tenant": tenant, "lease_type": "commercial" if commercial else "residential",
        "start_date": start.isoformat(), "end_date": end_of_term(start, term).isoformat(),
        "monthly_rent": amend["monthly_rent"] if amend else rent, "rent_steps": steps, "deposit": deposit,
        "renewal_option": renewal, "renewal_notice_days": notice_days, "pets_allowed": pets, "pet_fee": pet_fee,
        "late_fee": late, "late_fee_after_day": late_day, "early_termination_fee": etf,
        "utilities_included": utilities, "parking": parking, "sublet_allowed": sublet,
    }
    meta = {"id": lid, "unit_id": unit["id"], "unit": unit["label"], "building": b["name"], "address": b["address"],
            "owner": b["owner"], "tenant": tenant, "lease_type": key["lease_type"], "template": template,
            "corpus": "production" if new_template else "eval", "amendments": 1 if amend else 0,
            "original_rent": rent, "step_style": step_style, "step_pct": pct, "notice_phrase": phrase,
            "pet_deposit": pet_deposit, "amendment": amend, "term_months": term}
    return meta, key


def lease_text(m, k):
    lt = m["lease_type"]
    days = k["renewal_notice_days"]
    title = "Commercial Lease" if lt == "commercial" else "Residential Lease"
    out = [f"# {title} {m['id']}", "",
           f"Fernhill Homes lease for unit {m['unit']} at {m['building']}. Template: {m['template']}.", ""]

    def clause(cid, head, body):
        out.extend([f"## {cid} {head}", "", body, ""])

    landlord = f"Fernhill Homes, as managing agent for {m['owner']}"
    clause("c01", "Parties", f"This lease is between {landlord} (\"Landlord\") and {k['tenant']} (\"Tenant\").")
    clause("c02", "Premises", f"Landlord lets to Tenant unit {m['unit']} at {m['address']} (\"the Premises\").")
    clause("c03", "Term", f"The term starts on {words(date.fromisoformat(k['start_date']))} and ends on "
                          f"{words(date.fromisoformat(k['end_date']))}.")
    clause("c04", "Rent", f"Tenant shall pay monthly rent of {usd(m['original_rent'])}, due on the first day of each "
                          f"month.")
    if m["step_style"] == "table":
        rows = "\n".join(f"| {words(date.fromisoformat(s['effective']))} | {usd(s['monthly_rent'])} |"
                         for s in k["rent_steps"])
        clause("c05", "Rent increases", f"The monthly rent changes as follows.\n\n| From | Monthly rent |\n|---|---|\n{rows}")
    elif m["step_style"] == "prose":
        clause("c05", "Rent increases", f"On each anniversary of the start date, the monthly rent shall increase by "
                                        f"{m['step_pct']}% over the rent then payable, rounded to the nearest cent.")
    else:
        clause("c05", "Rent increases", "The rent does not change during the term.")
    clause("c06", "Security deposit", f"Tenant has paid a security deposit of {usd(k['deposit'])}, held under the "
                                      f"deposit rules that apply to the Premises.")
    late = k["late_fee"]
    fee = f"{late['value']}% of the overdue amount" if late["kind"] == "percent" else usd(late["value"])
    clause("c07", "Late charges", f"If rent is not received by the {nth(k['late_fee_after_day'])} of the month, Tenant "
                                  f"shall pay a late charge of {fee}.")
    if k["utilities_included"]:
        clause("c08", "Utilities", f"Landlord pays for {' and '.join(k['utilities_included'])}. Tenant pays for all "
                                   f"other utilities.")
    else:
        clause("c08", "Utilities", "Tenant pays for all utilities.")
    if lt == "commercial":
        clause("c09", "Animals", "No animals other than assistance animals are allowed on the Premises.")
    elif k["pets_allowed"]:
        extra = f" and a one-time pet deposit of {usd(m['pet_deposit'])}" if m["pet_deposit"] else ""
        clause("c09", "Pets", f"Tenant may keep up to two pets. Tenant shall pay a pet fee of {usd(k['pet_fee'])} "
                              f"per month{extra}.")
    else:
        clause("c09", "Pets", "No pets are allowed on the Premises.")
    clause("c10", "Parking", "One parking space is included." if k["parking"] else "No parking is included.")
    if k["sublet_allowed"]:
        clause("c11", "Assignment and subletting", "Tenant may sublet the Premises with Landlord's written consent, "
                                                   "which Landlord will not withhold without good reason.")
    else:
        clause("c11", "Assignment and subletting", "Tenant may not assign this lease or sublet any part of the "
                                                   "Premises.")
    if m["template"] == "FH-RES-2026":
        if days:
            clause("c12", "Extension", f"If the Tenant wants to stay on, the Tenant can extend for a further 12 "
                                       f"months by telling Fernhill at least {days} days before the term ends.")
        else:
            clause("c12", "Extension", "This lease cannot be extended.")
    elif days:
        n = f"{NUMWORDS[days]} ({days}) days"
        when = f"not less than {n}" if m["notice_phrase"] == "not_less_than" else n
        term = "five years" if lt == "commercial" else "12 months"
        clause("c12", "Renewal", f"Tenant may renew this lease for one further term of {term} by giving written "
                                 f"notice {when} before the end of the term.")
    else:
        clause("c12", "Renewal", "This lease has no renewal option.")
    if k["early_termination_fee"]:
        clause("c13", "Early termination", f"Tenant may end this lease early by giving 60 days' written notice and "
                                           f"paying an early termination fee of {usd(k['early_termination_fee'])}.")
    else:
        clause("c13", "Early termination", "Tenant has no right to end this lease early.")
    clause("c14", "Notices", "Notices must be in writing and sent to the addresses in this lease. A posted notice "
                             "is treated as received 3 days after posting.")
    if m["amendment"]:
        a = m["amendment"]
        clause("a01", "Amendment No. 1", f"Signed by both parties. From "
                                         f"{words(date.fromisoformat(a['effective']))}, clause c04 is changed: the "
                                         f"monthly rent is {usd(a['monthly_rent'])}."
                                         + (" Clause c05 no longer applies." if lt == "commercial" else "")
                                         + " All other terms stay the same.")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- the abstractor's mistakes

MODES = {
    "amended-rent-missed": "The abstract keeps the rent from the original lease and ignores a later amendment.",
    "rent-step-dropped": "The abstract has no rent steps although the lease raises the rent during the term.",
    "notice-days-wrong-clause": "The renewal notice days come from another clause, not the renewal clause.",
    "utilities-incomplete": "The abstract leaves out a utility that the landlord pays for.",
    "late-fee-percent-as-dollars": "A late fee written as a percent is recorded as a flat dollar amount.",
    "deposit-includes-pet-deposit": "The security deposit adds in the separate one-time pet deposit.",
}


def abstract_with_faults(m, k, rng, lease_faults, noise=1.0):
    """One abstractor reply for a lease, with the faults this lease and this draw carry."""
    a = copy.deepcopy(k)
    modes = []
    if "amended-rent-missed" in lease_faults:
        a["monthly_rent"] = m["original_rent"]
        modes.append("amended-rent-missed")
    if "rent-step-dropped" in lease_faults or (m["step_style"] == "prose" and m["lease_type"] == "commercial"
                                               and rng.random() < 0.5):
        if a["rent_steps"]:
            a["rent_steps"] = []
            modes.append("rent-step-dropped")
    if m["notice_phrase"] == "not_less_than" and rng.random() < 0.4:
        a["renewal_notice_days"] = 60 if k["early_termination_fee"] and k["renewal_notice_days"] != 60 else 3
        modes.append("notice-days-wrong-clause")
    if a["utilities_included"] and rng.random() < 0.08 * noise:
        a["utilities_included"] = a["utilities_included"][1:]
        modes.append("utilities-incomplete")
    if k["late_fee"]["kind"] == "percent" and rng.random() < 0.5:
        a["late_fee"] = {"kind": "flat", "value": k["late_fee"]["value"] * 100}
        modes.append("late-fee-percent-as-dollars")
    if m["pet_deposit"] and rng.random() < 0.2:
        a["deposit"] = k["deposit"] + m["pet_deposit"]
        modes.append("deposit-includes-pet-deposit")
    return a, modes


# ---------------------------------------------------------------- the lease desk

QUESTIONS = {
    "pets": ("Can the tenant in unit {u} at {b} keep a cat?", ["c09"]),
    "renewal": ("How much notice does the tenant in unit {u} at {b} need to give to renew?", ["c12"]),
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


def good_answer(kind, m, k, cite):
    c = lambda x: f"[{m['id']}-{x}]"
    days = k["renewal_notice_days"]
    if kind == "pets":
        if k["pets_allowed"]:
            return f"Yes. The lease allows up to two pets for a pet fee of {usd(k['pet_fee'])} a month {c('c09')}."
        return f"No. The lease does not allow pets {c('c09')}."
    if kind == "renewal":
        if m["template"] == "FH-RES-2026":
            return f"The tenant must tell Fernhill at least {days} days before the term ends {c('c12')}."
        lim = "not less than " if m["notice_phrase"] == "not_less_than" else ""
        return f"The tenant must give written notice {lim}{days} days before the end of the term {c('c12')}."
    if kind == "rent":
        if m["amendment"]:
            return f"The rent is {usd(k['monthly_rent'])} a month, set by Amendment No. 1 {c('a01')}."
        return f"The rent is {usd(k['monthly_rent'])} a month {c('c04')}."
    if kind == "late":
        late = k["late_fee"]
        fee = f"{late['value']}% of the overdue amount" if late["kind"] == "percent" else usd(late["value"])
        return f"A late charge of {fee} applies if rent is not received by the {nth(k['late_fee_after_day'])} {c('c07')}."
    if kind == "sublet":
        if k["sublet_allowed"]:
            return f"Yes, with Fernhill's written consent {c('c11')}."
        return f"No. The lease does not allow subletting {c('c11')}."
    if kind == "water":
        if "water" in k["utilities_included"]:
            return f"The landlord pays for water {c('c08')}."
        return f"The tenant pays for water {c('c08')}."
    if kind == "parking":
        return (f"Yes, one parking space is included {c('c10')}." if k["parking"]
                else f"No, parking is not included {c('c10')}.")
    if kind == "deposit":
        return f"The tenant paid a security deposit of {usd(k['deposit'])} {c('c06')}."
    if kind == "early":
        if k["early_termination_fee"]:
            return (f"Yes, with 60 days' written notice and a fee of {usd(k['early_termination_fee'])} "
                    f"{c('c13')}.")
        return f"No. The lease gives no right to end early {c('c13')}."
    raise ValueError(kind)


def bad_answer(kind, m, k, rng, retrieved):
    """An answer that is NOT grounded in its citations. Returns (answer, fault number or 0)."""
    c = lambda x: f"[{m['id']}-{x}]"
    if kind in ("business", "paint"):
        cid = retrieved[0].split("-")[1]
        claim = rng.choice(["Yes, a home business is allowed if it does not disturb neighbours",
                            "Yes, a home office is fine but no customers may visit",
                            "No, the lease bans any business use"] if kind == "business" else
                           ["Yes, the tenant may paint if the walls are returned to white",
                            "Yes, with written consent from Fernhill",
                            "No, the lease bans any decorating"])
        return f"{claim} {c(cid)}.", 5
    if kind == "renewal" and m["notice_phrase"] == "not_less_than":
        return rng.choice([f"The tenant must give written notice {k['renewal_notice_days']} days before the end of the term {c('c12')}.",
                           f"Exactly {k['renewal_notice_days']} days' written notice is needed {c('c12')}.",
                           f"The tenant needs to give {k['renewal_notice_days']} days' notice before the term ends {c('c12')}."]), 3
    if kind == "rent" and m["amendment"]:
        return rng.choice([f"The rent is {usd(m['original_rent'])} a month {c('c04')}.",
                           f"Monthly rent is {usd(m['original_rent'])}, due on the first day of each month {c('c04')}."]), 0
    if kind == "late":
        return (f"A late charge applies if rent is not received by the {nth(k['late_fee_after_day'] + rng.choice([1, 2, 5]))} "
                f"{c('c07')}."), 0
    if kind == "sublet" and k["sublet_allowed"]:
        return f"Yes, the tenant may sublet freely {c('c11')}.", 0
    if kind == "deposit":
        return f"The tenant paid a security deposit of {usd(k['deposit'] + rng.choice([30000, 50000, 75000]))} {c('c06')}.", 0
    if kind == "pets" and k["pets_allowed"]:
        return f"Yes. The lease allows pets with no extra fee {c('c09')}.", 0
    if kind == "early" and k["early_termination_fee"]:
        return rng.choice([f"Yes, with 30 days' notice and no fee {c('c13')}.",
                           f"Yes, with 60 days' notice and no fee {c('c13')}."]), 0
    return rng.choice([f"Yes, and the landlord covers any extra cost {c(retrieved[0].split('-')[1])}.",
                       f"Yes, as long as the tenant tells Fernhill first {c(retrieved[0].split('-')[1])}.",
                       f"No, the lease forbids it {c(retrieved[0].split('-')[1])}."]), 0


def desk_run(q, m, k, rng, release="live", new_template=False):
    """One lease desk run: real retrieval, a reply written by rule, the truth about it."""
    found = retrieval.search(m["id"], q["question"], 5)
    retrieved = [x["id"] for x in found]
    gold = q["gold"]
    kind = q["kind"]
    fault = 0
    unanswerable = not gold
    hit = all(g in retrieved for g in gold)
    if unanswerable:
        if release == "shorter-prompt" or rng.random() < 0.3:
            answer, fault = bad_answer(kind, m, k, rng, retrieved)
            grounded = False
        else:
            answer, grounded = lease_desk.ABSTAIN, True
    elif not hit:
        answer, grounded = lease_desk.ABSTAIN, True
    else:
        p_bad = 0.75 if new_template else (0.6 if (kind == "renewal" and m["notice_phrase"] == "not_less_than")
                                           else 0.5 if (kind == "rent" and m["amendment"]) else 0.2)
        if rng.random() < p_bad:
            answer, fault = bad_answer(kind, m, k, rng, retrieved)
            grounded = False
        else:
            answer, grounded = good_answer(kind, m, k, None), True
    cited = lease_desk.cited(answer)
    abstained = answer == lease_desk.ABSTAIN
    return {"retrieved": retrieved, "answer": answer, "cited": cited, "grounded": grounded, "fault": fault,
            "abstained": abstained, "should_abstain": unanswerable, "messages": lease_desk.messages(q["question"], found)}


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


# ---------------------------------------------------------------- main

def main():
    out = paths.DATA
    if out.exists():
        shutil.rmtree(out)
    if paths.REPLAY.exists():
        shutil.rmtree(paths.REPLAY)
    paths.LEASES.mkdir(parents=True)
    paths.REPLAY.mkdir(parents=True)
    replay: dict[str, list] = {"abstractor": [], "lease_desk": [], "judge": [], "agent": [], "models": []}

    def record(file, role, messages, reply, trial=1):
        replay[file].append({"key": llm.key(role, messages, trial), "role": role, "trial": trial, "reply": reply})

    buildings, units = make_buildings()
    free = list(units)
    metas, keys = [], {}
    for i in range(1, 131):
        m, k = make_lease(i, buildings, free)
        metas.append(m)
        keys[m["id"]] = k
    by_id = {m["id"]: m for m in metas}
    for m in metas:
        (paths.LEASES / f"{m['id']}.md").write_text(lease_text(m, keys[m["id"]]))
    paths.write_jsonl(out / "buildings.jsonl", buildings)
    paths.write_jsonl(out / "units.jsonl", units)
    paths.write_jsonl(out / "leases.jsonl", metas)
    paths.write_jsonl(out / "keys.jsonl", [{"lease_id": i, "abstract": keys[i]} for i in keys])

    evals = [m for m in metas if m["corpus"] == "eval"]
    amended = [m["id"] for m in evals if m["amendment"]]
    commercial = [m["id"] for m in evals if m["lease_type"] == "commercial"]
    rng = random.Random(SEED + 1)

    # Splits: golden (Part 2), gate (Part 4), the rest.
    am = list(amended)
    rng.shuffle(am)
    co = [x for x in commercial if x not in am]
    rng.shuffle(co)
    others = [m["id"] for m in evals if m["id"] not in am and m["id"] not in co]
    rng.shuffle(others)
    golden = sorted(am[:10] + co[:3] + others[:27])
    gate = sorted(am[10:28] + co[3:7] + others[27:55])
    review = sorted(m["id"] for m in evals if m["id"] not in golden and m["id"] not in gate)

    # Lease-level faults in the live abstractor.
    gate_am = [x for x in gate if x in amended]
    rest_am = [x for x in amended if x not in golden and x not in gate]
    live_amend_wrong = sorted(gate_am[:5] + rest_am[:2])
    prose_res = [m["id"] for m in evals if m["step_style"] == "prose" and m["lease_type"] == "residential"]
    step_drop = sorted(x for x in prose_res if sub_rng("drop", x).random() < 0.4)
    lease_faults = {m["id"]: set() for m in metas}
    for x in live_amend_wrong:
        lease_faults[x].add("amended-rent-missed")
    for x in step_drop:
        lease_faults[x].add("rent-step-dropped")
    planted = []
    for x in live_amend_wrong:
        planted.append({"id": f"F1-{x}", "fault": 1, "system": "abstractor", "ref": x,
                        "detail": "the live abstractor keeps the original rent and misses Amendment No. 1"})
    for x in step_drop:
        planted.append({"id": f"F2-{x}", "fault": 2, "system": "abstractor", "ref": x,
                        "detail": "the rent step is written in prose and the live abstractor drops it"})

    # Abstractor traces: 300 runs over the 120 eval leases.
    traces, dana = [], []
    visits = [m["id"] for m in evals for _ in range(2)] + sorted(rng.sample([m["id"] for m in evals], 60))
    visits.sort()
    first_output = {}
    for n, lid in enumerate(visits, 1):
        m, k = by_id[lid], keys[lid]
        tid = f"abs-{n:04d}"
        a, modes = abstract_with_faults(m, k, sub_rng("trace", tid), lease_faults[lid])
        first_output.setdefault(lid, (a, tid))
        traces.append({
            "trace_id": tid, "system": "abstractor", "release": "live", "lease_id": lid, "unit": m["unit"],
            "building": m["building"], "lease_type": m["lease_type"], "template": m["template"],
            "amendments": m["amendments"], "output": a,
            "spans": [{"name": "read_document", "documents": 1 + m["amendments"]},
                      {"name": "llm", "role": "fast", "input_tokens": 1400 + 120 * m["amendments"],
                       "output_tokens": 310},
                      {"name": "write_abstract", "table": "leases"}],
        })
        dana.append({"trace_id": tid, "verdict": "fail" if modes else "pass", "modes": modes})
        for f, mode in ((3, "notice-days-wrong-clause"),):
            if mode in modes:
                planted.append({"id": f"F3-{tid}", "fault": 3, "system": "abstractor", "ref": tid,
                                "detail": "renewal notice is 'not less than N days'; the abstract takes days from another clause"})
    paths.TRACES.mkdir(parents=True, exist_ok=True)
    paths.write_jsonl(paths.TRACES / "abstractor.jsonl", traces)
    paths.LABELS.mkdir(parents=True, exist_ok=True)
    with open(paths.LABELS / "abstractor.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trace_id", "verdict"] + list(MODES))
        for d in dana:
            w.writerow([d["trace_id"], d["verdict"]] + [1 if mo in d["modes"] else 0 for mo in MODES])
    (paths.LABELS / "abstractor_modes.json").write_text(json.dumps(MODES, indent=2) + "\n")

    # The system of record holds what the live abstractor wrote, faults and all.
    sor = []
    for m in metas:
        if m["corpus"] == "eval":
            a, tid = first_output[m["id"]]
            sor.append({"lease_id": m["id"], "abstract": a, "written_by": f"abstractor ({tid})"})
        else:
            sor.append({"lease_id": m["id"], "abstract": keys[m["id"]], "written_by": "lease admin team"})
        record("abstractor", "fast", abstractor.messages(m["id"]), leases.dumps(sor[-1]["abstract"]))
    paths.write_jsonl(out / "system_of_record.jsonl", sor)

    # Ledger: twelve months of charges. Faults 4 and 6 live here.
    def rent_for(m, k, month):
        r = m["original_rent"]
        if m["amendment"] and month >= m["amendment"]["effective"][:7]:
            r = m["amendment"]["monthly_rent"]
        for s in k["rent_steps"]:
            if month >= s["effective"][:7]:
                r = s["monthly_rent"]
        return r

    missed_step = sorted(x for x in step_drop if keys[x]["rent_steps"] and keys[x]["rent_steps"][0]["effective"][:7] <= WINDOW[-1])
    no_pets = [m["id"] for m in evals if m["lease_type"] == "residential" and not keys[m["id"]]["pets_allowed"]
               and m["id"] not in missed_step]
    pet_conflict = sorted(rng.sample(no_pets, 5))
    pet_from = {x: WINDOW[rng.randint(2, 7)] for x in pet_conflict}
    ledger = []
    for m in evals:
        k = keys[m["id"]]
        lr = random.Random(f"ledger-{m['id']}")
        for month in WINDOW:
            if not (k["start_date"][:7] <= month <= k["end_date"][:7]):
                continue
            r = rent_for(m, k, month)
            note = "monthly rent"
            if m["id"] in missed_step:
                r = m["original_rent"]
            ledger.append({"lease_id": m["id"], "month": month, "kind": "rent", "amount_cents": r, "note": note})
            if k["pets_allowed"]:
                ledger.append({"lease_id": m["id"], "month": month, "kind": "pet_fee", "amount_cents": k["pet_fee"],
                               "note": "monthly pet fee"})
            if m["id"] in pet_conflict and month >= pet_from[m["id"]]:
                ledger.append({"lease_id": m["id"], "month": month, "kind": "pet_fee", "amount_cents": 3500,
                               "note": "monthly pet fee"})
            paid = sum(x["amount_cents"] for x in ledger if x["lease_id"] == m["id"] and x["month"] == month
                       and x["kind"] != "payment")
            if lr.random() < 0.05:
                fee = k["late_fee"]["value"] if k["late_fee"]["kind"] == "flat" else int(r * k["late_fee"]["value"] / 100)
                ledger.append({"lease_id": m["id"], "month": month, "kind": "late_fee", "amount_cents": fee,
                               "note": "late charge"})
                paid += fee
            ledger.append({"lease_id": m["id"], "month": month, "kind": "payment", "amount_cents": -paid,
                           "note": "tenant payment"})
    paths.write_jsonl(out / "ledger.jsonl", ledger)
    for x in pet_conflict:
        planted.append({"id": f"F4-{x}", "fault": 4, "system": "ledger", "ref": x,
                        "detail": f"pets are banned but the ledger charges a pet fee from {pet_from[x]}"})
    for x in missed_step:
        planted.append({"id": f"F6-{x}", "fault": 6, "system": "ledger", "ref": x,
                        "detail": "the rent step was never charged because the abstract dropped it"})

    # Questions: 80 staff questions on eval leases, 10 on the new template.
    qs = []
    plan = (["renewal"] * 10 + ["rent"] * 10 + ["pets"] * 8 + ["late"] * 7 + ["sublet"] * 6 + ["water"] * 6
            + ["parking"] * 6 + ["deposit"] * 6 + ["early"] * 9 + ["business"] * 6 + ["paint"] * 6)
    used = set()
    for n, kind in enumerate(plan, 1):
        if kind == "renewal":
            pool = [m for m in evals if keys[m["id"]]["renewal_option"]
                    and (m["notice_phrase"] == "not_less_than" or n % 3 == 0)]
        elif kind == "rent":
            pool = [m for m in evals if m["amendment"] or n % 5 == 0]
        else:
            pool = evals
        pool = [m for m in pool if (m["id"], kind) not in used] or evals
        m = rng.choice(pool)
        used.add((m["id"], kind))
        text, gold = QUESTIONS[kind]
        gold = [f"{m['id']}-{g}" for g in gold if g != "a01" or m["amendment"]]
        if kind == "rent" and m["amendment"]:
            gold = [f"{m['id']}-a01"]
        qs.append({"id": f"q{n:03d}", "lease_id": m["id"], "kind": kind,
                   "question": text.format(u=m["unit"], b=m["building"]), "gold": gold, "answerable": bool(gold)})
    paths.write_jsonl(out / "questions.jsonl", qs)
    qby = {q["id"]: q for q in qs}

    # Lease desk: 320 recorded runs on the eval corpus.
    desk, desk_truth = [], []
    order = [q["id"] for q in qs for _ in range(4)]
    for n, qid in enumerate(order, 1):
        q = qby[qid]
        m, k = by_id[q["lease_id"]], keys[q["lease_id"]]
        run = desk_run(q, m, k, sub_rng("desk", n))
        rid = f"desk-{n:04d}"
        desk.append({"trace_id": rid, "system": "lease_desk", "release": "live", "question_id": qid,
                     "lease_id": m["id"], "question": q["question"], "retrieved": run["retrieved"],
                     "answer": run["answer"], "cited": run["cited"]})
        desk_truth.append({"trace_id": rid, "grounded": run["grounded"], "fault": run["fault"],
                           "abstained": run["abstained"], "should_abstain": run["should_abstain"]})
        if n <= 80 or qid not in {d["question_id"] for d in desk[:-1]}:
            pass
        if run["fault"] in (3, 5):
            planted.append({"id": f"F{run['fault']}-{rid}", "fault": run["fault"], "system": "lease_desk", "ref": rid,
                            "detail": "drops 'not less than' from the renewal notice" if run["fault"] == 3
                            else "answers a question the lease does not answer"})
    for q in qs:  # the finished lease desk replays its first recorded answer for each question
        first = next(d for d in desk if d["question_id"] == q["id"])
        found = retrieval.search(q["lease_id"], q["question"], 5)
        record("lease_desk", "fast", lease_desk.messages(q["question"], found), first["answer"])
    paths.write_jsonl(paths.TRACES / "lease_desk.jsonl", desk)
    truth_by = {t["trace_id"]: t for t in desk_truth}

    # Dana's grounded labels: 60 pass and 60 fail, split train 20, dev 50, test 50.
    # Dana labels each distinct answer once, so a repeated run never sits in two splits.
    distinct = {}
    for d in desk:
        distinct.setdefault((d["question_id"], d["answer"]), d["trace_id"])
    uniq = sorted(distinct.values())
    passes = [t for t in uniq if truth_by[t]["grounded"]]
    fails = [t for t in uniq if not truth_by[t]["grounded"]]
    rng.shuffle(passes)
    rng.shuffle(fails)
    assert len(fails) >= 60, f"only {len(fails)} ungrounded runs; raise the fault rates"
    split = {}
    for name, size in (("train", 10), ("dev", 25), ("test", 25)):
        for _ in range(size):
            split[passes.pop()] = name
            split[fails.pop()] = name
    with open(paths.LABELS / "grounded.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trace_id", "split", "label"])
        for d in desk:
            if d["trace_id"] in split:
                w.writerow([d["trace_id"], split[d["trace_id"]], "pass" if truth_by[d["trace_id"]]["grounded"] else "fail"])
    paths.write_jsonl(paths.LABELS / "lease_desk_truth.jsonl", desk_truth)

    # The finished judge's recorded verdicts: TPR 0.92 and TNR 0.88 on test, near that elsewhere.
    by_content = {}

    def content(i):
        d = desk_by.get(i) or prod_by[i]
        return (d["question"], d["answer"], tuple(d["cited"]))

    def verdicts_for(ids, tpr_miss, tnr_miss, seed):
        """Flip a set share of verdicts. The same prompt always gets the same verdict, as at temperature 0."""
        r = random.Random(seed)
        done = {i: by_content[content(i)] for i in ids if content(i) in by_content}
        ids = [i for i in ids if i not in done]
        pos = [i for i in ids if truth_by_all[i]["grounded"]]
        neg = [i for i in ids if not truth_by_all[i]["grounded"]]
        flip = set(r.sample(pos, tpr_miss) if isinstance(tpr_miss, int) else [i for i in pos if r.random() < tpr_miss])
        flip |= set(r.sample(neg, tnr_miss) if isinstance(tnr_miss, int) else [i for i in neg if r.random() < tnr_miss])
        out = dict(done)
        for i in ids:
            if content(i) in by_content:
                out[i] = by_content[content(i)]
                continue
            v = "pass" if truth_by_all[i]["grounded"] else "fail"
            out[i] = ("fail" if v == "pass" else "pass") if i in flip else v
            by_content[content(i)] = out[i]
        return out

    truth_by_all = dict(truth_by)
    desk_by = {d["trace_id"]: d for d in desk}
    prod_by = {}
    verdict = {}
    verdict.update(verdicts_for([i for i, s in split.items() if s == "test"], 2, 3, 11))
    verdict.update(verdicts_for([i for i, s in split.items() if s == "dev"], 2, 3, 12))
    verdict.update(verdicts_for([i for i, s in split.items() if s == "train"], 1, 1, 13))
    verdict.update(verdicts_for([d["trace_id"] for d in desk if d["trace_id"] not in split], 0.08, 0.12, 14))

    def record_judge(d, v):
        cited = [{"id": c["id"], "text": c["text"]} for c in leases.clauses(d["lease_id"]) if c["id"] in d["cited"]]
        run = {**truth_by_all[d["trace_id"]]}
        reply = json.dumps({"critique": critique(run, v), "verdict": v})
        record("judge", "judge", judge_mod.messages(d["question"], d["answer"], cited), reply)

    for d in desk:
        record_judge(d, verdict[d["trace_id"]])

    # Production: 7 batches of 40 lease desk runs. Batch 5 brings the new lease template.
    prod_q = []
    for m in [x for x in metas if x["corpus"] == "production"]:
        for kind in ("renewal", "rent"):
            text, gold = QUESTIONS[kind]
            prod_q.append({"id": f"p-{m['id']}-{kind}", "lease_id": m["id"], "kind": kind,
                           "question": text.format(u=m["unit"], b=m["building"]),
                           "gold": [f"{m['id']}-c12" if kind == "renewal" else f"{m['id']}-c04"], "answerable": True})
    prod = []
    for batch in range(1, 8):
        for j in range(40):
            if batch >= 5 and j < 16:
                q = prod_q[(batch * 16 + j) % len(prod_q)]
            else:
                q = qs[(batch * 37 + j * 11) % len(qs)]
            m, k = by_id[q["lease_id"]], keys[q["lease_id"]]
            run = desk_run(q, m, k, sub_rng("prod", batch, j), new_template=m["template"] == "FH-RES-2026")
            rid = f"prod-{batch}-{j + 1:02d}"
            prod.append({"trace_id": rid, "system": "lease_desk", "release": "live", "batch": batch,
                         "building": m["building"], "question_id": q["id"], "lease_id": m["id"],
                         "question": q["question"], "retrieved": run["retrieved"], "answer": run["answer"],
                         "cited": run["cited"]})
            truth_by_all[rid] = {"trace_id": rid, "grounded": run["grounded"], "fault": run["fault"],
                                 "abstained": run["abstained"], "should_abstain": run["should_abstain"]}
    prod_by.update({p["trace_id"]: p for p in prod})
    verdict.update(verdicts_for([p["trace_id"] for p in prod], 0.08, 0.12, 15))
    for p in prod:
        record_judge(p, verdict[p["trace_id"]])
    paths.write_jsonl(paths.TRACES / "lease_desk_production.jsonl", prod)
    paths.write_jsonl(paths.LABELS / "production_truth.jsonl", [truth_by_all[p["trace_id"]] for p in prod])

    # Releases: 3 trials per eval lease and per question, for four candidate releases.
    cheaper_extra = [x for x in gate_am if x not in live_amend_wrong][:9]
    flaky = next(x for x in gate if x not in amended and keys[x]["lease_type"] == "residential")
    for x in cheaper_extra:
        planted.append({"id": f"F7-{x}", "fault": 7, "system": "release:cheaper-model", "ref": x,
                        "detail": "the cheaper model misses Amendment No. 1 on this lease in every trial"})
    paths.RELEASES.mkdir(parents=True, exist_ok=True)
    manifests = {
        "live": "What runs today.",
        "cheaper-model": "The abstractor moves to a cheaper model to cut cost per lease.",
        "shorter-prompt": "The lease desk prompt is cut to half its length to save tokens.",
        "clause-ids-in-answer": "The lease desk puts clause ids in a fixed place at the end of each answer.",
    }
    for rel, change in manifests.items():
        rows = []
        for m in evals:
            k = keys[m["id"]]
            for trial in (1, 2, 3):
                lf = set(lease_faults[m["id"]])
                noise = 1.0
                if rel == "cheaper-model":
                    noise = 1.6
                    if m["id"] in cheaper_extra:
                        lf.add("amended-rent-missed")
                a, modes = abstract_with_faults(m, k, sub_rng("release", m["id"], trial), lf, noise)
                if rel == "cheaper-model" and sub_rng("cheap-park", m["id"], trial).random() < 0.05:
                    a["parking"] = not a["parking"]
                if rel == "clause-ids-in-answer" and m["id"] == flaky and trial == 2:
                    a["monthly_rent"] = k["monthly_rent"] + 10000
                rows.append({"release": rel, "kind": "abstract", "lease_id": m["id"], "trial": trial, "output": a})
        for q in qs:
            m, k = by_id[q["lease_id"]], keys[q["lease_id"]]
            for trial in (1, 2, 3):
                run = desk_run(q, m, k, sub_rng("release-desk", q["id"], trial), release=rel)
                rows.append({"release": rel, "kind": "desk", "question_id": q["id"], "lease_id": m["id"],
                             "trial": trial, "output": {"answer": run["answer"], "cited": run["cited"],
                                                        "retrieved": run["retrieved"]}})
        paths.write_jsonl(paths.RELEASES / f"{rel}.jsonl", rows)
        (paths.RELEASES / f"{rel}.json").write_text(json.dumps({"name": rel, "change": change}, indent=2) + "\n")

    # Agent tasks: 20 tasks, 4 recorded trials each.
    def steps_due(x):
        return [s for s in keys[x]["rent_steps"] if s["effective"][:7] in ("2026-11", "2026-12")]

    notice_pool = [m["id"] for m in evals if steps_due(m["id"]) and m["id"] not in step_drop]
    renew_pool = [m["id"] for m in evals if keys[m["id"]]["renewal_option"] and m["lease_type"] == "residential"
                  and keys[m["id"]]["end_date"][:7] in ("2026-12", "2027-01")
                  and m["id"] not in missed_step and m["id"] not in pet_conflict]
    tasks = []

    def task(kind, lid, prompt, expect):
        tasks.append({"id": f"task-{len(tasks) + 1:02d}", "kind": kind, "lease_id": lid, "prompt": prompt,
                      "expect": expect})

    for lid in missed_step[:5]:
        k = keys[lid]
        s = k["rent_steps"][0]
        months = [mo for mo in WINDOW if mo >= s["effective"][:7] and mo <= k["end_date"][:7]]
        owed = (s["monthly_rent"] - by_id[lid]["original_rent"]) * len(months)
        task("missed-step", lid, f"Monthly rent review for lease {lid} (unit {k['unit']} at {by_id[lid]['building']}). "
             "Check that the ledger charges the rent the lease sets. Propose a charge for anything owed.",
             {"charge_cents": owed, "notice": None})
    for lid in pet_conflict:
        k = keys[lid]
        charged = sum(x["amount_cents"] for x in ledger if x["lease_id"] == lid and x["kind"] == "pet_fee")
        task("pet-fee-conflict", lid, f"Monthly rent review for lease {lid} (unit {k['unit']} at "
             f"{by_id[lid]['building']}). Check every fee in the ledger against the lease. Propose a credit for "
             "any fee the lease does not allow.", {"charge_cents": -charged, "notice": None})
    for lid in sorted(rng.sample(notice_pool, min(5, len(notice_pool)))):
        k = keys[lid]
        s = steps_due(lid)[0]
        task("rent-step-notice", lid, f"Monthly rent review for lease {lid} (unit {k['unit']} at "
             f"{by_id[lid]['building']}). If the rent changes in the next two months, draft the rent increase "
             "notice with the new monthly rent.", {"charge_cents": None, "notice": "rent_increase",
                                                   "notice_amount": usd(s["monthly_rent"])})
    for lid in sorted(rng.sample(renew_pool, min(20 - len(tasks), len(renew_pool)))):
        k = keys[lid]
        task("renewal-offer", lid, f"Monthly rent review for lease {lid} (unit {k['unit']} at "
             f"{by_id[lid]['building']}). If the renewal window is open, draft the renewal offer notice.",
             {"charge_cents": None, "notice": "renewal_offer", "notice_amount": None})
    assert len(tasks) == 20, f"{len(tasks)} agent tasks; widen the pools"
    paths.write_jsonl(out / "agent_tasks.jsonl", tasks)

    # Which trial goes wrong, and how. Trials 1 to 3 give pass^3; trial 4 adds history for the failure map.
    faults_plan = {
        ("task-01", 2): "trust_abstract", ("task-02", 1): "trust_abstract", ("task-03", 3): "post_charge",
        ("task-04", 4): "trust_abstract", ("task-05", 2): "wrong_amount", ("task-06", 3): "stopped",
        ("task-08", 4): "post_charge", ("task-11", 1): "wrong_lease", ("task-13", 4): "wrong_lease",
        ("task-16", 2): "stopped", ("task-18", 3): "wrong_lease", ("task-02", 4): "wrong_amount",
        ("task-19", 4): "stopped",
    }
    perm_counter = {"n": 0}
    for p in planted:
        pass
    paths.write_jsonl(out / "planted_faults.jsonl", planted)
    db.build()
    tmp = Path(tempfile.mkdtemp())
    agent_traces = []
    for t in tasks:
        k, lid = keys[t["lease_id"]], t["lease_id"]
        for trial in (1, 2, 3, 4):
            how = faults_plan.get((t["id"], trial), "ok")
            script = agent_script(t, k, by_id[lid], how)
            calls = iter(script)

            def fake(msgs, _calls=calls, _trial=trial):
                reply = next(_calls)
                record("agent", "smart", msgs, reply, _trial)
                return reply

            res = agent.run(t, db.copy(tmp / f"{t['id']}-{trial}.db"), trial, complete=fake)
            agent_traces.append({"trace_id": f"agent-{t['id']}-{trial}", "system": "agent", "task_id": t["id"],
                                 "trial": trial, "lease_id": lid, "steps": res["steps"], "final": res["final"]})
            if how == "post_charge":
                perm_counter["n"] += 1
    shutil.rmtree(tmp)
    paths.write_jsonl(paths.TRACES / "agent.jsonl", agent_traces)
    for t in tasks:
        for trial in (1, 2, 3, 4):
            how = faults_plan.get((t["id"], trial))
            if how == "post_charge":
                planted.append({"id": f"F6-agent-{t['id']}-{trial}", "fault": 6, "system": "agent",
                                "ref": f"agent-{t['id']}-{trial}", "detail": "posts a charge without approval"})
    paths.write_jsonl(out / "planted_faults.jsonl", planted)

    # One tiny call per role for `uv run models`.
    from .models_cli import PING
    for role in ("fast", "smart", "judge"):
        record("models", role, PING, "ok")

    demo = next(q for q in qs if q["kind"] == "rent" and q["lease_id"] in live_amend_wrong)
    split_info = {"golden": golden, "gate": gate, "review": review, "demo_lease": demo["lease_id"],
                  "flaky_gate_lease": flaky}
    (out / "splits.json").write_text(json.dumps(split_info, indent=2) + "\n")
    for name, rows in replay.items():
        paths.write_jsonl(paths.REPLAY / f"{name}.jsonl", rows)
    db.build()
    print(f"Generated {len(metas)} leases, {len(traces)} abstractor traces, {len(desk)} lease desk runs, "
          f"{len(prod)} production runs, {len(agent_traces)} agent runs, {len(planted)} planted faults.")


def agent_script(t, k, m, how):
    """The replies a small model gives on this task, as JSON actions."""
    lid = t["lease_id"]
    j = lambda **x: json.dumps(x, sort_keys=True)
    query = {"missed-step": "rent increases anniversary", "pet-fee-conflict": "pets animals fee",
             "rent-step-notice": "rent increases", "renewal-offer": "renewal notice"}[t["kind"]]
    s = [j(tool="get_abstract", args={"lease_id": lid})]
    if how == "trust_abstract":
        return s + [j(tool="get_ledger", args={"lease_id": lid}),
                    j(done="The abstract shows no rent change and the ledger matches it. Nothing to do.")]
    s.append(j(tool="search_lease", args={"lease_id": lid, "query": query}))
    if how == "stopped":
        return s + [j(done="I read the lease. A person should review this one.")]
    exp = t["expect"]
    if t["kind"] in ("missed-step", "pet-fee-conflict"):
        s.append(j(tool="get_ledger", args={"lease_id": lid}))
        amount = exp["charge_cents"]
        if how == "wrong_amount":
            amount = int(amount / 3)
        reason = "rent step not charged" if t["kind"] == "missed-step" else "credit for pet fees the lease does not allow"
        name = "post_charge" if how == "post_charge" else "propose_charge"
        s.append(j(tool=name, args={"lease_id": lid, "amount_cents": amount, "reason": reason}))
        return s + [j(done=f"{'Posted' if name == 'post_charge' else 'Proposed'} {usd(abs(amount))}: {reason}.")]
    target = lid
    if how == "wrong_lease":
        target = f"L{int(lid[1:]) % 110 + 1:03d}"
    if t["kind"] == "rent-step-notice":
        body = f"Your monthly rent changes to {exp['notice_amount']} as your lease sets out."
        s.append(j(tool="draft_notice", args={"lease_id": target, "kind": "rent_increase", "body": body}))
    else:
        body = "Your lease can be renewed. Please tell us within the notice period in your lease if you wish to renew."
        s.append(j(tool="draft_notice", args={"lease_id": target, "kind": "renewal_offer", "body": body}))
    return s + [j(done="Drafted the notice for staff to review.")]


if __name__ == "__main__":
    main()
