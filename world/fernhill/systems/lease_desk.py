"""Lease desk: staff ask a question about a unit's lease.

It answers from the clauses that retrieval finds, and cites each clause it relies on.
"""

import re

from .. import llm
from . import retrieval

ABSTAIN = "The lease does not say."
SYSTEM = (
    "You answer questions from Fernhill Homes staff about one lease. Use only the clauses given. "
    "Cite every clause you rely on by its id in square brackets, like [L014-c04]. "
    f"If the clauses do not answer the question, reply exactly: {ABSTAIN}"
)
CITATION = re.compile(r"\[(L\d{3}-[a-z]\d\d)\]")


def messages(question: str, clauses: list[dict]) -> list[dict]:
    clause_lines = [f"[{clause['id']}] {clause['heading']}: {clause['text']}" for clause in clauses]
    clause_text = "\n".join(clause_lines)
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nClauses:\n{clause_text}"},
    ]


def cited(answer: str) -> list[str]:
    """The clause ids an answer cites, each once, in the order they first appear."""
    citations = CITATION.findall(answer)
    return list(dict.fromkeys(citations))


def run(lease_id: str, question: str, how_many: int = 5, trial: int = 1) -> dict:
    found = retrieval.search(lease_id, question, how_many)
    settings = llm.CallSettings(system="lease-desk", trial=trial)
    reply = llm.complete("fast", messages(question, found), settings)
    return {
        "retrieved": [clause["id"] for clause in found],
        "answer": reply.text,
        "cited": cited(reply.text),
    }
