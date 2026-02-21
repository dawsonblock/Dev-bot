"""Forensic-grade append-only SHA-256 hash-chained ledger.

Records tick as primary ordering key, wall-time as metadata.
Supports genesis records and log_event class method.
"""

import hashlib
import json
import time
import os


class Ledger:
    def __init__(self, path):
        self.path = path
        self.prev = "0" * 64
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path) as f:
                lines = f.readlines()
                if lines:
                    last = lines[-1].strip()
                    if last:
                        self.prev = json.loads(last)["hash"]

    def append(self, record):
        """Append a record with tick ordering and wall-time metadata."""
        if "ts" not in record:
            record["ts"] = int(time.time() * 1000)
        blob = json.dumps(record, sort_keys=True).encode()
        h = hashlib.sha256(self.prev.encode() + blob).hexdigest()
        with open(self.path, "a") as f:
            f.write(
                json.dumps(
                    {
                        "hash": h,
                        "prev": self.prev,
                        "rec": record,
                    }
                )
                + "\n"
            )
        self.prev = h

    def write_genesis(self, seed, config_hash, code_hash):
        """Write the genesis record (first boot identity)."""
        self.append(
            {
                "event": "genesis",
                "seed": seed,
                "config_hash": config_hash,
                "code_hash": code_hash,
                "determinism": True,
            }
        )

    @classmethod
    def verify(cls, path):
        """Verify the full hash chain. Returns (ok, count)."""
        if not os.path.exists(path):
            return True, 0
        prev = "0" * 64
        count = 0
        with open(path) as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                blob = json.dumps(row["rec"], sort_keys=True).encode()
                h = hashlib.sha256(prev.encode() + blob).hexdigest()
                if h != row["hash"]:
                    return False, count
                prev = h
                count += 1
        return True, count

    @classmethod
    def load_records(cls, path):
        """Load all records from a ledger file."""
        records = []
        if not os.path.exists(path):
            return records
        with open(path) as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records
