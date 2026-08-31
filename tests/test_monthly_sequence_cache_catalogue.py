"""Synthetic tests for the pure monthly sequence-cache catalogue."""

from __future__ import annotations

from dataclasses import replace
import csv
import hashlib
from io import StringIO
import json
from pathlib import Path

import pytest

import bacselect.monthly_sequence_cache_catalogue as module
from bacselect import source_eligibility
from bacselect.monthly_sequence_cache_catalogue import (
    CHAINED,
    GENESIS,
    CompletedSequenceCacheBatchEvidence,
    MonthlySequenceCacheCatalogueError,
    audit_sequence_cache_catalogue,
    serialize_sequence_cache_catalogue,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
)


RELEASE_1 = "2032.03"
RELEASE_2 = "2032.04"
RELEASE_3 = "2032.05"

SNAPSHOT_1 = (
    "bacselect-source-2032.03-"
    "20320301T001700Z"
)

SNAPSHOT_2 = (
    "bacselect-source-2032.04-"
    "20320401T001700Z"
)

SNAPSHOT_3 = (
    "bacselect-source-2032.05-"
    "20320501T001700Z"
)

COMMIT_1 = "1" * 40
COMMIT_2 = "2" * 40
COMMIT_3 = "3" * 40

ACCESSION_1 = "GCA_000000001.1"
ACCESSION_2 = "GCA_000000002.1"
ACCESSION_3 = "GCA_000000003.1"

BIOSAMPLE_1 = "SAMN00000001"
BIOSAMPLE_2 = "SAMN00000002"
BIOSAMPLE_3 = "SAMN00000003"


def canonical_json(
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
        "ascii"
    )


def tsv_bytes(
    fields,
    rows,
):
    buffer = StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        buffer,
        fieldnames=list(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
    )

    writer.writeheader()
    writer.writerows(
        rows
    )

    return buffer.getvalue().encode(
        "utf-8"
    )


def sha(
    payload,
):
    return hashlib.sha256(
        payload
    ).hexdigest()


def candidate_row(
    accession,
    biosample,
    *,
    fasta_sha,
    primary=1,
):
    row = {
        field:
            "synthetic"
        for field in CANDIDATE_AUDIT_FIELDS
    }

    row.update(
        {
            "canonical_genbank_assembly_accession":
                accession,
            "expected_biosample":
                biosample,
            "observed_biosample":
                biosample,
            "primary_assembly_records":
                str(
                    primary
                ),
            "sequence_eligibility":
                "eligible",
            "exclusion_reasons":
                "none",
            "fasta_file":
                f"{accession}_genomic.fna",
            "fasta_sha256":
                fasta_sha,
            "result":
                "PASS",
        }
    )

    return row


def component_row(
    accession,
    *,
    component="CP000001.1",
    sequence_sha=None,
):
    if sequence_sha is None:
        sequence_sha = "a" * 64

    row = {
        field:
            "synthetic"
        for field in COMPONENT_AUDIT_FIELDS
    }

    row.update(
        {
            "canonical_genbank_assembly_accession":
                accession,
            "component_genbank_accession":
                component,
            "length":
                "100",
            "topology":
                "circular",
            "ambiguous_base_count":
                "0",
            "sequence_sha256":
                sequence_sha,
        }
    )

    return row


def package_row(
    path,
    payload,
):
    return {
        "path":
            path,
        "size_bytes":
            str(
                len(
                    payload
                )
            ),
        "sha256":
            sha(
                payload
            ),
    }


