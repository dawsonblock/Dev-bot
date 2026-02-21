import subprocess
import shlex


def run(cmd, timeout=10):
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
