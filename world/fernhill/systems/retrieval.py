"""Keyword search over one lease's clauses (BM25, standard library only)."""

import math
import re
from collections import Counter

from .. import leases

STOP = set(
    ["a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "has", "have", "how", "i", "if", "in", "is", "it", "its", "of", "on", "or", "the", "this", "to", "what", "when", "who", "will", "with"]
)


def tokens(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]


def search(lease_id: str, query: str, k: int = 5) -> list[dict]:
    docs = leases.clauses(lease_id)
    toks = [tokens(d["heading"] + " " + d["text"]) for d in docs]
    n, avg = len(docs), sum(len(t) for t in toks) / max(1, len(docs))
    df = Counter(w for t in toks for w in set(t))
    q = tokens(query)
    scored = []
    for d, t in zip(docs, toks):
        tf, s = Counter(t), 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(t) / avg))
        scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return [d for _, d in scored[:k]]
