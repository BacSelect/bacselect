#!/usr/bin/env python3
"""Blinded prospective coverage comparison of OPS and SR."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import fields
from pathlib import Path

import numpy as np

from bacselect.geometry import species_balanced_percentile_matrix
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
EXPECTED_FEATURES = 12

PANEL_SIZES = (10, 20, 50, 100, 200, 500)
MAX_N = max(PANEL_SIZES)

EXPECTED_OPS_LADDER_SHA256 = (
    "3f9a7c4557268fad829b078de9679cda"
    "4ee26a81982c1aed71fc066f8290f3b8"
)

EXPECTED_SR_LADDER_SHA256 = (
    "dbe0174a5e96202e7d755ac616318c5e"
    "6007939b5062a3f5b9dabea0a8bfe5e8"
)

ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"


def sequence_sha256(namespace: str, values: list[str]) -> str:
    """Return an identity-blinded fingerprint of an ordered sequence."""
    payload = namespace + "\n" + "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def format_metric(value: float) -> str:
    """Return deterministic high-precision text for one binary64 metric."""
    return format(value, ".17g")


def load_foundation() -> tuple[
    np.ndarray,
    list[str],
    list[str],
]:
    """Load and verify the frozen Finch validation foundation."""
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

    raw_matrix = np.asarray(
        [
            [
                float(row[feature])
                for feature in feature_names
            ]
            for row in raw_rows
        ],
        dtype=np.float64,
    )

    coordinates = species_balanced_percentile_matrix(
        raw_matrix,
        species_ids,
    )

    return coordinates, species_ids, accessions


def validate_ladder_hash(
    selector: str,
    ladder: np.ndarray,
    accessions: list[str],
    expected_hash: str,
) -> str:
    """Require a candidate ladder to match its frozen blinded fingerprint."""
    ladder_accessions = [
        accessions[int(index)]
        for index in ladder
    ]

    observed_hash = sequence_sha256(
        f"BacSelect-selector-v1|{selector}|ladder|N=500",
        ladder_accessions,
    )

    assert observed_hash == expected_hash, (
        f"{selector} ladder fingerprint changed: "
        f"{observed_hash}"
    )

    return observed_hash


def evaluate_ladder(
    coordinates: np.ndarray,
    species_ids: list[str],
    ladder: np.ndarray,
) -> dict[int, CoverageSummary]:
    """Calculate all pre-specified coverage metrics at each validation N."""
    summaries: dict[int, CoverageSummary] = {}

    for panel_size in PANEL_SIZES:
        distances = nearest_panel_distances(
            coordinates,
            ladder[:panel_size],
        )

        summaries[panel_size] = coverage_summary(
            distances,
            species_ids,
        )

    return summaries


def main() -> None:
    coordinates, species_ids, accessions = load_foundation()

    print(
        f"PASS | immutable validation universe | "
        f"{EXPECTED_GENOMES} genomes | "
        f"{EXPECTED_SPECIES} species | "
        f"{EXPECTED_FEATURES} features"
    )

    ops = ops_ladder(
        coordinates,
        species_ids,
        accessions,
        max_n=MAX_N,
    )

    ops_hash = validate_ladder_hash(
        "OPS",
        ops,
        accessions,
        EXPECTED_OPS_LADDER_SHA256,
    )

    print(
        "PASS | frozen blinded OPS ladder fingerprint | "
        f"{ops_hash}"
    )

    sr = sr_ladder(
        coordinates,
        species_ids,
        accessions,
        max_n=MAX_N,
    )

    sr_hash = validate_ladder_hash(
        "SR",
        sr,
        accessions,
        EXPECTED_SR_LADDER_SHA256,
    )

    print(
        "PASS | frozen blinded SR ladder fingerprint | "
        f"{sr_hash}"
    )

    ops_metrics = evaluate_ladder(
        coordinates,
        species_ids,
        ops,
    )

    sr_metrics = evaluate_ladder(
        coordinates,
        species_ids,
        sr,
    )

    print()
    print("PRIMARY")
    print(
        "N\tOPS_weighted_p95\tSR_weighted_p95\t"
        "lower\tSR_minus_OPS"
    )

    primary_winners: list[str] = []

    for panel_size in PANEL_SIZES:
        ops_value = ops_metrics[panel_size].weighted_p95
        sr_value = sr_metrics[panel_size].weighted_p95

        if ops_value < sr_value:
            lower = "OPS"
        elif sr_value < ops_value:
            lower = "SR"
        else:
            lower = "TIE"

        primary_winners.append(lower)

        print(
            f"{panel_size}\t"
            f"{format_metric(ops_value)}\t"
            f"{format_metric(sr_value)}\t"
            f"{lower}\t"
            f"{format_metric(sr_value - ops_value)}"
        )

    print()
    print("SECONDARY")

    metric_names = [
        field.name
        for field in fields(CoverageSummary)
    ]

    print("N\tselector\t" + "\t".join(metric_names))

    for panel_size in PANEL_SIZES:
        for selector, summaries in (
            ("OPS", ops_metrics),
            ("SR", sr_metrics),
        ):
            summary = summaries[panel_size]

            values = [
                format_metric(getattr(summary, name))
                for name in metric_names
            ]

            print(
                f"{panel_size}\t{selector}\t"
                + "\t".join(values)
            )

    print()
    print("DECISION-RULE STATUS")

    if all(winner == "OPS" for winner in primary_winners):
        status = "OPS_LOWER_AT_ALL_SIX_N"
    elif all(winner == "SR" for winner in primary_winners):
        status = "SR_LOWER_AT_ALL_SIX_N"
    elif all(winner == "TIE" for winner in primary_winners):
        status = "PRIMARY_TIE_AT_ALL_SIX_N"
    else:
        status = "PRIMARY_CURVES_NOT_UNIFORMLY_ORDERED"

    print(f"primary_status\t{status}")

    print()
    print("PASS | comparison remained identity-blinded")


if __name__ == "__main__":
    main()
