"""Central non-bypassable executor.

ALL tool dispatch MUST go through Executor.execute_checked().
No direct tool calls anywhere else in the codebase.
Enforces: gate → budget → transaction → tool → ledger.
"""

import time
from .gate import Gate
from .txn import Transaction
from .statehash import state_hash
from .determinism import get_tick


class Executor:
    def __init__(
        self,
        gate,
        budgets,
        tool_registry,
        ledger,
        memory_router=None,
        invariants=None,
        telemetry=None,
    ):
        self.gate = gate
        self.budgets = budgets
        self.tools = tool_registry
        self.ledger = ledger
        self.memory = memory_router
        self.invariants = invariants
        self.telemetry = telemetry
        self._recent_failures = []

    def execute_checked(self, action, state, context=""):
        """Execute an action through the full safety pipeline.

        Returns:
            dict with keys: status, ok, result, gate_rule, state_before, state_after
        """
        tick = get_tick()
        t0 = time.time()
        tool_name = action.get("tool", "noop")

        # ── 1. Gate check ─────────────────────────────
        allowed, reason, rule_id = self.gate.check(action)
        if not allowed:
            record = {
                "status": "rejected",
                "ok": False,
                "reason": reason,
                "gate_rule": rule_id,
                "tick": tick,
                "tool": tool_name,
            }
            self.ledger.append(
                {
                    "event": "gate_reject",
                    "tick": tick,
                    "action": action,
                    "reason": reason,
                    "rule_id": rule_id,
                }
            )
            if self.telemetry:
                self.telemetry.emit(
                    "gate_reject",
                    {
                        "tool": tool_name,
                        "reason": reason,
                        "rule_id": rule_id,
                    },
                )
            return record

        # ── 2. Budget check ───────────────────────────
        if not self.budgets.use_call():
            record = {
                "status": "budget_block",
                "ok": False,
                "reason": "budget_exhausted",
                "tick": tick,
                "tool": tool_name,
            }
            self.ledger.append(
                {
                    "event": "budget_block",
                    "tick": tick,
                    "action": action,
                }
            )
            if self.telemetry:
                self.telemetry.emit("budget_block", {"tool": tool_name})
            return record

        # ── 3. Repeat-failure guard ───────────────────
        if self._is_repeat_failure(tool_name):
            record = {
                "status": "repeat_blocked",
                "ok": False,
                "reason": "repeated_failure_blocked",
                "tick": tick,
                "tool": tool_name,
            }
            self.ledger.append(
                {
                    "event": "repeat_blocked",
                    "tick": tick,
                    "action": action,
                }
            )
            return record

        # ── 4. Resolve tool ───────────────────────────
        tool_cls = self.tools.get(tool_name)
        if not tool_cls:
            return {
                "status": "tool_not_found",
                "ok": False,
                "tick": tick,
                "tool": tool_name,
            }

        # ── 5. State hash (before) ────────────────────
        before = state_hash(state)

        # ── 6. Transaction-wrapped execution ──────────
        with Transaction(state, memory_router=self.memory) as txn:
            try:
                result = tool_cls.run(action.get("args", {}))
            except Exception as e:
                result = {
                    "ok": False,
                    "error": str(e),
                    "rc": -1,
                    "stdout": "",
                    "stderr": str(e),
                }

            success = result.get("ok", False)

            if not success:
                txn.abort()
                self._record_failure(tool_name)
            else:
                # ── 7. Invariant check ────────────────
                if self.invariants:
                    try:
                        self.invariants.validate(state)
                    except Exception as inv_err:
                        txn.abort()
                        self.ledger.append(
                            {
                                "event": "invariant_violation",
                                "tick": tick,
                                "action": action,
                                "error": str(inv_err),
                            }
                        )
                        return {
                            "status": "invariant_violation",
                            "ok": False,
                            "reason": str(inv_err),
                            "tick": tick,
                        }
                txn.commit()

        # ── 8. State hash (after) ─────────────────────
        after = state_hash(state)
        latency = time.time() - t0

        # ── 9. Forensic ledger entry ──────────────────
        self.ledger.append(
            {
                "event": "exec",
                "tick": tick,
                "action": action,
                "context": context[:200],
                "result": {
                    "ok": success,
                    "rc": result.get("rc"),
                    "stdout": result.get("stdout", "")[:200],
                    "stderr": result.get("stderr", "")[:200],
                },
                "state_before": before,
                "state_after": after,
                "gate_rule": rule_id,
                "latency_ms": round(latency * 1000, 1),
            }
        )

        # ── 10. Telemetry ─────────────────────────────
        if self.telemetry:
            self.telemetry.emit(
                "exec",
                {
                    "tool": tool_name,
                    "ok": success,
                    "latency_ms": round(latency * 1000, 1),
                },
            )

        return {
            "status": "executed",
            "ok": success,
            "result": result,
            "gate_rule": rule_id,
            "state_before": before,
            "state_after": after,
            "tick": tick,
        }

    def _is_repeat_failure(self, tool_name, lookback=3):
        """Block tool if it failed N consecutive times recently."""
        recent = [f for f in self._recent_failures[-lookback:] if f == tool_name]
        return len(recent) >= lookback

    def _record_failure(self, tool_name):
        """Track recent failures for repeat-failure detection."""
        self._recent_failures.append(tool_name)
        if len(self._recent_failures) > 20:
            self._recent_failures.pop(0)
