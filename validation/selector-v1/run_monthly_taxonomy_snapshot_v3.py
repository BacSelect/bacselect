#!/usr/bin/env python3
"""
Execute BacSelect monthly Stage 7 using a verified local content-addressed view.

Stage 7-v3 preserves the frozen taxonomy acquisition/scientific implementation
while correcting the storage boundary: local filesystem CAS verification is
not durable scholarly archival authority. Durable preservation is deferred to
the later publication/archive gate.
"""

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


STAGE7_V2_WRAPPER_SHA256 = (
    "55e0338f64d792246633b3a821cb59fa"
    "3a7b24423277cb0ab93ee92486b9c2d6"
)

STAGE7_V2_TEST_SHA256 = (
    "12def0ee67fb01e945358cc1286cae75"
    "74121673a66eb62749679fd7603f5d9b"
)

COMPLETION_NAME = (
    "taxonomy-snapshot-completion-v3.json"
)

COMPLETION_TEMP_NAME = (
    ".taxonomy-snapshot-completion-v3.json.tmp"
)

COMPLETION_SCHEMA = (
    "bacselect-monthly-taxonomy-snapshot-completion-v3"
)

COMPLETION_STATUS = (
    "TAXONOMY_SNAPSHOT_EXECUTION_COMPLETE"
)

LOCAL_CAS_STATUS = (
    "LOCAL_CONTENT_ADDRESSABLE_VIEW_VERIFIED"
)

DURABLE_ARCHIVE_BOUNDARY = (
    "DEFERRED_TO_PUBLICATION_GATE"
)

EXPECTED_LOCAL_CAS_VERIFIED_OBJECT_COUNT = 8


class MonthlyTaxonomyV3ExecutionError(
    RuntimeError
):
    """Raised when Stage 7-v3 execution fails closed."""


@dataclass(
    frozen=True,
)
class MonthlyTaxonomyV3ExecutionResult:
    release_id: str
    source_snapshot_id: str
    taxonomy_snapshot_id: str

    stage_path: Path
    completion_path: Path

    record_sha256: str
    completion_sha256: str

    local_cas_manifest_sha256: str
    local_cas_receipt_sha256: str
    local_cas_verified_object_count: int


