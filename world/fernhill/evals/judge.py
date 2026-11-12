"""The finished grounded judge: one criterion, pass or fail, critique before verdict."""
import json

from .. import llm

SYSTEM = """You grade one answer from the Fernhill Homes lease desk on ONE criterion: grounded.

Pass: every claim in the answer is stated in the cited clauses, with the same numbers and the same limits.
An answer of exactly "The lease does not say." passes, because it makes no claim.
Fail: any claim is missing from the cited clauses, changes a number or a date, or drops a limit such as
"not less than" or "with written consent".

Write a one-sentence critique first, then the verdict.
Reply with JSON only: {"critique": "...", "verdict": "pass" or "fail"}"""


def messages(question: str, answer: str, cited: list[dict]) -> list[dict]:
    ctx = "\n".join(f"[{c['id']}] {c['text']}" for c in cited) or "(no clauses cited)"
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Question: {question}\n\nAnswer: {answer}\n\nCited clauses:\n{ctx}"}]


def judge(question: str, answer: str, cited: list[dict]) -> dict:
    reply = llm.complete("judge", messages(question, answer, cited), system="judge")
    t = reply.text
    out = json.loads(t[t.find("{"): t.rfind("}") + 1])
    if out.get("verdict") not in ("pass", "fail"):
        raise ValueError("the judge must reply pass or fail")
    return out
