"""Structured telemetry — JSONL metrics for observability."""

import json
import time
from pathlib import Path


class Telemetry:
    """Append-only JSONL metrics sink.

    Tracks: gate rejects, rollbacks, anomaly rate, CI failures,
    habit hits, decision latency, resource usage, scheduler load.
    """

    def __init__(self, path="metrics.jsonl"):
        self.path = Path(path)
        self._counters = {
            "gate_rejects": 0,
            "budget_blocks": 0,
            "rollbacks": 0,
            "exec_success": 0,
            "exec_fail": 0,
            "anomalies": 0,
            "habit_hits": 0,
            "ci_failures": 0,
            "invariant_violations": 0,
        }

    def emit(self, event, data=None):
        """Write a telemetry event to the JSONL log."""
        rec = {
            "ts": time.time(),
            "event": event,
            "data": data or {},
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(rec) + "\n")

        # Update counters
        if event == "gate_reject":
            self._counters["gate_rejects"] += 1
        elif event == "budget_block":
            self._counters["budget_blocks"] += 1
        elif event == "rollback":
            self._counters["rollbacks"] += 1
        elif event == "exec":
            if data and data.get("ok"):
                self._counters["exec_success"] += 1
            else:
                self._counters["exec_fail"] += 1
        elif event == "anomaly":
            self._counters["anomalies"] += 1
        elif event == "habit_hit":
            self._counters["habit_hits"] += 1
        elif event == "ci_fail":
            self._counters["ci_failures"] += 1
        elif event == "invariant_violation":
            self._counters["invariant_violations"] += 1

    def summary(self):
        """Return current counter snapshot."""
        return dict(self._counters)
