import math
from collections import Counter


def vec(text):
    return Counter(text.lower().split())


def cosine(a, b):
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / max(1e-9, na * nb)


class VectorStore:
    def __init__(self):
        self.db = []

    def add(self, text, metadata=None):
        self.db.append((text, vec(text), metadata or {}))

    def search(self, q, k=3):
        if not self.db:
            return []
        qv = vec(q)
        scored = [(cosine(qv, v), t) for t, v, _ in self.db]
        return [t for _, t in sorted(scored, reverse=True)[:k]]
