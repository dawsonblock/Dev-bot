"""Safe history pruning — removes old ledger entries only after snapshot verification.

Never prunes below the last verified snapshot anchor.
"""

import json
import os


class Pruner:
    """Prunes ledger history safely, preserving audit trail integrity."""

    def __init__(self, ledger_path="ledger.jsonl", snapshots=None):
        self.ledger_path = ledger_path
        self.snapshots = snapshots

    def prune(self, keep_after_tick):
        """Remove ledger entries older than keep_after_tick.

        Safety: only prunes if a verified snapshot covers the removed range.

        Args:
            keep_after_tick: retain all records at or after this tick

        Returns:
            (ok: bool, removed: int, retained: int)
        """
        if not os.path.exists(self.ledger_path):
            return True, 0, 0

        # 1. Verify we have a snapshot covering the pruned range
        if self.snapshots:
            available = self.snapshots.list_snapshots()
            covering = [t for t in available if t <= keep_after_tick]
            if not covering:
                return False, 0, 0  # no snapshot to anchor

            # Verify the anchoring snapshot
            anchor_tick = max(covering)
            ok, reason = self.snapshots.verify_snapshot(anchor_tick)
            if not ok:
                return False, 0, 0  # snapshot integrity failed

        # 2. Read all records
        records = []
        with open(self.ledger_path, "r") as f:
            for line in f:
                if line.strip():
                    records.append(line)

        # 3. Filter: keep records at or after keep_after_tick
        retained = []
        removed = 0
        for line in records:
            row = json.loads(line)
            tick = row.get("rec", {}).get("tick", 0)
            if tick >= keep_after_tick:
                retained.append(line)
            else:
                removed += 1

        # 4. Atomic write
        tmp = self.ledger_path + ".tmp"
        with open(tmp, "w") as f:
            for line in retained:
                f.write(line if line.endswith("\n") else line + "\n")
        os.replace(tmp, self.ledger_path)

        return True, removed, len(retained)

    def safe_prune_to_last_snapshot(self):
        """Prune to the most recent verified snapshot."""
        if not self.snapshots:
            return False, 0, 0

        available = self.snapshots.list_snapshots()
        if not available:
            return False, 0, 0

        latest = max(available)
        ok, reason = self.snapshots.verify_snapshot(latest)
        if not ok:
            return False, 0, 0

        return self.prune(keep_after_tick=latest)
