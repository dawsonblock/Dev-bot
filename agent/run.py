"""Dev-bot: Deterministic Autonomous DevOps Agent — Hardened Runner.

All tool execution flows through kernel/execute.py (non-bypassable).
State transitions are tick-driven and transactional.
Every decision is forensically logged to the hash-chained ledger.
"""

import argparse
import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent))

# ── Kernel imports ────────────────────────────────────
from kernel.determinism import init_determinism, config_hash
from kernel.event_loop import EventLoop
from kernel.gate import Gate
from kernel.ledger import Ledger
from kernel.watchdog import Watchdog
from kernel.rollback import Rollback
from kernel.execute import Executor
from kernel.policy_schema import validate_policy, validate_budgets
from kernel.integrity import full_integrity_hash
from kernel.invariants import default_invariants
from kernel.escalation import Escalation
from kernel.predictive import FailurePredictor
from kernel.evolution_bounds import EvolutionBounds
from kernel.snapshots import SnapshotManager
from kernel.adaptation import AdaptationEngine
from kernel.statehash import state_hash

# ── Subsystem imports ─────────────────────────────────
from sparse.anomaly import EWMA, anomalous
from sparse.habits import Habits

from dense.llm_iface import LLM
from dense.planner import Planner
from dense.patcher import Patcher

from memory.hot_cache import HotCache
from memory.vector_store import VectorStore
from memory.episodic_ledger import Episodic
from memory.archive import Archive
from memory.router import MemoryRouter

from tools.metrics import read as read_metrics
from tools.system_ops import TOOL_REGISTRY
from tools.telemetry import Telemetry

from scheduler.clocks import Clocks
from scheduler.budgets import Budgets

from kernel.sandbox import DockerSandbox
from tools.shell import set_sandbox as shell_set_sandbox
from tools.system_ops import set_sandbox as ops_set_sandbox

# ── Config ────────────────────────────────────────────
CONFIG_DIR = Path(__file__).parent / "config"
policy_cfg = yaml.safe_load((CONFIG_DIR / "policy.yaml").read_text())
budgets_cfg = yaml.safe_load((CONFIG_DIR / "budgets.yaml").read_text())


