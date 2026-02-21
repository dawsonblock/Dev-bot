from .shell import run


def run_tests():
    res = run("python tests/replay_tests.py")
    return {"ok": res["rc"] == 0, "summary": res["out"][:200]}
