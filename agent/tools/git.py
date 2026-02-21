from .shell import run
def status():
    return run("git status --porcelain")
