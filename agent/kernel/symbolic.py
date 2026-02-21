"""Symbolic invariant checker — property enumeration and boundary verification.

Generates boundary test cases from invariant rules and reports which
invariants are provably satisfiable or violated under edge conditions.
"""

import copy
from .invariants import default_invariants, InvariantViolation


class PropertyResult:
    """Result of checking a single property."""

    def __init__(self, name, passed, detail=""):
        self.name = name
        self.passed = passed
        self.detail = detail

    def __repr__(self):
        tag = "HOLD" if self.passed else "VIOLATED"
        return f"<{tag} {self.name}: {self.detail}>"


class SymbolicChecker:
    """Symbolic invariant checker.

    Enumerates invariant properties by generating boundary states
    and checking whether invariants hold or correctly reject.
    """

    # Boundary values to probe
    BOUNDARY_VALUES = {
        "int": [0, 1, -1, 100, -100, 999999],
        "str": ["", "normal", "safe", "degraded", "chaos", "x" * 1000],
        "bool": [True, False],
    }

    def __init__(self, invariants=None):
        self.invariants = invariants or default_invariants()

    def generate_boundary_states(self, base_state=None):
        """Generate boundary test states from a base state.

        Returns a list of (description, state) tuples.
        """
        base = base_state or {
            "incident_count": 0,
            "mode": "normal",
        }

        states = [("baseline", dict(base))]

        # Probe incident_count boundaries
        for val in self.BOUNDARY_VALUES["int"]:
            s = dict(base)
            s["incident_count"] = val
            states.append((f"incident_count={val}", s))

        # Probe mode boundaries
        for val in self.BOUNDARY_VALUES["str"]:
            s = dict(base)
            s["mode"] = val
            states.append((f"mode='{val}'", s))

        # Probe state size boundaries
        for size in [0, 10, 50, 99, 100, 101, 200]:
            s = {f"key_{i}": i for i in range(size)}
            s["incident_count"] = 0
            s["mode"] = "normal"
            states.append((f"state_size={size}", s))

        return states

    def check_all(self, base_state=None):
        """Run all boundary states through invariant checker.

        Returns:
            list of PropertyResult
        """
        results = []
        states = self.generate_boundary_states(base_state)

        for desc, state in states:
            try:
                self.invariants.validate(state)
                results.append(PropertyResult(desc, True, "invariants hold"))
            except InvariantViolation as e:
                results.append(PropertyResult(desc, False, str(e)))

        return results

    def report(self, base_state=None):
        """Generate a structured report of all property checks."""
        results = self.check_all(base_state)
        held = sum(1 for r in results if r.passed)
        violated = sum(1 for r in results if not r.passed)

        return {
            "total": len(results),
            "held": held,
            "violated": violated,
            "properties": [
                {"name": r.name, "passed": r.passed, "detail": r.detail}
                for r in results
            ],
        }

    def prove_satisfiability(self):
        """Check if invariants are satisfiable (at least one valid state exists)."""
        results = self.check_all()
        satisfiable = any(r.passed for r in results)
        return satisfiable, sum(1 for r in results if r.passed)
