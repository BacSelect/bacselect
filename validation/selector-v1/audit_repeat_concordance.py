#!/usr/bin/env python3
"""
Final fail-closed audit for BacSelect selector-v1 repeat reference concordance.

This script is read-only with respect to:
  - the BacSelect scientific repository,
  - the repeat-concordance production output,
  - the frozen target manifest,
  - the frozen reference matrix.

It writes only audit reports under --report-dir.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED = {
    "analysis": "selector-v1-repeat-reference-concordance",
    "schema_version": 1,
    "git_head": "b25037af85f65f080eb00c95e97328983923645e",
    "target_manifest_sha256": "bc4acba1384524f956887d02d2f54aa7e501a2c23e2930b779a4e6520d8fcee1",
    "reference_matrix_sha256": "fd264bedda627d737a647de601c8b835f53baeca246724e9aafb73fd50c9d656",
    "engine_sha256": "e0b5ea3a892aee3f9af80e5676010f1e1145563ca900058485e07d6433988968",
    "engine_source_sha256": "bea979167a353c41e51bb96c83acebfb8e8136269d2902d99142c0780bf46925",
    "environment_lock_sha256": "aa6984b17e86f7d0627379e295fabed837cf7d43cc6a9fd80f32b7092ac5f64f",
    "finch_basic_sha256": "30bc3f52fdf68cf7b6433262935b3ed2bb189b256672687bea56f3a4f4cc043a",
    "finch_driver_sha256": "e4d76a44731000dc8330d6f3289aca76ce6562329dd371f6f63ec090ab42db50",
    "repeat_concordance_module_sha256": "6dc25a2d382ebdf0a5c6327b211bb4dae064363727b42864a725b626bb325a51",
    "worker_sha256": "4e012d24a04c547f2dd01564d4b01122de887b0858be2de20f457b64b120030b",
    "k_values": [150, 400],
    "batch_count": 111,
    "target_count": 55306,
}

EXPECTED_OBSERVED_KEYS = {
    "06_non_unique_canonical_150mer_fraction",
    "07_non_unique_canonical_400mer_fraction",
    "08_maximum_canonical_150mer_multiplicity",
    "09_maximum_canonical_400mer_multiplicity",
    "11_inter_replicon_shared_canonical_150mer_fraction",
    "12_inter_replicon_shared_canonical_400mer_fraction",
}

EXPECTED_RESULTS_HEADER = [
    "position",
    "batch_index",
    "accession",
    "output_file",
    "output_sha256",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def parse_args() -> argparse.Namespace:
    home = Path.home()
    commit = EXPECTED["git_head"]

    parser = argparse.ArgumentParser(
        description="Final fail-closed audit of all 111 BacSelect repeat-concordance batches."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/"
            f"reference-concordance/{commit}/production"
        ),
        help="Production repeat-concordance output root.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/repeat-scale/"
            "concordance-inputs/repeat-concordance-targets.tsv"
        ),
        help="Frozen repeat-concordance target manifest.",
    )
    parser.add_argument(
        "--reference-matrix",
        type=Path,
        default=Path(
            "/NGS/scratch/EXT/Rhys_wkdir/project-finch/experiment-0/"
            "corrected-eligible-percentile-feature-space/"
            "corrected-eligible-structural-feature-matrix.tsv"
        ),
        help="Frozen corrected structural-feature reference matrix.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=home / "github" / "bacselect",
        help="Scientific BacSelect checkout used for the production commit gate.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=home / "bacselect-repeat-concordance-final-audit",
        help="Directory for audit reports. This is the only location written by the script.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    manifest_path = args.manifest.resolve()
    reference_matrix = args.reference_matrix.resolve()
    repo = args.repo.resolve()
    report_dir = args.report_dir.expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    warnings: list[str] = []
    batch_rows: list[dict[str, Any]] = []

    def fail(message: str) -> None:
        errors.append(message)

    def check_equal(label: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            fail(f"{label}: expected {expected!r}, observed {actual!r}")

    started = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # Immutable input / repository gates
    # ------------------------------------------------------------------
    if not manifest_path.is_file():
        fail(f"target manifest missing: {manifest_path}")
    else:
        check_equal(
            "target manifest SHA256",
            sha256_file(manifest_path),
            EXPECTED["target_manifest_sha256"],
        )

    if not reference_matrix.is_file():
        fail(f"reference matrix missing: {reference_matrix}")
    else:
        check_equal(
            "reference matrix SHA256",
            sha256_file(reference_matrix),
            EXPECTED["reference_matrix_sha256"],
        )

    if not repo.is_dir():
        fail(f"scientific repository missing: {repo}")
    else:
        try:
            check_equal(
                "scientific repository HEAD",
                run_git(repo, "rev-parse", "HEAD"),
                EXPECTED["git_head"],
            )
            check_equal(
                "scientific repository origin/main",
                run_git(repo, "rev-parse", "origin/main"),
                EXPECTED["git_head"],
            )
            status = run_git(repo, "status", "--porcelain")
            if status:
                fail("scientific repository working tree is not clean")
        except Exception as exc:
            fail(f"scientific repository gate failed: {exc}")

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------
    manifest_rows: list[dict[str, str]] = []
    manifest_by_batch: dict[str, list[dict[str, str]]] = defaultdict(list)
    manifest_by_batch_accession: dict[tuple[str, str], dict[str, str]] = {}

    required_manifest_columns = {
        "batch",
        "batch_index",
        "canonical_genbank_assembly_accession",
        "primary_assembly_records",
    }

    if manifest_path.is_file():
        try:
            with manifest_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle, delimiter="\t")
                columns = set(reader.fieldnames or [])
                missing = sorted(required_manifest_columns - columns)
                if missing:
                    fail(f"target manifest missing required columns: {', '.join(missing)}")
                else:
                    for row in reader:
                        manifest_rows.append(row)
                        batch = row["batch"]
                        accession = row["canonical_genbank_assembly_accession"]
                        manifest_by_batch[batch].append(row)
                        key = (batch, accession)
                        if key in manifest_by_batch_accession:
                            fail(f"duplicate manifest batch/accession: {batch} {accession}")
                        manifest_by_batch_accession[key] = row
        except Exception as exc:
            fail(f"could not parse target manifest: {exc}")

    if manifest_rows:
        check_equal("target manifest row count", len(manifest_rows), EXPECTED["target_count"])

        accession_counts = Counter(
            row["canonical_genbank_assembly_accession"] for row in manifest_rows
        )
        duplicate_accessions = sorted(a for a, n in accession_counts.items() if n != 1)
        if duplicate_accessions:
            fail(
                "target manifest has non-unique canonical accessions: "
                + ", ".join(duplicate_accessions[:20])
                + (" ..." if len(duplicate_accessions) > 20 else "")
            )

        expected_batches = {f"batch-{i:03d}" for i in range(1, EXPECTED["batch_count"] + 1)}
        observed_batches = set(manifest_by_batch)
        missing_batches = sorted(expected_batches - observed_batches)
        unexpected_batches = sorted(observed_batches - expected_batches)
        if missing_batches:
            fail("manifest missing batches: " + ", ".join(missing_batches))
        if unexpected_batches:
            fail("manifest has unexpected batches: " + ", ".join(unexpected_batches))

    # ------------------------------------------------------------------
    # Production batches
    # ------------------------------------------------------------------
    all_result_accessions: list[str] = []
    expected_batches_ordered = [
        f"batch-{i:03d}" for i in range(1, EXPECTED["batch_count"] + 1)
    ]

    provenance_constant_fields = {
        "analysis": EXPECTED["analysis"],
        "schema_version": EXPECTED["schema_version"],
        "git_head": EXPECTED["git_head"],
        "target_manifest_sha256": EXPECTED["target_manifest_sha256"],
        "reference_matrix_sha256": EXPECTED["reference_matrix_sha256"],
        "engine_sha256": EXPECTED["engine_sha256"],
        "engine_source_sha256": EXPECTED["engine_source_sha256"],
        "environment_lock_sha256": EXPECTED["environment_lock_sha256"],
        "finch_basic_sha256": EXPECTED["finch_basic_sha256"],
        "finch_driver_sha256": EXPECTED["finch_driver_sha256"],
        "repeat_concordance_module_sha256": EXPECTED["repeat_concordance_module_sha256"],
        "worker_sha256": EXPECTED["worker_sha256"],
        "k_values": EXPECTED["k_values"],
    }

    for batch in expected_batches_ordered:
        batch_errors: list[str] = []
        batch_dir = root / batch
        summary_path = batch_dir / "batch-summary.json"
        results_path = batch_dir / "candidate-results.tsv"
        provenance_path = batch_dir / "run-provenance.json"
        candidates_dir = batch_dir / "candidates"

        expected_rows = manifest_by_batch.get(batch, [])
        expected_accessions = [
            row["canonical_genbank_assembly_accession"] for row in expected_rows
        ]
        expected_set = set(expected_accessions)
        expected_map = {
            row["canonical_genbank_assembly_accession"]: row for row in expected_rows
        }

        def bfail(message: str) -> None:
            batch_errors.append(message)

        summary: dict[str, Any] | None = None
        provenance: dict[str, Any] | None = None
        result_rows: list[dict[str, str]] = []

        if not batch_dir.is_dir():
            bfail("batch directory missing")
        else:
            if not summary_path.is_file():
                bfail("batch-summary.json missing")
            if not results_path.is_file():
                bfail("candidate-results.tsv missing")
            if not provenance_path.is_file():
                bfail("run-provenance.json missing")
            if not candidates_dir.is_dir():
                bfail("candidates directory missing")

        if summary_path.is_file():
            try:
                summary = read_json(summary_path)
                expected_summary = {
                    "analysis": EXPECTED["analysis"],
                    "batch": batch,
                    "schema_version": EXPECTED["schema_version"],
                    "all_pass": True,
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

        if provenance_path.is_file():
            try:
                provenance = read_json(provenance_path)
                for key, expected_value in provenance_constant_fields.items():
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
                    "candidate-results.tsv SHA256 does not match batch-summary.json"
                )

        if summary is not None and provenance_path.is_file():
            actual_provenance_sha = sha256_file(provenance_path)
            if summary.get("run_provenance_sha256") != actual_provenance_sha:
                bfail(
                    "run-provenance.json SHA256 does not match batch-summary.json"
                )

        if results_path.is_file():
            try:
                with results_path.open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
                    if (reader.fieldnames or []) != EXPECTED_RESULTS_HEADER:
                        bfail(
                            "candidate-results.tsv header mismatch: "
                            f"observed {reader.fieldnames!r}"
                        )
                    result_rows = list(reader)
            except Exception as exc:
                bfail(f"could not parse candidate-results.tsv: {exc}")

        if result_rows:
            if len(result_rows) != len(expected_rows):
                bfail(
                    f"candidate row count: expected {len(expected_rows)}, "
                    f"observed {len(result_rows)}"
                )

            positions: list[int] = []
            observed_accessions: list[str] = []

            for row_number, row in enumerate(result_rows, start=2):
                accession = row.get("accession", "")
                observed_accessions.append(accession)
                all_result_accessions.append(accession)

                try:
                    position = int(row.get("position", ""))
                    positions.append(position)
                except Exception:
                    bfail(f"row {row_number}: invalid position {row.get('position')!r}")

                expected_manifest_row = expected_map.get(accession)
                if expected_manifest_row is None:
                    bfail(f"row {row_number}: unexpected accession {accession}")
                    continue

                try:
                    observed_batch_index = int(row.get("batch_index", ""))
                    expected_batch_index = int(expected_manifest_row["batch_index"])
                    if observed_batch_index != expected_batch_index:
                        bfail(
                            f"{accession}: batch_index expected {expected_batch_index}, "
                            f"observed {observed_batch_index}"
                        )
                except Exception as exc:
                    bfail(f"{accession}: invalid batch_index: {exc}")

                output_file = row.get("output_file", "")
                expected_output_file = f"{accession}.repeat-concordance.json"
                if output_file != expected_output_file:
                    bfail(
                        f"{accession}: output_file expected {expected_output_file!r}, "
                        f"observed {output_file!r}"
                    )

                candidate_path = candidates_dir / output_file
                if not candidate_path.is_file():
                    bfail(f"{accession}: candidate JSON missing: {candidate_path.name}")
                    continue

                actual_candidate_sha = sha256_file(candidate_path)
                if row.get("output_sha256") != actual_candidate_sha:
                    bfail(f"{accession}: candidate JSON SHA256 mismatch")

                try:
                    candidate = read_json(candidate_path)
                except Exception as exc:
                    bfail(f"{accession}: could not parse candidate JSON: {exc}")
                    continue

                candidate_expectations = {
                    "analysis": EXPECTED["analysis"],
                    "batch": batch,
                    "schema_version": EXPECTED["schema_version"],
                    "canonical_genbank_assembly_accession": accession,
                    "k_values": EXPECTED["k_values"],
                    "passed": True,
                    "mismatches": [],
                }
                for key, expected_value in candidate_expectations.items():
                    if candidate.get(key) != expected_value:
                        bfail(
                            f"{accession}: candidate {key} expected "
                            f"{expected_value!r}, observed {candidate.get(key)!r}"
                        )

                try:
                    candidate_batch_index = int(candidate.get("batch_index"))
                    expected_batch_index = int(expected_manifest_row["batch_index"])
                    if candidate_batch_index != expected_batch_index:
                        bfail(
                            f"{accession}: candidate batch_index expected "
                            f"{expected_batch_index}, observed {candidate_batch_index}"
                        )
                except Exception as exc:
                    bfail(f"{accession}: invalid candidate batch_index: {exc}")

                source = candidate.get("source")
                if not isinstance(source, dict):
                    bfail(f"{accession}: candidate source is not an object")
                else:
                    try:
                        source_records = int(source.get("primary_assembly_records"))
                        expected_records = int(
                            expected_manifest_row["primary_assembly_records"]
                        )
                        if source_records != expected_records:
                            bfail(
                                f"{accession}: primary_assembly_records expected "
                                f"{expected_records}, observed {source_records}"
                            )
                    except Exception as exc:
                        bfail(
                            f"{accession}: invalid primary_assembly_records: {exc}"
                        )

                    if not source.get("genomic_fasta_file"):
                        bfail(f"{accession}: source genomic_fasta_file missing")
                    if not source.get("sequence_report_file"):
                        bfail(f"{accession}: source sequence_report_file missing")

                observed = candidate.get("observed")
                if not isinstance(observed, dict):
                    bfail(f"{accession}: candidate observed is not an object")
                else:
                    observed_keys = set(observed)
                    if observed_keys != EXPECTED_OBSERVED_KEYS:
                        bfail(
                            f"{accession}: observed feature keys mismatch; "
                            f"expected {sorted(EXPECTED_OBSERVED_KEYS)!r}, "
                            f"observed {sorted(observed_keys)!r}"
                        )
                    for feature, value in observed.items():
                        if isinstance(value, bool) or not isinstance(value, (int, float)):
                            bfail(
                                f"{accession}: observed {feature} is not numeric: {value!r}"
                            )
                        elif not math.isfinite(float(value)):
                            bfail(
                                f"{accession}: observed {feature} is not finite: {value!r}"
                            )

            if positions:
                expected_positions = list(range(1, len(result_rows) + 1))
                if positions != expected_positions:
                    bfail(
                        "candidate position column is not exactly 1..N in result order"
                    )

            observed_set = set(observed_accessions)
            missing_accessions = sorted(expected_set - observed_set)
            unexpected_accessions = sorted(observed_set - expected_set)
            if missing_accessions:
                bfail(
                    "missing expected accessions: "
                    + ", ".join(missing_accessions[:20])
                    + (" ..." if len(missing_accessions) > 20 else "")
                )
            if unexpected_accessions:
                bfail(
                    "unexpected accessions: "
                    + ", ".join(unexpected_accessions[:20])
                    + (" ..." if len(unexpected_accessions) > 20 else "")
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
                    + (" ..." if len(duplicates) > 20 else "")
                )

        if candidates_dir.is_dir():
            candidate_json_names = {
                path.name
                for path in candidates_dir.glob("*.repeat-concordance.json")
                if path.is_file()
            }
            expected_json_names = {
                f"{accession}.repeat-concordance.json"
                for accession in expected_accessions
            }
            extra_json = sorted(candidate_json_names - expected_json_names)
            missing_json = sorted(expected_json_names - candidate_json_names)
            if extra_json:
                bfail(
                    "unexpected candidate JSON files: "
                    + ", ".join(extra_json[:20])
                    + (" ..." if len(extra_json) > 20 else "")
                )
            if missing_json:
                bfail(
                    "missing candidate JSON files: "
                    + ", ".join(missing_json[:20])
                    + (" ..." if len(missing_json) > 20 else "")
                )

        batch_ok = not batch_errors
        if batch_errors:
            for message in batch_errors:
                fail(f"{batch}: {message}")

        batch_rows.append(
            {
                "batch": batch,
                "expected_targets": len(expected_rows),
                "candidate_rows": len(result_rows),
                "batch_ok": batch_ok,
                "error_count": len(batch_errors),
            }
        )

    # ------------------------------------------------------------------
    # Global coverage
    # ------------------------------------------------------------------
    if len(all_result_accessions) != EXPECTED["target_count"]:
        fail(
            "global candidate-results row count: expected "
            f"{EXPECTED['target_count']}, observed {len(all_result_accessions)}"
        )

    if manifest_rows:
        expected_global = {
            row["canonical_genbank_assembly_accession"] for row in manifest_rows
        }
        observed_global = set(all_result_accessions)

        missing_global = sorted(expected_global - observed_global)
        unexpected_global = sorted(observed_global - expected_global)

        if missing_global:
            fail(
                "global missing accessions: "
                + ", ".join(missing_global[:20])
                + (" ..." if len(missing_global) > 20 else "")
            )
        if unexpected_global:
            fail(
                "global unexpected accessions: "
                + ", ".join(unexpected_global[:20])
                + (" ..." if len(unexpected_global) > 20 else "")
            )

        global_duplicates = sorted(
            accession
            for accession, count in Counter(all_result_accessions).items()
            if count != 1
        )
        if global_duplicates:
            fail(
                "global duplicate result accessions: "
                + ", ".join(global_duplicates[:20])
                + (" ..." if len(global_duplicates) > 20 else "")
            )

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------
    finished = datetime.now(timezone.utc)
    all_pass = not errors

    batch_report = report_dir / "batch-audit.tsv"
    with batch_report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            delimiter="\t",
            fieldnames=[
                "batch",
                "expected_targets",
                "candidate_rows",
                "batch_ok",
                "error_count",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(batch_rows)

    error_report = report_dir / "errors.txt"
    with error_report.open("w", encoding="utf-8") as handle:
        if errors:
            for error in errors:
                handle.write(error + "\n")
        else:
            handle.write("NONE\n")

    summary = {
        "analysis": "bacselect-repeat-concordance-final-audit",
        "audit_schema_version": 1,
        "all_pass": all_pass,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "production_root": str(root),
        "target_manifest": str(manifest_path),
        "reference_matrix": str(reference_matrix),
        "scientific_repo": str(repo),
        "expected_git_head": EXPECTED["git_head"],
        "expected_batches": EXPECTED["batch_count"],
        "expected_targets": EXPECTED["target_count"],
        "manifest_rows_observed": len(manifest_rows),
        "result_rows_observed": len(all_result_accessions),
        "batches_audited": len(batch_rows),
        "batches_passed": sum(1 for row in batch_rows if row["batch_ok"]),
        "batches_failed": sum(1 for row in batch_rows if not row["batch_ok"]),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "batch_audit_sha256": sha256_file(batch_report),
        "errors_sha256": sha256_file(error_report),
        "expected": EXPECTED,
    }

    summary_path = report_dir / "audit-summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("===== BacSelect repeat-concordance final audit =====")
    print(f"production_root\t{root}")
    print(f"manifest_rows\t{len(manifest_rows)} / {EXPECTED['target_count']}")
    print(f"result_rows\t{len(all_result_accessions)} / {EXPECTED['target_count']}")
    print(f"batches\t{len(batch_rows)} / {EXPECTED['batch_count']}")
    print(f"batches_passed\t{summary['batches_passed']}")
    print(f"batches_failed\t{summary['batches_failed']}")
    print(f"errors\t{len(errors)}")
    print(f"report_dir\t{report_dir}")
    print(f"audit_summary\t{summary_path}")
    print(f"all_pass\t{str(all_pass).lower()}")

    if errors:
        print()
        print("===== first audit errors =====")
        for error in errors[:30]:
            print(error)
        if len(errors) > 30:
            print(f"... {len(errors) - 30} additional errors; see {error_report}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
