import argparse
import sys
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent))

from kernel.event_loop import EventLoop
from kernel.gate import Gate
from kernel.ledger import Ledger
from kernel.watchdog import Watchdog
from kernel.rollback import Rollback

from sparse.anomaly import EWMA, anomalous
from sparse.habits import Habits

from dense.llm_iface import LLM
from dense.planner import Planner
from dense.patcher import Patcher

from memory.hot_cache import HotCache
from memory.vector_store import VectorStore
from memory.episodic_ledger import Episodic
from memory.archive import Archive

from tools.metrics import read as read_metrics
from tools.ci import run_tests as run_tests_stub
from tools.shell import run as run_shell

from scheduler.clocks import Clocks
from scheduler.budgets import Budgets

CONFIG_DIR = Path(__file__).parent / "config"
policy_cfg = yaml.safe_load((CONFIG_DIR / "policy.yaml").read_text())
budgets_cfg = yaml.safe_load((CONFIG_DIR / "budgets.yaml").read_text())


def build_agent(llm_mode="stub"):
    state = {"ok": True, "incident_count": 0, "last_action": None}
    agent = {}

    def on_watchdog_trip(reason):
        print(f"\n[WATCHDOG TRIP] reason={reason} triggering rollback")
        if state:
            restored = agent["rollback"].restore()
            if restored:
                agent["state"].update(restored)
                print(f"[WATCHDOG] restored state: {state}")

    rollback = Rollback(max_depth=budgets_cfg.get("rollback_window", 10))
    wd = Watchdog(timeout_s=10.0, on_trip=on_watchdog_trip)
    gate = Gate(policy_cfg)
    ledger = Ledger("ledger.jsonl")

    ewma = EWMA(alpha=0.1)
    habits = Habits()

    llm = LLM(mode=llm_mode)
    planner = Planner(llm, token_budget=256)
    patcher = Patcher()

    hot = HotCache(k=64)
    vs = VectorStore()
    epi = Episodic()
    arc = Archive("archive")

    bud = Budgets(
        token_per_min=budgets_cfg.get("token_per_min", 8000),
        tool_calls_per_min=budgets_cfg.get("tool_calls_per_min", 30),
    )

    clocks = Clocks(
        fast_s=budgets_cfg.get("tick_s", 0.5),
        medium_s=budgets_cfg.get("anomaly_interval_s", 5.0),
        slow_s=budgets_cfg.get("plan_interval_s", 15.0),
    )

    agent.update(
        {
            "rollback": rollback,
            "wd": wd,
            "gate": gate,
            "ledger": ledger,
            "ewma": ewma,
            "habits": habits,
            "planner": planner,
            "patcher": patcher,
            "epi": epi,
            "arc": arc,
            "hot": hot,
            "vs": vs,
            "bud": bud,
            "clocks": clocks,
            "state": state,
        }
    )
    return agent


