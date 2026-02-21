"""Independent verifier — validates ledger chain, signatures, and invariant flags.

Can run standalone against a ledger file without executing the system.
"""

import hashlib
import json
from .verified_record import verify_record_signature


class VerificationReport:
    """Structured pass/fail report from verification."""

    def __init__(self):
        self.total = 0
        self.chain_ok = True
        self.signatures_ok = True
        self.invariants_ok = True
        self.errors = []

    @property
    def passed(self):
        return self.chain_ok and self.signatures_ok and self.invariants_ok

    def summary(self):
        return {
            "passed": self.passed,
            "total_records": self.total,
            "chain_ok": self.chain_ok,
            "signatures_ok": self.signatures_ok,
            "invariants_ok": self.invariants_ok,
            "errors": self.errors[:20],  # cap for readability
        }


def verify_ledger(path, check_signatures=True, device_key=None):
    """Full verification of a ledger file.

    Checks:
        1. SHA-256 hash chain integrity
        2. HMAC signature validity on verified_exec records
        3. Invariant flags (no false flags in committed records)

    Args:
        path: path to ledger.jsonl
        check_signatures: whether to verify HMAC signatures
        device_key: optional device key (bytes) for signature verification

    Returns:
        VerificationReport
    """
    report = VerificationReport()
    prev_hash = "0" * 64

    try:
        with open(path) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue

                row = json.loads(line)
                report.total += 1

                # ── 1. Hash chain ─────────────────────
                blob = json.dumps(row["rec"], sort_keys=True).encode()
                expected = hashlib.sha256(prev_hash.encode() + blob).hexdigest()
                if expected != row["hash"]:
                    report.chain_ok = False
                    report.errors.append(
                        {
                            "index": i,
                            "type": "hash_chain_break",
                            "expected": expected[:16],
                            "got": row["hash"][:16],
                        }
                    )
                    return report  # chain break is fatal

                prev_hash = row["hash"]
                rec = row["rec"]

                # ── 2. Signature check ────────────────
                if check_signatures and rec.get("type") == "verified_exec":
                    valid, reason = verify_record_signature(rec, key=device_key)
                    if not valid:
                        report.signatures_ok = False
                        report.errors.append(
                            {
                                "index": i,
                                "type": "signature_invalid",
                                "reason": reason,
                                "tick": rec.get("tick"),
                            }
                        )

                # ── 3. Invariant flags ────────────────
                if (
                    rec.get("type") == "verified_exec"
                    and rec.get("invariant_ok") is False
                ):
                    report.invariants_ok = False
                    report.errors.append(
                        {
                            "index": i,
                            "type": "invariant_violation_committed",
                            "tick": rec.get("tick"),
                        }
                    )

    except FileNotFoundError:
        pass  # empty ledger is valid
    except json.JSONDecodeError as e:
        report.chain_ok = False
        report.errors.append({"type": "json_parse_error", "detail": str(e)})

    return report


def verify_file(path):
    """CLI-friendly verification. Prints results and returns exit code."""
    report = verify_ledger(path)
    s = report.summary()
    status = "PASS" if s["passed"] else "FAIL"
    print(f"[Verifier] {status}")
    print(f"  Records  : {s['total_records']}")
    print(f"  Chain    : {'OK' if s['chain_ok'] else 'BROKEN'}")
    print(f"  Signatures: {'OK' if s['signatures_ok'] else 'INVALID'}")
    print(f"  Invariants: {'OK' if s['invariants_ok'] else 'VIOLATED'}")
    if s["errors"]:
        print(f"  Errors ({len(s['errors'])}):")
        for e in s["errors"][:5]:
            print(f"    {e}")
    return 0 if s["passed"] else 1


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "ledger.jsonl"
    exit(verify_file(path))
