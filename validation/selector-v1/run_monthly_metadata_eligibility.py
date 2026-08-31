#!/usr/bin/env python3
"""Execute BacSelect monthly metadata eligibility from an audited Stage 1."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Callable, Sequence

from bacselect import source_eligibility
from bacselect.monthly_metadata_eligibility import (
    MonthlyMetadataEligibilityError,
    assess_monthly_source_metadata,
    audit_metadata_assessments,
    audit_metadata_eligibility_record,
    audit_metadata_summary,
    serialize_metadata_assessments,
    serialize_metadata_eligibility_record,
    serialize_metadata_summary,
)
from bacselect.monthly_release_start import (
    MonthlyReleaseStartError,
    audit_source_snapshot_record,
)


SOURCE_ELIGIBILITY_RELATIVE = Path(
    "src/bacselect/source_eligibility.py"
)

METADATA_CORE_RELATIVE = Path(
    "src/bacselect/monthly_metadata_eligibility.py"
)

METADATA_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_metadata_eligibility.py"
)

METADATA_METHOD_RELATIVE = Path(
    "validation/selector-v1/prospective-monthly-metadata-eligibility.md"
)

EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/prospective-monthly-metadata-eligibility-execution.md"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_metadata_eligibility.py"
)

EXPECTED_SOURCE_ELIGIBILITY_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2"
)

EXPECTED_METADATA_CORE_SHA256 = (
    "90c86d304d42c3e7dc4978a28d1d01a92660d9a359e07516f536ff3a0a2df87f"
)

EXPECTED_METADATA_CORE_TEST_SHA256 = (
    "e50bb48c73e98a619a0d2a180a71d74b295acd9d5d5b3f18e6641a47fa8e6c1e"
)

EXPECTED_METADATA_METHOD_SHA256 = (
    "bca379e3e3657863ebc9a9dbff2b3c6bca6b37684d5fbf15ab24102410230d51"
)

EXPECTED_EXECUTION_METHOD_SHA256 = (
    "d99db46fc4487a1e880abc9f0e7b67a780557747df7f80638c4374b22d271aaa"
)

EXPECTED_DATASETS_VERSION = "18.35.0"

EXPECTED_DATASETS_ENVIRONMENT_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

CHECKPOINT_NAME = (
    "release-start-checkpoint.json"
)

RAW_RESPONSE_NAME = (
    "assembly_data_report.raw.jsonl"
)

SOURCE_SNAPSHOT_RECORD_NAME = (
    "source-snapshot-record.json"
)

METADATA_STAGE_NAME = (
    "metadata-eligibility"
)

METADATA_PARTIAL_STAGE_NAME = (
    "metadata-eligibility.partial"
)

ASSESSMENTS_NAME = (
    "metadata-eligibility-assessments.jsonl"
)

SUMMARY_NAME = (
    "metadata-eligibility-summary.json"
)

RECORD_NAME = (
    "metadata-eligibility-record.json"
)

COMPLETION_NAME = (
    "metadata-eligibility-completion.json"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-metadata-eligibility-completion-v1"
)

COMPLETION_STATUS = (
    "METADATA_ELIGIBILITY_EXECUTION_COMPLETE"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)


class MonthlyMetadataEligibilityExecutionError(
    RuntimeError
):
    """Raised when monthly metadata execution fails closed."""


@dataclass(frozen=True)
class Stage1Contract:
    release_id: str
    source_snapshot_id: str
    stage1_root: Path
    checkpoint_payload: bytes
    raw_response: bytes
    snapshot_payload: bytes
    snapshot_sha256: str


@dataclass(frozen=True)
class MonthlyMetadataEligibilityResult:
    release_id: str
    source_snapshot_id: str
    stage_root: Path
    assessment_count: int
    retained_count: int
    excluded_count: int
    withheld_count: int
    assessments_sha256: str
    summary_sha256: str
    record_sha256: str
    completion_sha256: str


def validate_git_commit(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or COMMIT_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            f"{label} must be a lowercase 40-character Git commit"
        )

    return value


def validate_sha256(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or SHA256_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            f"{label} must be lowercase SHA256"
        )

    return value


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024
                * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    *,
    label: str,
    reader: Callable[
        [Path],
        str,
    ] = sha256_file,
) -> None:
    expected_sha = validate_sha256(
        expected,
        label=(
            f"expected {label} SHA256"
        ),
    )

    observed = reader(
        Path(
            path
        )
    )

    if observed != expected_sha:
        raise MonthlyMetadataEligibilityExecutionError(
            f"{label} SHA256 mismatch: {observed}"
        )


def git_output(
    repo: Path,
    *args: str,
) -> str:
    """Perform one local Git read."""

    result = subprocess.run(
        (
            "git",
            *args,
        ),
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise MonthlyMetadataEligibilityExecutionError(
            "Git command failed: "
            + " ".join(
                args
            )
            + ": "
            + (
                result.stderr.strip()
                or result.stdout.strip()
            )
        )

    return result.stdout.strip()


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    git_reader: Callable[
        ...,
        str,
    ] = git_output,
    file_sha256_reader: Callable[
        [Path],
        str,
    ] = sha256_file,
) -> None:
    """Require the exact pushed clean executor implementation."""

    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    if git_reader(
        repo,
        "rev-parse",
        "HEAD",
    ) != commit:
        raise MonthlyMetadataEligibilityExecutionError(
            "repository HEAD mismatch"
        )

    if git_reader(
        repo,
        "rev-parse",
        "origin/main",
    ) != commit:
        raise MonthlyMetadataEligibilityExecutionError(
            "local origin/main mismatch"
        )

    if git_reader(
        repo,
        "status",
        "--porcelain",
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            "repository working tree is not clean"
        )

    require_sha256(
        repo
        / SOURCE_ELIGIBILITY_RELATIVE,
        EXPECTED_SOURCE_ELIGIBILITY_SHA256,
        label=(
            "frozen source-eligibility implementation"
        ),
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / METADATA_CORE_RELATIVE,
        EXPECTED_METADATA_CORE_SHA256,
        label=(
            "monthly metadata-eligibility contract"
        ),
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / METADATA_CORE_TEST_RELATIVE,
        EXPECTED_METADATA_CORE_TEST_SHA256,
        label=(
            "monthly metadata-eligibility contract test"
        ),
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / METADATA_METHOD_RELATIVE,
        EXPECTED_METADATA_METHOD_SHA256,
        label=(
            "monthly metadata-eligibility contract method"
        ),
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / EXECUTION_METHOD_RELATIVE,
        EXPECTED_EXECUTION_METHOD_SHA256,
        label=(
            "monthly metadata-eligibility execution method"
        ),
        reader=file_sha256_reader,
    )

    wrapper_path = Path(
        __file__
    ).resolve()

    require_sha256(
        wrapper_path,
        expected_wrapper_sha256,
        label=(
            "monthly metadata-eligibility execution wrapper"
        ),
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label=(
            "monthly metadata-eligibility execution wrapper test"
        ),
        reader=file_sha256_reader,
    )

    if (
        source_eligibility.DATASETS_VERSION
        != EXPECTED_DATASETS_VERSION
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            "source-eligibility Datasets version binding changed"
        )


def fsync_directory(
    path: Path,
) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY,
    )

    try:
        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )


def write_atomic_fresh(
    path: Path,
    payload: bytes,
) -> None:
    """Atomically create one fresh mode-0644 artifact."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "artifact payload must be bytes"
        )

    if path.exists():
        raise MonthlyMetadataEligibilityExecutionError(
            f"refusing to overwrite artifact: {path.name}"
        )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if temporary.exists():
        raise MonthlyMetadataEligibilityExecutionError(
            f"temporary artifact already exists: {temporary.name}"
        )

    descriptor = os.open(
        temporary,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL,
        0o644,
    )

    try:
        os.fchmod(
            descriptor,
            0o644,
        )

        offset = 0

        while offset < len(
            payload
        ):
            written = os.write(
                descriptor,
                payload[
                    offset:
                ],
            )

            if written <= 0:
                raise MonthlyMetadataEligibilityExecutionError(
                    f"short write for artifact: {path.name}"
                )

            offset += written

        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )

    os.replace(
        temporary,
        path,
    )

    fsync_directory(
        path.parent
    )

    if path.read_bytes() != payload:
        raise MonthlyMetadataEligibilityExecutionError(
            f"artifact readback mismatch: {path.name}"
        )

    if stat.S_IMODE(
        path.stat().st_mode
    ) != 0o644:
        raise MonthlyMetadataEligibilityExecutionError(
            f"artifact mode mismatch: {path.name}"
        )


