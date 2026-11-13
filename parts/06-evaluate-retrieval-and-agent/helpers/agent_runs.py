"""Run the rent review agent on every task, 3 trials each, in replay mode.

Each trial runs against its own fresh copy of the system of record. It prints one JSON list:
the task, the trial, the path of that copy, the agent's steps and last message, and the
finished grader's grade. The checks of grade-the-agent-outcome and the learner's
run_trials.py both use it.

Run: uv run python parts/06-evaluate-retrieval-and-agent/helpers/agent_runs.py --out-dir DIR
"""

import argparse
import json
from pathlib import Path

from fernhill import db, paths
from fernhill.evals import agent_grade
from fernhill.systems import agent

TRIALS = (1, 2, 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    options = parser.parse_args()
    out_dir = Path(options.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for task in paths.read_jsonl(paths.DATA / "agent_tasks.jsonl"):
        for trial in TRIALS:
            trial_db = db.copy(out_dir / f"{task['id']}-{trial}.db")
            result = agent.run(task, trial_db, trial)
            grade = agent_grade.grade(task, trial_db)
            run = {"task": task, "trial": trial, "db": str(trial_db)}
            run["steps"] = result["steps"]
            run["final"] = result["final"]
            run["expected"] = {"passed": grade["passed"], "posted": grade["posted"]}
            runs.append(run)
    print(json.dumps(runs))


if __name__ == "__main__":
    main()
