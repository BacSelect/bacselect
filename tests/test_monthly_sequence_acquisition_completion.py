"""Synthetic tests for monthly Stage 3B release-level completion."""

from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import bacselect.monthly_sequence_acquisition_completion as module
from bacselect.monthly_sequence_acquisition_completion import (
    CompletedTransportBatchEvidence,
    MonthlySequenceAcquisitionCompletionError,
    PackageFileReadbackObservation,
    audit_sequence_acquisition_completion_record,
    build_sequence_acquisition_completion_record,
    serialize_sequence_acquisition_completion_record,
)
from bacselect.monthly_sequence_plan import (
    FRESH_BATCH_SIZE,
    FRESH_TARGET_FIELDS,
    MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA,
    NO_VERIFIED_CACHE,
    accession_manifest_bytes,
)
from bacselect.monthly_sequence_transport import (
    TARGETED_RETRY_ROUNDS,
    MonthlyFreshAcquisitionTarget,
    batch_accession_bytes,
    batch_target_manifest_sha256,
)
from bacselect.monthly_sequence_validation import (
    PACKAGE_FILE_FIELDS,
)
from bacselect.source_eligibility import (
    DATASETS_VERSION,
)


SNAPSHOT = (
    "bacselect-source-2032.04-"
    "0123456789abcdef"
)

SNAPSHOT_SHA = "1" * 64
COMMIT = "a" * 40
ENVIRONMENT_SHA = "b" * 64


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


