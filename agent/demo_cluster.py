import time
import threading
import random
from kernel.consensus import ConsensusEngine
from kernel.node import Node
from kernel.distributed_ledger import DistributedLedger
from tools.dashboard import start_dashboard, DashboardState

def run_node(node_id, peers, dashboard_state, is_primary=False):
    node = Node(node_id=node_id)
    for p in peers:
        node.register_peer(p, f"{p}:7000")
        
    ce = ConsensusEngine(node_id=node_id, peers=peers)
    dl = DistributedLedger(f"ledger_{node_id}.jsonl", ce)
    
    # Genesis
    dl.write_genesis(seed=42, config_hash="demo", code_hash="demo")
    
    tick = 1
    while True:
        time.sleep(1.0)
        
        # Heartbeats
        for p in peers:
            node.heartbeat_received(p)
            
        ce.heartbeat()
        
        # Primary node proposes actions
        if is_primary and ce.is_leader:
            if random.random() > 0.3:
                action = {"tool": random.choice(["scan", "patch", "analyze", "test"]), "target": f"file_{tick}.py"}
                committed, entry = dl.propose_and_append(action, tick)
                
                if committed:
                    dashboard_state.update(
                        tick=tick,
                        ledger_height=dl.height(),
                        state_hash=f"hash_{tick}_{random.randint(1000,9999)}",
                        mode="consensus_active"
                    )
                    dashboard_state.add_event(f"Action committed: {action['tool']} on {action['target']}", tick=tick)
                else:
                    dashboard_state.add_event(f"Action failed consensus: {action['tool']}", tick=tick)
        
        tick += 1

if __name__ == "__main__":
    print("Starting 3-node Dev-bot consensus cluster simulation...")
    
    state = DashboardState()
    start_dashboard(state, port=8081)
    print("Dashboard streaming SSE on http://localhost:8081/events")
    
    nodes = ["alpha", "beta", "gamma"]
    
    # Start threads
    threads = []
    for i, n in enumerate(nodes):
        peers = [p for p in nodes if p != n]
        t = threading.Thread(target=run_node, args=(n, peers, state, i==0), daemon=True)
        t.start()
        threads.append(t)
        
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down cluster.")
