#!/usr/bin/env python3
"""
Independent fail-closed audit of the BacSelect selector-v1 alternative-k
repeat-scale full production universe (batches 001-111).

The audit is read-only with respect to:
  - the BacSelect scientific repository,
  - production outputs,
  - frozen target/reference inputs,
  - the frozen NCBI sequence-validation snapshot.

It writes only to --report-dir.

Checks include:
  * exact Git commit / origin/main / clean working tree;
  * frozen target, reference, source-audit and production-input hashes;
  * all tracked production-input hashes listed in the manifest;
  * frozen source-batch audit hashes for batches 001-111;
  * exact full-universe manifest membership and batch_index values;
  * batch summary and run-provenance schemas and cryptographic links;
  * candidate-results.tsv schema, order, membership and candidate SHA256;
  * exact 13-k grid and three repeat-feature families for every candidate;
  * integer/count/range/fraction consistency for every k;
  * candidate source metadata against the frozen target manifest;
  * actual FASTA and sequence-report file SHA256 against candidate provenance;
  * embedded k=150/400 reference anchors against both features_by_k and the
    frozen corrected reference matrix;
  * no missing, unexpected or duplicate full-universe candidate outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED = {
    "analysis": "selector-v1-repeat-scale-grid",
    "schema_version": 1,
    "git_head": "83516de6cd3713415e78502ba58db072fa6b38f9",
    "target_manifest_sha256": (
        "bc4acba1384524f956887d02d2f54aa7e501a2c23e2930b779a4e6520d8fcee1"
    ),
    "reference_matrix_sha256": (
        "fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656"
    ),
    "source_audit_manifest_sha256": (
        "21c5d5287bc909fd47d76c62b2d7848b55bb987b0389639aae54442aac885183"
    ),
    "production_inputs_manifest_sha256": (
        "692a26945983b05cf1d84a2540e5837a82a5a95543ef5fe75f425c601be1c352"
    ),
    "worker_sha256": (
        "49f4ffd22edb1116fc34e520c9eb1094f837b9d2c2a24780138fd2fee5011527"
    ),
    "repeat_scale_module_sha256": (
        "7dcd0cab3da9698ca4a697315326bc303e30c96d3b3ed12e48b627287a3b6f6c"
    ),
    "repeat_concordance_module_sha256": (
        "6dc25a2d382ebdf0a5c6327b211bb4dae064363727b42864a725b626bb325a51"
    ),
    "repeat_scale_method_sha256": (
        "2897282450221e662bb1d6c1142da7c999e07e23c21d66f265cbf2fe13313d01"
    ),
    "finch_driver_sha256": (
        "e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50"
    ),
    "finch_basic_sha256": (
        "30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a"
    ),
    "engine_source_sha256": (
        "bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925"
    ),
    "engine_sha256": (
        "e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968"
    ),
    "environment_lock_sha256": (
        "aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f"
    ),
    "all_target_rows": 55306,
    "all_batches": 111,
    "full_universe_batches": 111,
    "full_universe_targets": 55306,
}

K_VALUES = [
    50,
    75,
    100,
    150,
    200,
    300,
    400,
    600,
    800,
    1200,
    1600,
    2400,
    3200,
]

K_KEYS = {str(k) for k in K_VALUES}

FAMILIES = [
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_fraction",
]

FEATURE_FIELDS = {
    "valid_start_count",
    "non_unique_start_count",
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_start_count",
    "inter_replicon_shared_fraction",
}

ANCHOR_FIELDS = {
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
}

ANCHOR_TO_GRID = {
    "06_non_unique_canonical_150mer_fraction": ("150", "non_unique_fraction"),
    "07_non_unique_canonical_400mer_fraction": ("400", "non_unique_fraction"),
    "08_maximum_canonical_150mer_multiplicity": ("150", "maximum_multiplicity"),
    "09_maximum_canonical_400mer_multiplicity": ("400", "maximum_multiplicity"),
    "11_inter_replicon_shared_canonical_150mer_fraction": (
        "150",
        "inter_replicon_shared_fraction",
    ),
    "12_inter_replicon_shared_canonical_400mer_fraction": (
        "400",
        "inter_replicon_shared_fraction",
    ),
}

TARGET_HEADER = [
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
    "total_sequence_length",
    "primary_assembly_records",
    "topology_circular_records",
    "topology_linear_records",
]

RESULTS_HEADER = [
    "position",
    "batch_index",
    "accession",
    "output_file",
    "output_sha256",
]

SOURCE_AUDIT_HEADER = [
    "batch",
    "batch_summary_sha256",
    "candidate_sequence_audit_sha256",
    "component_sequence_audit_sha256",
    "package_files_sha256",
]

SOURCE_AUDIT_FILES = {
    "batch_summary_sha256": "batch-summary.json",
    "candidate_sequence_audit_sha256": "candidate-sequence-audit.tsv",
    "component_sequence_audit_sha256": "component-sequence-audit.tsv",
    "package_files_sha256": "package-files.tsv",
}

PROVENANCE_KEYS = {
    "analysis",
    "batch",
    "engine_sha256",
    "engine_source_sha256",
    "environment_lock_sha256",
    "finch_basic_sha256",
    "finch_driver_sha256",
    "git_head",
    "k_values",
    "production_inputs_manifest_sha256",
    "reference_matrix_sha256",
    "repeat_concordance_module_sha256",
    "repeat_feature_families",
    "repeat_scale_method_sha256",
    "repeat_scale_module_sha256",
    "schema_version",
    "source_audit_manifest_sha256",
    "target_manifest_sha256",
    "worker_sha256",
}

SUMMARY_KEYS = {
    "all_pass",
    "analysis",
    "batch",
    "candidate_results_sha256",
    "k_values",
    "reference_anchor_pass_count",
    "repeat_feature_families",
    "run_provenance_sha256",
    "schema_version",
    "target_count",
}

CANDIDATE_KEYS = {
    "analysis",
    "batch",
    "batch_index",
    "canonical_genbank_assembly_accession",
    "features_by_k",
    "k_values",
    "reference_anchor",
    "repeat_feature_families",
    "schema_version",
    "source",
}

ANCHOR_KEYS = {
    "k_values",
    "mismatches",
    "observed",
    "passed",
}

SOURCE_KEYS = {
    "genomic_fasta_file",
    "genomic_fasta_sha256",
    "primary_assembly_records",
    "sequence_report_file",
    "sequence_report_sha256",
    "topology_circular_records",
    "topology_linear_records",
    "total_sequence_length",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def same_number(left: Any, right: Any) -> bool:
    if is_int(left) and is_int(right):
        return left == right
    if not finite_number(left) or not finite_number(right):
        return False
    return math.isclose(
        float(left),
        float(right),
        rel_tol=0.0,
        abs_tol=1e-15,
    )


def parse_args() -> argparse.Namespace:
    home = Path.home()
    commit = EXPECTED["git_head"]

    parser = argparse.ArgumentParser(
        description=(
            "Independent full-universe audit of BacSelect selector-v1 "
            "alternative-k repeat-scale production."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/"
            f"alternative-k-grid/{commit}/production"
        ),
    )
    parser.add_argument(
        "--target-manifest",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/"
            "concordance-inputs/repeat-concordance-targets.tsv"
        ),
    )
    parser.add_argument(
        "--reference-matrix",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/"
            "corrected-eligible-percentile-feature-space/"
            "corrected-eligible-structural-feature-matrix.tsv"
        ),
    )
    parser.add_argument(
        "--source-snapshot-root",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/"
            "ncbi-sequence-validation-snapshot"
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=home / "github" / "bacselect",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=home / "bacselect-repeat-scale-full-universe-audit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    root = args.root.expanduser().resolve()
    target_manifest = args.target_manifest.expanduser().resolve()
    reference_matrix = args.reference_matrix.expanduser().resolve()
    source_snapshot_root = args.source_snapshot_root.expanduser().resolve()
    repo = args.repo.expanduser().resolve()
    report_dir = args.report_dir.expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    source_audit_manifest = (
        repo / "validation/selector-v1/repeat-scale-source-snapshot.tsv"
    )
    production_inputs_manifest = (
        repo / "validation/selector-v1/repeat-scale-production-inputs.sha256"
    )

    errors: list[str] = []
    warnings: list[str] = []
    batch_report: list[dict[str, Any]] = []
    candidate_report: list[dict[str, Any]] = []

    started = datetime.now(timezone.utc)

    def fail(message: str) -> None:
        errors.append(message)

    def check_equal(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            fail(f"{label}: expected {expected!r}, observed {actual!r}")

    # ------------------------------------------------------------------
    # Repository and immutable top-level inputs
    # ------------------------------------------------------------------

    try:
        check_equal(
            "repository HEAD",
            run_git(repo, "rev-parse", "HEAD"),
            EXPECTED["git_head"],
        )
        check_equal(
            "repository origin/main",
            run_git(repo, "rev-parse", "origin/main"),
            EXPECTED["git_head"],
        )
        status = run_git(repo, "status", "--porcelain")
        if status:
            fail("scientific repository working tree is not clean")
    except Exception as exc:
        fail(f"repository validation failed: {exc}")

    immutable_hashes = [
        (
            target_manifest,
            EXPECTED["target_manifest_sha256"],
            "target manifest",
        ),
        (
            reference_matrix,
            EXPECTED["reference_matrix_sha256"],
            "reference matrix",
        ),
        (
            source_audit_manifest,
            EXPECTED["source_audit_manifest_sha256"],
            "source-audit manifest",
        ),
        (
            production_inputs_manifest,
            EXPECTED["production_inputs_manifest_sha256"],
            "production-input manifest",
        ),
    ]

    for path, expected_hash, label in immutable_hashes:
        if not path.is_file():
            fail(f"{label} missing: {path}")
            continue
        try:
            observed = sha256_file(path)
            check_equal(f"{label} SHA256", observed, expected_hash)
        except Exception as exc:
            fail(f"could not hash {label}: {exc}")

    # Verify every file listed in the committed production-input manifest.
    if production_inputs_manifest.is_file():
        try:
            for line_number, raw in enumerate(
                production_inputs_manifest.read_text(encoding="utf-8").splitlines(),
                start=1,
            ):
                if not raw.strip():
                    continue
                parts = raw.split(None, 1)
                if len(parts) != 2:
                    fail(
                        f"production-input manifest line {line_number}: "
                        "invalid checksum row"
                    )
                    continue
                expected_hash, relpath = parts
                relpath = relpath.strip()
                path = repo / relpath
                if not SHA256_RE.fullmatch(expected_hash):
                    fail(
                        f"production-input manifest line {line_number}: "
                        "invalid SHA256"
                    )
                    continue
                if not path.is_file():
                    fail(f"production input missing: {relpath}")
                    continue
                actual = sha256_file(path)
                if actual != expected_hash:
                    fail(
                        f"production input SHA256 mismatch: {relpath}: "
                        f"expected {expected_hash}, observed {actual}"
                    )
        except Exception as exc:
            fail(f"could not verify production-input manifest: {exc}")

    # ------------------------------------------------------------------
    # Frozen target manifest
    # ------------------------------------------------------------------

    manifest_rows: list[dict[str, str]] = []
    manifest_by_batch: defaultdict[str, list[dict[str, str]]] = defaultdict(list)

    if target_manifest.is_file():
        try:
            with target_manifest.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                if (reader.fieldnames or []) != TARGET_HEADER:
                    fail(
                        "target manifest header mismatch: "
                        f"observed {reader.fieldnames!r}"
                    )
                for row in reader:
                    manifest_rows.append(row)
                    manifest_by_batch[row["batch"]].append(row)
        except Exception as exc:
            fail(f"could not parse target manifest: {exc}")

    if manifest_rows:
        check_equal(
            "target manifest row count",
            len(manifest_rows),
            EXPECTED["all_target_rows"],
        )
        check_equal(
            "target manifest distinct batch count",
            len(manifest_by_batch),
            EXPECTED["all_batches"],
        )

        accessions = [
            row["canonical_genbank_assembly_accession"]
            for row in manifest_rows
        ]
        duplicates = sorted(
            accession
            for accession, count in Counter(accessions).items()
            if count != 1
        )
        if duplicates:
            fail(
                "target manifest duplicate canonical accessions: "
                + ", ".join(duplicates[:20])
            )

    full_universe_batches = [
        f"batch-{index:03d}"
        for index in range(1, EXPECTED["full_universe_batches"] + 1)
    ]
    full_universe_rows = [
        row
        for batch in full_universe_batches
        for row in manifest_by_batch.get(batch, [])
    ]

    if full_universe_rows:
        check_equal(
            "full-universe target count",
            len(full_universe_rows),
            EXPECTED["full_universe_targets"],
        )

    # ------------------------------------------------------------------
    # Frozen source-audit manifest and source batch anchors
    # ------------------------------------------------------------------

    source_rows_by_batch: dict[str, dict[str, str]] = {}

    if source_audit_manifest.is_file():
        try:
            with source_audit_manifest.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                if (reader.fieldnames or []) != SOURCE_AUDIT_HEADER:
                    fail(
                        "source-audit manifest header mismatch: "
                        f"observed {reader.fieldnames!r}"
                    )
                rows = list(reader)

            check_equal(
                "source-audit manifest row count",
                len(rows),
                EXPECTED["all_batches"],
            )

            for row in rows:
                batch = row["batch"]
                if batch in source_rows_by_batch:
                    fail(f"source-audit manifest duplicate batch: {batch}")
                source_rows_by_batch[batch] = row

            expected_all_batches = {
                f"batch-{index:03d}"
                for index in range(1, EXPECTED["all_batches"] + 1)
            }
            if set(source_rows_by_batch) != expected_all_batches:
                fail("source-audit manifest batch set is not exactly batch-001..111")
        except Exception as exc:
            fail(f"could not parse source-audit manifest: {exc}")

    for batch in full_universe_batches:
        source_row = source_rows_by_batch.get(batch)
        source_batch = source_snapshot_root / batch

        if source_row is None:
            fail(f"{batch}: source-audit manifest row missing")
            continue
        if not source_batch.is_dir():
            fail(f"{batch}: frozen source snapshot directory missing")
            continue

        for column, filename in SOURCE_AUDIT_FILES.items():
            expected_hash = source_row.get(column, "")
            path = source_batch / filename

            if not SHA256_RE.fullmatch(expected_hash):
                fail(f"{batch}: invalid frozen {column}")
                continue
            if not path.is_file():
                fail(f"{batch}: frozen source file missing: {filename}")
                continue

            actual_hash = sha256_file(path)
            if actual_hash != expected_hash:
                fail(
                    f"{batch}: frozen source file SHA256 mismatch "
                    f"for {filename}"
                )

    # ------------------------------------------------------------------
    # Frozen reference matrix anchor rows for the first wave
    # ------------------------------------------------------------------

    reference_by_key: dict[tuple[str, str], dict[str, str]] = {}
    reference_rows_seen = 0

    full_universe_keys = {
        (
            row["batch"],
            row["canonical_genbank_assembly_accession"],
        )
        for row in full_universe_rows
    }

    if reference_matrix.is_file():
        try:
            with reference_matrix.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                fields = reader.fieldnames or []

                required_reference_fields = set(TARGET_HEADER[:3]) | ANCHOR_FIELDS
                missing_fields = sorted(
                    required_reference_fields - set(fields)
                )
                if missing_fields:
                    fail(
                        "reference matrix missing required fields: "
                        + ", ".join(missing_fields)
                    )

                for row in reader:
                    reference_rows_seen += 1
                    key = (
                        row.get("batch", ""),
                        row.get("canonical_genbank_assembly_accession", ""),
                    )
                    if key in full_universe_keys:
                        if key in reference_by_key:
                            fail(
                                "duplicate full-universe row in reference matrix: "
                                f"{key[0]} {key[1]}"
                            )
                        reference_by_key[key] = row
        except Exception as exc:
            fail(f"could not parse reference matrix: {exc}")

    if reference_rows_seen:
        check_equal(
            "reference matrix row count",
            reference_rows_seen,
            EXPECTED["all_target_rows"],
        )
        check_equal(
            "full-universe reference row count",
            len(reference_by_key),
            EXPECTED["full_universe_targets"],
        )

    # ------------------------------------------------------------------
    # Production output
    # ------------------------------------------------------------------

    provenance_constants = {
        "analysis": EXPECTED["analysis"],
        "engine_sha256": EXPECTED["engine_sha256"],
        "engine_source_sha256": EXPECTED["engine_source_sha256"],
        "environment_lock_sha256": EXPECTED["environment_lock_sha256"],
        "finch_basic_sha256": EXPECTED["finch_basic_sha256"],
        "finch_driver_sha256": EXPECTED["finch_driver_sha256"],
        "git_head": EXPECTED["git_head"],
        "k_values": K_VALUES,
        "production_inputs_manifest_sha256": (
            EXPECTED["production_inputs_manifest_sha256"]
        ),
        "reference_matrix_sha256": EXPECTED["reference_matrix_sha256"],
        "repeat_concordance_module_sha256": (
            EXPECTED["repeat_concordance_module_sha256"]
        ),
        "repeat_feature_families": FAMILIES,
        "repeat_scale_method_sha256": EXPECTED["repeat_scale_method_sha256"],
        "repeat_scale_module_sha256": EXPECTED["repeat_scale_module_sha256"],
        "schema_version": EXPECTED["schema_version"],
        "source_audit_manifest_sha256": (
            EXPECTED["source_audit_manifest_sha256"]
        ),
        "target_manifest_sha256": EXPECTED["target_manifest_sha256"],
        "worker_sha256": EXPECTED["worker_sha256"],
    }

    all_result_accessions: list[str] = []
    total_source_files_hashed = 0
    total_anchor_passes = 0
    total_candidates_checked = 0

    for batch in full_universe_batches:
        batch_errors: list[str] = []
        expected_rows = manifest_by_batch.get(batch, [])
        expected_map = {
            row["canonical_genbank_assembly_accession"]: row
            for row in expected_rows
        }
        expected_accessions = [
            row["canonical_genbank_assembly_accession"]
            for row in expected_rows
        ]
        expected_set = set(expected_accessions)

        batch_dir = root / batch
        summary_path = batch_dir / "batch-summary.json"
        results_path = batch_dir / "candidate-results.tsv"
        provenance_path = batch_dir / "run-provenance.json"
        candidates_dir = batch_dir / "candidates"
        source_batch = source_snapshot_root / batch

        def bfail(message: str) -> None:
            batch_errors.append(message)

        summary: dict[str, Any] | None = None
        provenance: dict[str, Any] | None = None
        result_rows: list[dict[str, str]] = []

        if not batch_dir.is_dir():
            bfail("production batch directory missing")

        for path, label in [
            (summary_path, "batch-summary.json"),
            (results_path, "candidate-results.tsv"),
            (provenance_path, "run-provenance.json"),
        ]:
            if not path.is_file():
                bfail(f"{label} missing")

        if not candidates_dir.is_dir():
            bfail("candidates directory missing")

        # Batch summary.
        if summary_path.is_file():
            try:
                summary = read_json(summary_path)
                if set(summary) != SUMMARY_KEYS:
                    bfail(
                        "batch summary key set mismatch: "
                        f"observed {sorted(summary)!r}"
                    )

                expected_summary = {
                    "all_pass": True,
                    "analysis": EXPECTED["analysis"],
                    "batch": batch,
                    "k_values": K_VALUES,
                    "reference_anchor_pass_count": len(expected_rows),
                    "repeat_feature_families": FAMILIES,
                    "schema_version": EXPECTED["schema_version"],
                    "target_count": len(expected_rows),
                }

                for key, expected_value in expected_summary.items():
                    if summary.get(key) != expected_value:
                        bfail(
                            f"summary {key}: expected {expected_value!r}, "
                            f"observed {summary.get(key)!r}"
                        )
            except Exception as exc:
                bfail(f"could not parse batch-summary.json: {exc}")

        # Run provenance.
        if provenance_path.is_file():
            try:
                provenance = read_json(provenance_path)
                if set(provenance) != PROVENANCE_KEYS:
                    bfail(
                        "run provenance key set mismatch: "
                        f"observed {sorted(provenance)!r}"
                    )

                for key, expected_value in provenance_constants.items():
                    if provenance.get(key) != expected_value:
                        bfail(
                            f"provenance {key}: expected {expected_value!r}, "
                            f"observed {provenance.get(key)!r}"
                        )

                if provenance.get("batch") != batch:
                    bfail(
                        f"provenance batch: expected {batch!r}, "
                        f"observed {provenance.get('batch')!r}"
                    )
            except Exception as exc:
                bfail(f"could not parse run-provenance.json: {exc}")

        if summary is not None and results_path.is_file():
            actual_results_sha = sha256_file(results_path)
            if summary.get("candidate_results_sha256") != actual_results_sha:
                bfail(
                    "candidate-results.tsv SHA256 does not match "
                    "batch-summary.json"
                )

        if summary is not None and provenance_path.is_file():
            actual_provenance_sha = sha256_file(provenance_path)
            if summary.get("run_provenance_sha256") != actual_provenance_sha:
                bfail(
                    "run-provenance.json SHA256 does not match "
                    "batch-summary.json"
                )

        # Candidate results table.
        if results_path.is_file():
            try:
                with results_path.open(
                    "r",
                    encoding="utf-8",
                    newline="",
                ) as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
                    if (reader.fieldnames or []) != RESULTS_HEADER:
                        bfail(
                            "candidate-results.tsv header mismatch: "
                            f"observed {reader.fieldnames!r}"
                        )
                    result_rows = list(reader)
            except Exception as exc:
                bfail(f"could not parse candidate-results.tsv: {exc}")

        if len(result_rows) != len(expected_rows):
            bfail(
                f"candidate-results row count: expected {len(expected_rows)}, "
                f"observed {len(result_rows)}"
            )

        observed_accessions: list[str] = []
        positions: list[int] = []
        independent_anchor_passes = 0

        for row_number, result_row in enumerate(result_rows, start=2):
            accession = result_row.get("accession", "")
            observed_accessions.append(accession)
            all_result_accessions.append(accession)

            candidate_errors: list[str] = []

            def cfail(message: str) -> None:
                candidate_errors.append(message)

            try:
                position = int(result_row.get("position", ""))
                positions.append(position)
            except Exception:
                cfail(f"invalid position {result_row.get('position')!r}")

            expected_manifest_row = expected_map.get(accession)
            if expected_manifest_row is None:
                cfail("accession not present in frozen batch manifest")
                candidate_report.append(
                    {
                        "batch": batch,
                        "batch_index": result_row.get("batch_index", ""),
                        "accession": accession,
                        "candidate_ok": False,
                        "error_count": len(candidate_errors),
                    }
                )
                for message in candidate_errors:
                    bfail(f"{accession or f'row-{row_number}'}: {message}")
                continue

            expected_batch_index = int(expected_manifest_row["batch_index"])

            try:
                if int(result_row.get("batch_index", "")) != expected_batch_index:
                    cfail("candidate-results batch_index mismatch")
            except Exception:
                cfail("candidate-results batch_index is invalid")

            output_file = result_row.get("output_file", "")
            expected_output_file = f"{accession}.repeat-scale.json"
            if output_file != expected_output_file:
                cfail(
                    f"output_file expected {expected_output_file!r}, "
                    f"observed {output_file!r}"
                )

            candidate_path = candidates_dir / output_file
            candidate: dict[str, Any] | None = None

            if not candidate_path.is_file():
                cfail("candidate JSON missing")
            else:
                try:
                    actual_candidate_sha = sha256_file(candidate_path)
                    if result_row.get("output_sha256") != actual_candidate_sha:
                        cfail("candidate JSON SHA256 mismatch")
                    candidate = read_json(candidate_path)
                except Exception as exc:
                    cfail(f"candidate JSON could not be validated: {exc}")

            if candidate is not None:
                total_candidates_checked += 1

                if set(candidate) != CANDIDATE_KEYS:
                    cfail(
                        "candidate top-level key set mismatch: "
                        f"observed {sorted(candidate)!r}"
                    )

                candidate_expected = {
                    "analysis": EXPECTED["analysis"],
                    "batch": batch,
                    "batch_index": expected_batch_index,
                    "canonical_genbank_assembly_accession": accession,
                    "k_values": K_VALUES,
                    "repeat_feature_families": FAMILIES,
                    "schema_version": EXPECTED["schema_version"],
                }

                for key, expected_value in candidate_expected.items():
                    if candidate.get(key) != expected_value:
                        cfail(
                            f"candidate {key}: expected {expected_value!r}, "
                            f"observed {candidate.get(key)!r}"
                        )

                # Full 13-k grid.
                features_by_k = candidate.get("features_by_k")
                if not isinstance(features_by_k, dict):
                    cfail("features_by_k is not an object")
                    features_by_k = {}
                elif set(features_by_k) != K_KEYS:
                    cfail(
                        "features_by_k scale set mismatch: "
                        f"observed {sorted(features_by_k)!r}"
                    )

                for k in K_VALUES:
                    key = str(k)
                    feature = features_by_k.get(key)
                    if not isinstance(feature, dict):
                        cfail(f"k={k}: feature record missing or not an object")
                        continue

                    if set(feature) != FEATURE_FIELDS:
                        cfail(
                            f"k={k}: feature field set mismatch: "
                            f"observed {sorted(feature)!r}"
                        )

                    valid = feature.get("valid_start_count")
                    non_unique = feature.get("non_unique_start_count")
                    non_unique_fraction = feature.get("non_unique_fraction")
                    maximum = feature.get("maximum_multiplicity")
                    inter = feature.get("inter_replicon_shared_start_count")
                    inter_fraction = feature.get(
                        "inter_replicon_shared_fraction"
                    )

                    if not is_int(valid) or valid <= 0:
                        cfail(f"k={k}: invalid valid_start_count {valid!r}")
                        continue

                    if (
                        not is_int(non_unique)
                        or non_unique < 0
                        or non_unique > valid
                    ):
                        cfail(
                            f"k={k}: invalid non_unique_start_count "
                            f"{non_unique!r}"
                        )

                    if (
                        not is_int(inter)
                        or inter < 0
                        or inter > valid
                    ):
                        cfail(
                            f"k={k}: invalid "
                            f"inter_replicon_shared_start_count {inter!r}"
                        )

                    if not is_int(maximum) or maximum < 1:
                        cfail(
                            f"k={k}: invalid maximum_multiplicity {maximum!r}"
                        )

                    for label, value in [
                        ("non_unique_fraction", non_unique_fraction),
                        ("inter_replicon_shared_fraction", inter_fraction),
                    ]:
                        if not finite_number(value):
                            cfail(f"k={k}: {label} is not finite numeric")
                        elif not 0.0 <= float(value) <= 1.0:
                            cfail(f"k={k}: {label} outside [0,1]")

                    if (
                        is_int(non_unique)
                        and finite_number(non_unique_fraction)
                        and not math.isclose(
                            float(non_unique_fraction),
                            non_unique / valid,
                            rel_tol=0.0,
                            abs_tol=1e-15,
                        )
                    ):
                        cfail(
                            f"k={k}: non_unique_fraction is inconsistent "
                            "with count / valid_start_count"
                        )

                    if (
                        is_int(inter)
                        and finite_number(inter_fraction)
                        and not math.isclose(
                            float(inter_fraction),
                            inter / valid,
                            rel_tol=0.0,
                            abs_tol=1e-15,
                        )
                    ):
                        cfail(
                            f"k={k}: inter_replicon_shared_fraction is "
                            "inconsistent with count / valid_start_count"
                        )

                # Source provenance and actual source payload.
                source = candidate.get("source")
                if not isinstance(source, dict):
                    cfail("source is not an object")
                    source = {}
                elif set(source) != SOURCE_KEYS:
                    cfail(
                        "source key set mismatch: "
                        f"observed {sorted(source)!r}"
                    )

                manifest_integer_fields = [
                    "total_sequence_length",
                    "primary_assembly_records",
                    "topology_circular_records",
                    "topology_linear_records",
                ]
                for field in manifest_integer_fields:
                    try:
                        observed = int(source.get(field))
                        expected_value = int(expected_manifest_row[field])
                        if observed != expected_value:
                            cfail(
                                f"source {field}: expected {expected_value}, "
                                f"observed {observed}"
                            )
                    except Exception:
                        cfail(f"source {field} is invalid")

                fasta_name = source.get("genomic_fasta_file")
                fasta_sha = source.get("genomic_fasta_sha256")
                report_name = source.get("sequence_report_file")
                report_sha = source.get("sequence_report_sha256")

                for label, value in [
                    ("genomic_fasta_sha256", fasta_sha),
                    ("sequence_report_sha256", report_sha),
                ]:
                    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                        cfail(f"source {label} is not a valid SHA256")

                if not isinstance(fasta_name, str) or not fasta_name:
                    cfail("source genomic_fasta_file is missing")
                if not isinstance(report_name, str) or not report_name:
                    cfail("source sequence_report_file is missing")

                source_candidate_dir = (
                    source_batch
                    / "package"
                    / "ncbi_dataset"
                    / "data"
                    / accession
                )

                for name, expected_hash, label in [
                    (fasta_name, fasta_sha, "genomic FASTA"),
                    (report_name, report_sha, "sequence report"),
                ]:
                    if (
                        isinstance(name, str)
                        and name
                        and isinstance(expected_hash, str)
                        and SHA256_RE.fullmatch(expected_hash)
                    ):
                        payload_path = source_candidate_dir / name
                        if not payload_path.is_file():
                            cfail(f"source {label} file missing")
                        else:
                            try:
                                actual_payload_hash = sha256_file(payload_path)
                                total_source_files_hashed += 1
                                if actual_payload_hash != expected_hash:
                                    cfail(f"source {label} SHA256 mismatch")
                            except Exception as exc:
                                cfail(
                                    f"source {label} could not be hashed: {exc}"
                                )

                # Embedded 150/400 reference anchor.
                anchor = candidate.get("reference_anchor")
                if not isinstance(anchor, dict):
                    cfail("reference_anchor is not an object")
                    anchor = {}
                elif set(anchor) != ANCHOR_KEYS:
                    cfail(
                        "reference_anchor key set mismatch: "
                        f"observed {sorted(anchor)!r}"
                    )

                if anchor.get("k_values") != [150, 400]:
                    cfail("reference_anchor k_values are not [150, 400]")
                if anchor.get("passed") is not True:
                    cfail("reference_anchor passed is not true")
                if anchor.get("mismatches") != []:
                    cfail("reference_anchor mismatch list is not empty")

                anchor_observed = anchor.get("observed")
                if not isinstance(anchor_observed, dict):
                    cfail("reference_anchor observed is not an object")
                    anchor_observed = {}
                elif set(anchor_observed) != ANCHOR_FIELDS:
                    cfail(
                        "reference_anchor observed field set mismatch: "
                        f"observed {sorted(anchor_observed)!r}"
                    )

                # Anchor must be internally identical to the 150/400 grid.
                for anchor_field, (k_key, grid_field) in ANCHOR_TO_GRID.items():
                    grid_record = features_by_k.get(k_key, {})
                    grid_value = (
                        grid_record.get(grid_field)
                        if isinstance(grid_record, dict)
                        else None
                    )
                    anchor_value = anchor_observed.get(anchor_field)

                    if not same_number(anchor_value, grid_value):
                        cfail(
                            f"{anchor_field}: anchor value differs from "
                            f"features_by_k[{k_key!r}][{grid_field!r}]"
                        )

                # Anchor must independently match the frozen corrected matrix.
                reference_row = reference_by_key.get((batch, accession))
                if reference_row is None:
                    cfail("frozen reference-matrix row missing")
                else:
                    try:
                        if int(reference_row["batch_index"]) != expected_batch_index:
                            cfail("reference-matrix batch_index mismatch")
                    except Exception:
                        cfail("reference-matrix batch_index invalid")

                    for anchor_field in sorted(ANCHOR_FIELDS):
                        anchor_value = anchor_observed.get(anchor_field)
                        raw_expected = reference_row.get(anchor_field)

                        try:
                            if "multiplicity" in anchor_field:
                                expected_value: int | float = int(raw_expected)
                            else:
                                expected_value = float(raw_expected)
                        except Exception:
                            cfail(
                                f"reference matrix {anchor_field} is not numeric"
                            )
                            continue

                        if not same_number(anchor_value, expected_value):
                            cfail(
                                f"{anchor_field}: reference anchor differs "
                                "from frozen corrected reference matrix"
                            )

                if not candidate_errors:
                    independent_anchor_passes += 1
                    total_anchor_passes += 1

            candidate_ok = not candidate_errors
            candidate_report.append(
                {
                    "batch": batch,
                    "batch_index": expected_batch_index,
                    "accession": accession,
                    "candidate_ok": candidate_ok,
                    "error_count": len(candidate_errors),
                }
            )

            for message in candidate_errors:
                bfail(f"{accession}: {message}")

        # Exact position and membership checks.
        if positions and positions != list(range(1, len(result_rows) + 1)):
            bfail("candidate position column is not exactly 1..N in result order")

        observed_set = set(observed_accessions)
        missing_accessions = sorted(expected_set - observed_set)
        unexpected_accessions = sorted(observed_set - expected_set)

        if missing_accessions:
            bfail(
                "missing expected accessions: "
                + ", ".join(missing_accessions[:20])
            )
        if unexpected_accessions:
            bfail(
                "unexpected accessions: "
                + ", ".join(unexpected_accessions[:20])
            )

        duplicates = sorted(
            accession
            for accession, count in Counter(observed_accessions).items()
            if count != 1
        )
        if duplicates:
            bfail(
                "duplicate candidate-results accessions: "
                + ", ".join(duplicates[:20])
            )

        if candidates_dir.is_dir():
            observed_json = {
                path.name
                for path in candidates_dir.glob("*.repeat-scale.json")
                if path.is_file()
            }
            expected_json = {
                f"{accession}.repeat-scale.json"
                for accession in expected_accessions
            }

            missing_json = sorted(expected_json - observed_json)
            extra_json = sorted(observed_json - expected_json)

            if missing_json:
                bfail(
                    "missing candidate JSON files: "
                    + ", ".join(missing_json[:20])
                )
            if extra_json:
                bfail(
                    "unexpected candidate JSON files: "
                    + ", ".join(extra_json[:20])
                )

        if summary is not None:
            if summary.get("reference_anchor_pass_count") != independent_anchor_passes:
                bfail(
                    "summary reference_anchor_pass_count differs from "
                    f"independent candidate audit: expected "
                    f"{independent_anchor_passes}, observed "
                    f"{summary.get('reference_anchor_pass_count')!r}"
                )

        batch_ok = not batch_errors
        if batch_errors:
            for message in batch_errors:
                fail(f"{batch}: {message}")

        batch_report.append(
            {
                "batch": batch,
                "expected_targets": len(expected_rows),
                "candidate_rows": len(result_rows),
                "independent_anchor_passes": independent_anchor_passes,
                "batch_ok": batch_ok,
                "error_count": len(batch_errors),
            }
        )

    # ------------------------------------------------------------------
    # Global full-universe coverage
    # ------------------------------------------------------------------

    check_equal(
        "full-universe candidate-results row count",
        len(all_result_accessions),
        EXPECTED["full_universe_targets"],
    )
    check_equal(
        "candidate JSONs fully parsed",
        total_candidates_checked,
        EXPECTED["full_universe_targets"],
    )
    check_equal(
        "independent full-universe reference-anchor passes",
        total_anchor_passes,
        EXPECTED["full_universe_targets"],
    )
    check_equal(
        "source payload files hashed",
        total_source_files_hashed,
        EXPECTED["full_universe_targets"] * 2,
    )

    expected_global = {
        row["canonical_genbank_assembly_accession"]
        for row in full_universe_rows
    }
    observed_global = set(all_result_accessions)

    missing_global = sorted(expected_global - observed_global)
    unexpected_global = sorted(observed_global - expected_global)

    if missing_global:
        fail(
            "global full-universe missing accessions: "
            + ", ".join(missing_global[:20])
        )
    if unexpected_global:
        fail(
            "global full-universe unexpected accessions: "
            + ", ".join(unexpected_global[:20])
        )

    global_duplicates = sorted(
        accession
        for accession, count in Counter(all_result_accessions).items()
        if count != 1
    )
    if global_duplicates:
        fail(
            "global full-universe duplicate accessions: "
            + ", ".join(global_duplicates[:20])
        )

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    finished = datetime.now(timezone.utc)
    all_pass = not errors

    errors_path = report_dir / "errors.txt"
    errors_path.write_text(
        "NONE\n" if not errors else "\n".join(errors) + "\n",
        encoding="utf-8",
    )

    batch_path = report_dir / "batch-audit.tsv"
    with batch_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "batch",
            "expected_targets",
            "candidate_rows",
            "independent_anchor_passes",
            "batch_ok",
            "error_count",
        ]
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(batch_report)

    candidate_path = report_dir / "candidate-audit.tsv"
    with candidate_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "batch",
            "batch_index",
            "accession",
            "candidate_ok",
            "error_count",
        ]
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(candidate_report)

    summary = {
        "all_pass": all_pass,
        "analysis": "bacselect-repeat-scale-full-universe-audit",
        "audit_schema_version": 1,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "production_root": str(root),
        "target_manifest": str(target_manifest),
        "reference_matrix": str(reference_matrix),
        "source_snapshot_root": str(source_snapshot_root),
        "scientific_repo": str(repo),
        "expected_git_head": EXPECTED["git_head"],
        "expected_batches": EXPECTED["full_universe_batches"],
        "batches_audited": len(batch_report),
        "batches_passed": sum(
            1 for row in batch_report if row["batch_ok"]
        ),
        "batches_failed": sum(
            1 for row in batch_report if not row["batch_ok"]
        ),
        "expected_targets": EXPECTED["full_universe_targets"],
        "manifest_rows_observed": len(full_universe_rows),
        "result_rows_observed": len(all_result_accessions),
        "candidate_jsons_checked": total_candidates_checked,
        "source_payload_files_hashed": total_source_files_hashed,
        "reference_anchor_passes": total_anchor_passes,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "batch_audit_sha256": sha256_file(batch_path),
        "candidate_audit_sha256": sha256_file(candidate_path),
        "errors_sha256": sha256_file(errors_path),
        "expected": {
            key: EXPECTED[key]
            for key in [
                "analysis",
                "schema_version",
                "git_head",
                "target_manifest_sha256",
                "reference_matrix_sha256",
                "source_audit_manifest_sha256",
                "production_inputs_manifest_sha256",
                "worker_sha256",
                "repeat_scale_module_sha256",
                "repeat_concordance_module_sha256",
                "repeat_scale_method_sha256",
                "finch_driver_sha256",
                "finch_basic_sha256",
                "engine_source_sha256",
                "engine_sha256",
                "environment_lock_sha256",
            ]
        },
        "k_values": K_VALUES,
        "repeat_feature_families": FAMILIES,
    }

    summary_path = report_dir / "audit-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("===== BacSelect repeat-scale full-universe audit =====")
    print(f"production_root       {root}")
    print(
        f"batches               {len(batch_report)} / "
        f"{EXPECTED['full_universe_batches']}"
    )
    print(
        f"batches_passed        "
        f"{sum(1 for row in batch_report if row['batch_ok'])}"
    )
    print(
        f"batches_failed        "
        f"{sum(1 for row in batch_report if not row['batch_ok'])}"
    )
    print(
        f"manifest_rows         {len(full_universe_rows)} / "
        f"{EXPECTED['full_universe_targets']}"
    )
    print(
        f"result_rows           {len(all_result_accessions)} / "
        f"{EXPECTED['full_universe_targets']}"
    )
    print(
        f"candidate_jsons       {total_candidates_checked} / "
        f"{EXPECTED['full_universe_targets']}"
    )
    print(
        f"source_payload_files  {total_source_files_hashed} / "
        f"{EXPECTED['full_universe_targets'] * 2}"
    )
    print(
        f"reference_anchors     {total_anchor_passes} / "
        f"{EXPECTED['full_universe_targets']}"
    )
    print(f"errors                {len(errors)}")
    print(f"warnings              {len(warnings)}")
    print(f"report_dir            {report_dir}")
    print(f"audit_summary         {summary_path}")
    print(f"all_pass              {str(all_pass).lower()}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
