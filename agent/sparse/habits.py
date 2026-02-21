"""Confidence-bounded Bayesian habits — reflex only fires with evidence.

Uses a Beta posterior for success probability estimation.
Reflex fires only when trials ≥ threshold AND lower confidence bound ≥ minimum.
Includes time-based decay.
"""

import math
import time


class Habit:
    """Single habit entry with Beta posterior tracking."""

    def __init__(self):
        self.successes = 0
        self.failures = 0
        self.last_used = 0

    @property
    def trials(self):
        return self.successes + self.failures

    def update(self, ok):
        """Record a trial outcome."""
        if ok:
            self.successes += 1
        else:
            self.failures += 1
        self.last_used = time.time()

    def success_rate(self):
        if self.trials == 0:
            return 0.0
        return self.successes / self.trials

    def confidence_lower(self):
        """Wilson score lower confidence bound (approx 95%)."""
        if self.trials == 0:
            return 0.0
        p = self.success_rate()
        n = self.trials
        z = 1.96  # 95% CI
        denom = 1 + z * z / n
        center = p + z * z / (2 * n)
        spread = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
        return (center - spread) / denom

    def usable(self, min_trials=5, min_confidence=0.6):
        """Check if this habit has enough evidence to be used as reflex."""
        return self.trials >= min_trials and self.confidence_lower() >= min_confidence


class Habits:
    """Confidence-bounded habit table with decay.

    Replaces the original frequency-counter approach with a Bayesian model.
    """

    def __init__(self, min_trials=5, min_confidence=0.6, decay_hours=24):
        self.table = {}
        self.min_trials = min_trials
        self.min_confidence = min_confidence
        self.decay_seconds = decay_hours * 3600

    def record(self, key, success):
        """Record a trial outcome for a tool."""
        if key not in self.table:
            self.table[key] = Habit()
        self.table[key].update(success)

    def score(self, key):
        """Get the success rate for a tool."""
        habit = self.table.get(key)
        if not habit:
            return 0.0
        return habit.success_rate()

    def confidence(self, key):
        """Get the lower confidence bound for a tool."""
        habit = self.table.get(key)
        if not habit:
            return 0.0
        return habit.confidence_lower()

    def best_action(self, candidates):
        """Find the best reflex candidate with sufficient confidence.

        Returns None if no candidate meets the evidence threshold.
        """
        if not candidates:
            return None

        usable = []
        for c in candidates:
            habit = self.table.get(c)
            if habit and habit.usable(self.min_trials, self.min_confidence):
                usable.append((habit.confidence_lower(), c))

        if not usable:
            return None

        usable.sort(reverse=True)
        return usable[0][1]

    def apply_decay(self):
        """Remove habits that haven't been used within the decay window."""
        now = time.time()
        stale = [
            key
            for key, habit in self.table.items()
            if habit.last_used > 0 and now - habit.last_used > self.decay_seconds
        ]
        for key in stale:
            del self.table[key]

    def summary(self):
        """Return a dict summarizing all habits."""
        return {
            key: {
                "trials": h.trials,
                "success_rate": round(h.success_rate(), 3),
                "confidence": round(h.confidence_lower(), 3),
                "usable": h.usable(self.min_trials, self.min_confidence),
            }
            for key, h in self.table.items()
        }
