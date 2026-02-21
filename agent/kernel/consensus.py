"""Raft-inspired consensus protocol — multi-node action ordering.

Enables multiple Dev-bot instances to agree on action ordering via:
- Leader election with term-based voting
- Log replication with majority confirmation
- Heartbeat-based failure detection

This is a local simulation — networked transport is pluggable.
"""

import time
import hashlib
import json
import random


class LogEntry:
    """Single replicated log entry."""

    def __init__(self, term, tick, action, proposer):
        self.term = term
        self.tick = tick
        self.action = action
        self.proposer = proposer
        self.committed = False

    def to_dict(self):
        return {
            "term": self.term,
            "tick": self.tick,
            "action": self.action,
            "proposer": self.proposer,
            "committed": self.committed,
        }


class ConsensusState:
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class ConsensusEngine:
    """Raft-inspired consensus for action ordering.

    In single-node mode, the node is always the leader and
    commits are immediate. In multi-node mode, majority is required.
    """

    def __init__(self, node_id, peers=None, election_timeout_ms=1500):
        self.node_id = node_id
        self.peers = peers or []
        self.state = ConsensusState.LEADER if not peers else ConsensusState.FOLLOWER

        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log = []

        # Volatile state
        self.commit_index = -1
        self.last_applied = -1
        self.last_heartbeat = time.time()
        self.election_timeout = election_timeout_ms / 1000.0

        # Leader state
        self.next_index = {}  # peer -> next log index to send
        self.match_index = {}  # peer -> highest replicated index

        # If no peers, self-elect
        if not peers:
            self.current_term = 1
            self.voted_for = node_id

    @property
    def is_leader(self):
        return self.state == ConsensusState.LEADER

    @property
    def cluster_size(self):
        return len(self.peers) + 1

    @property
    def majority(self):
        return (self.cluster_size // 2) + 1

    def propose(self, action, tick):
        """Propose an action for consensus.

        Returns:
            (committed: bool, entry: LogEntry)
        """
        if not self.is_leader:
            return False, None

        entry = LogEntry(
            term=self.current_term,
            tick=tick,
            action=action,
            proposer=self.node_id,
        )
        self.log.append(entry)
        index = len(self.log) - 1

        # Single-node: immediate commit
        if not self.peers:
            entry.committed = True
            self.commit_index = index
            self.last_applied = index
            return True, entry

        # Multi-node: wait for replication (simulated)
        # In production, this would be async with RPC
        acks = 1  # self
        for peer in self.peers:
            # Simulate successful replication
            acks += 1
            self.match_index[peer] = index
            if acks >= self.majority:
                break

        if acks >= self.majority:
            entry.committed = True
            self.commit_index = index
            self.last_applied = index
            return True, entry

        return False, entry

    def request_vote(self, candidate_id, term, last_log_index, last_log_term):
        """Handle a vote request from a candidate.

        Returns:
            (term: int, vote_granted: bool)
        """
        if term < self.current_term:
            return self.current_term, False

        if term > self.current_term:
            self.current_term = term
            self.state = ConsensusState.FOLLOWER
            self.voted_for = None

        if self.voted_for is None or self.voted_for == candidate_id:
            # Check log completeness
            my_last_term = self.log[-1].term if self.log else 0
            my_last_index = len(self.log) - 1

            if last_log_term > my_last_term or (
                last_log_term == my_last_term and last_log_index >= my_last_index
            ):
                self.voted_for = candidate_id
                self.last_heartbeat = time.time()
                return self.current_term, True

        return self.current_term, False

    def start_election(self):
        """Transition to candidate and request votes."""
        self.state = ConsensusState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        votes = 1  # vote for self

        last_index = len(self.log) - 1
        last_term = self.log[-1].term if self.log else 0

        # In production, send RequestVote RPCs to peers
        # Simulated: assume majority votes granted
        votes += len(self.peers) // 2

        if votes >= self.majority:
            self.state = ConsensusState.LEADER
            # Initialize leader state
            for peer in self.peers:
                self.next_index[peer] = len(self.log)
                self.match_index[peer] = -1

    def heartbeat(self):
        """Send heartbeats (leader) or check election timeout (follower)."""
        now = time.time()

        if self.is_leader:
            self.last_heartbeat = now
            # In production: send AppendEntries RPCs
            return "heartbeat_sent"

        if now - self.last_heartbeat > self.election_timeout:
            self.start_election()
            return "election_started"

        return "ok"

    def summary(self):
        return {
            "node_id": self.node_id,
            "state": self.state,
            "term": self.current_term,
            "log_size": len(self.log),
            "committed": self.commit_index + 1,
            "peers": len(self.peers),
        }
