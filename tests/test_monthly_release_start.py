"""Synthetic tests for BacSelect monthly release-start/source-snapshot primitives."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bacselect.monthly_release_start import (
    ARCHITECTURE_SCHEMA_VERSION,
    FORBIDDEN_HISTORICAL_BINDINGS,
    RELEASE_START_KEYS,
    RELEASE_START_SCHEMA_VERSION,
    RELEASE_START_STATUS,
    SELECTOR,
    SELECTOR_VERSION,
    SOURCE_QUERY_SPECIFICATION,
    SOURCE_SNAPSHOT_KEYS,
    SOURCE_SNAPSHOT_SCHEMA_VERSION,
    SOURCE_SNAPSHOT_STATUS,
    MonthlyReleaseStartError,
    audit_release_start_checkpoint,
    audit_source_query_specification,
    audit_source_snapshot_record,
    build_release_start_payload,
    canonical_json_bytes,
    derive_release_id,
    parse_utc_timestamp,
    require_current_assembly_status,
    serialize_release_start_checkpoint,
    serialize_source_snapshot_record,
    sha256_bytes,
    source_query_specification,
    source_snapshot_id_from_start,
    validate_canonical_gca,
    validate_query_command,
    validate_release_id,
)


COMMIT = "a" * 40
ENV_SHA = "b" * 64
DATASETS_VERSION = "18.35.0"

START = "2026-09-01T00:00:00Z"
QUERY_START = "2026-09-01T00:00:01Z"
QUERY_END = "2026-09-01T00:01:00Z"

COMMAND = (
    "datasets",
    "summary",
    "genome",
    "taxon",
    "Bacteria",
)

RAW_RESPONSE = (
    b'{"accession":"GCA_900000001.1"}\n'
)


def checkpoint() -> bytes:
    return serialize_release_start_checkpoint(
        snapshot_start_utc=START,
        expected_git_commit=COMMIT,
        ncbi_datasets_version=DATASETS_VERSION,
        ncbi_datasets_environment_sha256=ENV_SHA,
    )


def snapshot_record() -> bytes:
    return serialize_source_snapshot_record(
        release_start_checkpoint=checkpoint(),
        source_query_started_utc=QUERY_START,
        source_query_completed_utc=QUERY_END,
        source_query_command=COMMAND,
        raw_response=RAW_RESPONSE,
    )


def mutate_json(
    payload: bytes,
    key: str,
    value,
) -> bytes:
    record = json.loads(
        payload.decode(
            "utf-8"
        )
    )

    record[
        key
    ] = value

    return canonical_json_bytes(
        record
    )


def test_day_one_release_start_is_valid() -> None:
    assert derive_release_id(
        START
    ) == "2026.09"


def test_day_two_release_start_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="UTC day 01",
    ):
        derive_release_id(
            "2026-09-02T00:00:00Z"
        )


def test_release_id_is_derived_from_utc_year_and_month() -> None:
    assert derive_release_id(
        "2031-12-01T23:59:59Z"
    ) == "2031.12"


def test_offset_timestamp_is_not_canonical_utc() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="YYYY-MM-DDTHH:MM:SSZ",
    ):
        parse_utc_timestamp(
            "2026-09-01T12:00:00+12:00",
            label="test timestamp",
        )


def test_fractional_second_timestamp_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
    ):
        parse_utc_timestamp(
            "2026-09-01T00:00:00.000Z",
            label="test timestamp",
        )


def test_impossible_calendar_timestamp_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="not a valid UTC timestamp",
    ):
        parse_utc_timestamp(
            "2026-02-30T00:00:00Z",
            label="test timestamp",
        )


def test_release_id_syntax_accepts_valid_month() -> None:
    assert validate_release_id(
        "2026.09"
    ) == "2026.09"


def test_release_id_invalid_month_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="invalid month",
    ):
        validate_release_id(
            "2026.13"
        )


def test_source_query_specification_is_exact() -> None:
    assert source_query_specification() == {
        "accession_prefix":
            "GCA_",
        "assembly_level":
            "Complete Genome",
        "assembly_source":
            "GenBank",
        "assembly_status_required":
            "current",
        "assembly_version":
            "current",
        "exclude_mags":
            True,
        "exclude_multi_isolate":
            True,
        "taxon":
            "Bacteria",
    }


def test_source_query_specification_copy_is_independent() -> None:
    observed = source_query_specification()

    observed[
        "taxon"
    ] = "Archaea"

    assert SOURCE_QUERY_SPECIFICATION[
        "taxon"
    ] == "Bacteria"


def test_changed_source_query_specification_is_refused() -> None:
    changed = source_query_specification()

    changed[
        "assembly_version"
    ] = "all"

    with pytest.raises(
        MonthlyReleaseStartError,
        match="specification changed",
    ):
        audit_source_query_specification(
            changed
        )


def test_release_start_payload_has_exact_schema() -> None:
    record = build_release_start_payload(
        snapshot_start_utc=START,
        expected_git_commit=COMMIT,
        ncbi_datasets_version=DATASETS_VERSION,
        ncbi_datasets_environment_sha256=ENV_SHA,
    )

    assert set(
        record
    ) == RELEASE_START_KEYS

    assert record[
        "schema_version"
    ] == RELEASE_START_SCHEMA_VERSION

    assert record[
        "status"
    ] == RELEASE_START_STATUS

    assert record[
        "release_id"
    ] == "2026.09"


def test_release_start_checkpoint_is_canonical_json() -> None:
    payload = checkpoint()

    parsed = json.loads(
        payload.decode(
            "utf-8"
        )
    )

    assert canonical_json_bytes(
        parsed
    ) == payload


def test_release_start_checkpoint_has_exact_final_newline() -> None:
    payload = checkpoint()

    assert payload.endswith(
        b"\n"
    )

    assert not payload.endswith(
        b"\n\n"
    )


def test_release_start_checkpoint_audit_passes() -> None:
    record = audit_release_start_checkpoint(
        checkpoint(),
        expected_git_commit=COMMIT,
    )

    assert record[
        "selector"
    ] == SELECTOR

    assert record[
        "selector_version"
    ] == SELECTOR_VERSION

    assert record[
        "architecture_schema_version"
    ] == ARCHITECTURE_SCHEMA_VERSION


def test_malformed_release_start_json_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="valid JSON",
    ):
        audit_release_start_checkpoint(
            b"{bad-json}\n"
        )


def test_noncanonical_release_start_json_is_refused() -> None:
    payload = json.dumps(
        json.loads(
            checkpoint().decode(
                "utf-8"
            )
        )
    ).encode(
        "utf-8"
    ) + b"\n"

    with pytest.raises(
        MonthlyReleaseStartError,
        match="canonically serialized",
    ):
        audit_release_start_checkpoint(
            payload
        )


def test_mutated_release_identifier_is_refused() -> None:
    payload = mutate_json(
        checkpoint(),
        "release_id",
        "2026.10",
    )

    with pytest.raises(
        MonthlyReleaseStartError,
        match="does not match",
    ):
        audit_release_start_checkpoint(
            payload
        )


def test_mutated_selector_is_refused() -> None:
    payload = mutate_json(
        checkpoint(),
        "selector",
        "SR",
    )

    with pytest.raises(
        MonthlyReleaseStartError,
        match="exactly OPS",
    ):
        audit_release_start_checkpoint(
            payload
        )


def test_mutated_architecture_schema_is_refused() -> None:
    payload = mutate_json(
        checkpoint(),
        "architecture_schema_version",
        2,
    )

    with pytest.raises(
        MonthlyReleaseStartError,
        match="architecture",
    ):
        audit_release_start_checkpoint(
            payload
        )


def test_expected_commit_mismatch_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="Git commit mismatch",
    ):
        audit_release_start_checkpoint(
            checkpoint(),
            expected_git_commit=(
                "c" * 40
            ),
        )


def test_empty_datasets_version_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="single-line",
    ):
        serialize_release_start_checkpoint(
            snapshot_start_utc=START,
            expected_git_commit=COMMIT,
            ncbi_datasets_version="",
            ncbi_datasets_environment_sha256=ENV_SHA,
        )


def test_invalid_environment_hash_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="lowercase SHA256",
    ):
        serialize_release_start_checkpoint(
            snapshot_start_utc=START,
            expected_git_commit=COMMIT,
            ncbi_datasets_version=DATASETS_VERSION,
            ncbi_datasets_environment_sha256="not-a-hash",
        )


def test_historical_snapshot_binding_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="historical validation binding",
    ):
        serialize_release_start_checkpoint(
            snapshot_start_utc=START,
            expected_git_commit=COMMIT,
            ncbi_datasets_version=(
                FORBIDDEN_HISTORICAL_BINDINGS[
                    0
                ]
            ),
            ncbi_datasets_environment_sha256=ENV_SHA,
        )


def test_source_snapshot_id_is_deterministic() -> None:
    assert source_snapshot_id_from_start(
        START
    ) == (
        "bacselect-source-2026.09-"
        "20260901T000000Z"
    )


def test_query_command_is_validated_as_argument_vector() -> None:
    assert validate_query_command(
        COMMAND
    ) == COMMAND


def test_empty_query_command_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="must not be empty",
    ):
        validate_query_command(
            ()
        )


def test_string_query_command_is_refused() -> None:
    with pytest.raises(
        TypeError,
        match="sequence",
    ):
        validate_query_command(
            "datasets summary"
        )


def test_nonstring_query_argument_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="single-line",
    ):
        validate_query_command(
            (
                "datasets",
                7,
            )
        )


def test_historical_command_binding_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="historical validation binding",
    ):
        validate_query_command(
            (
                "datasets",
                FORBIDDEN_HISTORICAL_BINDINGS[
                    1
                ],
            )
        )


def test_source_query_cannot_start_before_checkpoint_time() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="cannot start before",
    ):
        serialize_source_snapshot_record(
            release_start_checkpoint=checkpoint(),
            source_query_started_utc=(
                "2026-08-31T23:59:59Z"
            ),
            source_query_completed_utc=QUERY_END,
            source_query_command=COMMAND,
            raw_response=RAW_RESPONSE,
        )


def test_source_query_completion_cannot_precede_start() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="cannot precede",
    ):
        serialize_source_snapshot_record(
            release_start_checkpoint=checkpoint(),
            source_query_started_utc=QUERY_END,
            source_query_completed_utc=QUERY_START,
            source_query_command=COMMAND,
            raw_response=RAW_RESPONSE,
        )


def test_empty_raw_source_response_is_refused() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="must not be empty",
    ):
        serialize_source_snapshot_record(
            release_start_checkpoint=checkpoint(),
            source_query_started_utc=QUERY_START,
            source_query_completed_utc=QUERY_END,
            source_query_command=COMMAND,
            raw_response=b"",
        )


def test_source_snapshot_record_has_exact_schema() -> None:
    record = json.loads(
        snapshot_record().decode(
            "utf-8"
        )
    )

    assert set(
        record
    ) == SOURCE_SNAPSHOT_KEYS

    assert record[
        "schema_version"
    ] == SOURCE_SNAPSHOT_SCHEMA_VERSION

    assert record[
        "status"
    ] == SOURCE_SNAPSHOT_STATUS


def test_source_snapshot_record_is_canonical_json() -> None:
    payload = snapshot_record()

    assert canonical_json_bytes(
        json.loads(
            payload.decode(
                "utf-8"
            )
        )
    ) == payload


def test_source_snapshot_binds_release_start_checkpoint_hash() -> None:
    record = audit_source_snapshot_record(
        snapshot_record(),
        release_start_checkpoint=checkpoint(),
        raw_response=RAW_RESPONSE,
    )

    assert record[
        "release_start_checkpoint_sha256"
    ] == sha256_bytes(
        checkpoint()
    )


def test_source_snapshot_binds_raw_response_hash_and_bytes() -> None:
    record = audit_source_snapshot_record(
        snapshot_record(),
        release_start_checkpoint=checkpoint(),
        raw_response=RAW_RESPONSE,
    )

    assert record[
        "raw_response_sha256"
    ] == sha256_bytes(
        RAW_RESPONSE
    )

    assert record[
        "raw_response_bytes"
    ] == len(
        RAW_RESPONSE
    )


def test_changed_raw_response_is_refused_by_audit() -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="SHA256 mismatch",
    ):
        audit_source_snapshot_record(
            snapshot_record(),
            release_start_checkpoint=checkpoint(),
            raw_response=(
                RAW_RESPONSE
                + b"x"
            ),
        )


def test_changed_release_start_checkpoint_is_refused() -> None:
    other_checkpoint = serialize_release_start_checkpoint(
        snapshot_start_utc=START,
        expected_git_commit=(
            "d" * 40
        ),
        ncbi_datasets_version=DATASETS_VERSION,
        ncbi_datasets_environment_sha256=ENV_SHA,
    )

    with pytest.raises(
        MonthlyReleaseStartError,
        match="checkpoint fingerprint changed",
    ):
        audit_source_snapshot_record(
            snapshot_record(),
            release_start_checkpoint=other_checkpoint,
            raw_response=RAW_RESPONSE,
        )


def test_mutated_source_snapshot_release_id_is_refused() -> None:
    payload = mutate_json(
        snapshot_record(),
        "release_id",
        "2026.10",
    )

    with pytest.raises(
        MonthlyReleaseStartError,
        match="inherited binding changed",
    ):
        audit_source_snapshot_record(
            payload,
            release_start_checkpoint=checkpoint(),
            raw_response=RAW_RESPONSE,
        )


def test_mutated_source_snapshot_identifier_is_refused() -> None:
    payload = mutate_json(
        snapshot_record(),
        "source_snapshot_id",
        "wrong",
    )

    with pytest.raises(
        MonthlyReleaseStartError,
        match="identifier changed",
    ):
        audit_source_snapshot_record(
            payload,
            release_start_checkpoint=checkpoint(),
            raw_response=RAW_RESPONSE,
        )


def test_current_assembly_status_is_accepted() -> None:
    assert require_current_assembly_status(
        "current"
    ) == "current"


@pytest.mark.parametrize(
    "status",
    (
        "previous",
        "suppressed",
        "retired",
        "latest",
        "",
        None,
    ),
)
def test_noncurrent_assembly_status_is_refused(
    status,
) -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="exactly current",
    ):
        require_current_assembly_status(
            status
        )


def test_canonical_gca_accession_is_accepted() -> None:
    assert validate_canonical_gca(
        "GCA_123456789.2"
    ) == "GCA_123456789.2"


@pytest.mark.parametrize(
    "accession",
    (
        "GCF_123456789.2",
        "GCA_123456789",
        "GCA_x.1",
        "",
        None,
    ),
)
def test_noncanonical_gca_accession_is_refused(
    accession,
) -> None:
    with pytest.raises(
        MonthlyReleaseStartError,
        match="canonical GCA",
    ):
        validate_canonical_gca(
            accession
        )


def test_unit_test_contains_no_real_monthly_snapshot_path() -> None:
    source = Path(
        __file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/"
        + "NGS"
        + "/",
        "bacselect/monthly/"
        + "2026.09",
        "snapshot-"
        + "20260825T132821Z",
        "external-decision-"
        + "holdout",
    )

    for token in forbidden:
        assert token not in source
