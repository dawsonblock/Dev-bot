import time

class EventLoop:
    def __init__(self, tick_s, step_fn):
        self.tick = tick_s
        self.step = step_fn
        self.running = True

    def run(self):
        while self.running:
            t0 = time.time()
            self.step(t0)
            dt = time.time() - t0
            time.sleep(max(0, self.tick - dt))