def make_batch(
    batch_id,
    candidates,
):
    candidate_rows = []
    component_rows = []
    package_rows = []

    for index, (
        accession,
        biosample,
    ) in enumerate(
        candidates,
        1,
    ):
        fasta = (
            f">{accession}\n"
            f"ACGTACGT{index}\n"
        ).encode(
            "ascii"
        )

        fasta_sha = sha(
            fasta
        )

        candidate_rows.append(
            candidate_row(
                accession,
                biosample,
                fasta_sha=(
                    fasta_sha
                ),
            )
        )

        component_rows.append(
            component_row(
                accession,
                component=(
                    f"CP{index:06d}.1"
                ),
                sequence_sha=(
                    format(
                        index,
                        "064x",
                    )
                ),
            )
        )

        prefix = (
            f"ncbi_dataset/data/"
            f"{accession}/"
        )

        package_rows.extend(
            (
                package_row(
                    prefix
                    + f"{accession}_genomic.fna",
                    fasta,
                ),
                package_row(
                    prefix
                    + f"{accession}_genomic.gbff",
                    (
                        b"synthetic gbff "
                        + accession.encode(
                            "ascii"
                        )
                        + b"\n"
                    ),
                ),
                package_row(
                    prefix
                    + "sequence_report.jsonl",
                    (
                        b'{"synthetic":"report"}\n'
                    ),
                ),
            )
        )

    # Batch-shared evidence is intentionally present in Stage 3B but must not
    # be duplicated into accession catalogue entries.
    package_rows.append(
        package_row(
            "ncbi_dataset/data/"
            "assembly_data_report.jsonl",
            b'{"synthetic":"shared"}\n',
        )
    )

    candidate_payload = tsv_bytes(
        CANDIDATE_AUDIT_FIELDS,
        candidate_rows,
    )

    component_payload = tsv_bytes(
        COMPONENT_AUDIT_FIELDS,
        component_rows,
    )

    package_payload = tsv_bytes(
        PACKAGE_FILE_FIELDS,
        package_rows,
    )

    summary_payload = canonical_json(
        {
            "batch_id":
                batch_id,
            "synthetic":
                True,
        }
    )

    evidence = (
        CompletedSequenceCacheBatchEvidence(
            batch_id=batch_id,
            summary_payload=summary_payload,
            candidate_audit_payload=(
                candidate_payload
            ),
            component_audit_payload=(
                component_payload
            ),
            package_files_payload=(
                package_payload
            ),
        )
    )

    completion_row = {
        "accessions_sha256":
            sha(
                "".join(
                    accession
                    + "\n"
                    for accession, _
                    in candidates
                ).encode(
                    "ascii"
                )
            ),
        "batch_id":
            batch_id,
        "batch_index":
            int(
                batch_id.split(
                    "-"
                )[
                    1
                ]
            ),
        "batch_summary_sha256":
            sha(
                summary_payload
            ),
        "batch_target_manifest_sha256":
            "b" * 64,
        "candidate_sequence_audit_sha256":
            sha(
                candidate_payload
            ),
        "component_sequence_audit_sha256":
            sha(
                component_payload
            ),
        "fetch_entries":
            len(
                candidates
            ),
        "first_accession":
            candidates[
                0
            ][
                0
            ],
        "last_accession":
            candidates[
                -1
            ][
                0
            ],
        "package_file_readback_count":
            len(
                package_rows
            ),
        "package_file_readback_sha256":
            "c" * 64,
        "package_files":
            len(
                package_rows
            ),
        "package_files_sha256":
            sha(
                package_payload
            ),
        "requested_accessions":
            len(
                candidates
            ),
    }

    return (
        evidence,
        completion_row,
    )


def completion_payload(
    *,
    snapshot,
    commit,
    batches,
):
    rows = [
        row
        for _, row
        in batches
    ]

    count = sum(
        row[
            "requested_accessions"
        ]
        for row in rows
    )

    return canonical_json(
        {
            "batches":
                rows,
            "completed_accession_count":
                count,
            "completed_batch_count":
                len(
                    rows
                ),
            "environment_explicit_sha256":
                "d" * 64,
            "expected_batch_count":
                len(
                    rows
                ),
            "fresh_acquisition_count":
                count,
            "fresh_batch_size":
                500,
            "origin_git_commit":
                commit,
            "schema_version":
                (
                    "bacselect-monthly-sequence-"
                    "acquisition-completion-v1"
                ),
            "source_snapshot_id":
                snapshot,
            "source_snapshot_record_sha256":
                "e" * 64,
            "stage2_fresh_target_manifest_sha256":
                "f" * 64,
            "stage2_sequence_plan_record_sha256":
                "0" * 64,
            "status":
                "SEQUENCE_ACQUISITION_COMPLETE",
        }
    )


