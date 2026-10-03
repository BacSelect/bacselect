from __future__ import annotations

import dataclasses
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import monthly_missing_datasets_gbff_execution as gbff_execution
from bacselect import monthly_post_snapshot_supersession_execution as supersession_execution
from bacselect import monthly_post_snapshot_supersession_recovery as supersession_recovery
from bacselect import monthly_sequence_recovery_authority as authority
from bacselect import monthly_sequence_recovery_provider as provider


ROOT = Path(__file__).resolve().parents[1]


def load_fixture_module(
    name: str,
    relative_path: str,
):
    path = (
        ROOT
        / relative_path
    )

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
        raise RuntimeError(
            f"could not load fixture module {path}"
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


gbff_fixture = load_fixture_module(
    "_bacselect_provider_gbff_fixture",
    "tests/"
    "test_monthly_missing_datasets_gbff_execution.py",
)

supersession_fixture = load_fixture_module(
    "_bacselect_provider_supersession_fixture",
    "tests/"
    "test_monthly_post_snapshot_supersession_execution.py",
)


def resolve_one(
    *,
    sequence_root,
    recovery_root,
    batch_id,
    release,
    source_commit,
):
    resolved = (
        authority
        .resolve_authoritative_sequence_batches(
            sequence_root=(
                sequence_root
            ),
            recovery_roots=(
                recovery_root,
            ),
            expected_batch_ids=(
                batch_id,
            ),
            expected_release_id=(
                release
            ),
            expected_source_production_commit=(
                source_commit
            ),
        )
    )

    assert len(
        resolved
    ) == 1

    return resolved[
        0
    ]


def make_gbff_provider(
    tmp_path,
):
    (
        sequence_root,
        source_partial,
        _,
        recovery_root,
        _,
        result,
    ) = gbff_fixture.run_execution(
        tmp_path
    )

    authoritative = resolve_one(
        sequence_root=sequence_root,
        recovery_root=recovery_root,
        batch_id=(
            gbff_fixture.BATCH
        ),
        release=(
            gbff_fixture.RELEASE
        ),
        source_commit=(
            gbff_fixture.SOURCE_COMMIT
        ),
    )

    return (
        authoritative,
        source_partial,
        result,
    )


def make_supersession_provider(
    tmp_path,
):
    (
        snapshot,
        sequence_root,
        source_partial,
        recovery_root,
        result,
        _,
        _,
    ) = (
        supersession_fixture
        .run_success(
            tmp_path
        )
    )

    authoritative = resolve_one(
        sequence_root=sequence_root,
        recovery_root=recovery_root,
        batch_id=(
            supersession_fixture.BATCH
        ),
        release=(
            supersession_fixture.RELEASE
        ),
        source_commit=(
            supersession_fixture.SOURCE_COMMIT
        ),
    )

    return (
        authoritative,
        source_partial,
        snapshot,
        result,
    )


def test_missing_gbff_provider_dispatches_and_reaudits(
    tmp_path,
):
    (
        authoritative,
        source_partial,
        result,
    ) = make_gbff_provider(
        tmp_path
        / "gbff"
    )

    audited = (
        provider
        .audit_authoritative_recovery_provider(
            authoritative,
            targets=(
                gbff_fixture
                .fixture
                .make_target(),
            ),
            expected_release_id=(
                gbff_fixture.RELEASE
            ),
            expected_source_production_commit=(
                gbff_fixture.SOURCE_COMMIT
            ),
        )
    )

    assert audited.batch_id == (
        gbff_fixture.BATCH
    )

    assert (
        audited.source_class
        == authority.SOURCE_CLASS_FRESH_RECOVERY
    )

    assert (
        audited.recovery_class
        == gbff_execution.FAILURE_CLASS
    )

    assert (
        audited.source_partial_dir
        == source_partial
    )

    assert (
        audited.recovery_commit
        == result.recovery_commit
    )

    assert (
        audited.recovery_summary_sha256
        == result.recovery_summary_sha256
    )

    assert (
        audited.cause_evidence_sha256
        == result.recovery_evidence_sha256
    )

    assert (
        audited.transport_record_sha256
        is None
    )


def test_supersession_provider_dispatches_and_reaudits(
    tmp_path,
):
    (
        authoritative,
        source_partial,
        snapshot,
        result,
    ) = make_supersession_provider(
        tmp_path
        / "supersession"
    )

    audited = (
        provider
        .audit_authoritative_recovery_provider(
            authoritative,
            targets=(
                supersession_fixture
                .targets()
            ),
            expected_release_id=(
                supersession_fixture.RELEASE
            ),
            expected_source_production_commit=(
                supersession_fixture
                .SOURCE_COMMIT
            ),
            source_snapshot_report=(
                snapshot
            ),
        )
    )

    assert audited.batch_id == (
        supersession_fixture.BATCH
    )

    assert (
        audited.source_class
        == authority.SOURCE_CLASS_FRESH_RECOVERY
    )

    assert (
        audited.recovery_class
        == supersession_recovery.FAILURE_CLASS
    )

    assert (
        audited.source_partial_dir
        == source_partial
    )

    assert (
        audited.recovery_commit
        == result.recovery_commit
    )

    assert (
        audited.recovery_summary_sha256
        == result.recovery_summary_sha256
    )

    assert (
        audited.cause_evidence_sha256
        == result.supersession_evidence_sha256
    )

    assert (
        audited.transport_record_sha256
        == result.transport_record_sha256
    )


def test_supersession_requires_snapshot(
    tmp_path,
):
    (
        authoritative,
        _,
        _,
        _,
    ) = make_supersession_provider(
        tmp_path
        / "supersession"
    )

    with pytest.raises(
        provider.MonthlySequenceRecoveryProviderError,
        match="requires source_snapshot_report",
    ):
        provider.audit_authoritative_recovery_provider(
            authoritative,
            targets=(
                supersession_fixture
                .targets()
            ),
            expected_release_id=(
                supersession_fixture.RELEASE
            ),
            expected_source_production_commit=(
                supersession_fixture
                .SOURCE_COMMIT
            ),
        )


def test_multiple_explicit_recovery_classes_fail_closed(
    tmp_path,
):
    (
        authoritative,
        _,
        _,
    ) = make_gbff_provider(
        tmp_path
        / "gbff"
    )

    transport = (
        authoritative.batch_dir
        / supersession_execution.TRANSPORT_RECORD_NAME
    )

    transport.write_text(
        json.dumps(
            {
                "classification":
                    supersession_recovery
                    .FAILURE_CLASS,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        provider.MonthlySequenceRecoveryProviderError,
        match="multiple recognized",
    ):
        provider.audit_authoritative_recovery_provider(
            authoritative,
            targets=(
                gbff_fixture
                .fixture
                .make_target(),
            ),
            expected_release_id=(
                gbff_fixture.RELEASE
            ),
            expected_source_production_commit=(
                gbff_fixture.SOURCE_COMMIT
            ),
        )


def test_unknown_explicit_recovery_class_fails_closed(
    tmp_path,
):
    (
        authoritative,
        _,
        _,
    ) = make_gbff_provider(
        tmp_path
        / "gbff"
    )

    path = (
        authoritative.batch_dir
        / gbff_execution.RECOVERY_EVIDENCE_NAME
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    payload[
        "failure_class"
    ] = "synthetic_future_recovery_class"

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        provider.MonthlySequenceRecoveryProviderError,
        match="discriminator is unknown",
    ):
        provider.audit_authoritative_recovery_provider(
            authoritative,
            targets=(
                gbff_fixture
                .fixture
                .make_target(),
            ),
            expected_release_id=(
                gbff_fixture.RELEASE
            ),
            expected_source_production_commit=(
                gbff_fixture.SOURCE_COMMIT
            ),
        )


def test_no_explicit_recovery_class_fails_closed(
    tmp_path,
):
    (
        authoritative,
        _,
        _,
    ) = make_gbff_provider(
        tmp_path
        / "gbff"
    )

    (
        authoritative.batch_dir
        / gbff_execution.RECOVERY_EVIDENCE_NAME
    ).unlink()

    with pytest.raises(
        provider.MonthlySequenceRecoveryProviderError,
        match="no recognized",
    ):
        provider.audit_authoritative_recovery_provider(
            authoritative,
            targets=(
                gbff_fixture
                .fixture
                .make_target(),
            ),
            expected_release_id=(
                gbff_fixture.RELEASE
            ),
            expected_source_production_commit=(
                gbff_fixture.SOURCE_COMMIT
            ),
        )


def test_resolver_identity_mismatch_fails_closed(
    tmp_path,
):
    (
        authoritative,
        _,
        _,
    ) = make_gbff_provider(
        tmp_path
        / "gbff"
    )

    forged = dataclasses.replace(
        authoritative,
        recovery_summary_sha256=(
            "0" * 64
        ),
    )

    with pytest.raises(
        provider.MonthlySequenceRecoveryProviderError,
        match="resolver authority differs",
    ):
        provider.audit_authoritative_recovery_provider(
            forged,
            targets=(
                gbff_fixture
                .fixture
                .make_target(),
            ),
            expected_release_id=(
                gbff_fixture.RELEASE
            ),
            expected_source_production_commit=(
                gbff_fixture.SOURCE_COMMIT
            ),
        )


def test_ordinary_fresh_batch_is_not_a_recovery_provider(
    tmp_path,
):
    ordinary = (
        authority
        .AuthoritativeSequenceBatch(
            batch_id="batch-00001",
            source_class=(
                authority
                .SOURCE_CLASS_FRESH
            ),
            batch_dir=(
                tmp_path
                / "batch-00001"
            ),
            source_partial_dir=None,
            recovery_commit=None,
            recovery_summary_sha256=None,
        )
    )

    with pytest.raises(
        provider.MonthlySequenceRecoveryProviderError,
        match="requires source_class fresh-recovery",
    ):
        provider.audit_authoritative_recovery_provider(
            ordinary,
            targets=(),
            expected_release_id="2026.09",
            expected_source_production_commit=(
                "a" * 40
            ),
        )
