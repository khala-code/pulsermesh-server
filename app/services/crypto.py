"""
app/services/crypto.py — Cryptographic Agility Layer

All hash operations in Pulser Mesh are routed through this module.
No call site should import hashlib directly.  Swap the algorithm here
and every downstream caller inherits the change automatically.

Current default: SHA-256.
Upgrade path: set HASH_ALGORITHM = "sha3_256" or "blake2b" and
re-run; or add a post-quantum wrapper in _get_hasher().

See docs/architecture.md § Principle 7 — Cryptographic Agility.
"""
import hashlib
from typing import Literal

# ── algorithm selector ─────────────────────────────────────────────
# Change this string (or wire it to an env var) to swap primitives.
HASH_ALGORITHM: str = "sha256"

# Supported algorithms for static validation at startup.
SUPPORTED_ALGORITHMS = frozenset([
    "sha256",
    "sha3_256",
    "sha3_512",
    "blake2b",
    "blake2s",
])


def _get_hasher() -> "hashlib._Hash":
    """Return a fresh hasher for the configured algorithm."""
    if HASH_ALGORITHM not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported hash algorithm '{HASH_ALGORITHM}'. "
            f"Supported: {sorted(SUPPORTED_ALGORITHMS)}"
        )
    return hashlib.new(HASH_ALGORITHM)


def digest(data: str) -> str:
    """
    Hash a plain string and return a hex digest.

    Use for checkpoint hashes and any unauthenticated structural hash.
    """
    h = _get_hasher()
    h.update(data.encode())
    return h.hexdigest()


def keyed_digest(data: str, key: str) -> str:
    """
    Hash a plain string with a secret key appended.

    Use for steward key derivation and any MAC-like operation.
    The key is appended (not HMAC), which is sufficient for key
    derivation where the key material is a high-entropy API secret.
    Upgrade to hmac.new() if a proper MAC is later required.
    """
    h = _get_hasher()
    h.update(f"{data}|{key}".encode())
    return h.hexdigest()


def assert_algorithm_available() -> None:
    """
    Call at application startup to fail fast if the configured
    algorithm is unavailable in this Python build.
    """
    try:
        _get_hasher()
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(
            f"Configured hash algorithm '{HASH_ALGORITHM}' is not "
            f"available: {exc}"
        ) from exc
