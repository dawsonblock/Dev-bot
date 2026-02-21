"""Code + config integrity fingerprinting.

Hashes all Python source and config at boot.
Logged in the genesis record for tamper detection.
"""

import hashlib
import pathlib


def hash_codebase(root="agent"):
    """SHA-256 hash of all .py files under root, in sorted order."""
    h = hashlib.sha256()
    root_path = pathlib.Path(root)
    for p in sorted(root_path.rglob("*.py")):
        h.update(p.read_bytes())
    return h.hexdigest()


def hash_configs(root="agent/config"):
    """SHA-256 hash of all config files under root."""
    h = hashlib.sha256()
    root_path = pathlib.Path(root)
    for p in sorted(root_path.rglob("*")):
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


def full_integrity_hash(code_root="agent", config_root="agent/config"):
    """Combined integrity fingerprint of code + config."""
    code = hash_codebase(code_root)
    cfg = hash_configs(config_root)
    return hashlib.sha256((code + cfg).encode()).hexdigest()
