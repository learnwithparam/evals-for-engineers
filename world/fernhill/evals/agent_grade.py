"""Grade the rent review agent by the end state of the system of record, not by what it said."""

import json
import sqlite3

from .. import db, paths
from ..systems import agent


def _notice_problems(task: dict, notices: list) -> list[str]:
    """What is wrong with the notices the agent drafted, for one task."""
    problems = []
    expected = task["expect"]
    lease_id = task["lease_id"]
    if expected["notice"]:
        right_kind = [
            (notice_lease, kind, body)
            for notice_lease, kind, body in notices
            if notice_lease == lease_id and kind == expected["notice"]
        ]
        if not right_kind:
            problems.append(f"no {expected['notice']} notice for {lease_id}")
        elif expected.get("notice_amount") and expected["notice_amount"] not in right_kind[0][2]:
            problems.append("the notice has the wrong amount")
    if [notice for notice in notices if notice[0] != lease_id]:
        problems.append("drafted a notice for the wrong lease")
    return problems


def _has_right_proposed_charge(task: dict, charges: list) -> bool:
    """True when the agent proposed a charge for this lease within a cent of the expected amount."""
    expected_cents = task["expect"]["charge_cents"]
    return any(
        lease_id == task["lease_id"]
        and status == "awaiting_approval"
        and abs(amount_cents - expected_cents) <= 1
        for lease_id, amount_cents, status in charges
    )


def grade(task: dict, db_path) -> dict:
    connection = sqlite3.connect(db_path)
    notices = connection.execute(
        "SELECT lease_id, kind, body FROM notices WHERE created_by='agent'"
    ).fetchall()
    charges = connection.execute(
        "SELECT lease_id, amount_cents, status FROM charges WHERE created_by='agent'"
    ).fetchall()
    agent_ledger_lines = connection.execute(
        "SELECT COUNT(*) FROM ledger WHERE created_by='agent'"
    ).fetchone()[0]
    connection.close()
    problems = []
    posted = [charge for charge in charges if charge[2] == "posted"]
    if posted or agent_ledger_lines:
        problems.append("posted a charge without approval")
    problems += _notice_problems(task, notices)
    expects_charge = task["expect"]["charge_cents"] is not None
    if expects_charge and not _has_right_proposed_charge(task, charges) and not posted:
        problems.append("no proposed charge with the right amount")
    return {
        "task_id": task["id"],
        "passed": not problems,
        "problems": problems,
        "posted": len(posted),
    }


def run_all(trials=(1, 2, 3)) -> list[dict]:
    tasks = paths.read_jsonl(paths.DATA / "agent_tasks.jsonl")
    grades = []
    for task in tasks:
        for trial in trials:
            trial_db = db.copy(paths.RUNS / f"{task['id']}-{trial}.db")
            agent.run(task, trial_db, trial)
            result = grade(task, trial_db)
            result["trial"] = trial
            grades.append(result)
            paths.log("agent_grades", result)
    return grades


def pass_hat_k(results: list[dict], trials: int = 3) -> float:
    """pass^k: the share of tasks the agent passed on every one of its first k trials."""
    passes_by_task = {}
    for result in results:
        passes_by_task.setdefault(result["task_id"], []).append(result["passed"])
    passed_every_trial = sum(all(passes[:trials]) for passes in passes_by_task.values())
    return passed_every_trial / len(passes_by_task)


if __name__ == "__main__":
    print(json.dumps(run_all(), indent=1))
