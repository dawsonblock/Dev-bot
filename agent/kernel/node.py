"""Node identity — peer discovery, heartbeat, split-brain detection.

Each Dev-bot instance has a unique node identity with:
- Cryptographic node ID
- Peer registry with liveness tracking
- Split-brain detection via heartbeat monitoring
"""

import hashlib
import time
import os


class Node:
    """Dev-bot cluster node identity."""

    def __init__(self, node_id=None, listen_addr="localhost:7000"):
        self.node_id = node_id or self._generate_id()
        self.listen_addr = listen_addr
        self.created_at = time.time()
        self.peers = {}  # node_id -> PeerInfo
        self._heartbeat_interval = 1.0  # seconds
        self._timeout = 5.0  # peer timeout

    @staticmethod
    def _generate_id():
        """Generate a unique node ID from hostname + random + time."""
        raw = f"{os.getpid()}-{time.time_ns()}-{os.urandom(8).hex()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def register_peer(self, node_id, addr):
        """Add or update a peer in the registry."""
        self.peers[node_id] = {
            "addr": addr,
            "last_seen": time.time(),
            "alive": True,
        }

    def heartbeat_received(self, node_id):
        """Record that a peer sent a heartbeat."""
        if node_id in self.peers:
            self.peers[node_id]["last_seen"] = time.time()
            self.peers[node_id]["alive"] = True

    def check_peers(self):
        """Check peer liveness and detect potential split-brain.

        Returns:
            (alive_peers: list, dead_peers: list, split_brain: bool)
        """
        now = time.time()
        alive = []
        dead = []

        for pid, info in self.peers.items():
            if now - info["last_seen"] > self._timeout:
                info["alive"] = False
                dead.append(pid)
            else:
                alive.append(pid)

        # Split-brain: if we see fewer than majority of expected peers
        total = len(self.peers) + 1  # include self
        majority = (total // 2) + 1
        split_brain = len(alive) + 1 < majority  # +1 for self

        return alive, dead, split_brain

    def summary(self):
        alive, dead, split = self.check_peers()
        return {
            "node_id": self.node_id,
            "addr": self.listen_addr,
            "peers": len(self.peers),
            "alive_peers": len(alive),
            "dead_peers": len(dead),
            "split_brain": split,
        }
