"""uv run world [status|reset|tour|generate]: the Fernhill Homes world and its system of record."""

import shutil
import sys

from . import db, leases, paths

TOUR = "\n".join(
    [
        "Fernhill Homes manages {units:,} homes and shops in {buildings} buildings for 60 owners.",
        "",
        'Dana Mensah, head of lease administration, owns what "correct" means. '
        "Her labels are the truth here.",
        "",
        "Three LLM systems run every day:",
        "  Lease abstractor  reads a signed lease and its amendments, "
        "writes an 18-field abstract to the system of record",
        "  Lease desk        answers staff questions about a lease, citing clauses, "
        'or says "The lease does not say."',
        "  Rent review agent finds lease events, reads the lease and ledger, "
        "drafts notices and proposes charges",
        "",
        "Dana's note: \"Owners got two wrong rent letters last month. "
        "I need to know how often this happens,",
        "and what kind of mistake it is, "
        'before anyone switches the abstractor to the cheaper model."',
        "",
        "The system of record: world/fernhill.db "
        "({leases} leases, {ledger:,} ledger lines, {faults} planted faults).",
        "The recorded runs: world/data/traces/. Dana's labels: world/data/labels/.",
        "Next: uv run fernhill demo",
    ]
)


def status() -> int:
    counts = db.counts()
    print(
        f"World ready: {counts['units']:,} units in {counts['buildings']} buildings, "
        f"{counts['eval_corpus_leases']} leases in the eval corpus ({counts['leases']} in all), "
        f"{counts['ledger']:,} ledger lines, {counts['planted_faults']} planted faults."
    )
    print(f"Agent writes: {counts['notices']} notices, {counts['charges']} charges.")
    return 0


def reset() -> int:
    counts = db.build()
    print(
        f"Reset the system of record from world/data: {counts['units']:,} units, "
        f"{counts['leases']} leases, {counts['ledger']:,} ledger lines, "
        f"{counts['planted_faults']} planted faults."
    )
    # Old agent runs were copies of the old system of record, so they go too.
    if paths.RUNS.exists():
        shutil.rmtree(paths.RUNS)
    return status()


def tour() -> int:
    counts = db.counts()
    print(
        TOUR.format(
            units=counts["units"],
            buildings=counts["buildings"],
            leases=counts["leases"],
            ledger=counts["ledger"],
            faults=counts["planted_faults"],
        )
    )
    return 0


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "reset":
        return reset()
    if command == "status":
        return status()
    if command == "tour":
        return tour()
    if command == "generate":
        from . import generate

        generate.main()
        return 0
    if command == "lease":
        print(leases.text(sys.argv[2]))
        return 0
    print("Use: uv run world [status|reset|tour|lease <id>|generate]")
    return 1


if __name__ == "__main__":
    sys.exit(main())
