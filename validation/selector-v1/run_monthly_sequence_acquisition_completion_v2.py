#!/usr/bin/env python3
"""Execute recovery-aware BacSelect monthly sequence-acquisition completion v2."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import sys
from typing import Callable
from typing import Sequence

from bacselect import monthly_sequence_recovery_authority as authority
from bacselect import monthly_sequence_recovery_provider as recovery_provider
from bacselect import monthly_sequence_ordinary_provider as ordinary_provider
from bacselect.monthly_sequence_acquisition_completion import (
    MonthlySequenceAcquisitionCompletionError,
    PackageFileReadbackObservation,
    _audit_package_files_manifest,
    _audit_package_readback,
)
from bacselect.monthly_sequence_acquisition_completion_v2 import (
    AuthoritativeCompletedBatchEvidence,
    FRESH_PACKAGE_MANIFEST_NAME,
    FRESH_PROVIDER_SUMMARY_NAME,
    MonthlySequenceAcquisitionCompletionV2Error,
    RECOVERY_PACKAGE_MANIFEST_NAME,
    RECOVERY_PROVIDER_SUMMARY_NAME,
    SOURCE_CLASS_FRESH,
    SOURCE_CLASS_FRESH_RECOVERY,
    audit_sequence_acquisition_completion_v2_record,
    serialize_sequence_acquisition_completion_v2_record,
)
from bacselect.monthly_sequence_transport import (
    MonthlySequenceTransportError,
    batch_accession_bytes,
    batch_target_manifest_sha256,
)


V1_WRAPPER_NAME = (
    "run_monthly_sequence_acquisition_completion.py"
)

V1_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_sequence_acquisition_completion.py"
)

V1_WRAPPER_TEST_RELATIVE = Path(
    "tests/"
    "test_run_monthly_sequence_acquisition_completion.py"
)

V2_CORE_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_acquisition_completion_v2.py"
)

V2_CORE_TEST_RELATIVE = Path(
    "tests/"
    "test_monthly_sequence_acquisition_completion_v2.py"
)

ORDINARY_PROVIDER_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_ordinary_provider.py"
)

ORDINARY_PROVIDER_TEST_RELATIVE = Path(
    "tests/"
    "test_monthly_sequence_ordinary_provider.py"
)

RECOVERY_AUTHORITY_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_recovery_authority.py"
)

RECOVERY_PROVIDER_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_recovery_provider.py"
)

MISSING_GBFF_RECOVERY_RELATIVE = Path(
    "src/bacselect/"
    "monthly_missing_datasets_gbff_recovery.py"
)

MISSING_GBFF_EXECUTION_RELATIVE = Path(
    "src/bacselect/"
    "monthly_missing_datasets_gbff_execution.py"
)

SUPERSESSION_RECOVERY_RELATIVE = Path(
    "src/bacselect/"
    "monthly_post_snapshot_supersession_recovery.py"
)

SUPERSESSION_EXECUTION_RELATIVE = Path(
    "src/bacselect/"
    "monthly_post_snapshot_supersession_execution.py"
)

WRAPPER_TEST_RELATIVE = Path(
    "tests/"
    "test_run_monthly_sequence_acquisition_completion_v2.py"
)

EXPECTED_V1_WRAPPER_SHA256 = (
    "21c582b4e41dd8013f4716afe10c21f8c664133d423dd1daf9c7d1f7d0048c41"
)

EXPECTED_V1_WRAPPER_TEST_SHA256 = (
    "cef4b962a416b7ac276ef5086b24e78b9e0ca20aaead4c86acd8473a33de04b2"
)

FROZEN_DEPENDENCIES = (
    (
        V2_CORE_RELATIVE,
        "b3fd2c170acfcd14e0ca634da7c63f29c52d1d85c8c9b5dd3b70b01a2b2c305a",
        "sequence-acquisition completion v2 core",
    ),
    (
        V2_CORE_TEST_RELATIVE,
        "b1fbed49ee92f3bacc4a23dbc77846f646d5088a68b33e77cbce8f6f695a5936",
        "sequence-acquisition completion v2 core test",
    ),
    (
        ORDINARY_PROVIDER_RELATIVE,
        "24b9c543e2ebfd9ccc02b41082de13053b27b7b424b9969d27d0d6a5161d0fbd",
        "ordinary monthly sequence provider",
    ),
    (
        ORDINARY_PROVIDER_TEST_RELATIVE,
        "472bae90da8449200f7445875b4ea1012e190befad328be5e806090bb66e9d82",
        "ordinary monthly sequence provider test",
    ),
    (
        RECOVERY_AUTHORITY_RELATIVE,
        "cedcd2e69e2af2d891b3e27a2a99304a70d256c013e4b7b9faf1684e645370c1",
        "monthly sequence recovery authority",
    ),
    (
        RECOVERY_PROVIDER_RELATIVE,
        "460923545b890bd973c1310020c3f1e5d91958cd74e4fc6af676aa85d1beb441",
        "monthly sequence recovery provider",
    ),
    (
        MISSING_GBFF_RECOVERY_RELATIVE,
        "3cbcb8fd7e822cea3617614aede283771db18358f796b56b98eeee43bc1e2388",
        "missing-Datasets-GBFF recovery validator",
    ),
    (
        MISSING_GBFF_EXECUTION_RELATIVE,
        "88cbdd38350f1db6bc95c760737abc9673e97af1056f85dbab98f68ecc9e9378",
        "missing-Datasets-GBFF recovery execution",
    ),
    (
        SUPERSESSION_RECOVERY_RELATIVE,
        "dcb27d556a6532e6d51d3c5c8d953446f26c95c355ba09d1fc5b86ba7eb779c9",
        "post-snapshot supersession recovery validator",
    ),
    (
        SUPERSESSION_EXECUTION_RELATIVE,
        "2db63a487d97d256cb4f79502241ed6047c6b046ec78137d45368d940b57d9c0",
        "post-snapshot supersession recovery execution",
    ),
)

RECOVERY_PARENT_NAME = (
    "sequence-acquisition-recovery"
)

COMPLETION_NAME = (
    "sequence-acquisition-completion-v2.json"
)

COMPLETION_TEMP_NAME = (
    ".sequence-acquisition-completion-v2.json.tmp"
)


class MonthlySequenceAcquisitionCompletionV2ExecutionError(
    RuntimeError
):
    """Raised when recovery-aware completion execution fails closed."""


@dataclass(
    frozen=True,
)
class SequenceAcquisitionCompletionV2ExecutionResult:
    release_id: str
    source_snapshot_id: str
    source_production_commit: str
    completion_execution_commit: str
    completion_path: Path
    fresh_acquisition_count: int
    completed_batch_count: int
    fresh_batch_count: int
    recovery_batch_count: int
    completion_sha256: str


def _load_v1_execution():
    path = (
        Path(
            __file__
        ).resolve().with_name(
            V1_WRAPPER_NAME
        )
    )

    name = (
        "_bacselect_monthly_sequence_"
        "acquisition_completion_v1_execution"
    )

    existing = sys.modules.get(
        name
    )

    if existing is not None:
        return existing

    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "could not load frozen v1 completion executor"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


v1 = _load_v1_execution()


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
        message
    )


def _require_real_directory(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_dir()
    ):
        _fail(
            f"{label} is not a real directory: {value}"
        )

    return value


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    try:
        metadata = os.lstat(
            value
        )

    except FileNotFoundError:
        _fail(
            f"missing {label}: {value}"
        )

    if not stat.S_ISREG(
        metadata.st_mode
    ):
        _fail(
            f"{label} is not a regular file: {value}"
        )

    return value


def repository_preflight(
    repo: Path,
    *,
    completion_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
    git_reader: Callable[
        ...,
        str,
    ] | None = None,
    file_sha256_reader: Callable[
        [Path],
        str,
    ] | None = None,
) -> None:
    """
    Bind the executing checkout to the completion-execution commit.

    Stage 1 provenance is intentionally not checked here. It is independently
    bound to source_production_commit by the frozen v1 upstream loader.
    """

    repo_root = Path(
        repo
    ).resolve()

    if git_reader is None:
        git_reader = v1.git_output

    if file_sha256_reader is None:
        file_sha256_reader = v1.sha256_file

    v1.repository_preflight(
        repo_root,
        expected_commit=(
            completion_execution_commit
        ),
        expected_wrapper_sha256=(
            EXPECTED_V1_WRAPPER_SHA256
        ),
        expected_wrapper_test_sha256=(
            EXPECTED_V1_WRAPPER_TEST_SHA256
        ),
        git_reader=git_reader,
        file_sha256_reader=(
            file_sha256_reader
        ),
    )

    for (
        relative,
        expected,
        label,
    ) in FROZEN_DEPENDENCIES:
        v1.require_sha256(
            repo_root
            / relative,
            expected,
            label=label,
            reader=(
                file_sha256_reader
            ),
        )

    v1.require_sha256(
        Path(
            __file__
        ).resolve(),
        expected_wrapper_sha256,
        label=(
            "sequence-acquisition "
            "completion v2 executor"
        ),
        reader=(
            file_sha256_reader
        ),
    )

    v1.require_sha256(
        repo_root
        / WRAPPER_TEST_RELATIVE,
        expected_wrapper_test_sha256,
        label=(
            "sequence-acquisition "
            "completion v2 executor test"
        ),
        reader=(
            file_sha256_reader
        ),
    )


def _validate_recovery_roots(
    stage1_root: Path,
    recovery_roots: Sequence[
        Path
    ],
    *,
    source_production_commit: str,
) -> tuple[
    tuple[
        Path,
        ...,
    ],
    dict[
        Path,
        str,
    ],
]:
    source_commit = (
        v1.validate_git_commit(
            source_production_commit,
            label=(
                "source production commit"
            ),
        )
    )

    stage1 = _require_real_directory(
        Path(
            stage1_root
        ),
        label="Stage 1 production root",
    ).resolve()

    canonical_parent = (
        stage1
        / RECOVERY_PARENT_NAME
    )

    values = []
    commits = {}

    for supplied in recovery_roots:
        path = Path(
            supplied
        )

        if not path.is_absolute():
            _fail(
                "recovery root must be absolute"
            )

        if (
            path.is_symlink()
            or not path.is_dir()
        ):
            _fail(
                "recovery root is not a real directory"
            )

        resolved = path.resolve()

        if (
            resolved.name
            != f"source-{source_commit}"
        ):
            _fail(
                "recovery root source-production "
                "binding changed"
            )

        recovery_commit = (
            v1.validate_git_commit(
                resolved.parent.name,
                label="recovery-root commit",
            )
        )

        if (
            resolved.parent.parent
            != canonical_parent
        ):
            _fail(
                "recovery root is outside canonical "
                "sequence-acquisition-recovery hierarchy"
            )

        if resolved in commits:
            _fail(
                "duplicate recovery root supplied"
            )

        values.append(
            resolved
        )

        commits[
            resolved
        ] = recovery_commit

    return (
        tuple(
            values
        ),
        commits,
    )


def _batch_targets(
    targets: Sequence[
        object
    ],
    *,
    batch_index: int,
    batch_size: int,
) -> tuple[
    object,
    ...,
]:
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

    values = tuple(
        targets[
            start:
            stop
        ]
    )

    if not values:
        _fail(
            "expected authoritative batch has no targets"
        )

    return values


def _recovery_package_readback(
    audited: (
        recovery_provider
        .AuditedRecoveryProvider
    ),
) -> tuple[
    int,
    str,
    str,
]:
    batch = _require_real_directory(
        audited.batch_dir,
        label="audited recovery batch",
    )

    package = _require_real_directory(
        batch
        / authority.PACKAGE_NAME,
        label="audited recovery package",
    )

    manifest_path = (
        _require_regular_file(
            batch
            / authority.RECOVERY_PACKAGE_MANIFEST_NAME,
            label=(
                "recovery-package manifest"
            ),
        )
    )

    manifest_before = (
        manifest_path.read_bytes()
    )

    try:
        fingerprint = (
            authority.strict_tree_fingerprint(
                package
            )
        )

    except (
        authority
        .MonthlySequenceRecoveryAuthorityError
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "recovery package independent fingerprint failed"
        ) from exc

    manifest_after = (
        manifest_path.read_bytes()
    )

    if (
        manifest_after
        != manifest_before
    ):
        _fail(
            "recovery-package manifest changed "
            "during completion readback"
        )

    if (
        manifest_after
        != fingerprint.payload
    ):
        _fail(
            "recovery-package manifest differs "
            "from live package fingerprint"
        )

    if (
        fingerprint.sha256
        != audited.recovery_package_sha256
    ):
        _fail(
            "recovery package identity changed "
            "after provider audit"
        )

    try:
        manifest_rows = (
            _audit_package_files_manifest(
                manifest_after
            )
        )

        observations = tuple(
            PackageFileReadbackObservation(
                path=row[
                    "path"
                ],
                observed_size_bytes=int(
                    row[
                        "size_bytes"
                    ]
                ),
                observed_sha256=row[
                    "sha256"
                ],
            )
            for row
            in fingerprint.rows
        )

        (
            count,
            readback_sha,
        ) = _audit_package_readback(
            manifest_rows,
            observations,
        )

    except (
        TypeError,
        ValueError,
        MonthlySequenceAcquisitionCompletionError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "recovery package independent readback failed"
        ) from exc

    if count != fingerprint.file_count:
        raise RuntimeError(
            "recovery package readback population "
            "became inconsistent"
        )

    return (
        count,
        readback_sha,
        fingerprint.sha256,
    )


def _normalize_ordinary(
    authoritative: (
        authority
        .AuthoritativeSequenceBatch
    ),
    audited: (
        ordinary_provider
        .AuditedOrdinaryProvider
    ),
) -> AuthoritativeCompletedBatchEvidence:
    if (
        authoritative.source_class
        != SOURCE_CLASS_FRESH
    ):
        _fail(
            "ordinary provider received non-fresh authority"
        )

    if (
        audited.source_class
        != SOURCE_CLASS_FRESH
    ):
        _fail(
            "ordinary provider returned wrong source class"
        )

    if (
        audited.batch_id
        != authoritative.batch_id
    ):
        _fail(
            "ordinary provider batch identity changed"
        )

    return AuthoritativeCompletedBatchEvidence(
        batch_id=(
            audited.batch_id
        ),
        source_class=(
            SOURCE_CLASS_FRESH
        ),
        recovery_class=None,
        requested_accessions=(
            audited.requested_accessions
        ),
        first_accession=(
            audited.first_accession
        ),
        last_accession=(
            audited.last_accession
        ),
        observed_batch_target_manifest_sha256=(
            audited
            .observed_batch_target_manifest_sha256
        ),
        observed_accessions_sha256=(
            audited
            .observed_accessions_sha256
        ),
        observed_candidate_audit_sha256=(
            audited
            .observed_candidate_audit_sha256
        ),
        observed_component_audit_sha256=(
            audited
            .observed_component_audit_sha256
        ),
        provider_summary_name=(
            FRESH_PROVIDER_SUMMARY_NAME
        ),
        provider_summary_sha256=(
            audited.provider_summary_sha256
        ),
        package_manifest_name=(
            FRESH_PACKAGE_MANIFEST_NAME
        ),
        package_manifest_sha256=(
            audited.package_manifest_sha256
        ),
        package_file_count=(
            audited.package_file_count
        ),
        package_file_readback_count=(
            audited.package_file_readback_count
        ),
        package_file_readback_sha256=(
            audited.package_file_readback_sha256
        ),
    )


def _normalize_recovery(
    authoritative: (
        authority
        .AuthoritativeSequenceBatch
    ),
    audited: (
        recovery_provider
        .AuditedRecoveryProvider
    ),
    *,
    batch_targets: Sequence[
        object
    ],
    recovery_root_commits: dict[
        Path,
        str,
    ],
) -> AuthoritativeCompletedBatchEvidence:
    if (
        authoritative.source_class
        != SOURCE_CLASS_FRESH_RECOVERY
    ):
        _fail(
            "recovery provider received non-recovery authority"
        )

    if (
        audited.source_class
        != SOURCE_CLASS_FRESH_RECOVERY
    ):
        _fail(
            "recovery provider returned wrong source class"
        )

    if (
        audited.batch_id
        != authoritative.batch_id
    ):
        _fail(
            "recovery provider batch identity changed"
        )

    recovery_root = (
        audited.batch_dir.parent.resolve()
    )

    if (
        recovery_root
        not in recovery_root_commits
    ):
        _fail(
            "audited recovery came from an "
            "unsupplied recovery root"
        )

    if (
        recovery_root_commits[
            recovery_root
        ]
        != audited.recovery_commit
    ):
        _fail(
            "recovery root commit differs from "
            "audited recovery commit"
        )

    target_values = tuple(
        batch_targets
    )

    try:
        first_accession = (
            target_values[
                0
            ].canonical_genbank_assembly_accession
        )

        last_accession = (
            target_values[
                -1
            ].canonical_genbank_assembly_accession
        )

        target_sha = (
            batch_target_manifest_sha256(
                target_values
            )
        )

        accessions_sha = (
            hashlib.sha256(
                batch_accession_bytes(
                    target_values
                )
            ).hexdigest()
        )

    except (
        AttributeError,
        IndexError,
        MonthlySequenceTransportError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "unable to derive recovery batch target identity"
        ) from exc

    (
        package_count,
        readback_sha,
        package_manifest_sha,
    ) = _recovery_package_readback(
        audited
    )

    return AuthoritativeCompletedBatchEvidence(
        batch_id=(
            audited.batch_id
        ),
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        ),
        recovery_class=(
            audited.recovery_class
        ),
        requested_accessions=len(
            target_values
        ),
        first_accession=(
            first_accession
        ),
        last_accession=(
            last_accession
        ),
        observed_batch_target_manifest_sha256=(
            target_sha
        ),
        observed_accessions_sha256=(
            accessions_sha
        ),
        observed_candidate_audit_sha256=(
            audited.candidate_audit_sha256
        ),
        observed_component_audit_sha256=(
            audited.component_audit_sha256
        ),
        provider_summary_name=(
            RECOVERY_PROVIDER_SUMMARY_NAME
        ),
        provider_summary_sha256=(
            audited.recovery_summary_sha256
        ),
        package_manifest_name=(
            RECOVERY_PACKAGE_MANIFEST_NAME
        ),
        package_manifest_sha256=(
            package_manifest_sha
        ),
        package_file_count=(
            package_count
        ),
        package_file_readback_count=(
            package_count
        ),
        package_file_readback_sha256=(
            readback_sha
        ),
        source_partial_name=(
            audited.source_partial_dir.name
        ),
        recovery_commit=(
            audited.recovery_commit
        ),
        source_batch_sha256=(
            audited.source_batch_sha256
        ),
        source_package_sha256=(
            audited.source_package_sha256
        ),
        recovery_package_sha256=(
            audited.recovery_package_sha256
        ),
        recovery_summary_sha256=(
            audited.recovery_summary_sha256
        ),
        cause_evidence_sha256=(
            audited.cause_evidence_sha256
        ),
        transport_record_sha256=(
            audited.transport_record_sha256
        ),
    )


def _write_all(
    path: Path,
    payload: bytes,
) -> None:
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
    )

    descriptor = os.open(
        path,
        flags,
        0o644,
    )

    try:
        with os.fdopen(
            descriptor,
            "wb",
        ) as handle:
            descriptor = -1

            handle.write(
                payload
            )

            handle.flush()

            os.fsync(
                handle.fileno()
            )

    finally:
        if descriptor >= 0:
            os.close(
                descriptor
            )


def write_audited_completion_v2(
    stage1_root: Path,
    *,
    payload: bytes,
    auditor: Callable[
        [bytes],
        object,
    ],
) -> tuple[
    Path,
    bytes,
]:
    stage1 = _require_real_directory(
        stage1_root,
        label="Stage 1 production root",
    )

    final_path = (
        stage1
        / COMPLETION_NAME
    )

    temporary_path = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final_path
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "artifact already exists"
        )

    if os.path.lexists(
        temporary_path
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "temporary artifact already exists"
        )

    _write_all(
        temporary_path,
        payload,
    )

    temporary_payload = (
        temporary_path.read_bytes()
    )

    if temporary_payload != payload:
        _fail(
            "completion v2 temporary readback changed"
        )

    auditor(
        temporary_payload
    )

    try:
        os.link(
            temporary_path,
            final_path,
        )

    except FileExistsError as exc:
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "sequence-acquisition completion v2 "
            "artifact appeared concurrently"
        ) from exc

    v1.fsync_directory(
        stage1
    )

    try:
        temporary_stat = os.stat(
            temporary_path,
            follow_symlinks=False,
        )

        final_stat = os.stat(
            final_path,
            follow_symlinks=False,
        )

        same_inode = (
            temporary_stat.st_dev
            == final_stat.st_dev
            and temporary_stat.st_ino
            == final_stat.st_ino
        )

        if not same_inode:
            _fail(
                "completion v2 canonical inode "
                "differs from audited temporary inode"
            )

        final_payload = (
            final_path.read_bytes()
        )

        if final_payload != payload:
            _fail(
                "completion v2 canonical readback changed"
            )

        auditor(
            final_payload
        )

    except Exception:
        try:
            if (
                os.path.lexists(
                    final_path
                )
                and os.path.lexists(
                    temporary_path
                )
            ):
                temp_stat = os.stat(
                    temporary_path,
                    follow_symlinks=False,
                )

                final_stat = os.stat(
                    final_path,
                    follow_symlinks=False,
                )

                if (
                    temp_stat.st_dev
                    == final_stat.st_dev
                    and temp_stat.st_ino
                    == final_stat.st_ino
                ):
                    final_path.unlink()

                    v1.fsync_directory(
                        stage1
                    )

        finally:
            pass

        raise

    temporary_path.unlink()

    v1.fsync_directory(
        stage1
    )

    return (
        final_path,
        final_payload,
    )


def execute_monthly_sequence_acquisition_completion_v2(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    recovery_roots: Sequence[
        Path
    ] = (),
    package_validator: Callable[
        ...,
        object,
    ] | None = None,
) -> SequenceAcquisitionCompletionV2ExecutionResult:
    repo_root = Path(
        repo
    ).resolve()

    source_commit = (
        v1.validate_git_commit(
            source_production_commit,
            label=(
                "source production commit"
            ),
        )
    )

    completion_commit = (
        v1.validate_git_commit(
            completion_execution_commit,
            label=(
                "completion execution commit"
            ),
        )
    )

    try:
        upstream = (
            v1.load_upstream_contract(
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
                    source_commit
                ),
            )
        )

    except (
        Exception,
    ) as exc:
        if isinstance(
            exc,
            MonthlySequenceAcquisitionCompletionV2ExecutionError,
        ):
            raise

        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "source-production upstream contract audit failed"
        ) from exc

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
        _fail(
            "sequence-acquisition completion v2 "
            "artifact already exists"
        )

    if os.path.lexists(
        temporary_path
    ):
        _fail(
            "sequence-acquisition completion v2 "
            "temporary artifact already exists"
        )

    stage3b = (
        v1.load_frozen_stage3b_execution(
            repo_root
        )
    )

    try:
        targets = tuple(
            stage3b.parse_fresh_targets(
                upstream
                .fresh_target_manifest_payload
            )
        )

    except Exception as exc:
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "frozen Stage 3B target reconstruction failed"
        ) from exc

    if (
        len(
            targets
        )
        != upstream.fresh_acquisition_count
    ):
        _fail(
            "Stage 3B target reconstruction changed "
            "the Stage 2 population"
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
        _fail(
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
        _fail(
            "frozen Stage 3B TSV serializer is unavailable"
        )

    if package_validator is None:
        package_validator = (
            v1.validate_hydrated_package
        )

    if not callable(
        package_validator
    ):
        _fail(
            "Stage 3A package validator is unavailable"
        )

    expected_ids = (
        v1.expected_batch_ids(
            upstream.expected_batch_count
        )
    )

    sequence_root = (
        upstream.stage1_root
        / v1.SEQUENCE_ROOT_NAME
    )

    (
        normalized_recovery_roots,
        recovery_root_commits,
    ) = _validate_recovery_roots(
        upstream.stage1_root,
        recovery_roots,
        source_production_commit=(
            source_commit
        ),
    )

    if not expected_ids:
        if os.path.lexists(
            sequence_root
        ):
            try:
                authoritative = (
                    authority
                    .resolve_authoritative_sequence_batches(
                        sequence_root=(
                            sequence_root
                        ),
                        recovery_roots=(
                            normalized_recovery_roots
                        ),
                        expected_batch_ids=(
                            expected_ids
                        ),
                        expected_release_id=(
                            upstream.release_id
                        ),
                        expected_source_production_commit=(
                            source_commit
                        ),
                    )
                )

            except (
                authority
                .MonthlySequenceRecoveryAuthorityError
            ) as exc:
                raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
                    "authoritative sequence-batch resolution failed"
                ) from exc

        else:
            if normalized_recovery_roots:
                _fail(
                    "recovery roots supplied for an empty "
                    "Stage 3B population"
                )

            authoritative = ()

    else:
        try:
            authoritative = (
                authority
                .resolve_authoritative_sequence_batches(
                    sequence_root=(
                        sequence_root
                    ),
                    recovery_roots=(
                        normalized_recovery_roots
                    ),
                    expected_batch_ids=(
                        expected_ids
                    ),
                    expected_release_id=(
                        upstream.release_id
                    ),
                    expected_source_production_commit=(
                        source_commit
                    ),
                )
            )

        except (
            authority
            .MonthlySequenceRecoveryAuthorityError
        ) as exc:
            raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
                "authoritative sequence-batch resolution failed"
            ) from exc

    if tuple(
        value.batch_id
        for value
        in authoritative
    ) != expected_ids:
        _fail(
            "authoritative sequence-batch order changed"
        )

    plan_sha = hashlib.sha256(
        upstream.sequence_plan_payload
    ).hexdigest()

    manifest_sha = hashlib.sha256(
        upstream.fresh_target_manifest_payload
    ).hexdigest()

    source_snapshot_report = (
        upstream.stage1_root
        / v1.RAW_RESPONSE_NAME
    )

    evidence_values = []

    for (
        batch_index,
        authoritative_batch,
    ) in enumerate(
        authoritative,
        1,
    ):
        target_values = _batch_targets(
            targets,
            batch_index=(
                batch_index
            ),
            batch_size=(
                batch_size
            ),
        )

        if (
            authoritative_batch.source_class
            == SOURCE_CLASS_FRESH
        ):
            try:
                transport_evidence = (
                    v1.collect_completed_batch_evidence(
                        authoritative_batch.batch_dir,
                        batch_targets=(
                            target_values
                        ),
                        package_validator=(
                            package_validator
                        ),
                        tsv_serializer=(
                            tsv_serializer
                        ),
                    )
                )

            except Exception as exc:
                raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
                    "ordinary Stage 3B filesystem "
                    "revalidation failed"
                ) from exc

            try:
                audited = (
                    ordinary_provider
                    .audit_completed_transport_provider(
                        transport_evidence,
                        batch_index=(
                            batch_index
                        ),
                        expected_batch_count=(
                            upstream
                            .expected_batch_count
                        ),
                        expected_fresh_count=(
                            upstream
                            .fresh_acquisition_count
                        ),
                        batch_targets=(
                            target_values
                        ),
                        source_snapshot_id=(
                            upstream
                            .source_snapshot_id
                        ),
                        source_snapshot_record_sha256=(
                            upstream
                            .source_snapshot_record_sha256
                        ),
                        stage2_sequence_plan_record_sha256=(
                            plan_sha
                        ),
                        stage2_fresh_target_manifest_sha256=(
                            manifest_sha
                        ),
                        source_production_commit=(
                            source_commit
                        ),
                        environment_explicit_sha256=(
                            v1
                            .EXPECTED_DATASETS_ENVIRONMENT_SHA256
                        ),
                    )
                )

            except (
                ordinary_provider
                .MonthlySequenceOrdinaryProviderError,
                TypeError,
                ValueError,
            ) as exc:
                raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
                    "ordinary provider audit failed"
                ) from exc

            evidence_values.append(
                _normalize_ordinary(
                    authoritative_batch,
                    audited,
                )
            )

        elif (
            authoritative_batch.source_class
            == SOURCE_CLASS_FRESH_RECOVERY
        ):
            try:
                audited_recovery = (
                    recovery_provider
                    .audit_authoritative_recovery_provider(
                        authoritative_batch,
                        targets=(
                            target_values
                        ),
                        expected_release_id=(
                            upstream.release_id
                        ),
                        expected_source_production_commit=(
                            source_commit
                        ),
                        source_snapshot_report=(
                            source_snapshot_report
                        ),
                    )
                )

            except (
                recovery_provider
                .MonthlySequenceRecoveryProviderError,
                TypeError,
                ValueError,
            ) as exc:
                raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
                    "recovery provider audit failed"
                ) from exc

            if (
                audited_recovery
                .source_production_commit
                != source_commit
            ):
                _fail(
                    "recovery provider source-production "
                    "commit changed"
                )

            evidence_values.append(
                _normalize_recovery(
                    authoritative_batch,
                    audited_recovery,
                    batch_targets=(
                        target_values
                    ),
                    recovery_root_commits=(
                        recovery_root_commits
                    ),
                )
            )

        else:
            _fail(
                "authority resolver returned "
                "unknown source class"
            )

    contract_kwargs = {
        "source_snapshot_id":
            upstream.source_snapshot_id,
        "source_snapshot_record_sha256":
            upstream
            .source_snapshot_record_sha256,
        "stage2_sequence_plan_record":
            upstream.sequence_plan_payload,
        "stage2_fresh_target_manifest":
            upstream
            .fresh_target_manifest_payload,
        "source_production_commit":
            source_commit,
        "completion_execution_commit":
            completion_commit,
        "environment_explicit_sha256":
            v1
            .EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        "batches":
            tuple(
                evidence_values
            ),
    }

    try:
        completion_payload = (
            serialize_sequence_acquisition_completion_v2_record(
                **contract_kwargs
            )
        )

    except (
        MonthlySequenceAcquisitionCompletionV2Error,
        TypeError,
        ValueError,
    ) as exc:
        raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
            "frozen sequence-acquisition "
            "completion v2 contract failed"
        ) from exc

    def auditor(
        payload: bytes,
    ) -> object:
        try:
            return (
                audit_sequence_acquisition_completion_v2_record(
                    payload,
                    **contract_kwargs
                )
            )

        except (
            MonthlySequenceAcquisitionCompletionV2Error,
            TypeError,
            ValueError,
        ) as exc:
            raise MonthlySequenceAcquisitionCompletionV2ExecutionError(
                "completion v2 artifact read-back audit failed"
            ) from exc

    (
        final_path,
        final_payload,
    ) = write_audited_completion_v2(
        upstream.stage1_root,
        payload=(
            completion_payload
        ),
        auditor=auditor,
    )

    final_record = auditor(
        final_payload
    )

    class_counts = final_record[
        "source_class_counts"
    ]

    return SequenceAcquisitionCompletionV2ExecutionResult(
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        source_production_commit=(
            source_commit
        ),
        completion_execution_commit=(
            completion_commit
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
        fresh_batch_count=int(
            class_counts[
                SOURCE_CLASS_FRESH
            ]
        ),
        recovery_batch_count=int(
            class_counts[
                SOURCE_CLASS_FRESH_RECOVERY
            ]
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
            "Seal BacSelect monthly Stage 3B "
            "sequence acquisition using explicit "
            "ordinary/recovery authority."
        )
    )

    parser.add_argument(
        "--source-production-commit",
        required=True,
    )

    parser.add_argument(
        "--completion-execution-commit",
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
        "--recovery-root",
        action="append",
        default=[],
    )

    parser.add_argument(
        "--authorize-real-execution",
        action="store_true",
    )

    args = parser.parse_args(
        argv
    )

    if not args.authorize_real_execution:
        _fail(
            "production sequence-acquisition "
            "completion v2 requires explicit authorization"
        )

    script_path = Path(
        __file__
    ).resolve()

    repo = script_path.parents[
        2
    ]

    repository_preflight(
        repo,
        completion_execution_commit=(
            args.completion_execution_commit
        ),
        expected_wrapper_sha256=(
            args.expected_wrapper_sha256
        ),
        expected_wrapper_test_sha256=(
            args.expected_wrapper_test_sha256
        ),
    )

    result = (
        execute_monthly_sequence_acquisition_completion_v2(
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
            source_production_commit=(
                args.source_production_commit
            ),
            completion_execution_commit=(
                args.completion_execution_commit
            ),
            recovery_roots=tuple(
                Path(
                    value
                )
                for value
                in args.recovery_root
            ),
        )
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        "source_snapshot_id="
        f"{result.source_snapshot_id}"
    )

    print(
        "source_production_commit="
        f"{result.source_production_commit}"
    )

    print(
        "completion_execution_commit="
        f"{result.completion_execution_commit}"
    )

    print(
        "fresh_acquisition_count="
        f"{result.fresh_acquisition_count}"
    )

    print(
        "completed_batch_count="
        f"{result.completed_batch_count}"
    )

    print(
        "fresh_batch_count="
        f"{result.fresh_batch_count}"
    )

    print(
        "recovery_batch_count="
        f"{result.recovery_batch_count}"
    )

    print(
        "completion_path="
        f"{result.completion_path}"
    )

    print(
        "completion_sha256="
        f"{result.completion_sha256}"
    )

    print(
        "cumulative_cache_catalogue_complete=no"
    )

    print(
        "public_monthly_release_generated=no"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
