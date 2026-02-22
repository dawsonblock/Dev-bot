import subprocess
import shlex

sandbox_instance = None


def set_sandbox(sb):
    global sandbox_instance
    sandbox_instance = sb


def run(cmd, timeout=10):
    if sandbox_instance:
        return sandbox_instance.execute(cmd, timeout=timeout)
    try:
        p = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}
    except Exception as e:
        return {"rc": -1, "out": "", "err": str(e)}
