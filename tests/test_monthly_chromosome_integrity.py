from __future__ import annotations

import hashlib
import json

import pytest

from bacselect import monthly_biosample_reconciliation as stage5
from bacselect import monthly_chromosome_integrity as monthly
from bacselect import source_chromosome_integrity as chromosome
from bacselect import source_chromosome_integrity_execution as execution
from bacselect import source_post_sequence_eligibility as eligibility


def stage5_payload(
    rows,
):
    lines = [
        "\t".join(
            stage5.DECISION_FIELDS
        )
    ]

    for row in rows:
        lines.append(
            "\t".join(
                row[
                    field
                ]
                for field in stage5.DECISION_FIELDS
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode()


def stage5_row(
    accession,
    *,
    source_char="1",
    fingerprint_char="2",
    status=eligibility.BIOSAMPLE_CONTINUE,
    reason="BIOSAMPLE_SINGLETON",
):
    return {
        "canonical_genbank_assembly_accession":
            accession,
        "biosample":
            "SAMN10000001",
        "source_evidence_sha256":
            source_char * 64,
        "assembly_fingerprint":
            fingerprint_char * 64,
        "biosample_status":
            status,
        "biosample_reason":
            reason,
    }


def population(
    rows=None,
):
    if rows is None:
        rows = [
            stage5_row(
                "GCA_000000001.1",
            )
        ]

    payload = stage5_payload(
        rows
    )

    return (
        monthly.build_monthly_chromosome_population(
            payload,
            expected_biosample_decisions_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-"
                "20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
        ),
        payload,
    )


def evaluation(
    accession="GCA_000000001.1",
    *,
    source_char="1",
    primary_count=1,
    chromosome_count=1,
    supported_count=1,
    unsupported_count=0,
    triggered=False,
    status=chromosome.PASS,
    reason="NO_CHROMOSOME_INTEGRITY_TRIGGER",
    reused=False,
):
    return execution.Stage3CandidateEvaluation(
        accession=accession,
        source_evidence_sha256=(
            source_char * 64
        ),
        primary_component_count=primary_count,
        trigger=chromosome.TriggerAssessment(
            triggered=triggered,
            chromosome_component_count=(
                chromosome_count
            ),
            closure_supported_chromosome_count=(
                supported_count
            ),
            closure_unsupported_chromosome_count=(
                unsupported_count
            ),
        ),
        decision=chromosome.ChromosomeIntegrityDecision(
            status=status,
            reason=reason,
            triggered=triggered,
            historical_adjudication_reused=reused,
        ),
    )


def test_population_authenticates_and_filters_stage5_continue():
    rows = [
        stage5_row(
            "GCA_000000001.1",
        ),
        stage5_row(
            "GCA_000000002.1",
            source_char="3",
            fingerprint_char="4",
            status=eligibility.BIOSAMPLE_NONREPRESENTATIVE,
            reason="BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE",
        ),
    ]

    observed, payload = population(
        rows
    )

    assert observed.continue_accessions == (
        "GCA_000000001.1",
    )

    assert observed.biosample_decisions_sha256 == (
        hashlib.sha256(
            payload
        ).hexdigest()
    )

    assert (
        observed.source_evidence_sha256_by_accession
        == {
            "GCA_000000001.1":
                "1" * 64,
        }
    )


def test_population_rejects_unauthenticated_stage5_table():
    payload = stage5_payload(
        [
            stage5_row(
                "GCA_000000001.1",
            )
        ]
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="authenticated Stage 5 completion",
    ):
        monthly.build_monthly_chromosome_population(
            payload,
            expected_biosample_decisions_sha256=(
                "f" * 64
            ),
            release_id="2034.05",
            source_snapshot_id="snapshot",
            origin_git_commit="a" * 40,
        )


def test_population_requires_continue_candidate():
    payload = stage5_payload(
        [
            stage5_row(
                "GCA_000000001.1",
                status=eligibility.BIOSAMPLE_NONREPRESENTATIVE,
                reason="BIOSAMPLE_IDENTICAL_NONREPRESENTATIVE",
            )
        ]
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="no CONTINUE",
    ):
        monthly.build_monthly_chromosome_population(
            payload,
            expected_biosample_decisions_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            release_id="2034.05",
            source_snapshot_id="snapshot",
            origin_git_commit="a" * 40,
        )


def test_nontriggered_pass_builds():
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    assert build.triggered_candidate_count == 0
    assert build.nontriggered_candidate_count == 1
    assert build.historical_adjudication_reuse_count == 0

    assert build.status_counts == {
        chromosome.PASS:
            1,
    }


@pytest.mark.parametrize(
    (
        "status",
        "reason",
    ),
    (
        (
            chromosome.PASS,
            "HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE",
        ),
        (
            chromosome.EXCLUDE,
            "HISTORICAL_FRAGMENTED_CHROMOSOME_SET",
        ),
        (
            chromosome.UNRESOLVED,
            "HISTORICAL_UNRESOLVED",
        ),
    ),
)
def test_reusable_historical_outcomes_are_frozen(
    status,
    reason,
):
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(
                primary_count=2,
                chromosome_count=2,
                supported_count=1,
                unsupported_count=1,
                triggered=True,
                status=status,
                reason=reason,
                reused=True,
            ),
        ),
    )

    assert build.triggered_candidate_count == 1
    assert build.historical_adjudication_reuse_count == 1


