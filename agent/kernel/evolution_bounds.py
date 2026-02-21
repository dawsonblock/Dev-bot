"""Bounded evolution — prevents silent behavioral drift.

Enforces maximum change per interval for:
- Memory growth (episodic rows, vector entries, hot cache)
- Learning rate (habit table size, confidence deltas)
- Resource usage (tool calls, token consumption)
- Architecture (no unverified self-modification)
"""


class BoundViolation(Exception):
    """Raised when an evolution bound is exceeded."""

    pass


class EvolutionBounds:
    """Tracks and enforces growth constraints per measurement window."""

    def __init__(
        self,
        max_episodes_per_window=200,
        max_vectors_per_window=500,
        max_habits=50,
        max_state_keys=100,
        max_tool_calls_per_window=300,
        window_ticks=1000,
    ):
        self.limits = {
            "episodes": max_episodes_per_window,
            "vectors": max_vectors_per_window,
            "habits": max_habits,
            "state_keys": max_state_keys,
            "tool_calls": max_tool_calls_per_window,
        }
        self.window_ticks = window_ticks
        self._counters = {k: 0 for k in self.limits}
        self._last_reset_tick = 0
        self._violations = []

    def _reset_window(self, tick):
        """Reset window counters if window has elapsed."""
        if tick - self._last_reset_tick >= self.window_ticks:
            self._counters = {k: 0 for k in self.limits}
            self._last_reset_tick = tick

    def record(self, metric, amount=1, tick=0):
        """Record growth in a metric. Returns True if within bounds."""
        self._reset_window(tick)
        if metric not in self._counters:
            return True

        self._counters[metric] += amount
        if self._counters[metric] > self.limits[metric]:
            violation = {
                "metric": metric,
                "count": self._counters[metric],
                "limit": self.limits[metric],
                "tick": tick,
            }
            self._violations.append(violation)
            return False
        return True

    def check_state(self, state, tick=0):
        """Check that current state is within structural bounds."""
        self._reset_window(tick)
        violations = []

        if len(state) > self.limits["state_keys"]:
            violations.append(
                {
                    "metric": "state_keys",
                    "count": len(state),
                    "limit": self.limits["state_keys"],
                }
            )

        return len(violations) == 0, violations

    def check_habits(self, habits_table, tick=0):
        """Check that habit table hasn't grown unbounded."""
        self._reset_window(tick)
        size = len(habits_table)
        if size > self.limits["habits"]:
            return False, {
                "metric": "habits",
                "count": size,
                "limit": self.limits["habits"],
            }
        return True, None

    def summary(self):
        return {
            "counters": dict(self._counters),
            "limits": dict(self.limits),
            "violations": len(self._violations),
            "recent_violations": self._violations[-5:],
        }
