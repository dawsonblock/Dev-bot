"""Health check endpoint — readiness, liveness, and deep-check probes.

Exposes HTTP endpoints for container orchestrators (k8s, Docker):
- /healthz — liveness (agent process running)
- /readyz  — readiness (all subsystems initialized)
- /deepz   — deep check (ledger valid, invariants hold, bounds within limits)
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler


class HealthState:
    """Shared state for health probes."""

    def __init__(self):
        self.alive = True
        self.ready = False
        self.checks = {}

    def set_ready(self, ready=True):
        self.ready = ready

    def update_check(self, name, passed, detail=""):
        self.checks[name] = {"passed": passed, "detail": detail}

    def deep_check(self):
        """Returns (all_ok, details)."""
        all_ok = all(c["passed"] for c in self.checks.values())
        return all_ok, dict(self.checks)


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for health endpoints."""

    health_state = None  # Set by start_health_server

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        hs = self.__class__.health_state

        if self.path == "/healthz":
            self._respond(200 if hs.alive else 503, {"alive": hs.alive})

        elif self.path == "/readyz":
            self._respond(200 if hs.ready else 503, {"ready": hs.ready})

        elif self.path == "/deepz":
            ok, checks = hs.deep_check()
            self._respond(200 if ok else 503, {"ok": ok, "checks": checks})

        else:
            self._respond(404, {"error": "not_found"})

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


def start_health_server(state, port=8080):
    """Start the health server in a background daemon thread.

    Args:
        state: HealthState instance
        port: HTTP port

    Returns:
        (server, thread)
    """
    HealthHandler.health_state = state
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
