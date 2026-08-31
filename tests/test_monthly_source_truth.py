from __future__ import annotations

import hashlib
import json

import pytest

from bacselect import monthly_source_truth as monthly
from bacselect import source_truth
from bacselect.source_truth_execution import (
    ContainmentEvidence,
    DuplicateEvidence,
    SourceTruthDecision,
)


RELEASE = (
    "2034.05"
)

SNAPSHOT = (
    "bacselect-source-2034.05-20340501T001700Z"
)

COMMIT = (
    "a" * 40
)

CATALOGUE_SHA = (
    "1" * 64
)

ENTRIES_SHA = (
    "2" * 64
)

METADATA_RECORD_SHA = (
    "3" * 64
)

METADATA_COMPLETION_SHA = (
    "4" * 64
)

A1 = (
    "GCA_000000001.1"
)

A2 = (
    "GCA_000000002.1"
)

A3 = (
    "GCA_000000003.1"
)

B1 = (
    "SAMN00000001"
)

B2 = (
    "SAMN00000002"
)

B3 = (
    "SAMN00000003"
)


def fake_catalogue_record(
    *,
    entries,
):
    return {
        "release_id":
            RELEASE,
        "source_snapshot_id":
            SNAPSHOT,
        "origin_git_commit":
            COMMIT,
        "entries_sha256":
            ENTRIES_SHA,
        "entries":
            list(
                entries
            ),
    }


def entry(
    accession,
    biosample,
    state,
):
    return {
        "canonical_genbank_assembly_accession":
            accession,
        "biosample":
            biosample,
        "origin_sequence_eligibility":
            state,
    }


def population(
    *,
    entries=None,
    metadata=None,
):
    if entries is None:
        entries = (
            entry(
                A1,
                B1,
                "eligible",
            ),
            entry(
                A2,
                B2,
                "ineligible",
            ),
        )

    if metadata is None:
        metadata = {
            A1:
                B1,
            A2:
                B2,
        }

    return monthly._population_from_audited_catalogue(
        fake_catalogue_record(
            entries=entries
        ),
        catalogue_sha256=(
            CATALOGUE_SHA
        ),
        current_metadata=(
            metadata
        ),
        release_id=RELEASE,
        source_snapshot_id=SNAPSHOT,
        origin_git_commit=COMMIT,
    )


def decision(
    accession,
    *,
    status=source_truth.SUITABLE,
    reason="NO_SOURCE_REDUNDANCY",
    duplicates=(),
    containments=(),
):
    return SourceTruthDecision(
        accession=accession,
        source_evidence_sha256=(
            "5" * 64
        ),
        sequence_set_sha256=(
            "6" * 64
        ),
        duplicate_relations=tuple(
            duplicates
        ),
        containment_relations=tuple(
            containments
        ),
        status=status,
        reason=reason,
        explanation="synthetic",
    )


def test_population_partitions_retained_universe():
    observed = population()

    assert observed.retained_accessions == (
        A1,
        A2,
    )

    assert (
        observed.sequence_eligible_accessions
        == (
            A1,
        )
    )

    assert (
        observed.sequence_ineligible_accessions
        == (
            A2,
        )
    )


def test_population_requires_exact_catalogue_coverage():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="lacks complete",
    ):
        population(
            metadata={
                A1:
                    B1,
                A2:
                    B2,
                A3:
                    B3,
            }
        )


def test_population_rejects_catalogue_extra():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="outside current retained metadata",
    ):
        population(
            entries=(
                entry(
                    A1,
                    B1,
                    "eligible",
                ),
                entry(
                    A2,
                    B2,
                    "ineligible",
                ),
                entry(
                    A3,
                    B3,
                    "eligible",
                ),
            )
        )


def test_population_rejects_biosample_drift():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="BioSample differs",
    ):
        population(
            entries=(
                entry(
                    A1,
                    B2,
                    "eligible",
                ),
                entry(
                    A2,
                    B2,
                    "ineligible",
                ),
            )
        )


def test_population_rejects_unknown_sequence_state():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="eligibility state",
    ):
        population(
            entries=(
                entry(
                    A1,
                    B1,
                    "unknown",
                ),
                entry(
                    A2,
                    B2,
                    "ineligible",
                ),
            )
        )


def test_only_sequence_eligible_candidates_receive_source_truth():
    observed = (
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1
                ),
            ),
        )
    )

    assert [
        item.accession
        for item in observed.decisions
    ] == [
        A1
    ]


def test_missing_eligible_decision_fails_closed():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="exactly cover",
    ):
        monthly.build_monthly_source_truth(
            population(),
            (),
        )


