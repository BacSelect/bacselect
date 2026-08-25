"""Shared loader for the frozen BacSelect selector-v1 300/2400 foundation."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from bacselect.geometry import species_balanced_percentile_matrix
from bacselect.provenance import verify_input_manifest


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765
EXPECTED_FEATURES = 12

MANIFEST_PATH = Path(
    "validation/selector-v1/final-feature-space-inputs.tsv"
)

EXPECTED_MANIFEST_SHA256 = (
    "512d466ff6b8af3e51eb91db715d5fc5c"
    "76995892a4c1b18489d922a0414f0f2"
)

EXPECTED_RAW_FILE_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666"
    "fe2112b6a3ae8dae2090b60a2a598948"
)

EXPECTED_PERCENTILE_FILE_SHA256 = (
    "f48e20b28ee89988e7abb42488a35c62"
    "fbfa4a538c15c8d2d70b6b5ba7ae83c1"
)

EXPECTED_SPECIES_FILE_SHA256 = (
    "f0343238930e957f82bc28997a216ab3"
    "a8967d007b3d3471679e3f054c76af6c"
)

EXPECTED_RAW_ARRAY_SHA256 = (
    "2a0dbd5809fa4d5d77ab6e2d5255ddec"
    "9bb933a94be6c270260ec81758d8cbd6"
)

EXPECTED_PERCENTILE_ARRAY_SHA256 = (
    "9a4a120562ff1151fd8c83e831eb81362"
    "b2372844f7dd7407746554af49cda67"
)

METADATA_COLUMNS = (
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
)

FEATURES = (
    "01_total_genome_length",
    "02_whole_genome_gc_fraction",
    "03_replicon_count",
    "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction",
    "06_non_unique_canonical_300mer_fraction",
    "07_non_unique_canonical_2400mer_fraction",
    "08_maximum_canonical_300mer_multiplicity",
    "09_maximum_canonical_2400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_300mer_fraction",
    "12_inter_replicon_shared_canonical_2400mer_fraction",
)

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"


@dataclass(frozen=True)
class FinalFoundation:
    """Verified frozen final selector-v1 feature foundation."""

    raw: npt.NDArray[np.float64]
    coordinates: npt.NDArray[np.float64]
    species_ids: list[str]
    accessions: list[str]
    raw_path: Path
    percentile_path: Path
    species_path: Path


def file_sha256(path: Path) -> str:
    """Return streaming SHA256 for one file."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def matrix_sha256(matrix: npt.NDArray[np.floating]) -> str:
    """Return SHA256 for little-endian contiguous float64 matrix bytes."""
    canonical = np.ascontiguousarray(
        matrix,
        dtype="<f8",
    )

    return hashlib.sha256(
        canonical.tobytes(order="C")
    ).hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    """Require one exact file SHA256."""
    if not path.is_file():
        raise AssertionError(
            f"{label} missing: {path}"
        )

    observed = file_sha256(path)

    if observed != expected:
        raise AssertionError(
            f"{label} SHA256 changed: "
            f"expected {expected}, observed {observed}"
        )

    return observed


def _row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row["batch"],
        row["batch_index"],
        row[ACCESSION_COLUMN],
    )


