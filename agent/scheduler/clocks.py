"""Tick-based three-tier due-time tracker."""


class Clocks:
    def __init__(self, fast_s, medium_s, slow_s, tick_s=0.5):
        self.tick_s = tick_s
        self.fast_every = max(1, int(fast_s / tick_s))
        self.medium_every = max(1, int(medium_s / tick_s))
        self.slow_every = max(1, int(slow_s / tick_s))

    def due_fast(self, tick):
        return tick % self.fast_every == 0

    def due_medium(self, tick):
        return tick % self.medium_every == 0

    def due_slow(self, tick):
        return tick % self.slow_every == 0
