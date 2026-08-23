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


def species_tie_key(canonical_accessions: list[str] | tuple[str, ...]) -> str:
    """Return the frozen selector-v1 species-level SHA-256 tie key."""
    accessions = list(canonical_accessions)

    if not accessions:
        raise ValueError("canonical_accessions must not be empty")

    if any(not accession for accession in accessions):
        raise ValueError("canonical_accessions must not contain empty values")

    if len(accessions) != len(set(accessions)):
        raise ValueError("canonical_accessions must be unique")

    payload = (
        "BacSelect-selector-v1|species|"
        + "\n".join(sorted(accessions))
    ).encode("utf-8")

    return hashlib.sha256(payload).hexdigest()
