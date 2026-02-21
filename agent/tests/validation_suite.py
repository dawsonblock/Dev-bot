"""Operational Validation Framework — repeatable Tier 8 tests.

Five core tests:
1. Invariant stress test
2. Replay determinism test
3. Bounded growth test
4. Failure recovery test
5. Reconstruction fidelity test
"""

import sys
import os

# Ensure agent/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kernel.determinism import init_determinism, get_tick, next_tick, config_hash
from kernel.statehash import state_hash
from kernel.invariants import default_invariants, InvariantViolation
from kernel.evolution_bounds import EvolutionBounds
from kernel.escalation import Escalation
from kernel.ledger import Ledger
from kernel.verifier import verify_ledger


PASS = 0
FAIL = 1
results = []


def log(name, passed, detail=""):
    tag = "PASS" if passed else "FAIL"
    results.append((name, passed))
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))


# ── 1. Invariant Stress Test ──────────────────────────
def test_invariants():
    """Validate invariants reject bad states and accept good states."""
    inv = default_invariants()

    # Good state
    good = {"incident_count": 0, "mode": "normal"}
    try:
        inv.validate(good)
        log("invariant_accept_good", True)
    except InvariantViolation:
        log("invariant_accept_good", False, "incorrectly rejected good state")

    # Bad state: negative incidents
    bad1 = {"incident_count": -5, "mode": "normal"}
    try:
        inv.validate(bad1)
        log("invariant_reject_negative", False, "should have rejected")
    except InvariantViolation:
        log("invariant_reject_negative", True)

    # Bad state: invalid mode
    bad2 = {"incident_count": 0, "mode": "chaos"}
    try:
        inv.validate(bad2)
        log("invariant_reject_bad_mode", False, "should have rejected")
    except InvariantViolation:
        log("invariant_reject_bad_mode", True)

    # Bad state: too many keys
    bad3 = {f"key_{i}": i for i in range(150)}
    try:
        inv.validate(bad3)
        log("invariant_reject_overflow", False, "should have rejected")
    except InvariantViolation:
        log("invariant_reject_overflow", True)


# ── 2. Replay Determinism Test ────────────────────────
def test_determinism():
    """Two runs with same seed produce identical state hash sequence."""
    hashes_a = []
    hashes_b = []

    for run_hashes in [hashes_a, hashes_b]:
        init_determinism(seed=42)
        state = {"ok": True, "mode": "normal", "incident_count": 0}
        for _ in range(20):
            next_tick()
            state["_tick"] = get_tick()
            run_hashes.append(state_hash(state))

    if hashes_a == hashes_b:
        log("replay_determinism", True, f"{len(hashes_a)} hashes identical")
    else:
        mismatches = sum(a != b for a, b in zip(hashes_a, hashes_b))
        log("replay_determinism", False, f"{mismatches} mismatches")


# ── 3. Bounded Growth Test ────────────────────────────
def test_bounded_growth():
    """Evolution bounds reject excessive growth."""
    bounds = EvolutionBounds(
        max_episodes_per_window=10,
        max_vectors_per_window=20,
        max_habits=5,
        window_ticks=100,
    )

    # Normal growth
    for i in range(10):
        ok = bounds.record("episodes", 1, tick=i)
    log("bounds_accept_normal", ok, "10 episodes within limit of 10")

    # Excessive growth
    ok = bounds.record("episodes", 1, tick=11)
    log("bounds_reject_overflow", not ok, "11th episode should be rejected")

    # State key check
    big_state = {f"k{i}": i for i in range(150)}
    ok, violations = bounds.check_state(big_state, tick=12)
    log("bounds_reject_big_state", not ok, f"{len(violations)} violations")


# ── 4. Failure Recovery Test ──────────────────────────
def test_failure_recovery():
    """Escalation triggers safe mode after threshold violations."""
    esc = Escalation(policy_threshold=2, tool_failure_threshold=3)

    # Below threshold
    mode, triggered = esc.record("tool_failure")
    log("escalation_below_threshold", not triggered)

    # At threshold
    esc.record("tool_failure")
    mode, triggered = esc.record("tool_failure")
    log("escalation_triggers_safe", triggered and mode == "safe")

    # Reset
    esc.reset()
    log("escalation_reset", not esc.in_safe_mode())

    # Immediate escalation for invariant violation
    mode, triggered = esc.record("invariant_violation")
    log("escalation_immediate_invariant", triggered and mode == "safe")


# ── 5. Reconstruction Fidelity Test ──────────────────
def test_reconstruction():
    """Config hash is deterministic across calls."""
    cfg1 = {"a": 1, "b": {"c": 2}}
    cfg2 = {"a": 1, "b": {"c": 2}}
    h1 = config_hash(cfg1)
    h2 = config_hash(cfg2)
    log("config_hash_deterministic", h1 == h2)

    # State hash determinism
    state = {"ok": True, "mode": "normal", "count": 5}
    sh1 = state_hash(state)
    sh2 = state_hash(state)
    log("state_hash_deterministic", sh1 == sh2)


# ── 6. Ledger Verification ───────────────────────────
def test_ledger_verification():
    """Create a small ledger and verify it."""
    test_path = "/tmp/test_validation_ledger.jsonl"
    try:
        os.remove(test_path)
    except FileNotFoundError:
        pass

    ledger = Ledger(test_path)
    ledger.write_genesis(seed=42, config_hash="abc", code_hash="def")
    ledger.append({"event": "test", "tick": 1, "data": "hello"})
    ledger.append({"event": "test", "tick": 2, "data": "world"})

    ok, count = Ledger.verify(test_path)
    log("ledger_chain_verify", ok and count == 3, f"{count} records")

    report = verify_ledger(test_path, check_signatures=False)
    log("verifier_report", report.passed, f"{report.total} records checked")

    os.remove(test_path)


def main():
    print("\n" + "=" * 50)
    print("  Tier 8 Operational Validation Suite")
    print("=" * 50 + "\n")

    test_invariants()
    test_determinism()
    test_bounded_growth()
    test_failure_recovery()
    test_reconstruction()
    test_ledger_verification()

    print("\n" + "-" * 50)
    passed = sum(1 for _, ok in results if ok)
    failed = sum(1 for _, ok in results if not ok)
    print(f"  Total: {len(results)}  Passed: {passed}  Failed: {failed}")
    print("-" * 50)

    return PASS if failed == 0 else FAIL


if __name__ == "__main__":
    exit(main())
