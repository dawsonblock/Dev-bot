import copy

class Rollback:
    def __init__(self, max_depth=10):
        self.snapshots = []
        self.max_depth = max_depth

    def snapshot(self, state):
        self.snapshots.append(copy.deepcopy(state))
        if len(self.snapshots) > self.max_depth:
            self.snapshots.pop(0)

    def restore(self):
        return self.snapshots.pop() if self.snapshots else None
