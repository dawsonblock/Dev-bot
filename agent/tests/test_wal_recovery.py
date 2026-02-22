import pytest
from kernel.consensus import ConsensusEngine
from kernel.wal import WAL


@pytest.fixture
def temp_wal_path(tmp_path):
    return str(tmp_path / "test_raft.wal")


def test_wal_recovery_basic(temp_wal_path):
    """Test that a node can crash and recover its exact state from WAL."""

    # 1. Initialize first node (Node A)
    wal_a = WAL(temp_wal_path)
    node_a = ConsensusEngine("node-1", peers={"node-2": "mock"}, wal=wal_a)

    # Simulate some Raft state changes
    node_a.start_election()  # Promotes term to 1, votes for self
    assert node_a.current_term == 1
    assert node_a.voted_for == "node-1"

    # Propose an action (adds to log)
    node_a.propose({"tool": "ping", "args": {}}, tick=5)

    # Receive a higher term heartbeat (demotes to follower)
    node_a.append_entries(
        "node-2",
        term=2,
        prev_log_index=-1,
        prev_log_term=0,
        entries=[],
        leader_commit=0,
    )
    assert node_a.current_term == 2
    assert node_a.state == "follower"

    # Vote for someone else
    term, granted = node_a.request_vote(
        "node-3", term=3, last_log_index=0, last_log_term=1
    )
    assert node_a.current_term == 3
    assert node_a.voted_for == "node-3"
    assert granted is True

    # 2. Simulate Crash (Destroy Node A)
    del node_a
    del wal_a

    # 3. Recover Node (Node B reading same WAL)
    wal_b = WAL(temp_wal_path)
    node_b = ConsensusEngine("node-1", peers={"node-2": "mock"}, wal=wal_b)

    # 4. Assert State Fidelity
    assert node_b.current_term == 3
    assert node_b.voted_for == "node-3"
    assert len(node_b.log) == 1
    assert node_b.log[0].term == 1
    assert node_b.log[0].action["tool"] == "ping"
    assert node_b.log[0].tick == 5
    assert node_b.log[0].proposer == "node-1"


def test_wal_log_truncation(temp_wal_path):
    """Test that log truncations (simulating diverging logs) are persisted safely."""

    wal_a = WAL(temp_wal_path)
    node_a = ConsensusEngine("node-1", peers={"node-2": "mock"}, wal=wal_a)

    # Node A is leader in term 1
    node_a.current_term = 1
    node_a.voted_for = "node-1"
    node_a.state = "leader"
    wal_a.save(term=1, voted_for="node-1")

    # Propose two actions
    node_a.propose({"tool": "action1"}, tick=1)
    node_a.propose({"tool": "action2"}, tick=2)

    # Node B (term 2) sends an AppendEntries that conflicts at index 1
    conflicting_entries = [
        {
            "term": 2,
            "tick": 3,
            "action": {"tool": "override2"},
            "proposer": "node-2",
            "committed": False,
        }
    ]
    node_a.append_entries(
        "node-2",
        term=2,
        prev_log_index=0,
        prev_log_term=1,
        entries=conflicting_entries,
        leader_commit=0,
    )

    # Log should now be length 2: (action1, override2)
    assert len(node_a.log) == 2
    assert node_a.log[1].action["tool"] == "override2"

    # Simulate Crash
    del node_a
    del wal_a

    # Recover
    wal_b = WAL(temp_wal_path)
    node_b = ConsensusEngine("node-1", peers={"node-2": "mock"}, wal=wal_b)

    # Assert Truncation Fidelity
    assert len(node_b.log) == 2
    assert node_b.log[0].action["tool"] == "action1"
    assert node_b.log[1].action["tool"] == "override2"
    assert node_b.log[1].term == 2