@pytest.mark.parametrize(
    "reason",
    (
        "NO_REUSABLE_HISTORICAL_ADJUDICATION",
        "NOT_HISTORICAL_PROJECT_FINCH_PACKAGE",
        "HISTORICAL_CACHE_NOT_VERIFIED",
        "HISTORICAL_ADJUDICATION_ABSENT",
        "HISTORICAL_ACCESSION_MISMATCH",
    ),
)
def test_triggered_nonreused_unresolved_outcomes_are_frozen(
    reason,
):
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(
                primary_count=2,
                chromosome_count=2,
                supported_count=1,
                unsupported_count=1,
                triggered=True,
                status=chromosome.UNRESOLVED,
                reason=reason,
                reused=False,
            ),
        ),
    )

    assert build.triggered_candidate_count == 1
    assert build.historical_adjudication_reuse_count == 0


def test_source_evidence_must_match_authenticated_stage5():
    pop, _ = population()

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="source evidence differs",
    ):
        monthly.build_monthly_chromosome_integrity(
            pop,
            (
                evaluation(
                    source_char="9",
                ),
            ),
        )


def test_population_must_match_exactly_and_in_order():
    rows = [
        stage5_row(
            "GCA_000000001.1",
            source_char="1",
        ),
        stage5_row(
            "GCA_000000002.1",
            source_char="2",
            fingerprint_char="3",
        ),
    ]

    pop, _ = population(
        rows
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="sorted",
    ):
        monthly.build_monthly_chromosome_integrity(
            pop,
            (
                evaluation(
                    "GCA_000000002.1",
                    source_char="2",
                ),
                evaluation(
                    "GCA_000000001.1",
                    source_char="1",
                ),
            ),
        )


def test_trigger_accounting_must_balance():
    pop, _ = population()

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="trigger accounting",
    ):
        monthly.build_monthly_chromosome_integrity(
            pop,
            (
                evaluation(
                    primary_count=2,
                    chromosome_count=2,
                    supported_count=0,
                    unsupported_count=1,
                    triggered=True,
                    status=chromosome.UNRESOLVED,
                    reason="NO_REUSABLE_HISTORICAL_ADJUDICATION",
                ),
            ),
        )


def test_decision_trigger_must_match_trigger_assessment():
    pop, _ = population()

    malformed = (
        execution.Stage3CandidateEvaluation(
            accession="GCA_000000001.1",
            source_evidence_sha256="1" * 64,
            primary_component_count=2,
            trigger=chromosome.TriggerAssessment(
                triggered=True,
                chromosome_component_count=2,
                closure_supported_chromosome_count=1,
                closure_unsupported_chromosome_count=1,
            ),
            decision=chromosome.ChromosomeIntegrityDecision(
                status=chromosome.PASS,
                reason="NO_CHROMOSOME_INTEGRITY_TRIGGER",
                triggered=False,
                historical_adjudication_reused=False,
            ),
        )
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="decision trigger disagrees",
    ):
        monthly.build_monthly_chromosome_integrity(
            pop,
            (
                malformed,
            ),
        )


def test_status_reason_trigger_reuse_combination_is_exact():
    pop, _ = population()

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="combination is not frozen",
    ):
        monthly.build_monthly_chromosome_integrity(
            pop,
            (
                evaluation(
                    primary_count=2,
                    chromosome_count=2,
                    supported_count=1,
                    unsupported_count=1,
                    triggered=True,
                    status=chromosome.PASS,
                    reason="NO_CHROMOSOME_INTEGRITY_TRIGGER",
                ),
            ),
        )


def test_decision_serialization_roundtrip():
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    payload = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    rows = (
        monthly.audit_monthly_chromosome_decisions(
            payload
        )
    )

    assert len(
        rows
    ) == 1

    assert rows[
        0
    ][
        "chromosome_integrity_status"
    ] == chromosome.PASS

    assert payload.endswith(
        b"\n"
    )

    assert not payload.endswith(
        b"\n\n"
    )


