"""Execution graph validator — enforces phase transition ordering.

SENSE → ANALYZE → PLAN → GATE → EXECUTE → LEARN → LOG → SENSE
No skipping allowed.
"""


class ExecutionGraphViolation(Exception):
    pass


class ExecutionGraph:
    """Enforces allowed phase transitions in the agent loop."""

    PHASES = ["sense", "analyze", "plan", "gate", "execute", "learn", "log"]

    ALLOWED = {
        "sense": ["analyze"],
        "analyze": ["plan", "sense"],  # can skip plan if no anomaly
        "plan": ["gate"],
        "gate": ["execute", "sense"],  # rejected actions skip execute
        "execute": ["learn"],
        "learn": ["log"],
        "log": ["sense"],
    }

    def __init__(self):
        self.current = "log"  # start ready for sense

    def transition(self, phase):
        """Advance to the next phase. Raises if transition is invalid."""
        if phase not in self.PHASES:
            raise ExecutionGraphViolation(f"Unknown phase '{phase}'")
        allowed = self.ALLOWED.get(self.current, [])
        if phase not in allowed:
            raise ExecutionGraphViolation(
                f"Invalid transition: {self.current} → {phase} " f"(allowed: {allowed})"
            )
        self.current = phase
        return True

    def reset(self):
        """Reset to initial state (ready for sense)."""
        self.current = "log"
