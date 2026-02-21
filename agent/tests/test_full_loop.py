import os
import shutil
import tempfile

from kernel.node import Node
from kernel.consensus import ConsensusEngine
from kernel.distributed_ledger import DistributedLedger
from run import build_agent, make_step


class MockState:
    def __init__(self):
        self.dashboard_state = type(
            "DS",
            (),
            {"update": lambda **kwargs: None, "add_event": lambda *a, **kw: None},
        )()


def test_full_agent_loop_e2e():
    """End-to-End Test: 15 ticks of full agent loop with bounded constraints."""

    # Setup clean room
    temp_dir = tempfile.mkdtemp()
    ledger_path = os.path.join(temp_dir, "test_ledger.jsonl")
    snapshots_dir = os.path.join(temp_dir, "snapshots")
    archive_dir = os.path.join(temp_dir, "archive")
    vector_dir = os.path.join(temp_dir, "vectors")

    try:
        # Build node and ledger
        _node = Node("test-node-1")
        engine = ConsensusEngine("test-node-1")
        ledger = DistributedLedger(ledger_path, engine)
        ledger.write_genesis(seed=42, config_hash="e2e-config", code_hash="e2e-code")

        agent = build_agent(
            llm_mode="stub",  # Use stub so we don't require API keys in CI
            ledger_path=ledger_path,
            snapshot_dir=snapshots_dir,
            archive_dir=archive_dir,
            vector_dir=vector_dir,
            _ledger_obj=ledger,
        )

        step_func = make_step(agent)

        step_func = make_step(agent)

        try:
            # Run 100 ticks (at 0.5s/tick, this spans 50 seconds of logical time)
            for tick in range(1, 101):
                # Engine tick
                engine.heartbeat()

                # Directly test the executor pipeline halfway through
                if tick == 50:
                    agent["executor"].execute_checked(
                        {
                            "tool": "noop",
                            "risk": 0,
                            "args": {},
                            "reasoning": "e2e_test",
                        },
                        agent["state"],
                    )

                # Agent step
                step_func(tick)
        except Exception as e:
            print(f"Exception during step: {e}")
            raise

        # Post-run assertions
        # 1. Ledger should have genesis + actions from the slow clock
        from kernel.ledger import Ledger

        records = Ledger.load_records(ledger_path)
        print("--- FULL LEDGER RECORDS ---")
        for r in records:
            print(r.get("rec"))
        print("---------------------------")

        assert (
            len(records) > 2
        ), f"Ledger should contain genesis and actions, found {len(records)}"

        # 2. Invariants should be intact
        last_state = records[-1].get("rec", {}).get("state_after")
        assert last_state is not None, "Final record should contain a state_after hash"

        # 3. Validation via verifier
        from kernel.verifier import verify_ledger

        report = verify_ledger(ledger_path, check_signatures=True)
        assert report.chain_ok, "Ledger hash chain broke"
        assert report.signatures_ok, "Signatures failed verification"
        assert report.invariants_ok, "Invariant flag violated in ledger"

        # 4. Reconstruction fidelity test
        from kernel.reconstruct import reconstruct_from_ledger

        hashes, genesis, final_hash = reconstruct_from_ledger(ledger_path)
        assert final_hash, "Reconstruction module failed to extract final hash"
        assert len(hashes) > 0, "Reconstruction module extracted zero state hashes"

        # If we reached 15 ticks without an exception bringing down the main process
        # and all tests pass, the E2E loop is entirely stable.

    finally:
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    test_full_agent_loop_e2e()
    print("E2E Test Passed: Full pipeline is stable.")
