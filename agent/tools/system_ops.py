"""Constrained system operations — replaces freeform shell.py.

Only allowlisted commands with strict argument parsing.
No arbitrary shell execution.
"""

import subprocess
import shlex

sandbox_instance = None


def set_sandbox(sb):
    global sandbox_instance
    sandbox_instance = sb


def _run_cmd(cmd_list, timeout=10, limit=500):
    if sandbox_instance:
        res = sandbox_instance.execute(cmd_list, timeout=timeout)
        success = res["rc"] == 0
        return {
            "ok": success,
            "rc": res["rc"],
            "stdout": res["out"][:limit],
            "stderr": res["err"][:limit],
        }
    else:
        try:
            p = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "ok": p.returncode == 0,
                "rc": p.returncode,
                "stdout": p.stdout[:limit],
                "stderr": p.stderr[:limit],
            }
        except Exception as e:
            return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


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
            return _run_cmd(["systemctl", "restart", svc], timeout=30, limit=500)
        except Exception as e:
            return {"ok": False, "rc": -1, "stdout": "", "stderr": str(e)}


class HealthCheck:
    name = "run_healthcheck"

    @staticmethod
    def run(args):
        url = args.get("url", "http://localhost/")
        try:
            cmd = ["curl", "-s", "-f", "-o", "/dev/null", "-w", "%{http_code}", url]
            return _run_cmd(cmd, timeout=10, limit=500)
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
            cmd = ["journalctl", "-u", svc, "-n", str(lines), "--no-pager"]
            return _run_cmd(cmd, timeout=10, limit=2000)
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
            return _run_cmd(shlex.split(cmd), timeout=120, limit=2000)
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
