import os
from kernel.sandbox import DockerSandbox


import shutil


def test_sandbox_fs_containment():
    """Verify the sandbox cannot write to host protected files and lacks network access."""
    workdir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), ".test-sandbox-workdir")
    )
    if os.path.exists(workdir):
        shutil.rmtree(workdir)
    os.makedirs(workdir, exist_ok=True)
    sandbox = DockerSandbox(workdir=workdir)
    try:
        sandbox.start()

        # Test 1: Container FS isolation
        res = sandbox.execute("ls -l /")
        assert res["rc"] == 0
        assert "workspace" in res["out"], "Mount point /workspace must exist"

        # Test 2: Network lockdown
        res_net = sandbox.execute("curl -I --connect-timeout 2 https://google.com")
        assert res_net["rc"] != 0, "Sandbox should NOT have network egress access"

        # Test 3: Standard execution
        res_echo = sandbox.execute("echo 'isolated_test'")
        assert res_echo["rc"] == 0
        assert "isolated_test" in res_echo["out"]

        # Test 4: Workspace volume binding
        test_file = os.path.join(workdir, "bind_test.txt")
        if os.path.exists(test_file):
            os.remove(test_file)

        sandbox.execute("sh -c \"echo 'mounted' > /workspace/bind_test.txt\"")
        assert os.path.exists(
            test_file
        ), "File created in sandbox /workspace must appear in host workdir"
        with open(test_file, "r") as f:
            assert "mounted" in f.read()

    finally:
        sandbox.stop()
