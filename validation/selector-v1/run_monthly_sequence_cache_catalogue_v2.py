#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from typing import Sequence

from bacselect import monthly_sequence_cache_catalogue as cache_v1
from bacselect import monthly_sequence_cache_catalogue_v2 as cache_v2


COMPLETION_V2_WRAPPER_NAME = (
    "run_monthly_sequence_acquisition_completion_v2.py"
)

CACHE_V1_WRAPPER_NAME = (
    "run_monthly_sequence_cache_catalogue.py"
)

COMPLETION_V2_WRAPPER_RELATIVE = Path(
    "validation/selector-v1/"
    "run_monthly_sequence_acquisition_completion_v2.py"
)

AUTHORITY_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_recovery_authority.py"
)

ORDINARY_PROVIDER_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_ordinary_provider.py"
)

RECOVERY_PROVIDER_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_recovery_provider.py"
)

CACHE_V2_CORE_RELATIVE = Path(
    "src/bacselect/"
    "monthly_sequence_cache_catalogue_v2.py"
)

CACHE_V2_CORE_TEST_RELATIVE = Path(
    "tests/"
    "test_monthly_sequence_cache_catalogue_v2.py"
)

EXPECTED_COMPLETION_V2_WRAPPER_SHA256 = (
    "6be860e1d491a3e75457e7020774a05310faaa48444656517e0a40a1f2574d51"
)

EXPECTED_AUTHORITY_SHA256 = (
    "cedcd2e69e2af2d891b3e27a2a99304a70d256c013e4b7b9faf1684e645370c1"
)

EXPECTED_ORDINARY_PROVIDER_SHA256 = (
    "24b9c543e2ebfd9ccc02b41082de13053b27b7b424b9969d27d0d6a5161d0fbd"
)

EXPECTED_RECOVERY_PROVIDER_SHA256 = (
    "460923545b890bd973c1310020c3f1e5d91958cd74e4fc6af676aa85d1beb441"
)

EXPECTED_CACHE_V2_CORE_SHA256 = (
    "1a7f9c2015c73e0cbada26064ad137fd6468ce5592dd5c518095d8f20d2937ca"
)

EXPECTED_CACHE_V2_CORE_TEST_SHA256 = (
    "7a33c75dd3f3e4a0515546070ca3303a6699c631975c6967e2dc775d498b3de8"
)

COMPLETION_NAME = (
    "sequence-acquisition-completion-v2.json"
)

SEQUENCE_ROOT_NAME = (
    "sequence-acquisition"
)

CATALOGUE_V1_NAME = (
    "sequence-cache-catalogue.json"
)

CATALOGUE_V2_NAME = (
    "sequence-cache-catalogue-v2.json"
)

CATALOGUE_V2_TEMP_NAME = (
    ".sequence-cache-catalogue-v2.json.tmp"
)