def make_step(agent):
    rollback = agent["rollback"]
    wd = agent["wd"]
    gate = agent["gate"]
    ledger = agent["ledger"]
    ewma = agent["ewma"]
    habits = agent["habits"]
    planner = agent["planner"]
    patcher = agent["patcher"]
    hot = agent["hot"]
    vs = agent["vs"]
    epi = agent["epi"]
    bud = agent["bud"]
    clocks = agent["clocks"]
    state = agent["state"]

    def step(now):
        wd.kick(now)

        if clocks.due_fast(now):
            m = read_metrics()
            mu = ewma.update(m["error_rate"])
            bad = anomalous(
                m["error_rate"], mu, k=2.5, sigma=getattr(ewma, "sigma", 0.05)
            )

            ctx = f"ts={now:.1f} error_rate={m['error_rate']:.4f} mu={mu:.4f} lat={m.get('latency_p99',0):.1f} bad={bad}"
            hot.put(ctx)
            vs.add(ctx, metadata={"ts": now, "bad": bad})

            state["_last_ctx"] = ctx
            state["_last_bad"] = bad

        if clocks.due_medium(now) and state.get("_last_bad"):
            ctx = state.get("_last_ctx", "")
            print(f"\n[ANOMALY] {ctx}")

            candidates = ["restart_service", "run_healthcheck", "noop"]
            best = habits.best_action(candidates)
            if best:
                print(
                    f"[REFLEX] Known-good habit found: bypassing LLM to deploy {best}"
                )
            state["_candidate"] = best

        if clocks.due_slow(now) and state.get("_last_bad") and bud.use_call():
            ctx = state.get("_last_ctx", "")
            history = epi.to_strings(5)

            candidate = state.get("_candidate")
            if candidate:
                plan = f"Reflex execution of {candidate}"
                act = {
                    "tool": candidate,
                    "risk": 0,
                    "args": {},
                    "reasoning": "bypassed LLM via habit reflex",
                }
                state["_candidate"] = None
            else:
                plan = planner.propose(ctx, history=history)
                act = patcher.plan_to_action(plan)

            ok, reason = gate.check(act)

            ledger.append(
                {
                    "event": "action_proposal",
                    "plan": plan,
                    "act": act,
                    "gate": reason,
                }
            )

            print(f"[PLAN] {plan}")
            print(
                f"[GATE] ok={ok} tool={act.get('tool')} risk={act.get('risk')} reason={reason}"
            )

            if ok:
                rollback.snapshot(dict(state))

                test_result = run_tests_stub()
                if not test_result.get("ok", True):
                    print(
                        f"[CI FAIL] rolling back. Summary: {test_result.get('summary')}"
                    )
                    restored = rollback.restore()
                    if restored:
                        state.update(restored)
                    ledger.append({"event": "ci_fail", "act": act})
                else:
                    success = execute(act)
                    habits.record(act["tool"], success)
                    epi.add({"ctx": ctx, "act": act, "success": success})

                    state["last_action"] = act["tool"]
                    state["incident_count"] += int(not success)

                    ledger.append(
                        {
                            "event": "action_executed",
                            "act": act,
                            "success": success,
                        }
                    )
                    print(f"[EXEC] {act['tool']} success={success}")

                    if not success:
                        print("[EXEC FAIL] rolling back")
                        restored = rollback.restore()
                        if restored:
                            state.update(restored)

                    state["_last_bad"] = False

        wd.check(now)

    return step


def execute(act):
    tool = act.get("tool", "noop")
    if tool == "noop":
        return True

    if tool == "restart_service":
        svc = act.get("args", {}).get("name", "")
        if not svc:
            print("[EXEC FAIL] restart_service requires a 'name' argument")
            return False
        print(f"  -> [systemctl] restarting service: {svc}")
        res = run_shell(f"sudo systemctl restart {svc}")
        return res["rc"] == 0

    if tool == "run_healthcheck":
        url = act.get("args", {}).get("url", "http://localhost/")
        print(f"  -> [curl] healthchecking: {url}")
        res = run_shell(f"curl -s -f {url}")
        return res["rc"] == 0

    if tool == "shell":
        cmd = act.get("args", {}).get("cmd", "")
        if not cmd:
            return False
        print(f"  -> [shell] executing: {cmd}")
        res = run_shell(cmd)
        return res["rc"] == 0

    return False


def main():
    parser = argparse.ArgumentParser(description="Autonomous DevOps Agent")
    parser.add_argument(
        "--llm",
        default="stub",
        choices=["stub", "api", "ollama"],
        help="LLM backend (default: stub)",
    )
    parser.add_argument(
        "--tick", type=float, default=None, help="Override event loop tick (seconds)"
    )
    args = parser.parse_args()

    print("=" * 60)
    print(" Deterministic Autonomous DevOps Agent")
    print(f" LLM mode : {args.llm}")
    print(f" Policy   : {CONFIG_DIR / 'policy.yaml'}")
    print(" Ledger   : ledger.jsonl")
    print("=" * 60)

    agent = build_agent(llm_mode=args.llm)
    tick = args.tick or budgets_cfg.get("tick_s", 0.5)
    step_fn = make_step(agent)
    loop = EventLoop(tick_s=tick, step_fn=step_fn)

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\n[Agent] shutting down, archiving state...")
        Path("archive").mkdir(exist_ok=True)

        agent["arc"].dump(agent["state"], label="shutdown")
        print("[Agent] Shutdown complete.")

        ok, n = Ledger.verify("ledger.jsonl")
        print(
            f"[Ledger integrity check]: {'PASS' if ok else 'FAIL'} ({n} mathematically verified records)"
        )


if __name__ == "__main__":
    main()
