"""Policy schema validation — refuse to boot on malformed policy."""

REQUIRED_TOOL_FIELDS = {"allowed"}
OPTIONAL_TOOL_FIELDS = {
    "max_risk",
    "requires_approval",
    "reversibility",
    "max_rate",
    "args",
    "retry",
    "failure_behavior",
}
VALID_REVERSIBILITY = {"reversible", "compensatable", "irreversible"}


class PolicyValidationError(Exception):
    pass


def _validate_tool(tool_name, cfg):
    if not isinstance(cfg, dict):
        raise PolicyValidationError(f"Tool '{tool_name}': config must be a dict")

    if "allowed" not in cfg:
        raise PolicyValidationError(
            f"Tool '{tool_name}': missing required field 'allowed'"
        )

    rev = cfg.get("reversibility")
    if rev and rev not in VALID_REVERSIBILITY:
        raise PolicyValidationError(
            f"Tool '{tool_name}': invalid reversibility '{rev}'"
        )

    args = cfg.get("args")
    if args:
        if not isinstance(args, dict):
            raise PolicyValidationError(f"Tool '{tool_name}': 'args' must be a dict")
        for arg_name, rule in args.items():
            if not isinstance(rule, dict):
                raise PolicyValidationError(
                    f"Tool '{tool_name}' arg '{arg_name}': rule must be a dict"
                )


def validate_policy(policy):
    """Validate the full policy dict. Raises PolicyValidationError on failure."""
    if not isinstance(policy, dict):
        raise PolicyValidationError("Policy must be a dict")

    tools = policy.get("tools")
    if not tools or not isinstance(tools, dict):
        raise PolicyValidationError("Policy must contain a 'tools' dict")

    for tool_name, cfg in tools.items():
        _validate_tool(tool_name, cfg)

    return True


def validate_budgets(budgets):
    """Validate the budgets config dict."""
    if not isinstance(budgets, dict):
        raise PolicyValidationError("Budgets must be a dict")
    required = ["token_per_min", "tool_calls_per_min", "tick_s"]
    for key in required:
        if key not in budgets:
            raise PolicyValidationError(f"Budgets missing required key '{key}'")
    return True
