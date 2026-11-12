"""The system of record: one SQLite file, rebuilt from world/data with `uv run world reset`."""

import json
import shutil
import sqlite3
from pathlib import Path

from . import leases, paths

SCHEMA = """
CREATE TABLE buildings (id TEXT PRIMARY KEY, name TEXT, address TEXT, owner TEXT, units INTEGER);
CREATE TABLE units (id TEXT PRIMARY KEY, building_id TEXT, label TEXT, bedrooms INTEGER, kind TEXT);
CREATE TABLE leases (id TEXT PRIMARY KEY, unit_id TEXT, unit TEXT, building TEXT, tenant TEXT, lease_type TEXT,
  template TEXT, corpus TEXT, abstract TEXT, written_by TEXT);
CREATE TABLE documents (clause_id TEXT PRIMARY KEY, lease_id TEXT, heading TEXT, text TEXT);
CREATE TABLE ledger (id INTEGER PRIMARY KEY, lease_id TEXT, month TEXT, kind TEXT, amount_cents INTEGER,
  note TEXT, created_by TEXT);
CREATE TABLE notices (id INTEGER PRIMARY KEY, lease_id TEXT, kind TEXT, body TEXT, created_by TEXT);
CREATE TABLE charges (id INTEGER PRIMARY KEY, lease_id TEXT, amount_cents INTEGER, reason TEXT, status TEXT,
  approval_id INTEGER, created_by TEXT);
CREATE TABLE approvals (id INTEGER PRIMARY KEY, charge_id INTEGER, approved_by TEXT);
CREATE TABLE planted_faults (id TEXT PRIMARY KEY, fault INTEGER, system TEXT, ref TEXT, detail TEXT);
"""


def build(path: Path = paths.DB) -> dict:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    d = paths.DATA
    for b in paths.read_jsonl(d / "buildings.jsonl"):
        con.execute(
            "INSERT INTO buildings VALUES (?,?,?,?,?)",
            (b["id"], b["name"], b["address"], b["owner"], b["units"]),
        )
    con.executemany(
        "INSERT INTO units VALUES (?,?,?,?,?)",
        [
            (u["id"], u["building_id"], u["label"], u["bedrooms"], u["kind"])
            for u in paths.read_jsonl(d / "units.jsonl")
        ],
    )
    record = {r["lease_id"]: r for r in paths.read_jsonl(d / "system_of_record.jsonl")}
    for le in leases.leases():
        r = record[le["id"]]
        con.execute(
            "INSERT INTO leases VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                le["id"],
                le["unit_id"],
                le["unit"],
                le["building"],
                le["tenant"],
                le["lease_type"],
                le["template"],
                le["corpus"],
                json.dumps(r["abstract"], sort_keys=True),
                r["written_by"],
            ),
        )
        for c in leases.clauses(le["id"]):
            con.execute(
                "INSERT INTO documents VALUES (?,?,?,?)",
                (c["id"], le["id"], c["heading"], c["text"]),
            )
    con.executemany(
        "INSERT INTO ledger (lease_id, month, kind, amount_cents, note, created_by) VALUES (?,?,?,?,?,?)",
        [
            (r["lease_id"], r["month"], r["kind"], r["amount_cents"], r["note"], "billing")
            for r in paths.read_jsonl(d / "ledger.jsonl")
        ],
    )
    con.executemany(
        "INSERT INTO planted_faults VALUES (?,?,?,?,?)",
        [
            (f["id"], f["fault"], f["system"], f["ref"], f["detail"])
            for f in paths.read_jsonl(d / "planted_faults.jsonl")
        ],
    )
    con.commit()
    counts = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("buildings", "units", "leases", "documents", "ledger", "planted_faults")
    }
    con.close()
    return counts


def copy(dest: Path) -> Path:
    """A fresh copy of the seeded system of record, for one agent trial."""
    if not paths.DB.exists():
        build()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(paths.DB, dest)
    return dest


def connect(path: Path = paths.DB) -> sqlite3.Connection:
    if path == paths.DB and not path.exists():
        build()
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def counts(path: Path = paths.DB) -> dict:
    con = connect(path)
    out = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in (
            "buildings",
            "units",
            "leases",
            "documents",
            "ledger",
            "notices",
            "charges",
            "planted_faults",
        )
    }
    out["eval_corpus_leases"] = con.execute(
        "SELECT COUNT(*) FROM leases WHERE corpus='eval'"
    ).fetchone()[0]
    con.close()
    return out
