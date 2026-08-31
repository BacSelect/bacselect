#!/usr/bin/env python3
"""Execute the BacSelect monthly sequence-acquisition completion seal."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from typing import Callable, Sequence

from bacselect.monthly_release_start import (
    MonthlyReleaseStartError,
    audit_source_snapshot_record,
)
from bacselect.monthly_sequence_acquisition_completion import (
    CompletedTransportBatchEvidence,
    MonthlySequenceAcquisitionCompletionError,
    PackageFileReadbackObservation,
    audit_sequence_acquisition_completion_record,
    serialize_sequence_acquisition_completion_record,
)
from bacselect.monthly_sequence_plan import (
    audit_monthly_sequence_plan_record,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
    MonthlyValidatedPackage,
    package_file_manifest,
    validate_hydrated_package,
)


SOURCE_ELIGIBILITY_RELATIVE = Path(
    "src/bacselect/source_eligibility.py"
)

RELEASE_START_RELATIVE = Path(
    "src/bacselect/monthly_release_start.py"
)

SEQUENCE_PLAN_RELATIVE = Path(
    "src/bacselect/monthly_sequence_plan.py"
)

SEQUENCE_TRANSPORT_RELATIVE = Path(
    "src/bacselect/monthly_sequence_transport.py"
)

SEQUENCE_VALIDATION_RELATIVE = Path(
    "src/bacselect/monthly_sequence_validation.py"
)

STAGE3B_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/run_monthly_sequence_transport.py"
)

STAGE3B_WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_transport.py"
)

COMPLETION_CORE_RELATIVE = Path(
    "src/bacselect/monthly_sequence_acquisition_completion.py"
)

COMPLETION_CORE_TEST_RELATIVE = Path(
    "tests/test_monthly_sequence_acquisition_completion.py"
)

COMPLETION_METHOD_RELATIVE = Path(
    "validation/selector-v1/prospective-monthly-sequence-acquisition-completion.md"
)

EXECUTION_METHOD_RELATIVE = Path(
    "validation/selector-v1/"
    "prospective-monthly-sequence-acquisition-completion-execution.md"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/test_run_monthly_sequence_acquisition_completion.py"
)

ENVIRONMENT_RELATIVE = Path(
    "environments/ncbi-datasets-linux-64.explicit.txt"
)


EXPECTED_SOURCE_ELIGIBILITY_SHA256 = (
    "6e57dd950f972a9883e8fcbc78a18c694a5fabda58b03835f268eef681a03cc2"
)

EXPECTED_RELEASE_START_SHA256 = (
    "76cb24d9c70f1418e580408a04321fc7e5ae1e78709e60cb2f5d15b8a531588c"
)

EXPECTED_SEQUENCE_PLAN_SHA256 = (
    "e2213fee3703580b0e96fd280a050765812d0a369eff34846d8d1b958dae9e18"
)

EXPECTED_SEQUENCE_TRANSPORT_SHA256 = (
    "167a2a761d4f2488f4cbd562c4c289742469b3522196cf69017c1829a316a876"
)

EXPECTED_SEQUENCE_VALIDATION_SHA256 = (
    "dddb3d1ec355ee26537de653ef1b0f14d4a0e164aef2e34297726c9c6ab73d6f"
)

EXPECTED_STAGE3B_WRAPPER_SHA256 = (
    "110c9e5c26df8384893a51eb5d0dc0097d0b58e5f010828469973b56c67b5244"
)

EXPECTED_STAGE3B_WRAPPER_TEST_SHA256 = (
    "0e7aae01c326c9059ab9c1a9bdaa70b12c5e5dd9569646527fcfda352b50848f"
)

EXPECTED_COMPLETION_CORE_SHA256 = (
    "7482f70aa6c12c9dcc0a6c6b84c4058eeea1c0a227125b3ad97947a0eb303d61"
)

EXPECTED_COMPLETION_CORE_TEST_SHA256 = (
    "83c5fd0b285df4b6e593165160646d4c0c08054a5e434736fcb7b58476733965"
)

EXPECTED_COMPLETION_METHOD_SHA256 = (
    "e9991a28ecbd9ef1a6b294f68566494b1b0f35032dd5cb108c8782870f622595"
)

EXPECTED_EXECUTION_METHOD_SHA256 = (
    "faabdfb9270cff66d5d87c908bb6538e25c00a12b40554dddcb14b5750958aed"
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

SEQUENCE_ROOT_NAME = (
    "sequence-acquisition"
)

COMPLETION_NAME = (
    "sequence-acquisition-completion.json"
)

COMPLETION_TEMP_NAME = (
    ".sequence-acquisition-completion.json.tmp"
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

PACKAGE_NAME = (
    "package"
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

FETCH_RELATIVE = Path(
    "ncbi_dataset"
) / "fetch.txt"


COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

RELEASE_RE = re.compile(
    r"^[0-9]{4}\.[0-9]{2}$"
)

BATCH_RE = re.compile(
    r"^batch-[0-9]{5}$"
)

PARTIAL_BATCH_RE = re.compile(
    r"^batch-[0-9]{5}\.partial$"
)


class MonthlySequenceAcquisitionCompletionExecutionError(
    RuntimeError
):
    """Raised when completion execution fails closed."""


@dataclass(frozen=True)
class UpstreamContract:
    release_id: str
    source_snapshot_id: str
    source_snapshot_record_sha256: str
    stage1_root: Path
    sequence_plan_payload: bytes
    fresh_target_manifest_payload: bytes
    fresh_acquisition_count: int
    expected_batch_count: int


@dataclass(frozen=True)
class SequenceAcquisitionCompletionExecutionResult:
    release_id: str
    source_snapshot_id: str
    completion_path: Path
    fresh_acquisition_count: int
    completed_batch_count: int
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} must be lowercase SHA256"
        )

    return value


def sha256_file(
    path: Path,
    block_size: int = 1024 * 1024,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for block in iter(
            lambda:
                handle.read(
                    block_size
                ),
            b"",
        ):
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
        label=f"expected {label} SHA256",
    )

    observed = reader(
        path
    )

    if observed != expected_sha:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} SHA256 mismatch: {observed}"
        )


def git_output(
    repo: Path,
    *args: str,
) -> str:
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Git command failed: "
            + " ".join(
                args
            )
        )

    return result.stdout.strip()


def load_frozen_stage3b_execution(
    repo: Path,
):
    """Load the already-pinned Stage 3B execution module for exact helpers."""

    root = Path(
        repo
    ).resolve()

    path = (
        root
        / STAGE3B_WRAPPER_RELATIVE
    )

    try:
        metadata = os.lstat(
            path
        )
    except FileNotFoundError:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"missing frozen Stage 3B wrapper: {path}"
        ) from None

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISREG(
            metadata.st_mode
        )
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen Stage 3B wrapper is not a regular non-symlink file"
        )

    module_name = (
        "_bacselect_frozen_monthly_sequence_transport_execution"
    )

    existing = sys.modules.get(
        module_name
    )

    if existing is not None:
        existing_file = getattr(
            existing,
            "__file__",
            None,
        )

        if (
            existing_file is not None
            and Path(
                existing_file
            ).resolve()
            == path.resolve()
        ):
            return existing

        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen Stage 3B module name is already bound to another path"
        )

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "unable to construct frozen Stage 3B module specification"
        )

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        module_name
    ] = module

    try:
        spec.loader.exec_module(
            module
        )
    except Exception:
        sys.modules.pop(
            module_name,
            None,
        )
        raise

    for name in (
        "parse_fresh_targets",
        "_serialize_tsv",
        "FRESH_BATCH_SIZE",
    ):
        if not hasattr(
            module,
            name,
        ):
            raise MonthlySequenceAcquisitionCompletionExecutionError(
                f"frozen Stage 3B helper disappeared: {name}"
            )

    return module


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
    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    if git_reader(
        repo,
        "rev-parse",
        "HEAD",
    ) != commit:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "repository HEAD mismatch"
        )

    if git_reader(
        repo,
        "rev-parse",
        "origin/main",
    ) != commit:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "local origin/main mismatch"
        )

    if git_reader(
        repo,
        "status",
        "--porcelain",
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "repository working tree is not clean"
        )

    fixed = (
        (
            SOURCE_ELIGIBILITY_RELATIVE,
            EXPECTED_SOURCE_ELIGIBILITY_SHA256,
            "source-eligibility implementation",
        ),
        (
            RELEASE_START_RELATIVE,
            EXPECTED_RELEASE_START_SHA256,
            "monthly release-start implementation",
        ),
        (
            SEQUENCE_PLAN_RELATIVE,
            EXPECTED_SEQUENCE_PLAN_SHA256,
            "monthly sequence-plan implementation",
        ),
        (
            SEQUENCE_TRANSPORT_RELATIVE,
            EXPECTED_SEQUENCE_TRANSPORT_SHA256,
            "monthly sequence-transport implementation",
        ),
        (
            SEQUENCE_VALIDATION_RELATIVE,
            EXPECTED_SEQUENCE_VALIDATION_SHA256,
            "monthly sequence-validation implementation",
        ),
        (
            STAGE3B_WRAPPER_RELATIVE,
            EXPECTED_STAGE3B_WRAPPER_SHA256,
            "Stage 3B execution wrapper",
        ),
        (
            STAGE3B_WRAPPER_TEST_RELATIVE,
            EXPECTED_STAGE3B_WRAPPER_TEST_SHA256,
            "Stage 3B execution wrapper test",
        ),
        (
            COMPLETION_CORE_RELATIVE,
            EXPECTED_COMPLETION_CORE_SHA256,
            "sequence-acquisition completion contract",
        ),
        (
            COMPLETION_CORE_TEST_RELATIVE,
            EXPECTED_COMPLETION_CORE_TEST_SHA256,
            "sequence-acquisition completion contract test",
        ),
        (
            COMPLETION_METHOD_RELATIVE,
            EXPECTED_COMPLETION_METHOD_SHA256,
            "sequence-acquisition completion method",
        ),
        (
            EXECUTION_METHOD_RELATIVE,
            EXPECTED_EXECUTION_METHOD_SHA256,
            "sequence-acquisition completion execution method",
        ),
        (
            ENVIRONMENT_RELATIVE,
            EXPECTED_DATASETS_ENVIRONMENT_SHA256,
            "NCBI Datasets explicit environment",
        ),
    )

    for relative, expected, label in fixed:
        require_sha256(
            repo
            / relative,
            expected,
            label=label,
            reader=file_sha256_reader,
        )

    require_sha256(
        Path(
            __file__
        ).resolve(),
        expected_wrapper_sha256,
        label="sequence-acquisition completion executor",
        reader=file_sha256_reader,
    )

    require_sha256(
        repo
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label="sequence-acquisition completion executor test",
        reader=file_sha256_reader,
    )


def _require_absolute_file(
    path: Path,
    *,
    label: str,
) -> Path:
    supplied = Path(
        path
    )

    if not supplied.is_absolute():
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} path must be absolute"
        )

    try:
        metadata = os.lstat(
            supplied
        )
    except FileNotFoundError:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} does not exist: {supplied}"
        ) from None

    if stat.S_ISLNK(
        metadata.st_mode
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} path must not be a symbolic link: {supplied}"
        )

    if not stat.S_ISREG(
        metadata.st_mode
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} is not a regular file: {supplied}"
        )

    resolved = supplied.resolve()

    if not resolved.is_file():
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} does not resolve to a regular file: {resolved}"
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} must be below audited Stage 1 production root"
        )


def load_upstream_contract(
    *,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    expected_commit: str,
) -> UpstreamContract:
    commit = validate_git_commit(
        expected_commit,
        label="expected execution commit",
    )

    production = Path(
        production_root
    )

    if not production.is_absolute():
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "production root must be absolute"
        )

    supplied_stage1 = Path(
        stage1_root
    )

    if not supplied_stage1.is_absolute():
        raise MonthlySequenceAcquisitionCompletionExecutionError(
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
        if (
            path.is_symlink()
            or not path.is_file()
        ):
            raise MonthlySequenceAcquisitionCompletionExecutionError(
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 1 source-snapshot audit failed"
        ) from exc

    if snapshot[
        "expected_git_commit"
    ] != commit:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 1 source snapshot was produced by a different commit"
        )

    if snapshot[
        "ncbi_datasets_version"
    ] != EXPECTED_DATASETS_VERSION:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 1 NCBI Datasets version changed"
        )

    if snapshot[
        "ncbi_datasets_environment_sha256"
    ] != EXPECTED_DATASETS_ENVIRONMENT_SHA256:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 1 release ID is invalid"
        )

    expected_stage1 = (
        production.resolve()
        / release_id
        / "production"
        / commit
    )

    if stage1 != expected_stage1:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
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
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 2 sequence-plan provenance audit failed"
        ) from exc

    fresh_count = plan[
        "fresh_acquisition_count"
    ]

    batch_count = plan[
        "fresh_batch_count"
    ]

    if (
        isinstance(
            fresh_count,
            bool,
        )
        or not isinstance(
            fresh_count,
            int,
        )
        or fresh_count < 0
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 2 fresh-acquisition count is invalid"
        )

    if (
        isinstance(
            batch_count,
            bool,
        )
        or not isinstance(
            batch_count,
            int,
        )
        or batch_count < 0
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 2 expected batch count is invalid"
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
        stage1_root=stage1,
        sequence_plan_payload=(
            plan_payload
        ),
        fresh_target_manifest_payload=(
            manifest_payload
        ),
        fresh_acquisition_count=(
            fresh_count
        ),
        expected_batch_count=(
            batch_count
        ),
    )


def expected_batch_ids(
    count: int,
) -> tuple[
    str,
    ...,
]:
    return tuple(
        f"batch-{index:05d}"
        for index in range(
            1,
            count
            + 1,
        )
    )


def discover_sequence_entries(
    stage1_root: Path,
) -> tuple[
    tuple[
        str,
        ...,
    ],
    tuple[
        str,
        ...,
    ],
    tuple[
        str,
        ...,
    ],
]:
    sequence_root = (
        Path(
            stage1_root
        )
        / SEQUENCE_ROOT_NAME
    )

    if not os.path.lexists(
        sequence_root
    ):
        return (
            (),
            (),
            (),
        )

    if (
        sequence_root.is_symlink()
        or not sequence_root.is_dir()
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "sequence-acquisition root is not a real directory"
        )

    finals = []
    partials = []
    unexpected = []

    for entry in sorted(
        sequence_root.iterdir(),
        key=lambda value:
            value.name,
    ):
        name = entry.name

        if BATCH_RE.fullmatch(
            name
        ):
            if (
                entry.is_symlink()
                or not entry.is_dir()
            ):
                unexpected.append(
                    name
                )
            else:
                finals.append(
                    name
                )

        elif PARTIAL_BATCH_RE.fullmatch(
            name
        ):
            partials.append(
                name
            )

        else:
            unexpected.append(
                name
            )

    return (
        tuple(
            finals
        ),
        tuple(
            partials
        ),
        tuple(
            unexpected
        ),
    )


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    if (
        path.is_symlink()
        or not path.is_dir()
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} is not a real directory: {path}"
        )

    return path


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    try:
        metadata = os.lstat(
            path
        )
    except FileNotFoundError:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"missing {label}: {path}"
        ) from None

    if (
        stat.S_ISLNK(
            metadata.st_mode
        )
        or not stat.S_ISREG(
            metadata.st_mode
        )
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            f"{label} is not a regular non-symlink file: {path}"
        )

    return path


def observe_package_files(
    package: Path,
) -> tuple[
    PackageFileReadbackObservation,
    ...,
]:
    root = _require_real_directory(
        package,
        label="Stage 3B package",
    )

    observations = []

    for current, directory_names, filenames in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(
            current
        )

        for name in tuple(
            directory_names
        ):
            directory = (
                current_path
                / name
            )

            metadata = os.lstat(
                directory
            )

            if (
                stat.S_ISLNK(
                    metadata.st_mode
                )
                or not stat.S_ISDIR(
                    metadata.st_mode
                )
            ):
                raise MonthlySequenceAcquisitionCompletionExecutionError(
                    "package contains non-directory or symbolic-link "
                    f"directory entry: {directory}"
                )

        for name in filenames:
            path = (
                current_path
                / name
            )

            metadata = os.lstat(
                path
            )

            if (
                stat.S_ISLNK(
                    metadata.st_mode
                )
                or not stat.S_ISREG(
                    metadata.st_mode
                )
            ):
                raise MonthlySequenceAcquisitionCompletionExecutionError(
                    "package contains non-regular or symbolic-link file: "
                    f"{path}"
                )

            relative = (
                path.relative_to(
                    root
                ).as_posix()
            )

            observations.append(
                PackageFileReadbackObservation(
                    path=relative,
                    observed_size_bytes=(
                        metadata.st_size
                    ),
                    observed_sha256=(
                        sha256_file(
                            path
                        )
                    ),
                )
            )

    return tuple(
        sorted(
            observations,
            key=lambda value:
                value.path,
        )
    )


def collect_completed_batch_evidence(
    batch_dir: Path,
    *,
    batch_targets: Sequence[
        object
    ],
    package_validator: Callable[
        ...,
        MonthlyValidatedPackage,
    ] = validate_hydrated_package,
    tsv_serializer: Callable[
        ...,
        bytes,
    ],
) -> CompletedTransportBatchEvidence:
    batch = _require_real_directory(
        batch_dir,
        label="completed Stage 3B batch",
    )

    targets_path = _require_regular_file(
        batch
        / BATCH_TARGETS_NAME,
        label="batch-target manifest",
    )

    accessions_path = _require_regular_file(
        batch
        / ACCESSIONS_NAME,
        label="batch accession list",
    )

    attempt_path = _require_regular_file(
        batch
        / ATTEMPT_ORIGIN_NAME,
        label="attempt-origin evidence",
    )

    dehydrated_path = _require_regular_file(
        batch
        / DEHYDRATED_ZIP_NAME,
        label="dehydrated ZIP",
    )

    candidate_path = _require_regular_file(
        batch
        / CANDIDATE_AUDIT_NAME,
        label="candidate-sequence audit",
    )

    component_path = _require_regular_file(
        batch
        / COMPONENT_AUDIT_NAME,
        label="component-sequence audit",
    )

    package_files_path = _require_regular_file(
        batch
        / PACKAGE_FILES_NAME,
        label="package-files manifest",
    )

    summary_path = _require_regular_file(
        batch
        / SUMMARY_NAME,
        label="batch summary",
    )

    package = _require_real_directory(
        batch
        / PACKAGE_NAME,
        label="Stage 3B package",
    )

    fetch_path = _require_regular_file(
        package
        / FETCH_RELATIVE,
        label="NCBI Datasets fetch.txt",
    )

    candidate_payload = (
        candidate_path.read_bytes()
    )

    component_payload = (
        component_path.read_bytes()
    )

    package_files_payload = (
        package_files_path.read_bytes()
    )

    package_observations_before = (
        observe_package_files(
            package
        )
    )

    try:
        validated = package_validator(
            package,
            tuple(
                batch_targets
            ),
        )
    except Exception as exc:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 3A package revalidation failed during completion"
        ) from exc

    if not isinstance(
        validated,
        MonthlyValidatedPackage,
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 3A package revalidator returned unexpected result type"
        )

    try:
        reconstructed_candidate = (
            tsv_serializer(
                validated.candidate_rows,
                CANDIDATE_AUDIT_FIELDS,
            )
        )

        reconstructed_component = (
            tsv_serializer(
                validated.component_rows,
                COMPONENT_AUDIT_FIELDS,
            )
        )

        reconstructed_package_files = (
            tsv_serializer(
                validated.package_file_rows,
                PACKAGE_FILE_FIELDS,
            )
        )
    except Exception as exc:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen Stage 3B TSV serialization failed during completion"
        ) from exc

    if (
        candidate_payload
        != reconstructed_candidate
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "persisted candidate-sequence audit differs "
            "from Stage 3A reconstruction"
        )

    if (
        component_payload
        != reconstructed_component
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "persisted component-sequence audit differs "
            "from Stage 3A reconstruction"
        )

    if (
        package_files_payload
        != reconstructed_package_files
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "persisted package-files manifest differs "
            "from Stage 3A reconstruction"
        )

    candidate_payload_after = (
        candidate_path.read_bytes()
    )

    component_payload_after = (
        component_path.read_bytes()
    )

    package_files_payload_after = (
        package_files_path.read_bytes()
    )

    if (
        candidate_payload_after
        != candidate_payload
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "candidate-sequence audit changed during Stage 3A revalidation"
        )

    if (
        component_payload_after
        != component_payload
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "component-sequence audit changed during Stage 3A revalidation"
        )

    if (
        package_files_payload_after
        != package_files_payload
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "package-files manifest changed during Stage 3A revalidation"
        )

    package_observations_after = (
        observe_package_files(
            package
        )
    )

    if (
        package_observations_after
        != package_observations_before
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "package filesystem changed during Stage 3A revalidation"
        )

    return CompletedTransportBatchEvidence(
        batch_id=(
            batch.name
        ),
        summary_payload=(
            summary_path.read_bytes()
        ),
        observed_batch_target_manifest_sha256=(
            sha256_file(
                targets_path
            )
        ),
        observed_accessions_sha256=(
            sha256_file(
                accessions_path
            )
        ),
        observed_dehydrated_zip_sha256=(
            sha256_file(
                dehydrated_path
            )
        ),
        observed_fetch_txt_sha256=(
            sha256_file(
                fetch_path
            )
        ),
        observed_attempt_origin_sha256=(
            sha256_file(
                attempt_path
            )
        ),
        observed_candidate_audit_sha256=(
            sha256_file(
                candidate_path
            )
        ),
        observed_component_audit_sha256=(
            sha256_file(
                component_path
            )
        ),
        package_files_payload=(
            package_files_payload_after
        ),
        package_file_observations=(
            package_observations_after
        ),
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


def _write_all(
    descriptor: int,
    payload: bytes,
) -> None:
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
            raise MonthlySequenceAcquisitionCompletionExecutionError(
                "short write while creating completion artifact"
            )

        offset += written


def write_audited_completion(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[
        [bytes],
        object,
    ],
) -> tuple[
    Path,
    bytes,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "completion payload must be bytes"
        )

    final = (
        stage1_root
        / COMPLETION_NAME
    )

    temporary = (
        stage1_root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "sequence-acquisition completion artifact already exists"
        )

    if os.path.lexists(
        temporary
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "sequence-acquisition completion temporary artifact already exists"
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

        _write_all(
            descriptor,
            payload,
        )

        os.fsync(
            descriptor
        )
    finally:
        os.close(
            descriptor
        )

    temporary_readback = (
        temporary.read_bytes()
    )

    if temporary_readback != payload:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "temporary completion artifact readback changed"
        )

    if stat.S_IMODE(
        temporary.stat().st_mode
    ) != 0o644:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "temporary completion artifact mode changed"
        )

    auditor(
        temporary_readback
    )

    fsync_directory(
        stage1_root
    )

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )
    except FileExistsError as exc:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "sequence-acquisition completion artifact appeared "
            "before canonical publication"
        ) from exc

    fsync_directory(
        stage1_root
    )

    try:
        final_readback = (
            final.read_bytes()
        )

        if final_readback != payload:
            raise MonthlySequenceAcquisitionCompletionExecutionError(
                "final completion artifact readback changed"
            )

        if stat.S_IMODE(
            final.stat().st_mode
        ) != 0o644:
            raise MonthlySequenceAcquisitionCompletionExecutionError(
                "final completion artifact mode changed"
            )

        auditor(
            final_readback
        )

    except Exception:
        # os.link() succeeded only because the canonical path was absent.
        # On failed post-publication verification, remove only the link
        # created by this execution and retain the audited temporary inode.
        try:
            os.unlink(
                final
            )
        finally:
            fsync_directory(
                stage1_root
            )

        raise

    os.unlink(
        temporary
    )

    fsync_directory(
        stage1_root
    )

    return (
        final,
        final_readback,
    )


def execute_monthly_sequence_acquisition_completion(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    execution_commit: str,
    package_validator: Callable[
        ...,
        MonthlyValidatedPackage,
    ] = validate_hydrated_package,
) -> SequenceAcquisitionCompletionExecutionResult:
    repo_root = Path(
        repo
    ).resolve()

    upstream = load_upstream_contract(
        production_root=(
            production_root
        ),
        stage1_root=(
            stage1_root
        ),
        sequence_plan_record=(
            sequence_plan_record
        ),
        fresh_target_manifest=(
            fresh_target_manifest
        ),
        expected_commit=(
            execution_commit
        ),
    )

    completion_path = (
        upstream.stage1_root
        / COMPLETION_NAME
    )

    temporary_path = (
        upstream.stage1_root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        completion_path
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "sequence-acquisition completion artifact already exists"
        )

    if os.path.lexists(
        temporary_path
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "sequence-acquisition completion temporary artifact already exists"
        )

    stage3b = load_frozen_stage3b_execution(
        repo_root
    )

    try:
        targets = tuple(
            stage3b.parse_fresh_targets(
                upstream.fresh_target_manifest_payload
            )
        )
    except Exception as exc:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen Stage 3B target reconstruction failed"
        ) from exc

    if len(
        targets
    ) != upstream.fresh_acquisition_count:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 3B target reconstruction changed the Stage 2 population"
        )

    batch_size = getattr(
        stage3b,
        "FRESH_BATCH_SIZE",
        None,
    )

    if (
        isinstance(
            batch_size,
            bool,
        )
        or not isinstance(
            batch_size,
            int,
        )
        or batch_size <= 0
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen Stage 3B batch size is invalid"
        )

    tsv_serializer = getattr(
        stage3b,
        "_serialize_tsv",
        None,
    )

    if not callable(
        tsv_serializer
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen Stage 3B TSV serializer is unavailable"
        )

    (
        discovered_final_ids,
        discovered_partial_ids,
        unexpected_entries,
    ) = discover_sequence_entries(
        upstream.stage1_root
    )

    expected_ids = expected_batch_ids(
        upstream.expected_batch_count
    )

    if (
        discovered_final_ids
        != expected_ids
        or discovered_partial_ids
        or unexpected_entries
    ):
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "Stage 3B discovery is incomplete or contains "
            "partial/unexpected entries"
        )

    sequence_root = (
        upstream.stage1_root
        / SEQUENCE_ROOT_NAME
    )

    evidence_values = []

    for batch_index, batch_id in enumerate(
        expected_ids,
        1,
    ):
        start = (
            batch_index
            - 1
        ) * batch_size

        stop = min(
            start
            + batch_size,
            len(
                targets
            ),
        )

        batch_targets = targets[
            start:
            stop
        ]

        if not batch_targets:
            raise MonthlySequenceAcquisitionCompletionExecutionError(
                "derived Stage 3B completion batch target set is empty"
            )

        evidence_values.append(
            collect_completed_batch_evidence(
                sequence_root
                / batch_id,
                batch_targets=(
                    batch_targets
                ),
                package_validator=(
                    package_validator
                ),
                tsv_serializer=(
                    tsv_serializer
                ),
            )
        )

    evidence = tuple(
        evidence_values
    )

    contract_kwargs = {
        "source_snapshot_id":
            upstream.source_snapshot_id,
        "source_snapshot_record_sha256":
            upstream.source_snapshot_record_sha256,
        "stage2_sequence_plan_record":
            upstream.sequence_plan_payload,
        "stage2_fresh_target_manifest":
            upstream.fresh_target_manifest_payload,
        "origin_git_commit":
            execution_commit,
        "environment_explicit_sha256":
            EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        "batches":
            evidence,
        "discovered_final_batch_ids":
            discovered_final_ids,
        "discovered_partial_batch_ids":
            discovered_partial_ids,
        "unexpected_batch_entries":
            unexpected_entries,
    }

    try:
        completion_payload = (
            serialize_sequence_acquisition_completion_record(
                **contract_kwargs
            )
        )
    except (
        MonthlySequenceAcquisitionCompletionError,
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "frozen sequence-acquisition completion contract failed"
        ) from exc

    def auditor(
        payload: bytes,
    ) -> object:
        try:
            return (
                audit_sequence_acquisition_completion_record(
                    payload,
                    **contract_kwargs
                )
            )
        except (
            MonthlySequenceAcquisitionCompletionError,
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlySequenceAcquisitionCompletionExecutionError(
                "completion artifact read-back audit failed"
            ) from exc

    (
        final_path,
        final_payload,
    ) = write_audited_completion(
        stage1_root=(
            upstream.stage1_root
        ),
        payload=(
            completion_payload
        ),
        auditor=auditor,
    )

    return SequenceAcquisitionCompletionExecutionResult(
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        completion_path=(
            final_path
        ),
        fresh_acquisition_count=(
            upstream.fresh_acquisition_count
        ),
        completed_batch_count=(
            upstream.expected_batch_count
        ),
        completion_sha256=(
            hashlib.sha256(
                final_payload
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
            "Seal BacSelect monthly Stage 3B sequence acquisition "
            "after independent filesystem revalidation."
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
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        raise MonthlySequenceAcquisitionCompletionExecutionError(
            "production sequence-acquisition completion requires "
            "explicit authorization"
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
        execute_monthly_sequence_acquisition_completion(
            repo=repo,
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
            execution_commit=(
                args.expected_commit
            ),
        )
    )

    print(
        "PASS | BacSelect monthly sequence acquisition complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        f"source_snapshot_id={result.source_snapshot_id}"
    )

    print(
        f"fresh_acquisition_count={result.fresh_acquisition_count}"
    )

    print(
        f"completed_batch_count={result.completed_batch_count}"
    )

    print(
        f"completion_path={result.completion_path}"
    )

    print(
        f"completion_sha256={result.completion_sha256}"
    )

    print(
        "cumulative_cache_catalogue_complete=no"
    )

    print(
        "cache_verification_execution_complete=no"
    )

    print(
        "sequence_plan_execution_complete=no"
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
        MonthlySequenceAcquisitionCompletionExecutionError,
        MonthlySequenceAcquisitionCompletionError,
        MonthlyReleaseStartError,
        OSError,
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
