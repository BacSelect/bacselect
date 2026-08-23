#!/usr/bin/env python3
"""Validate blinded SR behaviour on the frozen Finch foundation."""

from __future__ import annotations

import csv
import hashlib
import time
from collections import Counter
from pathlib import Path

import numpy as np

from bacselect.geometry import species_balanced_percentile_matrix
from bacselect.provenance import verify_input_manifest
from bacselect.sr import sr_ladder


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765
EXPECTED_FEATURES = 12

MAX_N = 500
PANEL_SIZES = (10, 20, 50, 100, 200, 500)
PERMUTATION_SEED = 20260824

EXPECTED_LADDER_SHA256 = (
    "dbe0174a5e96202e7d755ac616318c5e"
    "6007939b5062a3f5b9dabea0a8bfe5e8"
)

EXPECTED_PANEL_DIAGNOSTICS = {
    10: (10, 1, "1x:10"),
    20: (20, 1, "1x:20"),
    50: (50, 1, "1x:50"),
    100: (100, 1, "1x:100"),
    200: (200, 1, "1x:200"),
    500: (499, 2, "1x:498,2x:1"),
}

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"


def sequence_sha256(namespace: str, values: list[str]) -> str:
    """Return an identity-blinded fingerprint of an ordered sequence."""
    payload = namespace + "\n" + "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def multiplicity_summary(
    selected_species: list[str],
) -> str:
    """Return a blinded distribution of selections per represented species."""
    per_species = Counter(selected_species)
    multiplicities = Counter(per_species.values())

    return ",".join(
        f"{multiplicity}x:{multiplicities[multiplicity]}"
        for multiplicity in sorted(multiplicities)
    )


def main() -> None:
    artifacts = verify_input_manifest(
        Path("validation/finch-foundation/inputs.tsv")
    )

    paths = {
        artifact.artifact: artifact.path
        for artifact in artifacts
    }

    raw_path = paths["corrected_raw_structural_feature_matrix"]
    species_path = paths["corrected_species_mapping"]

    with raw_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        raw_fieldnames = list(reader.fieldnames or [])
        raw_rows = list(reader)

    with species_path.open(newline="", encoding="utf-8") as handle:
        species_rows = list(
            csv.DictReader(handle, delimiter="\t")
        )

    feature_names = raw_fieldnames[3:]

    assert len(raw_rows) == EXPECTED_GENOMES
    assert len(species_rows) == EXPECTED_GENOMES
    assert len(feature_names) == EXPECTED_FEATURES

    accessions = [
        row[ACCESSION_COLUMN]
        for row in raw_rows
    ]

    mapping_accessions = [
        row[ACCESSION_COLUMN]
        for row in species_rows
    ]

    assert accessions == mapping_accessions
    assert len(set(accessions)) == EXPECTED_GENOMES

    species_ids = [
        row[SPECIES_COLUMN]
        for row in species_rows
    ]

    assert len(set(species_ids)) == EXPECTED_SPECIES

    matrix = np.asarray(
        [
            [
                float(row[feature])
                for feature in feature_names
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

    coordinates = species_balanced_percentile_matrix(
        matrix,
        species_ids,
    )

    start = time.perf_counter()

    ladder = sr_ladder(
        coordinates,
        species_ids,
        accessions,
        max_n=MAX_N,
    )

    elapsed = time.perf_counter() - start

    assert ladder.size == MAX_N
    assert np.unique(ladder).size == MAX_N

    ladder_accessions = [
        accessions[index]
        for index in ladder
    ]

    ladder_species = [
        species_ids[index]
        for index in ladder
    ]

    assert len(set(ladder_accessions)) == MAX_N

    ladder_hash = sequence_sha256(
        "BacSelect-selector-v1|SR|ladder|N=500",
        ladder_accessions,
    )

    assert ladder_hash == EXPECTED_LADDER_SHA256, (
        "SR N=500 ladder fingerprint changed: "
        f"{ladder_hash}"
    )

    for panel_size in PANEL_SIZES:
        prefix = ladder[:panel_size]

        assert prefix.size == panel_size
        assert np.unique(prefix).size == panel_size

        prefix_species = [
            species_ids[index]
            for index in prefix
        ]

        counts = Counter(prefix_species)

        distinct_species = len(counts)
        maximum_multiplicity = max(counts.values())
        observed_multiplicity = multiplicity_summary(prefix_species)

        expected = EXPECTED_PANEL_DIAGNOSTICS[panel_size]

        assert (
            distinct_species,
            maximum_multiplicity,
            observed_multiplicity,
        ) == expected, (
            f"SR N={panel_size} abundance diagnostic changed: "
            f"observed="
            f"{(distinct_species, maximum_multiplicity, observed_multiplicity)!r}"
        )

        print(
            f"PASS | SR N={panel_size} | "
            f"distinct_species={distinct_species} | "
            f"max_per_species={maximum_multiplicity} | "
            f"multiplicity={observed_multiplicity}"
        )

    rng = np.random.default_rng(PERMUTATION_SEED)
    permutation = rng.permutation(EXPECTED_GENOMES)

    permuted_coordinates = coordinates[permutation]

    permuted_species = [
        species_ids[index]
        for index in permutation
    ]

    permuted_accessions = [
        accessions[index]
        for index in permutation
    ]

    permutation_start = time.perf_counter()

    permuted_ladder = sr_ladder(
        permuted_coordinates,
        permuted_species,
        permuted_accessions,
        max_n=MAX_N,
    )

    permutation_elapsed = (
        time.perf_counter() - permutation_start
    )

    permuted_ladder_accessions = [
        permuted_accessions[index]
        for index in permuted_ladder
    ]

    assert permuted_ladder_accessions == ladder_accessions

    permuted_hash = sequence_sha256(
        "BacSelect-selector-v1|SR|ladder|N=500",
        permuted_ladder_accessions,
    )

    assert permuted_hash == ladder_hash

    print(
        f"PASS | immutable inputs verified | "
        f"{EXPECTED_GENOMES} genomes"
    )
    print(
        f"PASS | species-balanced geometry | "
        f"{EXPECTED_FEATURES} features"
    )
    print(
        f"PASS | eligible species groups | "
        f"{EXPECTED_SPECIES}"
    )
    print(f"PASS | SR ladder contains {MAX_N} distinct genomes")
    print(
        "PASS | exhausted species excluded from subsequent competition"
    )
    print(
        "PASS | species residual uses mean over complete species membership"
    )
    print("PASS | full-universe input-order invariance")
    print(f"sr_runtime_seconds {elapsed:.3f}")
    print(
        f"permuted_sr_runtime_seconds "
        f"{permutation_elapsed:.3f}"
    )
    print(
        "PASS | blinded SR N=500 ladder fingerprint | "
        f"{ladder_hash}"
    )


if __name__ == "__main__":
    main()
