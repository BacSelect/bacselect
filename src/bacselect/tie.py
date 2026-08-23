"""Identity-neutral deterministic tie-breaking."""

from __future__ import annotations

import hashlib


_TIE_NAMESPACE = "BacSelect-selector-v1|"


def tie_key(canonical_accession: str) -> str:
    """Return the frozen selector-v1 SHA-256 tie key."""
    if not canonical_accession:
        raise ValueError("canonical_accession must not be empty")

    payload = f"{_TIE_NAMESPACE}{canonical_accession}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
