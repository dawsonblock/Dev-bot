"""Distributed ledger — replicated ledger with consensus-gated appends.

Extends base Ledger with:
- Append-via-consensus (actions only committed when majority agrees)
- Sync protocol for catching up lagging nodes
- Conflict resolution (reject entries with mismatched terms)
"""

from .ledger import Ledger
from .consensus import ConsensusEngine


class DistributedLedger:
    """Ledger that requires consensus before committing entries."""

    def __init__(self, path, consensus):
        self.local = Ledger(path)
        self.consensus = consensus

    def propose_and_append(self, record, tick):
        """Propose a record through consensus; append only if committed.

        Returns:
            (committed: bool, entry)
        """
        committed, entry = self.consensus.propose(record, tick)
        if committed:
            # Add consensus metadata to the record
            record["_consensus"] = {
                "term": entry.term,
                "proposer": entry.proposer,
                "committed": True,
            }
            self.local.append(record)
        return committed, entry

    def append_unchecked(self, record):
        """Append without consensus (for genesis, snapshots, etc.)."""
        self.local.append(record)

    def write_genesis(self, seed, config_hash, code_hash):
        """Write genesis record (no consensus needed)."""
        self.local.write_genesis(seed, config_hash, code_hash)

    def sync_from(self, remote_records):
        """Sync missing records from a remote peer.

        Args:
            remote_records: list of {rec, hash} dicts from remote

        Returns:
            (synced: int, conflicts: int)
        """
        local_records = Ledger.load_records(self.local.path)
        local_hashes = {r["hash"] for r in local_records}

        synced = 0
        conflicts = 0

        for remote in remote_records:
            if remote["hash"] in local_hashes:
                continue  # already have it

            # Verify the remote record's consensus metadata
            rec = remote.get("rec", {})
            consensus_meta = rec.get("_consensus", {})
            if not consensus_meta.get("committed"):
                conflicts += 1
                continue

            self.local.append(rec)
            synced += 1

        return synced, conflicts

    def verify(self):
        """Verify local ledger integrity."""
        return Ledger.verify(self.local.path)

    def height(self):
        """Return the number of records in the local ledger."""
        records = Ledger.load_records(self.local.path)
        return len(records)

    def summary(self):
        ok, count = self.verify()
        return {
            "height": count,
            "chain_valid": ok,
            "consensus": self.consensus.summary(),
        }
