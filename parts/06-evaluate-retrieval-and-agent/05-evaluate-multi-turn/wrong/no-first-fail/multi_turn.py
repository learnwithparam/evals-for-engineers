"""Score a multi-turn eval: did the whole conversation reach its goal, and where did it break?

Each row in conversations.jsonl is one chat between a tenant and the lease desk. "turns" holds one
true or false per desk reply, from a judge. "goal_met" says whether the tenant got what they came
for by the end, such as the right late fee and a payment plan.

It writes multi_turn.json.

Run: uv run python multi_turn.py
"""

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def read_jsonl(path: Path) -> list[dict]:
    with open(path) as jsonl_file:
        return [json.loads(line) for line in jsonl_file if line.strip()]


def summarise(conversations: list[dict]) -> dict:
    """The numbers that tell a whole conversation from a single reply."""
    all_turns = [conversation for conversation in conversations if all(conversation["turns"])]
    goal = [conversation for conversation in conversations if conversation["goal_met"]]
    every_turn = [ok for conversation in conversations for ok in conversation["turns"]]
    first_fails = Counter(
        len(conversation["turns"])
        for conversation in conversations
        if not all(conversation["turns"])
    )
    recovered = [
        conversation["id"]
        for conversation in conversations
        if conversation["goal_met"] and not all(conversation["turns"])
    ]
    return {
        "goal_rate": round(len(goal) / len(conversations), 3),
        "all_turns_rate": round(len(all_turns) / len(conversations), 3),
        "per_turn_rate": round(sum(every_turn) / len(every_turn), 3),
        "first_fail_turns": {str(turn): count for turn, count in sorted(first_fails.items())},
        "recovered": recovered,
    }


def main() -> None:
    summary = summarise(read_jsonl(HERE / "conversations.jsonl"))
    (HERE / "multi_turn.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Goal met in {summary['goal_rate']} of conversations.")
    every_turn = summary["all_turns_rate"]
    print(f"Every turn right in {every_turn}. Single turns right: {summary['per_turn_rate']}.")
    print("Wrote multi_turn.json")


if __name__ == "__main__":
    main()
