"""uv run world [status|reset|tour|generate]: the Fernhill Homes world and its system of record."""

import sys

from . import db, leases, paths

TOUR = """Fernhill Homes manages {units:,} homes and shops in {buildings} buildings for 60 owners.

Dana Mensah, head of lease administration, owns what "correct" means. Her labels are the truth here.

Three LLM systems run every day:
  Lease abstractor  reads a signed lease and its amendments, writes an 18-field abstract to the system of record
  Lease desk        answers staff questions about a lease, citing clauses, or says "The lease does not say."
  Rent review agent finds lease events, reads the lease and ledger, drafts notices and proposes charges

Dana's note: "Owners got two wrong rent letters last month. I need to know how often this happens,
and what kind of mistake it is, before anyone switches the abstractor to the cheaper model."

The system of record: world/fernhill.db ({leases} leases, {ledger:,} ledger lines, {faults} planted faults).
The recorded runs: world/data/traces/. Dana's labels: world/data/labels/.
Next: uv run fernhill demo"""


def status() -> int:
    c = db.counts()
    print(
        f"World ready: {c['units']:,} units in {c['buildings']} buildings, {c['eval_corpus_leases']} leases in "
        f"the eval corpus ({c['leases']} in all), {c['ledger']:,} ledger lines, {c['planted_faults']} planted faults."
    )
    print(f"Agent writes: {c['notices']} notices, {c['charges']} charges.")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "reset":
        c = db.build()
        print(
            f"Reset the system of record from world/data: {c['units']:,} units, {c['leases']} leases, "
            f"{c['ledger']:,} ledger lines, {c['planted_faults']} planted faults."
        )
        if paths.RUNS.exists():
            import shutil

            shutil.rmtree(paths.RUNS)
        return status()
    if cmd == "status":
        return status()
    if cmd == "tour":
        c = db.counts()
        print(
            TOUR.format(
                units=c["units"],
                buildings=c["buildings"],
                leases=c["leases"],
                ledger=c["ledger"],
                faults=c["planted_faults"],
            )
        )
        return 0
    if cmd == "generate":
        from . import generate

        generate.main()
        return 0
    if cmd == "lease":
        print(leases.text(sys.argv[2]))
        return 0
    print("Use: uv run world [status|reset|tour|lease <id>|generate]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
