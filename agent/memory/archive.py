import json, gzip, time, os

class Archive:
    def __init__(self, path):
        self.path = path
        os.makedirs(path, exist_ok=True)

    def dump(self, obj, label="snapshot"):
        fn = os.path.join(self.path, f"snap_{label}_{int(time.time())}.json.gz")
        with gzip.open(fn, "wt") as f:
            json.dump(obj, f)
