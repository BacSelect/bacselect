#!/usr/bin/env python3
"""Run blinded final-300/2400 selector-v1 leave-one-feature-out validation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
from dataclasses import fields
from pathlib import Path

import numpy as np

from bacselect.ablation import (
    panel_overlap_count,
    remove_feature_column,
)
from bacselect.metrics import (
    CoverageSummary,
    coverage_summary,
    nearest_panel_distances,
)
from bacselect.ops import ops_ladder
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

FINAL_INPUT_MANIFEST = Path(
    "validation/selector-v1/"
    "final-feature-space-inputs.tsv"
)

EXPECTED_FINAL_INPUT_MANIFEST_SHA256 = (
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

REFERENCE_METRICS = Path(
    "validation/selector-v1/results/"
    "final300-2400-ops-vs-sr-metrics.tsv"
)

EXPECTED_REFERENCE_METRICS_SHA256 = (
    "9cd2cc838cb74a044e356a1a418633ef"
    "2bdc89c4e9f71f924e4c1c0a79073388"
)

REFERENCE_SUMMARY = Path(
    "validation/selector-v1/results/"
    "final300-2400-ops-vs-sr-summary.json"
)

EXPECTED_REFERENCE_SUMMARY_SHA256 = (
    "4908739ac15bd2e842acb83bba6588ad"
    "7c2dc29be78a6a57b500709b33e16cf6"
)

EXPECTED_REFERENCE_ANALYSIS_COMMIT = (
    "ea547dbe7eeffbd5ce426c7ca5cb4347d8a1bc9d"
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
    if not path.is_file():
        raise FileNotFoundError(
            f"required file is missing: {path}"
        )

    observed = file_sha256(path)

    if observed != expected:
        raise AssertionError(
            "SHA256 changed for "
            f"{path}: expected {expected}, "
            f"observed {observed}"
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


def load_final_input_manifest() -> dict[str, Path]:
    require_sha256(
        FINAL_INPUT_MANIFEST,
        EXPECTED_FINAL_INPUT_MANIFEST_SHA256,
    )

    with FINAL_INPUT_MANIFEST.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    expected_artifacts = {
        "final_raw_structural_feature_matrix",
        "final_species_balanced_percentile_feature_matrix",
        "corrected_species_mapping",
    }

    observed_artifacts = {
        row["artifact"]
        for row in rows
    }

    if observed_artifacts != expected_artifacts:
        raise AssertionError(
            "final feature-space input manifest "
            "artifact set changed"
        )

    by_artifact = {
        row["artifact"]: row
        for row in rows
    }

    percentile_row = by_artifact[
        "final_species_balanced_percentile_feature_matrix"
    ]
    species_row = by_artifact[
        "corrected_species_mapping"
    ]

    if percentile_row["sha256"] != EXPECTED_PERCENTILE_MATRIX_SHA256:
        raise AssertionError(
            "percentile matrix manifest SHA256 changed"
        )

    if species_row["sha256"] != EXPECTED_SPECIES_MAPPING_SHA256:
        raise AssertionError(
            "species mapping manifest SHA256 changed"
        )

    if int(percentile_row["data_rows"]) != EXPECTED_GENOMES:
        raise AssertionError(
            "percentile matrix manifest row count changed"
        )

    if int(species_row["data_rows"]) != EXPECTED_GENOMES:
        raise AssertionError(
            "species mapping manifest row count changed"
        )

    paths = {
        "coordinates": Path(
            percentile_row["path"]
        ),
        "species": Path(
            species_row["path"]
        ),
    }

    require_sha256(
        paths["coordinates"],
        EXPECTED_PERCENTILE_MATRIX_SHA256,
    )
    require_sha256(
        paths["species"],
        EXPECTED_SPECIES_MAPPING_SHA256,
    )

    return paths


def load_final_geometry() -> tuple[
    np.ndarray,
    list[str],
    list[str],
]:
    paths = load_final_input_manifest()

    with paths["coordinates"].open(
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

        coordinate_rows = list(reader)

    with paths["species"].open(
        newline="",
        encoding="utf-8",
    ) as handle:
        species_rows = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    if len(coordinate_rows) != EXPECTED_GENOMES:
        raise AssertionError(
            "final coordinate row count changed"
        )

    if len(species_rows) != EXPECTED_GENOMES:
        raise AssertionError(
            "species mapping row count changed"
        )

    accessions = [
        row[ACCESSION_COLUMN]
        for row in coordinate_rows
    ]

    mapping_accessions = [
        row[ACCESSION_COLUMN]
        for row in species_rows
    ]

    if accessions != mapping_accessions:
        raise AssertionError(
            "coordinate and species accession order changed"
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
            for row in coordinate_rows
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

    if not np.all(
        np.isfinite(
            coordinates
        )
    ):
        raise AssertionError(
            "final coordinate matrix contains "
            "non-finite values"
        )

    if np.any(
        coordinates < 0.0
    ) or np.any(
        coordinates > 1.0
    ):
        raise AssertionError(
            "final percentile coordinates outside [0, 1]"
        )

    env_hash = require_sha256(
        ENV_LOCK,
        EXPECTED_ENV_LOCK_SHA256,
    )

    print(
        "PASS | frozen final validation universe | "
        f"{EXPECTED_GENOMES} genomes | "
        f"{EXPECTED_SPECIES} species | "
        f"{len(FEATURES)} features"
    )

    print(
        "PASS | frozen final percentile geometry | "
        f"{EXPECTED_PERCENTILE_MATRIX_SHA256}"
    )

    print(
        "PASS | frozen species mapping | "
        f"{EXPECTED_SPECIES_MAPPING_SHA256}"
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
    selector_name: str,
    ladder: np.ndarray,
    accessions: list[str],
) -> str:
    ladder_accessions = [
        accessions[int(index)]
        for index in ladder
    ]

    return sequence_sha256(
        (
            "BacSelect-selector-v1|"
            "final300-2400|"
            f"{selector_name}|ladder|N=500"
        ),
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


def load_expected_reference_metrics() -> dict[
    tuple[int, str],
    dict[str, str],
]:
    require_sha256(
        REFERENCE_METRICS,
        EXPECTED_REFERENCE_METRICS_SHA256,
    )

    require_sha256(
        REFERENCE_SUMMARY,
        EXPECTED_REFERENCE_SUMMARY_SHA256,
    )

    summary = json.loads(
        REFERENCE_SUMMARY.read_text(
            encoding="utf-8",
        )
    )

    if (
        summary.get("analysis_commit")
        != EXPECTED_REFERENCE_ANALYSIS_COMMIT
    ):
        raise AssertionError(
            "final OPS/SR evidence-generation "
            "commit changed"
        )

    if summary.get(
        "secondary_interpretation_evaluated"
    ) is not False:
        raise AssertionError(
            "unexpected secondary interpretation state"
        )

    if summary.get(
        "new_decision_criterion_introduced"
    ) is not False:
        raise AssertionError(
            "unexpected selector decision criterion state"
        )

    with REFERENCE_METRICS.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )

    if len(rows) != 12:
        raise AssertionError(
            "final OPS/SR reference metric row count changed"
        )

    expected_keys = {
        (panel_size, selector)
        for panel_size in PANEL_SIZES
        for selector in ("OPS", "SR")
    }

    result = {
        (
            int(row["N"]),
            row["selector"],
        ): row
        for row in rows
    }

    if set(result) != expected_keys:
        raise AssertionError(
            "final OPS/SR reference metric keys changed"
        )

    return result


def build_reference_ladders(
    coordinates: np.ndarray,
    species_ids: list[str],
    accessions: list[str],
) -> tuple[
    dict[str, np.ndarray],
    dict[str, str],
]:
    expected_metrics = (
        load_expected_reference_metrics()
    )

    ladders: dict[str, np.ndarray] = {}
    hashes: dict[str, str] = {}

    metric_names = [
        field.name
        for field in fields(CoverageSummary)
    ]

    for selector_name in (
        "OPS",
        "SR",
    ):
        if selector_name == "OPS":
            ladder = ops_ladder(
                coordinates,
                species_ids,
                accessions,
                max_n=MAX_N,
            )
        else:
            ladder = sr_ladder(
                coordinates,
                species_ids,
                accessions,
                max_n=MAX_N,
            )

        if ladder.size != MAX_N:
            raise AssertionError(
                "reference ladder length changed"
            )

        if np.unique(ladder).size != MAX_N:
            raise AssertionError(
                "reference ladder contains duplicates"
            )

        summaries = evaluate_ladder(
            coordinates,
            species_ids,
            ladder,
        )

        for panel_size in PANEL_SIZES:
            expected = expected_metrics[
                (
                    panel_size,
                    selector_name,
                )
            ]

            summary = summaries[
                panel_size
            ]

            for metric_name in metric_names:
                observed = format_metric(
                    getattr(
                        summary,
                        metric_name,
                    )
                )

                if observed != expected[
                    metric_name
                ]:
                    raise AssertionError(
                        "rebuilt full-feature "
                        "reference metric changed | "
                        f"selector={selector_name} | "
                        f"N={panel_size} | "
                        f"metric={metric_name} | "
                        f"expected={expected[metric_name]} | "
                        f"observed={observed}"
                    )

        fingerprint = ladder_hash(
            selector_name,
            ladder,
            accessions,
        )

        ladders[selector_name] = ladder
        hashes[selector_name] = fingerprint

        print(
            "PASS | rebuilt frozen final reference ladder | "
            f"selector={selector_name} | "
            f"{fingerprint}"
        )

    print(
        "PASS | rebuilt reference coverage matches "
        "frozen final OPS/SR evidence exactly"
    )

    return (
        ladders,
        hashes,
    )


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
            "removed_feature",
            "selector",
            "N",
            "ablation_ladder_sha256",
            "overlap_count",
            "overlap_fraction",
            *metric_names,
        ]
    )

    row_count = 0

    for feature_index, feature_name in enumerate(
        FEATURES
    ):
        selection_coordinates = (
            remove_feature_column(
                coordinates,
                feature_index,
            )
        )

        if selection_coordinates.shape != (
            EXPECTED_GENOMES,
            len(FEATURES) - 1,
        ):
            raise AssertionError(
                "ablated coordinate shape changed"
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
                    "ablated ladder length changed"
                )

            if np.unique(ladder).size != MAX_N:
                raise AssertionError(
                    "ablated ladder contains duplicates"
                )

            ladder_accessions = [
                accessions[int(index)]
                for index in ladder
            ]

            fingerprint = sequence_sha256(
                (
                    "BacSelect-selector-v1|"
                    "final300-2400|LOFO|"
                    f"remove={feature_name}|"
                    f"{selector_name}|ladder|N=500"
                ),
                ladder_accessions,
            )

            print(
                "PASS | blinded final LOFO ladder | "
                f"remove={feature_name} | "
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
                        feature_name,
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
        len(FEATURES)
        * 2
        * len(PANEL_SIZES)
    )

    if row_count != expected_rows:
        raise AssertionError(
            f"final LOFO row count changed: {row_count}"
        )

    text = buffer.getvalue()

    for token in (
        "GCA_",
        "GCF_",
    ):
        if token in text:
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

    (
        coordinates,
        species_ids,
        accessions,
    ) = load_final_geometry()

    (
        references,
        reference_hashes,
    ) = build_reference_ladders(
        coordinates,
        species_ids,
        accessions,
    )

    print(
        "environment | "
        f"python={platform.python_version()} | "
        f"numpy={np.__version__}"
    )

    print(
        "reference_ladder_sha256 | "
        f"OPS={reference_hashes['OPS']} | "
        f"SR={reference_hashes['SR']}"
    )

    if args.verify_inputs_only:
        if args.output is not None:
            raise ValueError(
                "--output must not be supplied with "
                "--verify-inputs-only"
            )

        print(
            "PASS | verification only | "
            "no 11-feature selector calculated"
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
        "PASS | complete final LOFO report | "
        "12 features x 2 selectors x 6 N"
    )
    print(
        "PASS | coverage evaluated in frozen "
        "final 300/2400 full-12 geometry"
    )
    print(
        "PASS | identity-blind final LOFO report"
    )
    print(
        f"final_lofo_sha256 | {output_hash}"
    )


if __name__ == "__main__":
    main()
