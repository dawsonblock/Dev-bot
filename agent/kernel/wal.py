import json
import os
import threading


class WAL:
    """A simple persistent Write-Ahead Log for Raft state and log entries."""

    def __init__(self, filepath):
        self.filepath = filepath
        self._lock = threading.Lock()
        self.term = 0
        self.voted_for = None
        self.entries = []

        self.recover()

    def recover(self):
        """Read the WAL to recover state and log."""
        if not os.path.exists(self.filepath):
            return

        try:
            with open(self.filepath, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                        if "term" in record:
                            self.term = record["term"]
                        if "voted_for" in record:
                            self.voted_for = record["voted_for"]
                        if "log_truncate" in record:
                            idx = record["log_truncate"]
                            self.entries = self.entries[:idx]
                        if "log_entries" in record:
                            self.entries.extend(record["log_entries"])
                    except json.JSONDecodeError:
                        # Corrupt tail, ignore
                        break
        except Exception as e:
            print(f"WAL recover error: {e}")

    def save(self, term=None, voted_for=None, append_entries=None, truncate_idx=None):
        """Append to WAL and fsync."""
        with self._lock:
            record = {}
            if term is not None:
                self.term = term
                record["term"] = self.term
            if voted_for is not None:
                self.voted_for = voted_for
                record["voted_for"] = self.voted_for
            if truncate_idx is not None:
                self.entries = self.entries[:truncate_idx]
                record["log_truncate"] = truncate_idx
            if append_entries:
                self.entries.extend(append_entries)
                record["log_entries"] = append_entries

            if not record:
                # If both are None, we still want to write the current state if called
                record = {"term": self.term, "voted_for": self.voted_for}

            # Use append mode. In a real db we'd compact this log.
            with open(self.filepath, "a") as f:
                f.write(json.dumps(record) + "\n")
                f.flush()
                os.fsync(f.fileno())
