from __future__ import annotations

import hashlib
import json

import pytest

from bacselect import monthly_release_start
from bacselect import monthly_taxonomy_snapshot as module


COMMIT = (
    "a" * 40
)

SOURCE_RECORD_SHA = None


def canonical_json(
    value,
):
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def source_record(
    *,
    release_id="2026.09",
    snapshot_start="2026-09-01T00:17:00Z",
    commit=COMMIT,
):
    return {
        "architecture_schema_version":
            monthly_release_start
            .ARCHITECTURE_SCHEMA_VERSION,
        "expected_git_commit":
            commit,
        "ncbi_datasets_environment_sha256":
            "1" * 64,
        "ncbi_datasets_version":
            "18.35.0",
        "raw_response_bytes":
            100,
        "raw_response_sha256":
            "2" * 64,
        "release_id":
            release_id,
        "release_start_checkpoint_sha256":
            "3" * 64,
        "schema_version":
            monthly_release_start
            .SOURCE_SNAPSHOT_SCHEMA_VERSION,
        "selector":
            monthly_release_start.SELECTOR,
        "selector_version":
            monthly_release_start
            .SELECTOR_VERSION,
        "snapshot_start_utc":
            snapshot_start,
        "source_query_command":
            [
                "datasets",
                "summary",
                "genome",
                "taxon",
                "2",
            ],
        "source_query_completed_utc":
            "2026-09-01T00:18:00Z",
        "source_query_specification":
            {},
        "source_query_started_utc":
            "2026-09-01T00:17:01Z",
        "source_snapshot_id":
            (
                monthly_release_start
                .source_snapshot_id_from_start(
                    snapshot_start
                )
            ),
        "status":
            monthly_release_start
            .SOURCE_SNAPSHOT_STATUS,
    }


def source_payload(
    **kwargs,
):
    return canonical_json(
        source_record(
            **kwargs
        )
    )


def source_context():
    payload = source_payload()

    return (
        module
        .build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=(
                COMMIT
            ),
        )
    )


def evidence(
    **overrides,
):
    values = {
        "acquisition_started_utc":
            "2026-09-01T00:30:00Z",
        "acquisition_completed_utc":
            "2026-09-01T00:31:00Z",
        "requested_url":
            module.TAXONOMY_URL,
        "final_url":
            module.TAXONOMY_URL,
        "archive_sha256":
            "4" * 64,
        "archive_size_bytes":
            1000,
        "nodes_sha256":
            "5" * 64,
        "nodes_size_bytes":
            500,
        "merged_sha256":
            "6" * 64,
        "merged_size_bytes":
            200,
        "delnodes_sha256":
            "7" * 64,
        "delnodes_size_bytes":
            100,
        "acquisition_provenance_sha256":
            "8" * 64,
        "content_manifest_sha256":
            "9" * 64,
        "acquisition_implementation_sha256":
            "b" * 64,
        "source_taxonomy_sha256":
            module.SOURCE_TAXONOMY_SHA256,
    }

    values.update(
        overrides
    )

    return (
        module
        .MonthlyTaxonomyAcquisitionEvidence(
            **values
        )
    )


def valid_build():
    return (
        module
        .build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(),
        )
    )


def test_source_context_binds_exact_record_sha():
    payload = source_payload()

    observed = (
        module
        .build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=(
                COMMIT
            ),
        )
    )

    assert observed.release_id == "2026.09"

    assert observed.source_snapshot_id == (
        monthly_release_start
        .source_snapshot_id_from_start(
            "2026-09-01T00:17:00Z"
        )
    )

    assert (
        observed.source_raw_response_sha256
        == "2" * 64
    )


def test_source_context_rejects_record_sha_mismatch():
    payload = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="record SHA256 mismatch",
    ):
        module.build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                "f" * 64
            ),
            origin_git_commit=(
                COMMIT
            ),
        )


def test_source_context_rejects_wrong_schema():
    record = source_record()

    record[
        "schema_version"
    ] = "wrong"

    payload = canonical_json(
        record
    )

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="schema version changed",
    ):
        module.build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_source_context_rejects_extra_field():
    record = source_record()

    record[
        "unexpected"
    ] = True

    payload = canonical_json(
        record
    )

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="record schema changed",
    ):
        module.build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_source_context_rejects_wrong_origin_commit():
    payload = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="Git commit differs",
    ):
        module.build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=(
                "c" * 40
            ),
        )


