"""Design-by-contract decorators — pre/post-condition enforcement.

Provides @requires, @ensures, and @invariant_of decorators that
validate function inputs and outputs at runtime. Violations are
logged and optionally escalated.

Usage:
    @requires(lambda x: x > 0, "x must be positive")
    @ensures(lambda result: result is not None, "must return a value")
    def my_function(x):
        return x * 2
"""

import functools


class ContractViolation(Exception):
    """Raised when a contract (pre/post condition) is violated."""

    def __init__(self, kind, message, func_name="unknown"):
        self.kind = kind  # 'precondition' | 'postcondition' | 'invariant'
        self.func_name = func_name
        super().__init__(f"[{kind}] {func_name}: {message}")


def requires(predicate, message="Precondition failed"):
    """Decorator enforcing a precondition on function arguments.

    The predicate receives the same arguments as the decorated function.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not predicate(*args, **kwargs):
                raise ContractViolation("precondition", message, fn.__name__)
            return fn(*args, **kwargs)

        wrapper._contracts = getattr(fn, "_contracts", []) + [
            {"type": "requires", "message": message}
        ]
        return wrapper

    return decorator


def ensures(predicate, message="Postcondition failed"):
    """Decorator enforcing a postcondition on the return value.

    The predicate receives the return value as its sole argument.
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            if not predicate(result):
                raise ContractViolation("postcondition", message, fn.__name__)
            return result

        wrapper._contracts = getattr(fn, "_contracts", []) + [
            {"type": "ensures", "message": message}
        ]
        return wrapper

    return decorator


def invariant_of(state_fn, predicate, message="Invariant violation"):
    """Decorator asserting that a state invariant holds after execution.

    Args:
        state_fn: callable returning the state dict to check
        predicate: callable(state) -> bool
        message: error message on failure
    """

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            state = state_fn()
            if not predicate(state):
                raise ContractViolation("invariant", message, fn.__name__)
            return result

        wrapper._contracts = getattr(fn, "_contracts", []) + [
            {"type": "invariant", "message": message}
        ]
        return wrapper

    return decorator


def list_contracts(fn):
    """Introspect contracts attached to a decorated function."""
    return getattr(fn, "_contracts", [])


class ContractRegistry:
    """Central registry of all contract-annotated functions.

    Allows enumeration and reporting of all contracts in the system.
    """

    def __init__(self):
        self._functions = []

    def register(self, fn):
        """Register a contract-decorated function."""
        contracts = list_contracts(fn)
        if contracts:
            self._functions.append(
                {
                    "name": fn.__name__,
                    "module": fn.__module__,
                    "contracts": contracts,
                }
            )
        return fn

    def report(self):
        """Generate a summary of all registered contracts."""
        total = sum(len(f["contracts"]) for f in self._functions)
        return {
            "functions": len(self._functions),
            "total_contracts": total,
            "details": self._functions,
        }
