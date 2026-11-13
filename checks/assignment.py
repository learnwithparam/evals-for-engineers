"""Check the Inspect AI assignment: uv run checks/assignment.py [--dir assignment]

It tests each Done-when line and writes result.json into the folder it checked.
Exit 0 when every line passes, 1 when one fails.
"""

import json
import sys
from importlib import metadata
from pathlib import Path

from fernhill.evals import gate
from inspect_ai.log import EvalLog, list_eval_logs, read_eval_log

PINNED_VERSION = "0.3.289"
LINES = [
    "inspect-ai resolves to 0.3.289",
    "an eval log has one score per dataset row",
    "the failing rows match the hand-built gate",
]


def installed_version() -> str:
    try:
        return metadata.version("inspect-ai")
    except metadata.PackageNotFoundError:
        return "none"


def latest_log(folder: Path) -> EvalLog | None:
    logs = list_eval_logs(str(folder / "logs"))
    if not logs:
        return None
    return read_eval_log(logs[0])


def scored_rows(log: EvalLog) -> dict[str, dict]:
    """The reduced score of each dataset row, by lease id."""
    if not log.reductions:
        return {}
    return {str(entry.sample_id): entry.value for entry in log.reductions[0].samples}


def failing_rows(rows: dict[str, dict]) -> set[str]:
    return {lease_id for lease_id, fields in rows.items() if not all(fields.values())}


def hand_built_failures(release: str) -> set[str]:
    cases = gate.case_results(release)["cases"]
    return {lease_id for lease_id, fields in cases.items() if not all(fields.values())}


def judge(folder: Path) -> dict:
    log = latest_log(folder)
    rows = scored_rows(log) if log else {}
    release = log.eval.task_args.get("release", "cheaper-model") if log else "cheaper-model"
    expected = hand_built_failures(release)
    log_version = log.eval.packages.get("inspect_ai") if log else None
    return {
        LINES[0]: installed_version() == PINNED_VERSION and log_version in (None, PINNED_VERSION),
        LINES[1]: bool(rows) and len(rows) == len(gate.case_results(release)["cases"]),
        LINES[2]: bool(expected) and failing_rows(rows) == expected,
    }


def main(arguments: list[str]) -> int:
    folder = Path(arguments[arguments.index("--dir") + 1] if "--dir" in arguments else "assignment")
    verdicts = {line: "pass" if ok else "fail" for line, ok in judge(folder).items()}
    result = {"inspect_ai": installed_version(), "lines": verdicts}
    (folder / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    for line, verdict in verdicts.items():
        print(f"{verdict.upper()}  {line}")
    return 0 if set(verdicts.values()) == {"pass"} else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
