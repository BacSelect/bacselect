#!/usr/bin/env python3
"""Derive the frozen 55,306-genome repeat-concordance target manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import tempfile
from pathlib import Path


EXPECTED_CORRECTED_MATRIX_SHA256 = (
    "fd264bedda627d737a647de601c8b835"
    "f53baeca246724e9aafb73fd50c9d656"
)

EXPECTED_FINCH_TARGET_SHA256 = (
    "da8c1f1496d44044a97be4935af19bbe"
    "87343faa8c7e747e2bcf16e2dd478942"
)

EXPECTED_OUTPUT_SHA256 = (
    "bc4acba1384524f956887d02d2f54aa7"
    "e501a2c23e2930b779a4e6520d8fcee1"
)

EXPECTED_CORRECTED_ROWS = 55306
EXPECTED_FINCH_ROWS = 55420
EXPECTED_EXCLUDED_ROWS = 114
EXPECTED_BATCHES = 111


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
) -> None:
    observed = sha256_file(path)

    if observed != expected:
        raise RuntimeError(
            f"SHA-256 mismatch for {path}: "
            f"expected {expected}, observed {observed}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--corrected-matrix",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--finch-targets",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    require_sha256(
        args.corrected_matrix,
        EXPECTED_CORRECTED_MATRIX_SHA256,
    )

    require_sha256(
        args.finch_targets,
        EXPECTED_FINCH_TARGET_SHA256,
    )

    with args.corrected_matrix.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        corrected = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    if len(corrected) != EXPECTED_CORRECTED_ROWS:
        raise RuntimeError(
            f"corrected rows changed: {len(corrected)}"
        )

    accessions = [
        row["canonical_genbank_assembly_accession"]
        for row in corrected
    ]

    if len(set(accessions)) != len(accessions):
        raise RuntimeError(
            "corrected accessions are not unique"
        )

    with args.finch_targets.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        finch = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    if len(finch) != EXPECTED_FINCH_ROWS:
        raise RuntimeError(
            f"Finch target rows changed: {len(finch)}"
        )

    by_accession: dict[
        str,
        tuple[dict[str, str], int],
    ] = {}

    positions: dict[str, int] = {}

    for row in finch:
        batch = row["batch"]

        position = positions.get(
            batch,
            0,
        ) + 1

        positions[batch] = position

        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if accession in by_accession:
            raise RuntimeError(
                f"duplicate Finch target: {accession}"
            )

        by_accession[accession] = (
            row,
            position,
        )

    output_rows = []

    for corrected_row in corrected:
        accession = corrected_row[
            "canonical_genbank_assembly_accession"
        ]

        try:
            finch_row, original_index = (
                by_accession[accession]
            )
        except KeyError as exc:
            raise RuntimeError(
                f"corrected accession absent from Finch targets: "
                f"{accession}"
            ) from exc

        if corrected_row["batch"] != finch_row["batch"]:
            raise RuntimeError(
                f"batch mismatch for {accession}"
            )

        if int(
            corrected_row["batch_index"]
        ) != original_index:
            raise RuntimeError(
                f"batch_index mismatch for {accession}"
            )

        if int(
            corrected_row[
                "01_total_genome_length"
            ]
        ) != int(
            finch_row[
                "total_sequence_length"
            ]
        ):
            raise RuntimeError(
                f"genome length mismatch for {accession}"
            )

        if int(
            corrected_row[
                "03_replicon_count"
            ]
        ) != int(
            finch_row[
                "primary_assembly_records"
            ]
        ):
            raise RuntimeError(
                f"replicon count mismatch for {accession}"
            )

        output_rows.append(
            {
                "batch": corrected_row["batch"],
                "batch_index": corrected_row[
                    "batch_index"
                ],
                "canonical_genbank_assembly_accession": accession,
                "total_sequence_length": finch_row[
                    "total_sequence_length"
                ],
                "primary_assembly_records": finch_row[
                    "primary_assembly_records"
                ],
                "topology_circular_records": finch_row[
                    "topology_circular_records"
                ],
                "topology_linear_records": finch_row[
                    "topology_linear_records"
                ],
            }
        )

    if (
        EXPECTED_FINCH_ROWS
        - len(output_rows)
        != EXPECTED_EXCLUDED_ROWS
    ):
        raise RuntimeError(
            "corrected exclusion count changed"
        )

    batches = {
        row["batch"]
        for row in output_rows
    }

    if len(batches) != EXPECTED_BATCHES:
        raise RuntimeError(
            f"batch count changed: {len(batches)}"
        )

    fieldnames = [
        "batch",
        "batch_index",
        "canonical_genbank_assembly_accession",
        "total_sequence_length",
        "primary_assembly_records",
        "topology_circular_records",
        "topology_linear_records",
    ]

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=args.output.name + ".",
        suffix=".tmp",
        dir=args.output.parent,
        text=True,
    )

    temporary = Path(
        temporary_name
    )

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
            )

            writer.writeheader()
            writer.writerows(output_rows)

            handle.flush()
            os.fsync(
                handle.fileno()
            )

        temporary.replace(
            args.output
        )

    except Exception:
        temporary.unlink(
            missing_ok=True
        )
        raise

    require_sha256(
        args.output,
        EXPECTED_OUTPUT_SHA256,
    )

    print(
        "PASS | frozen repeat-concordance target manifest"
    )
    print(
        f"targets\t{len(output_rows)}"
    )
    print(
        f"batches\t{len(batches)}"
    )
    print(
        f"sha256\t{EXPECTED_OUTPUT_SHA256}"
    )


if __name__ == "__main__":
    main()
