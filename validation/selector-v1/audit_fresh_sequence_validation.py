#!/usr/bin/env python3
"""Audit BacSelect fresh sequence-acquisition batch outputs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Mapping

MANIFEST_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
    "final-acquisition-manifests/"
    "a8f045506ac4a3f17034cd9170867995a87eb894"
)
FRESH_MANIFEST = MANIFEST_ROOT / "fresh-download-manifest.tsv"
FRESH_BATCH_INDEX = MANIFEST_ROOT / "fresh-batch-index.tsv"
FRESH_MANIFEST_SHA256 = (
    "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b"
)
FRESH_BATCH_INDEX_SHA256 = (
    "2a52f7ba3b23867bfe85078b47b840e5a1e240b09187d130fb0578087b483c4a"
)
EXPECTED_TARGETS = 15_326
EXPECTED_BATCHES = 31
BATCH_SIZE = 500
EXPECTED_FINAL_BATCH_SIZE = 326
DATASETS_VERSION = "18.35.0"
ENVIRONMENT_EXPLICIT_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GCA_RE = re.compile(r"^GCA_[0-9]+\.[0-9]+$")


def die(message: str) -> None:
    raise SystemExit(f"ERROR | {message}")


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader.fieldnames or ()), list(reader)


def frozen_inputs() -> tuple[dict[str, str], dict[str, tuple[int, str]]]:
    if sha256_file(FRESH_MANIFEST) != FRESH_MANIFEST_SHA256:
        die("fresh target manifest SHA256 mismatch")
    if sha256_file(FRESH_BATCH_INDEX) != FRESH_BATCH_INDEX_SHA256:
        die("fresh batch index SHA256 mismatch")

    fields, rows = read_tsv(FRESH_MANIFEST)
    required = {
        "canonical_genbank_assembly_accession",
        "fresh_biosample",
        "acquisition_reason",
    }
    if not required.issubset(fields):
        die("fresh target manifest schema mismatch")
    if len(rows) != EXPECTED_TARGETS:
        die("fresh target manifest count mismatch")

    biosamples: dict[str, str] = {}
    ordered: list[str] = []
    for row in rows:
        accession = row["canonical_genbank_assembly_accession"]
        biosample = row["fresh_biosample"]
        if not GCA_RE.fullmatch(accession):
            die("invalid accession in fresh target manifest")
        if accession in biosamples:
            die("duplicate accession in fresh target manifest")
        if not biosample:
            die("empty BioSample in fresh target manifest")
        if row["acquisition_reason"] != "not_in_historical_cache":
            die("unexpected acquisition reason")
        biosamples[accession] = biosample
        ordered.append(accession)

    if ordered != sorted(ordered):
        die("fresh target manifest is not sorted")

    _, batch_rows = read_tsv(FRESH_BATCH_INDEX)
    if len(batch_rows) != EXPECTED_BATCHES:
        die("fresh batch index count mismatch")

    batch_index: dict[str, tuple[int, str]] = {}
    for index, row in enumerate(batch_rows, 1):
        batch = f"batch-{index:03d}"
        if row.get("batch") != batch:
            die("fresh batch index is not contiguous")
        expected_count = (
            EXPECTED_FINAL_BATCH_SIZE if index == EXPECTED_BATCHES else BATCH_SIZE
        )
        try:
            observed_count = int(row["accession_count"])
        except (KeyError, ValueError):
            die("invalid fresh batch accession count")
        if observed_count != expected_count:
            die(f"{batch}: unexpected frozen batch count")
        sha = row.get("accessions_sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", sha):
            die(f"{batch}: invalid frozen accession SHA256")
        path = MANIFEST_ROOT / "fresh-batches" / batch / "accessions.txt"
        if sha256_file(path) != sha:
            die(f"{batch}: frozen accession file SHA256 mismatch")
        batch_index[batch] = (expected_count, sha)

    return biosamples, batch_index


def safe_package_path(package: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        die(f"unsafe package path: {relative!r}")
    path = package / rel
    try:
        path.resolve().relative_to(package.resolve())
    except ValueError:
        die(f"package path escapes root: {relative!r}")
    return path


def validate_batch(
    output_root: Path,
    production_commit: str,
    batch_number: int,
    *,
    verify_package_content: bool,
) -> dict[str, object]:
    if not GIT_SHA_RE.fullmatch(production_commit):
        die("invalid production commit")
    if not 1 <= batch_number <= EXPECTED_BATCHES:
        die("batch number outside frozen range")

    biosamples, batch_index = frozen_inputs()
    batch = f"batch-{batch_number:03d}"
    final_dir = output_root / batch
    partial_dir = output_root / f"{batch}.partial"

    if not final_dir.is_dir():
        die(f"{batch}: finalized output missing")
    if partial_dir.exists():
        die(f"{batch}: final and partial outputs both exist")

    expected_count, expected_accession_sha = batch_index[batch]
    frozen_accessions_path = MANIFEST_ROOT / "fresh-batches" / batch / "accessions.txt"
    expected_accessions = tuple(
        frozen_accessions_path.read_text(encoding="ascii").splitlines()
    )

    required = (
        "accessions.txt",
        "candidate-sequence-audit.tsv",
        "component-sequence-audit.tsv",
        "package-files.tsv",
        "batch-summary.json",
        "attempt-origin.json",
        "dehydrated.zip",
    )
    for name in required:
        if not (final_dir / name).exists():
            die(f"{batch}: missing required output {name}")

    accessions_path = final_dir / "accessions.txt"
    if sha256_file(accessions_path) != expected_accession_sha:
        die(f"{batch}: output accession SHA256 mismatch")
    observed_accessions = tuple(
        accessions_path.read_text(encoding="ascii").splitlines()
    )
    if observed_accessions != expected_accessions:
        die(f"{batch}: output accessions differ from frozen batch")

    summary = json.loads(
        (final_dir / "batch-summary.json").read_text(encoding="utf-8")
    )
    expected_summary = {
        "schema_version": 2,
        "datasets_version": DATASETS_VERSION,
        "environment_explicit_sha256": ENVIRONMENT_EXPLICIT_SHA256,
        "git_head": production_commit,
        "target_manifest_sha256": FRESH_MANIFEST_SHA256,
        "target_count": EXPECTED_TARGETS,
        "batch_index": batch_number,
        "batch_id": batch,
        "batch_count": EXPECTED_BATCHES,
        "batch_size": BATCH_SIZE,
        "requested_accessions": expected_count,
        "accessions_sha256": expected_accession_sha,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            die(
                f"{batch}: summary {key} mismatch: expected {expected!r}, "
                f"observed {summary.get(key)!r}"
            )

    candidate_path = final_dir / "candidate-sequence-audit.tsv"
    component_path = final_dir / "component-sequence-audit.tsv"
    package_files_path = final_dir / "package-files.tsv"
    attempt_path = final_dir / "attempt-origin.json"

    hashes = {
        "candidate_sequence_audit_sha256": candidate_path,
        "component_sequence_audit_sha256": component_path,
        "package_files_sha256": package_files_path,
        "attempt_origin_sha256": attempt_path,
        "dehydrated_zip_sha256": final_dir / "dehydrated.zip",
    }
    for key, path in hashes.items():
        expected = summary.get(key)
        if not isinstance(expected, str) or sha256_file(path) != expected:
            die(f"{batch}: {key} mismatch")

    candidate_fields, candidate_rows = read_tsv(candidate_path)
    required_candidate_fields = {
        "canonical_genbank_assembly_accession",
        "expected_biosample",
        "observed_biosample",
        "assembly_status",
        "current_accession",
        "assembly_level",
        "total_sequence_length",
        "ambiguous_base_count",
        "sequence_eligibility",
        "exclusion_reasons",
        "gbff_source",
    }
    if not required_candidate_fields.issubset(candidate_fields):
        die(f"{batch}: candidate audit schema mismatch")
    if len(candidate_rows) != expected_count:
        die(f"{batch}: candidate audit row count mismatch")

    candidate_accessions = tuple(
        row["canonical_genbank_assembly_accession"] for row in candidate_rows
    )
    if candidate_accessions != expected_accessions:
        die(f"{batch}: candidate audit accession order mismatch")

    for row in candidate_rows:
        accession = row["canonical_genbank_assembly_accession"]
        expected_biosample = biosamples[accession]
        if row["expected_biosample"] != expected_biosample:
            die(f"{batch}: expected BioSample mismatch")
        if row["observed_biosample"] != expected_biosample:
            die(f"{batch}: observed BioSample mismatch")
        if row["current_accession"] != accession:
            die(f"{batch}: current accession mismatch")
        if row["assembly_status"] != "current":
            die(f"{batch}: assembly status is not current")
        if row["assembly_level"] != "Complete Genome":
            die(f"{batch}: assembly level mismatch")
        if row["sequence_eligibility"] not in {"eligible", "ineligible"}:
            die(f"{batch}: unexpected sequence eligibility")

    _, component_rows = read_tsv(component_path)
    _, package_rows = read_tsv(package_files_path)
    if len(candidate_rows) != summary.get("candidate_records"):
        die(f"{batch}: candidate summary count mismatch")
    if len(component_rows) != summary.get("component_records"):
        die(f"{batch}: component summary count mismatch")
    if len(package_rows) != summary.get("package_files"):
        die(f"{batch}: package-file summary count mismatch")

    if verify_package_content:
        package = final_dir / "package"
        if not package.is_dir():
            die(f"{batch}: hydrated package directory missing")
        for row in package_rows:
            try:
                expected_size = int(row["size_bytes"])
            except (KeyError, ValueError):
                die(f"{batch}: invalid package file size")
            expected_sha = row.get("sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                die(f"{batch}: invalid package file SHA256")
            path = safe_package_path(package, row["path"])
            if not path.is_file():
                die(f"{batch}: package file missing: {row['path']}")
            if path.stat().st_size != expected_size:
                die(f"{batch}: package file size mismatch: {row['path']}")
            if sha256_file(path) != expected_sha:
                die(f"{batch}: package file SHA256 mismatch: {row['path']}")

    eligibility = Counter(row["sequence_eligibility"] for row in candidate_rows)
    exclusions = Counter()
    for row in candidate_rows:
        if row["exclusion_reasons"] != "none":
            exclusions.update(row["exclusion_reasons"].split("|"))
    topology = Counter(row.get("topology", "") for row in component_rows)
    gbff_sources = Counter(row["gbff_source"] for row in candidate_rows)

    return {
        "batch": batch,
        "requested_accessions": expected_count,
        "candidate_records": len(candidate_rows),
        "component_records": len(component_rows),
        "package_files": len(package_rows),
        "total_sequence_bases": sum(
            int(row["total_sequence_length"]) for row in candidate_rows
        ),
        "ambiguous_base_count": sum(
            int(row["ambiguous_base_count"]) for row in candidate_rows
        ),
        "sequence_eligibility_counts": dict(sorted(eligibility.items())),
        "sequence_exclusion_reason_counts": dict(sorted(exclusions.items())),
        "topology_counts": dict(sorted(topology.items())),
        "gbff_source_counts": dict(sorted(gbff_sources.items())),
        "package_content_verified": verify_package_content,
    }


def add_counts(target: Counter[str], values: Mapping[str, object]) -> None:
    for key, value in values.items():
        target[key] += int(value)


def validate_all(
    output_root: Path,
    production_commit: str,
    *,
    verify_package_content: bool,
) -> dict[str, object]:
    eligibility: Counter[str] = Counter()
    exclusions: Counter[str] = Counter()
    topology: Counter[str] = Counter()
    gbff_sources: Counter[str] = Counter()
    total_candidates = 0
    total_components = 0
    total_package_files = 0
    total_bases = 0
    total_ambiguous = 0

    for batch_number in range(1, EXPECTED_BATCHES + 1):
        result = validate_batch(
            output_root,
            production_commit,
            batch_number,
            verify_package_content=verify_package_content,
        )
        total_candidates += int(result["candidate_records"])
        total_components += int(result["component_records"])
        total_package_files += int(result["package_files"])
        total_bases += int(result["total_sequence_bases"])
        total_ambiguous += int(result["ambiguous_base_count"])
        add_counts(eligibility, result["sequence_eligibility_counts"])
        add_counts(exclusions, result["sequence_exclusion_reason_counts"])
        add_counts(topology, result["topology_counts"])
        add_counts(gbff_sources, result["gbff_source_counts"])

    if total_candidates != EXPECTED_TARGETS:
        die("aggregate candidate count mismatch")

    return {
        "schema_version": 1,
        "status": "FRESH_SEQUENCE_VALIDATION_COMPLETE",
        "production_commit": production_commit,
        "fresh_targets": EXPECTED_TARGETS,
        "batch_count": EXPECTED_BATCHES,
        "candidate_records": total_candidates,
        "component_records": total_components,
        "package_files": total_package_files,
        "total_sequence_bases": total_bases,
        "ambiguous_base_count": total_ambiguous,
        "sequence_eligibility_counts": dict(sorted(eligibility.items())),
        "sequence_exclusion_reason_counts": dict(sorted(exclusions.items())),
        "topology_counts": dict(sorted(topology.items())),
        "gbff_source_counts": dict(sorted(gbff_sources.items())),
        "package_content_verified": verify_package_content,
        "fresh_manifest_sha256": FRESH_MANIFEST_SHA256,
        "fresh_batch_index_sha256": FRESH_BATCH_INDEX_SHA256,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--production-commit", required=True)
    parser.add_argument("--batch", type=int)
    parser.add_argument("--verify-package-content", action="store_true")
    parser.add_argument("--write-summary", type=Path)
    args = parser.parse_args()

    if args.batch is not None:
        result = validate_batch(
            args.output_root,
            args.production_commit,
            args.batch,
            verify_package_content=args.verify_package_content,
        )
    else:
        result = validate_all(
            args.output_root,
            args.production_commit,
            verify_package_content=args.verify_package_content,
        )

    if args.write_summary is not None:
        if args.batch is not None:
            die("--write-summary is only valid for aggregate audit")
        if args.write_summary.exists():
            die("refusing to overwrite aggregate summary")
        args.write_summary.write_text(
            json.dumps(result, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