def load_stage1_contract(
    *,
    production_root: Path,
    stage1_root: Path,
    expected_commit: str,
) -> Stage1Contract:
    """Audit the exact Stage 1 source snapshot before metadata work."""

    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    production = Path(
        production_root
    )

    if not production.is_absolute():
        raise MonthlyMetadataEligibilityExecutionError(
            "production root must be absolute"
        )

    supplied_stage1 = Path(
        stage1_root
    )

    if not supplied_stage1.is_absolute():
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 production root must be absolute"
        )

    stage1 = supplied_stage1.resolve()

    checkpoint_path = (
        stage1
        / CHECKPOINT_NAME
    )

    raw_path = (
        stage1
        / RAW_RESPONSE_NAME
    )

    snapshot_path = (
        stage1
        / SOURCE_SNAPSHOT_RECORD_NAME
    )

    for path, label in (
        (
            checkpoint_path,
            "release-start checkpoint",
        ),
        (
            raw_path,
            "raw source response",
        ),
        (
            snapshot_path,
            "source-snapshot record",
        ),
    ):
        if not path.is_file():
            raise MonthlyMetadataEligibilityExecutionError(
                f"missing Stage 1 {label}: {path}"
            )

    checkpoint = (
        checkpoint_path.read_bytes()
    )

    raw_response = (
        raw_path.read_bytes()
    )

    snapshot_payload = (
        snapshot_path.read_bytes()
    )

    try:
        snapshot = (
            audit_source_snapshot_record(
                snapshot_payload,
                release_start_checkpoint=(
                    checkpoint
                ),
                raw_response=(
                    raw_response
                ),
            )
        )
    except MonthlyReleaseStartError as exc:
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 source-snapshot audit failed"
        ) from exc

    if snapshot[
        "expected_git_commit"
    ] != commit:
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 source snapshot was produced by a different commit"
        )

    if snapshot[
        "ncbi_datasets_version"
    ] != EXPECTED_DATASETS_VERSION:
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 NCBI Datasets version changed"
        )

    if snapshot[
        "ncbi_datasets_environment_sha256"
    ] != EXPECTED_DATASETS_ENVIRONMENT_SHA256:
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 NCBI environment identity changed"
        )

    release_id = str(
        snapshot[
            "release_id"
        ]
    )

    if RELEASE_RE.fullmatch(
        release_id
    ) is None:
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 release ID is invalid"
        )

    expected_stage1 = (
        production.resolve()
        / release_id
        / "production"
        / commit
    )

    if stage1 != expected_stage1:
        raise MonthlyMetadataEligibilityExecutionError(
            "Stage 1 production root does not match "
            "release/commit production identity"
        )

    snapshot_sha = hashlib.sha256(
        snapshot_payload
    ).hexdigest()

    return Stage1Contract(
        release_id=release_id,
        source_snapshot_id=str(
            snapshot[
                "source_snapshot_id"
            ]
        ),
        stage1_root=stage1,
        checkpoint_payload=checkpoint,
        raw_response=raw_response,
        snapshot_payload=(
            snapshot_payload
        ),
        snapshot_sha256=(
            snapshot_sha
        ),
    )


