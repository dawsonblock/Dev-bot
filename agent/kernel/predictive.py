"""Predictive failure model — forecasts risk from rolling metrics window."""


class FailurePredictor:
    """Tracks metrics over a rolling window and produces a risk score.

    When risk exceeds threshold, recommends pre-emptive safe mode.
    """

    def __init__(self, window=100, risk_threshold=0.7):
        self.window = window
        self.threshold = risk_threshold
        self.history = []

    def update(self, metrics):
        """Push a metrics snapshot into the rolling window.

        Expected keys: fail (bool/int), load (0-1 float), latency_ms (float)
        """
        self.history.append(metrics)
        if len(self.history) > self.window:
            self.history.pop(0)

    def risk_score(self):
        """Compute a 0-1 risk score from the rolling window."""
        if not self.history:
            return 0.0

        n = len(self.history)
        failures = sum(1 for m in self.history if m.get("fail"))
        avg_load = sum(m.get("load", 0) for m in self.history) / n
        avg_latency = sum(m.get("latency_ms", 0) for m in self.history) / n

        # Weighted risk: 50% failure rate, 30% load, 20% latency norm
        failure_rate = failures / n
        latency_norm = min(1.0, avg_latency / 5000.0)  # 5s = max

        score = failure_rate * 0.5 + avg_load * 0.3 + latency_norm * 0.2
        return round(min(1.0, score), 4)

    def should_safe_mode(self):
        """Returns True if risk exceeds threshold."""
        return self.risk_score() >= self.threshold

    def summary(self):
        return {
            "window_size": len(self.history),
            "risk_score": self.risk_score(),
            "threshold": self.threshold,
            "above_threshold": self.should_safe_mode(),
        }