def build_agent(
    llm_mode="stub",
    ledger_path="ledger.jsonl",
    snapshot_dir="snapshots",
    archive_dir="archive",
    vector_dir="vectors",
    _ledger_obj=None,
):
    """Construct the full hardened agent."""

    # ── 0. Determinism ────────────────────────────────
    seed = budgets_cfg.get("seed", 1337)
    init_determinism(seed)

    # ── 1. Validate configs ───────────────────────────
    validate_policy(policy_cfg)
    validate_budgets(budgets_cfg)

    cfg_hash = config_hash(policy_cfg, budgets_cfg)
    code_hash = full_integrity_hash(
        str(Path(__file__).parent),
        str(CONFIG_DIR),
    )

    # ── 2. State ──────────────────────────────────────
    state = {
        "ok": True,
        "mode": "normal",
        "incident_count": 0,
        "last_action": None,
    }

    # ── 3. Kernel ─────────────────────────────────────
    gate = Gate(policy_cfg)
    ledger = _ledger_obj if _ledger_obj else Ledger(ledger_path)
    rollback = Rollback(max_depth=budgets_cfg.get("rollback_window", 10))
    invariants = default_invariants()
    escalation = Escalation(
        policy_threshold=budgets_cfg.get("policy_violation_threshold", 3),
        invariant_threshold=budgets_cfg.get("invariant_violation_threshold", 1),
        tool_failure_threshold=budgets_cfg.get("tool_failure_threshold", 5),
        ci_failure_threshold=budgets_cfg.get("ci_failure_threshold", 3),
    )
    predictor = FailurePredictor(
        window=budgets_cfg.get("risk_window", 100),
        risk_threshold=budgets_cfg.get("risk_threshold", 0.7),
    )
    telemetry = Telemetry("metrics.jsonl")

    def on_watchdog_trip(reason):
        print(f"\n[WATCHDOG TRIP] reason={reason} triggering rollback")
        restored = rollback.restore()
        if restored:
            state.update(restored)
            print("[WATCHDOG] restored state")
        telemetry.emit("rollback", {"reason": reason})

    wd = Watchdog(timeout_s=10.0, on_trip=on_watchdog_trip)

    # ── 4. Sparse ─────────────────────────────────────
    ewma = EWMA(alpha=0.1)
    habits = Habits(
        min_trials=budgets_cfg.get("habit_min_trials", 5),
        min_confidence=budgets_cfg.get("habit_min_confidence", 0.6),
        decay_hours=budgets_cfg.get("habit_decay_hours", 24),
    )

    # ── 5. Dense ──────────────────────────────────────
    llm = LLM(mode=llm_mode)
    planner = Planner(llm, token_budget=256)
    patcher = Patcher()

    # ── 6. Memory ─────────────────────────────────────
    hot = HotCache(k=64)
    vs = VectorStore()
    epi = Episodic()
    arc = Archive("archive")
    memory = MemoryRouter(hot, vs, epi)

    # ── 7. Scheduler ──────────────────────────────────
    tick_s = budgets_cfg.get("tick_s", 0.5)
    bud = Budgets(
        token_per_min=budgets_cfg.get("token_per_min", 8000),
        tool_calls_per_min=budgets_cfg.get("tool_calls_per_min", 30),
    )
    clocks = Clocks(
        fast_s=budgets_cfg.get("tick_s", 0.5),
        medium_s=budgets_cfg.get("anomaly_interval_s", 5.0),
        slow_s=budgets_cfg.get("plan_interval_s", 15.0),
        tick_s=tick_s,
    )

    # ── 8. Central Executor (NON-BYPASSABLE) ──────────
    executor = Executor(
        gate=gate,
        budgets=bud,
        tool_registry=TOOL_REGISTRY,
        ledger=ledger,
        memory_router=memory,
        invariants=invariants,
        telemetry=telemetry,
    )

    # ── 9. Genesis record ─────────────────────────────
    ledger.write_genesis(seed, cfg_hash, code_hash)

    # ── 10. Sandbox ───────────────────────────────────
    sandbox = DockerSandbox()
    try:
        sandbox.start()
        shell_set_sandbox(sandbox)
        ops_set_sandbox(sandbox)
        print("[SANDBOX] Docker isolation active.")
    except Exception as e:
        print(
            f"[WARN] Failed to start Docker sandbox, falling back to host execution: {e}"
        )
        sandbox = None

    agent = {
        "state": state,
        "gate": gate,
        "ledger": ledger,
        "rollback": rollback,
        "wd": wd,
        "ewma": ewma,
        "habits": habits,
        "planner": planner,
        "patcher": patcher,
        "memory": memory,
        "arc": arc,
        "bud": bud,
        "clocks": clocks,
        "executor": executor,
        "escalation": escalation,
        "predictor": predictor,
        "telemetry": telemetry,
        "invariants": invariants,
        "evolution_bounds": EvolutionBounds(
            max_episodes_per_window=200,
            max_vectors_per_window=500,
            max_habits=50,
            window_ticks=1000,
        ),
        "snapshots": SnapshotManager(snapshot_dir="snapshots", interval_ticks=500),
        "adaptation": AdaptationEngine(),
        "sandbox": sandbox,
    }
    return agent


