#!/usr/bin/env python3
"""Validate blinded species-balanced random ladders on the frozen foundation."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np

from bacselect.provenance import verify_input_manifest
from bacselect.random_baseline import (
    DEFAULT_MAX_N,
    DEFAULT_REPLICATES,
    DEFAULT_SEED,
    random_ladders,
)


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765
EXPECTED_REPLICATES = 1000
EXPECTED_MAX_N = 500
EXPECTED_SEED = 20260824
PERMUTATION_SEED = 20260824

EXPECTED_LADDER_SET_SHA256 = (
    "9394a26ded92fb2baafea0101b837335"
    "e9d434f4cd3d8c6484ef61bbf0741719"
)

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"


def ladder_matrix_sha256(
    ladders: np.ndarray,
    accessions: list[str],
) -> str:
    """Return a blinded fingerprint of the complete ordered ladder set."""
    digest = hashlib.sha256()
    digest.update(
        b"BacSelect-selector-v1|random|1000x500\n"
    )

    for ladder in ladders:
        for index in ladder:
            digest.update(
                accessions[int(index)].encode("utf-8")
            )
            digest.update(b"\n")

        digest.update(b"--replicate--\n")

    return digest.hexdigest()


def main() -> None:
    assert DEFAULT_REPLICATES == EXPECTED_REPLICATES
    assert DEFAULT_MAX_N == EXPECTED_MAX_N
    assert DEFAULT_SEED == EXPECTED_SEED

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
        raw_rows = list(
            csv.DictReader(handle, delimiter="\t")
        )

    with species_path.open(newline="", encoding="utf-8") as handle:
        species_rows = list(
            csv.DictReader(handle, delimiter="\t")
        )

    assert len(raw_rows) == EXPECTED_GENOMES
    assert len(species_rows) == EXPECTED_GENOMES

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

    ladders = random_ladders(
        species_ids,
        accessions,
        max_n=EXPECTED_MAX_N,
        replicates=EXPECTED_REPLICATES,
        seed=EXPECTED_SEED,
    )

    assert ladders.shape == (
        EXPECTED_REPLICATES,
        EXPECTED_MAX_N,
    )
    assert ladders.dtype == np.int64

    for ladder in ladders:
        assert np.unique(ladder).size == EXPECTED_MAX_N

        selected_species = [
            species_ids[int(index)]
            for index in ladder
        ]

        assert len(set(selected_species)) == EXPECTED_MAX_N

    observed_hash = ladder_matrix_sha256(
        ladders,
        accessions,
    )

    assert observed_hash == EXPECTED_LADDER_SET_SHA256, (
        "random ladder-set fingerprint changed: "
        f"{observed_hash}"
    )

    rebuild = random_ladders(
        species_ids,
        accessions,
        max_n=EXPECTED_MAX_N,
        replicates=EXPECTED_REPLICATES,
        seed=EXPECTED_SEED,
    )

    assert np.array_equal(rebuild, ladders)

    rebuild_hash = ladder_matrix_sha256(
        rebuild,
        accessions,
    )

    assert rebuild_hash == observed_hash

    rng = np.random.default_rng(PERMUTATION_SEED)
    permutation = rng.permutation(EXPECTED_GENOMES)

    permuted_species = [
        species_ids[index]
        for index in permutation
    ]

    permuted_accessions = [
        accessions[index]
        for index in permutation
    ]

    permuted_ladders = random_ladders(
        permuted_species,
        permuted_accessions,
        max_n=EXPECTED_MAX_N,
        replicates=EXPECTED_REPLICATES,
        seed=EXPECTED_SEED,
    )

    canonical_ladder_accessions = [
        [
            accessions[int(index)]
            for index in ladder
        ]
        for ladder in ladders
    ]

    permuted_ladder_accessions = [
        [
            permuted_accessions[int(index)]
            for index in ladder
        ]
        for ladder in permuted_ladders
    ]

    assert (
        permuted_ladder_accessions
        == canonical_ladder_accessions
    )

    permuted_hash = ladder_matrix_sha256(
        permuted_ladders,
        permuted_accessions,
    )

    assert permuted_hash == observed_hash

    print(
        f"PASS | immutable inputs verified | "
        f"{EXPECTED_GENOMES} genomes"
    )
    print(
        f"PASS | eligible species groups | "
        f"{EXPECTED_SPECIES}"
    )
    print(
        f"PASS | random ladders | "
        f"{EXPECTED_REPLICATES} x {EXPECTED_MAX_N}"
    )
    print("PASS | every replicate contains 500 distinct species")
    print("PASS | same-seed rebuild is byte-identical")
    print("PASS | full-universe input-order invariance")
    print(
        "PASS | blinded random ladder-set fingerprint | "
        f"{observed_hash}"
    )


if __name__ == "__main__":
    main()
