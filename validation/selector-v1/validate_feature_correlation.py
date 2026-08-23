#!/usr/bin/env python3
"""Validate and report selector-v1 feature correlations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import platform
from pathlib import Path

import numpy as np
import scipy

from bacselect.correlation import spearman_correlation_matrix
from bacselect.provenance import verify_input_manifest


EXPECTED_GENOMES = 55306

EXPECTED_FEATURES = (
    "01_total_genome_length",
    "02_whole_genome_gc_fraction",
    "03_replicon_count",
    "04_non_chromosomal_replicon_count",
    "05_non_chromosomal_sequence_fraction",
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
)

EXPECTED_RAW_SHA256 = (
    "fd264bedda627d737a647de601c8b835"
    "f53baeca246724e9aafb73fd50c9d656"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207ea"
    "ef5c2435e1b6feeddc1e4654686bc2a8c"
)

ENV_LOCK = Path("envs/bacselect-dev-linux-64.lock")

METADATA_COLUMNS = (
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
) -> str:
    observed = file_sha256(path)

    if observed != expected:
        raise AssertionError(
            f"SHA256 changed for {path}: {observed}"
        )

    return observed


def load_inputs() -> np.ndarray:
    artifacts = verify_input_manifest(
        Path("validation/finch-foundation/inputs.tsv")
    )

    paths = {
        artifact.artifact: artifact.path
        for artifact in artifacts
    }

    raw_path = paths[
        "corrected_raw_structural_feature_matrix"
    ]

    raw_hash = require_sha256(
        raw_path,
        EXPECTED_RAW_SHA256,
    )

    env_hash = require_sha256(
        ENV_LOCK,
        EXPECTED_ENV_LOCK_SHA256,
    )

    with raw_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fieldnames = tuple(reader.fieldnames or ())

        expected_header = (
            *METADATA_COLUMNS,
            *EXPECTED_FEATURES,
        )

        if fieldnames != expected_header:
            raise AssertionError(
                "raw feature header changed"
            )

        rows = list(reader)

    if len(rows) != EXPECTED_GENOMES:
        raise AssertionError(
            f"row count changed: {len(rows)}"
        )

    matrix = np.asarray(
        [
            [
                float(row[feature])
                for feature in EXPECTED_FEATURES
            ]
            for row in rows
        ],
        dtype=np.float64,
    )

    if matrix.shape != (
        EXPECTED_GENOMES,
        len(EXPECTED_FEATURES),
    ):
        raise AssertionError(
            f"matrix shape changed: {matrix.shape}"
        )

    if not np.all(np.isfinite(matrix)):
        raise AssertionError(
            "raw feature matrix contains non-finite values"
        )

    if np.any(
        np.all(
            matrix == matrix[0, :],
            axis=0,
        )
    ):
        raise AssertionError(
            "raw feature matrix contains a constant feature"
        )

    print(
        "PASS | frozen raw feature matrix | "
        f"{EXPECTED_GENOMES} genomes x "
        f"{len(EXPECTED_FEATURES)} features | "
        f"{raw_hash}"
    )
    print(
        "PASS | frozen environment lock | "
        f"{env_hash}"
    )
    print(
        "PASS | exact feature schema | "
        f"{len(EXPECTED_FEATURES)} dimensions"
    )

    return matrix


def write_matrix(
    output: Path,
    correlation: np.ndarray,
) -> str:
    if output.exists():
        raise FileExistsError(
            f"refusing to overwrite: {output}"
        )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.writer(
            handle,
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writerow(
            [
                "feature",
                *EXPECTED_FEATURES,
            ]
        )

        for row_name, row in zip(
            EXPECTED_FEATURES,
            correlation,
        ):
            writer.writerow(
                [
                    row_name,
                    *[
                        format(float(value), ".17g")
                        for value in row
                    ],
                ]
            )

    return file_sha256(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--verify-inputs-only",
        action="store_true",
    )

    parser.add_argument(
        "--output",
        type=Path,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    matrix = load_inputs()

    print(
        "environment | "
        f"python={platform.python_version()} | "
        f"numpy={np.__version__} | "
        f"scipy={scipy.__version__}"
    )

    if args.verify_inputs_only:
        if args.output is not None:
            raise ValueError(
                "--output must not be supplied with "
                "--verify-inputs-only"
            )

        print(
            "PASS | verification only | "
            "no real correlation coefficients calculated"
        )
        return

    if args.output is None:
        raise ValueError(
            "--output is required unless "
            "--verify-inputs-only is used"
        )

    correlation = spearman_correlation_matrix(
        matrix
    )

    rebuilt = spearman_correlation_matrix(
        matrix
    )

    if not np.array_equal(
        correlation,
        rebuilt,
    ):
        raise AssertionError(
            "correlation matrix changed on deterministic rebuild"
        )

    expected_shape = (
        len(EXPECTED_FEATURES),
        len(EXPECTED_FEATURES),
    )

    if correlation.shape != expected_shape:
        raise AssertionError(
            f"correlation shape changed: {correlation.shape}"
        )

    if not np.all(np.isfinite(correlation)):
        raise AssertionError(
            "correlation contains non-finite values"
        )

    if not np.array_equal(
        correlation,
        correlation.T,
    ):
        raise AssertionError(
            "correlation matrix is not symmetric"
        )

    if not np.allclose(
        np.diag(correlation),
        np.ones(len(EXPECTED_FEATURES)),
        rtol=0.0,
        atol=1e-15,
    ):
        raise AssertionError(
            "correlation matrix diagonal is not unity"
        )

    output_hash = write_matrix(
        args.output,
        correlation,
    )

    print(
        "PASS | complete Spearman matrix | "
        "12 x 12"
    )
    print(
        "PASS | finite symmetric unit-diagonal matrix"
    )
    print(
        "PASS | deterministic rebuild"
    )
    print(
        "PASS | identity-blind correlation report"
    )
    print(
        f"correlation_sha256 | {output_hash}"
    )


if __name__ == "__main__":
    main()
