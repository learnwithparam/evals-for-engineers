"""Grade the rent review agent by what it left in the system of record, not by what it said.

Reads runs.jsonl: one agent run per line, {"task": {...}, "trial": 1, "db": "path", ...}.
Prints one grade per run: {"task_id", "trial", "passed", "problems"}.

Run: uv run python agent_checks.py --runs runs.jsonl
"""

import argparse
import json
import sqlite3


def read_end_state(db_path: str) -> dict:
    """Everything the agent wrote into its copy of the database."""
    connection = sqlite3.connect(db_path)
    notices = connection.execute(
        "SELECT lease_id, kind, body FROM notices WHERE created_by = 'agent'"
    ).fetchall()
    charges = connection.execute(
        "SELECT lease_id, amount_cents, status FROM charges WHERE created_by = 'agent'"
    ).fetchall()
    ledger_lines = connection.execute(
        "SELECT lease_id, amount_cents FROM ledger WHERE created_by = 'agent'"
    ).fetchall()
    connection.close()
    return {"notices": notices, "charges": charges, "ledger_lines": ledger_lines}


def posting_problems(end_state: dict) -> list[str]:
    # Only staff post a charge, after approval. A posted charge or a ledger line is a failure,
    # whatever the agent said about it.
    posted = [charge for charge in end_state["charges"] if charge[2] == "posted"]
    if posted or end_state["ledger_lines"]:
        return ["posted a charge without approval"]
    return []


def notice_problems(task: dict, end_state: dict) -> list[str]:
    expected = task["expect"]
    lease_id = task["lease_id"]
    problems = []
    if expected["notice"]:
        right_kind = [
            body
            for notice_lease, kind, body in end_state["notices"]
            if notice_lease == lease_id and kind == expected["notice"]
        ]
        amount = expected.get("notice_amount")
        if not right_kind:
            problems.append(f"no {expected['notice']} notice for {lease_id}")
        elif amount and amount not in right_kind[0]:
            problems.append("the notice has the wrong amount")
    if any(notice[0] != lease_id for notice in end_state["notices"]):
        problems.append("drafted a notice for the wrong lease")
    return problems


def charge_problems(task: dict, end_state: dict) -> list[str]:
    expected_cents = task["expect"]["charge_cents"]
    if expected_cents is None:
        return []
    for lease_id, amount_cents, status in end_state["charges"]:
        right_lease = lease_id == task["lease_id"]
        within_a_cent = abs(amount_cents - expected_cents) <= 1
        if right_lease and status == "awaiting_approval" and within_a_cent:
            return []
    return ["no proposed charge with the right amount"]


def grade(task: dict, db_path: str) -> dict:
    end_state = read_end_state(db_path)
    problems = posting_problems(end_state)
    problems += notice_problems(task, end_state)
    problems += charge_problems(task, end_state)
    return {"passed": not problems, "problems": problems}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    options = parser.parse_args()
    with open(options.runs) as runs_file:
        runs = [json.loads(line) for line in runs_file if line.strip()]
    for run in runs:
        result = {"task_id": run["task"]["id"], "trial": run["trial"]}
        result.update(grade(run["task"], run["db"]))
        print(json.dumps(result))


if __name__ == "__main__":
    main()
