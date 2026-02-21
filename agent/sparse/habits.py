class Habits:
    def __init__(self):
        self.table = {}

    def record(self, key, success):
        s, f = self.table.get(key, (0,0))
        self.table[key] = (s + int(success), f + int(not success))

    def score(self, key):
        s, f = self.table.get(key, (0,0))
        return s / max(1, s+f)

    def best_action(self, candidates):
        if not candidates: return None
        best = max(candidates, key=lambda c: self.score(c))
        return best if self.score(best) > 0.6 else None
