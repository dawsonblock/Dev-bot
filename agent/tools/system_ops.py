"""Constrained system operations — replaces freeform shell.py.

Only allowlisted commands with strict argument parsing.
No arbitrary shell execution.
"""

import subprocess
import shlex


class RestartService:
    name = "restart_service"

    @staticmethod
    def run(args):
        svc = args.get("service") or args.get("name", "")
        if not svc:
            return {
                "ok": False,
                "error": "missing_service",
                "rc": -1,
                "stdout": "",
                "stderr": "",
            }
        try:
            p = subprocess.run(
                ["systemctl", "restart", svc],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "stdout": p.stdout[:500],
                "stderr": p.stderr[:500],
            }
        except Exception as e:
            return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


class HealthCheck:
    name = "run_healthcheck"

    @staticmethod
    def run(args):
        url = args.get("url", "http://localhost/")
        try:
            p = subprocess.run(
                ["curl", "-s", "-f", "-o", "/dev/null", "-w", "%{http_code}", url],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "stdout": p.stdout[:500],
                "stderr": p.stderr[:500],
            }
        except Exception as e:
            return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


class GetLogs:
    name = "get_logs"

    @staticmethod
    def run(args):
        svc = args.get("service") or args.get("name", "")
        lines = args.get("lines", 50)
        if not svc:
            return {
                "ok": False,
                "error": "missing_service",
                "rc": -1,
                "stdout": "",
                "stderr": "",
            }
        try:
            p = subprocess.run(
                ["journalctl", "-u", svc, "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "stdout": p.stdout[:2000],
                "stderr": p.stderr[:500],
            }
        except Exception as e:
            return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


class RunCI:
    name = "run_ci"

    @staticmethod
    def run(args):
        cmd = args.get("cmd", "python tests/replay_tests.py")
        # Only allow known CI commands
        allowed_prefixes = ["python tests/", "pytest", "make test"]
        if not any(cmd.startswith(p) for p in allowed_prefixes):
            return {
                "ok": False,
                "error": "ci_command_not_allowed",
                "rc": -1,
                "stdout": "",
                "stderr": "",
            }
        try:
            p = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "stdout": p.stdout[:2000],
                "stderr": p.stderr[:500],
            }
        except Exception as e:
            return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


class Noop:
    name = "noop"

    @staticmethod
    def run(args):
        return {"ok": True, "rc": 0, "stdout": "", "stderr": ""}


# Registry of all allowed tool implementations
TOOL_REGISTRY = {
    "restart_service": RestartService,
    "run_healthcheck": HealthCheck,
    "get_logs": GetLogs,
    "run_ci": RunCI,
    "noop": Noop,
}


def get_tool(name):
    """Look up a tool by name. Returns None if not registered."""
    return TOOL_REGISTRY.get(name)
