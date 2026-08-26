"""Topology-aware sequence fingerprints for BacSelect source reconciliation.

This module implements the frozen
project-finch-topology-aware-sequence-v1 semantics.

It performs no acquisition, metadata eligibility, taxonomy resolution,
baseline comparison, structural-feature calculation, or selector analysis.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable


FINGERPRINT_SCHEMA = "project-finch-topology-aware-sequence-v1"
SUPPORTED_TOPOLOGIES = frozenset({"linear", "circular"})
DNA_ALPHABET = frozenset("ACGT")


def normalize_sequence(sequence: str) -> str:
    """Return an uppercase unambiguous DNA sequence, failing closed."""

    if not isinstance(sequence, str):
        raise TypeError("sequence must be a string")

    normalized = sequence.upper()

    if not normalized:
        raise ValueError("sequence must not be empty")

    invalid = set(normalized) - DNA_ALPHABET

    if invalid:
        raise ValueError(
            f"sequence contains unsupported symbols: {sorted(invalid)!r}"
        )

    return normalized


def sha256_text(text: str) -> str:
    """Return SHA256 of ASCII text."""

    return hashlib.sha256(text.encode("ascii")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    """Return SHA256 of bytes."""

    return hashlib.sha256(payload).hexdigest()


def reverse_complement(sequence: str) -> str:
    """Return reverse complement of validated DNA."""

    sequence = normalize_sequence(sequence)

    return sequence.translate(
        str.maketrans("ACGT", "TGCA")
    )[::-1]


def minimal_rotation(sequence: str) -> str:
    """Return the lexicographically minimal circular rotation in O(n)."""

    sequence = normalize_sequence(sequence)
    n = len(sequence)

    if n <= 1:
        return sequence

    doubled = sequence + sequence

    i = 0
    j = 1
    k = 0

    while i < n and j < n and k < n:
        left = doubled[i + k]
        right = doubled[j + k]

        if left == right:
            k += 1
            continue

        if left > right:
            i = i + k + 1

            if i <= j:
                i = j + 1
        else:
            j = j + k + 1

            if j <= i:
                j = i + 1

        k = 0

    start = min(i, j)

    return doubled[start:start + n]


def canonical_linear(sequence: str) -> str:
    """Canonicalize a linear sequence over strand orientation."""

    sequence = normalize_sequence(sequence)
    reverse = reverse_complement(sequence)

    return min(
        sequence,
        reverse,
    )


def canonical_circular(sequence: str) -> str:
    """Canonicalize a circular sequence over origin and strand orientation."""

    sequence = normalize_sequence(sequence)

    forward = minimal_rotation(sequence)

    reverse = minimal_rotation(
        reverse_complement(sequence)
    )

    return min(
        forward,
        reverse,
    )


def canonical_replicon(
    sequence: str,
    topology: str,
) -> str:
    """Canonicalize one replicon under the frozen topology-aware rules."""

    if topology == "linear":
        return canonical_linear(sequence)

    if topology == "circular":
        return canonical_circular(sequence)

    raise ValueError(
        f"unsupported topology: {topology!r}"
    )


def component_sequence_hash(
    sequence: str,
    topology: str,
) -> str:
    """Return canonical sequence SHA256 for one component."""

    return sha256_text(
        canonical_replicon(
            sequence,
            topology,
        )
    )


def assembly_fingerprint(
    topology_hash_pairs: Iterable[tuple[str, str]],
) -> str:
    """Return deterministic assembly fingerprint from topology/hash pairs."""

    pairs = []

    for topology, sequence_hash in topology_hash_pairs:
        if topology not in SUPPORTED_TOPOLOGIES:
            raise ValueError(
                f"unsupported topology: {topology!r}"
            )

        if (
            not isinstance(sequence_hash, str)
            or len(sequence_hash) != 64
            or any(
                symbol not in "0123456789abcdef"
                for symbol in sequence_hash
            )
        ):
            raise ValueError(
                "component sequence hash must be lowercase SHA256"
            )

        pairs.append(
            [
                topology,
                sequence_hash,
            ]
        )

    if not pairs:
        raise ValueError(
            "assembly fingerprint requires at least one component"
        )

    ordered = sorted(pairs)

    payload = json.dumps(
        ordered,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")

    return sha256_bytes(payload)


def fingerprint_components(
    components: Iterable[tuple[str, str]],
) -> str:
    """Fingerprint an iterable of ``(topology, sequence)`` components."""

    pairs = [
        (
            topology,
            component_sequence_hash(
                sequence,
                topology,
            ),
        )
        for topology, sequence in components
    ]

    return assembly_fingerprint(pairs)
