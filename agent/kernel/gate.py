"""Hardened policy gate — argument validation, rate limiting, reversibility.

Every action must pass through Gate.check() before execution.
Returns (allowed: bool, reason: str, rule_id: str).
"""

import re
import time


class Gate:
    def __init__(self, policy):
        self.policy = policy
        self._rate_tracker = {}  # tool -> [timestamps]

    def check(self, action):
        """Check an action against the full policy.

        Returns:
            (allowed, reason, rule_id) tuple
        """
        tool = action.get("tool", "")
        args = action.get("args", {})

        tools = self.policy.get("tools", self.policy)
        if tool not in tools:
            return False, "tool_not_defined", "GATE-001"

        cfg = tools[tool]

        # 1. Tool must be explicitly allowed
        if not cfg.get("allowed", False):
            return False, "tool_blocked", "GATE-002"

        # 2. Risk ceiling
        max_risk = cfg.get("max_risk", 0)
        if action.get("risk", 0) > max_risk:
            return False, f"risk_exceeded (max={max_risk})", "GATE-003"

        # 3. Approval required for irreversible / flagged actions
        if cfg.get("requires_approval", False) and not action.get("approved", False):
            return False, "needs_approval", "GATE-004"

        # 4. Argument validation via regex
        arg_rules = cfg.get("args", {})
        for arg_name, rule in arg_rules.items():
            val = args.get(arg_name, "")
            if "required" in rule and rule["required"] and not val:
                return False, f"arg_missing_{arg_name}", "GATE-005"
            if val and "regex" in rule:
                if not re.match(rule["regex"], str(val)):
                    return (
                        False,
                        f"arg_invalid_{arg_name} (pattern={rule['regex']})",
                        "GATE-006",
                    )

        # 5. Rate limiting
        max_rate = cfg.get("max_rate")
        if max_rate:
            now = time.time()
            history = self._rate_tracker.get(tool, [])
            # Keep only last 60 seconds
            history = [t for t in history if now - t < 60.0]
            if len(history) >= max_rate:
                return False, f"rate_exceeded (max={max_rate}/min)", "GATE-007"
            history.append(now)
            self._rate_tracker[tool] = history

        # 6. Reversibility warning (logged, not blocking by itself)
        reversibility = cfg.get("reversibility", "reversible")
        if reversibility == "irreversible" and not action.get("approved", False):
            return False, "irreversible_needs_approval", "GATE-008"

        return True, "ok", "GATE-000"
