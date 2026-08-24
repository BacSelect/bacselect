#!/usr/bin/env python3
"""Reference sequence primitives for Experiment 0 structural features.

These functions implement the frozen Project Finch definitions for canonical
k-mers, topology-aware source-coordinate starts, within-genome multiplicity,
and inter-replicon sharing.

They provide a transparent reference implementation for validation and small
synthetic examples. Production feature calculation over the full frozen
candidate pool will use a separately validated memory-efficient implementation
that must reproduce these reference semantics exactly.

Only A, C, G, and T sequences are accepted.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable


_DNA = frozenset("ACGT")
_COMPLEMENT = str.maketrans("ACGT", "TGCA")


@dataclass(frozen=True)
class Replicon:
    """One retained source-genome replicon."""

    name: str
    sequence: str
    topology: str

    def __post_init__(self) -> None:
        sequence = self.sequence.upper()

        if not self.name:
            raise ValueError("replicon name must not be empty")

        if self.topology not in {"circular", "linear"}:
            raise ValueError(
                f"unsupported topology: {self.topology!r}"
            )

        invalid = set(sequence) - _DNA

        if invalid:
            raise ValueError(
                "sequence contains non-ACGT symbols: "
                + ",".join(sorted(invalid))
            )

        if not sequence:
            raise ValueError("replicon sequence must not be empty")

        object.__setattr__(
            self,
            "sequence",
            sequence,
        )


def reverse_complement(sequence: str) -> str:
    """Return the reverse complement of an ACGT sequence."""

    sequence = sequence.upper()

    invalid = set(sequence) - _DNA

    if invalid:
        raise ValueError(
            "sequence contains non-ACGT symbols: "
            + ",".join(sorted(invalid))
        )

    return sequence.translate(
        _COMPLEMENT
    )[::-1]


def canonical_kmer(sequence: str) -> str:
    """Return the lexicographically smaller strand representation."""

    sequence = sequence.upper()

    rc = reverse_complement(
        sequence
    )

    return min(
        sequence,
        rc,
    )


def iter_kmer_starts(
    replicon: Replicon,
    k: int,
) -> Iterable[tuple[int, str]]:
    """Yield topology-aware source-coordinate k-mers.

    Coordinates are zero-based source start positions.

    Linear replicons contribute len(sequence) - k + 1 starts when len >= k.

    Circular replicons contribute exactly len(sequence) starts when len >= k.
    A k-mer may cross the recorded FASTA origin, but this function never
    creates artificial duplicate source-coordinate starts.
    """

    if k <= 0:
        raise ValueError("k must be positive")

    sequence = replicon.sequence
    length = len(sequence)

    if length < k:
        return

    if replicon.topology == "linear":
        for start in range(
            length - k + 1
        ):
            yield (
                start,
                sequence[start:start + k],
            )
        return

    extension = sequence + sequence[: k - 1]

    for start in range(length):
        yield (
            start,
            extension[start:start + k],
        )


def canonical_kmer_occurrences(
    replicons: Iterable[Replicon],
    k: int,
) -> dict[str, list[tuple[str, int]]]:
    """Map canonical k-mers to distinct source-coordinate occurrences."""

    occurrences: defaultdict[
        str,
        list[tuple[str, int]],
    ] = defaultdict(list)

    seen_replicon_names: set[str] = set()

    for replicon in replicons:
        if replicon.name in seen_replicon_names:
            raise ValueError(
                f"duplicate replicon name: {replicon.name!r}"
            )

        seen_replicon_names.add(
            replicon.name
        )

        for start, sequence in iter_kmer_starts(
            replicon,
            k,
        ):
            occurrences[
                canonical_kmer(sequence)
            ].append(
                (
                    replicon.name,
                    start,
                )
            )

    return dict(
        occurrences
    )


def longest_exact_repeat_reference(
    replicons: Iterable[Replicon],
) -> int:
    """Return the longest exact repeat length using reference semantics.

    This deliberately simple implementation is intended as a semantic oracle
    for synthetic and small validation examples, not for production-scale
    bacterial genomes.

    Two occurrences must have distinct source-coordinate starts. Forward and
    reverse-complement occurrences are equivalent through canonicalization.

    Linear occurrences must fit completely within the recorded sequence.
    Circular occurrences may cross the FASTA origin, but an occurrence may
    not be longer than its source replicon, so no source coordinate can be
    traversed more than once.
    """

    replicons = tuple(
        replicons
    )

    if not replicons:
        return 0

    # Validate names even if no repeat is ultimately found.
    seen_names: set[str] = set()

    for replicon in replicons:
        if replicon.name in seen_names:
            raise ValueError(
                f"duplicate replicon name: {replicon.name!r}"
            )

        seen_names.add(
            replicon.name
        )

    maximum_possible = max(
        len(replicon.sequence)
        for replicon in replicons
    )

    # Exhaustive descending search keeps the reference implementation
    # transparent and avoids relying on optimisation assumptions.
    for length in range(
        maximum_possible,
        0,
        -1,
    ):
        occurrences: defaultdict[
            str,
            list[tuple[str, int]],
        ] = defaultdict(list)

        for replicon in replicons:
            for start, sequence in iter_kmer_starts(
                replicon,
                length,
            ):
                key = canonical_kmer(
                    sequence
                )

                occurrences[key].append(
                    (
                        replicon.name,
                        start,
                    )
                )

                if len(occurrences[key]) >= 2:
                    return length

    return 0


def kmer_features(
    replicons: Iterable[Replicon],
    k: int,
) -> dict[str, int | float]:
    """Calculate the frozen k-mer structural features for one k.

    Returns:
      valid_start_count
      non_unique_start_count
      non_unique_fraction
      maximum_multiplicity
      inter_replicon_shared_start_count
      inter_replicon_shared_fraction
    """

    replicons = tuple(
        replicons
    )

    occurrences = canonical_kmer_occurrences(
        replicons,
        k,
    )

    valid_start_count = sum(
        len(coords)
        for coords in occurrences.values()
    )

    if valid_start_count == 0:
        return {
            "valid_start_count": 0,
            "non_unique_start_count": 0,
            "non_unique_fraction": 0.0,
            "maximum_multiplicity": 0,
            "inter_replicon_shared_start_count": 0,
            "inter_replicon_shared_fraction": 0.0,
        }

    multiplicities = {
        kmer: len(coords)
        for kmer, coords in occurrences.items()
    }

    non_unique_start_count = sum(
        multiplicity
        for multiplicity in multiplicities.values()
        if multiplicity > 1
    )

    maximum_multiplicity = max(
        multiplicities.values()
    )

    replicon_sets = {
        kmer: {
            replicon_name
            for replicon_name, _ in coords
        }
        for kmer, coords in occurrences.items()
    }

    inter_replicon_shared_start_count = sum(
        multiplicities[kmer]
        for kmer, names in replicon_sets.items()
        if len(names) > 1
    )

    return {
        "valid_start_count": valid_start_count,
        "non_unique_start_count": non_unique_start_count,
        "non_unique_fraction": (
            non_unique_start_count
            / valid_start_count
        ),
        "maximum_multiplicity": maximum_multiplicity,
        "inter_replicon_shared_start_count": (
            inter_replicon_shared_start_count
        ),
        "inter_replicon_shared_fraction": (
            inter_replicon_shared_start_count
            / valid_start_count
        ),
    }
