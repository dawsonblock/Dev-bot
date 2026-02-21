"""Unified memory router — controls all memory writes/reads with transaction staging."""


class MemoryRouter:
    """Routes memory operations to hot cache, vector store, and episodic ledger.

    Supports transaction staging: writes are buffered until commit().
    On abort(), staged writes are discarded.
    """

    def __init__(self, hot, vector, episodic):
        self.hot = hot
        self.vector = vector
        self.episodic = episodic
        self._staged_episodes = []
        self._staged_vectors = []
        self._in_txn = False

    def begin(self):
        """Begin a memory transaction — buffer writes until commit."""
        self._staged_episodes = []
        self._staged_vectors = []
        self._in_txn = True

    def commit(self):
        """Flush all staged writes to their stores."""
        for rec in self._staged_episodes:
            self.episodic.add(rec)
        for text, meta in self._staged_vectors:
            self.vector.add(text, metadata=meta)
        self._staged_episodes = []
        self._staged_vectors = []
        self._in_txn = False

    def abort(self):
        """Discard all staged writes."""
        self._staged_episodes = []
        self._staged_vectors = []
        self._in_txn = False

    # ── Write operations ──────────────────────────────

    def put_hot(self, item):
        """Hot cache writes are always immediate (read-only context)."""
        self.hot.put(item)

    def stage_episode(self, record):
        """Stage an episodic record. Committed only on txn.commit()."""
        if self._in_txn:
            self._staged_episodes.append(record)
        else:
            self.episodic.add(record)

    def stage_vector(self, text, metadata=None):
        """Stage a vector store entry. Committed only on txn.commit()."""
        if self._in_txn:
            self._staged_vectors.append((text, metadata or {}))
        else:
            self.vector.add(text, metadata=metadata)

    # ── Read operations ───────────────────────────────

    def get_context(self, n=10):
        """Read recent context from hot cache."""
        return self.hot.get_all()[-n:]

    def search(self, query, k=3):
        """Search vector store."""
        return self.vector.search(query, k=k)

    def get_episodes(self, n=10):
        """Get recent episodic records."""
        return self.episodic.last(n)

    def episode_strings(self, n=10):
        """Get recent episodes as formatted strings."""
        return self.episodic.to_strings(n)
