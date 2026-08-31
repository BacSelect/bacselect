from __future__ import annotations

import json
from pathlib import Path

import pytest

from bacselect.monthly_metadata_eligibility import (
    MONTHLY_METADATA_STATUS,
    MonthlyMetadataEligibilityError,
    assess_monthly_source_metadata,
    audit_metadata_assessments,
    audit_metadata_eligibility_record,
    audit_metadata_summary,
    serialize_metadata_assessments,
    serialize_metadata_eligibility_record,
    serialize_metadata_summary,
)
from bacselect.source_eligibility import (
    EXCLUDE,
    RETAIN,
)


SNAPSHOT = (
    "bacselect-source-2026.09-"
    "20260901T000000Z"
)

SNAPSHOT_SHA = "a" * 64
PARSER_SHA = "b" * 64


def valid_record(
    accession: str,
    biosample: str,
):
    return {
        "accession":
            accession,
        "current_accession":
            accession,
        "source_database":
            "SOURCE_DATABASE_GENBANK",
        "assembly_info": {
            "assembly_status":
                "current",
            "assembly_level":
                "Complete Genome",
            "biosample": {
                "accession":
                    biosample,
            },
        },
    }


def raw_bytes(
    records,
):
    return b"".join(
        (
            json.dumps(
                value,
                sort_keys=False,
                separators=(
                    ",",
                    ":",
                ),
            )
            + "\n"
        ).encode(
            "utf-8"
        )
        for value in records
    )


def example_raw():
    excluded = valid_record(
        "GCA_000000002.1",
        "SAMN2",
    )

    excluded[
        "assembly_info"
    ][
        "atypical"
    ] = {
        "is_atypical": True,
        "warnings": [
            "Contaminated",
        ],
    }

    return raw_bytes(
        (
            excluded,
            valid_record(
                "GCA_000000001.1",
                "SAMN1",
            ),
        )
    )


def bundle():
    raw = example_raw()

    assessments = (
        assess_monthly_source_metadata(
            raw
        )
    )

    assessment_payload = (
        serialize_metadata_assessments(
            assessments
        )
    )

    summary_payload = (
        serialize_metadata_summary(
            assessments
        )
    )

    return (
        raw,
        assessment_payload,
        summary_payload,
    )


def test_exact_raw_source_is_assessed_and_sorted():
    observed = (
        assess_monthly_source_metadata(
            example_raw()
        )
    )

    assert [
        value.accession
        for value in observed
    ] == [
        "GCA_000000001.1",
        "GCA_000000002.1",
    ]

    assert observed[
        0
    ].decision == RETAIN

    assert observed[
        1
    ].decision == EXCLUDE


def test_invalid_raw_json_fails_closed():
    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="invalid JSON",
    ):
        assess_monthly_source_metadata(
            b'{"accession":\n'
        )


def test_duplicate_raw_accession_fails_closed():
    record = valid_record(
        "GCA_000000001.1",
        "SAMN1",
    )

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="assessment failed",
    ):
        assess_monthly_source_metadata(
            raw_bytes(
                (
                    record,
                    record,
                )
            )
        )


def test_assessment_jsonl_is_canonical_deterministic_and_sorted():
    assessments = list(
        assess_monthly_source_metadata(
            example_raw()
        )
    )

    first = (
        serialize_metadata_assessments(
            assessments
        )
    )

    second = (
        serialize_metadata_assessments(
            tuple(
                reversed(
                    assessments
                )
            )
        )
    )

    assert first == second
    assert first.endswith(
        b"\n"
    )

    assert [
        value.accession
        for value in audit_metadata_assessments(
            first
        )
    ] == [
        "GCA_000000001.1",
        "GCA_000000002.1",
    ]


def test_assessment_jsonl_refuses_noncanonical_row():
    assessments = (
        assess_monthly_source_metadata(
            example_raw()
        )
    )

    payload = (
        serialize_metadata_assessments(
            assessments
        )
    )

    record = json.loads(
        payload.splitlines()[
            0
        ]
    )

    mutated = (
        json.dumps(
            record,
            sort_keys=True,
            separators=(
                ", ",
                ": ",
            ),
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="canonical",
    ):
        audit_metadata_assessments(
            mutated
        )


def test_assessment_jsonl_refuses_unsorted_rows():
    assessments = (
        assess_monthly_source_metadata(
            example_raw()
        )
    )

    payload = (
        serialize_metadata_assessments(
            assessments
        )
    )

    lines = payload.splitlines(
        keepends=True
    )

    mutated = (
        lines[
            1
        ]
        + lines[
            0
        ]
    )

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="sorted",
    ):
        audit_metadata_assessments(
            mutated
        )


