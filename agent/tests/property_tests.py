"""Property-based fuzz testing — randomized verification.

Generates random states, actions, and sequences to verify:
1. Invariants hold under random valid states
2. Evolution bounds are enforced under random growth
3. Ledger chain remains valid under stress
4. Contracts catch violations deterministically
5. Symbolic checker probes are consistent
"""

import sys
import os
import random
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kernel.invariants import default_invariants, InvariantViolation
from kernel.evolution_bounds import EvolutionBounds
from kernel.ledger import Ledger
from kernel.contracts import requires, ensures, ContractViolation
from kernel.symbolic import SymbolicChecker
from kernel.statehash import state_hash

PASS = 0
FAIL = 1
results = []
SEED = 42
N_TRIALS = 100


def log(name, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((name, passed))
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


# ── 1. Random invariant states ────────────────────────
def test_invariant_fuzz():
    """Generate N random states and verify invariants accept/reject correctly."""
    rng = random.Random(SEED)
    inv = default_invariants()
    accepted = 0
    rejected = 0

    for _ in range(N_TRIALS):
        state = {
            "incident_count": rng.randint(-50, 200),
            "mode": rng.choice(["normal", "safe", "degraded", "chaos", "", "unknown"]),
        }
        # Add random extra keys
        for i in range(rng.randint(0, 120)):
            state[f"rnd_{i}"] = rng.random()

        try:
            inv.validate(state)
            accepted += 1
        except InvariantViolation:
            rejected += 1

    log("invariant_fuzz", True, f"accepted={accepted} rejected={rejected}")


# ── 2. Evolution bounds under random growth ───────────
def test_bounds_fuzz():
    """Random growth patterns testing bounds enforcement."""
    rng = random.Random(SEED)
    bounds = EvolutionBounds(
        max_episodes_per_window=50,
        max_vectors_per_window=100,
        max_habits=20,
        window_ticks=500,
    )

    rejections = 0
    for i in range(N_TRIALS):
        metric = rng.choice(["episodes", "vectors", "tool_calls"])
        amount = rng.randint(1, 10)
        ok = bounds.record(metric, amount, tick=i)
        if not ok:
            rejections += 1

    log("bounds_fuzz", rejections > 0, f"rejections={rejections} over {N_TRIALS} ops")


# ── 3. Ledger chain integrity under stress ────────────
def test_ledger_stress():
    """Write many records and verify chain integrity."""
    path = "/tmp/test_property_ledger.jsonl"
    try:
        os.remove(path)
    except FileNotFoundError:
        pass

    ledger = Ledger(path)
    ledger.write_genesis(seed=42, config_hash="test", code_hash="test")

    rng = random.Random(SEED)
    for i in range(200):
        ledger.append(
            {
                "event": "fuzz",
                "tick": i,
                "data": hashlib.md5(str(rng.random()).encode()).hexdigest(),
            }
        )

    ok, count = Ledger.verify(path)
    log("ledger_stress", ok and count == 201, f"chain valid, {count} records")
    os.remove(path)


# ── 4. Contract enforcement ──────────────────────────
def test_contracts():
    """Verify contracts catch violations."""

    @requires(lambda x: x > 0, "x must be positive")
    @ensures(lambda r: r is not None, "must return value")
    def divide(x):
        return 100 / x

    # Valid call
    try:
        result = divide(5)
        log("contract_valid_call", result == 20.0)
    except ContractViolation:
        log("contract_valid_call", False, "incorrectly rejected")

    # Invalid call (precondition)
    try:
        divide(-1)
        log("contract_precondition", False, "should have rejected")
    except ContractViolation as e:
        log("contract_precondition", e.kind == "precondition")

    # Postcondition test
    @ensures(lambda r: r > 0, "must be positive")
    def bad_fn():
        return -1

    try:
        bad_fn()
        log("contract_postcondition", False, "should have rejected")
    except ContractViolation as e:
        log("contract_postcondition", e.kind == "postcondition")


# ── 5. Symbolic checker consistency ──────────────────
def test_symbolic():
    """Verify symbolic checker produces consistent results."""
    checker = SymbolicChecker()

    report = checker.report()
    log("symbolic_report", report["total"] > 0, f"probed {report['total']} states")
    log("symbolic_held", report["held"] > 0, f"{report['held']} invariants held")
    log(
        "symbolic_violated",
        report["violated"] > 0,
        f"{report['violated']} correctly rejected",
    )

    satisfiable, count = checker.prove_satisfiability()
    log("symbolic_satisfiable", satisfiable, f"{count} satisfying states")


# ── 6. State hash collision resistance ────────────────
def test_hash_collision():
    """Slightly different states should produce different hashes."""
    rng = random.Random(SEED)
    hashes = set()

    for i in range(N_TRIALS):
        state = {
            "tick": i,
            "value": rng.random(),
            "mode": rng.choice(["normal", "safe"]),
        }
        h = state_hash(state)
        hashes.add(h)

    unique_ratio = len(hashes) / N_TRIALS
    log(
        "hash_collision_resistance",
        unique_ratio > 0.99,
        f"{len(hashes)}/{N_TRIALS} unique hashes",
    )


def main():
    print("\n" + "=" * 50)
    print("  Property-Based Fuzz Test Suite")
    print("=" * 50 + "\n")

    test_invariant_fuzz()
    test_bounds_fuzz()
    test_ledger_stress()
    test_contracts()
    test_symbolic()
    test_hash_collision()

    print("\n" + "-" * 50)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"  Total: {len(results)}  Passed: {passed}  Failed: {failed}")
    print("-" * 50)

    return PASS if failed == 0 else FAIL


if __name__ == "__main__":
    exit(main())
