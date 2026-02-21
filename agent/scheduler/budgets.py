import time


class Budgets:
    def __init__(self, token_per_min, tool_calls_per_min):
        self.max_tokens = token_per_min
        self.max_calls = tool_calls_per_min
        self.tokens = token_per_min
        self.calls = tool_calls_per_min
        self.last_refill = time.time()

    def _refill(self):
        now = time.time()
        if now - self.last_refill >= 60.0:
            self.calls = self.max_calls
            self.tokens = self.max_tokens
            self.last_refill = now

    def use_call(self):
        self._refill()
        if self.calls <= 0:
            return False
        self.calls -= 1
        return True
