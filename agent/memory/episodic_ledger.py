class Episodic:
    def __init__(self):
        self.rows = []

    def add(self, rec):
        self.rows.append(rec)

    def last(self, n=10):
        return self.rows[-n:]

    def to_strings(self, n=10):
        return "\n".join([str(r) for r in self.last(n)])
