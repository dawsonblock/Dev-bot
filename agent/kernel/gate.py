class Gate:
    def __init__(self, policy):
        self.policy = policy

    def check(self, action):
        rule = self.policy.get(action.get("tool", "noop"), {})
        if not rule:
            return False, "tool_not_in_policy"
        if action.get("risk", 0) > rule.get("max_risk", 0):
            return False, "risk_exceeded"
        if rule.get("requires_approval", False) and not action.get("approved", False):
            return False, "needs_approval"
        return True, "ok"