def test_summary_is_blinded_and_exact():
    raw, assessments, _ = bundle()

    del raw

    values = (
        audit_metadata_assessments(
            assessments
        )
    )

    payload = (
        serialize_metadata_summary(
            values
        )
    )

    text = payload.decode(
        "ascii"
    )

    assert "GCA_" not in text
    assert "SAMN" not in text

    record = json.loads(
        payload
    )

    assert record[
        "records"
    ] == 2

    assert record[
        "decision_counts"
    ][
        RETAIN
    ] == 1

    assert record[
        "decision_counts"
    ][
        EXCLUDE
    ] == 1


def test_summary_audit_refuses_derived_tamper():
    _, assessments, summary = (
        bundle()
    )

    record = json.loads(
        summary
    )

    record[
        "records"
    ] += 1

    mutated = (
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="derived identity",
    ):
        audit_metadata_summary(
            mutated,
            assessments_payload=(
                assessments
            ),
        )


def test_record_binds_stage1_raw_parser_and_counts():
    raw, assessments, summary = (
        bundle()
    )

    payload = (
        serialize_metadata_eligibility_record(
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            raw_response=raw,
            assessments_payload=(
                assessments
            ),
            summary_payload=summary,
            source_eligibility_sha256=(
                PARSER_SHA
            ),
        )
    )

    record = json.loads(
        payload
    )

    assert record[
        "status"
    ] == MONTHLY_METADATA_STATUS

    assert record[
        "assessment_count"
    ] == 2

    assert record[
        "retained_count"
    ] == 1

    assert record[
        "excluded_count"
    ] == 1

    assert record[
        "source_eligibility_sha256"
    ] == PARSER_SHA


def test_record_is_canonical_deterministic_and_auditable():
    raw, assessments, summary = (
        bundle()
    )

    kwargs = {
        "source_snapshot_id":
            SNAPSHOT,
        "source_snapshot_record_sha256":
            SNAPSHOT_SHA,
        "raw_response":
            raw,
        "assessments_payload":
            assessments,
        "summary_payload":
            summary,
        "source_eligibility_sha256":
            PARSER_SHA,
    }

    first = (
        serialize_metadata_eligibility_record(
            **kwargs
        )
    )

    second = (
        serialize_metadata_eligibility_record(
            **kwargs
        )
    )

    assert first == second

    audited = (
        audit_metadata_eligibility_record(
            first,
            **kwargs,
        )
    )

    assert audited[
        "source_snapshot_id"
    ] == SNAPSHOT


def test_record_refuses_raw_source_tamper():
    raw, assessments, summary = (
        bundle()
    )

    changed = valid_record(
        "GCA_000000001.1",
        "SAMN999",
    )

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="exact raw",
    ):
        serialize_metadata_eligibility_record(
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            raw_response=raw_bytes(
                (
                    changed,
                )
            ),
            assessments_payload=(
                assessments
            ),
            summary_payload=summary,
            source_eligibility_sha256=(
                PARSER_SHA
            ),
        )


def test_record_refuses_assessment_tamper():
    raw, assessments, summary = (
        bundle()
    )

    lines = assessments.splitlines(
        keepends=True
    )

    mutated = lines[
        0
    ]

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="exact raw",
    ):
        serialize_metadata_eligibility_record(
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            raw_response=raw,
            assessments_payload=(
                mutated
            ),
            summary_payload=summary,
            source_eligibility_sha256=(
                PARSER_SHA
            ),
        )


def test_invalid_parser_sha_fails_closed():
    raw, assessments, summary = (
        bundle()
    )

    with pytest.raises(
        MonthlyMetadataEligibilityError,
        match="implementation SHA256",
    ):
        serialize_metadata_eligibility_record(
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            raw_response=raw,
            assessments_payload=(
                assessments
            ),
            summary_payload=summary,
            source_eligibility_sha256=(
                "bad"
            ),
        )


def test_contract_is_pure_and_history_free():
    module = (
        Path(
            __file__
        ).resolve().parents[
            1
        ]
        / "src"
        / "bacselect"
        / "monthly_metadata_eligibility.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "requests",
        "urllib",
        "urlopen",
        "http.client",
        "subprocess",
        "/NGS/",
        "Rhys_wkdir",
        "Project Finch",
        "SLURM_",
        "sbatch",
        "srun",
        "70_477",
        "55_151",
        "15_326",
    ):
        assert token not in module