def test_decision_audit_rejects_noncanonical_integer():
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    payload = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    corrupted = payload.replace(
        b"\t1\t1\t1\t0\t0\t0\t",
        b"\t01\t1\t1\t0\t0\t0\t",
        1,
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="canonical decimal",
    ):
        monthly.audit_monthly_chromosome_decisions(
            corrupted
        )


def test_record_roundtrip_rebuilds_from_authenticated_inputs():
    pop, stage5_bytes = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    decisions = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    record = (
        monthly.serialize_monthly_chromosome_record(
            build,
            biosample_record_sha256="b" * 64,
            biosample_completion_sha256="c" * 64,
        )
    )

    audited = monthly.audit_monthly_chromosome_record(
        record,
        biosample_decisions_payload=stage5_bytes,
        expected_biosample_decisions_sha256=(
            hashlib.sha256(
                stage5_bytes
            ).hexdigest()
        ),
        release_id="2034.05",
        source_snapshot_id=(
            "bacselect-source-2034.05-"
            "20340501T001700Z"
        ),
        origin_git_commit="a" * 40,
        biosample_record_sha256="b" * 64,
        biosample_completion_sha256="c" * 64,
        decisions_payload=decisions,
    )

    assert audited[
        "schema_version"
    ] == monthly.MONTHLY_CHROMOSOME_RECORD_SCHEMA

    assert audited[
        "status"
    ] == monthly.MONTHLY_CHROMOSOME_STATUS

    assert audited[
        "decision_count"
    ] == 1

    assert audited[
        "triggered_candidate_count"
    ] == 0


def test_record_binds_stage5_record_identity():
    pop, stage5_bytes = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    decisions = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    record = (
        monthly.serialize_monthly_chromosome_record(
            build,
            biosample_record_sha256="b" * 64,
            biosample_completion_sha256="c" * 64,
        )
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="differs from authenticated inputs",
    ):
        monthly.audit_monthly_chromosome_record(
            record,
            biosample_decisions_payload=stage5_bytes,
            expected_biosample_decisions_sha256=(
                hashlib.sha256(
                    stage5_bytes
                ).hexdigest()
            ),
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-"
                "20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
            biosample_record_sha256="d" * 64,
            biosample_completion_sha256="c" * 64,
            decisions_payload=decisions,
        )


def test_record_binds_decision_bytes():
    pop, stage5_bytes = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    decisions = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    record = (
        monthly.serialize_monthly_chromosome_record(
            build,
            biosample_record_sha256="b" * 64,
            biosample_completion_sha256="c" * 64,
        )
    )

    altered = decisions.replace(
        b"NO_CHROMOSOME_INTEGRITY_TRIGGER",
        b"HISTORICAL_RETAIN_CONFIRMED_MULTIPARTITE",
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
    ):
        monthly.audit_monthly_chromosome_record(
            record,
            biosample_decisions_payload=stage5_bytes,
            expected_biosample_decisions_sha256=(
                hashlib.sha256(
                    stage5_bytes
                ).hexdigest()
            ),
            release_id="2034.05",
            source_snapshot_id=(
                "bacselect-source-2034.05-"
                "20340501T001700Z"
            ),
            origin_git_commit="a" * 40,
            biosample_record_sha256="b" * 64,
            biosample_completion_sha256="c" * 64,
            decisions_payload=altered,
        )


def test_record_is_canonical_sorted_json():
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    payload = (
        monthly.serialize_monthly_chromosome_record(
            build,
            biosample_record_sha256="b" * 64,
            biosample_completion_sha256="c" * 64,
        )
    )

    decoded = json.loads(
        payload
    )

    expected = (
        json.dumps(
            decoded,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()

    assert payload == expected

def test_decision_audit_rejects_crlf_input():
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    payload = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    crlf = payload.replace(
        b"\n",
        b"\r\n",
    )

    with pytest.raises(
        monthly.MonthlyChromosomeIntegrityError,
        match="CR bytes",
    ):
        monthly.audit_monthly_chromosome_decisions(
            crlf
        )



def test_decision_audit_rejects_malformed_accessions():
    pop, _ = population()

    build = monthly.build_monthly_chromosome_integrity(
        pop,
        (
            evaluation(),
        ),
    )

    payload = (
        monthly.serialize_monthly_chromosome_decisions(
            build
        )
    )

    valid = b"GCA_000000001.1"

    malformed = (
        b"GCA_000000001",
        b"GCF_000000001.1",
        b"not-an-accession",
        b"",
    )

    for value in malformed:
        corrupted = payload.replace(
            valid,
            value,
            1,
        )

        with pytest.raises(
            monthly.MonthlyChromosomeIntegrityError,
            match="accession",
        ):
            monthly.audit_monthly_chromosome_decisions(
                corrupted
            )
