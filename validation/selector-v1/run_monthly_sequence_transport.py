#!/usr/bin/env python3
"""Execute one BacSelect monthly Stage 3B sequence-transport batch."""

from __future__ import annotations

import argparse
from collections.abc import (
    Callable,
    Mapping,
    Sequence,
)
import csv
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

from bacselect import source_eligibility
from bacselect.monthly_release_start import (
    MonthlyReleaseStartError,
    audit_source_snapshot_record,
    validate_git_commit,
)
from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
    FRESH_TARGET_FIELDS,
    MonthlyFreshAcquisitionTarget,
    audit_monthly_sequence_plan_record,
)
from bacselect.monthly_sequence_transport import (
    TARGETED_RETRY_ROUNDS,
    MonthlySequenceTransportError,
    MonthlyTransportBatch,
    batch_accession_bytes,
    batch_target_manifest_bytes,
    build_download_command,
    build_pre_network_attempt_record,
    build_rehydrate_command,
    build_targeted_rehydrate_command,
    parse_fetch_txt,
    remove_fetch_destinations,
    safe_extract,
    unresolved_fetches,
    validate_batch_contract,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
    MonthlyValidatedPackage,
    sha256_file,
    validate_hydrated_package,
    validate_metadata,
)


EXPECTED_DATASETS_VERSION = "18.35.0"

EXPECTED_DATASETS_ENVIRONMENT_SHA256 = (
    "6d965c7c4f7db0464e4fba2434f85f1b7da3f7136790babca444888b6e6096cd"
)

