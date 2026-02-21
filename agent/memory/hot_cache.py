class HotCache:
    def __init__(self, k=64):
        self.k = k
        self.buf = []

    def put(self, item):
        self.buf.append(item)
        if len(self.buf) > self.k:
            self.buf.pop(0)

    def get_all(self):
        return list(self.buf)
