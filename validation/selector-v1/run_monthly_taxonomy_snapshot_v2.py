#!/usr/bin/env python3
"""Execute recovery-aware BacSelect monthly Stage 7 taxonomy snapshot."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from typing import Mapping


STAGE7_V1_WRAPPER_SHA256 = (
    "e40d626e82992bdfb716e927945d72a7"
    "b337a981cf54942353a43b43e02df5bc"
)

STAGE6_V2_WRAPPER_SHA256 = (
    "df5ba50c5b7f3df2c5a823ddd35d5727"
    "3b61c4a1e1bc145bb34fc7e23a9b7ec8"
)

COMPLETION_NAME = (
    "taxonomy-snapshot-completion-v2.json"
)

COMPLETION_TEMP_NAME = (
    ".taxonomy-snapshot-completion-v2.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-taxonomy-snapshot-completion-v2"
)

COMPLETION_STATUS = (
    "TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE"
)


class MonthlyTaxonomyV2ExecutionError(
    RuntimeError
):
    """Raised when recovery-aware Stage 7 execution fails closed."""


@dataclass(
    frozen=True,
)
class AuthenticatedStage6V2:
    """Authenticated Stage 1 through Stage 6-v2 evidence."""

    support_upstream: object
    stage5_context: object

    stage6_decisions_payload: bytes
    stage6_record_payload: bytes
    stage6_completion_payload: bytes

    stage6_completion_record: Mapping[
        str,
        object,
    ]

    stage6_completion_sha256: str

    identity: tuple[
        object,
        ...,
    ]


@dataclass(
    frozen=True,
)
class MonthlyTaxonomyV2ExecutionResult:
    """Terminal identities for one completed Stage 7-v2 execution."""

    release_id: str
    source_snapshot_id: str
    taxonomy_snapshot_id: str

    stage_path: Path
    completion_path: Path

    record_sha256: str
    completion_sha256: str

    authoritative_manifest_sha256: str
    authoritative_receipt_sha256: str


def _fail(
    message: str,
) -> None:
    raise MonthlyTaxonomyV2ExecutionError(
        message
    )


def _sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def _sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with Path(
        path
    ).open(
        "rb"
    ) as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def _git(
    repo: Path,
    *args: str,
) -> str:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(
                repo
            ),
            *args,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    return result.stdout.strip()


def _load_module(
    path: Path,
    *,
    module_name: str,
    expected_sha256: str,
) -> ModuleType:
    path = Path(
        path
    )

    if (
        path.is_symlink()
        or not path.is_file()
    ):
        _fail(
            f"{module_name} is not a regular file"
        )

    if (
        _sha256_file(
            path
        )
        != expected_sha256
    ):
        _fail(
            f"{module_name} SHA256 mismatch"
        )

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
            f"cannot import {module_name}"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


def load_stage7_v1(
    repo: Path,
) -> ModuleType:
    return _load_module(
        Path(
            repo
        )
        / "validation"
        / "selector-v1"
        / "run_monthly_taxonomy_snapshot.py",
        module_name=(
            "_bacselect_frozen_stage7_v1"
        ),
        expected_sha256=(
            STAGE7_V1_WRAPPER_SHA256
        ),
    )


def load_stage6_v2(
    repo: Path,
) -> ModuleType:
    return _load_module(
        Path(
            repo
        )
        / "validation"
        / "selector-v1"
        / "run_monthly_chromosome_integrity_v2.py",
        module_name=(
            "_bacselect_frozen_stage6_v2_for_stage7"
        ),
        expected_sha256=(
            STAGE6_V2_WRAPPER_SHA256
        ),
    )


def _require_file(
    path: Path,
    *,
    label: str,
) -> Path:
    candidate = Path(
        path
    )

    if (
        candidate.is_symlink()
        or not candidate.is_file()
    ):
        _fail(
            f"{label} is not a regular file"
        )

    return candidate


def _require_exact_stage(
    stage: Path,
    *,
    expected: set[
        str
    ],
) -> Path:
    directory = Path(
        stage
    )

    if (
        directory.is_symlink()
        or not directory.is_dir()
    ):
        _fail(
            "canonical Stage 6 stage "
            "is not a real directory"
        )

    observed = {
        child.name
        for child
        in directory.iterdir()
    }

    if observed != expected:
        _fail(
            "canonical Stage 6 stage "
            "inventory changed"
        )

    return directory


def repository_preflight(
    repo: Path,
    *,
    taxonomy_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> Path:
    root = Path(
        repo
    ).resolve()

    if (
        root.is_symlink()
        or not root.is_dir()
    ):
        _fail(
            "repository root is not a real directory"
        )

    if (
        _git(
            root,
            "rev-parse",
            "HEAD",
        )
        != taxonomy_execution_commit
    ):
        _fail(
            "repository HEAD differs from "
            "taxonomy execution commit"
        )

    if _git(
        root,
        "status",
        "--porcelain",
    ):
        _fail(
            "repository is not clean"
        )

    identities = (
        (
            root
            / "validation/selector-v1/"
            "run_monthly_taxonomy_snapshot.py",
            STAGE7_V1_WRAPPER_SHA256,
            "Stage 7-v1 executor",
        ),
        (
            root
            / "validation/selector-v1/"
            "run_monthly_chromosome_integrity_v2.py",
            STAGE6_V2_WRAPPER_SHA256,
            "Stage 6-v2 executor",
        ),
        (
            root
            / "validation/selector-v1/"
            "run_monthly_taxonomy_snapshot_v2.py",
            expected_wrapper_sha256,
            "Stage 7-v2 executor",
        ),
        (
            root
            / "tests/"
            "test_run_monthly_taxonomy_snapshot_v2.py",
            expected_wrapper_test_sha256,
            "Stage 7-v2 tests",
        ),
    )

    for (
        path,
        expected,
        label,
    ) in identities:
        if (
            path.is_symlink()
            or not path.is_file()
        ):
            _fail(
                f"{label} is not a regular file"
            )

        if (
            _sha256_file(
                path
            )
            != expected
        ):
            _fail(
                f"{label} SHA256 mismatch"
            )

    stage7_v1 = (
        load_stage7_v1(
            root
        )
    )

    stage7_v1.verify_frozen_dependencies(
        root
    )

    load_stage6_v2(
        root
    )

    return root


def authenticate_stage6_v2(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    expected_chromosome_completion_sha256: str,
    stage7_v1: ModuleType,
    stage6_v2: ModuleType,
) -> AuthenticatedStage6V2:
    root = Path(
        repo
    ).resolve()

    stage1 = Path(
        stage1_root
    ).resolve()

    stage6_v1 = (
        stage6_v2
        .load_stage6_v1(
            root
        )
    )

    stage5_v2 = (
        stage6_v2
        .load_stage5_v2(
            root
        )
    )

    stage5_v1 = (
        stage5_v2
        .load_stage5_v1(
            root
        )
    )

    stage4_v2 = (
        stage5_v2
        .load_stage4_v2(
            root
        )
    )

    chromosome_commit = (
        stage4_v2
        .validate_commit(
            chromosome_execution_commit,
            label=(
                "chromosome execution commit"
            ),
        )
    )

    context = (
        stage6_v2
        .load_stage5_context_v2(
            repo=root,
            source_repo=(
                Path(
                    source_repo
                )
            ),
            production_root=(
                Path(
                    production_root
                )
            ),
            stage1_root=stage1,
            source_production_commit=(
                source_production_commit
            ),
            completion_execution_commit=(
                completion_execution_commit
            ),
            cache_execution_commit=(
                cache_execution_commit
            ),
            source_truth_execution_commit=(
                source_truth_execution_commit
            ),
            biosample_execution_commit=(
                biosample_execution_commit
            ),
            expected_completion_sha256=(
                expected_completion_sha256
            ),
            expected_catalogue_sha256=(
                expected_catalogue_sha256
            ),
            expected_source_truth_completion_sha256=(
                expected_source_truth_completion_sha256
            ),
            expected_biosample_completion_sha256=(
                expected_biosample_completion_sha256
            ),
            stage6_v1=stage6_v1,
            stage5_v2=stage5_v2,
        )
    )

    try:
        population = (
            stage6_v1
            .monthly_chromosome_integrity
            .build_monthly_chromosome_population(
                context.decisions_payload,
                expected_biosample_decisions_sha256=(
                    context
                    .completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    chromosome_commit
                ),
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyV2ExecutionError(
            "Stage 6 population reconstruction failed"
        ) from exc

    stage = (
        _require_exact_stage(
            stage1
            / stage6_v1.STAGE_NAME,
            expected={
                stage6_v1.DECISIONS_NAME,
                stage6_v1.RECORD_NAME,
            },
        )
    )

    decisions_payload = (
        _require_file(
            stage
            / stage6_v1.DECISIONS_NAME,
            label="Stage 6 decisions",
        )
        .read_bytes()
    )

    record_payload = (
        _require_file(
            stage
            / stage6_v1.RECORD_NAME,
            label="Stage 6 record",
        )
        .read_bytes()
    )

    completion_payload = (
        _require_file(
            stage1
            / stage6_v2.COMPLETION_NAME,
            label=(
                "Stage 6 completion-v2"
            ),
        )
        .read_bytes()
    )

    completion_sha = (
        _sha256_bytes(
            completion_payload
        )
    )

    if (
        completion_sha
        != expected_chromosome_completion_sha256
    ):
        _fail(
            "Stage 6 completion-v2 SHA256 "
            "differs from authorized identity"
        )

    try:
        decision_rows = tuple(
            stage6_v1
            .monthly_chromosome_integrity
            .audit_monthly_chromosome_decisions(
                decisions_payload
            )
        )

        if tuple(
            row[
                "canonical_genbank_assembly_accession"
            ]
            for row in decision_rows
        ) != (
            population
            .continue_accessions
        ):
            _fail(
                "Stage 6 decision membership differs "
                "from reconstructed Stage 5 CONTINUE "
                "population"
            )

        (
            stage6_v1
            .monthly_chromosome_integrity
            .audit_monthly_chromosome_record(
                record_payload,
                biosample_decisions_payload=(
                    context
                    .decisions_payload
                ),
                expected_biosample_decisions_sha256=(
                    context
                    .completion_record[
                        "decisions_sha256"
                    ]
                ),
                release_id=(
                    context.release_id
                ),
                source_snapshot_id=(
                    context.source_snapshot_id
                ),
                origin_git_commit=(
                    chromosome_commit
                ),
                biosample_record_sha256=(
                    _sha256_bytes(
                        context
                        .record_payload
                    )
                ),
                biosample_completion_sha256=(
                    context
                    .completion_sha256
                ),
                decisions_payload=(
                    decisions_payload
                ),
            )
        )

    except MonthlyTaxonomyV2ExecutionError:
        raise
    except Exception as exc:
        raise MonthlyTaxonomyV2ExecutionError(
            "Stage 6 canonical evidence "
            "authentication failed"
        ) from exc

    triggered_count = sum(
        row[
            "chromosome_integrity_triggered"
        ] == "1"
        for row in decision_rows
    )

    reused_count = sum(
        row[
            "historical_adjudication_reused"
        ] == "1"
        for row in decision_rows
    )

    pass_count = sum(
        row[
            "chromosome_integrity_status"
        ]
        == (
            stage6_v1
            .source_chromosome_integrity
            .PASS
        )
        for row in decision_rows
    )

    excluded_count = sum(
        row[
            "chromosome_integrity_status"
        ]
        == (
            stage6_v1
            .source_chromosome_integrity
            .EXCLUDE
        )
        for row in decision_rows
    )

    unresolved_count = sum(
        row[
            "chromosome_integrity_status"
        ]
        == (
            stage6_v1
            .source_chromosome_integrity
            .UNRESOLVED
        )
        for row in decision_rows
    )

    decisions_sha = (
        _sha256_bytes(
            decisions_payload
        )
    )

    record_sha = (
        _sha256_bytes(
            record_payload
        )
    )

    completion_kwargs = {
        "release_id":
            context.release_id,
        "source_snapshot_id":
            context.source_snapshot_id,
        "biosample_decisions_sha256":
            _sha256_bytes(
                context.decisions_payload
            ),
        "biosample_record_sha256":
            _sha256_bytes(
                context.record_payload
            ),
        "biosample_completion_sha256":
            context.completion_sha256,
        "continue_count":
            len(
                population
                .continue_accessions
            ),
        "continue_accessions_sha256":
            population
            .continue_accessions_sha256,
        "decision_count":
            len(
                decision_rows
            ),
        "triggered_candidate_count":
            triggered_count,
        "nontriggered_candidate_count":
            (
                len(
                    decision_rows
                )
                - triggered_count
            ),
        "historical_adjudication_reuse_count":
            reused_count,
        "pass_count":
            pass_count,
        "excluded_count":
            excluded_count,
        "unresolved_count":
            unresolved_count,
        "decisions_sha256":
            decisions_sha,
        "record_sha256":
            record_sha,
        "stage5_execution":
            stage5_v1,
    }

    stage4 = (
        context
        .stage4_context
    )

    audit_kwargs = {
        "source_production_commit":
            source_production_commit,
        "completion_execution_commit":
            completion_execution_commit,
        "cache_execution_commit":
            cache_execution_commit,
        "source_truth_execution_commit":
            source_truth_execution_commit,
        "biosample_execution_commit":
            biosample_execution_commit,
        "chromosome_execution_commit":
            chromosome_commit,
        "sequence_acquisition_completion_sha256":
            stage4
            .completion_v2_sha256,
        "source_truth_completion_sha256":
            stage4
            .source_truth_completion_sha256,
        **completion_kwargs,
    }

    try:
        completion_record = (
            stage6_v2
            .audit_completion_receipt_v2(
                stage6_v1,
                completion_payload,
                **audit_kwargs,
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyV2ExecutionError(
            "Stage 6 completion-v2 "
            "authentication failed"
        ) from exc

    if (
        completion_record[
            "decisions_sha256"
        ]
        != decisions_sha
    ):
        _fail(
            "Stage 6 decisions SHA changed"
        )

    if (
        completion_record[
            "record_sha256"
        ]
        != record_sha
    ):
        _fail(
            "Stage 6 record SHA changed"
        )

    source_snapshot_payload = (
        _require_file(
            stage1
            / stage7_v1
            .SOURCE_SNAPSHOT_RECORD_NAME,
            label=(
                "Stage 1 source-snapshot record"
            ),
        )
        .read_bytes()
    )

    raw_payload = (
        _require_file(
            stage1
            / stage7_v1
            .RAW_RESPONSE_NAME,
            label=(
                "Stage 1 raw source response"
            ),
        )
        .read_bytes()
    )

    authenticated_source_snapshot_sha = (
        stage4
        .metadata_context
        .source_snapshot_record_sha256
    )

    if (
        _sha256_bytes(
            source_snapshot_payload
        )
        != authenticated_source_snapshot_sha
    ):
        _fail(
            "Stage 1 source-snapshot record "
            "differs from authenticated "
            "Stage 1-5 chain"
        )

    try:
        support_upstream = (
            stage7_v1
            .monthly_taxonomy_snapshot_execution
            .build_authenticated_upstream_context(
                source_snapshot_record_payload=(
                    source_snapshot_payload
                ),
                raw_source_response_payload=(
                    raw_payload
                ),
                expected_release_id=(
                    context.release_id
                ),
                expected_source_snapshot_id=(
                    context.source_snapshot_id
                ),
                expected_source_snapshot_record_sha256=(
                    authenticated_source_snapshot_sha
                ),
                chromosome_integrity_decisions_sha256=(
                    decisions_sha
                ),
                chromosome_integrity_record_sha256=(
                    record_sha
                ),
                chromosome_integrity_completion_sha256=(
                    completion_sha
                ),
                # Frozen Stage 7 support uses this
                # legacy field as Stage 1 origin.
                execution_git_commit=(
                    source_production_commit
                ),
            )
        )

        support_upstream = (
            stage7_v1
            .monthly_taxonomy_snapshot_execution
            .audit_authenticated_upstream_context(
                support_upstream
            )
        )

    except Exception as exc:
        raise MonthlyTaxonomyV2ExecutionError(
            "Stage 7 support upstream binding failed"
        ) from exc

    identity = (
        context.release_id,
        context.source_snapshot_id,
        source_production_commit,
        completion_execution_commit,
        cache_execution_commit,
        source_truth_execution_commit,
        biosample_execution_commit,
        chromosome_commit,
        stage4.completion_v2_sha256,
        stage4.catalogue_sha256,
        stage4.source_truth_completion_sha256,
        context.completion_sha256,
        decisions_sha,
        record_sha,
        completion_sha,
        support_upstream
        .source_snapshot_record_sha256,
        support_upstream
        .source_raw_response_sha256,
    )

    return AuthenticatedStage6V2(
        support_upstream=(
            support_upstream
        ),
        stage5_context=(
            context
        ),
        stage6_decisions_payload=(
            decisions_payload
        ),
        stage6_record_payload=(
            record_payload
        ),
        stage6_completion_payload=(
            completion_payload
        ),
        stage6_completion_record=(
            completion_record
        ),
        stage6_completion_sha256=(
            completion_sha
        ),
        identity=(
            identity
        ),
    )


def build_completion_receipt_v2(
    stage7_v1: ModuleType,
    *,
    upstream: AuthenticatedStage6V2,
    support_result: object,
    validation_wrapper_sha256: str,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    taxonomy_execution_commit: str,
) -> bytes:
    base = (
        stage7_v1
        .build_completion_receipt(
            upstream=(
                upstream
                .support_upstream
            ),
            support_result=(
                support_result
            ),
            validation_wrapper_sha256=(
                validation_wrapper_sha256
            ),
        )
    )

    record = json.loads(
        base.decode(
            "ascii"
        )
    )

    record.pop(
        "execution_git_commit",
        None,
    )

    stage4 = (
        upstream
        .stage5_context
        .stage4_context
    )

    record.update(
        {
            "schema_version":
                COMPLETION_SCHEMA,
            "status":
                COMPLETION_STATUS,

            "source_production_commit":
                source_production_commit,

            # Explicitly identifies the frozen
            # support-layer compatibility field.
            "legacy_support_execution_git_commit":
                source_production_commit,

            "completion_execution_commit":
                completion_execution_commit,
            "cache_execution_commit":
                cache_execution_commit,
            "source_truth_execution_commit":
                source_truth_execution_commit,
            "biosample_execution_commit":
                biosample_execution_commit,
            "chromosome_execution_commit":
                chromosome_execution_commit,
            "taxonomy_execution_commit":
                taxonomy_execution_commit,

            "sequence_acquisition_completion_sha256":
                stage4
                .completion_v2_sha256,
            "sequence_cache_catalogue_sha256":
                stage4
                .catalogue_sha256,
            "source_truth_completion_sha256":
                stage4
                .source_truth_completion_sha256,
            "biosample_completion_sha256":
                upstream
                .stage5_context
                .completion_sha256,
        }
    )

    return (
        stage7_v1
        ._canonical_json(
            record
        )
    )


def audit_completion_receipt_v2(
    stage7_v1: ModuleType,
    payload: bytes,
    **kwargs,
) -> Mapping[
    str,
    object,
]:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "taxonomy completion-v2 "
            "receipt must be bytes"
        )

    expected = (
        build_completion_receipt_v2(
            stage7_v1,
            **kwargs,
        )
    )

    if payload != expected:
        _fail(
            "taxonomy completion-v2 receipt changed"
        )

    value = json.loads(
        payload.decode(
            "ascii"
        )
    )

    if (
        value.get(
            "schema_version"
        )
        != COMPLETION_SCHEMA
        or value.get(
            "status"
        )
        != COMPLETION_STATUS
    ):
        _fail(
            "taxonomy completion-v2 "
            "schema/status changed"
        )

    if "execution_git_commit" in value:
        _fail(
            "taxonomy completion-v2 "
            "reintroduced ambiguous "
            "execution_git_commit"
        )

    if (
        value.get(
            "legacy_support_execution_git_commit"
        )
        != value.get(
            "source_production_commit"
        )
    ):
        _fail(
            "legacy support commit differs "
            "from source production commit"
        )

    return value


def publish_completion_v2(
    *,
    stage1_root: Path,
    payload: bytes,
    auditor,
    stability_check,
    stage7_v1: ModuleType,
) -> Path:
    root = Path(
        stage1_root
    )

    final = (
        root
        / COMPLETION_NAME
    )

    temporary = (
        root
        / COMPLETION_TEMP_NAME
    )

    if os.path.lexists(
        final
    ):
        _fail(
            "taxonomy completion-v2 "
            "receipt already exists"
        )

    if os.path.lexists(
        temporary
    ):
        _fail(
            "taxonomy completion-v2 "
            "temporary artifact already exists"
        )

    stage7_v1._write_no_clobber(
        temporary,
        payload,
    )

    auditor(
        temporary.read_bytes()
    )

    stage7_v1._fsync_directory(
        root
    )

    stability_check()

    try:
        os.link(
            temporary,
            final,
            follow_symlinks=False,
        )

        stage7_v1._fsync_directory(
            root
        )

        observed = (
            stage7_v1
            ._require_regular_file(
                final,
                label=(
                    "taxonomy completion-v2 receipt"
                ),
            )
            .read_bytes()
        )

        if observed != payload:
            _fail(
                "taxonomy completion-v2 "
                "readback changed"
            )

        auditor(
            observed
        )

        stability_check()

    except Exception:
        if os.path.lexists(
            final
        ):
            os.unlink(
                final
            )

            stage7_v1._fsync_directory(
                root
            )

        raise

    os.unlink(
        temporary
    )

    stage7_v1._fsync_directory(
        root
    )

    return final


def execute_monthly_taxonomy_snapshot_v2(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    authoritative_root: Path,
    source_production_commit: str,
    completion_execution_commit: str,
    cache_execution_commit: str,
    source_truth_execution_commit: str,
    biosample_execution_commit: str,
    chromosome_execution_commit: str,
    taxonomy_execution_commit: str,
    expected_completion_sha256: str,
    expected_catalogue_sha256: str,
    expected_source_truth_completion_sha256: str,
    expected_biosample_completion_sha256: str,
    expected_chromosome_completion_sha256: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> MonthlyTaxonomyV2ExecutionResult:
    root = (
        repository_preflight(
            repo,
            taxonomy_execution_commit=(
                taxonomy_execution_commit
            ),
            expected_wrapper_sha256=(
                expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                expected_wrapper_test_sha256
            ),
        )
    )

    stage1 = Path(
        stage1_root
    ).resolve()

    authoritative = Path(
        authoritative_root
    ).resolve()

    stage7_v1 = (
        load_stage7_v1(
            root
        )
    )

    stage6_v2 = (
        load_stage6_v2(
            root
        )
    )

    auth_kwargs = {
        "repo":
            root,
        "source_repo":
            Path(
                source_repo
            ),
        "production_root":
            Path(
                production_root
            ),
        "stage1_root":
            stage1,
        "source_production_commit":
            source_production_commit,
        "completion_execution_commit":
            completion_execution_commit,
        "cache_execution_commit":
            cache_execution_commit,
        "source_truth_execution_commit":
            source_truth_execution_commit,
        "biosample_execution_commit":
            biosample_execution_commit,
        "chromosome_execution_commit":
            chromosome_execution_commit,
        "expected_completion_sha256":
            expected_completion_sha256,
        "expected_catalogue_sha256":
            expected_catalogue_sha256,
        "expected_source_truth_completion_sha256":
            expected_source_truth_completion_sha256,
        "expected_biosample_completion_sha256":
            expected_biosample_completion_sha256,
        "expected_chromosome_completion_sha256":
            expected_chromosome_completion_sha256,
        "stage7_v1":
            stage7_v1,
        "stage6_v2":
            stage6_v2,
    }

    initial = (
        authenticate_stage6_v2(
            **auth_kwargs
        )
    )

    partial = (
        stage1
        / stage7_v1.PARTIAL_NAME
    )

    final = (
        stage1
        / stage7_v1.STAGE_NAME
    )

    legacy_completion = (
        stage1
        / stage7_v1.COMPLETION_NAME
    )

    completion = (
        stage1
        / COMPLETION_NAME
    )

    completion_temp = (
        stage1
        / COMPLETION_TEMP_NAME
    )

    for path, label in (
        (
            partial,
            "partial taxonomy stage",
        ),
        (
            final,
            "canonical taxonomy stage",
        ),
        (
            legacy_completion,
            "legacy taxonomy completion",
        ),
        (
            completion,
            "taxonomy completion-v2",
        ),
        (
            completion_temp,
            "taxonomy completion-v2 temporary artifact",
        ),
    ):
        if os.path.lexists(
            path
        ):
            _fail(
                f"{label} already exists"
            )

    initial_identity = (
        initial.identity
    )

    def stability_check() -> None:
        observed = (
            authenticate_stage6_v2(
                **auth_kwargs
            )
        )

        if (
            observed.identity
            != initial_identity
        ):
            _fail(
                "Stage 1-6 evidence changed "
                "during Stage 7-v2"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    wrapper_sha = (
        _sha256_file(
            root
            / "validation/selector-v1/"
            "run_monthly_taxonomy_snapshot_v2.py"
        )
    )

    try:
        support_result = (
            stage7_v1
            .monthly_taxonomy_snapshot_execution
            .execute_monthly_taxonomy_support(
                workspace=(
                    partial
                ),
                authoritative_root=(
                    authoritative
                ),
                upstream=(
                    initial
                    .support_upstream
                ),
                validation_wrapper_sha256=(
                    wrapper_sha
                ),
                upstream_stability_check=(
                    stability_check
                ),
            )
        )
    except Exception as exc:
        raise MonthlyTaxonomyV2ExecutionError(
            "Stage 7 execution-support layer failed"
        ) from exc

    stage7_v1.publish_stage(
        stage1_root=(
            stage1
        ),
        partial=(
            partial
        ),
        final=(
            final
        ),
        support_result=(
            support_result
        ),
        stability_check=(
            stability_check
        ),
    )

    completion_kwargs = {
        "upstream":
            initial,
        "support_result":
            support_result,
        "validation_wrapper_sha256":
            wrapper_sha,
        "source_production_commit":
            source_production_commit,
        "completion_execution_commit":
            completion_execution_commit,
        "cache_execution_commit":
            cache_execution_commit,
        "source_truth_execution_commit":
            source_truth_execution_commit,
        "biosample_execution_commit":
            biosample_execution_commit,
        "chromosome_execution_commit":
            chromosome_execution_commit,
        "taxonomy_execution_commit":
            taxonomy_execution_commit,
    }

    completion_payload = (
        build_completion_receipt_v2(
            stage7_v1,
            **completion_kwargs,
        )
    )

    completion_path = (
        publish_completion_v2(
            stage1_root=(
                stage1
            ),
            payload=(
                completion_payload
            ),
            auditor=lambda payload:
                audit_completion_receipt_v2(
                    stage7_v1,
                    payload,
                    **completion_kwargs,
                ),
            stability_check=(
                stability_check
            ),
            stage7_v1=(
                stage7_v1
            ),
        )
    )

    return MonthlyTaxonomyV2ExecutionResult(
        release_id=(
            support_result.release_id
        ),
        source_snapshot_id=(
            support_result.source_snapshot_id
        ),
        taxonomy_snapshot_id=(
            support_result.taxonomy_snapshot_id
        ),
        stage_path=(
            final
        ),
        completion_path=(
            completion_path
        ),
        record_sha256=(
            support_result.record_sha256
        ),
        completion_sha256=(
            _sha256_bytes(
                completion_payload
            )
        ),
        authoritative_manifest_sha256=(
            support_result
            .authoritative_manifest_sha256
        ),
        authoritative_receipt_sha256=(
            support_result
            .authoritative_receipt_sha256
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--repo",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--source-repo",
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
        "--authoritative-root",
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
        "--source-truth-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--biosample-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--chromosome-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--taxonomy-execution-commit",
        required=True,
    )

    parser.add_argument(
        "--expected-completion-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-catalogue-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-source-truth-completion-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-biosample-completion-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-chromosome-completion-sha256",
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
        "--authorize-real-execution",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.authorize_real_execution:
        _fail(
            "real Stage 7 execution requires "
            "explicit authorization"
        )

    result = (
        execute_monthly_taxonomy_snapshot_v2(
            repo=(
                args.repo
            ),
            source_repo=(
                args.source_repo
            ),
            production_root=(
                args.production_root
            ),
            stage1_root=(
                args.stage1_root
            ),
            authoritative_root=(
                args.authoritative_root
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
            source_truth_execution_commit=(
                args.source_truth_execution_commit
            ),
            biosample_execution_commit=(
                args.biosample_execution_commit
            ),
            chromosome_execution_commit=(
                args.chromosome_execution_commit
            ),
            taxonomy_execution_commit=(
                args.taxonomy_execution_commit
            ),
            expected_completion_sha256=(
                args.expected_completion_sha256
            ),
            expected_catalogue_sha256=(
                args.expected_catalogue_sha256
            ),
            expected_source_truth_completion_sha256=(
                args
                .expected_source_truth_completion_sha256
            ),
            expected_biosample_completion_sha256=(
                args
                .expected_biosample_completion_sha256
            ),
            expected_chromosome_completion_sha256=(
                args
                .expected_chromosome_completion_sha256
            ),
            expected_wrapper_sha256=(
                args.expected_wrapper_sha256
            ),
            expected_wrapper_test_sha256=(
                args.expected_wrapper_test_sha256
            ),
        )
    )

    print(
        "PASS | BacSelect monthly "
        "taxonomy snapshot v2 complete"
    )

    print(
        f"release_id={result.release_id}"
    )

    print(
        "source_snapshot_id="
        f"{result.source_snapshot_id}"
    )

    print(
        "taxonomy_snapshot_id="
        f"{result.taxonomy_snapshot_id}"
    )

    print(
        f"record_sha256={result.record_sha256}"
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
        "authoritative_manifest_sha256="
        f"{result.authoritative_manifest_sha256}"
    )

    print(
        "authoritative_receipt_sha256="
        f"{result.authoritative_receipt_sha256}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
