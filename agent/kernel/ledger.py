import hashlib, json, time, os

class Ledger:
    def __init__(self, path):
        self.path = path
        self.prev = "0"*64
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "r") as f:
                lines = f.readlines()
                if lines:
                    self.prev = json.loads(lines[-1])["hash"]

    def append(self, record):
        record["ts"] = int(time.time() * 1000)
        blob = json.dumps(record, sort_keys=True).encode()
        h = hashlib.sha256(self.prev.encode() + blob).hexdigest()
        with open(self.path, "a") as f:
            f.write(json.dumps({"hash": h, "prev": self.prev, "rec": record})+"\n")
        self.prev = h

    @classmethod
    def verify(cls, path):
        if not os.path.exists(path): return True, 0
        prev = "0"*64
        count = 0
        with open(path, "r") as f:
            for line in f:
                if not line.strip(): continue
                row = json.loads(line)
                blob = json.dumps(row["rec"], sort_keys=True).encode()
                h = hashlib.sha256(prev.encode() + blob).hexdigest()
                if h != row["hash"]: return False, count
                prev = h
                count += 1
        return True, count