def test_source_context_rejects_wrong_source_snapshot_id():
    record = source_record()

    record[
        "source_snapshot_id"
    ] = (
        "bacselect-source-2026.09-"
        "20260901T001701Z"
    )

    payload = canonical_json(
        record
    )

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="does not match its frozen start",
    ):
        module.build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_source_context_rejects_timestamp_order():
    record = source_record()

    record[
        "source_query_started_utc"
    ] = "2026-09-01T00:20:00Z"

    record[
        "source_query_completed_utc"
    ] = "2026-09-01T00:19:00Z"

    payload = canonical_json(
        record
    )

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="timestamps are out of order",
    ):
        module.build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    payload
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_snapshot_id_depends_on_release_start_and_content():
    first = (
        module.taxonomy_snapshot_id_from_evidence(
            release_id="2026.09",
            acquisition_started_utc=(
                "2026-09-01T00:30:00Z"
            ),
            archive_sha256="4" * 64,
        )
    )

    assert first.startswith(
        "bacselect-taxonomy-2026.09-"
        "20260901T003000Z-"
    )

    assert first.endswith(
        "4" * 64
    )

    assert first != (
        module.taxonomy_snapshot_id_from_evidence(
            release_id="2026.10",
            acquisition_started_utc=(
                "2026-10-01T00:30:00Z"
            ),
            archive_sha256="4" * 64,
        )
    )

    assert first != (
        module.taxonomy_snapshot_id_from_evidence(
            release_id="2026.09",
            acquisition_started_utc=(
                "2026-09-01T00:30:01Z"
            ),
            archive_sha256="4" * 64,
        )
    )

    assert first != (
        module.taxonomy_snapshot_id_from_evidence(
            release_id="2026.09",
            acquisition_started_utc=(
                "2026-09-01T00:30:00Z"
            ),
            archive_sha256="5" * 64,
        )
    )


def test_valid_build_binds_frozen_resolver():
    observed = valid_build()

    assert (
        observed.evidence.source_taxonomy_sha256
        == module.SOURCE_TAXONOMY_SHA256
    )


def test_wrong_resolver_identity_fails_closed():
    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="resolver identity changed",
    ):
        module.build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(
                source_taxonomy_sha256=(
                    "f" * 64
                ),
            ),
        )


def test_taxonomy_requested_url_is_exact():
    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="requested URL changed",
    ):
        module.build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(
                requested_url=(
                    "https://example.invalid/"
                    "new_taxdump.tar.gz"
                ),
            ),
        )


def test_taxonomy_final_url_must_remain_https():
    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="final URL must use HTTPS",
    ):
        module.build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(
                final_url=(
                    "http://example.invalid/"
                    "new_taxdump.tar.gz"
                ),
            ),
        )


def test_taxonomy_completion_cannot_precede_start():
    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="completion precedes start",
    ):
        module.build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(
                acquisition_completed_utc=(
                    "2026-09-01T00:29:59Z"
                ),
            ),
        )


@pytest.mark.parametrize(
    "field",
    [
        "archive_size_bytes",
        "nodes_size_bytes",
        "merged_size_bytes",
        "delnodes_size_bytes",
    ],
)
def test_taxonomy_content_sizes_must_be_positive(
    field,
):
    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="positive integer",
    ):
        module.build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(
                **{
                    field:
                        0,
                }
            ),
        )


@pytest.mark.parametrize(
    "field",
    [
        "archive_sha256",
        "nodes_sha256",
        "merged_sha256",
        "delnodes_sha256",
        "acquisition_provenance_sha256",
        "content_manifest_sha256",
        "acquisition_implementation_sha256",
    ],
)
def test_taxonomy_hashes_must_be_canonical(
    field,
):
    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="lowercase SHA256",
    ):
        module.build_monthly_taxonomy_snapshot(
            source_context(),
            evidence(
                **{
                    field:
                        "INVALID",
                }
            ),
        )


