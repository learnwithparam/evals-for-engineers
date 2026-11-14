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
    """Sort case ids into three lists: "regression", "capability" and "refresh".

    TODO: regression holds the cases that passed all 5 runs. capability holds the cases that
    failed at least 3 of the 5. refresh holds the cases not written on CURRENT_TEMPLATE.
    A case can sit in refresh and in another list. A flaky case is in neither of the first two.
    """
    raise NotImplementedError("write split() in split_suites.py")


def main() -> None:
    suites = split(read_jsonl(HERE / "cases.jsonl"))
    (HERE / "suites.json").write_text(json.dumps(suites, indent=2) + "\n")
    for name, ids in suites.items():
        print(f"  {name:<11} {len(ids)} cases")
    print("Wrote suites.json")


if __name__ == "__main__":
    main()
