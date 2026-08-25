#!/usr/bin/env python3
"""Run final selector-level deterministic rebuild validation."""

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

from bacselect.ag import ag_ladder
from bacselect.geometry import species_balanced_percentile_matrix
from bacselect.metrics import (
    CoverageSummary,
    coverage_summary,
    nearest_panel_distances,
)
from bacselect.ops import ops_ladder
from bacselect.provenance import verify_input_manifest
from bacselect.sr import sr_ladder
from bacselect.tie import tie_key


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

METADATA_COLUMNS = (
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
)
ACCESSION_COLUMN = "canonical_genbank_assembly_accession"
SPECIES_COLUMN = "species_taxid"

PANEL_SIZES = (10, 20, 50, 100, 200, 500)
MAX_N = 500

INPUT_MANIFEST = Path(
    "validation/selector-v1/final-feature-space-inputs.tsv"
)
REFERENCE_METRICS = Path(
    "validation/selector-v1/results/final300-2400-ops-vs-sr-metrics.tsv"
)
ENV_LOCK = Path("envs/bacselect-dev-linux-64.lock")

EXPECTED_INPUT_MANIFEST_SHA256 = (
    "512d466ff6b8af3e51eb91db715d5fc5"
    "c76995892a4c1b18489d922a0414f0f2"
)
EXPECTED_RAW_FILE_SHA256 = (
    "86c0c3d49317dfc3cc452114e3863666"
    "fe2112b6a3ae8dae2090b60a2a598948"
)
EXPECTED_PERCENTILE_FILE_SHA256 = (
    "f48e20b28ee89988e7abb42488a35c62"
    "fbfa4a538c15c8d2d70b6b5ba7ae83c1"
)
EXPECTED_SPECIES_MAPPING_SHA256 = (
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha256(path: Path, expected: str) -> str:
    observed = file_sha256(path)
    if observed != expected:
        raise AssertionError(
            f"SHA256 changed for {path}: expected={expected} observed={observed}"
        )
    return observed


def array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values, dtype="<f8")
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def sequence_sha256(namespace: str, values: list[str]) -> str:
    payload = namespace + "\n" + "\n".join(values) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def format_metric(value: float) -> str:
    return format(value, ".17g")


