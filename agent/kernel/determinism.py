"""Determinism envelope — global seed, logical tick clock, config fingerprint."""

import os
import random
import hashlib
import json

GLOBAL_SEED = None
TICK = 0
WALL_ORIGIN = None


def init_determinism(seed=1337):
    """Initialize global determinism. Must be called before anything else."""
    global GLOBAL_SEED, TICK, WALL_ORIGIN
    GLOBAL_SEED = seed
    TICK = 0

    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass


def next_tick():
    """Advance and return the global logical tick."""
    global TICK
    TICK += 1
    return TICK


def get_tick():
    """Return the current logical tick without advancing."""
    return TICK


def config_hash(*config_dicts):
    """Produce a stable SHA-256 fingerprint of one or more config dicts."""
    blob = b""
    for d in config_dicts:
        blob += json.dumps(d, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def genesis_record(seed, cfg_hash, code_hash):
    """Build the genesis ledger record written on first boot."""
    return {
        "event": "genesis",
        "seed": seed,
        "config_hash": cfg_hash,
        "code_hash": code_hash,
        "determinism": True,
    }
