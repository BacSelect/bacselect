#!/usr/bin/env python3
"""Validate blinded OPS behaviour on the frozen Finch foundation."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np

from bacselect.geometry import species_balanced_percentile_matrix
from bacselect.ops import (
    ops_ladder,
    ops_species_representatives,
)
from bacselect.provenance import verify_input_manifest


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765
EXPECTED_FEATURES = 12
MAX_N = 500
PANEL_SIZES = (10, 20, 50, 100, 200, 500)
PERMUTATION_SEED = 20260824

EXPECTED_REPRESENTATIVE_SHA256 = (
    "8b6e71f14e473eef56bddcabeb40bfc0c"
    "91d1810bda8eefbe1b425dd3b09d947"
)

EXPECTED_LADDER_SHA256 = (
    "3f9a7c4557268fad829b078de9679cda"
    "4ee26a81982c1aed71fc066f8290f3b8"
)

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"


def sequence_sha256(namespace: str, values: list[str]) -> str:
    """Return an identity-blinded fingerprint of an ordered sequence."""
    payload = namespace + "\n" + "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

    coordinates = species_balanced_percentile_matrix(
        matrix,
        species_ids,
    )

    representatives = ops_species_representatives(
        coordinates,
        species_ids,
        accessions,
    )

    assert representatives.size == EXPECTED_SPECIES
    assert np.unique(representatives).size == EXPECTED_SPECIES

    representative_species = [
        species_ids[index]
        for index in representatives
    ]

    assert len(set(representative_species)) == EXPECTED_SPECIES

    representative_accessions = [
        accessions[index]
        for index in representatives
    ]

    representative_hash = sequence_sha256(
        "BacSelect-selector-v1|OPS|representatives",
        representative_accessions,
    )

    assert representative_hash == EXPECTED_REPRESENTATIVE_SHA256, (
        "OPS representative fingerprint changed: "
        f"{representative_hash}"
    )

    ladder = ops_ladder(
        coordinates,
        species_ids,
        accessions,
        max_n=MAX_N,
    )

    assert ladder.size == MAX_N
    assert np.unique(ladder).size == MAX_N
    assert set(ladder).issubset(set(representatives))

    ladder_species = [
        species_ids[index]
        for index in ladder
    ]

    assert len(set(ladder_species)) == MAX_N

    ladder_accessions = [
        accessions[index]
        for index in ladder
    ]

    ladder_hash = sequence_sha256(
        "BacSelect-selector-v1|OPS|ladder|N=500",
        ladder_accessions,
    )

    assert ladder_hash == EXPECTED_LADDER_SHA256, (
        "OPS N=500 ladder fingerprint changed: "
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

        assert len(set(prefix_species)) == panel_size

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

    permuted_representatives = ops_species_representatives(
        permuted_coordinates,
        permuted_species,
        permuted_accessions,
    )

    permuted_representative_accessions = [
        permuted_accessions[index]
        for index in permuted_representatives
    ]

    assert (
        permuted_representative_accessions
        == representative_accessions
    )

    permuted_ladder = ops_ladder(
        permuted_coordinates,
        permuted_species,
        permuted_accessions,
        max_n=MAX_N,
    )

    permuted_ladder_accessions = [
        permuted_accessions[index]
        for index in permuted_ladder
    ]

    assert permuted_ladder_accessions == ladder_accessions

    assert sequence_sha256(
        "BacSelect-selector-v1|OPS|representatives",
        permuted_representative_accessions,
    ) == representative_hash

    assert sequence_sha256(
        "BacSelect-selector-v1|OPS|ladder|N=500",
        permuted_ladder_accessions,
    ) == ladder_hash

    print(
        f"PASS | immutable inputs verified | "
        f"{EXPECTED_GENOMES} genomes"
    )
    print(
        f"PASS | species-balanced geometry | "
        f"{EXPECTED_FEATURES} features"
    )
    print(
        f"PASS | OPS representatives | "
        f"{EXPECTED_SPECIES}"
    )
    print("PASS | exactly one representative per species")
    print(
        f"PASS | nested OPS ladder | "
        f"N={','.join(str(value) for value in PANEL_SIZES)}"
    )
    print(f"PASS | N={MAX_N} contains {MAX_N} distinct species")
    print("PASS | full-universe input-order invariance")
    print(
        "PASS | blinded representative fingerprint | "
        f"{representative_hash}"
    )
    print(
        "PASS | blinded OPS N=500 ladder fingerprint | "
        f"{ladder_hash}"
    )


if __name__ == "__main__":
    main()