def test_ineligible_source_truth_decision_fails_closed():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="exactly cover",
    ):
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1
                ),
                decision(
                    A2
                ),
            ),
        )


def test_nonterminal_source_truth_decision_fails_closed():
    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="non-terminal",
    ):
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1,
                    status="UNKNOWN",
                ),
            ),
        )


def test_decisions_preserve_frozen_serialization():
    build = (
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1
                ),
            ),
        )
    )

    payload = (
        monthly.serialize_monthly_source_truth_decisions(
            build
        )
    )

    rows = (
        monthly.audit_monthly_source_truth_decisions(
            payload
        )
    )

    assert len(
        rows
    ) == 1

    assert rows[
        0
    ][
        "canonical_genbank_assembly_accession"
    ] == A1

    assert rows[
        0
    ][
        "source_truth_status"
    ] == source_truth.SUITABLE


def test_relation_serialization_preserves_duplicate_and_containment():
    duplicate = DuplicateEvidence(
        left_component="CP000001.1",
        right_component="CP000002.1",
        relation="exact",
    )

    containment = ContainmentEvidence(
        inner_component="CP000003.1",
        outer_component="CP000004.1",
        inner_topology="linear",
        outer_topology="circular",
        orientation="forward",
        outer_origin_crossing=True,
    )

    build = (
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1,
                    duplicates=(
                        duplicate,
                    ),
                    containments=(
                        containment,
                    ),
                ),
            ),
        )
    )

    payload = (
        monthly.serialize_monthly_source_truth_relations(
            build
        )
    )

    rows = (
        monthly.audit_monthly_source_truth_relations(
            payload
        )
    )

    assert [
        row[
            "relation_type"
        ]
        for row in rows
    ] == [
        "duplicate",
        "containment",
    ]


def test_record_binds_population_and_manifests():
    build = (
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1
                ),
            ),
        )
    )

    decision_payload = (
        monthly.serialize_monthly_source_truth_decisions(
            build
        )
    )

    relation_payload = (
        monthly.serialize_monthly_source_truth_relations(
            build
        )
    )

    payload = (
        monthly.serialize_monthly_source_truth_record(
            build,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
        )
    )

    record = json.loads(
        payload
    )

    assert record[
        "retained_count"
    ] == 2

    assert record[
        "sequence_eligible_count"
    ] == 1

    assert record[
        "sequence_ineligible_count"
    ] == 1

    assert record[
        "decision_count"
    ] == 1

    assert record[
        "decision_manifest_sha256"
    ] == hashlib.sha256(
        decision_payload
    ).hexdigest()

    assert record[
        "relation_manifest_sha256"
    ] == hashlib.sha256(
        relation_payload
    ).hexdigest()


def test_record_relation_counts_must_match_decisions():
    build = (
        monthly.build_monthly_source_truth(
            population(),
            (
                decision(
                    A1
                ),
            ),
        )
    )

    decisions = (
        monthly.serialize_monthly_source_truth_decisions(
            build
        )
    )

    bad_relations = (
        (
            "\t".join(
                monthly.RELATION_FIELDS
            )
            + "\n"
            + "\t".join(
                (
                    A1,
                    "duplicate",
                    "CP1",
                    "CP2",
                    "",
                    "",
                    "",
                    "",
                    "exact",
                    "",
                )
            )
            + "\n"
        ).encode(
            "ascii"
        )
    )

    decision_rows = (
        monthly.audit_monthly_source_truth_decisions(
            decisions
        )
    )

    relation_rows = (
        monthly.audit_monthly_source_truth_relations(
            bad_relations
        )
    )

    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="duplicate relation count",
    ):
        monthly._record_from_rows(
            build.population,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
            decisions_payload=(
                decisions
            ),
            decision_values=(
                decision_rows
            ),
            relations_payload=(
                bad_relations
            ),
            relation_values=(
                relation_rows
            ),
        )


def test_zero_eligible_population_is_valid():
    observed_population = population(
        entries=(
            entry(
                A1,
                B1,
                "ineligible",
            ),
        ),
        metadata={
            A1:
                B1,
        },
    )

    build = (
        monthly.build_monthly_source_truth(
            observed_population,
            (),
        )
    )

    decisions = (
        monthly.serialize_monthly_source_truth_decisions(
            build
        )
    )

    relations = (
        monthly.serialize_monthly_source_truth_relations(
            build
        )
    )

    assert decisions == (
        b"canonical_genbank_assembly_accession"
        b"\tsource_evidence_sha256"
        b"\tsequence_set_sha256"
        b"\tduplicate_relation_count"
        b"\tcontainment_relation_count"
        b"\tsource_truth_status"
        b"\tsource_truth_reason\n"
    )

    assert relations == (
        b"canonical_genbank_assembly_accession"
        b"\trelation_type"
        b"\tleft_component"
        b"\tright_component"
        b"\tinner_component"
        b"\touter_component"
        b"\tinner_topology"
        b"\touter_topology"
        b"\trelation"
        b"\touter_origin_crossing\n"
    )


