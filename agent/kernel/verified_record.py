"""Verified execution records — HMAC-signed, externally auditable.

Every committed action produces a record containing:
- deterministic tick
- state hash before and after
- action descriptor
- invariant check result
- HMAC-SHA256 signature

An independent verifier can confirm correctness without executing the system.
"""

import hashlib
import hmac
import json
import os
import time


# Device signing key — in production, sourced from HSM or environment.
_DEVICE_KEY = os.environ.get(
    "DEVBOT_DEVICE_KEY", "devbot-default-key-change-me"
).encode()


def _sign(payload_bytes, key=None):
    """Produce HMAC-SHA256 signature over payload bytes."""
    k = key or _DEVICE_KEY
    return hmac.new(k, payload_bytes, hashlib.sha256).hexdigest()


def build_verified_record(
    tick,
    action,
    state_before,
    state_after,
    invariant_ok,
    gate_rule="GATE-000",
    result_summary=None,
):
    """Build a signed verified execution record.

    Returns:
        dict with all required fields + signature
    """
    record = {
        "type": "verified_exec",
        "tick": tick,
        "wall_ts": int(time.time() * 1000),
        "action": {
            "tool": action.get("tool", "unknown"),
            "args": action.get("args", {}),
            "risk": action.get("risk", 0),
        },
        "state_before": state_before,
        "state_after": state_after,
        "invariant_ok": invariant_ok,
        "gate_rule": gate_rule,
        "result": result_summary or {},
    }

    # Canonical serialization for signing
    payload = json.dumps(record, sort_keys=True).encode()
    record["signature"] = _sign(payload)

    return record


def verify_record_signature(record, key=None):
    """Verify the HMAC signature on a verified record.

    Returns:
        (valid: bool, reason: str)
    """
    sig = record.get("signature")
    if not sig:
        return False, "missing_signature"

    # Reconstruct the signed payload (without the signature field)
    rec_copy = {k: v for k, v in record.items() if k != "signature"}
    payload = json.dumps(rec_copy, sort_keys=True).encode()
    expected = _sign(payload, key)

    if hmac.compare_digest(sig, expected):
        return True, "ok"
    return False, "signature_mismatch"
