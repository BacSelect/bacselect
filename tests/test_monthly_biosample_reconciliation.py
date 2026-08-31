from __future__ import annotations

import csv
import hashlib
import io

import pytest

from bacselect import monthly_biosample_reconciliation as monthly
from bacselect import monthly_source_truth
from bacselect import source_truth
from bacselect.source_post_sequence_eligibility import (
    BIOSAMPLE_CONTINUE,
    BIOSAMPLE_NONREPRESENTATIVE,
    BIOSAMPLE_UNRESOLVED,
)
from bacselect.source_repeated_biosample_execution import (
    VerifiedBioSampleFingerprint,
)


A1 = "GCA_000000001.1"
A2 = "GCA_000000002.1"
A3 = "GCA_000000003.1"
A4 = "GCA_000000004.1"

B1 = "SAMN00000001"
B2 = "SAMN00000002"

S1 = "1" * 64
S2 = "2" * 64
S3 = "3" * 64
S4 = "4" * 64

F1 = "a" * 64
F2 = "b" * 64


def source_truth_payload(
    rows,
):
    handle = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        handle,
        fieldnames=list(
            monthly_source_truth.DECISION_FIELDS
        ),
        delimiter="\t",
        lineterminator="\n",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            row
        )

    return handle.getvalue().encode(
        "ascii"
    )


def source_row(
    accession,
    source_sha,
    *,
    status=source_truth.SUITABLE,
    reason="SOURCE_TRUTH_SUITABLE",
):
    return {
        "canonical_genbank_assembly_accession":
            accession,
        "source_evidence_sha256":
            source_sha,
        "sequence_set_sha256":
            "f" * 64,
        "duplicate_relation_count":
            "0",
        "containment_relation_count":
            "0",
        "source_truth_status":
            status,
        "source_truth_reason":
            reason,
    }


def population(
    rows=None,
    metadata=None,
):
    if rows is None:
        rows = (
            source_row(
                A1,
                S1,
            ),
            source_row(
                A2,
                S2,
            ),
        )

    if metadata is None:
        metadata = {
            A1:
                B1,
            A2:
                B2,
        }

    payload = source_truth_payload(
        rows
    )

    return (
        monthly.build_monthly_biosample_population(
            payload,
            expected_source_truth_decisions_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            current_metadata=metadata,
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
        )
    )


def verified(
    accession,
    biosample,
    source_sha,
    fingerprint,
):
    return VerifiedBioSampleFingerprint(
        accession=accession,
        biosample=biosample,
        source_evidence_sha256=source_sha,
        assembly_fingerprint=fingerprint,
    )


def test_population_contains_only_source_truth_suitable():
    observed = population(
        rows=(
            source_row(
                A1,
                S1,
            ),
            source_row(
                A2,
                S2,
                status=source_truth.EXCLUDE,
                reason="SOURCE_TRUTH_EXCLUDED",
            ),
            source_row(
                A3,
                S3,
                status=source_truth.UNRESOLVED,
                reason="SOURCE_TRUTH_UNRESOLVED",
            ),
        ),
        metadata={
            A1:
                B1,
            A2:
                B1,
            A3:
                B2,
        },
    )

    assert observed.suitable_accessions == (
        A1,
    )

    assert (
        observed.source_evidence_sha256_by_accession[
            A1
        ]
        == S1
    )


def test_population_requires_biosample_for_every_suitable():
    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="lacks current BioSample",
    ):
        population(
            metadata={
                A1:
                    B1,
            }
        )


def test_population_rejects_empty_suitable_set():
    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="empty",
    ):
        population(
            rows=(
                source_row(
                    A1,
                    S1,
                    status=source_truth.EXCLUDE,
                    reason="SOURCE_TRUTH_EXCLUDED",
                ),
            ),
            metadata={
                A1:
                    B1,
            },
        )


def test_build_singletons_continue():
    observed = population()

    build = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
            ),
        )
    )

    assert build.decisions[
        A1
    ].status == BIOSAMPLE_CONTINUE

    assert build.decisions[
        A1
    ].reason == "BIOSAMPLE_SINGLETON"

    assert build.decisions[
        A2
    ].status == BIOSAMPLE_CONTINUE

    assert build.group_count == 2
    assert build.singleton_group_count == 2
    assert build.repeated_group_count == 0


def test_identical_repeated_biosample_uses_lexical_representative():
    observed = population(
        metadata={
            A1:
                B1,
            A2:
                B1,
        }
    )

    build = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A2,
                    B1,
                    S2,
                    F1,
                ),
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
            ),
        )
    )

    assert build.decisions[
        A1
    ].status == BIOSAMPLE_CONTINUE

    assert build.decisions[
        A1
    ].reason == (
        "BIOSAMPLE_IDENTICAL_REPRESENTATIVE"
    )

    assert build.decisions[
        A2
    ].status == BIOSAMPLE_NONREPRESENTATIVE

    assert build.decisions[
        A2
    ].reason == (
        "BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE"
    )

    assert build.group_count == 1
    assert build.repeated_group_count == 1
    assert build.identical_repeated_group_count == 1
    assert build.differing_repeated_group_count == 0


def test_differing_repeated_biosample_is_unresolved():
    observed = population(
        metadata={
            A1:
                B1,
            A2:
                B1,
        }
    )

    build = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B1,
                    S2,
                    F2,
                ),
            ),
        )
    )

    assert build.decisions[
        A1
    ].status == BIOSAMPLE_UNRESOLVED

    assert build.decisions[
        A2
    ].status == BIOSAMPLE_UNRESOLVED

    assert build.differing_repeated_group_count == 1


def test_build_rejects_missing_verified_candidate():
    observed = population()

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="population differs",
    ):
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
            ),
        )