def build_release(
    *,
    release,
    snapshot,
    commit,
    batch_specs,
    previous=None,
):
    batches = tuple(
        make_batch(
            batch_id,
            candidates,
        )
        for batch_id, candidates
        in batch_specs
    )

    completion = completion_payload(
        snapshot=snapshot,
        commit=commit,
        batches=batches,
    )

    payload = serialize_sequence_cache_catalogue(
        release_id=release,
        source_snapshot_id=snapshot,
        origin_git_commit=commit,
        sequence_acquisition_completion_payload=(
            completion
        ),
        current_batches=tuple(
            evidence
            for evidence, _
            in batches
        ),
        previous_catalogue_payload=(
            previous
        ),
    )

    return (
        payload,
        completion,
        batches,
    )


def test_genesis_single_batch_is_canonical_and_auditable():
    payload, completion, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                    (
                        ACCESSION_2,
                        BIOSAMPLE_2,
                    ),
                ),
            ),
        ),
    )

    record = audit_sequence_cache_catalogue(
        payload
    )

    assert record[
        "catalogue_mode"
    ] == GENESIS

    assert record[
        "catalogue_entry_count"
    ] == 2

    assert record[
        "new_entry_count"
    ] == 2

    assert record[
        "replaced_entry_count"
    ] == 0

    assert record[
        "previous_catalogue_sha256"
    ] is None

    assert record[
        "sequence_acquisition_completion_sha256"
    ] == sha(
        completion
    )


def test_catalogue_entries_are_sorted_independent_of_evidence_input_order():
    first = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    second = make_batch(
        "batch-00002",
        (
            (
                ACCESSION_2,
                BIOSAMPLE_2,
            ),
        ),
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            first,
            second,
        ),
    )

    payload = serialize_sequence_cache_catalogue(
        release_id=RELEASE_1,
        source_snapshot_id=SNAPSHOT_1,
        origin_git_commit=COMMIT_1,
        sequence_acquisition_completion_payload=(
            completion
        ),
        current_batches=(
            second[
                0
            ],
            first[
                0
            ],
        ),
    )

    record = audit_sequence_cache_catalogue(
        payload
    )

    assert [
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in record[
            "entries"
        ]
    ] == [
        ACCESSION_1,
        ACCESSION_2,
    ]


def test_package_artifacts_bind_authoritative_logical_paths():
    payload, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    entry = audit_sequence_cache_catalogue(
        payload
    )[
        "entries"
    ][
        0
    ]

    for artifact in entry[
        "package_artifacts"
    ]:
        assert artifact[
            "logical_path"
        ] == (
            "sequence-acquisition/"
            "batch-00001/"
            "package/"
            + artifact[
                "package_path"
            ]
        )


def test_package_logical_path_cannot_drift_from_origin_batch():
    payload, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    record = json.loads(
        payload
    )

    artifact = record[
        "entries"
    ][
        0
    ][
        "package_artifacts"
    ][
        0
    ]

    artifact[
        "logical_path"
    ] = (
        "sequence-acquisition/"
        "batch-99999/"
        "package/"
        + artifact[
            "package_path"
        ]
    )

    entry = record[
        "entries"
    ][
        0
    ]

    entry_base = {
        key:
            value
        for key, value
        in entry.items()
        if key != "entry_sha256"
    }

    entry[
        "entry_sha256"
    ] = sha(
        module._entry_payload(
            entry_base
        )
    )

    record[
        "entries_sha256"
    ] = sha(
        module._canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-"
                "entry-set-v1"
            ),
            field="entries",
            values=record[
                "entries"
            ],
        )
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match=(
            "logical path does not match "
            "origin batch"
        ),
    ):
        audit_sequence_cache_catalogue(
            canonical_json(
                record
            )
        )


def test_shared_batch_package_file_is_not_duplicated_into_entry():
    payload, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    record = audit_sequence_cache_catalogue(
        payload
    )

    paths = [
        item[
            "package_path"
        ]
        for item in record[
            "entries"
        ][
            0
        ][
            "package_artifacts"
        ]
    ]

    assert (
        "ncbi_dataset/data/"
        "assembly_data_report.jsonl"
        not in paths
    )

    assert len(
        paths
    ) == 3


