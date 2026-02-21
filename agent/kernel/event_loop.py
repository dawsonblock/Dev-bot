"""Tick-driven event loop — deterministic, no wall-clock steering."""

import time
from .determinism import next_tick


class EventLoop:
    def __init__(self, tick_s, step_fn):
        self.tick_interval = tick_s
        self.step = step_fn
        self.running = True

    def run(self):
        """Main loop: advance logical tick, call step, sleep remainder."""
        while self.running:
            t0 = time.time()
            tick = next_tick()
            self.step(tick)
            dt = time.time() - t0
            time.sleep(max(0, self.tick_interval - dt))
