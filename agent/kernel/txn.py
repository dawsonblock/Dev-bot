"""Transaction engine — atomic begin / commit / abort with state snapshots."""

import copy


class Transaction:
    """Context-manager transactional wrapper around agent state.

    Usage::

        with Transaction(state) as txn:
            # ... mutate state ...
            if something_wrong:
                txn.abort()
            else:
                txn.commit()

    If an exception propagates, the transaction auto-aborts.
    """

    def __init__(self, state, memory_router=None):
        self.state = state
        self.memory = memory_router
        self._snapshot = None
        self._active = False
        self._committed = False

    def __enter__(self):
        self._snapshot = copy.deepcopy(self.state)
        self._active = True
        self._committed = False
        if self.memory:
            self.memory.begin()
        return self

    def commit(self):
        """Finalize the transaction — keep current state, flush staged memory."""
        self._active = False
        self._committed = True
        if self.memory:
            self.memory.commit()

    def abort(self):
        """Roll back state to the pre-transaction snapshot."""
        if self._active:
            self.state.clear()
            self.state.update(self._snapshot)
            self._active = False
            if self.memory:
                self.memory.abort()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.abort()
        elif self._active and not self._committed:
            self.abort()
        return False
