#!/usr/bin/env python3
"""Run blinded final 300/2400 selector-v1 grouped feature-ablation validation."""

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
    "06_non_unique_canonical_300mer_fraction",
    "07_non_unique_canonical_2400mer_fraction",
    "08_maximum_canonical_300mer_multiplicity",
    "09_maximum_canonical_2400mer_multiplicity",
    "10_longest_exact_repeat_length",
    "11_inter_replicon_shared_canonical_300mer_fraction",
    "12_inter_replicon_shared_canonical_2400mer_fraction",
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
            "06_non_unique_canonical_300mer_fraction",
            "07_non_unique_canonical_2400mer_fraction",
            "08_maximum_canonical_300mer_multiplicity",
            "09_maximum_canonical_2400mer_multiplicity",
            "10_longest_exact_repeat_length",
        ),
    ),
    (
        "inter_replicon_sharing",
        (
            "11_inter_replicon_shared_canonical_300mer_fraction",
            "12_inter_replicon_shared_canonical_2400mer_fraction",
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

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"

METADATA_COLUMNS = (
    "batch",
    "batch_index",
    ACCESSION_COLUMN,
)

INPUT_MANIFEST = Path(
    "validation/selector-v1/final-feature-space-inputs.tsv"
)
REFERENCE_METRICS = Path(
    "validation/selector-v1/results/"
    "final300-2400-ops-vs-sr-metrics.tsv"
)
ENV_LOCK = Path(
    "envs/bacselect-dev-linux-64.lock"
)

EXPECTED_INPUT_MANIFEST_SHA256 = (
    "512d466ff6b8af3e51eb91db715d5fc5"
    "c76995892a4c1b18489d922a0414f0f2"
)
EXPECTED_PERCENTILE_MATRIX_SHA256 = (
    "f48e20b28ee89988e7abb42488a35c62"
    "fbfa4a538c15c8d2d70b6b5ba7ae83c1"
)
EXPECTED_SPECIES_MAPPING_SHA256 = (
    "f0343238930e957f82bc28997a216ab3"
    "a8967d007b3d3471679e3f054c76af6c"
)
EXPECTED_PERCENTILE_ARRAY_SHA256 = (
    "9a4a120562ff1151fd8c83e831eb81362"
    "b2372844f7dd7407746554af49cda67"
)
EXPECTED_REFERENCE_METRICS_SHA256 = (
    "9cd2cc838cb74a044e356a1a418633ef"
    "2bdc89c4e9f71f924e4c1c0a79073388"
)
EXPECTED_OPS_LADDER_SHA256 = (
    "c81d9fd30cda2d49f0f6c81d4bf99da"
    "ce9fff811c7612036d9265ef90707fa13"
)
EXPECTED_SR_LADDER_SHA256 = (
    "3c703f5f898e0a13c6eb8568c0b83f5"
    "b0d19d4e374155d2d3a8a4e20378bd51f"
)
EXPECTED_ENV_LOCK_SHA256 = (
    "f6f4a19c44a759705682ba4199207ea"
    "ef5c2435e1b6feeddc1e4654686bc2a8c"
)

EXPECTED_ARTIFACTS = {
    "final_raw_structural_feature_matrix",
    "final_species_balanced_percentile_feature_matrix",
    "corrected_species_mapping",
}


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


def array_sha256(values: np.ndarray) -> str:
    array = np.ascontiguousarray(
        values,
        dtype=np.float64,
    )

    return hashlib.sha256(
        array.tobytes(order="C")
    ).hexdigest()


def format_metric(value: float) -> str:
    return format(
        value,
        ".17g",
    )


def metric_names() -> list[str]:
    return [
        field.name
        for field in fields(CoverageSummary)
    ]


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
        "PASS | frozen final grouped-ablation definitions | "
        "4 groups | sizes=2,3,5,2"
    )


def load_final_geometry() -> tuple[
    np.ndarray,
    list[str],
    list[str],
]:
    manifest_hash = require_sha256(
        INPUT_MANIFEST,
        EXPECTED_INPUT_MANIFEST_SHA256,
    )

    artifacts = verify_input_manifest(
        INPUT_MANIFEST
    )

    observed_artifacts = {
        artifact.artifact
        for artifact in artifacts
    }

    if observed_artifacts != EXPECTED_ARTIFACTS:
        raise AssertionError(
            "final feature-space manifest artifact set changed"
        )

    paths = {
        artifact.artifact: artifact.path
        for artifact in artifacts
    }

    percentile_path = paths[
        "final_species_balanced_percentile_feature_matrix"
    ]
    species_path = paths[
        "corrected_species_mapping"
    ]

    percentile_hash = require_sha256(
        percentile_path,
        EXPECTED_PERCENTILE_MATRIX_SHA256,
    )

    species_hash = require_sha256(
        species_path,
        EXPECTED_SPECIES_MAPPING_SHA256,
    )

    with percentile_path.open(
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
                "final percentile feature schema changed"
            )

        percentile_rows = list(reader)

    with species_path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        species_fieldnames = set(
            reader.fieldnames or ()
        )

        required_species_columns = {
            ACCESSION_COLUMN,
            SPECIES_COLUMN,
        }

        if not required_species_columns.issubset(
            species_fieldnames
        ):
            raise AssertionError(
                "species mapping schema changed"
            )

        species_rows = list(reader)

    if len(percentile_rows) != EXPECTED_GENOMES:
        raise AssertionError(
            "final percentile feature row count changed"
        )

    if len(species_rows) != EXPECTED_GENOMES:
        raise AssertionError(
            "species mapping row count changed"
        )

    accessions = [
        row[ACCESSION_COLUMN]
        for row in percentile_rows
    ]

    mapping_accessions = [
        row[ACCESSION_COLUMN]
        for row in species_rows
    ]

    if accessions != mapping_accessions:
        raise AssertionError(
            "final feature and species accession order changed"
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

    if coordinates.shape != (
        EXPECTED_GENOMES,
        len(FEATURES),
    ):
        raise AssertionError(
            "final coordinate matrix shape changed: "
            f"{coordinates.shape}"
        )

    if not np.all(np.isfinite(coordinates)):
        raise AssertionError(
            "final coordinate matrix contains non-finite values"
        )

    observed_array_hash = array_sha256(
        coordinates
    )

    if (
        observed_array_hash
        != EXPECTED_PERCENTILE_ARRAY_SHA256
    ):
        raise AssertionError(
            "final percentile float64 C-order array changed: "
            f"{observed_array_hash}"
        )

    env_hash = require_sha256(
        ENV_LOCK,
        EXPECTED_ENV_LOCK_SHA256,
    )

    print(
        "PASS | frozen final feature-space input manifest | "
        f"{manifest_hash}"
    )
    print(
        "PASS | immutable final validation universe | "
        f"{EXPECTED_GENOMES} genomes | "
        f"{EXPECTED_SPECIES} species | "
        f"{len(FEATURES)} features"
    )
    print(
        "PASS | frozen final percentile matrix | "
        f"file={percentile_hash} | "
        f"float64_c_order={observed_array_hash}"
    )
    print(
        "PASS | frozen species mapping | "
        f"{species_hash}"
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


def full12_ladders(
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
            "frozen final OPS ladder fingerprint changed"
        )

    if sr_hash != EXPECTED_SR_LADDER_SHA256:
        raise AssertionError(
            "frozen final SR ladder fingerprint changed"
        )

    print(
        "PASS | frozen final blinded OPS ladder | "
        f"{ops_hash}"
    )
    print(
        "PASS | frozen final blinded SR ladder | "
        f"{sr_hash}"
    )

    return {
        "OPS": ops,
        "SR": sr,
    }


def load_frozen_reference_metrics() -> dict[
    tuple[int, str],
    dict[str, str],
]:
    metrics_hash = require_sha256(
        REFERENCE_METRICS,
        EXPECTED_REFERENCE_METRICS_SHA256,
    )

    names = metric_names()

    with REFERENCE_METRICS.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        reader = csv.DictReader(
            handle,
            delimiter="\t",
        )

        expected_header = [
            "N",
            "selector",
            *names,
        ]

        if list(reader.fieldnames or []) != expected_header:
            raise AssertionError(
                "frozen final reference-metrics schema changed"
            )

        rows = list(reader)

    if len(rows) != 12:
        raise AssertionError(
            "frozen final reference-metrics row count changed"
        )

    expected_keys = {
        (panel_size, selector)
        for panel_size in PANEL_SIZES
        for selector in ("OPS", "SR")
    }

    observed: dict[
        tuple[int, str],
        dict[str, str],
    ] = {}

    for row in rows:
        key = (
            int(row["N"]),
            row["selector"],
        )

        if key in observed:
            raise AssertionError(
                "duplicate frozen final reference-metrics key"
            )

        observed[key] = row

    if set(observed) != expected_keys:
        raise AssertionError(
            "frozen final reference-metrics key set changed"
        )

    print(
        "PASS | frozen final OPS/SR reference metrics | "
        f"{metrics_hash}"
    )

    return observed


def validate_reference_coverage(
    coordinates: np.ndarray,
    species_ids: list[str],
    references: dict[str, np.ndarray],
) -> None:
    frozen = load_frozen_reference_metrics()
    names = metric_names()

    for selector_name in (
        "OPS",
        "SR",
    ):
        summaries = evaluate_ladder(
            coordinates,
            species_ids,
            references[selector_name],
        )

        for panel_size in PANEL_SIZES:
            frozen_row = frozen[
                (
                    panel_size,
                    selector_name,
                )
            ]

            summary = summaries[
                panel_size
            ]

            for name in names:
                observed = format_metric(
                    getattr(
                        summary,
                        name,
                    )
                )

                expected = frozen_row[
                    name
                ]

                if observed != expected:
                    raise AssertionError(
                        "frozen final reference coverage changed | "
                        f"selector={selector_name} | "
                        f"N={panel_size} | "
                        f"metric={name} | "
                        f"expected={expected} | "
                        f"observed={observed}"
                    )

    print(
        "PASS | rebuilt frozen final OPS/SR coverage exactly | "
        "2 selectors x 6 N x 10 metrics"
    )


def build_report(
    coordinates: np.ndarray,
    species_ids: list[str],
    accessions: list[str],
    references: dict[str, np.ndarray],
) -> str:
    names = metric_names()

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
            *names,
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
                "final grouped-ablation coordinate shape changed"
            )

        if not np.all(
            np.isfinite(selection_coordinates)
        ):
            raise AssertionError(
                "final grouped-ablation coordinates "
                "contain non-finite values"
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
                    "final grouped-ablation ladder length changed"
                )

            if np.unique(ladder).size != MAX_N:
                raise AssertionError(
                    "final grouped-ablation ladder contains duplicates"
                )

            fingerprint = ladder_hash(
                (
                    "BacSelect-selector-v1|FINAL300-2400|"
                    "GROUPED|"
                    f"remove={group_name}|"
                    f"{selector_name}|ladder|N=500"
                ),
                ladder,
                accessions,
            )

            print(
                "PASS | blinded final grouped-ablation ladder | "
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
                                    name,
                                )
                            )
                            for name in names
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
            "final grouped-ablation row count changed: "
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
    ) = load_final_geometry()

    references = full12_ladders(
        coordinates,
        species_ids,
        accessions,
    )

    validate_reference_coverage(
        coordinates,
        species_ids,
        references,
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
        "PASS | complete final grouped-ablation report | "
        "4 groups x 2 selectors x 6 N"
    )
    print(
        "PASS | coverage evaluated in frozen final "
        "300/2400 full-12 geometry"
    )
    print(
        "PASS | identity-blind final grouped-ablation report"
    )
    print(
        f"final_grouped_ablation_sha256 | {output_hash}"
    )


if __name__ == "__main__":
    main()
