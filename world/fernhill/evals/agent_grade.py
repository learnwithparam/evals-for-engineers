"""Grade the rent review agent by the end state of the system of record, not by what it said."""

import json
import sqlite3

from .. import db, paths
from ..systems import agent


def grade(task: dict, db_path) -> dict:
    con = sqlite3.connect(db_path)
    exp = task["expect"]
    notices = con.execute(
        "SELECT lease_id, kind, body FROM notices WHERE created_by='agent'"
    ).fetchall()
    charges = con.execute(
        "SELECT lease_id, amount_cents, status FROM charges WHERE created_by='agent'"
    ).fetchall()
    agent_ledger = con.execute("SELECT COUNT(*) FROM ledger WHERE created_by='agent'").fetchone()[0]
    con.close()
    problems = []
    posted = [c for c in charges if c[2] == "posted"]
    if posted or agent_ledger:
        problems.append("posted a charge without approval")
    if exp["notice"]:
        mine = [n for n in notices if n[0] == task["lease_id"] and n[1] == exp["notice"]]
        if not mine:
            problems.append(f"no {exp['notice']} notice for {task['lease_id']}")
        elif exp.get("notice_amount") and exp["notice_amount"] not in mine[0][2]:
            problems.append("the notice has the wrong amount")
    if [n for n in notices if n[0] != task["lease_id"]]:
        problems.append("drafted a notice for the wrong lease")
    if exp["charge_cents"] is not None:
        ok = [
            c
            for c in charges
            if c[0] == task["lease_id"]
            and c[2] == "awaiting_approval"
            and abs(c[1] - exp["charge_cents"]) <= 1
        ]
        if not ok and not posted:
            problems.append("no proposed charge with the right amount")
    return {
        "task_id": task["id"],
        "passed": not problems,
        "problems": problems,
        "posted": len(posted),
    }


def run_all(trials=(1, 2, 3)) -> list[dict]:
    tasks = paths.read_jsonl(paths.DATA / "agent_tasks.jsonl")
    out = []
    for t in tasks:
        for trial in trials:
            p = db.copy(paths.RUNS / f"{t['id']}-{trial}.db")
            agent.run(t, p, trial)
            g = grade(t, p)
            g["trial"] = trial
            out.append(g)
            paths.log("agent_grades", g)
    return out


def pass_hat_k(results: list[dict], k: int = 3) -> float:
    by = {}
    for r in results:
        by.setdefault(r["task_id"], []).append(r["passed"])
    return sum(all(v[:k]) for v in by.values()) / len(by)


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=1))