def test_zero_fresh_genesis_is_valid_and_empty():
    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(),
    )

    payload = serialize_sequence_cache_catalogue(
        release_id=RELEASE_1,
        source_snapshot_id=SNAPSHOT_1,
        origin_git_commit=COMMIT_1,
        sequence_acquisition_completion_payload=(
            completion
        ),
        current_batches=(),
    )

    record = audit_sequence_cache_catalogue(
        payload
    )

    assert record[
        "catalogue_mode"
    ] == GENESIS

    assert record[
        "catalogue_entry_count"
    ] == 0

    assert record[
        "batch_provenance"
    ] == []


def test_zero_fresh_chained_release_carries_entries_exactly():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(),
        previous=first,
    )

    first_record = audit_sequence_cache_catalogue(
        first
    )

    second_record = audit_sequence_cache_catalogue(
        second
    )

    assert second_record[
        "catalogue_mode"
    ] == CHAINED

    assert second_record[
        "entries"
    ] == first_record[
        "entries"
    ]

    assert second_record[
        "batch_provenance"
    ] == first_record[
        "batch_provenance"
    ]

    assert second_record[
        "carried_forward_entry_count"
    ] == 1

    assert second_record[
        "new_entry_count"
    ] == 0

    assert second_record[
        "replaced_entry_count"
    ] == 0


def test_later_release_adds_new_accession():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_2,
                        BIOSAMPLE_2,
                    ),
                ),
            ),
        ),
        previous=first,
    )

    record = audit_sequence_cache_catalogue(
        second
    )

    assert record[
        "catalogue_entry_count"
    ] == 2

    assert record[
        "carried_forward_entry_count"
    ] == 1

    assert record[
        "new_entry_count"
    ] == 1

    assert record[
        "replaced_entry_count"
    ] == 0


def test_current_acquisition_replaces_prior_origin():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
        previous=first,
    )

    record = audit_sequence_cache_catalogue(
        second
    )

    assert record[
        "catalogue_entry_count"
    ] == 1

    assert record[
        "replaced_entry_count"
    ] == 1

    assert record[
        "new_entry_count"
    ] == 0

    origin_sha = record[
        "entries"
    ][
        0
    ][
        "origin_batch_provenance_sha256"
    ]

    origin = {
        row[
            "batch_provenance_sha256"
        ]:
            row
        for row in record[
            "batch_provenance"
        ]
    }[
        origin_sha
    ]

    assert origin[
        "cache_origin_release_id"
    ] == RELEASE_2

    assert origin[
        "cache_origin_git_commit"
    ] == COMMIT_2


def test_replacement_prunes_unreferenced_old_batch_provenance():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
        previous=first,
    )

    record = audit_sequence_cache_catalogue(
        second
    )

    assert record[
        "batch_provenance_count"
    ] == 1

    assert record[
        "batch_provenance"
    ][
        0
    ][
        "cache_origin_release_id"
    ] == RELEASE_2


def test_absent_current_accession_is_not_deleted():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                    (
                        ACCESSION_2,
                        BIOSAMPLE_2,
                    ),
                ),
            ),
        ),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_3,
                        BIOSAMPLE_3,
                    ),
                ),
            ),
        ),
        previous=first,
    )

    record = audit_sequence_cache_catalogue(
        second
    )

    assert {
        row[
            "canonical_genbank_assembly_accession"
        ]
        for row in record[
            "entries"
        ]
    } == {
        ACCESSION_1,
        ACCESSION_2,
        ACCESSION_3,
    }


def test_previous_catalogue_exact_sha_is_chained():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(),
        previous=first,
    )

    record = audit_sequence_cache_catalogue(
        second
    )

    assert record[
        "previous_catalogue_sha256"
    ] == sha(
        first
    )

    assert record[
        "previous_catalogue_release_id"
    ] == RELEASE_1


def test_previous_release_must_be_earlier():
    later, _, _ = build_release(
        release=RELEASE_3,
        snapshot=SNAPSHOT_3,
        commit=COMMIT_3,
        batch_specs=(),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="not earlier",
    ):
        build_release(
            release=RELEASE_2,
            snapshot=SNAPSHOT_2,
            commit=COMMIT_2,
            batch_specs=(),
            previous=later,
        )


