"""Lease desk: staff ask a question about a unit's lease; it answers from retrieved clauses, with citations."""

import re

from .. import llm
from . import retrieval

ABSTAIN = "The lease does not say."
SYSTEM = (
    "You answer questions from Fernhill Homes staff about one lease. Use only the clauses given. Cite every "
    "clause you rely on by its id in square brackets, like [L014-c04]. If the clauses do not answer the "
    f"question, reply exactly: {ABSTAIN}"
)
CITE = re.compile(r"\[(L\d{3}-[a-z]\d\d)\]")


def messages(question: str, clauses: list[dict]) -> list[dict]:
    ctx = "\n".join(f"[{c['id']}] {c['heading']}: {c['text']}" for c in clauses)
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nClauses:\n{ctx}"},
    ]


def cited(answer: str) -> list[str]:
    return list(dict.fromkeys(CITE.findall(answer)))


def run(lease_id: str, question: str, k: int = 5, trial: int = 1) -> dict:
    found = retrieval.search(lease_id, question, k)
    reply = llm.complete("fast", messages(question, found), trial=trial, system="lease-desk")
    return {"retrieved": [c["id"] for c in found], "answer": reply.text, "cited": cited(reply.text)}
