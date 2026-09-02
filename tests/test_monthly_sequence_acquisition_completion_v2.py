from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import monthly_sequence_recovery_authority as authority
from bacselect import monthly_sequence_recovery_provider as provider
from bacselect.monthly_sequence_acquisition_completion_v2 import (
    AuthoritativeCompletedBatchEvidence,
    FRESH_PACKAGE_MANIFEST_NAME,
    FRESH_PROVIDER_SUMMARY_NAME,
    MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_V2_SCHEMA,
    MonthlySequenceAcquisitionCompletionV2Error,
    RECOVERY_CLASS_MISSING_DATASETS_GBFF,
    RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION,
    RECOVERY_PACKAGE_MANIFEST_NAME,
    RECOVERY_PROVIDER_SUMMARY_NAME,
    SOURCE_CLASS_FRESH,
    SOURCE_CLASS_FRESH_RECOVERY,
    audit_sequence_acquisition_completion_v2_record,
    build_sequence_acquisition_completion_v2_record,
    serialize_sequence_acquisition_completion_v2_record,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE_PRODUCTION_COMMIT = "a" * 40
COMPLETION_EXECUTION_COMMIT = "b" * 40
ENVIRONMENT_SHA = "c" * 64


def load_v1_fixture():
    path = (
        ROOT
        / "tests"
        / "test_monthly_sequence_acquisition_completion.py"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            "_bacselect_completion_v2_v1_fixture",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "could not load frozen v1 completion fixture"
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


fixture = load_v1_fixture()


def fresh_evidence(
    plan,
    manifest,
    targets,
    batch_index,
):
    old = fixture.make_batch(
        plan,
        manifest,
        targets,
        batch_index,
    )

    summary = json.loads(
        old.summary_payload.decode(
            "utf-8"
        )
    )

    return AuthoritativeCompletedBatchEvidence(
        batch_id=old.batch_id,
        source_class=(
            SOURCE_CLASS_FRESH
        ),
        recovery_class=None,
        requested_accessions=(
            summary[
                "requested_accessions"
            ]
        ),
        first_accession=(
            summary[
                "first_accession"
            ]
        ),
        last_accession=(
            summary[
                "last_accession"
            ]
        ),
        observed_batch_target_manifest_sha256=(
            old.observed_batch_target_manifest_sha256
        ),
        observed_accessions_sha256=(
            old.observed_accessions_sha256
        ),
        observed_candidate_audit_sha256=(
            old.observed_candidate_audit_sha256
        ),
        observed_component_audit_sha256=(
            old.observed_component_audit_sha256
        ),
        provider_summary_name=(
            FRESH_PROVIDER_SUMMARY_NAME
        ),
        provider_summary_sha256=(
            hashlib.sha256(
                old.summary_payload
            ).hexdigest()
        ),
        package_manifest_name=(
            FRESH_PACKAGE_MANIFEST_NAME
        ),
        package_manifest_sha256=(
            hashlib.sha256(
                old.package_files_payload
            ).hexdigest()
        ),
        package_file_count=len(
            old.package_file_observations
        ),
        package_file_readback_count=len(
            old.package_file_observations
        ),
        package_file_readback_sha256=(
            "4" * 64
        ),
    )


def recovery_evidence(
    evidence,
    *,
    recovery_class,
):
    recovery_summary_sha = (
        "5" * 64
    )

    recovery_package_sha = (
        "6" * 64
    )

    return replace(
        evidence,
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        ),
        recovery_class=(
            recovery_class
        ),
        provider_summary_name=(
            RECOVERY_PROVIDER_SUMMARY_NAME
        ),
        provider_summary_sha256=(
            recovery_summary_sha
        ),
        package_manifest_name=(
            RECOVERY_PACKAGE_MANIFEST_NAME
        ),
        package_manifest_sha256=(
            recovery_package_sha
        ),
        source_partial_name=(
            evidence.batch_id
            + ".partial"
        ),
        recovery_commit=(
            "d" * 40
        ),
        source_batch_sha256=(
            "7" * 64
        ),
        source_package_sha256=(
            "8" * 64
        ),
        recovery_package_sha256=(
            recovery_package_sha
        ),
        recovery_summary_sha256=(
            recovery_summary_sha
        ),
        cause_evidence_sha256=(
            "9" * 64
        ),
        transport_record_sha256=(
            "e" * 64
            if recovery_class
            == RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
            else None
        ),
    )


def kwargs_for(
    count,
    *,
    recovery_indices=(),
    recovery_class=(
        RECOVERY_CLASS_MISSING_DATASETS_GBFF
    ),
):
    (
        plan,
        manifest,
        targets,
    ) = fixture.make_plan(
        count
    )

    batch_count = (
        (
            count
            + fixture.FRESH_BATCH_SIZE
            - 1
        )
        // fixture.FRESH_BATCH_SIZE
        if count
        else 0
    )

    values = []

    for index in range(
        1,
        batch_count
        + 1,
    ):
        evidence = fresh_evidence(
            plan,
            manifest,
            targets,
            index,
        )

        if index in recovery_indices:
            evidence = recovery_evidence(
                evidence,
                recovery_class=(
                    recovery_class
                ),
            )

        values.append(
            evidence
        )

    return {
        "source_snapshot_id":
            fixture.SNAPSHOT,
        "source_snapshot_record_sha256":
            fixture.SNAPSHOT_SHA,
        "stage2_sequence_plan_record":
            plan,
        "stage2_fresh_target_manifest":
            manifest,
        "source_production_commit":
            SOURCE_PRODUCTION_COMMIT,
        "completion_execution_commit":
            COMPLETION_EXECUTION_COMMIT,
        "environment_explicit_sha256":
            ENVIRONMENT_SHA,
        "batches":
            tuple(
                values
            ),
    }


def test_contract_constants_match_frozen_authority_provider():
    assert SOURCE_CLASS_FRESH == (
        authority.SOURCE_CLASS_FRESH
    )

    assert SOURCE_CLASS_FRESH_RECOVERY == (
        authority.SOURCE_CLASS_FRESH_RECOVERY
    )

    assert (
        RECOVERY_CLASS_MISSING_DATASETS_GBFF
        == provider.RECOVERY_CLASS_MISSING_DATASETS_GBFF
    )

    assert (
        RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
        == provider.RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
    )


def test_all_fresh_v2_completion():
    values = kwargs_for(
        3
    )

    result = (
        build_sequence_acquisition_completion_v2_record(
            **values
        )
    )

    assert (
        result[
            "schema_version"
        ]
        == MONTHLY_SEQUENCE_ACQUISITION_COMPLETION_V2_SCHEMA
    )

    assert (
        result[
            "source_production_commit"
        ]
        == SOURCE_PRODUCTION_COMMIT
    )

    assert (
        result[
            "completion_execution_commit"
        ]
        == COMPLETION_EXECUTION_COMMIT
    )

    assert result[
        "source_class_counts"
    ] == {
        SOURCE_CLASS_FRESH:
            1,
        SOURCE_CLASS_FRESH_RECOVERY:
            0,
    }

    row = result[
        "batches"
    ][0]

    assert (
        row[
            "source_class"
        ]
        == SOURCE_CLASS_FRESH
    )

    assert (
        row[
            "recovery_class"
        ]
        is None
    )

    assert (
        row[
            "provider_summary_name"
        ]
        == FRESH_PROVIDER_SUMMARY_NAME
    )

    assert (
        row[
            "package_manifest_name"
        ]
        == FRESH_PACKAGE_MANIFEST_NAME
    )


def test_mixed_authoritative_sources_are_explicit():
    values = kwargs_for(
        fixture.FRESH_BATCH_SIZE
        + 1,
        recovery_indices=(
            2,
        ),
    )

    result = (
        build_sequence_acquisition_completion_v2_record(
            **values
        )
    )

    assert result[
        "source_class_counts"
    ] == {
        SOURCE_CLASS_FRESH:
            1,
        SOURCE_CLASS_FRESH_RECOVERY:
            1,
    }

    first, second = result[
        "batches"
    ]

    assert (
        first[
            "source_class"
        ]
        == SOURCE_CLASS_FRESH
    )

    assert (
        second[
            "source_class"
        ]
        == SOURCE_CLASS_FRESH_RECOVERY
    )

    assert (
        second[
            "recovery_class"
        ]
        == RECOVERY_CLASS_MISSING_DATASETS_GBFF
    )

    assert (
        second[
            "source_partial_name"
        ]
        == "batch-00002.partial"
    )

    assert (
        second[
            "provider_summary_name"
        ]
        == RECOVERY_PROVIDER_SUMMARY_NAME
    )

    assert (
        second[
            "package_manifest_name"
        ]
        == RECOVERY_PACKAGE_MANIFEST_NAME
    )


def test_supersession_requires_transport_identity():
    values = kwargs_for(
        3,
        recovery_indices=(
            1,
        ),
        recovery_class=(
            RECOVERY_CLASS_POST_SNAPSHOT_SUPERSESSION
        ),
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            transport_record_sha256=None,
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="missing transport record",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_missing_gbff_rejects_supersession_transport_identity():
    values = kwargs_for(
        3,
        recovery_indices=(
            1,
        ),
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            transport_record_sha256=(
                "f" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="unexpectedly carries",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_fresh_provider_cannot_carry_recovery_identity():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            recovery_commit=(
                "d" * 40
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="recovery-only evidence",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_recovery_provider_names_cannot_masquerade_as_fresh():
    values = kwargs_for(
        3,
        recovery_indices=(
            1,
        ),
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            provider_summary_name=(
                FRESH_PROVIDER_SUMMARY_NAME
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="provider summary name changed",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_unknown_recovery_class_fails_closed():
    values = kwargs_for(
        3,
        recovery_indices=(
            1,
        ),
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            recovery_class=(
                "future_unknown_recovery"
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="unknown recovery class",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_provider_sequence_must_match_stage2_order_exactly():
    values = kwargs_for(
        fixture.FRESH_BATCH_SIZE
        + 1
    )

    values[
        "batches"
    ] = tuple(
        reversed(
            values[
                "batches"
            ]
        )
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="out of Stage 2 order",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_batch_target_identity_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            observed_batch_target_manifest_sha256=(
                "f" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="batch-target manifest identity changed",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_accession_identity_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            observed_accessions_sha256=(
                "f" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="accession-list identity changed",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_recovery_summary_and_package_manifest_are_bound():
    values = kwargs_for(
        3,
        recovery_indices=(
            1,
        ),
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            provider_summary_sha256=(
                "f" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="recovery-summary SHA256",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_package_readback_count_must_match_manifest_count():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        replace(
            first,
            package_file_readback_count=(
                first.package_file_count
                + 1
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="readback count changed",
    ):
        build_sequence_acquisition_completion_v2_record(
            **values
        )


def test_serialization_roundtrip_and_tamper_fail_closed():
    values = kwargs_for(
        fixture.FRESH_BATCH_SIZE
        + 1,
        recovery_indices=(
            2,
        ),
    )

    payload = (
        serialize_sequence_acquisition_completion_v2_record(
            **values
        )
    )

    audited = (
        audit_sequence_acquisition_completion_v2_record(
            payload,
            **values
        )
    )

    assert (
        audited[
            "completed_batch_count"
        ]
        == 2
    )

    changed = bytearray(
        payload
    )

    changed[
        changed.index(
            b"SEQUENCE_ACQUISITION_COMPLETE"
        )
    ] = ord(
        "X"
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionV2Error,
        match="derived identity changed",
    ):
        audit_sequence_acquisition_completion_v2_record(
            bytes(
                changed
            ),
            **values
        )


def test_v2_core_has_no_execution_or_environment_specific_bindings():
    text = Path(
        sys.modules[
            build_sequence_acquisition_completion_v2_record
            .__module__
        ].__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "/NGS/",
        "Rhys_wkdir",
        "subprocess",
        "requests.",
        "urllib.",
        "socket.",
        "sequence-acquisition-recovery/",
        "batch-00072",
        "batch-00118",
        "batch-00130",
        "GCA_030436345.2",
        "GCA_055419085.2",
        "GCA_059637575.1",
    ):
        assert token not in text
