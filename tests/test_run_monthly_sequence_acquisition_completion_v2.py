"""Synthetic tests for recovery-aware sequence-acquisition completion v2."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import monthly_sequence_recovery_authority as authority
from bacselect import monthly_sequence_recovery_provider as recovery_provider


ROOT = Path(
    __file__
).resolve().parents[
    1
]

WRAPPER_PATH = (
    ROOT
    / "validation"
    / "selector-v1"
    / "run_monthly_sequence_acquisition_completion_v2.py"
)


def load_module(
    path: Path,
    name: str,
):
    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            path,
        )
    )

    assert spec is not None
    assert spec.loader is not None

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


wrapper = load_module(
    WRAPPER_PATH,
    "_bacselect_completion_v2_execution_test",
)

v1_fixture = load_module(
    ROOT
    / "tests"
    / "test_run_monthly_sequence_acquisition_completion.py",
    "_bacselect_completion_v2_v1_wrapper_fixture",
)


COMPLETION_COMMIT = (
    "b" * 40
)

RECOVERY_COMMIT = (
    "c" * 40
)


def execute(
    paths,
    *,
    recovery_roots=(),
):
    return (
        wrapper
        .execute_monthly_sequence_acquisition_completion_v2(
            repo=(
                v1_fixture.REPO
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
            source_production_commit=(
                v1_fixture.COMMIT
            ),
            completion_execution_commit=(
                COMPLETION_COMMIT
            ),
            recovery_roots=(
                recovery_roots
            ),
            package_validator=(
                v1_fixture
                .synthetic_package_validator
            ),
        )
    )


def transport_json(
    value,
):
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


def install_synthetic_second_batch_recovery(
    monkeypatch,
    paths,
    *,
    provider_recovery_commit=(
        RECOVERY_COMMIT
    ),
):
    sequence_root = (
        paths[
            "stage1_root"
        ]
        / wrapper.v1.SEQUENCE_ROOT_NAME
    )

    source_partial = (
        sequence_root
        / "batch-00002.partial"
    )

    source_partial.mkdir(
        parents=True,
        exist_ok=False,
    )

    recovery_root = (
        paths[
            "stage1_root"
        ]
        / wrapper.RECOVERY_PARENT_NAME
        / RECOVERY_COMMIT
        / (
            "source-"
            + v1_fixture.COMMIT
        )
    )

    recovery_batch = (
        recovery_root
        / "batch-00002"
    )

    package = (
        recovery_batch
        / authority.PACKAGE_NAME
    )

    package.mkdir(
        parents=True
    )

    (
        package
        / "synthetic-recovered-file.txt"
    ).write_bytes(
        b"synthetic recovered package\n"
    )

    fingerprint = (
        authority.strict_tree_fingerprint(
            package
        )
    )

    (
        recovery_batch
        / authority.RECOVERY_PACKAGE_MANIFEST_NAME
    ).write_bytes(
        fingerprint.payload
    )

    ordinary_batch = (
        sequence_root
        / "batch-00001"
    )

    fresh_authority = (
        authority.AuthoritativeSequenceBatch(
            batch_id="batch-00001",
            source_class=(
                authority
                .SOURCE_CLASS_FRESH
            ),
            batch_dir=(
                ordinary_batch
            ),
            source_partial_dir=None,
            recovery_commit=None,
            recovery_summary_sha256=None,
        )
    )

    recovered_authority = (
        authority.AuthoritativeSequenceBatch(
            batch_id="batch-00002",
            source_class=(
                authority
                .SOURCE_CLASS_FRESH_RECOVERY
            ),
            batch_dir=(
                recovery_batch
            ),
            source_partial_dir=(
                source_partial
            ),
            recovery_commit=(
                RECOVERY_COMMIT
            ),
            recovery_summary_sha256=(
                "5" * 64
            ),
        )
    )

    def fake_resolver(
        **kwargs,
    ):
        assert kwargs[
            "expected_source_production_commit"
        ] == v1_fixture.COMMIT

        assert tuple(
            kwargs[
                "expected_batch_ids"
            ]
        ) == (
            "batch-00001",
            "batch-00002",
        )

        assert tuple(
            kwargs[
                "recovery_roots"
            ]
        ) == (
            recovery_root.resolve(),
        )

        return (
            fresh_authority,
            recovered_authority,
        )

    observed = {}

    def fake_recovery_provider(
        authoritative_batch,
        *,
        targets,
        expected_release_id,
        expected_source_production_commit,
        source_snapshot_report=None,
    ):
        observed[
            "source_snapshot_report"
        ] = source_snapshot_report

        observed[
            "targets"
        ] = tuple(
            targets
        )

        assert (
            authoritative_batch
            == recovered_authority
        )

        assert (
            expected_source_production_commit
            == v1_fixture.COMMIT
        )

        assert (
            source_snapshot_report
            == (
                paths[
                    "stage1_root"
                ]
                / wrapper.v1.RAW_RESPONSE_NAME
            )
        )

        return (
            recovery_provider
            .AuditedRecoveryProvider(
                batch_id="batch-00002",
                source_class=(
                    authority
                    .SOURCE_CLASS_FRESH_RECOVERY
                ),
                recovery_class=(
                    recovery_provider
                    .RECOVERY_CLASS_MISSING_DATASETS_GBFF
                ),
                batch_dir=(
                    recovery_batch
                ),
                source_partial_dir=(
                    source_partial
                ),
                source_production_commit=(
                    v1_fixture.COMMIT
                ),
                recovery_commit=(
                    provider_recovery_commit
                ),
                source_batch_sha256=(
                    "7" * 64
                ),
                source_package_sha256=(
                    "8" * 64
                ),
                recovery_package_sha256=(
                    fingerprint.sha256
                ),
                candidate_audit_sha256=(
                    "9" * 64
                ),
                component_audit_sha256=(
                    "a" * 64
                ),
                recovery_summary_sha256=(
                    "5" * 64
                ),
                cause_evidence_sha256=(
                    "6" * 64
                ),
                transport_record_sha256=None,
            )
        )

    monkeypatch.setattr(
        wrapper.authority,
        "resolve_authoritative_sequence_batches",
        fake_resolver,
    )

    monkeypatch.setattr(
        wrapper.recovery_provider,
        "audit_authoritative_recovery_provider",
        fake_recovery_provider,
    )

    return (
        recovery_root,
        observed,
    )


def test_all_fresh_execution_writes_distinct_v2_completion(
    tmp_path,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=1,
        )
    )

    v1_fixture.make_batch(
        paths
    )

    result = execute(
        paths
    )

    assert (
        result.source_production_commit
        == v1_fixture.COMMIT
    )

    assert (
        result.completion_execution_commit
        == COMPLETION_COMMIT
    )

    assert (
        result.fresh_batch_count
        == 1
    )

    assert (
        result.recovery_batch_count
        == 0
    )

    assert (
        result.completion_path.name
        == wrapper.COMPLETION_NAME
    )

    assert (
        not (
            paths[
                "stage1_root"
            ]
            / wrapper.v1.COMPLETION_NAME
        ).exists()
    )

    record = json.loads(
        result
        .completion_path
        .read_text(
            encoding="ascii"
        )
    )

    assert (
        record[
            "source_production_commit"
        ]
        == v1_fixture.COMMIT
    )

    assert (
        record[
            "completion_execution_commit"
        ]
        == COMPLETION_COMMIT
    )

    assert record[
        "source_class_counts"
    ] == {
        "fresh":
            1,
        "fresh-recovery":
            0,
    }


def test_ordinary_summary_source_commit_tamper_fails_closed(
    tmp_path,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=1,
        )
    )

    batch = (
        v1_fixture.make_batch(
            paths
        )
    )

    summary_path = (
        batch
        / wrapper.v1.SUMMARY_NAME
    )

    summary = json.loads(
        summary_path.read_text(
            encoding="utf-8"
        )
    )

    summary[
        "origin_git_commit"
    ] = "f" * 40

    summary_path.write_bytes(
        transport_json(
            summary
        )
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionV2ExecutionError,
        match="ordinary provider audit failed",
    ):
        execute(
            paths
        )


def test_mixed_fresh_recovery_execution(
    tmp_path,
    monkeypatch,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=(
                v1_fixture.FRESH_BATCH_SIZE
                + 1
            ),
        )
    )

    v1_fixture.make_batch(
        paths
    )

    (
        recovery_root,
        observed,
    ) = (
        install_synthetic_second_batch_recovery(
            monkeypatch,
            paths,
        )
    )

    result = execute(
        paths,
        recovery_roots=(
            recovery_root,
        ),
    )

    assert (
        result.completed_batch_count
        == 2
    )

    assert (
        result.fresh_batch_count
        == 1
    )

    assert (
        result.recovery_batch_count
        == 1
    )

    assert len(
        observed[
            "targets"
        ]
    ) == 1

    assert (
        observed[
            "source_snapshot_report"
        ]
        == (
            paths[
                "stage1_root"
            ]
            / wrapper.v1.RAW_RESPONSE_NAME
        )
    )

    record = json.loads(
        result
        .completion_path
        .read_text(
            encoding="ascii"
        )
    )

    first, second = (
        record[
            "batches"
        ]
    )

    assert (
        first[
            "source_class"
        ]
        == "fresh"
    )

    assert (
        second[
            "source_class"
        ]
        == "fresh-recovery"
    )

    assert (
        second[
            "recovery_class"
        ]
        == (
            recovery_provider
            .RECOVERY_CLASS_MISSING_DATASETS_GBFF
        )
    )

    assert (
        second[
            "source_partial_name"
        ]
        == "batch-00002.partial"
    )

    assert (
        second[
            "recovery_commit"
        ]
        == RECOVERY_COMMIT
    )


def test_recovery_root_commit_mismatch_fails_closed(
    tmp_path,
    monkeypatch,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=(
                v1_fixture.FRESH_BATCH_SIZE
                + 1
            ),
        )
    )

    v1_fixture.make_batch(
        paths
    )

    recovery_root, _ = (
        install_synthetic_second_batch_recovery(
            monkeypatch,
            paths,
            provider_recovery_commit=(
                "d" * 40
            ),
        )
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionV2ExecutionError,
        match="recovery root commit differs",
    ):
        execute(
            paths,
            recovery_roots=(
                recovery_root,
            ),
        )


def test_source_partial_without_recovery_fails_closed(
    tmp_path,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=1,
        )
    )

    sequence_root = (
        paths[
            "stage1_root"
        ]
        / wrapper.v1.SEQUENCE_ROOT_NAME
    )

    sequence_root.mkdir()

    (
        sequence_root
        / "batch-00001.partial"
    ).mkdir()

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionV2ExecutionError,
        match="authoritative sequence-batch resolution failed",
    ):
        execute(
            paths
        )


def test_duplicate_recovery_root_fails_closed(
    tmp_path,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=0,
        )
    )

    root = (
        paths[
            "stage1_root"
        ]
        / wrapper.RECOVERY_PARENT_NAME
        / RECOVERY_COMMIT
        / (
            "source-"
            + v1_fixture.COMMIT
        )
    )

    root.mkdir(
        parents=True
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionV2ExecutionError,
        match="duplicate recovery root",
    ):
        execute(
            paths,
            recovery_roots=(
                root,
                root,
            ),
        )


def test_existing_v2_completion_refuses_overwrite(
    tmp_path,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=1,
        )
    )

    v1_fixture.make_batch(
        paths
    )

    execute(
        paths
    )

    with pytest.raises(
        wrapper.MonthlySequenceAcquisitionCompletionV2ExecutionError,
        match="artifact already exists",
    ):
        execute(
            paths
        )


def test_existing_v1_completion_does_not_masquerade_as_v2(
    tmp_path,
):
    paths = (
        v1_fixture.make_upstream(
            tmp_path,
            count=1,
        )
    )

    v1_fixture.make_batch(
        paths
    )

    (
        paths[
            "stage1_root"
        ]
        / wrapper.v1.COMPLETION_NAME
    ).write_bytes(
        b"synthetic old completion\n"
    )

    result = execute(
        paths
    )

    assert (
        result.completion_path.name
        == wrapper.COMPLETION_NAME
    )

    assert (
        (
            paths[
                "stage1_root"
            ]
            / wrapper.v1.COMPLETION_NAME
        ).read_bytes()
        == b"synthetic old completion\n"
    )


def test_repository_preflight_binds_checkout_to_completion_commit(
    tmp_path,
    monkeypatch,
):
    observed = {}

    def fake_v1_preflight(
        repo,
        *,
        expected_commit,
        expected_wrapper_sha256,
        expected_wrapper_test_sha256,
        git_reader,
        file_sha256_reader,
    ):
        observed[
            "expected_commit"
        ] = expected_commit

        observed[
            "v1_wrapper_sha"
        ] = expected_wrapper_sha256

    monkeypatch.setattr(
        wrapper.v1,
        "repository_preflight",
        fake_v1_preflight,
    )

    monkeypatch.setattr(
        wrapper.v1,
        "require_sha256",
        lambda *args, **kwargs:
            None,
    )

    wrapper.repository_preflight(
        tmp_path,
        completion_execution_commit=(
            COMPLETION_COMMIT
        ),
        expected_wrapper_sha256=(
            "1" * 64
        ),
        expected_wrapper_test_sha256=(
            "2" * 64
        ),
        git_reader=lambda *args:
            "",
        file_sha256_reader=lambda path:
            "0" * 64,
    )

    assert (
        observed[
            "expected_commit"
        ]
        == COMPLETION_COMMIT
    )

    assert (
        observed[
            "v1_wrapper_sha"
        ]
        == wrapper.EXPECTED_V1_WRAPPER_SHA256
    )


def test_wrapper_has_no_incident_or_cache_bindings():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    for token in (
        "batch-00072",
        "batch-00118",
        "batch-00130",
        "GCA_030436345.2",
        "GCA_055419085.2",
        "GCA_059637575.1",
        "monthly_sequence_cache_catalogue",
        "run_monthly_sequence_cache_catalogue",
        "requests.",
        "urllib.",
        "socket.",
    ):
        assert token not in text