def test_missing_current_batch_fails_closed():
    batch = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            batch,
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="batch evidence set",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(),
        )


def test_extra_current_batch_fails_closed():
    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(),
    )

    evidence, _ = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="batch evidence set",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                evidence,
            ),
        )


@pytest.mark.parametrize(
    "field",
    (
        "batch_summary_sha256",
        "candidate_sequence_audit_sha256",
        "component_sequence_audit_sha256",
        "package_files_sha256",
    ),
)
def test_completion_bound_batch_artifact_hashes_fail_closed(
    field,
):
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    changed = dict(
        row
    )

    changed[
        field
    ] = "9" * 64

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                evidence,
                changed,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="identity differs",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                evidence,
            ),
        )


def test_contract_reuses_frozen_accession_and_biosample_validators():
    assert (
        module.CANONICAL_GCA_RE
        is source_eligibility.CANONICAL_GCA_RE
    )

    assert (
        module.BIOSAMPLE_RE
        is source_eligibility.BIOSAMPLE_RE
    )


def test_candidate_audit_accessions_must_preserve_frozen_order():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_2,
                BIOSAMPLE_2,
            ),
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                evidence,
                row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="accession order",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                evidence,
            ),
        )


def test_candidate_audit_accession_hash_must_match_completion():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "accessions_sha256"
    ] = "9" * 64

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="accession-list SHA256",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                evidence,
            ),
        )


