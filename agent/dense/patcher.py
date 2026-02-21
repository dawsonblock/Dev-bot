class Patcher:
    def plan_to_action(self, plan_dict):
        if isinstance(plan_dict, dict):
            return {
                "tool": plan_dict.get("tool", "noop"),
                "risk": int(plan_dict.get("risk", 0)),
                "args": plan_dict.get("args", {}),
                "reasoning": plan_dict.get("reasoning", "")
            }
        return {"tool": "noop", "risk": 0, "args": {}}