def test_build_rejects_extra_verified_candidate():
    observed = population()

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="outside",
    ):
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
                verified(
                    A3,
                    B2,
                    S3,
                    F2,
                ),
            ),
        )


def test_build_rejects_biosample_drift():
    observed = population()

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="BioSample differs",
    ):
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B2,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
            ),
        )


def test_build_rejects_stage4_source_evidence_drift():
    observed = population()

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="source evidence differs",
    ):
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    "9" * 64,
                    F1,
                ),
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
            ),
        )


def test_decisions_are_sorted_and_deterministic():
    observed = population()

    build_a = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
            ),
        )
    )

    build_b = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
            ),
        )
    )

    payload_a = (
        monthly.serialize_monthly_biosample_decisions(
            build_a
        )
    )

    payload_b = (
        monthly.serialize_monthly_biosample_decisions(
            build_b
        )
    )

    assert payload_a == payload_b

    audited = (
        monthly.audit_monthly_biosample_decisions(
            payload_a
        )
    )

    assert tuple(
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in audited
    ) == (
        A1,
        A2,
    )


def test_decision_audit_rejects_unknown_status_reason_pair():
    observed = population()

    build = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
            ),
        )
    )

    payload = (
        monthly.serialize_monthly_biosample_decisions(
            build
        )
    )

    broken = payload.replace(
        b"BIOSAMPLE_SINGLETON",
        b"UNKNOWN_REASON",
        1,
    )

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="status/reason",
    ):
        monthly.audit_monthly_biosample_decisions(
            broken
        )


def test_record_roundtrip_binds_stage4_and_decisions():
    observed = population()

    source_payload = source_truth_payload(
        (
            source_row(
                A1,
                S1,
            ),
            source_row(
                A2,
                S2,
            ),
        )
    )

    observed = (
        monthly.build_monthly_biosample_population(
            source_payload,
            expected_source_truth_decisions_sha256=(
                hashlib.sha256(
                    source_payload
                ).hexdigest()
            ),
            current_metadata={
                A1:
                    B1,
                A2:
                    B2,
            },
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
        )
    )

    build = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B2,
                    S2,
                    F2,
                ),
            ),
        )
    )

    decisions_payload = (
        monthly.serialize_monthly_biosample_decisions(
            build
        )
    )

    record = (
        monthly.serialize_monthly_biosample_record(
            build,
            source_truth_record_sha256=(
                "5" * 64
            ),
            source_truth_completion_sha256=(
                "6" * 64
            ),
        )
    )

    audited = (
        monthly.audit_monthly_biosample_record(
            record,
            source_truth_decisions_payload=(
                source_payload
            ),
            expected_source_truth_decisions_sha256=(
                hashlib.sha256(
                    source_payload
                ).hexdigest()
            ),
            current_metadata={
                A1:
                    B1,
                A2:
                    B2,
            },
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
            source_truth_record_sha256=(
                "5" * 64
            ),
            source_truth_completion_sha256=(
                "6" * 64
            ),
            decisions_payload=(
                decisions_payload
            ),
        )
    )

    assert (
        audited[
            "status"
        ]
        == monthly.MONTHLY_BIOSAMPLE_STATUS
    )

    assert audited[
        "decision_count"
    ] == 2

    assert audited[
        "singleton_group_count"
    ] == 2


def test_record_audit_recomputes_frozen_decisions():
    source_payload = source_truth_payload(
        (
            source_row(
                A1,
                S1,
            ),
            source_row(
                A2,
                S2,
            ),
        )
    )

    observed = (
        monthly.build_monthly_biosample_population(
            source_payload,
            expected_source_truth_decisions_sha256=(
                hashlib.sha256(
                    source_payload
                ).hexdigest()
            ),
            current_metadata={
                A1:
                    B1,
                A2:
                    B1,
            },
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
        )
    )

    build = (
        monthly.build_monthly_biosample_reconciliation(
            observed,
            (
                verified(
                    A1,
                    B1,
                    S1,
                    F1,
                ),
                verified(
                    A2,
                    B1,
                    S2,
                    F1,
                ),
            ),
        )
    )

    decisions_payload = (
        monthly.serialize_monthly_biosample_decisions(
            build
        )
    )

    broken = decisions_payload.replace(
        b"NONREPRESENTATIVE",
        b"REVIEW_UNRESOLVED",
        1,
    ).replace(
        b"BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE",
        b"BIOSAMPLE_FINGERPRINTS_DIFFER",
        1,
    )

    record = (
        monthly.serialize_monthly_biosample_record(
            build,
            source_truth_record_sha256=(
                "5" * 64
            ),
            source_truth_completion_sha256=(
                "6" * 64
            ),
        )
    )

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="frozen reconciler",
    ):
        monthly.audit_monthly_biosample_record(
            record,
            source_truth_decisions_payload=(
                source_payload
            ),
            expected_source_truth_decisions_sha256=(
                hashlib.sha256(
                    source_payload
                ).hexdigest()
            ),
            current_metadata={
                A1:
                    B1,
                A2:
                    B1,
            },
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
            source_truth_record_sha256=(
                "5" * 64
            ),
            source_truth_completion_sha256=(
                "6" * 64
            ),
            decisions_payload=broken,
        )

def test_population_rejects_unauthenticated_stage4_decision_table():
    payload = source_truth_payload(
        (
            source_row(
                A1,
                S1,
            ),
            source_row(
                A2,
                S2,
            ),
        )
    )

    with pytest.raises(
        monthly.MonthlyBioSampleReconciliationError,
        match="authenticated Stage 4 completion",
    ):
        monthly.build_monthly_biosample_population(
            payload,
            expected_source_truth_decisions_sha256=(
                "9" * 64
            ),
            current_metadata={
                A1:
                    B1,
                A2:
                    B2,
            },
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
        )
