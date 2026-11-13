"""A binary judge for one criterion: the lease desk abstains when the lease is silent.

Reads one JSON object per line on stdin:
  {"id": "...", "question": "...", "answer": "...", "clauses": [{"id": "...", "text": "..."}]}
The clauses are the ones the lease desk's search found. It writes one line per input:
  {"id": "...", "verdict": "pass" or "fail", "critique": "..."}

Run: uv run python align.py   (it calls this judge on the dev labels)
"""

import json
import sys
from pathlib import Path

from fernhill import llm

# The only part you change. Say when an answer passes and when it fails, in plain rules.
CRITERION = "\n".join(
    [
        "Pass: a clause answers the question and the answer gives that answer.",
        'Pass: no clause answers the question and the answer is exactly "The lease does not say."',
        "Fail: the answer makes a claim when no clause answers the question.",
        'Fail: the answer says "The lease does not say." when a clause does answer the question.',
    ]
)

SYSTEM = "\n".join(
    [
        "You grade one answer from the Fernhill Homes lease desk on ONE criterion: "
        "it abstains when the lease is silent.",
        "",
        CRITERION,
        "",
        "Write a one-sentence critique first, then the verdict.",
        'Reply with JSON only: {"critique": "...", "verdict": "pass" or "fail"}',
    ]
)

STEP_REPLIES = "parts/06-evaluate-retrieval-and-agent/helpers/abstention_replay.jsonl"


def find_repo_root() -> Path:
    # You may run this script from any folder, so look upward for the file that marks the repo.
    for folder in Path(__file__).resolve().parents:
        if (folder / "pyproject.toml").exists():
            return folder
    raise SystemExit("Run this inside the course repo.")


def load_step_replies(repo_root: Path) -> None:
    """Replay knows the finished system's prompts. This adds the replies recorded for this step."""
    recorded = llm.recorded()
    with open(repo_root / STEP_REPLIES) as replies_file:
        for line in replies_file:
            if line.strip():
                row = json.loads(line)
                recorded[row["key"]] = row


def messages(case: dict) -> list[dict]:
    clause_lines = [f"[{clause['id']}] {clause['text']}" for clause in case["clauses"]]
    clause_text = "\n".join(clause_lines) or "(no clauses found)"
    question = f"Question: {case['question']}"
    answer = f"Answer: {case['answer']}"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"{question}\n\n{answer}\n\nClauses found:\n{clause_text}"},
    ]


def judge(case: dict) -> dict:
    settings = llm.CallSettings(system="abstention-judge")
    reply = llm.complete("judge", messages(case), settings).text
    verdict = json.loads(reply[reply.find("{") : reply.rfind("}") + 1])
    if verdict.get("verdict") not in ("pass", "fail"):
        raise ValueError("the judge must reply pass or fail")
    return {"id": case["id"], "verdict": verdict["verdict"], "critique": verdict["critique"]}


def main() -> None:
    load_step_replies(find_repo_root())
    for line in sys.stdin:
        if line.strip():
            print(json.dumps(judge(json.loads(line))), flush=True)


if __name__ == "__main__":
    main()
