"""The grounded judge: one lease desk answer in, pass or fail out.

Run: uv run python cases.py train | uv run python run.py
It reads one JSON answer per line on stdin and writes one JSON verdict per line on stdout:
{"id": "desk-0009", "verdict": "pass" or "fail", "critique": "..."}

The prompt is grounded.md. With no key (replay), a reply comes from recorded.jsonl in this
folder or from the world's recordings. With a key in .env, add --record: each live reply is
saved in recorded.jsonl, so the checks can replay your own prompt later with no key.
"""

import json
import sys
from pathlib import Path

from fernhill import llm

HERE = Path(__file__).parent
PROMPT_FILE = HERE / "grounded.md"
RECORDINGS = HERE / "recorded.jsonl"


def build_messages(prompt: str, case: dict) -> list[dict]:
    """The same message shape as the finished judge: the prompt, then the answer to grade."""
    clause_lines = [f"[{clause['id']}] {clause['text']}" for clause in case["cited_clauses"]]
    clause_text = "\n".join(clause_lines) or "(no clauses cited)"
    question_and_answer = f"Question: {case['question']}\n\nAnswer: {case['answer']}"
    user_text = f"{question_and_answer}\n\nCited clauses:\n{clause_text}"
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_text},
    ]


def load_recordings() -> dict[str, str]:
    """Replies saved by an earlier live run with --record, by their key."""
    if not RECORDINGS.exists():
        return {}
    lines = RECORDINGS.read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return {row["key"]: row["reply"] for row in rows}


def save_recording(key: str, reply_text: str) -> None:
    row = {"key": key, "reply": reply_text, "role": "judge", "trial": 1}
    with open(RECORDINGS, "a") as recordings_file:
        recordings_file.write(json.dumps(row) + "\n")


def ask_judge(messages: list[dict], recordings: dict[str, str], record: bool) -> str:
    """The judge's reply text: from a recording when there is one, else from the model."""
    key = llm.key("judge", messages, 1)
    if key in recordings:
        return recordings[key]
    reply = llm.complete("judge", messages, llm.CallSettings(system="judge"))
    if record and not reply.replayed:
        save_recording(key, reply.text)
    return reply.text


def read_verdict(reply_text: str) -> dict:
    """Pull the JSON object out of the reply and keep only a pass or fail verdict."""
    start = reply_text.find("{")
    end = reply_text.rfind("}") + 1
    reply = json.loads(reply_text[start:end])
    # Capital letters read better in a report.
    verdict = str(reply.get("verdict", "")).strip().title()
    return {"verdict": verdict, "critique": reply.get("critique", "")}


def judge_all(cases: list[dict], record: bool = False) -> list[dict]:
    """A verdict for every case, in the order the cases came."""
    prompt = PROMPT_FILE.read_text().strip()
    recordings = load_recordings()
    verdicts = []
    for case in cases:
        reply_text = ask_judge(build_messages(prompt, case), recordings, record)
        verdicts.append({"id": case["id"], **read_verdict(reply_text)})
    return verdicts


def main() -> int:
    lines = [line for line in sys.stdin.read().splitlines() if line.strip()]
    cases = [json.loads(line) for line in lines]
    try:
        verdicts = judge_all(cases, record="--record" in sys.argv)
    except llm.ReplayMissingError as error:
        print(error, file=sys.stderr)
        return 2
    for verdict in verdicts:
        print(json.dumps(verdict))
    return 0


if __name__ == "__main__":
    sys.exit(main())
