"""Formal state invariants — validated before every transaction commit."""


class InvariantViolation(Exception):
    """Raised when a state invariant is violated."""

    pass


class Invariants:
    """Container for formal state invariant rules.

    Each rule is a callable (state) -> bool.
    Violation aborts the transaction.
    """

    def __init__(self):
        self.rules = []

    def add(self, name, predicate):
        """Register a named invariant rule."""
        self.rules.append((name, predicate))

    def validate(self, state):
        """Check all invariants. Raises InvariantViolation on first failure."""
        for name, rule in self.rules:
            if not rule(state):
                raise InvariantViolation(f"Invariant '{name}' violated")
        return True


# ── Built-in invariant rules ──────────────────────────


def no_negative_incidents(state):
    """Incident count must never be negative."""
    return state.get("incident_count", 0) >= 0


def state_size_bounded(state, max_keys=100):
    """State dict must not grow unbounded."""
    return len(state) <= max_keys


def mode_valid(state):
    """If mode exists, it must be a recognized value."""
    mode = state.get("mode")
    if mode is None:
        return True
    return mode in {"normal", "safe", "degraded", "shutdown"}


def default_invariants():
    """Return an Invariants instance with the standard ruleset."""
    inv = Invariants()
    inv.add("no_negative_incidents", no_negative_incidents)
    inv.add("state_size_bounded", state_size_bounded)
    inv.add("mode_valid", mode_valid)
    return inv