def create_partial_stage(
    stage1_root: Path,
) -> tuple[
    Path,
    Path,
]:
    """Create the hidden incomplete stage directory."""

    final = (
        stage1_root
        / METADATA_STAGE_NAME
    )

    partial = (
        stage1_root
        / METADATA_PARTIAL_STAGE_NAME
    )

    completion = (
        stage1_root
        / COMPLETION_NAME
    )

    if final.exists():
        raise MonthlyMetadataEligibilityExecutionError(
            "metadata-eligibility stage already exists"
        )

    if partial.exists():
        raise MonthlyMetadataEligibilityExecutionError(
            "metadata-eligibility partial stage already exists"
        )

    if completion.exists():
        raise MonthlyMetadataEligibilityExecutionError(
            "metadata-eligibility completion receipt already exists"
        )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    os.chmod(
        partial,
        0o755,
    )

    fsync_directory(
        stage1_root
    )

    return (
        partial,
        final,
    )


def build_completion_receipt(
    *,
    release_id: str,
    source_snapshot_id: str,
    source_snapshot_record_sha256: str,
    execution_commit: str,
    assessments_sha256: str,
    summary_sha256: str,
    record_sha256: str,
) -> bytes:
    """Build deterministic execution-completion evidence."""

    if (
        not isinstance(
            release_id,
            str,
        )
        or RELEASE_RE.fullmatch(
            release_id
        )
        is None
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            "completion receipt release ID is invalid"
        )

    if (
        not isinstance(
            source_snapshot_id,
            str,
        )
        or not source_snapshot_id
        or source_snapshot_id
        != source_snapshot_id.strip()
        or any(
            character.isspace()
            for character
            in source_snapshot_id
        )
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            "completion receipt source snapshot ID is invalid"
        )

    commit = validate_git_commit(
        execution_commit,
        label="completion receipt execution commit",
    )

    snapshot_sha = validate_sha256(
        source_snapshot_record_sha256,
        label="completion receipt source-snapshot-record SHA256",
    )

    assessment_sha = validate_sha256(
        assessments_sha256,
        label="completion receipt assessments SHA256",
    )

    summary_value_sha = validate_sha256(
        summary_sha256,
        label="completion receipt summary SHA256",
    )

    record_value_sha = validate_sha256(
        record_sha256,
        label="completion receipt record SHA256",
    )

    from bacselect.monthly_release_start import (
        canonical_json_bytes,
    )

    return canonical_json_bytes(
        {
            "assessments_sha256":
                assessment_sha,
            "execution_commit":
                commit,
            "metadata_stage_name":
                METADATA_STAGE_NAME,
            "record_sha256":
                record_value_sha,
            "release_id":
                release_id,
            "schema_version":
                COMPLETION_SCHEMA,
            "source_snapshot_id":
                source_snapshot_id,
            "source_snapshot_record_sha256":
                snapshot_sha,
            "status":
                COMPLETION_STATUS,
            "summary_sha256":
                summary_value_sha,
        }
    )


