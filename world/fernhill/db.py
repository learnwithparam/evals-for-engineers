"""The system of record: one SQLite file, rebuilt from world/data with `uv run world reset`."""

import json
import shutil
import sqlite3
from pathlib import Path

from . import leases, paths

# Each table on its own line. The text is stored in the database file as written, so it is kept
# exactly as the first build wrote it, line breaks and all.
TABLES = [
    "CREATE TABLE buildings "
    "(id TEXT PRIMARY KEY, name TEXT, address TEXT, owner TEXT, units INTEGER);",
    "CREATE TABLE units "
    "(id TEXT PRIMARY KEY, building_id TEXT, label TEXT, bedrooms INTEGER, kind TEXT);",
    "CREATE TABLE leases "
    "(id TEXT PRIMARY KEY, unit_id TEXT, unit TEXT, building TEXT, tenant TEXT, lease_type TEXT,"
    "\n  template TEXT, corpus TEXT, abstract TEXT, written_by TEXT);",
    "CREATE TABLE documents (clause_id TEXT PRIMARY KEY, lease_id TEXT, heading TEXT, text TEXT);",
    "CREATE TABLE ledger "
    "(id INTEGER PRIMARY KEY, lease_id TEXT, month TEXT, kind TEXT, amount_cents INTEGER,"
    "\n  note TEXT, created_by TEXT);",
    "CREATE TABLE notices "
    "(id INTEGER PRIMARY KEY, lease_id TEXT, kind TEXT, body TEXT, created_by TEXT);",
    "CREATE TABLE charges "
    "(id INTEGER PRIMARY KEY, lease_id TEXT, amount_cents INTEGER, reason TEXT, status TEXT,"
    "\n  approval_id INTEGER, created_by TEXT);",
    "CREATE TABLE approvals (id INTEGER PRIMARY KEY, charge_id INTEGER, approved_by TEXT);",
    "CREATE TABLE planted_faults "
    "(id TEXT PRIMARY KEY, fault INTEGER, system TEXT, ref TEXT, detail TEXT);",
]
SCHEMA = "\n" + "\n".join(TABLES) + "\n"

# The tables a fresh build reports, and the tables `uv run world status` reports.
BUILT_TABLES = ("buildings", "units", "leases", "documents", "ledger", "planted_faults")
STATUS_TABLES = (
    "buildings",
    "units",
    "leases",
    "documents",
    "ledger",
    "notices",
    "charges",
    "planted_faults",
)


def _insert_buildings(connection: sqlite3.Connection) -> None:
    for building in paths.read_jsonl(paths.DATA / "buildings.jsonl"):
        connection.execute(
            "INSERT INTO buildings VALUES (?,?,?,?,?)",
            (
                building["id"],
                building["name"],
                building["address"],
                building["owner"],
                building["units"],
            ),
        )


def _insert_units(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO units VALUES (?,?,?,?,?)",
        [
            (unit["id"], unit["building_id"], unit["label"], unit["bedrooms"], unit["kind"])
            for unit in paths.read_jsonl(paths.DATA / "units.jsonl")
        ],
    )


def _insert_leases_and_clauses(connection: sqlite3.Connection) -> None:
    records = paths.read_jsonl(paths.DATA / "system_of_record.jsonl")
    record_by_lease = {record["lease_id"]: record for record in records}
    for lease in leases.leases():
        record = record_by_lease[lease["id"]]
        connection.execute(
            "INSERT INTO leases VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                lease["id"],
                lease["unit_id"],
                lease["unit"],
                lease["building"],
                lease["tenant"],
                lease["lease_type"],
                lease["template"],
                lease["corpus"],
                json.dumps(record["abstract"], sort_keys=True),
                record["written_by"],
            ),
        )
        for clause in leases.clauses(lease["id"]):
            connection.execute(
                "INSERT INTO documents VALUES (?,?,?,?)",
                (clause["id"], lease["id"], clause["heading"], clause["text"]),
            )


def _insert_ledger(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO ledger (lease_id, month, kind, amount_cents, note, created_by) "
        "VALUES (?,?,?,?,?,?)",
        [
            (
                line["lease_id"],
                line["month"],
                line["kind"],
                line["amount_cents"],
                line["note"],
                "billing",
            )
            for line in paths.read_jsonl(paths.DATA / "ledger.jsonl")
        ],
    )


def _insert_planted_faults(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT INTO planted_faults VALUES (?,?,?,?,?)",
        [
            (fault["id"], fault["fault"], fault["system"], fault["ref"], fault["detail"])
            for fault in paths.read_jsonl(paths.DATA / "planted_faults.jsonl")
        ],
    )


def _count_rows(connection: sqlite3.Connection, tables: tuple[str, ...]) -> dict:
    return {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    }


def build(path: Path = paths.DB) -> dict:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(SCHEMA)
    _insert_buildings(connection)
    _insert_units(connection)
    _insert_leases_and_clauses(connection)
    _insert_ledger(connection)
    _insert_planted_faults(connection)
    connection.commit()
    counts = _count_rows(connection, BUILT_TABLES)
    connection.close()
    return counts


def copy(destination: Path) -> Path:
    """A fresh copy of the seeded system of record, for one agent trial."""
    if not paths.DB.exists():
        build()
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(paths.DB, destination)
    return destination


def connect(path: Path = paths.DB) -> sqlite3.Connection:
    if path == paths.DB and not path.exists():
        build()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def counts(path: Path = paths.DB) -> dict:
    connection = connect(path)
    found = _count_rows(connection, STATUS_TABLES)
    eval_corpus = connection.execute("SELECT COUNT(*) FROM leases WHERE corpus='eval'")
    found["eval_corpus_leases"] = eval_corpus.fetchone()[0]
    connection.close()
    return found
