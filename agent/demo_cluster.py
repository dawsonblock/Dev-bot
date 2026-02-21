"""Dev-bot 3-node consensus cluster — multiprocessing edition.

Spawns 3 independent OS processes, each running a full Dev-bot node
with its own HTTP RPC server. The Raft consensus engine handles leader
election, log replication, and heartbeats across real TCP connections.

Usage:
    PYTHONPATH=agent python agent/demo_cluster.py
"""

import os
import sys
import time
import random
import signal
import multiprocessing

# Ensure the agent package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from kernel.consensus import ConsensusEngine
from kernel.node import Node
from kernel.distributed_ledger import DistributedLedger
from kernel.network_rpc import start_rpc_server, rpc_call


def run_node(node_id, port, peers):
    """Entry point for each OS-level node process."""
    node = Node(node_id=node_id, listen_addr=f"localhost:{port}")
    for p_id, p_addr in peers.items():
        node.register_peer(p_id, p_addr)

    ce = ConsensusEngine(node_id=node_id, peers=peers, rpc_client=rpc_call)
    dl = DistributedLedger(f"ledger_{node_id}.jsonl", ce)

    # Start HTTP RPC listener
    start_rpc_server(port, node, ce)
    print(f"[{node_id}] RPC server listening on port {port}")

    # Genesis
    dl.write_genesis(seed=42, config_hash="demo", code_hash="demo")

    tick = 1
    while True:
        time.sleep(1.0)

        # Raft heartbeat / election timeout check
        ce.heartbeat()

        # The elected leader proposes actions
        if ce.is_leader:
            if random.random() > 0.3:
                action = {
                    "tool": random.choice(["scan", "patch", "analyze", "test"]),
                    "target": f"file_{tick}.py",
                }
                committed, entry = dl.propose_and_append(action, tick)

                status = "COMMITTED" if committed else "FAILED"
                print(
                    f"[{node_id}] tick={tick} term={ce.current_term} "
                    f"action={action['tool']} status={status} "
                    f"ledger_height={dl.height()}"
                )

        tick += 1


def main():
    print("=" * 60)
    print("  Dev-bot Raft Consensus Cluster (multiprocessing)")
    print("  3 nodes on TCP ports 7001, 7002, 7003")
    print("=" * 60)

    nodes = {
        "alpha": 7001,
        "beta": 7002,
        "gamma": 7003,
    }

    processes = []
    for n_id, n_port in nodes.items():
        peers = {
            p_id: f"localhost:{p_port}"
            for p_id, p_port in nodes.items()
            if p_id != n_id
        }
        p = multiprocessing.Process(
            target=run_node,
            args=(n_id, n_port, peers),
            daemon=True,
        )
        p.start()
        processes.append(p)
        print(f"  Started process {p.pid} for node '{n_id}' on :{n_port}")

    print()
    print("Cluster is running. Press Ctrl+C to shut down.")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down cluster...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=2)
        print("All nodes stopped.")


if __name__ == "__main__":
    main()
