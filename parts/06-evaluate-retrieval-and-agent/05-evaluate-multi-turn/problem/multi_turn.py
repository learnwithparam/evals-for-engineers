"""Score a multi-turn eval: did the whole conversation reach its goal, and where did it break?

Each row in conversations.jsonl is one chat between a tenant and the lease desk. "turns" holds one
true or false per desk reply, from a judge. "goal_met" says whether the tenant got what they came
for by the end, such as the right late fee and a payment plan.

It writes multi_turn.json.

Run: uv run python multi_turn.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def summarise(conversations: list[dict]) -> dict:
    """Return a dict with five keys.

    TODO:
    - "goal_rate": the share of conversations with goal_met true.
    - "all_turns_rate": the share where every turn is true.
    - "per_turn_rate": the share of all turns, over every conversation, that are true.
    - "first_fail_turns": for conversations with a false turn, a count by the number of the
      first false turn, counting from 1. The keys are strings, such as "2". Counter helps.
    - "recovered": the ids of conversations that had a false turn but still met the goal.
    Round every rate to 3 places.
    """
    raise NotImplementedError("write summarise() in multi_turn.py")


def main() -> None:
    summary = summarise(read_jsonl(HERE / "conversations.jsonl"))
    (HERE / "multi_turn.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Goal met in {summary['goal_rate']} of conversations.")
    every_turn = summary["all_turns_rate"]
    print(f"Every turn right in {every_turn}. Single turns right: {summary['per_turn_rate']}.")
    print("Wrote multi_turn.json")


if __name__ == "__main__":
    main()