def write_text_exact(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def metric_names() -> list[str]:
    return [field.name for field in fields(CoverageSummary)]


def load_inputs() -> tuple[np.ndarray, list[str], list[str]]:
    require_sha256(INPUT_MANIFEST, EXPECTED_INPUT_MANIFEST_SHA256)
    artifacts = verify_input_manifest(INPUT_MANIFEST)
    artifact_map = {artifact.artifact: artifact.path for artifact in artifacts}

    raw_path = artifact_map["final_raw_structural_feature_matrix"]
    percentile_path = artifact_map[
        "final_species_balanced_percentile_feature_matrix"
    ]
    species_path = artifact_map["corrected_species_mapping"]

    require_sha256(raw_path, EXPECTED_RAW_FILE_SHA256)
    require_sha256(percentile_path, EXPECTED_PERCENTILE_FILE_SHA256)
    require_sha256(species_path, EXPECTED_SPECIES_MAPPING_SHA256)
    require_sha256(ENV_LOCK, EXPECTED_ENV_LOCK_SHA256)
    require_sha256(REFERENCE_METRICS, EXPECTED_REFERENCE_METRICS_SHA256)

    with raw_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != (*METADATA_COLUMNS, *FEATURES):
            raise AssertionError("final raw feature schema changed")
        raw_rows = list(reader)

    with species_path.open(newline="", encoding="utf-8") as handle:
        species_rows = list(csv.DictReader(handle, delimiter="\t"))

    if len(raw_rows) != EXPECTED_GENOMES or len(species_rows) != EXPECTED_GENOMES:
        raise AssertionError("frozen universe row count changed")

    accessions = [row[ACCESSION_COLUMN] for row in raw_rows]
    mapping_accessions = [row[ACCESSION_COLUMN] for row in species_rows]
    if accessions != mapping_accessions:
        raise AssertionError("raw/species accession order changed")
    if len(set(accessions)) != EXPECTED_GENOMES:
        raise AssertionError("accessions are not unique")

    species_ids = [row[SPECIES_COLUMN] for row in species_rows]
    if len(set(species_ids)) != EXPECTED_SPECIES:
        raise AssertionError("species count changed")

    raw = np.asarray(
        [[float(row[feature]) for feature in FEATURES] for row in raw_rows],
        dtype=np.float64,
    )
    if raw.shape != (EXPECTED_GENOMES, len(FEATURES)):
        raise AssertionError(f"raw matrix shape changed: {raw.shape}")

    if array_sha256(raw) != EXPECTED_RAW_ARRAY_SHA256:
        raise AssertionError("frozen raw float64 array changed")

    print(
        "PASS | frozen final deterministic-rebuild inputs | "
        f"{EXPECTED_GENOMES} genomes | {EXPECTED_SPECIES} species | 12 features"
    )
    return raw, species_ids, accessions


def recompute_coordinates(
    raw: np.ndarray,
    species_ids: list[str],
) -> np.ndarray:
    coordinates = species_balanced_percentile_matrix(raw, species_ids)
    observed = array_sha256(coordinates)
    if observed != EXPECTED_PERCENTILE_ARRAY_SHA256:
        raise AssertionError(
            "recomputed final percentile array changed: "
            f"expected={EXPECTED_PERCENTILE_ARRAY_SHA256} observed={observed}"
        )
    print(
        "PASS | recomputed frozen final percentile array exactly | "
        f"{observed}"
    )
    return coordinates


def ladder_fingerprint(
    selector: str,
    ladder: np.ndarray,
    accessions: list[str],
) -> str:
    values = [accessions[int(index)] for index in ladder]
    return sequence_sha256(
        f"BacSelect-selector-v1|final300-2400|{selector}|ladder|N=500",
        values,
    )


def evaluate(
    coordinates: np.ndarray,
    species_ids: list[str],
    ladder: np.ndarray,
) -> dict[int, CoverageSummary]:
    return {
        n: coverage_summary(
            nearest_panel_distances(coordinates, ladder[:n]),
            species_ids,
        )
        for n in PANEL_SIZES
    }


def load_reference_metrics() -> dict[tuple[str, int], dict[str, str]]:
    with REFERENCE_METRICS.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if len(rows) != 12:
        raise AssertionError("frozen OPS/SR reference metric row count changed")
    return {(row["selector"], int(row["N"])): row for row in rows}


def serialize_matrix(
    coordinates: np.ndarray,
    accessions: list[str],
) -> str:
    order = sorted(range(len(accessions)), key=lambda i: tie_key(accessions[i]))
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(list(FEATURES))
    for index in order:
        writer.writerow(
            [format_metric(float(value)) for value in coordinates[index]]
        )
    return buffer.getvalue()


def serialize_ladders(
    ladders: dict[str, np.ndarray],
    accessions: list[str],
) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["selector", "max_n", "ladder_sha256"])
    for selector in ("OPS", "SR", "AG"):
        fingerprint = ladder_fingerprint(
            selector,
            ladders[selector],
            accessions,
        )
        writer.writerow([selector, MAX_N, fingerprint])
    return buffer.getvalue()


