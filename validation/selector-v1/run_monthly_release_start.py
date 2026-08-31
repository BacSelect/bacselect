#!/usr/bin/env python3
"""Execute the BacSelect monthly release-start/source-snapshot boundary."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Any

from bacselect import source_eligibility
from bacselect.monthly_release_start import (
    MonthlyReleaseStartError,
    audit_release_start_checkpoint,
    audit_source_snapshot_record,
    canonical_json_bytes,
    derive_release_id,
    parse_utc_timestamp,
    serialize_release_start_checkpoint,
    serialize_source_snapshot_record,
    sha256_bytes,
    validate_git_commit,
    validate_plain_text_identity,
    validate_release_id,
)


EXPECTED_METHOD_SHA256 = (
    "663b1513ea75286d1ddace76baaacff4541361e25367d98b192b93b7fb2f0bb4"
)

EXPECTED_CORE_SHA256 = (
    "76cb24d9c70f1418e580408a04321fc7e5ae1e78709e60cb2f5d15b8a531588c"
)

EXPECTED_CORE_TEST_SHA256 = (
    "64c08d36387c4a875cfa82b06df72736079936f55ab7e7acd679f7e13a231a59"
)

EXPECTED_DATASETS_VERSION = "18.35.0"

EXPECTED_DATASETS_ENVIRONMENT_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-production-release-method.md"
)

CORE_RELATIVE = Path(
    "src/bacselect/monthly_release_start.py"
)

CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_release_start.py"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_release_start.py"
)

ENVIRONMENT_RELATIVE = Path(
    "environments/ncbi-datasets-linux-64.explicit.txt"
)

CHECKPOINT_NAME = "release-start-checkpoint.json"
RAW_RESPONSE_NAME = "assembly_data_report.raw.jsonl"
QUERY_STDERR_NAME = "source-query.stderr"
QUERY_EXECUTION_NAME = "source-query-execution.json"
SOURCE_SNAPSHOT_RECORD_NAME = "source-snapshot-record.json"

QUERY_EXECUTION_SCHEMA_VERSION = (
    "bacselect-monthly-source-query-execution-v1"
)

QUERY_STATUS_SUCCESS = "SOURCE_QUERY_SUCCEEDED"
QUERY_STATUS_FAILED = "SOURCE_QUERY_FAILED"
QUERY_STATUS_EMPTY = "SOURCE_QUERY_INVALID_EMPTY_STDOUT"

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)


class MonthlyReleaseExecutionError(RuntimeError):
    """Raised when monthly source-snapshot execution fails closed."""


@dataclass(frozen=True)
class QueryResult:
    """Exact result from one external command."""

    stdout: bytes
    stderr: bytes
    returncode: int


@dataclass(frozen=True)
class MonthlySourceSnapshotResult:
    """Identities from one successful monthly source snapshot."""

    release_id: str
    source_snapshot_id: str
    output_root: Path
    checkpoint_sha256: str
    raw_response_sha256: str
    raw_response_bytes: int
    stderr_sha256: str
    stderr_bytes: int
    query_execution_sha256: str
    source_snapshot_record_sha256: str


def sha256_file(
    path: Path,
) -> str:
    """Return SHA256 for one exact file."""
    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:
        while True:
            block = handle.read(
                1024 * 1024
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
    reader: Callable[[Path], str] = sha256_file,
) -> None:
    """Require one exact frozen file identity."""
    if (
        not isinstance(
            expected,
            str,
        )
        or _SHA256_RE.fullmatch(
            expected
        )
        is None
    ):
        raise MonthlyReleaseExecutionError(
            f"invalid expected SHA256 for {label}"
        )

    observed = reader(
        path
    )

    if observed != expected:
        raise MonthlyReleaseExecutionError(
            f"{label} SHA256 mismatch: {observed}"
        )


def git_output(
    repo: Path,
    *args: str,
) -> str:
    """Run one local Git read and return stripped stdout."""
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
        raise MonthlyReleaseExecutionError(
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
    git_reader: Callable[..., str] = git_output,
    file_sha256_reader: Callable[[Path], str] = sha256_file,
) -> None:
    """Require an exact pushed clean repository before real source acquisition."""
    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    if git_reader(
        repo,
        "rev-parse",
        "HEAD",
    ) != commit:
        raise MonthlyReleaseExecutionError(
            "repository HEAD mismatch"
        )

    if git_reader(
        repo,
        "rev-parse",
        "origin/main",
    ) != commit:
        raise MonthlyReleaseExecutionError(
            "local origin/main mismatch"
        )

    if git_reader(
        repo,
        "status",
        "--porcelain",
    ):
        raise MonthlyReleaseExecutionError(
            "repository working tree is not clean"
        )

    require_sha256(
        repo
        / METHOD_RELATIVE,
        EXPECTED_METHOD_SHA256,
        label="monthly production method",
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / CORE_RELATIVE,
        EXPECTED_CORE_SHA256,
        label="monthly release-start core",
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / CORE_TEST_RELATIVE,
        EXPECTED_CORE_TEST_SHA256,
        label="monthly release-start core test",
        reader=file_sha256_reader,
    )

    wrapper_path = Path(
        __file__
    ).resolve()

    require_sha256(
        wrapper_path,
        expected_wrapper_sha256,
        label="monthly release-start execution wrapper",
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label="monthly release-start execution wrapper test",
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / ENVIRONMENT_RELATIVE,
        EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        label="NCBI Datasets explicit environment",
        reader=file_sha256_reader,
    )

    if (
        source_eligibility.DATASETS_VERSION
        != EXPECTED_DATASETS_VERSION
    ):
        raise MonthlyReleaseExecutionError(
            "source-eligibility Datasets version binding changed"
        )

    try:
        source_eligibility.validate_discovery_args(
            source_eligibility.DISCOVERY_ARGS
        )
    except ValueError as exc:
        raise MonthlyReleaseExecutionError(
            "frozen source-discovery arguments failed validation"
        ) from exc


def utc_now() -> str:
    """Return canonical whole-second UTC timestamp."""
    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def scientific_query_command() -> tuple[str, ...]:
    """Return the exact frozen NCBI Datasets scientific command."""
    try:
        source_eligibility.validate_discovery_args(
            source_eligibility.DISCOVERY_ARGS
        )
    except ValueError as exc:
        raise MonthlyReleaseExecutionError(
            "frozen source-discovery arguments changed"
        ) from exc

    command = (
        "datasets",
        *source_eligibility.DISCOVERY_ARGS,
    )

    expected = (
        "datasets",
        "summary",
        "genome",
        "taxon",
        "2",
        "--assembly-source",
        "GenBank",
        "--assembly-level",
        "complete",
        "--assembly-version",
        "current",
        "--mag",
        "exclude",
        "--exclude-multi-isolate",
        "--limit",
        "all",
        "--as-json-lines",
    )

    if command != expected:
        raise MonthlyReleaseExecutionError(
            "scientific NCBI Datasets command changed"
        )

    return command


def validate_launcher_prefix(
    launcher_prefix: Sequence[str],
) -> tuple[str, ...]:
    """Validate one explicit environment launcher ending in datasets."""
    if isinstance(
        launcher_prefix,
        (
            str,
            bytes,
        ),
    ):
        raise TypeError(
            "launcher prefix must be an argument sequence"
        )

    values = tuple(
        launcher_prefix
    )

    if not values:
        raise MonthlyReleaseExecutionError(
            "launcher prefix must not be empty"
        )

    for value in values:
        validate_plain_text_identity(
            value,
            label="launcher argument",
        )

    if Path(
        values[
            -1
        ]
    ).name != "datasets":
        raise MonthlyReleaseExecutionError(
            "launcher prefix must end with datasets"
        )

    return values


def default_command_runner(
    command: Sequence[str],
    *,
    cwd: Path,
) -> QueryResult:
    """Execute one command while preserving stdout/stderr as bytes."""
    result = subprocess.run(
        tuple(
            command
        ),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    return QueryResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def environment_preflight(
    repo: Path,
    *,
    datasets_executable: str | Path,
    command_runner: Callable[..., QueryResult] = default_command_runner,
) -> tuple[str, ...]:
    """Verify the frozen Datasets environment through an explicit executable."""
    require_sha256(
        repo
        / ENVIRONMENT_RELATIVE,
        EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        label="NCBI Datasets explicit environment",
    )

    executable = Path(
        datasets_executable
    )

    if not executable.is_absolute():
        raise MonthlyReleaseExecutionError(
            "datasets executable path must be absolute"
        )

    if executable.name != "datasets":
        raise MonthlyReleaseExecutionError(
            "datasets executable path must end with datasets"
        )

    prefix = (
        str(
            executable
        ),
    )

    version_result = command_runner(
        (
            *prefix,
            "--version",
        ),
        cwd=repo,
    )

    if version_result.returncode != 0:
        raise MonthlyReleaseExecutionError(
            "unable to validate NCBI Datasets version"
        )

    try:
        version_text = (
            version_result.stdout
            + b"\n"
            + version_result.stderr
        ).decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise MonthlyReleaseExecutionError(
            "NCBI Datasets version output is not UTF-8"
        ) from None

    try:
        source_eligibility.validate_datasets_version_text(
            version_text,
            expected=EXPECTED_DATASETS_VERSION,
        )
    except ValueError as exc:
        raise MonthlyReleaseExecutionError(
            "NCBI Datasets version mismatch"
        ) from exc

    return validate_launcher_prefix(
        prefix
    )

def output_root_for_release(
    production_root: Path,
    release_id: str,
    execution_commit: str,
) -> Path:
    """Return a commit-scoped output root below an explicit production root."""
    root = Path(
        production_root
    )

    if not root.is_absolute():
        raise MonthlyReleaseExecutionError(
            "production root must be an absolute path"
        )

    release = validate_release_id(
        release_id
    )

    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    return (
        root
        / release
        / "production"
        / commit
    )

def fsync_directory(
    path: Path,
) -> None:
    """Fsync one directory after a metadata mutation."""
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


def create_fresh_output_root(
    output_root: Path,
) -> None:
    """Create one fresh commit-scoped output root."""
    if output_root.exists():
        raise MonthlyReleaseExecutionError(
            "monthly production output root already exists"
        )

    output_root.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_root.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    os.chmod(
        output_root,
        0o755,
    )

    fsync_directory(
        output_root.parent
    )


def write_atomic_fresh(
    path: Path,
    payload: bytes,
) -> None:
    """Atomically publish one fresh mode-0644 file."""
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "artifact payload must be bytes"
        )

    if path.exists():
        raise MonthlyReleaseExecutionError(
            f"refusing to overwrite artifact: {path.name}"
        )

    temporary = path.with_name(
        "."
        + path.name
        + ".tmp"
    )

    if temporary.exists():
        raise MonthlyReleaseExecutionError(
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
                raise MonthlyReleaseExecutionError(
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

    observed = path.read_bytes()

    if observed != payload:
        raise MonthlyReleaseExecutionError(
            f"artifact readback mismatch: {path.name}"
        )

    if stat.S_IMODE(
        path.stat().st_mode
    ) != 0o644:
        raise MonthlyReleaseExecutionError(
            f"artifact mode mismatch: {path.name}"
        )


def query_execution_payload(
    *,
    release_start_checkpoint: bytes,
    release_id: str,
    execution_commit: str,
    scientific_command: Sequence[str],
    launcher_command: Sequence[str],
    query_started_utc: str,
    query_completed_utc: str,
    result: QueryResult,
    status: str,
) -> dict[str, Any]:
    """Construct deterministic source-query execution evidence."""
    started = parse_utc_timestamp(
        query_started_utc,
        label="source query started UTC",
    )

    completed = parse_utc_timestamp(
        query_completed_utc,
        label="source query completed UTC",
    )

    if completed < started:
        raise MonthlyReleaseExecutionError(
            "source query completion precedes source query start"
        )

    if isinstance(
        result.returncode,
        bool,
    ) or not isinstance(
        result.returncode,
        int,
    ):
        raise MonthlyReleaseExecutionError(
            "source query return code must be an integer"
        )

    if not isinstance(
        result.stdout,
        bytes,
    ) or not isinstance(
        result.stderr,
        bytes,
    ):
        raise MonthlyReleaseExecutionError(
            "source query streams must be bytes"
        )

    allowed_status = {
        QUERY_STATUS_SUCCESS,
        QUERY_STATUS_FAILED,
        QUERY_STATUS_EMPTY,
    }

    if status not in allowed_status:
        raise MonthlyReleaseExecutionError(
            "invalid source query execution status"
        )

    return {
        "execution_commit":
            validate_git_commit(
                execution_commit,
                label="execution commit",
            ),
        "exit_status":
            result.returncode,
        "launcher_command":
            list(
                launcher_command
            ),
        "raw_stderr_bytes":
            len(
                result.stderr
            ),
        "raw_stderr_sha256":
            sha256_bytes(
                result.stderr
            ),
        "raw_stdout_bytes":
            len(
                result.stdout
            ),
        "raw_stdout_sha256":
            sha256_bytes(
                result.stdout
            ),
        "release_id":
            validate_release_id(
                release_id
            ),
        "release_start_checkpoint_sha256":
            sha256_bytes(
                release_start_checkpoint
            ),
        "schema_version":
            QUERY_EXECUTION_SCHEMA_VERSION,
        "scientific_command":
            list(
                scientific_command
            ),
        "source_query_completed_utc":
            query_completed_utc,
        "source_query_started_utc":
            query_started_utc,
        "status":
            status,
    }


def audit_query_execution_payload(
    payload: bytes,
    *,
    release_start_checkpoint: bytes,
    stdout: bytes,
    stderr: bytes,
) -> Mapping[str, Any]:
    """Audit exact query-execution evidence against preserved streams."""
    try:
        record = json.loads(
            payload.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise MonthlyReleaseExecutionError(
            "query execution record is invalid JSON"
        ) from None

    expected_keys = {
        "execution_commit",
        "exit_status",
        "launcher_command",
        "raw_stderr_bytes",
        "raw_stderr_sha256",
        "raw_stdout_bytes",
        "raw_stdout_sha256",
        "release_id",
        "release_start_checkpoint_sha256",
        "schema_version",
        "scientific_command",
        "source_query_completed_utc",
        "source_query_started_utc",
        "status",
    }

    if set(
        record
    ) != expected_keys:
        raise MonthlyReleaseExecutionError(
            "query execution record key set changed"
        )

    if canonical_json_bytes(
        record
    ) != payload:
        raise MonthlyReleaseExecutionError(
            "query execution record is not canonical JSON"
        )

    if record[
        "schema_version"
    ] != QUERY_EXECUTION_SCHEMA_VERSION:
        raise MonthlyReleaseExecutionError(
            "query execution schema changed"
        )

    if record[
        "scientific_command"
    ] != list(
        scientific_query_command()
    ):
        raise MonthlyReleaseExecutionError(
            "query execution scientific command changed"
        )

    if record[
        "release_start_checkpoint_sha256"
    ] != sha256_bytes(
        release_start_checkpoint
    ):
        raise MonthlyReleaseExecutionError(
            "query execution checkpoint binding changed"
        )

    if record[
        "raw_stdout_sha256"
    ] != sha256_bytes(
        stdout
    ):
        raise MonthlyReleaseExecutionError(
            "query execution stdout SHA256 mismatch"
        )

    if record[
        "raw_stdout_bytes"
    ] != len(
        stdout
    ):
        raise MonthlyReleaseExecutionError(
            "query execution stdout byte count mismatch"
        )

    if record[
        "raw_stderr_sha256"
    ] != sha256_bytes(
        stderr
    ):
        raise MonthlyReleaseExecutionError(
            "query execution stderr SHA256 mismatch"
        )

    if record[
        "raw_stderr_bytes"
    ] != len(
        stderr
    ):
        raise MonthlyReleaseExecutionError(
            "query execution stderr byte count mismatch"
        )

    parse_utc_timestamp(
        record[
            "source_query_started_utc"
        ],
        label="source query started UTC",
    )

    parse_utc_timestamp(
        record[
            "source_query_completed_utc"
        ],
        label="source query completed UTC",
    )

    return record


def execute_monthly_source_snapshot(
    *,
    repo: Path,
    output_root: Path,
    execution_commit: str,
    snapshot_start_utc: str,
    launcher_prefix: Sequence[str],
    query_runner: Callable[..., QueryResult] = default_command_runner,
    timestamp_provider: Callable[[], str] = utc_now,
) -> MonthlySourceSnapshotResult:
    """Execute one source query after durably publishing its release checkpoint."""
    release_id = derive_release_id(
        snapshot_start_utc
    )

    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    launcher = validate_launcher_prefix(
        launcher_prefix
    )

    scientific = scientific_query_command()

    full_command = (
        *launcher,
        *source_eligibility.DISCOVERY_ARGS,
    )

    create_fresh_output_root(
        output_root
    )

    checkpoint = serialize_release_start_checkpoint(
        snapshot_start_utc=snapshot_start_utc,
        expected_git_commit=commit,
        ncbi_datasets_version=EXPECTED_DATASETS_VERSION,
        ncbi_datasets_environment_sha256=(
            EXPECTED_DATASETS_ENVIRONMENT_SHA256
        ),
    )

    checkpoint_path = (
        output_root
        / CHECKPOINT_NAME
    )

    write_atomic_fresh(
        checkpoint_path,
        checkpoint,
    )

    checkpoint_readback = checkpoint_path.read_bytes()

    if checkpoint_readback != checkpoint:
        raise MonthlyReleaseExecutionError(
            "release-start checkpoint readback changed"
        )

    try:
        audit_release_start_checkpoint(
            checkpoint_readback,
            expected_git_commit=commit,
        )
    except MonthlyReleaseStartError as exc:
        raise MonthlyReleaseExecutionError(
            "release-start checkpoint audit failed"
        ) from exc

    # No query runner is called before the checkpoint above has been:
    # written, fsynced, renamed, directory-fsynced, read back and audited.
    query_started_utc = timestamp_provider()

    if (
        parse_utc_timestamp(
            query_started_utc,
            label="source query started UTC",
        )
        < parse_utc_timestamp(
            snapshot_start_utc,
            label="snapshot start UTC",
        )
    ):
        raise MonthlyReleaseExecutionError(
            "source query cannot begin before snapshot start"
        )

    result = query_runner(
        full_command,
        cwd=repo,
    )

    query_completed_utc = timestamp_provider()

    if (
        parse_utc_timestamp(
            query_completed_utc,
            label="source query completed UTC",
        )
        < parse_utc_timestamp(
            query_started_utc,
            label="source query started UTC",
        )
    ):
        raise MonthlyReleaseExecutionError(
            "source query completion precedes source query start"
        )

    if not isinstance(
        result,
        QueryResult,
    ):
        raise MonthlyReleaseExecutionError(
            "query runner returned unexpected result type"
        )

    raw_path = (
        output_root
        / RAW_RESPONSE_NAME
    )

    stderr_path = (
        output_root
        / QUERY_STDERR_NAME
    )

    write_atomic_fresh(
        raw_path,
        result.stdout,
    )

    write_atomic_fresh(
        stderr_path,
        result.stderr,
    )

    if result.returncode != 0:
        query_status = QUERY_STATUS_FAILED
    elif not result.stdout:
        query_status = QUERY_STATUS_EMPTY
    else:
        query_status = QUERY_STATUS_SUCCESS

    execution_payload = canonical_json_bytes(
        query_execution_payload(
            release_start_checkpoint=checkpoint_readback,
            release_id=release_id,
            execution_commit=commit,
            scientific_command=scientific,
            launcher_command=full_command,
            query_started_utc=query_started_utc,
            query_completed_utc=query_completed_utc,
            result=result,
            status=query_status,
        )
    )

    execution_path = (
        output_root
        / QUERY_EXECUTION_NAME
    )

    write_atomic_fresh(
        execution_path,
        execution_payload,
    )

    audit_query_execution_payload(
        execution_path.read_bytes(),
        release_start_checkpoint=checkpoint_readback,
        stdout=raw_path.read_bytes(),
        stderr=stderr_path.read_bytes(),
    )

    if result.returncode != 0:
        raise MonthlyReleaseExecutionError(
            "NCBI Datasets source query failed; "
            "checkpoint and query evidence retained"
        )

    if not result.stdout:
        raise MonthlyReleaseExecutionError(
            "NCBI Datasets source query returned empty stdout; "
            "checkpoint and query evidence retained"
        )

    try:
        snapshot_record = serialize_source_snapshot_record(
            release_start_checkpoint=checkpoint_readback,
            source_query_started_utc=query_started_utc,
            source_query_completed_utc=query_completed_utc,
            source_query_command=scientific,
            raw_response=result.stdout,
        )

        audited_snapshot = audit_source_snapshot_record(
            snapshot_record,
            release_start_checkpoint=checkpoint_readback,
            raw_response=result.stdout,
        )
    except MonthlyReleaseStartError as exc:
        raise MonthlyReleaseExecutionError(
            "source-snapshot provenance construction failed"
        ) from exc

    snapshot_record_path = (
        output_root
        / SOURCE_SNAPSHOT_RECORD_NAME
    )

    write_atomic_fresh(
        snapshot_record_path,
        snapshot_record,
    )

    readback_snapshot = snapshot_record_path.read_bytes()

    if readback_snapshot != snapshot_record:
        raise MonthlyReleaseExecutionError(
            "source-snapshot record readback changed"
        )

    audit_source_snapshot_record(
        readback_snapshot,
        release_start_checkpoint=checkpoint_readback,
        raw_response=raw_path.read_bytes(),
    )

    return MonthlySourceSnapshotResult(
        release_id=release_id,
        source_snapshot_id=audited_snapshot[
            "source_snapshot_id"
        ],
        output_root=output_root,
        checkpoint_sha256=sha256_bytes(
            checkpoint_readback
        ),
        raw_response_sha256=sha256_bytes(
            raw_path.read_bytes()
        ),
        raw_response_bytes=raw_path.stat().st_size,
        stderr_sha256=sha256_bytes(
            stderr_path.read_bytes()
        ),
        stderr_bytes=stderr_path.stat().st_size,
        query_execution_sha256=sha256_bytes(
            execution_path.read_bytes()
        ),
        source_snapshot_record_sha256=sha256_bytes(
            readback_snapshot
        ),
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """CLI entry point for the real monthly source-snapshot boundary."""
    parser = argparse.ArgumentParser(
        description=(
            "Initiate one BacSelect monthly source snapshot. "
            "The release identifier is derived from current UTC."
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
        help=(
            "Absolute scratch root for this portable "
            "monthly production execution."
        ),
    )

    parser.add_argument(
        "--datasets-executable",
        required=True,
        help=(
            "Absolute path to datasets from the frozen "
            "NCBI Datasets environment."
        ),
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlyReleaseExecutionError(
            "real monthly source execution requires explicit authorization"
        )

    script_path = Path(
        __file__
    ).resolve()

    repo = script_path.parents[
        2
    ]

    repository_preflight(
        repo,
        expected_commit=args.expected_commit,
        expected_wrapper_sha256=args.expected_wrapper_sha256,
        expected_wrapper_test_sha256=args.expected_wrapper_test_sha256,
    )

    launcher = environment_preflight(
        repo,
        datasets_executable=args.datasets_executable,
    )

    # The CLI never accepts a caller-supplied release ID or source-snapshot
    # timestamp. The canonical start timestamp is captured here at execution.
    snapshot_start_utc = utc_now()

    release_id = derive_release_id(
        snapshot_start_utc
    )

    output_root = output_root_for_release(
        Path(
            args.production_root
        ),
        release_id,
        args.expected_commit,
    )

    result = execute_monthly_source_snapshot(
        repo=repo,
        output_root=output_root,
        execution_commit=args.expected_commit,
        snapshot_start_utc=snapshot_start_utc,
        launcher_prefix=launcher,
    )

    print(
        "PASS | BacSelect monthly source snapshot acquired"
    )
    print(
        f"release_id={result.release_id}"
    )
    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )
    print(
        f"output_root={result.output_root}"
    )
    print(
        f"release_start_checkpoint_sha256="
        f"{result.checkpoint_sha256}"
    )
    print(
        f"raw_response_sha256="
        f"{result.raw_response_sha256}"
    )
    print(
        f"raw_response_bytes="
        f"{result.raw_response_bytes}"
    )
    print(
        f"raw_stderr_sha256="
        f"{result.stderr_sha256}"
    )
    print(
        f"raw_stderr_bytes="
        f"{result.stderr_bytes}"
    )
    print(
        f"query_execution_sha256="
        f"{result.query_execution_sha256}"
    )
    print(
        f"source_snapshot_record_sha256="
        f"{result.source_snapshot_record_sha256}"
    )
    print(
        "monthly_release_assigned=yes"
    )
    print(
        "downstream_monthly_production_complete=no"
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
        MonthlyReleaseExecutionError,
        MonthlyReleaseStartError,
    ) as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )
        raise SystemExit(
            1
        )
