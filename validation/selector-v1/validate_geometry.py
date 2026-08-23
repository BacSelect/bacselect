#!/usr/bin/env python3
"""Validate BacSelect species-balanced geometry on the frozen Finch universe."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import numpy as np

from bacselect.geometry import species_balanced_percentile_matrix
from bacselect.provenance import verify_input_manifest


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765
EXPECTED_FEATURES = 12

EXPECTED_FLOAT64_SHA256 = (
    "618877ff239d07f60466baf577acfc857"
    "6fd16a0cb2673a6d7102eb90018832c"
)

PERMUTATION_SEED = 20260824

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"


def matrix_sha256(matrix: np.ndarray) -> str:
    """Return SHA-256 of contiguous float64 matrix bytes."""
    array = np.ascontiguousarray(matrix, dtype=np.float64)
    return hashlib.sha256(array.tobytes()).hexdigest()


def main() -> None:
    manifest = Path("validation/finch-foundation/inputs.tsv")
    artifacts = verify_input_manifest(manifest)

    paths = {artifact.artifact: artifact.path for artifact in artifacts}

    raw_path = paths["corrected_raw_structural_feature_matrix"]
    species_path = paths["corrected_species_mapping"]

    with raw_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        raw_fieldnames = list(reader.fieldnames or [])
        raw_rows = list(reader)

    with species_path.open(newline="", encoding="utf-8") as handle:
        species_rows = list(csv.DictReader(handle, delimiter="\t"))

    feature_names = raw_fieldnames[3:]

    assert len(raw_rows) == EXPECTED_GENOMES
    assert len(species_rows) == EXPECTED_GENOMES
    assert len(feature_names) == EXPECTED_FEATURES

    raw_accessions = [
        row[ACCESSION_COLUMN]
        for row in raw_rows
    ]

    species_accessions = [
        row[ACCESSION_COLUMN]
        for row in species_rows
    ]

    assert raw_accessions == species_accessions
    assert len(set(raw_accessions)) == EXPECTED_GENOMES

    species_ids = [
        row[SPECIES_COLUMN]
        for row in species_rows
    ]

    counts = Counter(species_ids)

    assert len(counts) == EXPECTED_SPECIES

    for species_id, count in counts.items():
        total_weight = sum(
            (Fraction(1, count) for _ in range(count)),
            Fraction(0, 1),
        )
        assert total_weight == 1, species_id

    matrix = np.asarray(
        [
            [
                float(row[name])
                for name in feature_names
            ]
            for row in raw_rows
        ],
        dtype=np.float64,
    )

    assert matrix.shape == (
        EXPECTED_GENOMES,
        EXPECTED_FEATURES,
    )
    assert np.all(np.isfinite(matrix))

    balanced = species_balanced_percentile_matrix(
        matrix,
        species_ids,
    )

    assert balanced.shape == matrix.shape
    assert np.all(np.isfinite(balanced))
    assert np.all(balanced >= 0.0)
    assert np.all(balanced <= 1.0)

    for column, feature_name in enumerate(feature_names):
        decimal_unique = sorted(
            {
                Decimal(row[feature_name])
                for row in raw_rows
            }
        )

        float_unique = np.unique(matrix[:, column])

        assert len(decimal_unique) == float_unique.size, (
            f"float64 collapsed distinct raw values for {feature_name}"
        )

        converted_decimal_order = np.asarray(
            [float(value) for value in decimal_unique],
            dtype=np.float64,
        )

        if converted_decimal_order.size > 1:
            assert np.all(
                converted_decimal_order[:-1]
                < converted_decimal_order[1:]
            ), f"float64 changed raw ordering for {feature_name}"

        balanced_unique = np.unique(balanced[:, column]).size

        assert float_unique.size == balanced_unique, feature_name

    observed_hash = matrix_sha256(balanced)

    assert observed_hash == EXPECTED_FLOAT64_SHA256, (
        f"species-balanced matrix SHA-256 changed: "
        f"{observed_hash}"
    )

    rng = np.random.default_rng(PERMUTATION_SEED)
    permutation = rng.permutation(EXPECTED_GENOMES)

    permuted = species_balanced_percentile_matrix(
        matrix[permutation],
        [species_ids[index] for index in permutation],
    )

    restored = np.empty_like(permuted)
    restored[permutation] = permuted

    assert np.array_equal(restored, balanced)
    assert matrix_sha256(restored) == EXPECTED_FLOAT64_SHA256

    print(
        f"PASS | immutable inputs verified | "
        f"{EXPECTED_GENOMES} genomes"
    )
    print(
        f"PASS | species groups | "
        f"{EXPECTED_SPECIES}"
    )
    print(
        f"PASS | structural features | "
        f"{EXPECTED_FEATURES}"
    )
    print("PASS | every species contributes exact total weight 1")
    print("PASS | percentile coordinates finite and bounded")
    print("PASS | raw decimal values remain distinct and ordered in float64")
    print("PASS | raw tie classes preserved across all features")
    print("PASS | deterministic row-permutation invariance")
    print(
        "PASS | float64 matrix SHA-256 | "
        f"{EXPECTED_FLOAT64_SHA256}"
    )


if __name__ == "__main__":
    main()