def test_record_roundtrip_is_byte_deterministic():
    build = valid_build()

    payload = (
        module
        .serialize_monthly_taxonomy_snapshot_record(
            build
        )
    )

    source = source_payload()

    observed = (
        module
        .audit_monthly_taxonomy_snapshot_record(
            payload,
            source_snapshot_record_payload=(
                source
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    source
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )
    )

    assert payload == canonical_json(
        observed
    )


def test_record_binds_current_source_snapshot():
    record = json.loads(
        module
        .serialize_monthly_taxonomy_snapshot_record(
            valid_build()
        )
    )

    source = source_context()

    assert (
        record[
            "release_id"
        ]
        == source.release_id
    )

    assert (
        record[
            "source_snapshot_id"
        ]
        == source.source_snapshot_id
    )

    assert (
        record[
            "source_snapshot_record_sha256"
        ]
        == source.source_snapshot_record_sha256
    )

    assert (
        record[
            "source_raw_response_sha256"
        ]
        == source.source_raw_response_sha256
    )


def test_record_has_no_downstream_results():
    record = json.loads(
        module
        .serialize_monthly_taxonomy_snapshot_record(
            valid_build()
        )
    )

    assert (
        record[
            "taxonomy_resolution_performed"
        ]
        is False
    )

    assert (
        record[
            "structural_features_calculated"
        ]
        is False
    )

    assert (
        record[
            "selector_outcomes_calculated"
        ]
        is False
    )


def test_record_rejects_taxonomy_resolution_true():
    payload = (
        module
        .serialize_monthly_taxonomy_snapshot_record(
            valid_build()
        )
    )

    record = json.loads(
        payload
    )

    record[
        "taxonomy_resolution_performed"
    ] = True

    changed = canonical_json(
        record
    )

    source = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="must remain false",
    ):
        module.audit_monthly_taxonomy_snapshot_record(
            changed,
            source_snapshot_record_payload=(
                source
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    source
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_record_rejects_changed_snapshot_id():
    payload = (
        module
        .serialize_monthly_taxonomy_snapshot_record(
            valid_build()
        )
    )

    record = json.loads(
        payload
    )

    record[
        "taxonomy_snapshot_id"
    ] = "wrong"

    changed = canonical_json(
        record
    )

    source = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="differs from reconstructed contract",
    ):
        module.audit_monthly_taxonomy_snapshot_record(
            changed,
            source_snapshot_record_payload=(
                source
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    source
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_record_rejects_extra_field():
    payload = (
        module
        .serialize_monthly_taxonomy_snapshot_record(
            valid_build()
        )
    )

    record = json.loads(
        payload
    )

    record[
        "unexpected"
    ] = 1

    changed = canonical_json(
        record
    )

    source = source_payload()

    with pytest.raises(
        module.MonthlyTaxonomySnapshotError,
        match="record schema changed",
    ):
        module.audit_monthly_taxonomy_snapshot_record(
            changed,
            source_snapshot_record_payload=(
                source
            ),
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    source
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )


def test_same_taxonomy_content_does_not_substitute_across_release():
    september_source = source_context()

    september = (
        module
        .build_monthly_taxonomy_snapshot(
            september_source,
            evidence(),
        )
    )

    october_payload = source_payload(
        release_id="2026.10",
        snapshot_start=(
            "2026-10-01T00:17:00Z"
        ),
    )

    october_record = json.loads(
        october_payload
    )

    october_record[
        "source_query_started_utc"
    ] = "2026-10-01T00:17:01Z"

    october_record[
        "source_query_completed_utc"
    ] = "2026-10-01T00:18:00Z"

    october_payload = canonical_json(
        october_record
    )

    october_source = (
        module
        .build_monthly_taxonomy_source_context(
            october_payload,
            expected_source_snapshot_record_sha256=(
                hashlib.sha256(
                    october_payload
                ).hexdigest()
            ),
            origin_git_commit=COMMIT,
        )
    )

    october_evidence = evidence(
        acquisition_started_utc=(
            "2026-10-01T00:30:00Z"
        ),
        acquisition_completed_utc=(
            "2026-10-01T00:31:00Z"
        ),
    )

    october = (
        module
        .build_monthly_taxonomy_snapshot(
            october_source,
            october_evidence,
        )
    )

    assert (
        september.evidence.archive_sha256
        == october.evidence.archive_sha256
    )

    assert (
        september.taxonomy_snapshot_id
        != october.taxonomy_snapshot_id
    )


def test_pure_contract_contains_no_historical_source_binding():
    text = open(
        module.__file__,
        encoding="utf-8",
    ).read()

    for token in (
        "SOURCE_SNAPSHOT_ID",
        "SOURCE_SNAPSHOT_COMMIT",
        "SOURCE_RAW_SHA256",
        "SOURCE_ACQUISITION_SHA256",
        "acquire_taxonomy_snapshot",
        "Project Finch",
        "/NGS/",
    ):
        assert token not in text

def test_source_context_is_binding_layer_not_stage1_provenance_authority():
    """The executor, not this pure layer, authenticates canonical Stage 1."""

    record = source_record()

    record[
        "source_query_command"
    ] = [
        "synthetic",
        "changed",
        "command",
    ]

    record[
        "source_query_specification"
    ] = {
        "synthetic":
            "changed",
    }

    payload = canonical_json(
        record
    )

    supplied_sha = hashlib.sha256(
        payload
    ).hexdigest()

    observed = (
        module
        .build_monthly_taxonomy_source_context(
            payload,
            expected_source_snapshot_record_sha256=(
                supplied_sha
            ),
            origin_git_commit=COMMIT,
        )
    )

    assert (
        observed.source_snapshot_record_sha256
        == supplied_sha
    )

    # This acceptance is intentional at the pure binding layer.
    # The production executor must authenticate the canonical Stage 1
    # evidence chain before it is allowed to supply this SHA256.
