"""Tick-based token + call budget with per-action resource ceilings."""

from .clocks import Clocks


class Budgets:
    def __init__(self, token_per_min, tool_calls_per_min, refill_ticks=120):
        self.max_tokens = token_per_min
        self.max_calls = tool_calls_per_min
        self.tokens = token_per_min
        self.calls = tool_calls_per_min
        self.refill_every = refill_ticks  # refill after N ticks
        self.last_refill_tick = 0

    def _refill(self, tick):
        """Refill budgets every N ticks (deterministic, not time-based)."""
        if tick - self.last_refill_tick >= self.refill_every:
            self.calls = self.max_calls
            self.tokens = self.max_tokens
            self.last_refill_tick = tick

    def use_call(self, tick=0):
        """Attempt to use one call from the budget.

        Args:
            tick: current logical tick for deterministic refill

        Returns:
            True if call was allowed, False if budget exhausted.
        """
        self._refill(tick)
        if self.calls <= 0:
            return False
        self.calls -= 1
        return True

    def use_tokens(self, n, tick=0):
        """Attempt to use N tokens from the budget."""
        self._refill(tick)
        if self.tokens < n:
            return False
        self.tokens -= n
        return True

    def allow(self, action, tick=0):
        """Check if an action is within budget (alias for use_call)."""
        return self.use_call(tick)

    def summary(self):
        return {
            "calls_remaining": self.calls,
            "tokens_remaining": self.tokens,
            "max_calls": self.max_calls,
            "max_tokens": self.max_tokens,
        }