def _fail(
    message: str,
) -> None:
    raise MonthlyTaxonomyV3ExecutionError(
        message
    )


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
            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def _sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


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
    candidate = Path(
        path
    )

    if (
        candidate.is_symlink()
        or not candidate.is_file()
    ):
        _fail(
            f"{module_name} is not a regular file"
        )

    if (
        _sha256_file(
            candidate
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
            candidate,
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


def load_stage7_v2(
    repo: Path,
) -> ModuleType:
    return _load_module(
        Path(
            repo
        )
        / "validation"
        / "selector-v1"
        / "run_monthly_taxonomy_snapshot_v2.py",
        module_name=(
            "_bacselect_frozen_stage7_v2_for_v3"
        ),
        expected_sha256=(
            STAGE7_V2_WRAPPER_SHA256
        ),
    )


def repository_preflight(
    repo: Path,
    *,
    taxonomy_execution_commit: str,
    expected_wrapper_sha256: str,
    expected_wrapper_test_sha256: str,
) -> tuple[
    Path,
    ModuleType,
]:
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

    stage7_v2 = (
        load_stage7_v2(
            root
        )
    )

    # Reuse the complete frozen dependency preflight
    # from Stage 7-v2, but authenticate the exact
    # frozen v2 wrapper/test identities.
    stage7_v2.repository_preflight(
        root,
        taxonomy_execution_commit=(
            taxonomy_execution_commit
        ),
        expected_wrapper_sha256=(
            STAGE7_V2_WRAPPER_SHA256
        ),
        expected_wrapper_test_sha256=(
            STAGE7_V2_TEST_SHA256
        ),
    )

    wrapper = (
        root
        / "validation/selector-v1/"
          "run_monthly_taxonomy_snapshot_v3.py"
    )

    test = (
        root
        / "tests/"
          "test_run_monthly_taxonomy_snapshot_v3.py"
    )

    if (
        _sha256_file(
            wrapper
        )
        != expected_wrapper_sha256
    ):
        _fail(
            "Stage 7-v3 executor SHA256 mismatch"
        )

    if (
        _sha256_file(
            test
        )
        != expected_wrapper_test_sha256
    ):
        _fail(
            "Stage 7-v3 executor-test SHA256 mismatch"
        )

    return (
        root,
        stage7_v2,
    )


def build_completion_receipt_v3(
    stage7_v2: ModuleType,
    stage7_v1: ModuleType,
    **kwargs,
) -> bytes:
    """
    Reclassify legacy filesystem storage evidence as local CAS verification.

    The frozen support module still uses the historical
    "authoritative_storage_*" compatibility names internally. Stage 7-v3
    deliberately does not expose those names as durable authority.
    """

    base = (
        stage7_v2
        .build_completion_receipt_v2(
            stage7_v1,
            **kwargs,
        )
    )

    record = json.loads(
        base.decode(
            "ascii"
        )
    )

    manifest_sha = record.pop(
        "authoritative_storage_manifest_sha256"
    )

    manifest_key = record.pop(
        "authoritative_storage_manifest_key"
    )

    receipt_sha = record.pop(
        "authoritative_storage_receipt_sha256"
    )

    receipt_key = record.pop(
        "authoritative_storage_receipt_key"
    )

    verified_count = record.pop(
        "authoritative_verified_object_count"
    )

    if (
        verified_count
        != EXPECTED_LOCAL_CAS_VERIFIED_OBJECT_COUNT
    ):
        _fail(
            "legacy CAS verified-object count changed"
        )

    record.update(
        {
            "schema_version":
                COMPLETION_SCHEMA,

            "status":
                COMPLETION_STATUS,

            "local_cas_status":
                LOCAL_CAS_STATUS,

            "local_cas_manifest_sha256":
                manifest_sha,

            "local_cas_manifest_key":
                manifest_key,

            "local_cas_receipt_sha256":
                receipt_sha,

            "local_cas_receipt_key":
                receipt_key,

            "local_cas_verified_object_count":
                verified_count,

            "durable_archive_boundary":
                DURABLE_ARCHIVE_BOUNDARY,
        }
    )

    return (
        stage7_v1
        ._canonical_json(
            record
        )
    )


def audit_completion_receipt_v3(
    stage7_v2: ModuleType,
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
            "taxonomy completion-v3 receipt "
            "must be bytes"
        )

    expected = (
        build_completion_receipt_v3(
            stage7_v2,
            stage7_v1,
            **kwargs,
        )
    )

    if payload != expected:
        _fail(
            "taxonomy completion-v3 receipt changed"
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
            "taxonomy completion-v3 "
            "schema/status changed"
        )

    forbidden = {
        key
        for key in value
        if (
            key.startswith(
                "authoritative_storage_"
            )
            or key
            == "authoritative_verified_object_count"
        )
    }

    if forbidden:
        _fail(
            "taxonomy completion-v3 exposes "
            "legacy authoritative-storage semantics"
        )

    if (
        value.get(
            "local_cas_status"
        )
        != LOCAL_CAS_STATUS
    ):
        _fail(
            "taxonomy completion-v3 local CAS "
            "status changed"
        )

    if (
        value.get(
            "local_cas_verified_object_count"
        )
        != EXPECTED_LOCAL_CAS_VERIFIED_OBJECT_COUNT
    ):
        _fail(
            "taxonomy completion-v3 local CAS "
            "verified-object count changed"
        )

    if (
        value.get(
            "durable_archive_boundary"
        )
        != DURABLE_ARCHIVE_BOUNDARY
    ):
        _fail(
            "taxonomy completion-v3 durable archive "
            "boundary changed"
        )

    return value


def publish_completion_v3(
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
            "taxonomy completion-v3 receipt "
            "already exists"
        )

    if os.path.lexists(
        temporary
    ):
        _fail(
            "taxonomy completion-v3 temporary "
            "artifact already exists"
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
                    "taxonomy completion-v3 receipt"
                ),
            )
            .read_bytes()
        )

        if observed != payload:
            _fail(
                "taxonomy completion-v3 "
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


def execute_monthly_taxonomy_snapshot_v3(
    *,
    repo: Path,
    source_repo: Path,
    production_root: Path,
    stage1_root: Path,
    local_cas_root: Path,
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
) -> MonthlyTaxonomyV3ExecutionResult:
    (
        root,
        stage7_v2,
    ) = repository_preflight(
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

    stage1 = Path(
        stage1_root
    ).resolve()

    stage7_v1 = (
        stage7_v2.load_stage7_v1(
            root
        )
    )

    stage6_v2 = (
        stage7_v2.load_stage6_v2(
            root
        )
    )

    local_cas = (
        stage7_v1
        ._require_absolute_real_directory(
            Path(
                local_cas_root
            ),
            label=(
                "local content-addressed view root"
            ),
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
        stage7_v2
        .authenticate_stage6_v2(
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

    prohibited_paths = (
        (
            stage1
            / stage7_v1.COMPLETION_NAME,
            "legacy taxonomy completion-v1",
        ),
        (
            stage1
            / stage7_v2.COMPLETION_NAME,
            "taxonomy completion-v2",
        ),
        (
            stage1
            / COMPLETION_NAME,
            "taxonomy completion-v3",
        ),
        (
            stage1
            / COMPLETION_TEMP_NAME,
            "taxonomy completion-v3 temporary artifact",
        ),
        (
            partial,
            "partial taxonomy stage",
        ),
        (
            final,
            "canonical taxonomy stage",
        ),
    )

    for (
        path,
        label,
    ) in prohibited_paths:
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
            stage7_v2
            .authenticate_stage6_v2(
                **auth_kwargs
            )
        )

        if (
            observed.identity
            != initial_identity
        ):
            _fail(
                "Stage 1-6 evidence changed "
                "during Stage 7-v3"
            )

    partial.mkdir(
        mode=0o755,
        exist_ok=False,
    )

    wrapper_sha = (
        _sha256_file(
            root
            / "validation/selector-v1/"
              "run_monthly_taxonomy_snapshot_v3.py"
        )
    )

    try:
        # Compatibility note:
        #
        # The frozen support function's parameter and internal schemas use
        # historical "authoritative" terminology. Under Stage 7-v3 this path
        # is explicitly a local verified content-addressed view only.
        support_result = (
            stage7_v1
            .monthly_taxonomy_snapshot_execution
            .execute_monthly_taxonomy_support(
                workspace=(
                    partial
                ),
                authoritative_root=(
                    local_cas
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
        raise MonthlyTaxonomyV3ExecutionError(
            "Stage 7-v3 taxonomy support execution failed"
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
        build_completion_receipt_v3(
            stage7_v2,
            stage7_v1,
            **completion_kwargs,
        )
    )

    completion_path = (
        publish_completion_v3(
            stage1_root=(
                stage1
            ),
            payload=(
                completion_payload
            ),
            auditor=lambda payload:
                audit_completion_receipt_v3(
                    stage7_v2,
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

    return MonthlyTaxonomyV3ExecutionResult(
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
        local_cas_manifest_sha256=(
            support_result
            .authoritative_manifest_sha256
        ),
        local_cas_receipt_sha256=(
            support_result
            .authoritative_receipt_sha256
        ),
        local_cas_verified_object_count=(
            support_result
            .authoritative_verified_object_count
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
        "--local-cas-root",
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
            "real Stage 7-v3 execution requires "
            "explicit authorization"
        )

    result = (
        execute_monthly_taxonomy_snapshot_v3(
            repo=args.repo,
            source_repo=args.source_repo,
            production_root=(
                args.production_root
            ),
            stage1_root=(
                args.stage1_root
            ),
            local_cas_root=(
                args.local_cas_root
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
                args.expected_source_truth_completion_sha256
            ),
            expected_biosample_completion_sha256=(
                args.expected_biosample_completion_sha256
            ),
            expected_chromosome_completion_sha256=(
                args.expected_chromosome_completion_sha256
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
        "PASS | BacSelect monthly taxonomy "
        "snapshot v3 complete"
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
        "local_cas_manifest_sha256="
        f"{result.local_cas_manifest_sha256}"
    )

    print(
        "local_cas_receipt_sha256="
        f"{result.local_cas_receipt_sha256}"
    )

    print(
        "local_cas_verified_object_count="
        f"{result.local_cas_verified_object_count}"
    )

    print(
        "durable_archive_boundary="
        f"{DURABLE_ARCHIVE_BOUNDARY}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
