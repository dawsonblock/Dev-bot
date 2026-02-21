"""Capability-scoped permission graph with cryptographic tokens."""

import hashlib
import json
import time


class Capability:
    """A named, scoped, expirable permission."""

    def __init__(self, name, scope, level=1, expiry=None):
        self.name = name
        self.scope = scope
        self.level = level
        self.expiry = expiry  # Unix timestamp or None (no expiry)

    def expired(self):
        if self.expiry is None:
            return False
        return time.time() > self.expiry

    def to_dict(self):
        return {
            "name": self.name,
            "scope": self.scope,
            "level": self.level,
            "expiry": self.expiry,
        }


class CapabilityToken:
    """Cryptographically signed capability token."""

    def __init__(self, capability, secret):
        self.capability = capability
        self.payload = capability.to_dict()
        blob = json.dumps(self.payload, sort_keys=True).encode()
        self.signature = hashlib.sha256(secret + blob).hexdigest()

    def verify(self, secret):
        """Verify token signature."""
        blob = json.dumps(self.payload, sort_keys=True).encode()
        expected = hashlib.sha256(secret + blob).hexdigest()
        return expected == self.signature


class CapabilityGraph:
    """Registry of granted capabilities."""

    def __init__(self):
        self.capabilities = {}

    def grant(self, capability):
        """Grant a capability."""
        self.capabilities[capability.name] = capability

    def revoke(self, name):
        """Revoke a capability by name."""
        self.capabilities.pop(name, None)

    def check(self, tool_name):
        """Check if a tool has a valid (non-expired) capability grant."""
        cap = self.capabilities.get(tool_name)
        if cap is None:
            return False, "no_capability"
        if cap.expired():
            return False, "capability_expired"
        return True, "ok"

    def list_active(self):
        """List all non-expired capabilities."""
        return {
            name: cap.to_dict()
            for name, cap in self.capabilities.items()
            if not cap.expired()
        }
