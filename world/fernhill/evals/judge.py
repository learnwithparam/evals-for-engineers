"""The finished grounded judge: one criterion, pass or fail, critique before verdict."""

import json

from .. import llm

SYSTEM = "\n".join(
    [
        "You grade one answer from the Fernhill Homes lease desk on ONE criterion: grounded.",
        "",
        "Pass: every claim in the answer is stated in the cited clauses, "
        "with the same numbers and the same limits.",
        'An answer of exactly "The lease does not say." passes, because it makes no claim.',
        "Fail: any claim is missing from the cited clauses, changes a number or a date, "
        "or drops a limit such as",
        '"not less than" or "with written consent".',
        "",
        "Write a one-sentence critique first, then the verdict.",
        'Reply with JSON only: {"critique": "...", "verdict": "pass" or "fail"}',
    ]
)


def messages(question: str, answer: str, cited: list[dict]) -> list[dict]:
    clause_lines = [f"[{clause['id']}] {clause['text']}" for clause in cited]
    clause_text = "\n".join(clause_lines) or "(no clauses cited)"
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": f"Question: {question}\n\nAnswer: {answer}\n\nCited clauses:\n{clause_text}",
        },
    ]


def judge(question: str, answer: str, cited: list[dict]) -> dict:
    reply = llm.complete(
        "judge", messages(question, answer, cited), llm.CallSettings(system="judge")
    )
    reply_text = reply.text
    json_text = reply_text[reply_text.find("{") : reply_text.rfind("}") + 1]
    verdict = json.loads(json_text)
    if verdict.get("verdict") not in ("pass", "fail"):
        raise ValueError("the judge must reply pass or fail")
    return verdict
