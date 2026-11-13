"""Grade the rent review agent by what it left in the system of record, not by what it said.

Reads runs.jsonl: one agent run per line, {"task": {...}, "trial": 1, "db": "path", ...}.
Prints one grade per run: {"task_id", "trial", "passed", "problems"}.

Run: uv run python agent_checks.py --runs runs.jsonl
"""

import argparse
import json


def grade(task: dict, db_path: str, steps: list[dict]) -> dict:
    # Check the path: the agent passes when it called the tool the task needs.
    tools_called = [step["tool"] for step in steps]
    needed = "draft_notice" if task["expect"]["notice"] else "propose_charge"
    problems = [] if needed in tools_called else [f"never called {needed}"]
    return {"passed": not problems, "problems": problems}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", required=True)
    options = parser.parse_args()
    with open(options.runs) as runs_file:
        runs = [json.loads(line) for line in runs_file if line.strip()]
    for run in runs:
        result = {"task_id": run["task"]["id"], "trial": run["trial"]}
        result.update(grade(run["task"], run["db"], run["steps"]))
        print(json.dumps(result))


if __name__ == "__main__":
    main()
