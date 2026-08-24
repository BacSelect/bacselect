#!/usr/bin/env python3
"""Exact sequence-derived structural features 1-5 for FINCH Experiment 0.

Chromosomal classification is supplied from the frozen NCBI
assignedMoleculeLocationType field. Sequence-derived quantities are calculated
from the exact retained nucleotide sequences rather than rounded NCBI summary
statistics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ClassifiedReplicon:
    name: str
    sequence: str
    topology: str
    molecule_location_type: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                "replicon name must not be empty"
            )

        sequence = self.sequence.upper()

        if not sequence:
            raise ValueError(
                f"{self.name}: sequence must not be empty"
            )

        invalid = sorted(
            set(sequence) - set("ACGT")
        )

        if invalid:
            raise ValueError(
                f"{self.name}: sequence contains "
                f"non-ACGT symbols: {''.join(invalid)}"
            )

        if self.topology not in {
            "linear",
            "circular",
        }:
            raise ValueError(
                f"{self.name}: unsupported topology: "
                f"{self.topology}"
            )

        if not self.molecule_location_type:
            raise ValueError(
                f"{self.name}: molecule location type "
                "must not be empty"
            )

        object.__setattr__(
            self,
            "sequence",
            sequence,
        )


def basic_structural_features(
    replicons: Iterable[ClassifiedReplicon],
) -> dict[str, int | float]:
    replicons = tuple(
        replicons
    )

    if not replicons:
        raise ValueError(
            "at least one retained replicon is required"
        )

    names = [
        replicon.name
        for replicon in replicons
    ]

    if len(names) != len(set(names)):
        raise ValueError(
            "replicon names must be unique"
        )

    total_length = sum(
        len(replicon.sequence)
        for replicon in replicons
    )

    gc_count = sum(
        replicon.sequence.count("G")
        + replicon.sequence.count("C")
        for replicon in replicons
    )

    non_chromosomal = tuple(
        replicon
        for replicon in replicons
        if replicon.molecule_location_type
        != "Chromosome"
    )

    non_chromosomal_length = sum(
        len(replicon.sequence)
        for replicon in non_chromosomal
    )

    plasmids = tuple(
        replicon
        for replicon in replicons
        if replicon.molecule_location_type
        == "Plasmid"
    )

    plasmid_length = sum(
        len(replicon.sequence)
        for replicon in plasmids
    )

    return {
        "total_genome_length": total_length,
        "whole_genome_gc_fraction": (
            gc_count / total_length
        ),
        "replicon_count": len(replicons),
        "non_chromosomal_replicon_count": (
            len(non_chromosomal)
        ),
        "non_chromosomal_sequence_fraction": (
            non_chromosomal_length
            / total_length
        ),
        # Descriptive metadata, not additional selection features.
        "plasmid_count": len(plasmids),
        "plasmid_sequence_length": plasmid_length,
    }
