"""Failure taxonomy and deterministic escalation ladder.

Classifies failures and triggers safe mode after threshold violations.
"""

FAILURE_TYPES = {
    "policy_violation",
    "budget_exceeded",
    "tool_failure",
    "ci_failure",
    "replay_mismatch",
    "state_corruption",
    "invariant_violation",
    "learning_conflict",
    "consensus_failure",
    "resource_exhaustion",
}


class Escalation:
    """Deterministic escalation ladder.

    Tracks failure counts and triggers mode transitions.
    """

    def __init__(
        self,
        policy_threshold=3,
        invariant_threshold=1,
        tool_failure_threshold=5,
        ci_failure_threshold=3,
    ):
        self.thresholds = {
            "policy_violation": policy_threshold,
            "invariant_violation": invariant_threshold,
            "tool_failure": tool_failure_threshold,
            "ci_failure": ci_failure_threshold,
        }
        self.counts = {t: 0 for t in FAILURE_TYPES}
        self.mode = "normal"

    def record(self, failure_type):
        """Record a failure and check if escalation is needed.

        Returns:
            (new_mode, triggered) tuple
        """
        if failure_type not in FAILURE_TYPES:
            return self.mode, False

        self.counts[failure_type] = self.counts.get(failure_type, 0) + 1

        # Immediate abort conditions
        if failure_type == "invariant_violation":
            self.mode = "safe"
            return self.mode, True

        if failure_type == "state_corruption":
            self.mode = "safe"
            return self.mode, True

        # Threshold-based escalation
        threshold = self.thresholds.get(failure_type)
        if threshold and self.counts[failure_type] >= threshold:
            self.mode = "safe"
            return self.mode, True

        return self.mode, False

    def reset(self):
        """Reset all failure counts and return to normal mode."""
        self.counts = {t: 0 for t in FAILURE_TYPES}
        self.mode = "normal"

    def in_safe_mode(self):
        return self.mode == "safe"

    def summary(self):
        return {
            "mode": self.mode,
            "counts": dict(self.counts),
        }
