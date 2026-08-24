#!/usr/bin/env python3
"""Run blinded selector-v1 grouped feature-ablation validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import platform
from dataclasses import fields
from pathlib import Path

import numpy as np

from bacselect.ablation import (
    panel_overlap_count,
    remove_feature_columns,
)
from bacselect.geometry import (
    species_balanced_percentile_matrix,
)
from bacselect.metrics import (
    CoverageSummary,
    coverage_summary,
    nearest_panel_distances,
)
from bacselect.ops import ops_ladder
from bacselect.provenance import verify_input_manifest
from bacselect.sr import sr_ladder


EXPECTED_GENOMES = 55306
EXPECTED_SPECIES = 13765

FEATURES = (
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

GROUPS = (
    (
        "basic_genome_properties",
        (
            "01_total_genome_length",
            "02_whole_genome_gc_fraction",
        ),
    ),
    (
        "replicon_architecture",
        (
            "03_replicon_count",
            "04_non_chromosomal_replicon_count",
            "05_non_chromosomal_sequence_fraction",
        ),
    ),
    (
        "repeat_architecture",
        (
            "06_non_unique_canonical_150mer_fraction",
            "07_non_unique_canonical_400mer_fraction",
            "08_maximum_canonical_150mer_multiplicity",
            "09_maximum_canonical_400mer_multiplicity",
            "10_longest_exact_repeat_length",
        ),
    ),
    (
        "inter_replicon_sharing",
        (
            "11_inter_replicon_shared_canonical_150mer_fraction",
            "12_inter_replicon_shared_canonical_400mer_fraction",
        ),
    ),
)


PANEL_SIZES = (
    10,
    20,
    50,
    100,
    200,
    500,
)
MAX_N = max(PANEL_SIZES)

ACCESSION_COLUMN = (
    "canonical_genbank_assembly_accession"
)
SPECIES_COLUMN = "species_taxid"

METADATA_COLUMNS = (
    "batch",
    "batch_index",
    ACCESSION_COLUMN,
)

EXPECTED_OPS_LADDER_SHA256 = (
    "3f9a7c4557268fad829b078de9679cda"
    "4ee26a81982c1aed71fc066f8290f3b8"
)

EXPECTED_SR_LADDER_SHA256 = (
    "dbe0174a5e96202e7d755ac616318c5e"
    "6007939b5062a3f5b9dabea0a8bfe5e8"
)

EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207ea"
    "ef5c2435e1b6feeddc1e4654686bc2a8c"
)

ENV_LOCK = Path(
    "envs/bacselect-dev-linux-64.lock"
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


def sequence_sha256(
    namespace: str,
    values: list[str],
) -> str:
    payload = (
        namespace
        + "\n"
        + "\n".join(values)
        + "\n"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def format_metric(value: float) -> str:
    return format(
        value,
        ".17g",
    )


def validate_group_definitions() -> None:
    group_names = [
        group_name
        for group_name, _ in GROUPS
    ]

    if len(set(group_names)) != len(group_names):
        raise AssertionError(
            "group names are not unique"
        )

    flattened = [
        feature
        for _, group_features in GROUPS
        for feature in group_features
    ]

    if len(flattened) != len(FEATURES):
        raise AssertionError(
            "grouped features do not cover exactly 12 dimensions"
        )

    if len(set(flattened)) != len(flattened):
        raise AssertionError(
            "a structural feature occurs in more than one group"
        )

    if set(flattened) != set(FEATURES):
        raise AssertionError(
            "grouped feature membership changed"
        )

    observed_sizes = tuple(
        len(group_features)
        for _, group_features in GROUPS
    )

    expected_sizes = (
        2,
        3,
        5,
        2,
    )

    if observed_sizes != expected_sizes:
        raise AssertionError(
            "grouped feature sizes changed"
        )

    print(
        "PASS | frozen grouped-ablation definitions | "
        "4 groups | sizes=2,3,5,2"
    )


def load_foundation() -> tuple[
    np.ndarray,
    list[str],
    list[str],
]:
    artifacts = verify_input_manifest(
        Path(
            "validation/finch-foundation/"
            "inputs.tsv"
        )
    )

    paths = {
        artifact.artifact: artifact.path
        for artifact in artifacts
    }

    raw_path = paths[
        "corrected_raw_structural_feature_matrix"
    ]
    species_path = paths[
        "corrected_species_mapping"
    ]

    with raw_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        fieldnames = tuple(
            reader.fieldnames or ()
        )

        expected_header = (
            *METADATA_COLUMNS,
            *FEATURES,
        )

        if fieldnames != expected_header:
            raise AssertionError(
                "raw feature schema changed"
            )

        raw_rows = list(reader)

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

    if len(raw_rows) != EXPECTED_GENOMES:
        raise AssertionError(
            "raw feature row count changed"
        )

    if len(species_rows) != EXPECTED_GENOMES:
        raise AssertionError(
            "species mapping row count changed"
        )

    accessions = [
        row[ACCESSION_COLUMN]
        for row in raw_rows
    ]

    mapping_accessions = [
        row[ACCESSION_COLUMN]
        for row in species_rows
    ]

    if accessions != mapping_accessions:
        raise AssertionError(
            "feature and species accession order changed"
        )

    if len(set(accessions)) != EXPECTED_GENOMES:
        raise AssertionError(
            "accessions are not unique"
        )

    species_ids = [
        row[SPECIES_COLUMN]
        for row in species_rows
    ]

    if len(set(species_ids)) != EXPECTED_SPECIES:
        raise AssertionError(
            "species count changed"
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

    if raw.shape != (
        EXPECTED_GENOMES,
        len(FEATURES),
    ):
        raise AssertionError(
            f"raw matrix shape changed: {raw.shape}"
        )

    coordinates = (
        species_balanced_percentile_matrix(
            raw,
            species_ids,
        )
    )

    if coordinates.shape != raw.shape:
        raise AssertionError(
            "coordinate matrix shape changed"
        )

    if not np.all(np.isfinite(coordinates)):
        raise AssertionError(
            "coordinate matrix contains non-finite values"
        )

    env_hash = require_sha256(
        ENV_LOCK,
        EXPECTED_ENV_LOCK_SHA256,
    )

    print(
        "PASS | immutable validation universe | "
        f"{EXPECTED_GENOMES} genomes | "
        f"{EXPECTED_SPECIES} species | "
        f"{len(FEATURES)} features"
    )

    print(
        "PASS | frozen environment lock | "
        f"{env_hash}"
    )

    return (
        coordinates,
        species_ids,
        accessions,
    )


def ladder_hash(
    namespace: str,
    ladder: np.ndarray,
    accessions: list[str],
) -> str:
    ladder_accessions = [
        accessions[int(index)]
        for index in ladder
    ]

    return sequence_sha256(
        namespace,
        ladder_accessions,
    )


def evaluate_ladder(
    evaluation_coordinates: np.ndarray,
    species_ids: list[str],
    ladder: np.ndarray,
) -> dict[int, CoverageSummary]:
    result: dict[
        int,
        CoverageSummary,
    ] = {}

    for panel_size in PANEL_SIZES:
        distances = nearest_panel_distances(
            evaluation_coordinates,
            ladder[:panel_size],
        )

        result[panel_size] = coverage_summary(
            distances,
            species_ids,
        )

    return result


def base12_ladders(
    coordinates: np.ndarray,
    species_ids: list[str],
    accessions: list[str],
) -> dict[str, np.ndarray]:
    ops = ops_ladder(
        coordinates,
        species_ids,
        accessions,
        max_n=MAX_N,
    )

    sr = sr_ladder(
        coordinates,
        species_ids,
        accessions,
        max_n=MAX_N,
    )

    ops_hash = ladder_hash(
        "BacSelect-selector-v1|OPS|ladder|N=500",
        ops,
        accessions,
    )

    sr_hash = ladder_hash(
        "BacSelect-selector-v1|SR|ladder|N=500",
        sr,
        accessions,
    )

    if ops_hash != EXPECTED_OPS_LADDER_SHA256:
        raise AssertionError(
            "frozen OPS ladder fingerprint changed"
        )

    if sr_hash != EXPECTED_SR_LADDER_SHA256:
        raise AssertionError(
            "frozen SR ladder fingerprint changed"
        )

    print(
        "PASS | frozen blinded OPS ladder | "
        f"{ops_hash}"
    )
    print(
        "PASS | frozen blinded SR ladder | "
        f"{sr_hash}"
    )

    return {
        "OPS": ops,
        "SR": sr,
    }


def build_report(
    coordinates: np.ndarray,
    species_ids: list[str],
    accessions: list[str],
    references: dict[str, np.ndarray],
) -> str:
    metric_names = [
        field.name
        for field in fields(CoverageSummary)
    ]

    buffer = io.StringIO(
        newline=""
    )

    writer = csv.writer(
        buffer,
        delimiter="\t",
        lineterminator="\n",
    )

    writer.writerow(
        [
            "removed_group",
            "removed_features",
            "selection_dimensions",
            "selector",
            "N",
            "ablation_ladder_sha256",
            "overlap_count",
            "overlap_fraction",
            *metric_names,
        ]
    )

    row_count = 0

    for group_name, removed_features in GROUPS:
        feature_indices = tuple(
            FEATURES.index(feature)
            for feature in removed_features
        )

        selection_coordinates = (
            remove_feature_columns(
                coordinates,
                feature_indices,
            )
        )

        selection_dimensions = (
            len(FEATURES)
            - len(removed_features)
        )

        if selection_coordinates.shape != (
            EXPECTED_GENOMES,
            selection_dimensions,
        ):
            raise AssertionError(
                "grouped-ablation coordinate shape changed"
            )

        removed_feature_text = ",".join(
            removed_features
        )

        for selector_name in (
            "OPS",
            "SR",
        ):
            if selector_name == "OPS":
                ladder = ops_ladder(
                    selection_coordinates,
                    species_ids,
                    accessions,
                    max_n=MAX_N,
                )
            else:
                ladder = sr_ladder(
                    selection_coordinates,
                    species_ids,
                    accessions,
                    max_n=MAX_N,
                )

            if ladder.size != MAX_N:
                raise AssertionError(
                    "grouped-ablation ladder length changed"
                )

            if np.unique(ladder).size != MAX_N:
                raise AssertionError(
                    "grouped-ablation ladder contains duplicates"
                )

            fingerprint = ladder_hash(
                (
                    "BacSelect-selector-v1|GROUPED|"
                    f"remove={group_name}|"
                    f"{selector_name}|ladder|N=500"
                ),
                ladder,
                accessions,
            )

            print(
                "PASS | blinded grouped-ablation ladder | "
                f"group={group_name} | "
                f"removed={removed_feature_text} | "
                f"selector={selector_name} | "
                f"{fingerprint}"
            )

            summaries = evaluate_ladder(
                coordinates,
                species_ids,
                ladder,
            )

            reference = references[
                selector_name
            ]

            for panel_size in PANEL_SIZES:
                overlap = panel_overlap_count(
                    reference[:panel_size],
                    ladder[:panel_size],
                )

                summary = summaries[
                    panel_size
                ]

                writer.writerow(
                    [
                        group_name,
                        removed_feature_text,
                        selection_dimensions,
                        selector_name,
                        panel_size,
                        fingerprint,
                        overlap,
                        f"{overlap}/{panel_size}",
                        *[
                            format_metric(
                                getattr(
                                    summary,
                                    metric_name,
                                )
                            )
                            for metric_name
                            in metric_names
                        ],
                    ]
                )

                row_count += 1

    expected_rows = (
        len(GROUPS)
        * 2
        * len(PANEL_SIZES)
    )

    if row_count != expected_rows:
        raise AssertionError(
            "grouped-ablation row count changed: "
            f"{row_count}"
        )

    text = buffer.getvalue()

    if "GCA_" in text or "GCF_" in text:
        raise AssertionError(
            "identity-like accession leaked into report"
        )

    return text



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

    validate_group_definitions()

    (
        coordinates,
        species_ids,
        accessions,
    ) = load_foundation()

    references = base12_ladders(
        coordinates,
        species_ids,
        accessions,
    )

    print(
        "environment | "
        f"python={platform.python_version()} | "
        f"numpy={np.__version__}"
    )

    if args.verify_inputs_only:
        if args.output is not None:
            raise ValueError(
                "--output must not be supplied with "
                "--verify-inputs-only"
            )

        print(
            "PASS | verification only | "
            "no grouped reduced-feature selector calculated"
        )
        return

    if args.output is None:
        raise ValueError(
            "--output is required unless "
            "--verify-inputs-only is used"
        )

    if args.output.exists():
        raise FileExistsError(
            f"refusing to overwrite: {args.output}"
        )

    text = build_report(
        coordinates,
        species_ids,
        accessions,
        references,
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        text,
        encoding="utf-8",
    )

    output_hash = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    print(
        "PASS | complete grouped-ablation report | "
        "4 groups x 2 selectors x 6 N"
    )
    print(
        "PASS | coverage evaluated in frozen "
        "base-12 geometry"
    )
    print(
        "PASS | identity-blind grouped-ablation report"
    )
    print(
        f"grouped_ablation_sha256 | {output_hash}"
    )


if __name__ == "__main__":
    main()