def audit_completion_receipt(
    payload: bytes,
    **kwargs,
) -> None:
    """Require exact deterministic completion-receipt bytes."""

    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "completion receipt must be bytes"
        )

    expected = build_completion_receipt(
        **kwargs
    )

    if payload != expected:
        raise MonthlyMetadataEligibilityExecutionError(
            "metadata-eligibility completion receipt changed"
        )


def execute_monthly_metadata_eligibility(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    execution_commit: str,
) -> MonthlyMetadataEligibilityResult:
    """Materialize one deterministic metadata-eligibility stage."""

    del repo

    upstream = load_stage1_contract(
        production_root=production_root,
        stage1_root=stage1_root,
        expected_commit=execution_commit,
    )

    partial, final = (
        create_partial_stage(
            upstream.stage1_root
        )
    )

    try:
        assessments = (
            assess_monthly_source_metadata(
                upstream.raw_response
            )
        )

        assessments_payload = (
            serialize_metadata_assessments(
                assessments
            )
        )

        summary_payload = (
            serialize_metadata_summary(
                assessments
            )
        )

        record_payload = (
            serialize_metadata_eligibility_record(
                source_snapshot_id=(
                    upstream.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    upstream.snapshot_sha256
                ),
                raw_response=(
                    upstream.raw_response
                ),
                assessments_payload=(
                    assessments_payload
                ),
                summary_payload=(
                    summary_payload
                ),
                source_eligibility_sha256=(
                    EXPECTED_SOURCE_ELIGIBILITY_SHA256
                ),
            )
        )

        assessments_path = (
            partial
            / ASSESSMENTS_NAME
        )

        summary_path = (
            partial
            / SUMMARY_NAME
        )

        record_path = (
            partial
            / RECORD_NAME
        )

        write_atomic_fresh(
            assessments_path,
            assessments_payload,
        )

        write_atomic_fresh(
            summary_path,
            summary_payload,
        )

        write_atomic_fresh(
            record_path,
            record_payload,
        )

        assessment_readback = (
            assessments_path.read_bytes()
        )

        summary_readback = (
            summary_path.read_bytes()
        )

        record_readback = (
            record_path.read_bytes()
        )

        audited_assessments = (
            audit_metadata_assessments(
                assessment_readback
            )
        )

        audit_metadata_summary(
            summary_readback,
            assessments_payload=(
                assessment_readback
            ),
        )

        audited_record = (
            audit_metadata_eligibility_record(
                record_readback,
                source_snapshot_id=(
                    upstream.source_snapshot_id
                ),
                source_snapshot_record_sha256=(
                    upstream.snapshot_sha256
                ),
                raw_response=(
                    upstream.raw_response
                ),
                assessments_payload=(
                    assessment_readback
                ),
                summary_payload=(
                    summary_readback
                ),
                source_eligibility_sha256=(
                    EXPECTED_SOURCE_ELIGIBILITY_SHA256
                ),
            )
        )

        expected_inventory = {
            ASSESSMENTS_NAME,
            SUMMARY_NAME,
            RECORD_NAME,
        }

        observed_inventory = {
            path.name
            for path in partial.iterdir()
            if path.is_file()
        }

        if observed_inventory != expected_inventory:
            raise MonthlyMetadataEligibilityExecutionError(
                "metadata stage artifact inventory changed"
            )

        if any(
            path.is_dir()
            for path in partial.iterdir()
        ):
            raise MonthlyMetadataEligibilityExecutionError(
                "metadata stage contains unexpected directory"
            )

        if stat.S_IMODE(
            partial.stat().st_mode
        ) != 0o755:
            raise MonthlyMetadataEligibilityExecutionError(
                "metadata partial stage mode changed"
            )

        fsync_directory(
            partial
        )

        os.replace(
            partial,
            final,
        )

        fsync_directory(
            upstream.stage1_root
        )

    except Exception:
        # A failed stage is intentionally retained only as the
        # ".partial" directory.  It is never promoted to the canonical
        # completed stage name.
        raise

    final_assessments = (
        final
        / ASSESSMENTS_NAME
    ).read_bytes()

    final_summary = (
        final
        / SUMMARY_NAME
    ).read_bytes()

    final_record = (
        final
        / RECORD_NAME
    ).read_bytes()

    if (
        final_assessments
        != assessments_payload
        or final_summary
        != summary_payload
        or final_record
        != record_payload
    ):
        raise MonthlyMetadataEligibilityExecutionError(
            "completed metadata stage readback changed"
        )

    if {
        path.name
        for path in final.iterdir()
        if path.is_file()
    } != {
        ASSESSMENTS_NAME,
        SUMMARY_NAME,
        RECORD_NAME,
    }:
        raise MonthlyMetadataEligibilityExecutionError(
            "completed metadata stage inventory changed"
        )

    if stat.S_IMODE(
        final.stat().st_mode
    ) != 0o755:
        raise MonthlyMetadataEligibilityExecutionError(
            "completed metadata stage mode changed"
        )

    for path in final.iterdir():
        if (
            path.is_file()
            and stat.S_IMODE(
                path.stat().st_mode
            )
            != 0o644
        ):
            raise MonthlyMetadataEligibilityExecutionError(
                f"completed artifact mode changed: {path.name}"
            )

    audit_metadata_assessments(
        final_assessments
    )

    audit_metadata_summary(
        final_summary,
        assessments_payload=(
            final_assessments
        ),
    )

    audit_metadata_eligibility_record(
        final_record,
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            upstream.snapshot_sha256
        ),
        raw_response=(
            upstream.raw_response
        ),
        assessments_payload=(
            final_assessments
        ),
        summary_payload=(
            final_summary
        ),
        source_eligibility_sha256=(
            EXPECTED_SOURCE_ELIGIBILITY_SHA256
        ),
    )

    final_assessments_sha = (
        hashlib.sha256(
            final_assessments
        ).hexdigest()
    )

    final_summary_sha = (
        hashlib.sha256(
            final_summary
        ).hexdigest()
    )

    final_record_sha = (
        hashlib.sha256(
            final_record
        ).hexdigest()
    )

    completion_payload = (
        build_completion_receipt(
            release_id=(
                upstream.release_id
            ),
            source_snapshot_id=(
                upstream.source_snapshot_id
            ),
            source_snapshot_record_sha256=(
                upstream.snapshot_sha256
            ),
            execution_commit=(
                execution_commit
            ),
            assessments_sha256=(
                final_assessments_sha
            ),
            summary_sha256=(
                final_summary_sha
            ),
            record_sha256=(
                final_record_sha
            ),
        )
    )

    completion_path = (
        upstream.stage1_root
        / COMPLETION_NAME
    )

    write_atomic_fresh(
        completion_path,
        completion_payload,
    )

    completion_readback = (
        completion_path.read_bytes()
    )

    audit_completion_receipt(
        completion_readback,
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            upstream.snapshot_sha256
        ),
        execution_commit=(
            execution_commit
        ),
        assessments_sha256=(
            final_assessments_sha
        ),
        summary_sha256=(
            final_summary_sha
        ),
        record_sha256=(
            final_record_sha
        ),
    )

    return MonthlyMetadataEligibilityResult(
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        stage_root=final,
        assessment_count=len(
            audited_assessments
        ),
        retained_count=int(
            audited_record[
                "retained_count"
            ]
        ),
        excluded_count=int(
            audited_record[
                "excluded_count"
            ]
        ),
        withheld_count=int(
            audited_record[
                "withheld_count"
            ]
        ),
        assessments_sha256=(
            final_assessments_sha
        ),
        summary_sha256=(
            final_summary_sha
        ),
        record_sha256=(
            final_record_sha
        ),
        completion_sha256=(
            hashlib.sha256(
                completion_readback
            ).hexdigest()
        ),
    )


