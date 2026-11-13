"""What the map-agent-failures check compares your work with.

It grades all 80 recorded agent runs (20 tasks, 4 trials) by their end state, replaying each
one against a fresh copy of the database. For the failed runs, it finds the last planned step
that went right and the first that went wrong, with the rule map_failures.py states.

Run: uv run python parts/06-evaluate-retrieval-and-agent/helpers/agent_failures.py
"""

import importlib.util
import json
import tempfile
from collections import Counter
from pathlib import Path

from fernhill import db, paths
from fernhill.evals import agent_grade
from fernhill.systems import agent

SAMPLE = Path(__file__).parents[1] / "04-map-agent-failures" / "solution" / "map_failures.py"


def sample_answer():
    spec = importlib.util.spec_from_file_location("map_failures", SAMPLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def failed_by_end_state(tasks: dict, traces: list[dict], scratch: Path) -> set[str]:
    failed = set()
    for trace in traces:
        task = tasks[trace["task_id"]]
        trial_db = db.copy(scratch / f"{trace['trace_id']}.db")
        agent.run(task, trial_db, trace["trial"])
        if not agent_grade.grade(task, trial_db)["passed"]:
            failed.add(trace["trace_id"])
    return failed


def main() -> None:
    tasks = {task["id"]: task for task in paths.read_jsonl(paths.DATA / "agent_tasks.jsonl")}
    traces = paths.read_jsonl(paths.TRACES / "agent.jsonl")
    with tempfile.TemporaryDirectory() as scratch:
        failed = failed_by_end_state(tasks, traces, Path(scratch))
    walk = sample_answer()
    cells = Counter()
    walked_failed = set()
    for trace in traces:
        failure = walk.first_failure(trace, tasks[trace["task_id"]])
        if failure is not None:
            cells["/".join(failure)] += 1
            walked_failed.add(trace["trace_id"])
    if walked_failed != failed:
        raise SystemExit("the walk and the end state disagree on which runs failed")
    print(json.dumps({"failed": sorted(failed), "traces": len(traces), "cells": cells}))


if __name__ == "__main__":
    main()