def make_step(agent):  # noqa: C901
    """Build the main tick step function using all hardened modules."""
    rollback = agent["rollback"]
    wd = agent["wd"]
    ledger = agent["ledger"]
    ewma = agent["ewma"]
    habits = agent["habits"]
    planner = agent["planner"]
    patcher = agent["patcher"]
    memory = agent["memory"]
    clocks = agent["clocks"]
    state = agent["state"]
    executor = agent["executor"]
    escalation = agent["escalation"]
    predictor = agent["predictor"]
    telemetry = agent["telemetry"]
    bounds = agent["evolution_bounds"]
    snapshots = agent["snapshots"]
    adaptation = agent["adaptation"]

    def step(tick):  # noqa: C901
        wd.kick(tick)

        # ── Check safe mode ───────────────────────────
        if escalation.in_safe_mode():
            state["mode"] = "safe"

        if predictor.should_safe_mode():
            state["mode"] = "safe"

        # ── FAST: Metric ingest ───────────────────────
        if clocks.due_fast(tick):
            m = read_metrics()
            mu = ewma.update(m["error_rate"])
            bad = anomalous(
                m["error_rate"],
                mu,
                k=2.5,
                sigma=getattr(ewma, "sigma", 0.05),
            )

            ctx = (
                f"tick={tick} error_rate={m['error_rate']:.4f} "
                f"mu={mu:.4f} lat={m.get('latency_p99', 0):.1f} bad={bad}"
            )
            memory.put_hot(ctx)
            memory.stage_vector(ctx, metadata={"tick": tick, "bad": bad})

            state["_last_ctx"] = ctx
            state["_last_bad"] = bad

            # Feed predictor
            predictor.update(
                {
                    "fail": bad,
                    "load": m["error_rate"],
                    "latency_ms": m.get("latency_p99", 0),
                }
            )

            if bad:
                telemetry.emit("anomaly", {"tick": tick, "error_rate": m["error_rate"]})

        # ── MEDIUM: Anomaly scoring + habit check ─────
        if clocks.due_medium(tick) and state.get("_last_bad"):
            ctx = state.get("_last_ctx", "")
            print(f"\n[ANOMALY] {ctx}")

            candidates = ["restart_service", "run_healthcheck", "noop"]
            best = habits.best_action(candidates)
            if best:
                print(f"[REFLEX] Confidence-bounded habit: {best}")
                telemetry.emit("habit_hit", {"tool": best})
            state["_candidate"] = best

        # ── SLOW: Planning + gated execution ──────────
        if clocks.due_slow(tick) and state.get("_last_bad"):
            ctx = state.get("_last_ctx", "")
            history = memory.episode_strings(5)

            # In safe mode, only allow noop
            if state.get("mode") == "safe":
                act = {"tool": "noop", "risk": 0, "args": {}}
                plan = "Safe mode: noop only"
            else:
                candidate = state.get("_candidate")
                if candidate:
                    plan = f"Reflex execution of {candidate}"
                    act = {
                        "tool": candidate,
                        "risk": 0,
                        "args": {"service": "app", "name": "app"},
                        "reasoning": "bypassed LLM via habit reflex",
                    }
                    state["_candidate"] = None
                else:
                    plan = planner.propose(ctx, history=history)
                    act = patcher.plan_to_action(plan)

            print(f"[PLAN] {plan}")

            # ── Snapshot for rollback ─────────────────
            rollback.snapshot(dict(state))

            # ── Central executor (gate → budget → txn → tool → ledger)
            result = executor.execute_checked(act, state, context=ctx)

            print(
                f"[EXEC] tool={act.get('tool')} "
                f"status={result['status']} ok={result.get('ok')}"
            )

            if result["ok"]:
                habits.record(act["tool"], True)
                memory.stage_episode(
                    {
                        "ctx": ctx,
                        "act": act,
                        "success": True,
                    }
                )
                state["last_action"] = act["tool"]
                state["_last_bad"] = False
            else:
                habits.record(act["tool"], False)

                # Escalation
                if result["status"] == "rejected":
                    escalation.record("policy_violation")
                elif result["status"] == "invariant_violation":
                    escalation.record("invariant_violation")
                else:
                    escalation.record("tool_failure")

                # Rollback
                restored = rollback.restore()
                if restored:
                    state.update(restored)
                    print("[ROLLBACK] state restored")
                    telemetry.emit("rollback", {"tool": act.get("tool")})

                state["incident_count"] += 1

            # ── Evolution bounds check ────────────────
            bounds.record("tool_calls", 1, tick=tick)
            ok, violations = bounds.check_state(state, tick=tick)
            if not ok:
                telemetry.emit("evolution_violation", {"violations": violations})

            ok, violation = bounds.check_habits(habits.table, tick=tick)
            if not ok:
                adaptation.adapt_habits(habits, tick=tick)
                telemetry.emit("habits_pruned", violation)

            # ── Periodic snapshots ────────────────────
            if snapshots.due(tick):
                _, ledger_height = Ledger.verify("ledger.jsonl")
                inv_hash = state_hash(state)
                anchor = snapshots.capture(state, ledger_height, inv_hash, tick)
                ledger.append(anchor)
                print(f"[SNAPSHOT] tick={tick}" f" h={anchor['snapshot_hash'][:12]}")

            # ── Stable adaptation ─────────────────────
            adaptation.reset_window()

        wd.check(tick)

    return step


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic Autonomous DevOps Agent (Hardened)"
    )
    parser.add_argument(
        "--llm",
        default="stub",
        choices=["stub", "api", "ollama"],
        help="LLM backend (default: stub)",
    )
    parser.add_argument(
        "--tick",
        type=float,
        default=None,
        help="Override event loop tick (seconds)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" Deterministic Autonomous DevOps Agent [HARDENED]")
    print(f" LLM mode : {args.llm}")
    print(f" Policy   : {CONFIG_DIR / 'policy.yaml'}")
    print(" Ledger   : ledger.jsonl")
    print(" Telemetry: metrics.jsonl")
    print("=" * 60)

    agent = build_agent(llm_mode=args.llm)
    tick = args.tick or budgets_cfg.get("tick_s", 0.5)
    step_fn = make_step(agent)
    loop = EventLoop(tick_s=tick, step_fn=step_fn)

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n[Agent] shutting down, archiving state...")
        if agent.get("sandbox"):
            agent["sandbox"].stop()
        Path("archive").mkdir(exist_ok=True)
        agent["arc"].dump(agent["state"], label="shutdown")

        ok, n = Ledger.verify("ledger.jsonl")
        print(
            f"[Ledger integrity]: {'PASS' if ok else 'FAIL'} " f"({n} verified records)"
        )

        telem = agent["telemetry"].summary()
        print(f"[Telemetry] {telem}")
        print("[Agent] Shutdown complete.")


if __name__ == "__main__":
    main()
