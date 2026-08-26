#!/usr/bin/env python3
"""Recover BacSelect batches containing terminally unavailable NCBI payloads.

The recovery is additive. The failed source .partial directories are treated
as immutable evidence. Their hydrated packages are copied into a commit-scoped
recovery workspace before any candidate validation is performed.

A target may be recorded as acquisition_unavailable only when the frozen
dehydrated package itself describes exactly one unresolved fetch destination
for that accession, that destination is sequence_report.jsonl with expected
size zero, the destination remains missing/empty, and no genomic FASTA or GBFF
payload exists for the accession. All other unresolved states remain fatal.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

REPO = Path("/home/rwhite/github/bacselect")
WORKER_PATH = REPO / "validation/selector-v1/fresh_sequence_validation_batch.py"

SOURCE_PRODUCTION_COMMIT = "7aba4b0a2aa22c05ce808bf9b5811606bd3d2293"
SOURCE_OUTPUT_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
    "fresh-sequence-validation"
) / SOURCE_PRODUCTION_COMMIT

RECOVERY_ROOT_BASE = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
    "fresh-sequence-validation-recovery"
)

MANIFEST_ROOT = Path(
    "/NGS/scratch/EXT/Rhys_wkdir/bacselect/selector-v1/"
    "final-acquisition-manifests/"
    "a8f045506ac4a3f17034cd9170867995a87eb894"
)
FRESH_MANIFEST = MANIFEST_ROOT / "fresh-download-manifest.tsv"
FRESH_MANIFEST_SHA256 = (
    "1c9a73231d6b8ebfed76fb60621616588a4f51b1144e5d7880f14ddf26d1863b"
)
EXPECTED_TARGETS = 15_326
EXPECTED_BATCHES = 31
BATCH_SIZE = 500
FINAL_BATCH_SIZE = 326
RECOVERY_BATCHES = (24, 28)
SCHEMA_VERSION = 2

GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GCA_RE = re.compile(r"^GCA_[0-9]+\.[0-9]+$")

ACQUISITION_STATUS_FIELDS = [
    "canonical_genbank_assembly_accession",
    "acquisition_status",
    "acquisition_unavailable_reason",
    "unresolved_fetch_problems",
]

UNAVAILABLE_REASON = "datasets_catalog_without_sequence_payload"


def die(message: str) -> None:
    raise SystemExit(f"ERROR | {message}")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def write_tsv(
    path: Path,
    fields: Iterable[str],
    rows: Iterable[dict[str, object]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fields),
            delimiter="\t",
            lineterminator="\n",
            extrasaction="raise",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def load_worker():
    spec = importlib.util.spec_from_file_location(
        "bacselect_fresh_sequence_worker",
        WORKER_PATH,
    )
    if spec is None or spec.loader is None:
        die("unable to load frozen fresh-sequence worker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def require_clean_pushed_commit() -> str:
    head = git("rev-parse", "HEAD")
    origin = git("rev-parse", "origin/main")
    if not GIT_SHA_RE.fullmatch(head):
        die("invalid HEAD")
    if head != origin:
        die("HEAD does not match origin/main")
    if git("status", "--porcelain"):
        die("repository is not clean")
    return head


def batch_accessions(batch: int) -> tuple[str, ...]:
    path = (
        MANIFEST_ROOT
        / "fresh-batches"
        / f"batch-{batch:03d}"
        / "accessions.txt"
    )
    rows = tuple(path.read_text(encoding="ascii").splitlines())
    expected = FINAL_BATCH_SIZE if batch == EXPECTED_BATCHES else BATCH_SIZE

    if len(rows) != expected:
        die(f"batch-{batch:03d}: frozen accession count mismatch")
    if any(not GCA_RE.fullmatch(accession) for accession in rows):
        die(f"batch-{batch:03d}: invalid accession")

    return rows


def target_rows_for(accessions: tuple[str, ...]) -> list[dict[str, str]]:
    # Reuse the frozen worker's own target loader rather than recreating its
    # compatibility adapter here. In particular, load_targets() validates the
    # frozen manifest and adds source_biosample as the internal alias required
    # by validate_metadata() and validate_candidate_payload().
    worker = load_worker()
    rows = worker.load_targets(REPO)

    wanted = set(accessions)
    by_accession: dict[str, dict[str, str]] = {}

    for row in rows:
        accession = row["canonical_genbank_assembly_accession"]
        if accession not in wanted:
            continue
        if accession in by_accession:
            die("duplicate accession in normalized fresh target rows")
        by_accession[accession] = row

    if set(by_accession) != wanted:
        missing = sorted(wanted - set(by_accession))
        die(f"normalized fresh target rows missing for {missing!r}")

    selected = [by_accession[accession] for accession in accessions]

    for row in selected:
        if row.get("source_biosample") != row.get("fresh_biosample"):
            die(
                f"{row['canonical_genbank_assembly_accession']}: "
                "frozen target compatibility alias mismatch"
            )

    return selected


def problem_text(problems: list[tuple[str, str]]) -> str:
    return json.dumps(
        [
            {"relative_path": path, "problem": problem}
            for path, problem in problems
        ],
        sort_keys=True,
        separators=(",", ":"),
    )


def terminal_unavailable_reason(
    package: Path,
    accession: str,
    entries: list[dict[str, object]],
    problems: list[tuple[str, str]],
) -> str:
    """Return the terminal reason or fail closed for any other unresolved state."""

    expected_relative = f"data/{accession}/sequence_report.jsonl"

    if len(entries) != 1:
        die(
            f"{accession}: unresolved acquisition is not terminally classifiable; "
            f"fetch entry count={len(entries)}"
        )

    entry = entries[0]
    if entry.get("relative_path") != expected_relative:
        die(
            f"{accession}: unresolved acquisition is not terminally classifiable; "
            "unexpected fetch destination"
        )

    try:
        expected_size = int(entry.get("expected_size", -1))
    except (TypeError, ValueError):
        die(f"{accession}: invalid expected fetch size")

    if expected_size != 0:
        die(
            f"{accession}: unresolved acquisition is not terminally classifiable; "
            f"expected fetch size={expected_size}"
        )

    allowed_problems = {
        ((expected_relative, "empty"),),
        ((expected_relative, "missing"),),
    }
    if tuple(problems) not in allowed_problems:
        die(
            f"{accession}: unresolved acquisition is not terminally classifiable; "
            f"problems={problems!r}"
        )

    acc_dir = package / "ncbi_dataset" / "data" / accession

    fasta_files = list(acc_dir.glob("*.fna")) if acc_dir.is_dir() else []
    gbff = acc_dir / "genomic.gbff"

    if fasta_files:
        die(
            f"{accession}: terminal-unavailable rule refused because genomic FASTA exists"
        )

    if gbff.is_file() and gbff.stat().st_size > 0:
        die(
            f"{accession}: terminal-unavailable rule refused because GBFF exists"
        )

    return UNAVAILABLE_REASON


def recovery_output_root(recovery_commit: str) -> Path:
    return (
        RECOVERY_ROOT_BASE
        / recovery_commit
        / f"source-{SOURCE_PRODUCTION_COMMIT}"
    )


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


def verify_manifest_against_package(
    worker,
    manifest_rows: list[dict[str, str]],
    package: Path,
    *,
    label: str,
) -> None:
    observed = worker.package_file_manifest(package)
    if observed != manifest_rows:
        die(f"{label}: package manifest differs from recorded manifest")


def validate_recovery_artifacts(
    recovery_dir: Path,
    source_partial: Path,
    recovery_commit: str,
    batch: int,
    *,
    verify_package_content: bool,
) -> dict[str, object]:
    """Validate a recovery directory whether partial or finalized."""

    if batch not in RECOVERY_BATCHES:
        die(f"batch-{batch:03d}: not in frozen recovery set")
    if not GIT_SHA_RE.fullmatch(recovery_commit):
        die("invalid recovery commit")
    if not recovery_dir.is_dir():
        die(f"batch-{batch:03d}: recovery directory missing")

    batch_id = f"batch-{batch:03d}"
    source_final = SOURCE_OUTPUT_ROOT / batch_id

    if source_final.exists():
        die(f"{batch_id}: source execution unexpectedly finalized")
    if not source_partial.is_dir():
        die(f"{batch_id}: source failed partial missing")

    accessions = batch_accessions(batch)
    target_rows = target_rows_for(accessions)
    target_by_accession = {
        row["canonical_genbank_assembly_accession"]: row
        for row in target_rows
    }

    required = (
        "candidate-sequence-audit.tsv",
        "component-sequence-audit.tsv",
        "acquisition-status.tsv",
        "source-package-files.tsv",
        "recovery-package-files.tsv",
        "recovery-summary.json",
        "package",
    )
    for name in required:
        if not (recovery_dir / name).exists():
            die(f"{batch_id}: missing recovery output {name}")

    summary = json.loads(
        (recovery_dir / "recovery-summary.json").read_text(encoding="utf-8")
    )
    expected_summary = {
        "schema_version": SCHEMA_VERSION,
        "recovery_commit": recovery_commit,
        "source_production_commit": SOURCE_PRODUCTION_COMMIT,
        "source_batch": batch_id,
        "target_manifest_sha256": FRESH_MANIFEST_SHA256,
        "requested_accessions": len(accessions),
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            die(
                f"{batch_id}: recovery summary {key} mismatch: "
                f"expected {expected!r}, observed {summary.get(key)!r}"
            )

    paths = {
        "candidate_sequence_audit_sha256":
            recovery_dir / "candidate-sequence-audit.tsv",
        "component_sequence_audit_sha256":
            recovery_dir / "component-sequence-audit.tsv",
        "acquisition_status_sha256":
            recovery_dir / "acquisition-status.tsv",
        "source_package_files_sha256":
            recovery_dir / "source-package-files.tsv",
        "recovery_package_files_sha256":
            recovery_dir / "recovery-package-files.tsv",
    }
    for key, path in paths.items():
        observed = summary.get(key)
        if not isinstance(observed, str) or sha256_file(path) != observed:
            die(f"{batch_id}: {key} mismatch")

    status_fields, status_rows = read_tsv(
        recovery_dir / "acquisition-status.tsv"
    )
    if status_fields != ACQUISITION_STATUS_FIELDS:
        die(f"{batch_id}: acquisition-status schema mismatch")
    if len(status_rows) != len(accessions):
        die(f"{batch_id}: acquisition-status row count mismatch")
    if tuple(
        row["canonical_genbank_assembly_accession"]
        for row in status_rows
    ) != accessions:
        die(f"{batch_id}: acquisition-status accession order mismatch")

    unavailable = {
        row["canonical_genbank_assembly_accession"]
        for row in status_rows
        if row["acquisition_status"] == "unavailable"
    }
    available = [
        row["canonical_genbank_assembly_accession"]
        for row in status_rows
        if row["acquisition_status"] == "available"
    ]

    if not unavailable:
        die(f"{batch_id}: recovery contains no unavailable acquisition")
    if any(
        row["acquisition_status"] not in {"available", "unavailable"}
        for row in status_rows
    ):
        die(f"{batch_id}: unexpected acquisition status")

    for row in status_rows:
        if row["acquisition_status"] == "unavailable":
            if row["acquisition_unavailable_reason"] != UNAVAILABLE_REASON:
                die(f"{batch_id}: unexpected unavailable reason")
        else:
            if row["acquisition_unavailable_reason"] != "none":
                die(f"{batch_id}: available row carries unavailable reason")
            if row["unresolved_fetch_problems"] != "none":
                die(f"{batch_id}: available row carries unresolved problems")

    _, candidate_rows = read_tsv(
        recovery_dir / "candidate-sequence-audit.tsv"
    )
    if [
        row["canonical_genbank_assembly_accession"]
        for row in candidate_rows
    ] != available:
        die(f"{batch_id}: candidate rows do not equal available subset")

    for row in candidate_rows:
        accession = row["canonical_genbank_assembly_accession"]
        target = target_by_accession[accession]
        if row["expected_biosample"] != target["fresh_biosample"]:
            die(f"{batch_id}: expected BioSample mismatch")
        if row["observed_biosample"] != target["fresh_biosample"]:
            die(f"{batch_id}: observed BioSample mismatch")
        if row["current_accession"] != accession:
            die(f"{batch_id}: current accession mismatch")
        if row["assembly_status"] != "current":
            die(f"{batch_id}: non-current available candidate")
        if row["assembly_level"] != "Complete Genome":
            die(f"{batch_id}: assembly level mismatch")
        if row["sequence_eligibility"] not in {"eligible", "ineligible"}:
            die(f"{batch_id}: unexpected sequence eligibility")

    _, component_rows = read_tsv(
        recovery_dir / "component-sequence-audit.tsv"
    )
    if any(
        row["canonical_genbank_assembly_accession"] in unavailable
        for row in component_rows
    ):
        die(f"{batch_id}: unavailable accession appears in component audit")

    worker = load_worker()

    source_package = source_partial / "package"
    recovery_package = recovery_dir / "package"

    source_fields, source_package_rows = read_tsv(
        recovery_dir / "source-package-files.tsv"
    )
    recovery_fields, recovery_package_rows = read_tsv(
        recovery_dir / "recovery-package-files.tsv"
    )
    expected_package_fields = list(worker.PACKAGE_FILE_FIELDS)

    if source_fields != expected_package_fields:
        die(f"{batch_id}: source package manifest schema mismatch")
    if recovery_fields != expected_package_fields:
        die(f"{batch_id}: recovery package manifest schema mismatch")

    if len(source_package_rows) != summary.get("source_package_files"):
        die(f"{batch_id}: source package file count mismatch")
    if len(recovery_package_rows) != summary.get("recovery_package_files"):
        die(f"{batch_id}: recovery package file count mismatch")

    if verify_package_content:
        verify_manifest_against_package(
            worker,
            source_package_rows,
            source_package,
            label=f"{batch_id} source",
        )
        verify_manifest_against_package(
            worker,
            recovery_package_rows,
            recovery_package,
            label=f"{batch_id} recovery",
        )

    (
        data_root,
        observed_biosamples,
        _assembly_report,
    ) = worker.validate_metadata(
        recovery_package,
        target_rows,
    )
    (
        _fetch_path,
        _fetch_entries,
        fetch_by_accession,
    ) = worker.parse_fetch_txt(
        recovery_package,
        set(accessions),
    )
    unresolved = worker.unresolved_fetches(
        recovery_package,
        fetch_by_accession,
    )
    if set(unresolved) != unavailable:
        die(
            f"{batch_id}: current recovery unresolved set differs from "
            "recorded unavailable set"
        )

    for accession in sorted(unavailable):
        terminal_unavailable_reason(
            recovery_package,
            accession,
            fetch_by_accession[accession],
            unresolved[accession],
        )

    # Re-run frozen candidate validation on the recovery copy. This can only
    # write within the recovery package, never into the source evidence.
    for accession in available:
        candidate, _components = worker.validate_candidate_payload(
            data_root,
            target_by_accession[accession],
            observed_biosamples[accession],
        )
        if candidate["canonical_genbank_assembly_accession"] != accession:
            die(f"{batch_id}: revalidated candidate accession mismatch")

    # If frozen validation created fallback provenance, the package manifest
    # must already have recorded it. Re-check after the validation calls.
    if verify_package_content:
        verify_manifest_against_package(
            worker,
            recovery_package_rows,
            recovery_package,
            label=f"{batch_id} recovery after candidate revalidation",
        )

    eligibility = Counter(
        row["sequence_eligibility"]
        for row in candidate_rows
    )
    exclusions: Counter[str] = Counter()
    for row in candidate_rows:
        if row["exclusion_reasons"] != "none":
            exclusions.update(row["exclusion_reasons"].split("|"))

    topology = Counter(row["topology"] for row in component_rows)
    gbff_sources = Counter(row["gbff_source"] for row in candidate_rows)
    acquisition = Counter(row["acquisition_status"] for row in status_rows)

    if len(candidate_rows) != acquisition["available"]:
        die(f"{batch_id}: available count does not equal candidate rows")
    if acquisition["available"] + acquisition["unavailable"] != len(accessions):
        die(f"{batch_id}: acquisition accounting mismatch")
    if sum(eligibility.values()) != len(candidate_rows):
        die(f"{batch_id}: sequence eligibility accounting mismatch")

    return {
        "batch": batch_id,
        "requested_accessions": len(accessions),
        "acquisition_status_counts": dict(sorted(acquisition.items())),
        "candidate_records": len(candidate_rows),
        "component_records": len(component_rows),
        "total_sequence_bases": sum(
            int(row["total_sequence_length"])
            for row in candidate_rows
        ),
        "ambiguous_base_count": sum(
            int(row["ambiguous_base_count"])
            for row in candidate_rows
        ),
        "sequence_eligibility_counts": dict(sorted(eligibility.items())),
        "sequence_exclusion_reason_counts": dict(sorted(exclusions.items())),
        "topology_counts": dict(sorted(topology.items())),
        "gbff_source_counts": dict(sorted(gbff_sources.items())),
        "package_content_verified": verify_package_content,
    }


def audit_recovery_batch(
    output_root: Path,
    recovery_commit: str,
    batch: int,
    *,
    verify_package_content: bool,
) -> dict[str, object]:
    batch_id = f"batch-{batch:03d}"
    final_dir = output_root / batch_id
    partial_dir = output_root / f"{batch_id}.partial"
    source_partial = SOURCE_OUTPUT_ROOT / f"{batch_id}.partial"

    if not final_dir.is_dir():
        die(f"{batch_id}: recovery final missing")
    if partial_dir.exists():
        die(f"{batch_id}: recovery final and partial both exist")

    return validate_recovery_artifacts(
        final_dir,
        source_partial,
        recovery_commit,
        batch,
        verify_package_content=verify_package_content,
    )


def recover_batch(batch: int) -> Path:
    if batch not in RECOVERY_BATCHES:
        die(
            f"batch-{batch:03d}: not in frozen recovery batch set "
            f"{RECOVERY_BATCHES!r}"
        )

    recovery_commit = require_clean_pushed_commit()
    worker = load_worker()

    accessions = batch_accessions(batch)
    target_rows = target_rows_for(accessions)

    batch_id = f"batch-{batch:03d}"
    source_final = SOURCE_OUTPUT_ROOT / batch_id
    source_partial = SOURCE_OUTPUT_ROOT / f"{batch_id}.partial"

    if source_final.exists():
        die(f"{batch_id}: source final unexpectedly exists")
    if not source_partial.is_dir():
        die(f"{batch_id}: source partial is missing")

    source_package = source_partial / "package"
    if not source_package.is_dir():
        die(f"{batch_id}: source package missing")

    source_accessions = tuple(
        (source_partial / "accessions.txt")
        .read_text(encoding="ascii")
        .splitlines()
    )
    if source_accessions != accessions:
        die(f"{batch_id}: source partial accessions differ from frozen batch")

    output_root = recovery_output_root(recovery_commit)
    final_dir = output_root / batch_id
    partial_dir = output_root / f"{batch_id}.partial"

    if final_dir.exists() or partial_dir.exists():
        die(f"{batch_id}: recovery output already exists")

    partial_dir.parent.mkdir(parents=True, exist_ok=True)
    partial_dir.mkdir()

    # Freeze a content manifest from the failed source package before copying.
    source_package_files = worker.package_file_manifest(source_package)
    source_package_manifest = partial_dir / "source-package-files.tsv"
    worker.write_tsv(
        source_package_manifest,
        worker.PACKAGE_FILE_FIELDS,
        source_package_files,
    )

    # Work only on a recovery copy. Frozen candidate validation may invoke its
    # EFetch GBFF fallback, and that must never mutate the source .partial.
    package = partial_dir / "package"
    shutil.copytree(
        source_package,
        package,
        copy_function=shutil.copy2,
    )

    copied_package_files = worker.package_file_manifest(package)
    if copied_package_files != source_package_files:
        die(f"{batch_id}: recovery package copy differs from source package")

    (
        data_root,
        observed_biosamples,
        assembly_report,
    ) = worker.validate_metadata(
        package,
        target_rows,
    )

    (
        fetch_path,
        fetch_entries,
        fetch_by_accession,
    ) = worker.parse_fetch_txt(
        package,
        set(accessions),
    )

    unresolved = worker.unresolved_fetches(
        package,
        fetch_by_accession,
    )
    if not unresolved:
        die(f"{batch_id}: no unresolved acquisition remains to recover")

    unavailable: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for accession in sorted(unresolved):
        reason = terminal_unavailable_reason(
            package,
            accession,
            fetch_by_accession[accession],
            unresolved[accession],
        )
        unavailable[accession] = (reason, unresolved[accession])

    candidate_rows: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    status_rows: list[dict[str, object]] = []

    target_by_accession = {
        row["canonical_genbank_assembly_accession"]: row
        for row in target_rows
    }

    for accession in accessions:
        if accession in unavailable:
            reason, problems = unavailable[accession]
            status_rows.append(
                {
                    "canonical_genbank_assembly_accession": accession,
                    "acquisition_status": "unavailable",
                    "acquisition_unavailable_reason": reason,
                    "unresolved_fetch_problems": problem_text(problems),
                }
            )
            continue

        candidate, components = worker.validate_candidate_payload(
            data_root,
            target_by_accession[accession],
            observed_biosamples[accession],
        )
        candidate_rows.append(candidate)
        component_rows.extend(components)
        status_rows.append(
            {
                "canonical_genbank_assembly_accession": accession,
                "acquisition_status": "available",
                "acquisition_unavailable_reason": "none",
                "unresolved_fetch_problems": "none",
            }
        )

    if [
        row["canonical_genbank_assembly_accession"]
        for row in status_rows
    ] != list(accessions):
        die(f"{batch_id}: acquisition status order mismatch")

    available_accessions = [
        row["canonical_genbank_assembly_accession"]
        for row in status_rows
        if row["acquisition_status"] == "available"
    ]
    if [
        row["canonical_genbank_assembly_accession"]
        for row in candidate_rows
    ] != available_accessions:
        die(
            f"{batch_id}: candidate audit does not match "
            "available acquisition subset"
        )

    candidate_path = partial_dir / "candidate-sequence-audit.tsv"
    component_path = partial_dir / "component-sequence-audit.tsv"
    status_path = partial_dir / "acquisition-status.tsv"
    recovery_package_manifest = partial_dir / "recovery-package-files.tsv"

    worker.write_tsv(
        candidate_path,
        worker.CANDIDATE_AUDIT_FIELDS,
        candidate_rows,
    )
    worker.write_tsv(
        component_path,
        worker.COMPONENT_AUDIT_FIELDS,
        component_rows,
    )
    write_tsv(
        status_path,
        ACQUISITION_STATUS_FIELDS,
        status_rows,
    )

    recovery_package_files = worker.package_file_manifest(package)
    worker.write_tsv(
        recovery_package_manifest,
        worker.PACKAGE_FILE_FIELDS,
        recovery_package_files,
    )

    eligibility_counts = Counter(
        row["sequence_eligibility"]
        for row in candidate_rows
    )
    exclusion_counts: Counter[str] = Counter()
    for row in candidate_rows:
        if row["exclusion_reasons"] != "none":
            exclusion_counts.update(row["exclusion_reasons"].split("|"))

    topology_counts = Counter(
        row["topology"]
        for row in component_rows
    )
    gbff_source_counts = Counter(
        row["gbff_source"]
        for row in candidate_rows
    )

    acquisition_counts = Counter(
        row["acquisition_status"]
        for row in status_rows
    )
    unavailable_reason_counts = Counter(
        row["acquisition_unavailable_reason"]
        for row in status_rows
        if row["acquisition_status"] == "unavailable"
    )

    summary = {
        "schema_version": SCHEMA_VERSION,
        "recovery_commit": recovery_commit,
        "recovery_script":
            "validation/selector-v1/recover_acquisition_unavailable.py",
        "recovery_script_sha256": sha256_file(Path(__file__).resolve()),
        "source_production_commit": SOURCE_PRODUCTION_COMMIT,
        "source_batch": batch_id,
        "target_manifest_sha256": FRESH_MANIFEST_SHA256,
        "requested_accessions": len(accessions),
        "accessions_sha256":
            sha256_file(source_partial / "accessions.txt"),
        "source_attempt_origin_sha256":
            sha256_file(source_partial / "attempt-origin.json"),
        "source_dehydrated_zip_sha256":
            sha256_file(source_partial / "dehydrated.zip"),
        "source_assembly_data_report_sha256":
            sha256_file(assembly_report),
        "source_fetch_txt_sha256":
            sha256_file(fetch_path),
        "source_fetch_entries": len(fetch_entries),
        "acquisition_status_counts":
            dict(sorted(acquisition_counts.items())),
        "acquisition_unavailable_reason_counts":
            dict(sorted(unavailable_reason_counts.items())),
        "candidate_records": len(candidate_rows),
        "component_records": len(component_rows),
        "sequence_eligibility_counts":
            dict(sorted(eligibility_counts.items())),
        "sequence_exclusion_reason_counts":
            dict(sorted(exclusion_counts.items())),
        "topology_counts":
            dict(sorted(topology_counts.items())),
        "gbff_source_counts":
            dict(sorted(gbff_source_counts.items())),
        "total_sequence_bases": sum(
            int(row["total_sequence_length"])
            for row in candidate_rows
        ),
        "ambiguous_base_count": sum(
            int(row["ambiguous_base_count"])
            for row in candidate_rows
        ),
        "source_package_files": len(source_package_files),
        "recovery_package_files": len(recovery_package_files),
        "candidate_sequence_audit_sha256":
            sha256_file(candidate_path),
        "component_sequence_audit_sha256":
            sha256_file(component_path),
        "acquisition_status_sha256":
            sha256_file(status_path),
        "source_package_files_sha256":
            sha256_file(source_package_manifest),
        "recovery_package_files_sha256":
            sha256_file(recovery_package_manifest),
        "execution_completed_at_utc": utc_now(),
    }

    write_json(
        partial_dir / "recovery-summary.json",
        summary,
    )

    # Pre-final audit validates the .partial directly. Only after this passes is
    # the recovery directory atomically renamed to its finalized name.
    validate_recovery_artifacts(
        partial_dir,
        source_partial,
        recovery_commit,
        batch,
        verify_package_content=True,
    )

    partial_dir.replace(final_dir)

    # Re-audit the finalized path so both pre-final and finalized states use
    # the same validation implementation.
    audit_recovery_batch(
        output_root,
        recovery_commit,
        batch,
        verify_package_content=False,
    )

    print(
        f"PASS | {batch_id}: requested={len(accessions)} "
        f"available={acquisition_counts['available']} "
        f"unavailable={acquisition_counts['unavailable']}"
    )
    print(
        "sequence eligibility | "
        f"eligible={eligibility_counts['eligible']} | "
        f"ineligible={eligibility_counts['ineligible']} | "
        "unavailable=not_assessed"
    )
    print(f"summary | {final_dir / 'recovery-summary.json'}")

    return final_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--verify-package-content", action="store_true")
    args = parser.parse_args()

    recovery_commit = require_clean_pushed_commit()
    output_root = recovery_output_root(recovery_commit)

    if args.audit_only:
        result = audit_recovery_batch(
            output_root,
            recovery_commit,
            args.batch,
            verify_package_content=args.verify_package_content,
        )
        print(json.dumps(result, sort_keys=True))
        print(f"PASS | batch-{args.batch:03d} recovery audit")
    else:
        recover_batch(args.batch)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
