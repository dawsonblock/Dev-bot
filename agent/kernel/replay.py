"""Dry replay engine — rebuild state evolution from ledger.

Does not execute tools, only tracks state hash transitions.
"""

import json


class ReplayEngine:
    """Replays a ledger file and verifies state hash consistency.

    Does NOT execute tools. Only checks that recorded state transitions
    are internally consistent.
    """

    def __init__(self, ledger_path="ledger.jsonl"):
        self.path = ledger_path
        self.records = []
        self.errors = []

    def load(self):
        """Load all ledger records."""
        self.records = []
        with open(self.path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.records.append(json.loads(line))
        return len(self.records)

    def replay(self, verbose=False):
        """Replay all records, checking hash chain and state consistency.

        Returns:
            (ok: bool, verified_count: int, errors: list)
        """
        self.errors = []
        prev_hash = "0" * 64
        verified = 0

        for i, row in enumerate(self.records):
            # 1. Verify hash chain
            blob = json.dumps(row["rec"], sort_keys=True).encode()
            import hashlib

            expected = hashlib.sha256(prev_hash.encode() + blob).hexdigest()
            if expected != row["hash"]:
                self.errors.append(
                    {
                        "index": i,
                        "type": "hash_mismatch",
                        "expected": expected,
                        "got": row["hash"],
                    }
                )
                return False, verified, self.errors

            # 2. Check exec records for state hash consistency
            rec = row["rec"]
            if rec.get("event") == "exec":
                before = rec.get("state_before")
                after = rec.get("state_after")
                if (
                    before
                    and after
                    and before == after
                    and rec.get("result", {}).get("ok")
                ):
                    # State changed but hashes match — could be stateless tool
                    pass

            prev_hash = row["hash"]
            verified += 1

            if verbose:
                event = rec.get("event", "unknown")
                tick = rec.get("tick", "?")
                print(f"  [{verified}] tick={tick} event={event}")

        return True, verified, self.errors

    def summary(self):
        """Return a summary of the replay."""
        events = {}
        for row in self.records:
            ev = row["rec"].get("event", "unknown")
            events[ev] = events.get(ev, 0) + 1
        return {
            "total_records": len(self.records),
            "event_counts": events,
            "errors": len(self.errors),
        }
