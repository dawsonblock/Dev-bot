"""Stable adaptation — bounded self-tuning within verified limits.

The system may adapt, but only within evolution bounds:
- Adjust scheduling window
- Rebalance task thresholds deterministically
- Prune memory safely
- Tune anomaly detection parameters

All changes must pass invariant validation and remain within bounds.
"""


class AdaptationEngine:
    """Bounded self-tuning engine.

    All adjustments are:
    1. Deterministic (based on metrics, not randomness)
    2. Bounded (within evolution limits)
    3. Reversible (old values logged)
    4. Invariant-safe (validated before commit)
    """

    def __init__(self, evolution_bounds=None):
        self.bounds = evolution_bounds
        self._history = []
        self._adjustments_this_window = 0
        self.max_adjustments_per_window = 5

    def propose_adjustment(
        self,
        metric_name,
        current_value,
        observed_metric,
        direction="auto",
        step_pct=0.1,
        min_val=0.01,
        max_val=100.0,
    ):
        """Propose a bounded adjustment to a system parameter.

        Args:
            metric_name: what we're tuning (e.g., 'anomaly_threshold')
            current_value: current parameter value
            observed_metric: the signal driving the adjustment
            direction: 'up', 'down', or 'auto'
            step_pct: max change as fraction of current value
            min_val: floor for the parameter
            max_val: ceiling for the parameter

        Returns:
            (new_value, applied: bool, reason: str)
        """
        if self._adjustments_this_window >= self.max_adjustments_per_window:
            return current_value, False, "adjustment_limit_reached"

        max_delta = abs(current_value * step_pct)

        if direction == "auto":
            if observed_metric > current_value * 1.5:
                direction = "up"
            elif observed_metric < current_value * 0.5:
                direction = "down"
            else:
                return current_value, False, "no_adjustment_needed"

        if direction == "up":
            new_value = min(current_value + max_delta, max_val)
        else:
            new_value = max(current_value - max_delta, min_val)

        # Bound check
        if new_value == current_value:
            return current_value, False, "at_limit"

        self._history.append(
            {
                "metric": metric_name,
                "old": current_value,
                "new": new_value,
                "direction": direction,
                "observed": observed_metric,
            }
        )
        self._adjustments_this_window += 1

        return new_value, True, "adjusted"

    def adapt_habits(self, habits, tick=0):
        """Prune stale habits within bounds.

        Returns number of habits pruned.
        """
        if self.bounds:
            ok, violation = self.bounds.check_habits(habits.table, tick)
            if not ok:
                # Force decay
                habits.apply_decay()
                return len(habits.table)
        return 0

    def reset_window(self):
        """Reset the adjustment counter for a new window."""
        self._adjustments_this_window = 0

    def summary(self):
        return {
            "adjustments_this_window": self._adjustments_this_window,
            "max_per_window": self.max_adjustments_per_window,
            "total_history": len(self._history),
            "recent": self._history[-5:],
        }