def serialize_coverage(
    summaries: dict[str, dict[int, CoverageSummary]],
) -> str:
    names = metric_names()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
    writer.writerow(["selector", "N", *names])
    for selector in ("OPS", "SR", "AG"):
        for n in PANEL_SIZES:
            summary = summaries[selector][n]
            writer.writerow(
                [
                    selector,
                    n,
                    *[
                        format_metric(getattr(summary, name))
                        for name in names
                    ],
                ]
            )
    return buffer.getvalue()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-inputs-only", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw, species_ids, accessions = load_inputs()

    if args.verify_inputs_only:
        if args.output_dir is not None:
            raise ValueError("--output-dir must not be used with --verify-inputs-only")
        print(
            "PASS | verification only | "
            "no deterministic-rebuild scientific output calculated"
        )
        return

    if args.output_dir is None:
        raise ValueError("--output-dir is required")

    output_dir = args.output_dir
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite: {output_dir}")
    output_dir.mkdir(parents=True)

    coordinates = recompute_coordinates(raw, species_ids)

    ops = ops_ladder(coordinates, species_ids, accessions, max_n=MAX_N)
    sr = sr_ladder(coordinates, species_ids, accessions, max_n=MAX_N)
    ag = ag_ladder(coordinates, accessions, max_n=MAX_N)

    ops_hash = ladder_fingerprint("OPS", ops, accessions)
    sr_hash = ladder_fingerprint("SR", sr, accessions)

    if ops_hash != EXPECTED_OPS_LADDER_SHA256:
        raise AssertionError("frozen final OPS ladder fingerprint changed")
    if sr_hash != EXPECTED_SR_LADDER_SHA256:
        raise AssertionError("frozen final SR ladder fingerprint changed")

    print(f"PASS | frozen final OPS ladder | {ops_hash}")
    print(f"PASS | frozen final SR ladder | {sr_hash}")

    ladders = {"OPS": ops, "SR": sr, "AG": ag}
    summaries = {
        selector: evaluate(coordinates, species_ids, ladder)
        for selector, ladder in ladders.items()
    }

    reference = load_reference_metrics()
    names = metric_names()
    for selector in ("OPS", "SR"):
        for n in PANEL_SIZES:
            row = reference[(selector, n)]
            for name in names:
                observed = format_metric(getattr(summaries[selector][n], name))
                if observed != row[name]:
                    raise AssertionError(
                        "frozen final reference coverage changed | "
                        f"selector={selector} N={n} metric={name}"
                    )

    print(
        "PASS | rebuilt frozen final OPS/SR coverage exactly | "
        "2 selectors x 6 N x 10 metrics"
    )

    matrix_text = serialize_matrix(coordinates, accessions)
    ladder_text = serialize_ladders(ladders, accessions)
    coverage_text = serialize_coverage(summaries)

    matrix_path = output_dir / "final-determinism-percentile-matrix.tsv"
    ladder_path = output_dir / "final-determinism-ladders.tsv"
    coverage_path = output_dir / "final-determinism-coverage.tsv"
    report_path = output_dir / "final-determinism-report.json"

    write_text_exact(matrix_path, matrix_text)
    write_text_exact(ladder_path, ladder_text)
    write_text_exact(coverage_path, coverage_text)

    scientific_hashes = {
        "percentile_matrix": file_sha256(matrix_path),
        "ladders": file_sha256(ladder_path),
        "coverage": file_sha256(coverage_path),
    }

    report = {
        "analysis": "selector-v1-final-deterministic-rebuild",
        "schema_version": 1,
        "genomes": EXPECTED_GENOMES,
        "species": EXPECTED_SPECIES,
        "features": list(FEATURES),
        "panel_sizes": list(PANEL_SIZES),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "input_sha256": {
            "manifest": EXPECTED_INPUT_MANIFEST_SHA256,
            "raw_file": EXPECTED_RAW_FILE_SHA256,
            "species_mapping": EXPECTED_SPECIES_MAPPING_SHA256,
            "reference_metrics": EXPECTED_REFERENCE_METRICS_SHA256,
            "environment_lock": EXPECTED_ENV_LOCK_SHA256,
        },
        "array_sha256": {
            "raw_float64_c_order": EXPECTED_RAW_ARRAY_SHA256,
            "recomputed_percentile_float64_c_order":
                EXPECTED_PERCENTILE_ARRAY_SHA256,
        },
        "reference_ladder_sha256": {
            "OPS": ops_hash,
            "SR": sr_hash,
        },
        "scientific_output_sha256": scientific_hashes,
        "identity_blinding": "REQUIRED",
        "selector_decision_rule_introduced": False,
    }
    write_text_exact(
        report_path,
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )

    print("===== scientific output SHA256 =====")
    for path in (matrix_path, ladder_path, coverage_path, report_path):
        print(f"{file_sha256(path)}  {path}")
    print("PASS | final selector-level deterministic rebuild completed")


if __name__ == "__main__":
    main()