def test_candidate_fasta_field_must_be_frozen_basename_form():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    rows = list(
        csv.DictReader(
            StringIO(
                evidence.candidate_audit_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    rows[
        0
    ][
        "fasta_file"
    ] = (
        f"ncbi_dataset/data/{ACCESSION_1}/"
        f"{ACCESSION_1}_genomic.fna"
    )

    candidate_payload = tsv_bytes(
        CANDIDATE_AUDIT_FIELDS,
        rows,
    )

    changed_evidence = replace(
        evidence,
        candidate_audit_payload=(
            candidate_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "candidate_sequence_audit_sha256"
    ] = sha(
        candidate_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="basename",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_package_manifest_must_preserve_stage3a_path_order():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    rows = list(
        csv.DictReader(
            StringIO(
                evidence.package_files_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    rows.reverse()

    package_payload = tsv_bytes(
        PACKAGE_FILE_FIELDS,
        rows,
    )

    changed_evidence = replace(
        evidence,
        package_files_payload=(
            package_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "package_files_sha256"
    ] = sha(
        package_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="path order",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_unresolved_topology_is_catalogued_as_origin_ineligible():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    candidate_rows = list(
        csv.DictReader(
            StringIO(
                evidence.candidate_audit_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    candidate_rows[
        0
    ][
        "sequence_eligibility"
    ] = "ineligible"

    candidate_rows[
        0
    ][
        "exclusion_reasons"
    ] = "unresolved_topology"

    candidate_payload = tsv_bytes(
        CANDIDATE_AUDIT_FIELDS,
        candidate_rows,
    )

    component_rows = list(
        csv.DictReader(
            StringIO(
                evidence.component_audit_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    component_rows[
        0
    ][
        "topology"
    ] = "unspecified"

    component_payload = tsv_bytes(
        COMPONENT_AUDIT_FIELDS,
        component_rows,
    )

    changed_evidence = replace(
        evidence,
        candidate_audit_payload=(
            candidate_payload
        ),
        component_audit_payload=(
            component_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "candidate_sequence_audit_sha256"
    ] = sha(
        candidate_payload
    )

    changed_row[
        "component_sequence_audit_sha256"
    ] = sha(
        component_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    payload = serialize_sequence_cache_catalogue(
        release_id=RELEASE_1,
        source_snapshot_id=SNAPSHOT_1,
        origin_git_commit=COMMIT_1,
        sequence_acquisition_completion_payload=(
            completion
        ),
        current_batches=(
            changed_evidence,
        ),
    )

    entry = audit_sequence_cache_catalogue(
        payload
    )[
        "entries"
    ][
        0
    ]

    assert entry[
        "origin_sequence_eligibility"
    ] == "ineligible"

    assert entry[
        "origin_sequence_exclusion_reasons"
    ] == "unresolved_topology"


def test_stage3a_eligibility_must_match_component_evidence():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    candidate_rows = list(
        csv.DictReader(
            StringIO(
                evidence.candidate_audit_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    candidate_rows[
        0
    ][
        "sequence_eligibility"
    ] = "ineligible"

    candidate_rows[
        0
    ][
        "exclusion_reasons"
    ] = "unresolved_topology"

    candidate_payload = tsv_bytes(
        CANDIDATE_AUDIT_FIELDS,
        candidate_rows,
    )

    changed_evidence = replace(
        evidence,
        candidate_audit_payload=(
            candidate_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "candidate_sequence_audit_sha256"
    ] = sha(
        candidate_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match=(
            "exclusion reasons differ "
            "from component evidence"
        ),
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_candidate_biosample_disagreement_fails_closed():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    rows = list(
        csv.DictReader(
            StringIO(
                evidence.candidate_audit_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    rows[
        0
    ][
        "observed_biosample"
    ] = BIOSAMPLE_2

    candidate_payload = tsv_bytes(
        CANDIDATE_AUDIT_FIELDS,
        rows,
    )

    changed_evidence = replace(
        evidence,
        candidate_audit_payload=(
            candidate_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "candidate_sequence_audit_sha256"
    ] = sha(
        candidate_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="BioSample",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_component_count_mismatch_fails_closed():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    component_payload = tsv_bytes(
        COMPONENT_AUDIT_FIELDS,
        (),
    )

    changed_evidence = replace(
        evidence,
        component_audit_payload=(
            component_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "component_sequence_audit_sha256"
    ] = sha(
        component_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="component audit count",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_unsafe_package_path_fails_closed():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    rows = list(
        csv.DictReader(
            StringIO(
                evidence.package_files_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    rows[
        0
    ][
        "path"
    ] = "../escape"

    package_payload = tsv_bytes(
        PACKAGE_FILE_FIELDS,
        rows,
    )

    changed_evidence = replace(
        evidence,
        package_files_payload=(
            package_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "package_files_sha256"
    ] = sha(
        package_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="unsafe",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_candidate_fasta_must_bind_to_accession_package():
    evidence, row = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    rows = list(
        csv.DictReader(
            StringIO(
                evidence.package_files_payload.decode(
                    "utf-8"
                )
            ),
            delimiter="\t",
        )
    )

    for item in rows:
        if item[
            "path"
        ].endswith(
            "_genomic.fna"
        ):
            item[
                "sha256"
            ] = "9" * 64

    package_payload = tsv_bytes(
        PACKAGE_FILE_FIELDS,
        rows,
    )

    changed_evidence = replace(
        evidence,
        package_files_payload=(
            package_payload
        ),
    )

    changed_row = dict(
        row
    )

    changed_row[
        "package_files_sha256"
    ] = sha(
        package_payload
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            (
                changed_evidence,
                changed_row,
            ),
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="FASTA is not uniquely bound",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                changed_evidence,
            ),
        )


def test_duplicate_accession_across_current_batches_fails_closed():
    first = make_batch(
        "batch-00001",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    second = make_batch(
        "batch-00002",
        (
            (
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    completion = completion_payload(
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batches=(
            first,
            second,
        ),
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="duplicate accession",
    ):
        serialize_sequence_cache_catalogue(
            release_id=RELEASE_1,
            source_snapshot_id=SNAPSHOT_1,
            origin_git_commit=COMMIT_1,
            sequence_acquisition_completion_payload=(
                completion
            ),
            current_batches=(
                first[
                    0
                ],
                second[
                    0
                ],
            ),
        )


def test_noncanonical_previous_catalogue_fails_closed():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(),
    )

    changed = first.rstrip(
        b"\n"
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="canonical",
    ):
        build_release(
            release=RELEASE_2,
            snapshot=SNAPSHOT_2,
            commit=COMMIT_2,
            batch_specs=(),
            previous=changed,
        )


def test_audit_rejects_mutated_entry_sha():
    payload, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    record = json.loads(
        payload
    )

    record[
        "entries"
    ][
        0
    ][
        "entry_sha256"
    ] = "9" * 64

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="entry SHA256",
    ):
        audit_sequence_cache_catalogue(
            canonical_json(
                record
            )
        )


def test_audit_rejects_mutated_batch_provenance_sha():
    payload, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    record = json.loads(
        payload
    )

    record[
        "batch_provenance"
    ][
        0
    ][
        "batch_provenance_sha256"
    ] = "9" * 64

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="batch-provenance SHA256",
    ):
        audit_sequence_cache_catalogue(
            canonical_json(
                record
            )
        )


def test_audit_rejects_unreferenced_batch_provenance():
    first, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    second, _, _ = build_release(
        release=RELEASE_2,
        snapshot=SNAPSHOT_2,
        commit=COMMIT_2,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_2,
                        BIOSAMPLE_2,
                    ),
                ),
            ),
        ),
        previous=first,
    )

    record = json.loads(
        second
    )

    duplicate = dict(
        record[
            "batch_provenance"
        ][
            0
        ]
    )

    duplicate[
        "batch_id"
    ] = "batch-99999"

    duplicate[
        "batch_summary"
    ] = {
        **duplicate[
            "batch_summary"
        ],
        "logical_path":
            (
                "sequence-acquisition/"
                "batch-99999/"
                "batch-summary.json"
            ),
    }

    duplicate[
        "candidate_audit"
    ] = {
        **duplicate[
            "candidate_audit"
        ],
        "logical_path":
            (
                "sequence-acquisition/"
                "batch-99999/"
                "candidate-sequence-audit.tsv"
            ),
    }

    duplicate[
        "component_audit"
    ] = {
        **duplicate[
            "component_audit"
        ],
        "logical_path":
            (
                "sequence-acquisition/"
                "batch-99999/"
                "component-sequence-audit.tsv"
            ),
    }

    duplicate[
        "package_files_manifest"
    ] = {
        **duplicate[
            "package_files_manifest"
        ],
        "logical_path":
            (
                "sequence-acquisition/"
                "batch-99999/"
                "package-files.tsv"
            ),
    }

    base = {
        key:
            value
        for key, value
        in duplicate.items()
        if key != "batch_provenance_sha256"
    }

    duplicate[
        "batch_provenance_sha256"
    ] = sha(
        module._batch_provenance_payload(
            base
        )
    )

    record[
        "batch_provenance"
    ].append(
        duplicate
    )

    record[
        "batch_provenance"
    ] = sorted(
        record[
            "batch_provenance"
        ],
        key=lambda row:
            row[
                "batch_provenance_sha256"
            ],
    )

    record[
        "batch_provenance_count"
    ] += 1

    record[
        "batch_provenance_sha256"
    ] = sha(
        module._canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-"
                "batch-provenance-set-v1"
            ),
            field="batch_provenance",
            values=record[
                "batch_provenance"
            ],
        )
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueError,
        match="unreferenced",
    ):
        audit_sequence_cache_catalogue(
            canonical_json(
                record
            )
        )


def test_record_contains_no_current_snapshot_verification_claims():
    payload, _, _ = build_release(
        release=RELEASE_1,
        snapshot=SNAPSHOT_1,
        commit=COMMIT_1,
        batch_specs=(
            (
                "batch-00001",
                (
                    (
                        ACCESSION_1,
                        BIOSAMPLE_1,
                    ),
                ),
            ),
        ),
    )

    text = payload.decode(
        "ascii"
    )

    forbidden = (
        "verified_source_snapshot_id",
        "component_identity_sha256",
        "assembly_fingerprint",
        "source_evidence_sha256",
        "package_manifest_sha256",
        "verification_record_sha256",
    )

    for token in forbidden:
        assert token not in text


def test_contract_is_pure_portable_and_history_free():
    path = (
        Path(__file__).resolve().parents[
            1
        ]
        / "src"
        / "bacselect"
        / "monthly_sequence_cache_catalogue.py"
    )

    text = path.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "import os",
        "import subprocess",
        "import requests",
        "import urllib",
        "import socket",
        "/NGS/",
        "Rhys_wkdir",
        "SLURM_",
        "sbatch",
        "srun",
        "Project Finch",
        "finch-ncbi-datasets",
    )

    for token in forbidden:
        assert token not in text
