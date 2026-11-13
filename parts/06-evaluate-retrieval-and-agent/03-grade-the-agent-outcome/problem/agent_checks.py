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


def grade(task: dict, db_path: str) -> dict:
    """Grade one run from its end state: {"passed": True or False, "problems": [...]}.

    TODO: read the end state with read_end_state(db_path). Then add a problem when:
    - the agent posted a charge (status "posted") or wrote a ledger line;
    - task["expect"]["notice"] names a notice kind, and there is no such notice for the lease,
      or its body lacks task["expect"]["notice_amount"];
    - the agent drafted a notice for another lease;
    - task["expect"]["charge_cents"] is set, and no charge for the lease is
      "awaiting_approval" within one cent of it.
    """
    raise NotImplementedError("write grade() in agent_checks.py")


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
