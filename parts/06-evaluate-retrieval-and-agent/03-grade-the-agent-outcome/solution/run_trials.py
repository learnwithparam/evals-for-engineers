"""Run the agent 3 times on each of its 20 tasks, then grade every run with agent_checks.py.

You do not need to change this file. Each trial runs against a fresh copy of the database
in world/runs/agent-trials/, so one trial cannot change what the next one sees.
The list of runs it grades is world/runs/agent-trials/runs.jsonl.

Run: uv run python run_trials.py
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
TRIALS = 3


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def run_the_agent(repo_root: Path) -> Path:
    """Runs every trial and writes runs.jsonl, leaving out the finished grader's answers."""
    helper = repo_root / "parts/06-evaluate-retrieval-and-agent/helpers/agent_runs.py"
    out_dir = repo_root / "world/runs/agent-trials"
    command = [sys.executable, str(helper), "--out-dir", str(out_dir)]
    finished = subprocess.run(command, capture_output=True, text=True, check=True)
    runs_file = out_dir / "runs.jsonl"
    with open(runs_file, "w") as out:
        for run in json.loads(finished.stdout):
            del run["expected"]
            out.write(json.dumps(run) + "\n")
    return runs_file


def grade_the_runs(runs_file: Path) -> list[dict]:
    command = [sys.executable, str(HERE / "agent_checks.py"), "--runs", str(runs_file)]
    finished = subprocess.run(command, capture_output=True, text=True)
    if finished.returncode != 0:
        raise SystemExit(finished.stderr.strip().splitlines()[-1])
    return [json.loads(line) for line in finished.stdout.splitlines() if line.strip()]


def main() -> None:
    grades = grade_the_runs(run_the_agent(find_repo_root()))
    passes_by_task = defaultdict(list)
    for grade in grades:
        passes_by_task[grade["task_id"]].append(grade["passed"])
        if not grade["passed"]:
            problems = "; ".join(grade["problems"])
            print(f"  FAIL  {grade['task_id']} trial {grade['trial']}: {problems}")
    every_trial = sum(all(passes) for passes in passes_by_task.values())
    pass_hat_three = every_trial / len(passes_by_task)
    print(f"{len(grades)} runs graded. pass^{TRIALS} = {pass_hat_three:.2f}")


if __name__ == "__main__":
    main()