SUMMARY_NAME = (
    "batch-summary.json"
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

RECOVERY_SUMMARY_NAME = (
    "recovery-summary.json"
)

RECOVERY_PACKAGE_FILES_NAME = (
    "recovery-package-files.tsv"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

RELEASE_RE = re.compile(
    r"^(?P<year>[0-9]{4})\."
    r"(?P<month>0[1-9]|1[0-2])$"
)


class MonthlySequenceCacheCatalogueV2ExecutionError(
    RuntimeError
):
    pass


@dataclass(
    frozen=True
)
class CatalogueChainItemV2:
    release_id: str
    cache_execution_commit: str
    catalogue_path: Path
    catalogue_payload: bytes
    catalogue_sha256: str
    catalogue_record: dict[
        str,
        object,
    ]


@dataclass(
    frozen=True
)
class AuditedCompletionV2Context:
    release_id: str
    source_snapshot_id: str
    stage1_root: Path
    completion_payload: bytes
    completion_record: dict[
        str,
        object,
    ]
    batch_evidence: tuple[
        cache_v2.AuthoritativeSequenceCacheBatchEvidenceV2,
        ...,
    ]
    fresh_acquisition_count: int
    source_production_commit: str
    completion_execution_commit: str


@dataclass(
    frozen=True
)
class SequenceCacheCatalogueV2ExecutionResult:
    release_id: str
    source_snapshot_id: str
    catalogue_path: Path
    catalogue_sha256: str
    catalogue_mode: str
    previous_catalogue_release_id: str | None
    previous_catalogue_sha256: str | None
    catalogue_entry_count: int
    current_acquisition_count: int


def _fail(
    message: str,
) -> None:
    raise MonthlySequenceCacheCatalogueV2ExecutionError(
        message
    )


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
        _fail(
            f"{label} is not a 40-character lowercase Git commit"
        )

    return value


def validate_release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or RELEASE_RE.fullmatch(
            value
        )
        is None
    ):
        _fail(
            "release ID is invalid"
        )

    return value


def release_ordinal(
    release_id: str,
) -> int:
    release = validate_release_id(
        release_id
    )

    match = RELEASE_RE.fullmatch(
        release
    )

    if match is None:
        raise RuntimeError(
            "validated release did not match"
        )

    year = int(
        match.group(
            "year"
        )
    )

    month = int(
        match.group(
            "month"
        )
    )

    return (
        year
        * 12
        + month
    )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        for chunk in iter(
            lambda:
                handle.read(
                    1024
                    * 1024
                ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


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
            f"{label} is not a real directory"
        )

    return value.resolve()


def _require_regular_file(
    path: Path,
    *,
    label: str,
) -> Path:
    value = Path(
        path
    )

    if (
        value.is_symlink()
        or not value.is_file()
    ):
        _fail(
            f"{label} is not a regular file"
        )

    return value.resolve()


def _load_local_wrapper(
    filename: str,
    *,
    module_name: str,
):
    path = (
        Path(
            __file__
        ).resolve().with_name(
            filename
        )
    )

    existing = sys.modules.get(
        module_name
    )

    if existing is not None:
        return existing

    spec = (
        importlib.util
        .spec_from_file_location(
            module_name,
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        _fail(
            f"could not load frozen wrapper {filename}"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        module_name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


def load_completion_v2_execution():
    return _load_local_wrapper(
        COMPLETION_V2_WRAPPER_NAME,
        module_name=(
            "_bacselect_monthly_sequence_"
            "acquisition_completion_v2_for_cache_v2"
        ),
    )


def load_cache_v1_execution():
    return _load_local_wrapper(
        CACHE_V1_WRAPPER_NAME,
        module_name=(
            "_bacselect_monthly_sequence_"
            "cache_catalogue_v1_for_cache_v2"
        ),
    )


def git_output(
    repo: Path,
    *args: str,
) -> str:
    try:
        result = subprocess.run(
            (
                "git",
                "-C",
                str(
                    repo
                ),
                *args,
            ),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    except subprocess.CalledProcessError as exc:
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
            "Git repository preflight failed"
        ) from exc

    return result.stdout.strip()


def repository_preflight(
    repo: Path,
    *,
    cache_execution_commit: str,
) -> None:
    root = _require_real_directory(
        Path(
            repo
        ),
        label="repository root",
    )

    commit = validate_git_commit(
        cache_execution_commit,
        label="cache execution commit",
    )

    if (
        git_output(
            root,
            "rev-parse",
            "HEAD",
        )
        != commit
    ):
        _fail(
            "repository HEAD differs from cache execution commit"
        )

    if git_output(
        root,
        "status",
        "--porcelain",
    ):
        _fail(
            "repository is not clean"
        )

    expected = {
        COMPLETION_V2_WRAPPER_RELATIVE:
            EXPECTED_COMPLETION_V2_WRAPPER_SHA256,
        AUTHORITY_RELATIVE:
            EXPECTED_AUTHORITY_SHA256,
        ORDINARY_PROVIDER_RELATIVE:
            EXPECTED_ORDINARY_PROVIDER_SHA256,
        RECOVERY_PROVIDER_RELATIVE:
            EXPECTED_RECOVERY_PROVIDER_SHA256,
        CACHE_V2_CORE_RELATIVE:
            EXPECTED_CACHE_V2_CORE_SHA256,
        CACHE_V2_CORE_TEST_RELATIVE:
            EXPECTED_CACHE_V2_CORE_TEST_SHA256,
    }

    for relative, expected_sha in expected.items():
        path = _require_regular_file(
            root
            / relative,
            label=(
                "frozen cache-v2 dependency "
                + str(
                    relative
                )
            ),
        )

        observed = sha256_file(
            path
        )

        if observed != expected_sha:
            _fail(
                "frozen cache-v2 dependency identity changed: "
                + str(
                    relative
                )
            )


def _read_provider_payload(
    path: Path,
    *,
    expected_sha256: str,
    label: str,
) -> bytes:
    file = _require_regular_file(
        path,
        label=label,
    )

    payload = file.read_bytes()

    observed = hashlib.sha256(
        payload
    ).hexdigest()

    if observed != expected_sha256:
        _fail(
            f"{label} differs from audited provider identity"
        )

    return payload


def _cache_batch_evidence(
    authoritative,
    normalized,
) -> cache_v2.AuthoritativeSequenceCacheBatchEvidenceV2:
    batch = _require_real_directory(
        authoritative.batch_dir,
        label=(
            "authoritative provider batch "
            + authoritative.batch_id
        ),
    )

    source_class = normalized.source_class

    if (
        source_class
        == cache_v2.SOURCE_CLASS_FRESH
    ):
        if (
            normalized.provider_summary_name
            != SUMMARY_NAME
        ):
            _fail(
                "fresh provider summary name changed"
            )

        if (
            normalized.package_manifest_name
            != PACKAGE_FILES_NAME
        ):
            _fail(
                "fresh package manifest name changed"
            )

    elif (
        source_class
        == cache_v2.SOURCE_CLASS_FRESH_RECOVERY
    ):
        if (
            normalized.provider_summary_name
            != RECOVERY_SUMMARY_NAME
        ):
            _fail(
                "recovery provider summary name changed"
            )

        if (
            normalized.package_manifest_name
            != RECOVERY_PACKAGE_FILES_NAME
        ):
            _fail(
                "recovery package manifest name changed"
            )

    else:
        _fail(
            "normalized completion evidence carries unknown source class"
        )

    summary_payload = _read_provider_payload(
        batch
        / normalized.provider_summary_name,
        expected_sha256=(
            normalized.provider_summary_sha256
        ),
        label=(
            authoritative.batch_id
            + " provider summary"
        ),
    )

    candidate_payload = _read_provider_payload(
        batch
        / CANDIDATE_AUDIT_NAME,
        expected_sha256=(
            normalized
            .observed_candidate_audit_sha256
        ),
        label=(
            authoritative.batch_id
            + " candidate audit"
        ),
    )

    component_payload = _read_provider_payload(
        batch
        / COMPONENT_AUDIT_NAME,
        expected_sha256=(
            normalized
            .observed_component_audit_sha256
        ),
        label=(
            authoritative.batch_id
            + " component audit"
        ),
    )

    package_payload = _read_provider_payload(
        batch
        / normalized.package_manifest_name,
        expected_sha256=(
            normalized.package_manifest_sha256
        ),
        label=(
            authoritative.batch_id
            + " package manifest"
        ),
    )

    return (
        cache_v2
        .AuthoritativeSequenceCacheBatchEvidenceV2(
            batch_id=(
                normalized.batch_id
            ),
            source_class=(
                normalized.source_class
            ),
            recovery_class=(
                normalized.recovery_class
            ),
            provider_summary_name=(
                normalized.provider_summary_name
            ),
            provider_summary_payload=(
                summary_payload
            ),
            candidate_audit_payload=(
                candidate_payload
            ),
            component_audit_payload=(
                component_payload
            ),
            package_manifest_name=(
                normalized.package_manifest_name
            ),
            package_manifest_payload=(
                package_payload
            ),
            source_partial_name=(
                normalized.source_partial_name
            ),
            recovery_commit=(
                normalized.recovery_commit
            ),
            source_batch_sha256=(
                normalized.source_batch_sha256
            ),
            source_package_sha256=(
                normalized.source_package_sha256
            ),
            recovery_package_sha256=(
                normalized.recovery_package_sha256
            ),
            recovery_summary_sha256=(
                normalized.recovery_summary_sha256
            ),
            cause_evidence_sha256=(
                normalized.cause_evidence_sha256
            ),
            transport_record_sha256=(
                normalized.transport_record_sha256
            ),
        )
    )


def audit_existing_completion_v2(
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
    ],
    package_validator=None,
) -> AuditedCompletionV2Context:
    repo_root = _require_real_directory(
        Path(
            repo
        ),
        label="repository root",
    )

    source_commit = validate_git_commit(
        source_production_commit,
        label="source production commit",
    )

    completion_commit = validate_git_commit(
        completion_execution_commit,
        label="completion execution commit",
    )

    execution = (
        load_completion_v2_execution()
    )

    v1_execution = (
        execution._load_v1_execution()
    )

    try:
        upstream = (
            v1_execution
            .load_upstream_contract(
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

    except Exception as exc:
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
            "source-production upstream contract audit failed"
        ) from exc

    completion_file = _require_regular_file(
        upstream.stage1_root
        / COMPLETION_NAME,
        label=(
            "sequence-acquisition completion v2"
        ),
    )

    completion_payload_before = (
        completion_file.read_bytes()
    )

    stage3b = (
        v1_execution
        .load_frozen_stage3b_execution(
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
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
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
        package_validator = getattr(
            v1_execution,
            "validate_hydrated_package",
            None,
        )

    if not callable(
        package_validator
    ):
        _fail(
            "frozen Stage 3A package validator is unavailable"
        )

    expected_ids = (
        v1_execution
        .expected_batch_ids(
            upstream.expected_batch_count
        )
    )

    sequence_root = (
        upstream.stage1_root
        / SEQUENCE_ROOT_NAME
    )

    (
        normalized_recovery_roots,
        recovery_root_commits,
    ) = execution._validate_recovery_roots(
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
                    execution.authority
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

            except Exception as exc:
                raise MonthlySequenceCacheCatalogueV2ExecutionError(
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
                execution.authority
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

        except Exception as exc:
            raise MonthlySequenceCacheCatalogueV2ExecutionError(
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
        / v1_execution.RAW_RESPONSE_NAME
    )

    normalized_completion = []

    for (
        batch_index,
        authoritative_batch,
    ) in enumerate(
        authoritative,
        1,
    ):
        target_values = (
            execution._batch_targets(
                targets,
                batch_index=(
                    batch_index
                ),
                batch_size=(
                    batch_size
                ),
            )
        )

        if (
            authoritative_batch.source_class
            == cache_v2.SOURCE_CLASS_FRESH
        ):
            try:
                transport_evidence = (
                    v1_execution
                    .collect_completed_batch_evidence(
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

                audited = (
                    execution
                    .ordinary_provider
                    .audit_completed_transport_provider(
                        transport_evidence,
                        batch_index=(
                            batch_index
                        ),
                        expected_batch_count=(
                            upstream.expected_batch_count
                        ),
                        expected_fresh_count=(
                            upstream.fresh_acquisition_count
                        ),
                        batch_targets=(
                            target_values
                        ),
                        source_snapshot_id=(
                            upstream.source_snapshot_id
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
                            v1_execution
                            .EXPECTED_DATASETS_ENVIRONMENT_SHA256
                        ),
                    )
                )

                normalized = (
                    execution
                    ._normalize_ordinary(
                        authoritative_batch,
                        audited,
                    )
                )

            except Exception as exc:
                raise MonthlySequenceCacheCatalogueV2ExecutionError(
                    "ordinary authoritative provider audit failed"
                ) from exc

        elif (
            authoritative_batch.source_class
            == cache_v2.SOURCE_CLASS_FRESH_RECOVERY
        ):
            try:
                audited_recovery = (
                    execution
                    .recovery_provider
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

                if (
                    audited_recovery
                    .source_production_commit
                    != source_commit
                ):
                    _fail(
                        "recovery provider source-production "
                        "commit changed"
                    )

                normalized = (
                    execution
                    ._normalize_recovery(
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

            except Exception as exc:
                if isinstance(
                    exc,
                    MonthlySequenceCacheCatalogueV2ExecutionError,
                ):
                    raise

                raise MonthlySequenceCacheCatalogueV2ExecutionError(
                    "recovery authoritative provider audit failed"
                ) from exc

        else:
            _fail(
                "authority resolver returned unknown source class"
            )

        normalized_completion.append(
            (
                authoritative_batch,
                normalized,
            )
        )

    completion_evidence = tuple(
        normalized
        for _, normalized
        in normalized_completion
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
            v1_execution
            .EXPECTED_DATASETS_ENVIRONMENT_SHA256,
        "batches":
            completion_evidence,
    }

    try:
        completion_record = (
            execution
            .audit_sequence_acquisition_completion_v2_record(
                completion_payload_before,
                **contract_kwargs
            )
        )

    except Exception as exc:
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
            "sequence-acquisition completion v2 re-audit failed"
        ) from exc

    completion_payload_after = (
        completion_file.read_bytes()
    )

    if (
        completion_payload_after
        != completion_payload_before
    ):
        _fail(
            "sequence-acquisition completion v2 changed "
            "during re-audit"
        )

    batch_evidence = tuple(
        _cache_batch_evidence(
            authoritative_batch,
            normalized,
        )
        for (
            authoritative_batch,
            normalized,
        )
        in normalized_completion
    )

    if (
        completion_file.read_bytes()
        != completion_payload_before
    ):
        _fail(
            "sequence-acquisition completion v2 changed "
            "during provider evidence loading"
        )

    if (
        len(
            batch_evidence
        )
        != int(
            completion_record[
                "completed_batch_count"
            ]
        )
    ):
        _fail(
            "cache provider population differs from "
            "audited completion-v2"
        )

    return AuditedCompletionV2Context(
        release_id=(
            upstream.release_id
        ),
        source_snapshot_id=(
            upstream.source_snapshot_id
        ),
        stage1_root=(
            upstream.stage1_root
        ),
        completion_payload=(
            completion_payload_before
        ),
        completion_record=dict(
            completion_record
        ),
        batch_evidence=(
            batch_evidence
        ),
        fresh_acquisition_count=(
            upstream.fresh_acquisition_count
        ),
        source_production_commit=(
            source_commit
        ),
        completion_execution_commit=(
            completion_commit
        ),
    )


def _audit_catalogue_payload(
    payload: bytes,
) -> dict[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "catalogue payload must be bytes"
        )

    try:
        value = json.loads(
            payload.decode(
                "ascii"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
            "historical sequence-cache catalogue is invalid"
        ) from exc

    if not isinstance(
        value,
        dict,
    ):
        _fail(
            "historical sequence-cache catalogue "
            "is not an object"
        )

    schema = value.get(
        "schema_version"
    )

    try:
        if (
            schema
            == cache_v1
            .MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA
        ):
            return (
                cache_v1
                .audit_sequence_cache_catalogue(
                    payload
                )
            )

        if (
            schema
            == cache_v2
            .MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
        ):
            return (
                cache_v2
                .audit_sequence_cache_catalogue_v2(
                    payload
                )
            )

    except Exception as exc:
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
            "historical sequence-cache catalogue audit failed"
        ) from exc

    _fail(
        "historical sequence-cache catalogue schema is unsupported"
    )


def discover_catalogue_chain_v2(
    production_root: Path,
    *,
    current_release_id: str,
    include_current: bool = False,
    current_catalogue_path: Path | None = None,
) -> tuple[
    CatalogueChainItemV2,
    ...,
]:
    root = Path(
        production_root
    )

    if not root.is_absolute():
        _fail(
            "production root must be absolute"
        )

    root = _require_real_directory(
        root,
        label="production root",
    )

    current_release = validate_release_id(
        current_release_id
    )

    current_ordinal = release_ordinal(
        current_release
    )

    current_path_resolved = (
        Path(
            current_catalogue_path
        ).resolve()
        if current_catalogue_path
        is not None
        else None
    )

    candidates_by_release = {}

    for release_entry in sorted(
        root.iterdir(),
        key=lambda value:
            value.name,
    ):
        release_name = (
            release_entry.name
        )

        if RELEASE_RE.fullmatch(
            release_name
        ) is None:
            continue

        if (
            release_entry.is_symlink()
            or not release_entry.is_dir()
        ):
            _fail(
                "catalogue history release entry "
                "is not a real directory"
            )

        production = (
            release_entry
            / "production"
        )

        if not os.path.lexists(
            production
        ):
            continue

        production = _require_real_directory(
            production,
            label=(
                "catalogue history production directory"
            ),
        )

        release_candidates = []

        for commit_entry in sorted(
            production.iterdir(),
            key=lambda value:
                value.name,
        ):
            commit_name = (
                commit_entry.name
            )

            if COMMIT_RE.fullmatch(
                commit_name
            ) is None:
                continue

            if (
                commit_entry.is_symlink()
                or not commit_entry.is_dir()
            ):
                _fail(
                    "catalogue history commit entry "
                    "is not a real directory"
                )

            v1_path = (
                commit_entry
                / CATALOGUE_V1_NAME
            )

            v2_path = (
                commit_entry
                / CATALOGUE_V2_NAME
            )

            v1_exists = os.path.lexists(
                v1_path
            )

            v2_exists = os.path.lexists(
                v2_path
            )

            if (
                v1_exists
                and v2_exists
            ):
                _fail(
                    "both cache-v1 and cache-v2 catalogues "
                    "exist for one release/commit"
                )

            if not (
                v1_exists
                or v2_exists
            ):
                continue

            catalogue_path = (
                v2_path
                if v2_exists
                else v1_path
            )

            catalogue_file = _require_regular_file(
                catalogue_path,
                label=(
                    "historical sequence-cache catalogue"
                ),
            )

            payload = (
                catalogue_file.read_bytes()
            )

            record = _audit_catalogue_payload(
                payload
            )

            if (
                record[
                    "release_id"
                ]
                != release_name
            ):
                _fail(
                    "historical catalogue release identity "
                    "differs from directory identity"
                )

            schema = record[
                "schema_version"
            ]

            if (
                schema
                == cache_v1
                .MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA
            ):
                directory_commit = record[
                    "origin_git_commit"
                ]
                chain_cache_commit = record[
                    "origin_git_commit"
                ]

            elif (
                schema
                == cache_v2
                .MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
            ):
                directory_commit = record[
                    "source_production_commit"
                ]
                chain_cache_commit = record[
                    "cache_execution_commit"
                ]

            else:
                raise RuntimeError(
                    "audited catalogue returned "
                    "unsupported schema"
                )

            if (
                directory_commit
                != commit_name
            ):
                _fail(
                    "historical catalogue Git identity "
                    "differs from directory identity"
                )

            release_candidates.append(
                CatalogueChainItemV2(
                    release_id=(
                        release_name
                    ),
                    cache_execution_commit=(
                        chain_cache_commit
                    ),
                    catalogue_path=(
                        catalogue_file
                    ),
                    catalogue_payload=(
                        payload
                    ),
                    catalogue_sha256=(
                        hashlib.sha256(
                            payload
                        ).hexdigest()
                    ),
                    catalogue_record=dict(
                        record
                    ),
                )
            )

        if len(
            release_candidates
        ) > 1:
            _fail(
                "multiple canonical catalogues exist "
                f"for release {release_name}"
            )

        if release_candidates:
            candidates_by_release[
                release_name
            ] = release_candidates[
                0
            ]

    candidates = [
        value
        for _, value
        in sorted(
            candidates_by_release.items(),
            key=lambda item:
                release_ordinal(
                    item[
                        0
                    ]
                ),
        )
    ]

    accepted = []

    for item in candidates:
        ordinal = release_ordinal(
            item.release_id
        )

        if ordinal > current_ordinal:
            _fail(
                "a later canonical catalogue already exists"
            )

        if ordinal == current_ordinal:
            if not include_current:
                _fail(
                    "a canonical catalogue already exists "
                    "for the current release"
                )

            if current_path_resolved is None:
                _fail(
                    "current catalogue path is required "
                    "when including current release"
                )

            if (
                item.catalogue_path.resolve()
                != current_path_resolved
            ):
                _fail(
                    "a competing canonical catalogue exists "
                    "for the current release"
                )

        accepted.append(
            item
        )

    chain = tuple(
        accepted
    )

    if not chain:
        return ()

    first = chain[
        0
    ]

    if (
        first.catalogue_record[
            "catalogue_mode"
        ]
        != cache_v2.GENESIS
    ):
        _fail(
            "catalogue history does not begin with GENESIS"
        )

    for previous, current in zip(
        chain,
        chain[
            1:
        ],
    ):
        if (
            current.catalogue_record[
                "catalogue_mode"
            ]
            != cache_v2.CHAINED
        ):
            _fail(
                "non-genesis catalogue history member "
                "is not CHAINED"
            )

        if (
            current.catalogue_record[
                "previous_catalogue_release_id"
            ]
            != previous.release_id
        ):
            _fail(
                "catalogue history predecessor "
                "release link is broken"
            )

        if (
            current.catalogue_record[
                "previous_catalogue_sha256"
            ]
            != previous.catalogue_sha256
        ):
            _fail(
                "catalogue history predecessor "
                "SHA256 link is broken"
            )

    return chain


def chain_signature(
    chain: Sequence[
        CatalogueChainItemV2
    ],
) -> tuple[
    tuple[
        str,
        str,
        str,
    ],
    ...,
]:
    return tuple(
        (
            item.release_id,
            item.cache_execution_commit,
            item.catalogue_sha256,
        )
        for item
        in chain
    )


def fsync_directory(
    path: Path,
) -> None:
    descriptor = os.open(
        str(
            path
        ),
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
    view = memoryview(
        payload
    )

    written = 0

    while written < len(
        view
    ):
        count = os.write(
            descriptor,
            view[
                written:
            ],
        )

        if count <= 0:
            raise OSError(
                "short write"
            )

        written += count


def write_audited_catalogue_v2(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor: Callable[
        [
            bytes,
        ],
        object,
    ],
    prepublication_check: Callable[
        [],
        None,
    ],
    postpublication_check: Callable[
        [],
        None,
    ],
) -> tuple[
    Path,
    bytes,
]:
    stage1 = _require_real_directory(
        Path(
            stage1_root
        ),
        label="Stage 1 production root",
    )

    final = (
        stage1
        / CATALOGUE_V2_NAME
    )

    temporary = (
        stage1
        / CATALOGUE_V2_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        _fail(
            "sequence-cache catalogue v2 already exists"
        )

    if os.path.lexists(
        temporary
    ):
        _fail(
            "sequence-cache catalogue v2 temporary "
            "artifact already exists"
        )

    descriptor = None

    try:
        descriptor = os.open(
            str(
                temporary
            ),
            (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
            ),
            0o644,
        )

        _write_all(
            descriptor,
            payload,
        )

        os.fsync(
            descriptor
        )

        os.close(
            descriptor
        )

        descriptor = None

        temporary_payload = (
            _require_regular_file(
                temporary,
                label=(
                    "sequence-cache catalogue v2 "
                    "temporary artifact"
                ),
            ).read_bytes()
        )

        if temporary_payload != payload:
            _fail(
                "sequence-cache catalogue v2 temporary "
                "artifact changed after write"
            )

        auditor(
            temporary_payload
        )

        prepublication_check()

        os.replace(
            temporary,
            final,
        )

        fsync_directory(
            stage1
        )

        final_payload = (
            _require_regular_file(
                final,
                label=(
                    "sequence-cache catalogue v2"
                ),
            ).read_bytes()
        )

        if final_payload != payload:
            _fail(
                "sequence-cache catalogue v2 changed "
                "during publication"
            )

        auditor(
            final_payload
        )

        postpublication_check()

        return (
            final.resolve(),
            final_payload,
        )

    except Exception:
        if descriptor is not None:
            os.close(
                descriptor
            )

        if os.path.lexists(
            temporary
        ):
            try:
                temporary.unlink()

            except OSError:
                pass

        raise


def execute_monthly_sequence_cache_catalogue_v2(
    *,
    repo: Path,
    production_root: Path,
    stage1_root: Path,
    sequence_plan_record: Path,
    fresh_target_manifest: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    recovery_roots: Sequence[
        Path
    ] = (),
    package_validator=None,
    completion_context_loader: Callable[
        ...,
        AuditedCompletionV2Context,
    ] = audit_existing_completion_v2,
    preflight: Callable[
        ...,
        None,
    ] = repository_preflight,
) -> SequenceCacheCatalogueV2ExecutionResult:
    source_commit = validate_git_commit(
        source_production_commit,
        label="source production commit",
    )

    completion_commit = validate_git_commit(
        completion_execution_commit,
        label="completion execution commit",
    )

    cache_commit = validate_git_commit(
        cache_execution_commit,
        label="cache execution commit",
    )

    repo_root = _require_real_directory(
        Path(
            repo
        ),
        label="repository root",
    )

    root = Path(
        production_root
    )

    if not root.is_absolute():
        _fail(
            "production root must be absolute"
        )

    root = _require_real_directory(
        root,
        label="production root",
    )

    preflight(
        repo_root,
        cache_execution_commit=(
            cache_commit
        ),
    )

    context = completion_context_loader(
        repo=(
            repo_root
        ),
        production_root=(
            root
        ),
        stage1_root=Path(
            stage1_root
        ),
        sequence_plan_record=Path(
            sequence_plan_record
        ),
        fresh_target_manifest=Path(
            fresh_target_manifest
        ),
        source_production_commit=(
            source_commit
        ),
        completion_execution_commit=(
            completion_commit
        ),
        recovery_roots=tuple(
            Path(
                value
            )
            for value
            in recovery_roots
        ),
        package_validator=(
            package_validator
        ),
    )

    if not isinstance(
        context,
        AuditedCompletionV2Context,
    ):
        _fail(
            "completion context loader returned wrong type"
        )

    if (
        context.source_production_commit
        != source_commit
    ):
        _fail(
            "completion context source-production "
            "commit changed"
        )

    if (
        context.completion_execution_commit
        != completion_commit
    ):
        _fail(
            "completion context execution commit changed"
        )

    stage1 = (
        context.stage1_root.resolve()
    )

    final = (
        stage1
        / CATALOGUE_V2_NAME
    )

    temporary = (
        stage1
        / CATALOGUE_V2_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        _fail(
            "sequence-cache catalogue v2 already exists"
        )

    if os.path.lexists(
        temporary
    ):
        _fail(
            "sequence-cache catalogue v2 temporary "
            "artifact already exists"
        )

    prior_chain = (
        discover_catalogue_chain_v2(
            root,
            current_release_id=(
                context.release_id
            ),
        )
    )

    prior_signature = chain_signature(
        prior_chain
    )

    previous_payload = (
        prior_chain[
            -1
        ].catalogue_payload
        if prior_chain
        else None
    )

    try:
        catalogue_payload = (
            cache_v2
            .serialize_sequence_cache_catalogue_v2(
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                source_production_commit=(
                    source_commit
                ),
                completion_execution_commit=(
                    completion_commit
                ),
                cache_execution_commit=(
                    cache_commit
                ),
                sequence_acquisition_completion_payload=(
                    context.completion_payload
                ),
                current_batches=(
                    context.batch_evidence
                ),
                previous_catalogue_payload=(
                    previous_payload
                ),
            )
        )

        catalogue_record = (
            cache_v2
            .audit_sequence_cache_catalogue_v2(
                catalogue_payload
            )
        )

    except Exception as exc:
        raise MonthlySequenceCacheCatalogueV2ExecutionError(
            "frozen sequence-cache catalogue v2 "
            "contract failed"
        ) from exc

    catalogue_sha = hashlib.sha256(
        catalogue_payload
    ).hexdigest()

    def auditor(
        payload: bytes,
    ) -> object:
        try:
            return (
                cache_v2
                .audit_sequence_cache_catalogue_v2(
                    payload
                )
            )

        except Exception as exc:
            raise MonthlySequenceCacheCatalogueV2ExecutionError(
                "catalogue v2 artifact read-back audit failed"
            ) from exc

    def prepublication_check() -> None:
        observed = (
            discover_catalogue_chain_v2(
                root,
                current_release_id=(
                    context.release_id
                ),
            )
        )

        if (
            chain_signature(
                observed
            )
            != prior_signature
        ):
            _fail(
                "catalogue history changed "
                "before publication"
            )

    expected_post_signature = (
        prior_signature
        + (
            (
                context.release_id,
                cache_commit,
                catalogue_sha,
            ),
        )
    )

    def postpublication_check() -> None:
        observed = (
            discover_catalogue_chain_v2(
                root,
                current_release_id=(
                    context.release_id
                ),
                include_current=True,
                current_catalogue_path=(
                    final
                ),
            )
        )

        if (
            chain_signature(
                observed
            )
            != expected_post_signature
        ):
            _fail(
                "catalogue history changed "
                "during publication"
            )

    (
        final_path,
        final_payload,
    ) = write_audited_catalogue_v2(
        stage1_root=(
            stage1
        ),
        payload=(
            catalogue_payload
        ),
        auditor=(
            auditor
        ),
        prepublication_check=(
            prepublication_check
        ),
        postpublication_check=(
            postpublication_check
        ),
    )

    return SequenceCacheCatalogueV2ExecutionResult(
        release_id=(
            context.release_id
        ),
        source_snapshot_id=(
            context.source_snapshot_id
        ),
        catalogue_path=(
            final_path
        ),
        catalogue_sha256=(
            hashlib.sha256(
                final_payload
            ).hexdigest()
        ),
        catalogue_mode=str(
            catalogue_record[
                "catalogue_mode"
            ]
        ),
        previous_catalogue_release_id=(
            catalogue_record[
                "previous_catalogue_release_id"
            ]
        ),
        previous_catalogue_sha256=(
            catalogue_record[
                "previous_catalogue_sha256"
            ]
        ),
        catalogue_entry_count=int(
            catalogue_record[
                "catalogue_entry_count"
            ]
        ),
        current_acquisition_count=int(
            catalogue_record[
                "current_acquisition_count"
            ]
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one recovery-aware BacSelect "
            "monthly sequence-cache catalogue v2."
        )
    )

    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--production-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--stage1-root",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--sequence-plan-record",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--fresh-target-manifest",
        required=True,
        type=Path,
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
        "--cache-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--recovery-root",
        action="append",
        default=[],
        type=Path,
    )

    args = parser.parse_args()

    result = (
        execute_monthly_sequence_cache_catalogue_v2(
            repo=(
                args.repo
            ),
            production_root=(
                args.production_root
            ),
            stage1_root=(
                args.stage1_root
            ),
            sequence_plan_record=(
                args.sequence_plan_record
            ),
            fresh_target_manifest=(
                args.fresh_target_manifest
            ),
            source_production_commit=(
                args.source_production_commit
            ),
            completion_execution_commit=(
                args.completion_execution_commit
            ),
            cache_execution_commit=(
                args.cache_execution_commit
            ),
            recovery_roots=tuple(
                args.recovery_root
            ),
        )
    )

    print(
        json.dumps(
            {
                "catalogue_entry_count":
                    result.catalogue_entry_count,
                "catalogue_mode":
                    result.catalogue_mode,
                "catalogue_path":
                    str(
                        result.catalogue_path
                    ),
                "catalogue_sha256":
                    result.catalogue_sha256,
                "current_acquisition_count":
                    result.current_acquisition_count,
                "previous_catalogue_release_id":
                    result.previous_catalogue_release_id,
                "previous_catalogue_sha256":
                    result.previous_catalogue_sha256,
                "release_id":
                    result.release_id,
                "source_snapshot_id":
                    result.source_snapshot_id,
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
