"""Synthetic tests for the monthly sequence-acquisition completion executor."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

import pytest

from bacselect.monthly_release_start import (
    canonical_json_bytes as release_json_bytes,
    serialize_release_start_checkpoint,
    serialize_source_snapshot_record,
    source_snapshot_id_from_start,
)
from bacselect.monthly_sequence_acquisition_completion import (
    MonthlySequenceAcquisitionCompletionError,
    audit_sequence_acquisition_completion_record,
)
from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
    FRESH_TARGET_FIELDS,
    MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA,
    NO_VERIFIED_CACHE,
    MonthlyFreshAcquisitionTarget,
    accession_manifest_bytes,
)
from bacselect.monthly_sequence_transport import (
    TARGETED_RETRY_ROUNDS,
    batch_accession_bytes,
    batch_target_manifest_bytes,
)
from bacselect.monthly_sequence_validation import (
    PACKAGE_FILE_FIELDS,
)


WRAPPER_PATH = (
    Path(
        __file__
    ).resolve().parents[
        1
    ]
    / "validation"
    / "selector-v1"
    / "run_monthly_sequence_acquisition_completion.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_monthly_sequence_acquisition_completion",
    WRAPPER_PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

wrapper = importlib.util.module_from_spec(
    SPEC
)

sys.modules[
    SPEC.name
] = wrapper

SPEC.loader.exec_module(
    wrapper
)


REPO = WRAPPER_PATH.parents[
    2
]

STAGE3B = (
    wrapper.load_frozen_stage3b_execution(
        REPO
    )
)


COMMIT = (
    "a" * 40
)

START = (
    "2032-04-01T00:00:00Z"
)

ENVIRONMENT_SHA = (
    wrapper.EXPECTED_DATASETS_ENVIRONMENT_SHA256
)


def sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def accession(
    index: int,
) -> str:
    return (
        f"GCA_{index:09d}.1"
    )


def biosample(
    index: int,
) -> str:
    return (
        f"SAMN{index:08d}"
    )


def targets(
    count: int,
) -> tuple[
    MonthlyFreshAcquisitionTarget,
    ...,
]:
    return tuple(
        MonthlyFreshAcquisitionTarget(
            canonical_genbank_assembly_accession=(
                accession(
                    index
                )
            ),
            source_biosample=(
                biosample(
                    index
                )
            ),
            acquisition_reason=(
                NO_VERIFIED_CACHE
            ),
        )
        for index in range(
            1,
            count
            + 1,
        )
    )


def make_stage2(
    stage1_root: Path,
    *,
    snapshot_id: str,
    snapshot_sha: str,
    count: int,
):
    values = targets(
        count
    )

    lines = [
        "\t".join(
            FRESH_TARGET_FIELDS
        )
        + "\n"
    ]

    for target in values:
        lines.append(
            f"{target.canonical_genbank_assembly_accession}\t"
            f"{target.source_biosample}\t"
            f"{target.acquisition_reason}\n"
        )

    manifest = "".join(
        lines
    ).encode(
        "ascii"
    )

    accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target in values
    )

    fresh_sha = sha256_bytes(
        accession_manifest_bytes(
            accessions
        )
    )

    empty_sha = sha256_bytes(
        accession_manifest_bytes(
            ()
        )
    )

    batch_count = (
        (
            count
            + FRESH_BATCH_SIZE
            - 1
        )
        // FRESH_BATCH_SIZE
        if count
        else 0
    )

    record = {
        "cache_reuse_accessions_sha256":
            empty_sha,
        "cache_reuse_count":
            0,
        "fresh_acquisition_accessions_sha256":
            fresh_sha,
        "fresh_acquisition_count":
            count,
        "fresh_acquisition_reason_counts":
            (
                {
                    NO_VERIFIED_CACHE:
                        count,
                }
                if count
                else {}
            ),
        "fresh_batch_count":
            batch_count,
        "fresh_batch_size":
            FRESH_BATCH_SIZE,
        "fresh_target_manifest_sha256":
            sha256_bytes(
                manifest
            ),
        "retained_accessions_sha256":
            fresh_sha,
        "retained_count":
            count,
        "schema_version":
            MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA,
        "source_snapshot_id":
            snapshot_id,
        "source_snapshot_record_sha256":
            snapshot_sha,
    }

    plan_payload = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    plan_path = (
        stage1_root
        / "sequence-plan-record.json"
    )

    manifest_path = (
        stage1_root
        / "fresh-target-manifest.tsv"
    )

    plan_path.write_bytes(
        plan_payload
    )

    manifest_path.write_bytes(
        manifest
    )

    return {
        "plan_path":
            plan_path,
        "manifest_path":
            manifest_path,
        "plan_payload":
            plan_payload,
        "manifest_payload":
            manifest,
        "targets":
            values,
        "batch_count":
            batch_count,
    }


def make_upstream(
    tmp_path: Path,
    *,
    count: int,
):
    production_root = (
        tmp_path
        / "production-root"
    )

    release_id = (
        "2032.04"
    )

    stage1_root = (
        production_root
        / release_id
        / "production"
        / COMMIT
    )

    stage1_root.mkdir(
        parents=True
    )

    checkpoint = (
        serialize_release_start_checkpoint(
            snapshot_start_utc=(
                START
            ),
            expected_git_commit=(
                COMMIT
            ),
            ncbi_datasets_version=(
                wrapper.EXPECTED_DATASETS_VERSION
            ),
            ncbi_datasets_environment_sha256=(
                ENVIRONMENT_SHA
            ),
        )
    )

    raw = (
        b'{"synthetic":"source"}\n'
    )

    snapshot = (
        serialize_source_snapshot_record(
            release_start_checkpoint=(
                checkpoint
            ),
            source_query_started_utc=(
                "2032-04-01T00:00:01Z"
            ),
            source_query_completed_utc=(
                "2032-04-01T00:00:02Z"
            ),
            source_query_command=(
                "datasets",
                "summary",
                "genome",
            ),
            raw_response=(
                raw
            ),
        )
    )

    (
        stage1_root
        / wrapper.CHECKPOINT_NAME
    ).write_bytes(
        checkpoint
    )

    (
        stage1_root
        / wrapper.RAW_RESPONSE_NAME
    ).write_bytes(
        raw
    )

    (
        stage1_root
        / wrapper.SOURCE_SNAPSHOT_RECORD_NAME
    ).write_bytes(
        snapshot
    )

    snapshot_id = (
        source_snapshot_id_from_start(
            START
        )
    )

    snapshot_sha = (
        sha256_bytes(
            snapshot
        )
    )

    stage2 = make_stage2(
        stage1_root,
        snapshot_id=(
            snapshot_id
        ),
        snapshot_sha=(
            snapshot_sha
        ),
        count=count,
    )

    return {
        "production_root":
            production_root.resolve(),
        "stage1_root":
            stage1_root.resolve(),
        "snapshot_id":
            snapshot_id,
        "snapshot_sha":
            snapshot_sha,
        **stage2,
    }


def transport_json(
    value,
) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def package_manifest(
    package: Path,
) -> bytes:
    rows = (
        wrapper.package_file_manifest(
            package
        )
    )

    return STAGE3B._serialize_tsv(
        rows,
        PACKAGE_FILE_FIELDS,
    )


def synthetic_package_validator(
    package: Path,
    batch_targets,
):
    candidate_rows = []

    component_rows = []

    for target in batch_targets:
        candidate = {
            field:
                "synthetic"
            for field in wrapper.CANDIDATE_AUDIT_FIELDS
        }

        candidate[
            "canonical_genbank_assembly_accession"
        ] = (
            target.canonical_genbank_assembly_accession
        )

        candidate[
            "expected_biosample"
        ] = (
            target.source_biosample
        )

        candidate[
            "observed_biosample"
        ] = (
            target.source_biosample
        )

        candidate_rows.append(
            candidate
        )

        component = {
            field:
                "synthetic"
            for field in wrapper.COMPONENT_AUDIT_FIELDS
        }

        component[
            "canonical_genbank_assembly_accession"
        ] = (
            target.canonical_genbank_assembly_accession
        )

        component[
            "component_genbank_accession"
        ] = (
            target.canonical_genbank_assembly_accession
        )

        component_rows.append(
            component
        )

    return wrapper.MonthlyValidatedPackage(
        candidate_rows=tuple(
            candidate_rows
        ),
        component_rows=tuple(
            component_rows
        ),
        package_file_rows=(
            wrapper.package_file_manifest(
                package
            )
        ),
        assembly_data_report=(
            package
            / "synthetic-assembly-data-report.jsonl"
        ),
    )

def make_batch(
    paths,
    *,
    batch_index: int = 1,
):
    values = paths[
        "targets"
    ]

    start = (
        batch_index
        - 1
    ) * FRESH_BATCH_SIZE

    stop = min(
        start
        + FRESH_BATCH_SIZE,
        len(
            values
        ),
    )

    batch_targets = values[
        start:
        stop
    ]

    sequence_root = (
        paths[
            "stage1_root"
        ]
        / wrapper.SEQUENCE_ROOT_NAME
    )

    sequence_root.mkdir(
        exist_ok=True
    )

    batch_id = (
        f"batch-{batch_index:05d}"
    )

    batch = (
        sequence_root
        / batch_id
    )

    batch.mkdir()

    targets_payload = (
        batch_target_manifest_bytes(
            batch_targets
        )
    )

    accessions_payload = (
        batch_accession_bytes(
            batch_targets
        )
    )

    (
        batch
        / wrapper.BATCH_TARGETS_NAME
    ).write_bytes(
        targets_payload
    )

    (
        batch
        / wrapper.ACCESSIONS_NAME
    ).write_bytes(
        accessions_payload
    )

    attempt_payload = (
        b'{"synthetic":"attempt"}\n'
    )

    (
        batch
        / wrapper.ATTEMPT_ORIGIN_NAME
    ).write_bytes(
        attempt_payload
    )

    dehydrated_payload = (
        b"synthetic-dehydrated-zip\n"
    )

    (
        batch
        / wrapper.DEHYDRATED_ZIP_NAME
    ).write_bytes(
        dehydrated_payload
    )

    package = (
        batch
        / wrapper.PACKAGE_NAME
    )

    fetch = (
        package
        / "ncbi_dataset"
        / "fetch.txt"
    )

    fetch.parent.mkdir(
        parents=True
    )

    fetch_lines = []

    for target in batch_targets:
        accession_value = (
            target.canonical_genbank_assembly_accession
        )

        relative = (
            f"data/{accession_value}/payload.bin"
        )

        payload_path = (
            package
            / "ncbi_dataset"
            / relative
        )

        payload_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = (
            f"payload:{accession_value}\n"
        ).encode(
            "utf-8"
        )

        payload_path.write_bytes(
            payload
        )

        fetch_lines.append(
            "https://example.invalid/"
            f"{accession_value}\t"
            f"{len(payload)}\t"
            f"{relative}\n"
        )

    fetch.write_text(
        "".join(
            fetch_lines
        ),
        encoding="utf-8",
    )

    validated = synthetic_package_validator(
        package,
        batch_targets,
    )

    candidate_payload = (
        STAGE3B._serialize_tsv(
            validated.candidate_rows,
            wrapper.CANDIDATE_AUDIT_FIELDS,
        )
    )

    component_payload = (
        STAGE3B._serialize_tsv(
            validated.component_rows,
            wrapper.COMPONENT_AUDIT_FIELDS,
        )
    )

    package_files_payload = (
        STAGE3B._serialize_tsv(
            validated.package_file_rows,
            PACKAGE_FILE_FIELDS,
        )
    )

    (
        batch
        / wrapper.CANDIDATE_AUDIT_NAME
    ).write_bytes(
        candidate_payload
    )

    (
        batch
        / wrapper.COMPONENT_AUDIT_NAME
    ).write_bytes(
        component_payload
    )

    package_files_path = (
        batch
        / wrapper.PACKAGE_FILES_NAME
    )

    package_files_path.write_bytes(
        package_files_payload
    )

    summary = {
        "accessions_sha256":
            sha256_bytes(
                accessions_payload
            ),
        "attempt_origin_sha256":
            sha256_bytes(
                attempt_payload
            ),
        "batch_count":
            paths[
                "batch_count"
            ],
        "batch_index":
            batch_index,
        "batch_size":
            FRESH_BATCH_SIZE,
        "batch_target_manifest_sha256":
            sha256_bytes(
                targets_payload
            ),
        "broad_rehydrate_exit_code":
            0,
        "candidate_records":
            len(
                batch_targets
            ),
        "candidate_sequence_audit_sha256":
            sha256_bytes(
                candidate_payload
            ),
        "component_records":
            len(
                batch_targets
            ),
        "component_sequence_audit_sha256":
            sha256_bytes(
                component_payload
            ),
        "datasets_version":
            wrapper.EXPECTED_DATASETS_VERSION,
        "dehydrated_zip_sha256":
            sha256_bytes(
                dehydrated_payload
            ),
        "environment_explicit_sha256":
            ENVIRONMENT_SHA,
        "execution_completed_at_utc":
            "2032-04-01T01:00:00Z",
        "fetch_entries":
            len(
                batch_targets
            ),
        "fetch_txt_sha256":
            wrapper.sha256_file(
                fetch
            ),
        "first_accession":
            batch_targets[
                0
            ].canonical_genbank_assembly_accession,
        "full_target_count":
            len(
                values
            ),
        "initial_unresolved_accessions":
            0,
        "last_accession":
            batch_targets[
                -1
            ].canonical_genbank_assembly_accession,
        "origin_git_commit":
            COMMIT,
        "package_files":
            len(
                tuple(
                    item
                    for item in package.rglob(
                        "*"
                    )
                    if item.is_file()
                )
            ),
        "package_files_sha256":
            sha256_bytes(
                package_files_payload
            ),
        "requested_accessions":
            len(
                batch_targets
            ),
        "result":
            "PASS",
        "schema":
            "bacselect-monthly-sequence-transport-summary-v1",
        "source_snapshot_id":
            paths[
                "snapshot_id"
            ],
        "source_snapshot_record_sha256":
            paths[
                "snapshot_sha"
            ],
        "stage2_fresh_target_manifest_sha256":
            sha256_bytes(
                paths[
                    "manifest_payload"
                ]
            ),
        "stage2_sequence_plan_record_sha256":
            sha256_bytes(
                paths[
                    "plan_payload"
                ]
            ),
        "targeted_retry_events":
            [],
        "targeted_retry_rounds":
            TARGETED_RETRY_ROUNDS,
    }

    summary_payload = (
        transport_json(
            summary
        )
    )

    (
        batch
        / wrapper.SUMMARY_NAME
    ).write_bytes(
        summary_payload
    )

    return batch


def execute(
    paths,
):
    return (
        wrapper.execute_monthly_sequence_acquisition_completion(
            repo=(
                REPO
            ),
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ].resolve()
            ),
            fresh_target_manifest=(
                paths[
                    "manifest_path"
                ].resolve()
            ),
            execution_commit=(
                COMMIT
            ),
            package_validator=(
                synthetic_package_validator
            ),
        )
    )

def test_repository_preflight_accepts_exact_pushed_clean_repo(
    tmp_path,
):
    repo = tmp_path.resolve()

    wrapper_sha = "f" * 64
    wrapper_test_sha = "e" * 64

    fixed = {
        wrapper.SOURCE_ELIGIBILITY_RELATIVE:
            wrapper.EXPECTED_SOURCE_ELIGIBILITY_SHA256,
        wrapper.RELEASE_START_RELATIVE:
            wrapper.EXPECTED_RELEASE_START_SHA256,
        wrapper.SEQUENCE_PLAN_RELATIVE:
            wrapper.EXPECTED_SEQUENCE_PLAN_SHA256,
        wrapper.SEQUENCE_TRANSPORT_RELATIVE:
            wrapper.EXPECTED_SEQUENCE_TRANSPORT_SHA256,
        wrapper.SEQUENCE_VALIDATION_RELATIVE:
            wrapper.EXPECTED_SEQUENCE_VALIDATION_SHA256,
        wrapper.STAGE3B_WRAPPER_RELATIVE:
            wrapper.EXPECTED_STAGE3B_WRAPPER_SHA256,
        wrapper.STAGE3B_WRAPPER_TEST_RELATIVE:
            wrapper.EXPECTED_STAGE3B_WRAPPER_TEST_SHA256,
        wrapper.COMPLETION_CORE_RELATIVE:
            wrapper.EXPECTED_COMPLETION_CORE_SHA256,
        wrapper.COMPLETION_CORE_TEST_RELATIVE:
            wrapper.EXPECTED_COMPLETION_CORE_TEST_SHA256,
        wrapper.COMPLETION_METHOD_RELATIVE:
            wrapper.EXPECTED_COMPLETION_METHOD_SHA256,
        wrapper.EXECUTION_METHOD_RELATIVE:
            wrapper.EXPECTED_EXECUTION_METHOD_SHA256,
        wrapper.ENVIRONMENT_RELATIVE:
            wrapper.EXPECTED_DATASETS_ENVIRONMENT_SHA256,
    }

    def git_reader(
        root,
        *args,
    ):
        assert root == repo

        if args in (
            (
                "rev-parse",
                "HEAD",
            ),
            (
                "rev-parse",
                "origin/main",
            ),
        ):
            return COMMIT

        if args == (
            "status",
            "--porcelain",
        ):
            return ""

        raise AssertionError(
            args
        )

    def file_reader(
        path,
    ):
        resolved = Path(
            path
        ).resolve()

        if resolved == Path(
            wrapper.__file__
        ).resolve():
            return wrapper_sha

        if resolved == (
            repo
            / wrapper.WRAPPER_TEST_RELATIVE
        ).resolve():
            return wrapper_test_sha

        for relative, expected in fixed.items():
            if resolved == (
                repo
                / relative
            ).resolve():
                return expected

        raise AssertionError(
            resolved
        )

    wrapper.repository_preflight(
        repo,
        expected_commit=(
            COMMIT
        ),
        expected_wrapper_sha256=(
            wrapper_sha
        ),
        expected_wrapper_test_sha256=(
            wrapper_test_sha
        ),
        git_reader=(
            git_reader
        ),
        file_sha256_reader=(
            file_reader
        ),
    )


def test_repository_preflight_rejects_dirty_tree(
    tmp_path,
):
    def git_reader(
        repo,
        *args,
    ):
        del repo

        if args in (
            (
                "rev-parse",
                "HEAD",
            ),
            (
                "rev-parse",
                "origin/main",
            ),
        ):
            return COMMIT

        if args == (
            "status",
            "--porcelain",
        ):
            return "?? changed"

        raise AssertionError(
            args
        )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="working tree",
    ):
        wrapper.repository_preflight(
            tmp_path,
            expected_commit=(
                COMMIT
            ),
            expected_wrapper_sha256=(
                "f" * 64
            ),
            expected_wrapper_test_sha256=(
                "e" * 64
            ),
            git_reader=(
                git_reader
            ),
            file_sha256_reader=lambda path:
                "0" * 64,
        )


def test_load_upstream_contract_accepts_zero_fresh(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    upstream = (
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ].resolve()
            ),
            fresh_target_manifest=(
                paths[
                    "manifest_path"
                ].resolve()
            ),
            expected_commit=(
                COMMIT
            ),
        )
    )

    assert (
        upstream.fresh_acquisition_count
        == 0
    )

    assert (
        upstream.expected_batch_count
        == 0
    )


def test_load_upstream_contract_rejects_wrong_stage1_identity(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    wrong = (
        tmp_path
        / "wrong"
    )

    wrong.mkdir()

    for name in (
        wrapper.CHECKPOINT_NAME,
        wrapper.RAW_RESPONSE_NAME,
        wrapper.SOURCE_SNAPSHOT_RECORD_NAME,
    ):
        (
            wrong
            / name
        ).write_bytes(
            (
                paths[
                    "stage1_root"
                ]
                / name
            ).read_bytes()
        )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="production root does not match",
    ):
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                wrong.resolve()
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ].resolve()
            ),
            fresh_target_manifest=(
                paths[
                    "manifest_path"
                ].resolve()
            ),
            expected_commit=(
                COMMIT
            ),
        )


def test_discovery_allows_absent_sequence_root_for_zero(
    tmp_path,
):
    assert (
        wrapper.discover_sequence_entries(
            tmp_path
        )
        == (
            (),
            (),
            (),
        )
    )


def test_discovery_rejects_dangling_sequence_root_symlink(
    tmp_path,
):
    target = (
        tmp_path
        / "missing-sequence-root"
    )

    (
        tmp_path
        / wrapper.SEQUENCE_ROOT_NAME
    ).symlink_to(
        target,
        target_is_directory=True,
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="not a real directory",
    ):
        wrapper.discover_sequence_entries(
            tmp_path
        )


def test_discovery_classifies_complete_batch(
    tmp_path,
):
    root = (
        tmp_path
        / wrapper.SEQUENCE_ROOT_NAME
    )

    root.mkdir()

    (
        root
        / "batch-00001"
    ).mkdir()

    assert (
        wrapper.discover_sequence_entries(
            tmp_path
        )
        == (
            (
                "batch-00001",
            ),
            (),
            (),
        )
    )


def test_discovery_classifies_partial_and_unexpected(
    tmp_path,
):
    root = (
        tmp_path
        / wrapper.SEQUENCE_ROOT_NAME
    )

    root.mkdir()

    (
        root
        / "batch-00001.partial"
    ).mkdir()

    (
        root
        / "surprise"
    ).write_text(
        "x",
        encoding="utf-8",
    )

    assert (
        wrapper.discover_sequence_entries(
            tmp_path
        )
        == (
            (),
            (
                "batch-00001.partial",
            ),
            (
                "surprise",
            ),
        )
    )


def test_collect_batch_evidence_rehashes_complete_batch(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    evidence = (
        wrapper.collect_completed_batch_evidence(
            batch,
            batch_targets=(
                paths[
                    "targets"
                ]
            ),
            package_validator=(
                synthetic_package_validator
            ),
            tsv_serializer=(
                STAGE3B._serialize_tsv
            ),
        )
    )

    assert evidence.batch_id == "batch-00001"

    assert len(
        evidence.package_file_observations
    ) == 2

    assert (
        evidence.observed_fetch_txt_sha256
        == wrapper.sha256_file(
            batch
            / "package"
            / "ncbi_dataset"
            / "fetch.txt"
        )
    )


def test_collect_batch_evidence_rejects_missing_critical_artifact(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    (
        batch
        / wrapper.CANDIDATE_AUDIT_NAME
    ).unlink()

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="missing candidate-sequence audit",
    ):
        wrapper.collect_completed_batch_evidence(
            batch,
            batch_targets=(
                paths[
                    "targets"
                ]
            ),
            package_validator=(
                synthetic_package_validator
            ),
            tsv_serializer=(
                STAGE3B._serialize_tsv
            ),
        )


def test_collect_batch_evidence_rejects_package_symlink(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    package = (
        batch
        / wrapper.PACKAGE_NAME
    )

    target = (
        package
        / "real.txt"
    )

    target.write_text(
        "real",
        encoding="utf-8",
    )

    link = (
        package
        / "link.txt"
    )

    link.symlink_to(
        target
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="symbolic-link",
    ):
        wrapper.collect_completed_batch_evidence(
            batch,
            batch_targets=(
                paths[
                    "targets"
                ]
            ),
            package_validator=(
                synthetic_package_validator
            ),
            tsv_serializer=(
                STAGE3B._serialize_tsv
            ),
        )


def test_execute_zero_fresh_writes_completion_without_sequence_root(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    result = execute(
        paths
    )

    assert (
        result.completed_batch_count
        == 0
    )

    assert (
        result.fresh_acquisition_count
        == 0
    )

    assert result.completion_path.is_file()

    payload = (
        result.completion_path.read_bytes()
    )

    record = json.loads(
        payload
    )

    assert record[
        "completed_batch_count"
    ] == 0

    assert record[
        "completed_accession_count"
    ] == 0


def test_execute_one_batch_writes_completion(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    make_batch(
        paths
    )

    result = execute(
        paths
    )

    assert (
        result.completed_batch_count
        == 1
    )

    assert (
        stat.S_IMODE(
            result.completion_path.stat().st_mode
        )
        == 0o644
    )

    assert (
        result.completion_sha256
        == wrapper.sha256_file(
            result.completion_path
        )
    )


def test_execute_rejects_missing_expected_batch(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="discovery is incomplete",
    ):
        execute(
            paths
        )

    assert not (
        paths[
            "stage1_root"
        ]
        / wrapper.COMPLETION_NAME
    ).exists()


def test_execute_rejects_partial_batch(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    root = (
        paths[
            "stage1_root"
        ]
        / wrapper.SEQUENCE_ROOT_NAME
    )

    root.mkdir()

    (
        root
        / "batch-00001.partial"
    ).mkdir()

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="partial/unexpected",
    ):
        execute(
            paths
        )


def test_execute_rejects_unexpected_sequence_entry(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    root = (
        paths[
            "stage1_root"
        ]
        / wrapper.SEQUENCE_ROOT_NAME
    )

    root.mkdir()

    (
        root
        / "unexpected.txt"
    ).write_text(
        "x",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="partial/unexpected",
    ):
        execute(
            paths
        )


def test_execute_rejects_tampered_dehydrated_zip(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    (
        batch
        / wrapper.DEHYDRATED_ZIP_NAME
    ).write_bytes(
        b"changed\n"
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="frozen sequence-acquisition completion contract failed",
    ):
        execute(
            paths
        )


def test_execute_rejects_tampered_package_file(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    payload_file = next(
        path
        for path in (
            batch
            / wrapper.PACKAGE_NAME
        ).rglob(
            "payload.bin"
        )
    )

    payload_file.write_bytes(
        b"changed\n"
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="persisted package-files manifest differs",
    ):
        execute(
            paths
        )


def test_execute_rejects_extra_package_file(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    (
        batch
        / wrapper.PACKAGE_NAME
        / "extra.txt"
    ).write_text(
        "extra",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="persisted package-files manifest differs",
    ):
        execute(
            paths
        )


def test_collect_batch_evidence_rejects_package_change_during_stage3a(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    def mutating_validator(
        package,
        batch_targets,
    ):
        result = synthetic_package_validator(
            package,
            batch_targets,
        )

        (
            package
            / "late-mutation.txt"
        ).write_text(
            "changed during validation",
            encoding="utf-8",
        )

        return result

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="package filesystem changed during Stage 3A revalidation",
    ):
        wrapper.collect_completed_batch_evidence(
            batch,
            batch_targets=(
                paths[
                    "targets"
                ]
            ),
            package_validator=(
                mutating_validator
            ),
            tsv_serializer=(
                STAGE3B._serialize_tsv
            ),
        )


def test_collect_batch_evidence_rejects_audit_change_during_stage3a(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    candidate = (
        batch
        / wrapper.CANDIDATE_AUDIT_NAME
    )

    def mutating_validator(
        package,
        batch_targets,
    ):
        result = synthetic_package_validator(
            package,
            batch_targets,
        )

        candidate.write_bytes(
            candidate.read_bytes()
            + b"changed-during-validation\n"
        )

        return result

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="candidate-sequence audit changed during Stage 3A revalidation",
    ):
        wrapper.collect_completed_batch_evidence(
            batch,
            batch_targets=(
                paths[
                    "targets"
                ]
            ),
            package_validator=(
                mutating_validator
            ),
            tsv_serializer=(
                STAGE3B._serialize_tsv
            ),
        )


def test_completion_publication_never_overwrites_concurrent_final(
    tmp_path,
    monkeypatch,
):
    stage1 = tmp_path.resolve()

    final = (
        stage1
        / wrapper.COMPLETION_NAME
    )

    temporary = (
        stage1
        / wrapper.COMPLETION_TEMP_NAME
    )

    foreign_payload = (
        b"foreign-completion\n"
    )

    real_link = os.link

    def racing_link(
        source,
        destination,
        *,
        follow_symlinks=True,
    ):
        assert Path(
            source
        ) == temporary

        assert Path(
            destination
        ) == final

        final.write_bytes(
            foreign_payload
        )

        return real_link(
            source,
            destination,
            follow_symlinks=(
                follow_symlinks
            ),
        )

    monkeypatch.setattr(
        os,
        "link",
        racing_link,
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="appeared before canonical publication",
    ):
        wrapper.write_audited_completion(
            stage1_root=(
                stage1
            ),
            payload=(
                b'{"completion":"synthetic"}\n'
            ),
            auditor=lambda payload:
                payload,
        )

    assert (
        final.read_bytes()
        == foreign_payload
    )

    assert temporary.is_file()


def test_execute_refuses_dangling_completion_symlink(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    completion = (
        paths[
            "stage1_root"
        ]
        / wrapper.COMPLETION_NAME
    )

    completion.symlink_to(
        paths[
            "stage1_root"
        ]
        / "missing-completion-target"
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="completion artifact already exists",
    ):
        execute(
            paths
        )

    assert completion.is_symlink()


def test_execute_refuses_dangling_completion_temporary_symlink(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    temporary = (
        paths[
            "stage1_root"
        ]
        / wrapper.COMPLETION_TEMP_NAME
    )

    temporary.symlink_to(
        paths[
            "stage1_root"
        ]
        / "missing-temporary-target"
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="temporary artifact already exists",
    ):
        execute(
            paths
        )

    assert temporary.is_symlink()


def test_execute_refuses_existing_completion_record(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    completion = (
        paths[
            "stage1_root"
        ]
        / wrapper.COMPLETION_NAME
    )

    completion.write_text(
        "existing\n",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="already exists",
    ):
        execute(
            paths
        )

    assert (
        completion.read_text(
            encoding="utf-8"
        )
        == "existing\n"
    )


def test_completion_temporary_file_blocks_execution(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    temporary = (
        paths[
            "stage1_root"
        ]
        / wrapper.COMPLETION_TEMP_NAME
    )

    temporary.write_text(
        "inspect-me\n",
        encoding="utf-8",
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="temporary artifact already exists",
    ):
        execute(
            paths
        )


def test_load_upstream_contract_rejects_stage2_symlink(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=0,
    )

    original = (
        paths[
            "manifest_path"
        ]
    )

    real = original.with_name(
        "fresh-target-manifest.real.tsv"
    )

    original.rename(
        real
    )

    original.symlink_to(
        real
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="must not be a symbolic link",
    ):
        wrapper.load_upstream_contract(
            production_root=(
                paths[
                    "production_root"
                ]
            ),
            stage1_root=(
                paths[
                    "stage1_root"
                ]
            ),
            sequence_plan_record=(
                paths[
                    "plan_path"
                ].resolve()
            ),
            fresh_target_manifest=(
                original
            ),
            expected_commit=(
                COMMIT
            ),
        )


def test_execute_rejects_consistently_rewritten_candidate_audit(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    candidate = (
        batch
        / wrapper.CANDIDATE_AUDIT_NAME
    )

    candidate.write_bytes(
        candidate.read_bytes()
        + b"tampered\n"
    )

    summary_path = (
        batch
        / wrapper.SUMMARY_NAME
    )

    summary = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    summary[
        "candidate_sequence_audit_sha256"
    ] = wrapper.sha256_file(
        candidate
    )

    summary_path.write_bytes(
        transport_json(
            summary
        )
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="candidate-sequence audit differs",
    ):
        execute(
            paths
        )


def test_execute_rejects_consistently_rewritten_component_audit(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    batch = make_batch(
        paths
    )

    component = (
        batch
        / wrapper.COMPONENT_AUDIT_NAME
    )

    component.write_bytes(
        component.read_bytes()
        + b"tampered\n"
    )

    summary_path = (
        batch
        / wrapper.SUMMARY_NAME
    )

    summary = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    summary[
        "component_sequence_audit_sha256"
    ] = wrapper.sha256_file(
        component
    )

    summary_path.write_bytes(
        transport_json(
            summary
        )
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="component-sequence audit differs",
    ):
        execute(
            paths
        )


def test_main_requires_authorization():
    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionExecutionError,
        match="explicit authorization",
    ):
        wrapper.main(
            (
                "--expected-commit",
                COMMIT,
                "--expected-wrapper-sha256",
                "f" * 64,
                "--expected-wrapper-test-sha256",
                "e" * 64,
                "--production-root",
                "/tmp/production",
                "--stage1-root",
                "/tmp/stage1",
                "--sequence-plan-record",
                "/tmp/plan.json",
                "--fresh-target-manifest",
                "/tmp/targets.tsv",
            )
        )


def test_wrapper_contains_no_network_or_historical_bindings():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    for token in (
        "/NGS/",
        "Rhys_wkdir",
        "SLURM_",
        "sbatch",
        "srun",
        "requests.",
        "urllib.",
        "socket.",
    ):
        assert token not in text


def test_completion_record_remains_release_level(
    tmp_path,
):
    paths = make_upstream(
        tmp_path,
        count=1,
    )

    make_batch(
        paths
    )

    result = execute(
        paths
    )

    text = result.completion_path.read_text(
        encoding="ascii"
    )

    for token in (
        "VerifiedMonthlyCacheEvidence",
        "component_identity_sha256",
        "assembly_fingerprint",
        "source_evidence_sha256",
        "verification_record_sha256",
        "verified_source_snapshot_id",
    ):
        assert token not in text