def canonical_json(
    value,
) -> bytes:
    return (
        json.dumps(
            value,
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


def package_evidence(
    batch_targets,
):
    rows = []

    for target in batch_targets:
        accession_value = (
            target.canonical_genbank_assembly_accession
        )

        for filename in (
            f"{accession_value}_genomic.fna",
            f"{accession_value}_genomic.gbff",
            "sequence_report.jsonl",
        ):
            path = (
                f"ncbi_dataset/data/{accession_value}/{filename}"
            )

            synthetic_bytes = (
                f"synthetic:{path}\n"
            ).encode(
                "utf-8"
            )

            rows.append(
                (
                    path,
                    len(
                        synthetic_bytes
                    ),
                    hashlib.sha256(
                        synthetic_bytes
                    ).hexdigest(),
                )
            )

    shared_path = (
        "ncbi_dataset/data/assembly_data_report.jsonl"
    )

    shared_bytes = (
        b"synthetic:assembly-data-report\n"
    )

    rows.append(
        (
            shared_path,
            len(
                shared_bytes
            ),
            hashlib.sha256(
                shared_bytes
            ).hexdigest(),
        )
    )

    rows.sort(
        key=lambda item:
            item[
                0
            ]
    )

    lines = [
        "\t".join(
            PACKAGE_FILE_FIELDS
        )
        + "\n"
    ]

    observations = []

    for path, size, sha in rows:
        lines.append(
            f"{path}\t{size}\t{sha}\n"
        )

        observations.append(
            PackageFileReadbackObservation(
                path=path,
                observed_size_bytes=size,
                observed_sha256=sha,
            )
        )

    return (
        "".join(
            lines
        ).encode(
            "utf-8"
        ),
        tuple(
            observations
        ),
    )


def targets(
    count: int,
):
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


def make_plan(
    count: int,
):
    values = targets(
        count
    )

    manifest_rows = [
        "\t".join(
            FRESH_TARGET_FIELDS
        )
        + "\n"
    ]

    for target in values:
        manifest_rows.append(
            f"{target.canonical_genbank_assembly_accession}\t"
            f"{target.source_biosample}\t"
            f"{target.acquisition_reason}\n"
        )

    manifest = "".join(
        manifest_rows
    ).encode(
        "ascii"
    )

    accessions = tuple(
        target.canonical_genbank_assembly_accession
        for target in values
    )

    accession_sha = hashlib.sha256(
        accession_manifest_bytes(
            accessions
        )
    ).hexdigest()

    empty_sha = hashlib.sha256(
        accession_manifest_bytes(
            ()
        )
    ).hexdigest()

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
            accession_sha,
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
            hashlib.sha256(
                manifest
            ).hexdigest(),
        "retained_accessions_sha256":
            accession_sha,
        "retained_count":
            count,
        "schema_version":
            MONTHLY_SEQUENCE_PLAN_RECORD_SCHEMA,
        "source_snapshot_id":
            SNAPSHOT,
        "source_snapshot_record_sha256":
            SNAPSHOT_SHA,
    }

    return (
        canonical_json(
            record
        ),
        manifest,
        values,
    )


def make_batch(
    plan_payload: bytes,
    manifest: bytes,
    values,
    batch_index: int,
):
    batch_count = (
        (
            len(
                values
            )
            + FRESH_BATCH_SIZE
            - 1
        )
        // FRESH_BATCH_SIZE
    )

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

    target_sha = (
        batch_target_manifest_sha256(
            batch_targets
        )
    )

    accessions_sha = hashlib.sha256(
        batch_accession_bytes(
            batch_targets
        )
    ).hexdigest()

    dehydrated_sha = "c" * 64
    fetch_sha = "d" * 64
    attempt_sha = "e" * 64
    candidate_sha = "2" * 64
    component_sha = "3" * 64
    (
        package_files_payload,
        package_file_observations,
    ) = package_evidence(
        batch_targets
    )

    package_file_count = len(
        package_file_observations
    )

    package_sha = hashlib.sha256(
        package_files_payload
    ).hexdigest()

    summary = {
        "accessions_sha256":
            accessions_sha,
        "attempt_origin_sha256":
            attempt_sha,
        "batch_count":
            batch_count,
        "batch_index":
            batch_index,
        "batch_size":
            FRESH_BATCH_SIZE,
        "batch_target_manifest_sha256":
            target_sha,
        "broad_rehydrate_exit_code":
            0,
        "candidate_records":
            len(
                batch_targets
            ),
        "candidate_sequence_audit_sha256":
            candidate_sha,
        "component_records":
            len(
                batch_targets
            ),
        "component_sequence_audit_sha256":
            component_sha,
        "datasets_version":
            DATASETS_VERSION,
        "dehydrated_zip_sha256":
            dehydrated_sha,
        "environment_explicit_sha256":
            ENVIRONMENT_SHA,
        "execution_completed_at_utc":
            "2032-04-01T01:00:00Z",
        "fetch_entries":
            len(
                batch_targets
            )
            * 3,
        "fetch_txt_sha256":
            fetch_sha,
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
            package_file_count,
        "package_files_sha256":
            package_sha,
        "requested_accessions":
            len(
                batch_targets
            ),
        "result":
            "PASS",
        "schema":
            module.TRANSPORT_SUMMARY_SCHEMA,
        "source_snapshot_id":
            SNAPSHOT,
        "source_snapshot_record_sha256":
            SNAPSHOT_SHA,
        "stage2_fresh_target_manifest_sha256":
            hashlib.sha256(
                manifest
            ).hexdigest(),
        "stage2_sequence_plan_record_sha256":
            hashlib.sha256(
                plan_payload
            ).hexdigest(),
        "targeted_retry_events":
            [],
        "targeted_retry_rounds":
            TARGETED_RETRY_ROUNDS,
    }

    return CompletedTransportBatchEvidence(
        batch_id=(
            f"batch-{batch_index:05d}"
        ),
        summary_payload=(
            transport_json(
                summary
            )
        ),
        observed_batch_target_manifest_sha256=(
            target_sha
        ),
        observed_accessions_sha256=(
            accessions_sha
        ),
        observed_dehydrated_zip_sha256=(
            dehydrated_sha
        ),
        observed_fetch_txt_sha256=(
            fetch_sha
        ),
        observed_attempt_origin_sha256=(
            attempt_sha
        ),
        observed_candidate_audit_sha256=(
            candidate_sha
        ),
        observed_component_audit_sha256=(
            component_sha
        ),
        package_files_payload=(
            package_files_payload
        ),
        package_file_observations=(
            package_file_observations
        ),
    )


def kwargs_for(
    count: int,
):
    (
        plan,
        manifest,
        values,
    ) = make_plan(
        count
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

    batches = tuple(
        make_batch(
            plan,
            manifest,
            values,
            index,
        )
        for index in range(
            1,
            batch_count
            + 1,
        )
    )

    ids = tuple(
        item.batch_id
        for item in batches
    )

    return {
        "source_snapshot_id":
            SNAPSHOT,
        "source_snapshot_record_sha256":
            SNAPSHOT_SHA,
        "stage2_sequence_plan_record":
            plan,
        "stage2_fresh_target_manifest":
            manifest,
        "origin_git_commit":
            COMMIT,
        "environment_explicit_sha256":
            ENVIRONMENT_SHA,
        "batches":
            batches,
        "discovered_final_batch_ids":
            ids,
    }


def summary_with(
    evidence,
    **changes,
):
    summary = json.loads(
        evidence.summary_payload
    )

    summary.update(
        changes
    )

    return replace(
        evidence,
        summary_payload=(
            transport_json(
                summary
            )
        ),
    )


def test_zero_fresh_release_is_complete():
    record = (
        build_sequence_acquisition_completion_record(
            **kwargs_for(
                0
            )
        )
    )

    assert record[
        "fresh_acquisition_count"
    ] == 0

    assert record[
        "expected_batch_count"
    ] == 0

    assert record[
        "completed_batch_count"
    ] == 0

    assert record[
        "completed_accession_count"
    ] == 0

    assert record[
        "batches"
    ] == []


def test_single_batch_release_is_complete():
    record = (
        build_sequence_acquisition_completion_record(
            **kwargs_for(
                3
            )
        )
    )

    assert record[
        "expected_batch_count"
    ] == 1

    assert record[
        "completed_batch_count"
    ] == 1

    assert record[
        "completed_accession_count"
    ] == 3

    assert record[
        "batches"
    ][0][
        "batch_id"
    ] == "batch-00001"


def test_multi_batch_release_is_complete():
    record = (
        build_sequence_acquisition_completion_record(
            **kwargs_for(
                501
            )
        )
    )

    assert record[
        "expected_batch_count"
    ] == 2

    assert tuple(
        item[
            "requested_accessions"
        ]
        for item in record[
            "batches"
        ]
    ) == (
        500,
        1,
    )


def test_missing_final_batch_fails_closed():
    values = kwargs_for(
        501
    )

    values[
        "discovered_final_batch_ids"
    ] = (
        "batch-00001",
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="incomplete or contains extras",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_extra_final_batch_fails_closed():
    values = kwargs_for(
        3
    )

    values[
        "discovered_final_batch_ids"
    ] = (
        "batch-00001",
        "batch-00002",
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="incomplete or contains extras",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_partial_batch_fails_closed():
    values = kwargs_for(
        3
    )

    values[
        "discovered_partial_batch_ids"
    ] = (
        "batch-00001.partial",
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="partial Stage 3B batch",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_unexpected_batch_like_entry_fails_closed():
    values = kwargs_for(
        3
    )

    values[
        "unexpected_batch_entries"
    ] = (
        "batch-not-valid",
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="unexpected Stage 3B",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_duplicate_batch_evidence_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        first,
        first,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="duplicate completed",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_noncanonical_summary_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        summary_payload=(
            json.dumps(
                json.loads(
                    first.summary_payload
                )
            ).encode(
                "utf-8"
            )
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="not canonical",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_summary_schema_change_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            schema="changed",
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="schema version",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_nonpass_summary_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            result="FAIL",
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="not PASS",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_source_snapshot_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            source_snapshot_id="changed",
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="source snapshot ID",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_source_snapshot_record_sha_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            source_snapshot_record_sha256=(
                "9" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="source-snapshot-record",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_stage2_plan_identity_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            stage2_sequence_plan_record_sha256=(
                "9" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="sequence-plan identity",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_stage2_manifest_identity_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            stage2_fresh_target_manifest_sha256=(
                "9" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="fresh-target identity",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_origin_commit_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            origin_git_commit=(
                "9" * 40
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="origin Git commit",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_environment_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            environment_explicit_sha256=(
                "9" * 64
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="environment identity",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_batch_count_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            batch_count=2,
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="batch count changed",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_full_target_count_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            full_target_count=4,
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="full-target count",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_requested_accession_count_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            requested_accessions=2,
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="requested-accession count",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_batch_target_manifest_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        observed_batch_target_manifest_sha256=(
            "9" * 64
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="batch-target manifest identity",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_batch_accession_list_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        observed_accessions_sha256=(
            "9" * 64
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="accession-list identity",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_observed_scientific_audit_hash_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        observed_candidate_audit_sha256=(
            "9" * 64
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="candidate audit identity changed",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_package_files_manifest_identity_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        package_files_payload=(
            first.package_files_payload
            + b"\n"
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="package-files manifest identity changed",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_missing_package_file_readback_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        package_file_observations=(
            first.package_file_observations[
                1:
            ]
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="readback set differs",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_extra_package_file_readback_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        package_file_observations=(
            *first.package_file_observations,
            PackageFileReadbackObservation(
                path="unexpected.txt",
                observed_size_bytes=1,
                observed_sha256=(
                    "9" * 64
                ),
            ),
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="readback set differs",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_duplicate_package_file_readback_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    changed = replace(
        first,
        package_file_observations=(
            *first.package_file_observations,
            first.package_file_observations[
                0
            ],
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="duplicate package-file readback path",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_package_file_readback_size_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    observation = (
        first.package_file_observations[
            0
        ]
    )

    changed_observation = replace(
        observation,
        observed_size_bytes=(
            observation.observed_size_bytes
            + 1
        ),
    )

    changed = replace(
        first,
        package_file_observations=(
            changed_observation,
            *first.package_file_observations[
                1:
            ],
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="size changed during independent readback",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_package_file_readback_sha_mismatch_fails_closed():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    observation = (
        first.package_file_observations[
            0
        ]
    )

    changed_observation = replace(
        observation,
        observed_sha256=(
            "9" * 64
        ),
    )

    changed = replace(
        first,
        package_file_observations=(
            changed_observation,
            *first.package_file_observations[
                1:
            ],
        ),
    )

    values[
        "batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="SHA256 changed during independent readback",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_candidate_record_count_must_equal_expected_batch_population():
    values = kwargs_for(
        3
    )

    first = values[
        "batches"
    ][0]

    values[
        "batches"
    ] = (
        summary_with(
            first,
            candidate_records=2,
        ),
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="candidate-record count",
    ):
        build_sequence_acquisition_completion_record(
            **values
        )


def test_completion_record_tamper_fails_closed():
    values = kwargs_for(
        3
    )

    payload = (
        serialize_sequence_acquisition_completion_record(
            **values
        )
    )

    changed = payload.replace(
        b'"completed_batch_count":1',
        b'"completed_batch_count":0',
    )

    with pytest.raises(
        MonthlySequenceAcquisitionCompletionError,
        match="derived identity",
    ):
        audit_sequence_acquisition_completion_record(
            changed,
            **values
        )


def test_module_has_no_execution_or_historical_imports():
    tree = ast.parse(
        Path(
            module.__file__
        ).read_text(
            encoding="utf-8"
        )
    )

    imported = set()

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Import,
        ):
            imported.update(
                alias.name.split(
                    ".",
                    1,
                )[
                    0
                ]
                for alias in node.names
            )

        if isinstance(
            node,
            ast.ImportFrom,
        ) and node.module:
            imported.add(
                node.module.split(
                    ".",
                    1,
                )[
                    0
                ]
            )

    assert imported.isdisjoint(
        {
            "os",
            "subprocess",
            "requests",
            "urllib",
            "socket",
        }
    )

    text = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "/NGS/",
        "Rhys_wkdir",
        "SLURM_",
        "sbatch",
        "srun",
    ):
        assert token not in text
