"""HSM/TPM key management abstraction — pluggable signing backends.

Provides hardware-backed signing when available, with automatic
fallback to software HMAC. The interface is uniform regardless of backend.

Backends:
- SoftwareHSM: HMAC-SHA256 with in-memory key (default/testing)
- HardwareHSM: PKCS#11 interface (production, requires hardware)
"""

import hashlib
import hmac
import os
import time


class HSMError(Exception):
    """Raised on HSM operation failure."""

    pass


class SoftwareHSM:
    """Software-only HSM fallback using HMAC-SHA256.

    Uses a file-persisted or environment-sourced key.
    Suitable for development and single-node deployment.
    """

    def __init__(self, key=None, key_file=None):
        if key:
            self._key = key.encode() if isinstance(key, str) else key
        elif key_file and os.path.exists(key_file):
            with open(key_file, "rb") as f:
                self._key = f.read()
        else:
            self._key = os.environ.get(
                "DEVBOT_DEVICE_KEY", "devbot-default-key-change-me"
            ).encode()

        self.backend = "software"
        self.key_id = hashlib.sha256(self._key).hexdigest()[:16]

    def sign(self, data):
        """Sign data with HMAC-SHA256.

        Args:
            data: bytes to sign

        Returns:
            hex string signature
        """
        if isinstance(data, str):
            data = data.encode()
        return hmac.new(self._key, data, hashlib.sha256).hexdigest()

    def verify(self, data, signature):
        """Verify a signature.

        Returns:
            bool
        """
        if isinstance(data, str):
            data = data.encode()
        expected = self.sign(data)
        return hmac.compare_digest(expected, signature)

    def generate_key(self, label="devbot"):
        """Generate and store a new random key."""
        self._key = os.urandom(32)
        self.key_id = hashlib.sha256(self._key).hexdigest()[:16]
        return self.key_id

    def export_public_info(self):
        """Export non-secret key metadata."""
        return {
            "backend": self.backend,
            "key_id": self.key_id,
            "algorithm": "HMAC-SHA256",
        }


class HardwareHSM:
    """Hardware HSM interface stub (PKCS#11).

    In production, this connects to a real HSM/TPM device.
    This stub provides the interface for future hardware integration.
    """

    def __init__(self, slot=0, pin=None, library_path=None):
        self.backend = "hardware"
        self.slot = slot
        self._available = False
        self.key_id = "hw-not-initialized"

        # Attempt to load PKCS#11 library
        try:
            if library_path:
                # In production: load the PKCS#11 shared library
                self._available = True
                self.key_id = f"hw-slot{slot}"
        except Exception:
            self._available = False

    @property
    def available(self):
        return self._available

    def sign(self, data):
        """Sign using hardware key."""
        if not self._available:
            raise HSMError("Hardware HSM not available")
        # Placeholder for PKCS#11 C_Sign
        raise HSMError("Hardware signing not implemented — use SoftwareHSM fallback")

    def verify(self, data, signature):
        """Verify using hardware key."""
        if not self._available:
            raise HSMError("Hardware HSM not available")
        raise HSMError(
            "Hardware verification not implemented — use SoftwareHSM fallback"
        )

    def export_public_info(self):
        return {
            "backend": self.backend,
            "available": self._available,
            "slot": self.slot,
        }


def create_hsm(prefer_hardware=False, **kwargs):
    """Factory: create the best available HSM backend.

    Tries hardware first if requested, falls back to software.
    """
    if prefer_hardware:
        hw = HardwareHSM(**kwargs)
        if hw.available:
            return hw

    return SoftwareHSM(**kwargs)
