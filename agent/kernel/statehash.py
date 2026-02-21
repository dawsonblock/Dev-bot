"""Canonical state hashing — deterministic JSON fingerprinting."""

import hashlib
import json


def _default_serializer(obj):
    """Handle non-JSON-serializable types gracefully."""
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    if hasattr(obj, "__dict__"):
        return repr(obj)
    return str(obj)


def state_hash(state):
    """Produce a stable SHA-256 hash of the state dict.

    Uses sorted keys and a custom serializer so the hash is
    identical across runs for the same logical state.
    """
    blob = json.dumps(state, sort_keys=True, default=_default_serializer).encode()
    return hashlib.sha256(blob).hexdigest()
