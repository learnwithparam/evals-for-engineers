"""Split the golden cases into a regression suite, a capability suite and a refresh list.

Each row in cases.jsonl has a "history": the result of the last 5 runs, newest last, with
P for pass and F for fail. It also has the "template" the case was written on.

It writes suites.json.

Run: uv run python split_suites.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent

# Cases on any other template are old, because production has moved on.
CURRENT_TEMPLATE = "FH-RES-V3"


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def split(cases: list[dict]) -> dict[str, list[str]]:
    """Sort case ids into the three lists.

    regression: passed all 5 runs. It guards what works, so any failure is a real break.
    capability: failed at least 3 of the 5 runs. It measures what the system cannot do yet.
    refresh: written on a template other than CURRENT_TEMPLATE, so it needs new data.
    A case can sit in refresh and in another list. A flaky case is in neither of the first two.
    """
    return {
        "regression": [case["id"] for case in cases if case["history"] == "PPPPP"],
        "capability": [case["id"] for case in cases if case["history"].count("F") >= 3],
        "refresh": [case["id"] for case in cases if False],
    }


def main() -> None:
    suites = split(read_jsonl(HERE / "cases.jsonl"))
    (HERE / "suites.json").write_text(json.dumps(suites, indent=2) + "\n")
    for name, ids in suites.items():
        print(f"  {name:<11} {len(ids)} cases")
    print("Wrote suites.json")


if __name__ == "__main__":
    main()
