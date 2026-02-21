class Clocks:
    def __init__(self, fast_s, medium_s, slow_s):
        self.fast = fast_s
        self.medium = medium_s
        self.slow = slow_s
        self.last_fast = 0
        self.last_medium = 0
        self.last_slow = 0

    def due_fast(self, now):
        if now - self.last_fast >= self.fast:
            self.last_fast = now
            return True
        return False

    def due_medium(self, now):
        if now - self.last_medium >= self.medium:
            self.last_medium = now
            return True
        return False

    def due_slow(self, now):
        if now - self.last_slow >= self.slow:
            self.last_slow = now
            return True
        return False
