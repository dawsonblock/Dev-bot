"""Device attestation — signed attestation reports for remote verification.

Produces attestation reports containing:
- Node ID
- State hash
- Ledger height
- Timestamp
- HSM-backed signature

External parties can verify a node's state without trusting the node.
"""

import json
import time

from .hsm import create_hsm
from .statehash import state_hash


class AttestationReport:
    """Signed attestation of a node's current state."""

    def __init__(self, node_id, state, ledger_height, hsm=None):
        self.hsm = hsm or create_hsm()
        self.report = {
            "type": "attestation",
            "node_id": node_id,
            "state_hash": state_hash(state),
            "ledger_height": ledger_height,
            "timestamp": int(time.time() * 1000),
            "hsm_backend": self.hsm.backend,
            "key_id": self.hsm.key_id,
        }

        # Sign the canonical report
        payload = json.dumps(self.report, sort_keys=True).encode()
        self.report["signature"] = self.hsm.sign(payload)

    def to_dict(self):
        return dict(self.report)


class AttestationVerifier:
    """Verify attestation reports from remote nodes."""

    def __init__(self, hsm=None):
        self.hsm = hsm or create_hsm()

    def verify(self, report):
        """Verify an attestation report's signature.

        Args:
            report: dict with attestation data + signature

        Returns:
            (valid: bool, reason: str)
        """
        sig = report.get("signature")
        if not sig:
            return False, "missing_signature"

        # Reconstruct signed payload
        report_copy = {k: v for k, v in report.items() if k != "signature"}
        payload = json.dumps(report_copy, sort_keys=True).encode()

        if self.hsm.verify(payload, sig):
            return True, "ok"
        return False, "signature_mismatch"

    def verify_freshness(self, report, max_age_s=60):
        """Check that the attestation is recent enough."""
        ts = report.get("timestamp", 0)
        age = (time.time() * 1000) - ts
        if age > max_age_s * 1000:
            return False, f"attestation_stale ({age/1000:.1f}s old)"
        return True, "fresh"


def create_attestation(node_id, state, ledger_height, hsm=None):
    """Convenience: create and return attestation report dict."""
    report = AttestationReport(node_id, state, ledger_height, hsm)
    return report.to_dict()
