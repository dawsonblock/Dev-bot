import os
import time
import docker


class DockerSandbox:
    """Provides an isolated execution environment using Docker."""

    def __init__(self, workdir="/tmp/devbot-workdir"):
        self.workdir = os.path.abspath(workdir)
        os.makedirs(self.workdir, exist_ok=True)
        self.client = docker.from_env()
        self.container = None

    def start(self, image="python:3.9-slim", network_disabled=True, mem_limit="512m"):
        """Start the sandbox container."""
        self.stop()

        volumes = {self.workdir: {"bind": "/workspace", "mode": "rw"}}

        # Start a sleeping container that we can exec into
        self.container = self.client.containers.run(
            image,
            command="tail -f /dev/null",
            detach=True,
            network_disabled=network_disabled,
            mem_limit=mem_limit,
            volumes=volumes,
            working_dir="/workspace",
            name=f"devbot-sandbox-{int(time.time())}",
            auto_remove=True,
        )

    def execute(self, cmd, timeout=10):
        """Execute a command inside the sandbox."""
        if not self.container:
            raise RuntimeError("Sandbox not started")

        try:
            # Note: The docker SDK's exec_run doesn't natively support hard timeouts easily.
            # For a production system this would use a wrapped thread or API timeouts.
            exit_code, output = self.container.exec_run(
                cmd=cmd, workdir="/workspace", demux=True
            )
            stdout, stderr = output if output else (b"", b"")

            return {
                "rc": exit_code,
                "out": stdout.decode("utf-8", errors="replace") if stdout else "",
                "err": stderr.decode("utf-8", errors="replace") if stderr else "",
            }
        except Exception as e:
            return {"rc": -1, "out": "", "err": str(e)}

    def stop(self):
        """Stop and remove the sandbox container."""
        if self.container:
            try:
                self.container.stop(timeout=1)
            except Exception:
                pass
            self.container = None
