"""Print the newest Inspect log in a folder as JSON: uv run checks/read_inspect_log.py <folder>

The output is {"samples": {id: {"verdict": "pass" or "fail", "input": text}}}.
It is empty when the folder has no log, so a hand-typed answer cannot match it.
"""

import json
import sys
from pathlib import Path

from inspect_ai.log import list_eval_logs, read_eval_log


def verdict_of(sample) -> str:
    scores = sample.scores or {}
    value = next(iter(scores.values())).value if scores else None
    return "pass" if value == "C" else "fail"


def main(folder: str) -> dict:
    logs = list_eval_logs(str(Path(folder) / "logs"))
    if not logs:
        return {"samples": {}}
    log = read_eval_log(logs[0])
    samples = {}
    for sample in log.samples or []:
        samples[str(sample.id)] = {"verdict": verdict_of(sample), "input": str(sample.input)}
    return {"samples": samples}


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1])))