def test_public_population_loader_uses_frozen_catalogue_auditor(
    monkeypatch,
):
    calls = []

    monkeypatch.setattr(
        monthly.catalogue_contract,
        "audit_sequence_cache_catalogue",
        lambda payload: (
            calls.append(
                payload
            )
            or fake_catalogue_record(
                entries=(
                    entry(
                        A1,
                        B1,
                        "eligible",
                    ),
                )
            )
        ),
    )

    payload = b"synthetic catalogue\n"

    observed = (
        monthly.build_monthly_source_truth_population(
            payload,
            current_metadata={
                A1:
                    B1,
            },
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
        )
    )

    assert calls == [
        payload
    ]

    assert (
        observed.sequence_eligible_accessions
        == (
            A1,
        )
    )

    assert (
        observed.sequence_cache_catalogue_sha256
        == hashlib.sha256(
            payload
        ).hexdigest()
    )


def test_record_auditor_rederives_current_population(
    monkeypatch,
):
    catalogue_payload = (
        b"synthetic catalogue\n"
    )

    record = fake_catalogue_record(
        entries=(
            entry(
                A1,
                B1,
                "eligible",
            ),
        )
    )

    monkeypatch.setattr(
        monthly.catalogue_contract,
        "audit_sequence_cache_catalogue",
        lambda payload:
            record,
    )

    observed_population = (
        monthly.build_monthly_source_truth_population(
            catalogue_payload,
            current_metadata={
                A1:
                    B1,
            },
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
        )
    )

    build = (
        monthly.build_monthly_source_truth(
            observed_population,
            (
                decision(
                    A1
                ),
            ),
        )
    )

    decisions = (
        monthly.serialize_monthly_source_truth_decisions(
            build
        )
    )

    relations = (
        monthly.serialize_monthly_source_truth_relations(
            build
        )
    )

    payload = (
        monthly.serialize_monthly_source_truth_record(
            build,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
        )
    )

    audited = (
        monthly.audit_monthly_source_truth_record(
            payload,
            catalogue_payload=(
                catalogue_payload
            ),
            current_metadata={
                A1:
                    B1,
            },
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            origin_git_commit=COMMIT,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
            decisions_payload=(
                decisions
            ),
            relations_payload=(
                relations
            ),
        )
    )

    assert audited[
        "status"
    ] == (
        monthly
        .MONTHLY_SOURCE_TRUTH_STATUS
    )


def test_duplicate_relations_must_be_deterministically_ordered():
    payload = (
        (
            "\t".join(
                monthly.RELATION_FIELDS
            )
            + "\n"
            + "\t".join(
                (
                    A1,
                    "duplicate",
                    "CP000002.1",
                    "CP000004.1",
                    "",
                    "",
                    "",
                    "",
                    "exact",
                    "",
                )
            )
            + "\n"
            + "\t".join(
                (
                    A1,
                    "duplicate",
                    "CP000001.1",
                    "CP000005.1",
                    "",
                    "",
                    "",
                    "",
                    "exact",
                    "",
                )
            )
            + "\n"
        ).encode(
            "ascii"
        )
    )

    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="deterministically ordered",
    ):
        monthly.audit_monthly_source_truth_relations(
            payload
        )


def test_containment_relations_must_be_deterministically_ordered():
    payload = (
        (
            "\t".join(
                monthly.RELATION_FIELDS
            )
            + "\n"
            + "\t".join(
                (
                    A1,
                    "containment",
                    "",
                    "",
                    "CP000003.1",
                    "CP000009.1",
                    "linear",
                    "circular",
                    "forward",
                    "0",
                )
            )
            + "\n"
            + "\t".join(
                (
                    A1,
                    "containment",
                    "",
                    "",
                    "CP000002.1",
                    "CP000010.1",
                    "linear",
                    "circular",
                    "forward",
                    "0",
                )
            )
            + "\n"
        ).encode(
            "ascii"
        )
    )

    with pytest.raises(
        monthly.MonthlySourceTruthError,
        match="deterministically ordered",
    ):
        monthly.audit_monthly_source_truth_relations(
            payload
        )
