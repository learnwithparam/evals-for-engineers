"""Map where the rent review agent fails: the last step that went right, and the first that
went wrong, for every failed run in world/data/traces/agent.jsonl.

It writes transitions.csv (last_good, first_failed, count) and next_fix.txt.

Run: uv run python map_failures.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent

# The steps a good run takes, by kind of task. These are the state names everyone uses.
CHARGE_PLAN = ["get_abstract", "search_lease", "get_ledger", "propose_charge"]
NOTICE_PLAN = ["get_abstract", "search_lease", "draft_notice"]
PLAN = {
    "missed-step": CHARGE_PLAN,
    "pet-fee-conflict": CHARGE_PLAN,
    "rent-step-notice": NOTICE_PLAN,
    "renewal-offer": NOTICE_PLAN,
}


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def first_failure(trace: dict, task: dict) -> tuple[str, str] | None:
    # Blame the last step the agent took, and the step before it.
    if not trace["final"] or "Posted" in trace["final"] or "Nothing" in trace["final"]:
        tools = ["start"] + [step["tool"] for step in trace["steps"]]
        return tools[-2], tools[-1]
    return None


def main() -> None:
    repo_root = find_repo_root()
    tasks = {task["id"]: task for task in read_jsonl(repo_root / "world/data/agent_tasks.jsonl")}
    traces = read_jsonl(repo_root / "world/data/traces/agent.jsonl")
    cells = Counter()
    for trace in traces:
        failure = first_failure(trace, tasks[trace["task_id"]])
        if failure is not None:
            cells[failure] += 1
    with open(HERE / "transitions.csv", "w", newline="") as transitions_file:
        writer = csv.writer(transitions_file)
        writer.writerow(["last_good", "first_failed", "count"])
        for (last_good, first_failed), count in cells.most_common():
            writer.writerow([last_good, first_failed, count])
            print(f"  {last_good:<14} -> {first_failed:<16} {count}")
    (last_good, first_failed), count = cells.most_common(1)[0]
    next_fix = f"{last_good} -> {first_failed}: {count} of {sum(cells.values())} failed runs."
    (HERE / "next_fix.txt").write_text(next_fix + "\n")
    print(f"Next fix: {next_fix}")


if __name__ == "__main__":
    main()