ENVIRONMENT_RELATIVE = Path(
    "environments/ncbi-datasets-linux-64.explicit.txt"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_transport.py"
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

BATCH_TARGETS_NAME = (
    "batch-targets.tsv"
)

ACCESSIONS_NAME = (
    "accessions.txt"
)

ATTEMPT_ORIGIN_NAME = (
    "attempt-origin.json"
)

DEHYDRATED_ZIP_NAME = (
    "dehydrated.zip"
)

DEHYDRATED_ZIP_PARTIAL_NAME = (
    "dehydrated.zip.partial"
)

PACKAGE_NAME = "package"

HYDRATION_ORIGIN_NAME = (
    "hydration-origin.json"
)

TARGETED_EVENTS_NAME = (
    "targeted-retry-events.json"
)

CANDIDATE_AUDIT_NAME = (
    "candidate-sequence-audit.tsv"
)

COMPONENT_AUDIT_NAME = (
    "component-sequence-audit.tsv"
)

PACKAGE_FILES_NAME = (
    "package-files.tsv"
)

SUMMARY_NAME = (
    "batch-summary.json"
)

SUMMARY_SCHEMA = (
    "bacselect-monthly-sequence-transport-summary-v1"
)


class MonthlySequenceTransportExecutionError(
    RuntimeError
):
    """Raised when Stage 3B execution fails closed."""


def transport_json_bytes(
    payload: Any,
) -> bytes:
    """Serialize any JSON value using the frozen evidence representation."""

    try:
        value = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceTransportExecutionError(
            "transport evidence is not JSON serializable"
        ) from exc

    return (
        value
        + "\n"
    ).encode(
        "utf-8"
    )


def json_normalized(
    payload: Any,
) -> Any:
    """Return the exact value represented after canonical JSON round-trip."""

    return json.loads(
        transport_json_bytes(
            payload
        ).decode(
            "utf-8"
        )
    )


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class UpstreamContract:
    release_id: str
    source_snapshot_id: str
    source_snapshot_record_sha256: str
    sequence_plan_record_sha256: str
    fresh_target_manifest_sha256: str
    fresh_target_count: int
    fresh_batch_count: int
    targets: tuple[
        MonthlyFreshAcquisitionTarget,
        ...,
    ]


@dataclass(frozen=True)
class TransportBatchResult:
    batch_index: int
    batch_id: str
    output_dir: Path
    summary_sha256: str
    candidate_audit_sha256: str
    component_audit_sha256: str
    package_files_sha256: str


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def default_command_runner(
    command: Sequence[str],
    *,
    cwd: Path,
) -> CommandResult:
    result = subprocess.run(
        tuple(
            command
        ),
        cwd=cwd,
        capture_output=True,
        check=False,
    )

    return CommandResult(
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def git_output(
    repo: Path,
    *arguments: str,
) -> str:
    result = subprocess.run(
        (
            "git",
            *arguments,
        ),
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise MonthlySequenceTransportExecutionError(
            "git preflight command failed: "
            f"{arguments!r}"
        )

    return result.stdout.strip()


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
    if reader(
        path
    ) != expected:
        raise MonthlySequenceTransportExecutionError(
            f"{label} SHA256 mismatch"
        )


def repository_preflight(
    repo: Path,
    *,
    expected_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    git_reader: Callable[..., str] = git_output,
    file_sha256_reader: Callable[
        [Path],
        str,
    ] = sha256_file,
) -> None:
    """Require an exact pushed clean repository without remote network."""

    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    if git_reader(
        repo,
        "rev-parse",
        "HEAD",
    ) != commit:
        raise MonthlySequenceTransportExecutionError(
            "repository HEAD mismatch"
        )

    if git_reader(
        repo,
        "rev-parse",
        "origin/main",
    ) != commit:
        raise MonthlySequenceTransportExecutionError(
            "local origin/main mismatch"
        )

    if git_reader(
        repo,
        "status",
        "--porcelain",
    ):
        raise MonthlySequenceTransportExecutionError(
            "repository working tree is not clean"
        )

    wrapper_path = Path(
        __file__
    ).resolve()

    require_sha256(
        wrapper_path,
        expected_wrapper_sha256,
        label="monthly sequence-transport execution wrapper",
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label="monthly sequence-transport wrapper test",
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
        raise MonthlySequenceTransportExecutionError(
            "source-eligibility Datasets version binding changed"
        )


def environment_preflight(
    repo: Path,
    *,
    datasets_executable: str | Path,
    command_runner: Callable[
        ...,
        CommandResult,
    ] = default_command_runner,
    file_sha256_reader: Callable[
        [Path],
        str,
    ] = sha256_file,
) -> Path:
    """Validate the frozen Datasets executable without network retrieval."""

    require_sha256(
        repo
        / ENVIRONMENT_RELATIVE,
        EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        label="NCBI Datasets explicit environment",
        reader=file_sha256_reader,
    )

    executable = Path(
        datasets_executable
    )

    if not executable.is_absolute():
        raise MonthlySequenceTransportExecutionError(
            "datasets executable path must be absolute"
        )

    resolved = executable.resolve()

    if resolved.name != "datasets":
        raise MonthlySequenceTransportExecutionError(
            "datasets executable path must end with datasets"
        )

    result = command_runner(
        (
            str(
                resolved
            ),
            "--version",
        ),
        cwd=repo,
    )

    if result.returncode != 0:
        raise MonthlySequenceTransportExecutionError(
            "unable to validate NCBI Datasets version"
        )

    try:
        version_text = (
            result.stdout
            + b"\n"
            + result.stderr
        ).decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise MonthlySequenceTransportExecutionError(
            "NCBI Datasets version output is not UTF-8"
        ) from None

    try:
        source_eligibility.validate_datasets_version_text(
            version_text,
            expected=EXPECTED_DATASETS_VERSION,
        )
    except ValueError as exc:
        raise MonthlySequenceTransportExecutionError(
            "NCBI Datasets version mismatch"
        ) from exc

    return resolved


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


def _write_bytes(
    path: Path,
    payload: bytes,
) -> None:
    with path.open(
        "xb"
    ) as handle:
        handle.write(
            payload
        )
        handle.flush()
        os.fsync(
            handle.fileno()
        )


def write_atomic_fresh(
    path: Path,
    payload: bytes,
) -> None:
    if path.exists():
        raise MonthlySequenceTransportExecutionError(
            f"artifact already exists: {path.name}"
        )

    temporary = path.with_name(
        path.name
        + ".tmp"
    )

    if temporary.exists():
        raise MonthlySequenceTransportExecutionError(
            f"temporary artifact already exists: {temporary.name}"
        )

    _write_bytes(
        temporary,
        payload,
    )

    os.replace(
        temporary,
        path,
    )

    fsync_directory(
        path.parent
    )


def write_atomic_replace(
    path: Path,
    payload: bytes,
) -> None:
    temporary = path.with_name(
        path.name
        + ".tmp"
    )

    if temporary.exists():
        raise MonthlySequenceTransportExecutionError(
            f"temporary artifact already exists: {temporary.name}"
        )

    _write_bytes(
        temporary,
        payload,
    )

    os.replace(
        temporary,
        path,
    )

    fsync_directory(
        path.parent
    )


def write_or_verify(
    path: Path,
    payload: bytes,
) -> None:
    """Allow deterministic resume only when an existing artifact is identical."""

    if path.exists():
        if path.read_bytes() != payload:
            raise MonthlySequenceTransportExecutionError(
                f"existing artifact changed during resume: {path.name}"
            )
        return

    write_atomic_fresh(
        path,
        payload,
    )


def _canonical_json_read(
    path: Path,
    *,
    label: str,
) -> Any:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise MonthlySequenceTransportExecutionError(
            f"unable to read {label}: {path}"
        ) from exc

    try:
        value = json.loads(
            payload.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlySequenceTransportExecutionError(
            f"invalid {label}"
        ) from exc

    if transport_json_bytes(
        value
    ) != payload:
        raise MonthlySequenceTransportExecutionError(
            f"{label} is not canonical JSON"
        )

    return value


def _require_absolute_file(
    path: Path,
    *,
    label: str,
) -> Path:
    if not path.is_absolute():
        raise MonthlySequenceTransportExecutionError(
            f"{label} path must be absolute"
        )

    resolved = path.resolve()

    if not resolved.is_file():
        raise MonthlySequenceTransportExecutionError(
            f"{label} does not exist: {resolved}"
        )

    return resolved


def _require_under(
    path: Path,
    root: Path,
    *,
    label: str,
) -> None:
    resolved = path.resolve()
    root_resolved = root.resolve()

    if (
        resolved != root_resolved
        and root_resolved
        not in resolved.parents
    ):
        raise MonthlySequenceTransportExecutionError(
            f"{label} must be below audited Stage 1 production root"
        )


def parse_fresh_targets(
    payload: bytes,
) -> tuple[
    MonthlyFreshAcquisitionTarget,
    ...,
]:
    """Reconstruct exact Stage 2 targets after Stage 2 audit succeeds."""

    try:
        text = payload.decode(
            "ascii"
        )
    except UnicodeDecodeError as exc:
        raise MonthlySequenceTransportExecutionError(
            "fresh-target manifest is not ASCII"
        ) from exc

    lines = text.splitlines()

    expected_header = "\t".join(
        FRESH_TARGET_FIELDS
    )

    if (
        not lines
        or lines[0] != expected_header
    ):
        raise MonthlySequenceTransportExecutionError(
            "fresh-target manifest schema changed"
        )

    values = []

    for line in lines[
        1:
    ]:
        fields = line.split(
            "\t"
        )

        if len(
            fields
        ) != 3:
            raise MonthlySequenceTransportExecutionError(
                "fresh-target manifest row shape changed"
            )

        values.append(
            MonthlyFreshAcquisitionTarget(
                canonical_genbank_assembly_accession=fields[0],
                source_biosample=fields[1],
                acquisition_reason=fields[2],
            )
        )

    return tuple(
        values
    )


def load_upstream_contract(
    *,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    expected_commit: str,
) -> UpstreamContract:
    """Audit Stage 1 + Stage 2 before deriving any Stage 3B batch."""

    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    if not production_root.is_absolute():
        raise MonthlySequenceTransportExecutionError(
            "production root must be absolute"
        )

    if not stage1_root.is_absolute():
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 production root must be absolute"
        )

    stage1 = stage1_root.resolve()

    checkpoint_path = (
        stage1
        / CHECKPOINT_NAME
    )

    raw_response_path = (
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
            raw_response_path,
            "raw source response",
        ),
        (
            snapshot_path,
            "source-snapshot record",
        ),
    ):
        if not path.is_file():
            raise MonthlySequenceTransportExecutionError(
                f"missing Stage 1 {label}: {path}"
            )

    checkpoint = (
        checkpoint_path.read_bytes()
    )

    raw_response = (
        raw_response_path.read_bytes()
    )

    snapshot_payload = (
        snapshot_path.read_bytes()
    )

    try:
        snapshot = (
            audit_source_snapshot_record(
                snapshot_payload,
                release_start_checkpoint=checkpoint,
                raw_response=raw_response,
            )
        )
    except MonthlyReleaseStartError as exc:
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 source-snapshot audit failed"
        ) from exc

    if snapshot[
        "expected_git_commit"
    ] != commit:
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 source snapshot was produced by a different commit"
        )

    if snapshot[
        "ncbi_datasets_environment_sha256"
    ] != EXPECTED_DATASETS_ENVIRONMENT_SHA256:
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 NCBI environment identity changed"
        )

    if snapshot[
        "ncbi_datasets_version"
    ] != EXPECTED_DATASETS_VERSION:
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 NCBI Datasets version changed"
        )

    release_id = str(
        snapshot[
            "release_id"
        ]
    )

    expected_stage1 = (
        production_root.resolve()
        / release_id
        / "production"
        / commit
    )

    if stage1 != expected_stage1:
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 production root does not match "
            "release/commit production identity"
        )

    plan_path = _require_absolute_file(
        sequence_plan_record,
        label="Stage 2 sequence-plan record",
    )

    manifest_path = _require_absolute_file(
        fresh_target_manifest,
        label="Stage 2 fresh-target manifest",
    )

    _require_under(
        plan_path,
        stage1,
        label="Stage 2 sequence-plan record",
    )

    _require_under(
        manifest_path,
        stage1,
        label="Stage 2 fresh-target manifest",
    )

    plan_payload = (
        plan_path.read_bytes()
    )

    manifest_payload = (
        manifest_path.read_bytes()
    )

    snapshot_sha = hashlib.sha256(
        snapshot_payload
    ).hexdigest()

    try:
        plan = (
            audit_monthly_sequence_plan_record(
                plan_payload,
                source_snapshot_id=str(
                    snapshot[
                        "source_snapshot_id"
                    ]
                ),
                source_snapshot_record_sha256=(
                    snapshot_sha
                ),
                fresh_target_manifest=(
                    manifest_payload
                ),
            )
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceTransportExecutionError(
            "Stage 2 sequence-plan provenance audit failed"
        ) from exc

    targets = parse_fresh_targets(
        manifest_payload
    )

    fresh_count = plan[
        "fresh_acquisition_count"
    ]

    if len(
        targets
    ) != fresh_count:
        raise MonthlySequenceTransportExecutionError(
            "Stage 2 fresh-target count changed after audit"
        )

    if fresh_count <= 0:
        raise MonthlySequenceTransportExecutionError(
            "Stage 2 contains no fresh sequence-acquisition targets"
        )

    return UpstreamContract(
        release_id=release_id,
        source_snapshot_id=str(
            snapshot[
                "source_snapshot_id"
            ]
        ),
        source_snapshot_record_sha256=(
            snapshot_sha
        ),
        sequence_plan_record_sha256=(
            hashlib.sha256(
                plan_payload
            ).hexdigest()
        ),
        fresh_target_manifest_sha256=(
            hashlib.sha256(
                manifest_payload
            ).hexdigest()
        ),
        fresh_target_count=fresh_count,
        fresh_batch_count=plan[
            "fresh_batch_count"
        ],
        targets=targets,
    )


def derive_transport_batch(
    upstream: UpstreamContract,
    *,
    batch_index: int,
) -> MonthlyTransportBatch:
    """Derive one batch internally from the audited full Stage 2 target set."""

    if (
        isinstance(
            batch_index,
            bool,
        )
        or not isinstance(
            batch_index,
            int,
        )
    ):
        raise MonthlySequenceTransportExecutionError(
            "batch index must be an integer"
        )

    if not (
        1
        <= batch_index
        <= upstream.fresh_batch_count
    ):
        raise MonthlySequenceTransportExecutionError(
            "batch index is outside audited Stage 2 batch range"
        )

    start = (
        batch_index
        - 1
    ) * FRESH_BATCH_SIZE

    stop = min(
        start
        + FRESH_BATCH_SIZE,
        upstream.fresh_target_count,
    )

    batch = MonthlyTransportBatch(
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        source_snapshot_record_sha256=(
            upstream.source_snapshot_record_sha256
        ),
        stage2_sequence_plan_record_sha256=(
            upstream.sequence_plan_record_sha256
        ),
        stage2_fresh_target_manifest_sha256=(
            upstream.fresh_target_manifest_sha256
        ),
        batch_index=batch_index,
        batch_count=(
            upstream.fresh_batch_count
        ),
        batch_size=FRESH_BATCH_SIZE,
        full_target_count=(
            upstream.fresh_target_count
        ),
        targets=upstream.targets[
            start:
            stop
        ],
    )

    try:
        validate_batch_contract(
            batch
        )
    except MonthlySequenceTransportError as exc:
        raise MonthlySequenceTransportExecutionError(
            "derived Stage 3B batch failed frozen contract"
        ) from exc

    return batch


def _serialize_tsv(
    rows: Sequence[
        Mapping[str, object]
    ],
    fields: Sequence[str],
) -> bytes:
    buffer = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        buffer,
        fieldnames=tuple(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    expected = set(
        fields
    )

    for row in rows:
        if set(
            row
        ) != expected:
            raise MonthlySequenceTransportExecutionError(
                "audit row schema changed"
            )

        writer.writerow(
            {
                field:
                    row[
                        field
                    ]
                for field in fields
            }
        )

    return buffer.getvalue().encode(
        "utf-8"
    )


def _run_and_record(
    *,
    command: Sequence[str],
    prefix: str,
    evidence_dir: Path,
    repo: Path,
    command_runner: Callable[
        ...,
        CommandResult,
    ],
) -> CommandResult:
    command_path = (
        evidence_dir
        / f"{prefix}-command.json"
    )

    stdout_path = (
        evidence_dir
        / f"{prefix}.stdout.txt"
    )

    stderr_path = (
        evidence_dir
        / f"{prefix}.stderr.txt"
    )

    exit_path = (
        evidence_dir
        / f"{prefix}-exit-code.txt"
    )

    for path in (
        command_path,
        stdout_path,
        stderr_path,
        exit_path,
    ):
        if path.exists():
            raise MonthlySequenceTransportExecutionError(
                f"execution evidence already exists: {path.name}"
            )

    write_atomic_fresh(
        command_path,
        transport_json_bytes(
            list(
                command
            )
        ),
    )

    result = command_runner(
        tuple(
            command
        ),
        cwd=repo,
    )

    if not isinstance(
        result,
        CommandResult,
    ):
        raise MonthlySequenceTransportExecutionError(
            "command runner returned unexpected result type"
        )

    write_atomic_fresh(
        stdout_path,
        result.stdout,
    )

    write_atomic_fresh(
        stderr_path,
        result.stderr,
    )

    write_atomic_fresh(
        exit_path,
        (
            f"{result.returncode}\n"
        ).encode(
            "ascii"
        ),
    )

    return result


def _read_exit_code(
    path: Path,
) -> int:
    try:
        text = path.read_text(
            encoding="ascii"
        )
    except (
        OSError,
        UnicodeDecodeError,
    ) as exc:
        raise MonthlySequenceTransportExecutionError(
            f"invalid execution exit-code evidence: {path.name}"
        ) from exc

    try:
        return int(
            text.strip()
        )
    except ValueError:
        raise MonthlySequenceTransportExecutionError(
            f"invalid execution exit code: {path.name}"
        ) from None


def _load_retry_events(
    path: Path,
) -> list[
    dict[str, object]
]:
    if not path.exists():
        return []

    value = _canonical_json_read(
        path,
        label="targeted retry events",
    )

    if not isinstance(
        value,
        list,
    ):
        raise MonthlySequenceTransportExecutionError(
            "targeted retry events must be a JSON list"
        )

    events = []

    for event in value:
        if (
            not isinstance(
                event,
                dict,
            )
            or set(
                event
            )
            != {
                "assembly_accession",
                "attempt",
                "exit_code",
                "remaining",
            }
        ):
            raise MonthlySequenceTransportExecutionError(
                "targeted retry event schema changed"
            )

        events.append(
            event
        )

    return events


def _write_retry_events(
    path: Path,
    events: Sequence[
        Mapping[str, object]
    ],
) -> None:
    payload = transport_json_bytes(
        list(
            events
        )
    )

    if path.exists():
        write_atomic_replace(
            path,
            payload,
        )
    else:
        write_atomic_fresh(
            path,
            payload,
        )


def _validate_resume_attempt(
    *,
    attempt_path: Path,
    dehydrated_zip: Path,
    partial_zip: Path,
    package: Path,
    batch: MonthlyTransportBatch,
    origin_git_commit: str,
    environment_explicit_sha256: str,
    datasets_executable: Path,
    transport_implementation_sha256: str,
) -> Mapping[str, object]:
    if partial_zip.exists():
        raise MonthlySequenceTransportExecutionError(
            "cannot resume an interrupted dehydrated download; "
            "retain the partial for inspection and start a fresh batch"
        )

    if not dehydrated_zip.is_file():
        raise MonthlySequenceTransportExecutionError(
            "resume state lacks completed dehydrated ZIP"
        )

    if not package.is_dir():
        raise MonthlySequenceTransportExecutionError(
            "resume state lacks extracted package"
        )

    attempt = _canonical_json_read(
        attempt_path,
        label="attempt origin",
    )

    if not isinstance(
        attempt,
        dict,
    ):
        raise MonthlySequenceTransportExecutionError(
            "attempt origin must be a JSON object"
        )

    recorded_at = attempt.get(
        "recorded_at_utc"
    )

    if not isinstance(
        recorded_at,
        str,
    ):
        raise MonthlySequenceTransportExecutionError(
            "attempt origin lacks recorded-at UTC identity"
        )

    expected = json_normalized(
        dict(
            build_pre_network_attempt_record(
                batch,
                recorded_at_utc=recorded_at,
                origin_git_commit=origin_git_commit,
                environment_explicit_sha256=(
                    environment_explicit_sha256
                ),
                datasets_executable=(
                    datasets_executable
                ),
                transport_implementation_sha256=(
                    transport_implementation_sha256
                ),
            )
        )
    )

    for key, value in expected.items():
        if key == "dehydrated_zip_sha256":
            continue

        if attempt.get(
            key
        ) != value:
            raise MonthlySequenceTransportExecutionError(
                f"resume attempt-origin mismatch: {key}"
            )

    observed_zip_sha = attempt.get(
        "dehydrated_zip_sha256"
    )

    actual_zip_sha = sha256_file(
        dehydrated_zip
    )

    if observed_zip_sha != actual_zip_sha:
        raise MonthlySequenceTransportExecutionError(
            "resume dehydrated ZIP fingerprint changed"
        )

    return attempt


def _hydration_origin(
    *,
    path: Path,
    fetch_path: Path,
    fetch_entries: Sequence[object],
    unresolved_before: Mapping[
        str,
        object,
    ],
) -> Mapping[str, object]:
    fetch_sha = sha256_file(
        fetch_path
    )

    if path.exists():
        value = _canonical_json_read(
            path,
            label="hydration origin",
        )

        if (
            not isinstance(
                value,
                dict,
            )
            or set(
                value
            )
            != {
                "fetch_txt_sha256",
                "fetch_entries",
                "initial_unresolved_accessions",
            }
        ):
            raise MonthlySequenceTransportExecutionError(
                "hydration-origin schema changed"
            )

        if value[
            "fetch_txt_sha256"
        ] != fetch_sha:
            raise MonthlySequenceTransportExecutionError(
                "fetch.txt fingerprint changed during resume"
            )

        if value[
            "fetch_entries"
        ] != len(
            fetch_entries
        ):
            raise MonthlySequenceTransportExecutionError(
                "fetch.txt entry count changed during resume"
            )

        return value

    value = {
        "fetch_txt_sha256":
            fetch_sha,
        "fetch_entries":
            len(
                fetch_entries
            ),
        "initial_unresolved_accessions":
            len(
                unresolved_before
            ),
    }

    write_atomic_fresh(
        path,
        transport_json_bytes(
            value
        ),
    )

    return value


def execute_transport_batch(
    *,
    repo: Path,
    stage1_root: Path,
    batch: MonthlyTransportBatch,
    datasets_executable: Path,
    execution_commit: str,
    transport_implementation_sha256: str,
    resume: bool = False,
    command_runner: Callable[
        ...,
        CommandResult,
    ] = default_command_runner,
    metadata_validator: Callable[..., object] = validate_metadata,
    package_validator: Callable[
        ...,
        MonthlyValidatedPackage,
    ] = validate_hydrated_package,
) -> TransportBatchResult:
    """Execute one deterministic Stage 3B transport batch."""

    commit = validate_git_commit(
        execution_commit,
        label="execution commit",
    )

    try:
        validate_batch_contract(
            batch
        )
    except MonthlySequenceTransportError as exc:
        raise MonthlySequenceTransportExecutionError(
            "Stage 3B batch contract failed"
        ) from exc

    if not stage1_root.is_absolute():
        raise MonthlySequenceTransportExecutionError(
            "Stage 1 production root must be absolute"
        )

    sequence_root = (
        stage1_root
        / "sequence-acquisition"
    )

    sequence_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    fsync_directory(
        sequence_root.parent
    )

    batch_id = (
        f"batch-{batch.batch_index:05d}"
    )

    partial_dir = (
        sequence_root
        / f"{batch_id}.partial"
    )

    final_dir = (
        sequence_root
        / batch_id
    )

    if final_dir.exists():
        raise MonthlySequenceTransportExecutionError(
            f"completed batch already exists: {final_dir}"
        )

    targets_path = (
        partial_dir
        / BATCH_TARGETS_NAME
    )

    accessions_path = (
        partial_dir
        / ACCESSIONS_NAME
    )

    attempt_path = (
        partial_dir
        / ATTEMPT_ORIGIN_NAME
    )

    partial_zip = (
        partial_dir
        / DEHYDRATED_ZIP_PARTIAL_NAME
    )

    dehydrated_zip = (
        partial_dir
        / DEHYDRATED_ZIP_NAME
    )

    package = (
        partial_dir
        / PACKAGE_NAME
    )

    target_bytes = (
        batch_target_manifest_bytes(
            batch.targets
        )
    )

    accession_bytes = (
        batch_accession_bytes(
            batch.targets
        )
    )

    if resume:
        if not partial_dir.is_dir():
            raise MonthlySequenceTransportExecutionError(
                "cannot resume because partial batch does not exist"
            )

        write_or_verify(
            targets_path,
            target_bytes,
        )

        write_or_verify(
            accessions_path,
            accession_bytes,
        )

        if not attempt_path.is_file():
            raise MonthlySequenceTransportExecutionError(
                "resume state lacks attempt-origin record"
            )

        _validate_resume_attempt(
            attempt_path=attempt_path,
            dehydrated_zip=dehydrated_zip,
            partial_zip=partial_zip,
            package=package,
            batch=batch,
            origin_git_commit=commit,
            environment_explicit_sha256=(
                EXPECTED_DATASETS_ENVIRONMENT_SHA256
            ),
            datasets_executable=(
                datasets_executable
            ),
            transport_implementation_sha256=(
                transport_implementation_sha256
            ),
        )

    else:
        if partial_dir.exists():
            raise MonthlySequenceTransportExecutionError(
                "partial batch already exists; inspect it and use "
                "--resume only after a completed dehydrated download"
            )

        partial_dir.mkdir()

        fsync_directory(
            sequence_root
        )

        write_atomic_fresh(
            targets_path,
            target_bytes,
        )

        write_atomic_fresh(
            accessions_path,
            accession_bytes,
        )

        attempt = dict(
            build_pre_network_attempt_record(
                batch,
                recorded_at_utc=utc_now(),
                origin_git_commit=commit,
                environment_explicit_sha256=(
                    EXPECTED_DATASETS_ENVIRONMENT_SHA256
                ),
                datasets_executable=(
                    datasets_executable
                ),
                transport_implementation_sha256=(
                    transport_implementation_sha256
                ),
            )
        )

        attempt_payload = (
            transport_json_bytes(
                attempt
            )
        )

        write_atomic_fresh(
            attempt_path,
            attempt_payload,
        )

        if attempt_path.read_bytes() != attempt_payload:
            raise MonthlySequenceTransportExecutionError(
                "pre-network attempt-origin readback changed"
            )

        download_command = (
            build_download_command(
                datasets_executable=(
                    datasets_executable
                ),
                accessions_path=(
                    accessions_path
                ),
                partial_zip_path=(
                    partial_zip
                ),
            )
        )

        result = _run_and_record(
            command=download_command,
            prefix="download",
            evidence_dir=partial_dir,
            repo=repo,
            command_runner=command_runner,
        )

        if result.returncode != 0:
            raise MonthlySequenceTransportExecutionError(
                "NCBI Datasets dehydrated download failed; "
                "partial evidence retained"
            )

        if not partial_zip.is_file():
            raise MonthlySequenceTransportExecutionError(
                "Datasets reported success but dehydrated ZIP is absent"
            )

        package.mkdir()

        safe_extract(
            partial_zip,
            package,
        )

        os.replace(
            partial_zip,
            dehydrated_zip,
        )

        fsync_directory(
            partial_dir
        )

        attempt[
            "dehydrated_zip_sha256"
        ] = sha256_file(
            dehydrated_zip
        )

        write_atomic_replace(
            attempt_path,
            transport_json_bytes(
                attempt
            ),
        )

    try:
        metadata_validator(
            package,
            batch.targets,
        )
    except Exception as exc:
        raise MonthlySequenceTransportExecutionError(
            "hydrated-package metadata identity validation failed"
        ) from exc

    try:
        (
            fetch_path,
            fetch_entries,
            fetch_by_accession,
        ) = parse_fetch_txt(
            package,
            tuple(
                target.canonical_genbank_assembly_accession
                for target in batch.targets
            ),
        )
    except MonthlySequenceTransportError as exc:
        raise MonthlySequenceTransportExecutionError(
            "Datasets hydration manifest validation failed"
        ) from exc

    unresolved_before = (
        unresolved_fetches(
            package,
            fetch_by_accession,
        )
    )

    hydration_origin = (
        _hydration_origin(
            path=(
                partial_dir
                / HYDRATION_ORIGIN_NAME
            ),
            fetch_path=fetch_path,
            fetch_entries=fetch_entries,
            unresolved_before=(
                unresolved_before
            ),
        )
    )

    broad_exit_path = (
        partial_dir
        / "rehydrate-broad-exit-code.txt"
    )

    broad_exit_code = None

    if unresolved_before:
        if broad_exit_path.exists():
            broad_exit_code = (
                _read_exit_code(
                    broad_exit_path
                )
            )
        else:
            broad_command = (
                build_rehydrate_command(
                    datasets_executable=(
                        datasets_executable
                    ),
                    package=package,
                )
            )

            broad_result = (
                _run_and_record(
                    command=broad_command,
                    prefix="rehydrate-broad",
                    evidence_dir=partial_dir,
                    repo=repo,
                    command_runner=(
                        command_runner
                    ),
                )
            )

            broad_exit_code = (
                broad_result.returncode
            )

    unresolved_after_broad = (
        unresolved_fetches(
            package,
            fetch_by_accession,
        )
    )

    events_path = (
        partial_dir
        / TARGETED_EVENTS_NAME
    )

    retry_events = (
        _load_retry_events(
            events_path
        )
    )

    for accession in sorted(
        unresolved_after_broad
    ):
        previous_attempts = [
            event
            for event in retry_events
            if event[
                "assembly_accession"
            ] == accession
        ]

        used = max(
            (
                int(
                    event[
                        "attempt"
                    ]
                )
                for event in previous_attempts
            ),
            default=0,
        )

        problem = (
            unresolved_fetches(
                package,
                {
                    accession:
                        fetch_by_accession[
                            accession
                        ]
                },
            )
        )

        for attempt_number in range(
            used + 1,
            TARGETED_RETRY_ROUNDS + 1,
        ):
            if not problem:
                break

            remove_fetch_destinations(
                package,
                fetch_by_accession[
                    accession
                ],
            )

            target_command = (
                build_targeted_rehydrate_command(
                    datasets_executable=(
                        datasets_executable
                    ),
                    package=package,
                    accession=accession,
                )
            )

            prefix = (
                "targeted-rehydrate-"
                f"{accession}-"
                f"attempt-{attempt_number}"
            )

            target_result = (
                _run_and_record(
                    command=target_command,
                    prefix=prefix,
                    evidence_dir=partial_dir,
                    repo=repo,
                    command_runner=(
                        command_runner
                    ),
                )
            )

            problem = (
                unresolved_fetches(
                    package,
                    {
                        accession:
                            fetch_by_accession[
                                accession
                            ]
                    },
                )
            )

            remaining = []

            if problem:
                remaining = [
                    [
                        relative,
                        reason,
                    ]
                    for (
                        relative,
                        reason,
                    ) in problem[
                        accession
                    ]
                ]

            retry_events.append(
                {
                    "assembly_accession":
                        accession,
                    "attempt":
                        attempt_number,
                    "exit_code":
                        target_result.returncode,
                    "remaining":
                        remaining,
                }
            )

            _write_retry_events(
                events_path,
                retry_events,
            )

        if problem:
            raise MonthlySequenceTransportExecutionError(
                f"{accession}: hydrated payload remains incomplete "
                "after bounded targeted recovery"
            )

    unresolved_final = (
        unresolved_fetches(
            package,
            fetch_by_accession,
        )
    )

    if unresolved_final:
        raise MonthlySequenceTransportExecutionError(
            "hydrated package remains incomplete after transport recovery"
        )

    try:
        validated = package_validator(
            package,
            batch.targets,
        )
    except Exception as exc:
        raise MonthlySequenceTransportExecutionError(
            "Stage 3A scientific package validation failed; "
            "transport partial retained for deterministic resume"
        ) from exc

    if not isinstance(
        validated,
        MonthlyValidatedPackage,
    ):
        raise MonthlySequenceTransportExecutionError(
            "Stage 3A validator returned unexpected result type"
        )

    candidate_payload = (
        _serialize_tsv(
            validated.candidate_rows,
            CANDIDATE_AUDIT_FIELDS,
        )
    )

    component_payload = (
        _serialize_tsv(
            validated.component_rows,
            COMPONENT_AUDIT_FIELDS,
        )
    )

    package_files_payload = (
        _serialize_tsv(
            validated.package_file_rows,
            PACKAGE_FILE_FIELDS,
        )
    )

    candidate_path = (
        partial_dir
        / CANDIDATE_AUDIT_NAME
    )

    component_path = (
        partial_dir
        / COMPONENT_AUDIT_NAME
    )

    package_files_path = (
        partial_dir
        / PACKAGE_FILES_NAME
    )

    write_or_verify(
        candidate_path,
        candidate_payload,
    )

    write_or_verify(
        component_path,
        component_payload,
    )

    write_or_verify(
        package_files_path,
        package_files_payload,
    )

    summary_path = (
        partial_dir
        / SUMMARY_NAME
    )

    completed_at = None

    if summary_path.exists():
        existing_summary = (
            _canonical_json_read(
                summary_path,
                label="batch summary",
            )
        )

        if not isinstance(
            existing_summary,
            dict,
        ):
            raise MonthlySequenceTransportExecutionError(
                "batch summary must be a JSON object"
            )

        completed_at = (
            existing_summary.get(
                "execution_completed_at_utc"
            )
        )

        if not isinstance(
            completed_at,
            str,
        ):
            raise MonthlySequenceTransportExecutionError(
                "existing batch summary lacks completion timestamp"
            )

    if completed_at is None:
        completed_at = utc_now()

    attempt_sha = sha256_file(
        attempt_path
    )

    summary = {
        "schema":
            SUMMARY_SCHEMA,
        "result":
            "PASS",
        "source_snapshot_id":
            batch.source_snapshot_id,
        "source_snapshot_record_sha256":
            batch.source_snapshot_record_sha256,
        "stage2_sequence_plan_record_sha256":
            batch.stage2_sequence_plan_record_sha256,
        "stage2_fresh_target_manifest_sha256":
            batch.stage2_fresh_target_manifest_sha256,
        "origin_git_commit":
            commit,
        "datasets_version":
            EXPECTED_DATASETS_VERSION,
        "environment_explicit_sha256":
            EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        "batch_index":
            batch.batch_index,
        "batch_count":
            batch.batch_count,
        "batch_size":
            batch.batch_size,
        "full_target_count":
            batch.full_target_count,
        "requested_accessions":
            len(
                batch.targets
            ),
        "first_accession":
            batch.targets[
                0
            ].canonical_genbank_assembly_accession,
        "last_accession":
            batch.targets[
                -1
            ].canonical_genbank_assembly_accession,
        "batch_target_manifest_sha256":
            sha256_file(
                targets_path
            ),
        "accessions_sha256":
            sha256_file(
                accessions_path
            ),
        "dehydrated_zip_sha256":
            sha256_file(
                dehydrated_zip
            ),
        "fetch_txt_sha256":
            hydration_origin[
                "fetch_txt_sha256"
            ],
        "fetch_entries":
            hydration_origin[
                "fetch_entries"
            ],
        "initial_unresolved_accessions":
            hydration_origin[
                "initial_unresolved_accessions"
            ],
        "broad_rehydrate_exit_code":
            broad_exit_code,
        "targeted_retry_rounds":
            TARGETED_RETRY_ROUNDS,
        "targeted_retry_events":
            retry_events,
        "candidate_records":
            len(
                validated.candidate_rows
            ),
        "component_records":
            len(
                validated.component_rows
            ),
        "package_files":
            len(
                validated.package_file_rows
            ),
        "candidate_sequence_audit_sha256":
            sha256_file(
                candidate_path
            ),
        "component_sequence_audit_sha256":
            sha256_file(
                component_path
            ),
        "package_files_sha256":
            sha256_file(
                package_files_path
            ),
        "attempt_origin_sha256":
            attempt_sha,
        "execution_completed_at_utc":
            completed_at,
    }

    summary_payload = (
        transport_json_bytes(
            summary
        )
    )

    write_or_verify(
        summary_path,
        summary_payload,
    )

    if summary_path.read_bytes() != summary_payload:
        raise MonthlySequenceTransportExecutionError(
            "batch summary readback changed"
        )

    os.replace(
        partial_dir,
        final_dir,
    )

    fsync_directory(
        sequence_root
    )

    final_summary = (
        final_dir
        / SUMMARY_NAME
    )

    return TransportBatchResult(
        batch_index=(
            batch.batch_index
        ),
        batch_id=batch_id,
        output_dir=final_dir,
        summary_sha256=(
            sha256_file(
                final_summary
            )
        ),
        candidate_audit_sha256=(
            sha256_file(
                final_dir
                / CANDIDATE_AUDIT_NAME
            )
        ),
        component_audit_sha256=(
            sha256_file(
                final_dir
                / COMPONENT_AUDIT_NAME
            )
        ),
        package_files_sha256=(
            sha256_file(
                final_dir
                / PACKAGE_FILES_NAME
            )
        ),
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute one BacSelect monthly Stage 3B "
            "sequence-transport batch."
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
        "--sequence-plan-record",
        required=True,
    )

    parser.add_argument(
        "--fresh-target-manifest",
        required=True,
    )

    parser.add_argument(
        "--batch-index",
        required=True,
        type=int,
    )

    parser.add_argument(
        "--datasets-executable",
        required=True,
    )

    parser.add_argument(
        "--resume",
        action="store_true",
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlySequenceTransportExecutionError(
            "real monthly sequence transport requires explicit authorization"
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

    datasets = environment_preflight(
        repo,
        datasets_executable=(
            args.datasets_executable
        ),
    )

    upstream = load_upstream_contract(
        production_root=Path(
            args.production_root
        ),
        stage1_root=Path(
            args.stage1_root
        ),
        sequence_plan_record=Path(
            args.sequence_plan_record
        ),
        fresh_target_manifest=Path(
            args.fresh_target_manifest
        ),
        expected_commit=(
            args.expected_commit
        ),
    )

    batch = derive_transport_batch(
        upstream,
        batch_index=(
            args.batch_index
        ),
    )

    result = execute_transport_batch(
        repo=repo,
        stage1_root=Path(
            args.stage1_root
        ).resolve(),
        batch=batch,
        datasets_executable=datasets,
        execution_commit=(
            args.expected_commit
        ),
        transport_implementation_sha256=(
            sha256_file(
                script_path
            )
        ),
        resume=args.resume,
    )

    print(
        "PASS | BacSelect monthly sequence transport completed"
    )

    print(
        f"batch_id={result.batch_id}"
    )

    print(
        f"output_dir={result.output_dir}"
    )

    print(
        f"batch_summary_sha256="
        f"{result.summary_sha256}"
    )

    print(
        f"candidate_sequence_audit_sha256="
        f"{result.candidate_audit_sha256}"
    )

    print(
        f"component_sequence_audit_sha256="
        f"{result.component_audit_sha256}"
    )

    print(
        f"package_files_sha256="
        f"{result.package_files_sha256}"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(
            main()
        )
    except MonthlySequenceTransportExecutionError as exc:
        print(
            f"ERROR | {exc}",
            file=sys.stderr,
        )
        raise SystemExit(
            1
        )
