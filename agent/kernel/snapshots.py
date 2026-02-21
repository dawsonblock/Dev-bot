"""Canonical snapshots — long-term integrity preservation.

Periodically produces snapshots containing:
- Full state dict
- Ledger height (record count at snapshot time)
- Invariant proof hash (hash of all invariant check results)
- Rolling integrity checksum

Snapshot hash is anchored in the ledger for tamper-evidence.
"""

import hashlib
import json
import time
from pathlib import Path

from .statehash import state_hash


class SnapshotManager:
    """Manages periodic canonical snapshots for long-term integrity."""

    def __init__(self, snapshot_dir="snapshots", interval_ticks=500):
        self.dir = Path(snapshot_dir)
        self.dir.mkdir(exist_ok=True)
        self.interval = interval_ticks
        self.last_tick = 0
        self._rolling_hash = "0" * 64

    def due(self, tick):
        """Check if a snapshot is due at this tick."""
        return tick - self.last_tick >= self.interval

    def capture(self, state, ledger_height, invariant_proof, tick):
        """Produce a canonical snapshot and return its metadata.

        Args:
            state: current agent state dict
            ledger_height: number of ledger records
            invariant_proof: hash of invariant validation results
            tick: current logical tick

        Returns:
            dict with snapshot metadata including hash
        """
        snapshot = {
            "tick": tick,
            "wall_ts": int(time.time() * 1000),
            "state": state,
            "state_hash": state_hash(state),
            "ledger_height": ledger_height,
            "invariant_proof": invariant_proof,
            "rolling_integrity": self._rolling_hash,
        }

        # Canonical hash of the snapshot
        blob = json.dumps(snapshot, sort_keys=True, default=str).encode()
        snap_hash = hashlib.sha256(blob).hexdigest()
        snapshot["snapshot_hash"] = snap_hash

        # Update rolling integrity
        self._rolling_hash = hashlib.sha256(
            (self._rolling_hash + snap_hash).encode()
        ).hexdigest()

        # Write to disk
        filename = f"snap_{tick}.json"
        with open(self.dir / filename, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

        self.last_tick = tick

        # Return anchor record for the ledger
        return {
            "event": "snapshot_anchor",
            "tick": tick,
            "snapshot_hash": snap_hash,
            "ledger_height": ledger_height,
            "rolling_integrity": self._rolling_hash,
            "filename": filename,
        }

    def load(self, tick):
        """Load a snapshot by tick number."""
        path = self.dir / f"snap_{tick}.json"
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def list_snapshots(self):
        """List all available snapshot ticks."""
        snaps = []
        for p in sorted(self.dir.glob("snap_*.json")):
            name = p.stem  # snap_500
            try:
                tick = int(name.split("_")[1])
                snaps.append(tick)
            except (IndexError, ValueError):
                continue
        return snaps

    def verify_snapshot(self, tick):
        """Verify a snapshot's internal consistency."""
        snap = self.load(tick)
        if not snap:
            return False, "snapshot_not_found"

        stored_hash = snap.pop("snapshot_hash", None)
        blob = json.dumps(snap, sort_keys=True, default=str).encode()
        computed = hashlib.sha256(blob).hexdigest()

        if stored_hash != computed:
            return False, "hash_mismatch"

        return True, "ok"
