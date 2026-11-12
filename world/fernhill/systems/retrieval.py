"""Keyword search over one lease's clauses (BM25, standard library only)."""

import math
import re
from collections import Counter

from .. import leases

# Words too common to say anything about which clause a question is about.
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "when",
    "who",
    "will",
    "with",
}

# The two standard BM25 settings: how fast repeats of a word stop adding to the score, and how
# much a long clause is held back against a short one.
WORD_REPEAT_LIMIT = 1.2
LENGTH_WEIGHT = 0.75


def words(text: str) -> list[str]:
    """The lowercase words and numbers in a text, without the stop words."""
    all_words = re.findall(r"[a-z0-9]+", text.lower())
    return [word for word in all_words if word not in STOP_WORDS]


def search(lease_id: str, query: str, how_many: int = 5) -> list[dict]:
    """The clauses of one lease that best match the query, best first."""
    clauses = leases.clauses(lease_id)
    clause_words = [words(clause["heading"] + " " + clause["text"]) for clause in clauses]
    clause_count = len(clauses)
    average_length = sum(len(each) for each in clause_words) / max(1, clause_count)
    # How many clauses each word appears in; a word found in few clauses counts for more.
    clauses_with_word = Counter(word for each in clause_words for word in set(each))
    query_words = words(query)
    scored = []
    for clause, its_words in zip(clauses, clause_words, strict=True):
        times_in_clause, score = Counter(its_words), 0.0
        length_share = LENGTH_WEIGHT * len(its_words) / average_length
        length_penalty = WORD_REPEAT_LIMIT * (1 - LENGTH_WEIGHT + length_share)
        for word in query_words:
            if word not in times_in_clause:
                continue
            seen = clauses_with_word[word]
            rarity = math.log(1 + (clause_count - seen + 0.5) / (seen + 0.5))
            repeats = times_in_clause[word]
            score += rarity * repeats * (WORD_REPEAT_LIMIT + 1) / (repeats + length_penalty)
        scored.append((score, clause))
    scored.sort(key=lambda pair: -pair[0])
    return [clause for _, clause in scored[:how_many]]