def main(
    argv: Sequence[
        str
    ] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute BacSelect monthly metadata eligibility "
            "from an already-audited Stage 1 source snapshot."
        )
    )

    parser.add_argument(
        "--expected-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-wrapper-test-sha256",
        required=True,
    )

    parser.add_argument(
        "--production-root",
        required=True,
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlyMetadataEligibilityExecutionError(
            "production metadata execution requires explicit authorization"
        )

    script_path = Path(
        __file__
    ).resolve()

    repo = script_path.parents[
        2
    ]

    repository_preflight(
        repo,
        expected_commit=(
            args.expected_commit
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    result = (
        execute_monthly_metadata_eligibility(
            repo=repo,
            production_root=Path(
                args.production_root
            ),
            stage1_root=Path(
                args.stage1_root
            ),
            execution_commit=(
                args.expected_commit
            ),
        )
    )

    print(
        "PASS | BacSelect monthly metadata eligibility complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )

    print(
        f"stage_root={result.stage_root}"
    )

    print(
        f"assessment_count={result.assessment_count}"
    )

    print(
        f"retained_count={result.retained_count}"
    )

    print(
        f"excluded_count={result.excluded_count}"
    )

    print(
        f"withheld_count={result.withheld_count}"
    )

    print(
        f"metadata_assessments_sha256={result.assessments_sha256}"
    )

    print(
        f"metadata_summary_sha256={result.summary_sha256}"
    )

    print(
        f"metadata_record_sha256={result.record_sha256}"
    )

    print(
        f"metadata_completion_sha256={result.completion_sha256}"
    )

    print(
        "cache_verification_complete=no"
    )

    print(
        "sequence_plan_complete=no"
    )

    print(
        "source_sequence_acquisition_complete=no"
    )

    print(
        "public_monthly_release_generated=no"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except (
        MonthlyMetadataEligibilityExecutionError,
        MonthlyMetadataEligibilityError,
        MonthlyReleaseStartError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )

        raise SystemExit(
            1
        )