def load_final_foundation(
    *,
    recompute_coordinates: bool,
) -> FinalFoundation:
    """Load and fail-closed verify the frozen final 300/2400 foundation."""
    require_sha256(
        MANIFEST_PATH,
        EXPECTED_MANIFEST_SHA256,
        "final feature-space input manifest",
    )

    artifacts = verify_input_manifest(
        MANIFEST_PATH
    )

    artifact_map = {
        artifact.artifact: artifact.path
        for artifact in artifacts
    }

    expected_artifacts = {
        "final_raw_structural_feature_matrix",
        "final_species_balanced_percentile_feature_matrix",
        "corrected_species_mapping",
    }

    if set(artifact_map) != expected_artifacts:
        raise AssertionError(
            "final feature-space manifest artifact set changed: "
            f"{sorted(artifact_map)}"
        )

    raw_path = artifact_map[
        "final_raw_structural_feature_matrix"
    ]
    percentile_path = artifact_map[
        "final_species_balanced_percentile_feature_matrix"
    ]
    species_path = artifact_map[
        "corrected_species_mapping"
    ]

    require_sha256(
        raw_path,
        EXPECTED_RAW_FILE_SHA256,
        "final raw structural feature matrix",
    )
    require_sha256(
        percentile_path,
        EXPECTED_PERCENTILE_FILE_SHA256,
        "final percentile feature matrix",
    )
    require_sha256(
        species_path,
        EXPECTED_SPECIES_FILE_SHA256,
        "corrected species mapping",
    )

    with raw_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )
        raw_header = tuple(
            reader.fieldnames or ()
        )
        raw_rows = list(reader)

    with percentile_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )
        percentile_header = tuple(
            reader.fieldnames or ()
        )
        percentile_rows = list(reader)

    with species_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        species_rows = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    expected_header = (
        *METADATA_COLUMNS,
        *FEATURES,
    )

    if raw_header != expected_header:
        raise AssertionError(
            "final raw feature schema changed"
        )

    if percentile_header != expected_header:
        raise AssertionError(
            "final percentile feature schema changed"
        )

    for label, rows in (
        ("raw", raw_rows),
        ("percentile", percentile_rows),
        ("species", species_rows),
    ):
        if len(rows) != EXPECTED_GENOMES:
            raise AssertionError(
                f"{label} row count changed: {len(rows)}"
            )

    raw_keys = [
        _row_key(row)
        for row in raw_rows
    ]
    percentile_keys = [
        _row_key(row)
        for row in percentile_rows
    ]
    species_keys = [
        _row_key(row)
        for row in species_rows
    ]

    if raw_keys != percentile_keys:
        raise AssertionError(
            "raw and percentile genome order changed"
        )

    if raw_keys != species_keys:
        raise AssertionError(
            "feature and species genome order changed"
        )

    accessions = [
        row[ACCESSION_COLUMN]
        for row in raw_rows
    ]

    if len(set(accessions)) != EXPECTED_GENOMES:
        raise AssertionError(
            "final feature-space accessions are not unique"
        )

    species_ids = [
        row[SPECIES_COLUMN]
        for row in species_rows
    ]

    if any(
        species_id == ""
        for species_id in species_ids
    ):
        raise AssertionError(
            "species mapping contains empty species IDs"
        )

    if len(set(species_ids)) != EXPECTED_SPECIES:
        raise AssertionError(
            "final species-group count changed"
        )

    raw = np.asarray(
        [
            [
                float(row[feature])
                for feature in FEATURES
            ]
            for row in raw_rows
        ],
        dtype=np.float64,
    )

    coordinates = np.asarray(
        [
            [
                float(row[feature])
                for feature in FEATURES
            ]
            for row in percentile_rows
        ],
        dtype=np.float64,
    )

    expected_shape = (
        EXPECTED_GENOMES,
        EXPECTED_FEATURES,
    )

    if raw.shape != expected_shape:
        raise AssertionError(
            f"raw matrix shape changed: {raw.shape}"
        )

    if coordinates.shape != expected_shape:
        raise AssertionError(
            "percentile matrix shape changed: "
            f"{coordinates.shape}"
        )

    if not np.all(np.isfinite(raw)):
        raise AssertionError(
            "raw matrix contains non-finite values"
        )

    if not np.all(np.isfinite(coordinates)):
        raise AssertionError(
            "percentile matrix contains non-finite values"
        )

    if not np.all(
        (coordinates >= 0.0)
        & (coordinates <= 1.0)
    ):
        raise AssertionError(
            "percentile matrix contains values outside [0,1]"
        )

    raw_hash = matrix_sha256(raw)
    if raw_hash != EXPECTED_RAW_ARRAY_SHA256:
        raise AssertionError(
            "final raw float64 array identity changed: "
            f"{raw_hash}"
        )

    coordinate_hash = matrix_sha256(
        coordinates
    )
    if (
        coordinate_hash
        != EXPECTED_PERCENTILE_ARRAY_SHA256
    ):
        raise AssertionError(
            "final percentile float64 array identity changed: "
            f"{coordinate_hash}"
        )

    if recompute_coordinates:
        recalculated = (
            species_balanced_percentile_matrix(
                raw,
                species_ids,
            )
        )

        if not np.array_equal(
            recalculated,
            coordinates,
        ):
            raise AssertionError(
                "frozen percentile matrix differs from "
                "committed species-balanced transformation"
            )

        recalculated_hash = matrix_sha256(
            recalculated
        )

        if (
            recalculated_hash
            != EXPECTED_PERCENTILE_ARRAY_SHA256
        ):
            raise AssertionError(
                "recalculated percentile array identity changed: "
                f"{recalculated_hash}"
            )

    return FinalFoundation(
        raw=raw,
        coordinates=coordinates,
        species_ids=species_ids,
        accessions=accessions,
        raw_path=raw_path,
        percentile_path=percentile_path,
        species_path=species_path,
    )
