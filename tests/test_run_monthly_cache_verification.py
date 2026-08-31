"""Tests for portable monthly cache-verification execution."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from bacselect import monthly_authoritative_storage
from bacselect.monthly_cache_verification import (
    CACHE_FRESH_REQUIRED,
    CACHE_VERIFIED,
    REASON_BIOSAMPLE,
    REASON_PACKAGE_MISSING,
    REASON_PACKAGE_SHA256,
    audit_cache_verification_record,
    audit_cache_verification_results,
    audit_verified_cache_evidence,
    verify_cache_candidates,
)
from bacselect.monthly_release_start import (
    canonical_json_bytes,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
)


REPO = Path(
    __file__
).resolve().parents[
    1
]

WRAPPER_PATH = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_monthly_cache_verification.py"
)


def load_wrapper():
    name = (
        "_bacselect_test_monthly_cache_verification_execution"
    )

    existing = sys.modules.get(
        name
    )

    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(
        name,
        WRAPPER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


module = load_wrapper()


CURRENT_RELEASE = "2032.04"
ORIGIN_RELEASE = "2032.03"

CURRENT_SNAPSHOT = (
    "bacselect-source-2032.04-"
    "20320401T001700Z"
)

ORIGIN_SNAPSHOT = (
    "bacselect-source-2032.03-"
    "20320301T001700Z"
)

CURRENT_COMMIT = "4" * 40
ORIGIN_COMMIT = "3" * 40

ACCESSION = "GCA_000001.1"
BIOSAMPLE = "SAMN123456"
OTHER_BIOSAMPLE = "SAMN654321"
COMPONENT = "NZ_CP000001.1"
SEQUENCE = "ACGTACGT"

FASTA_NAME = (
    f"{ACCESSION}_genomic.fna"
)

FASTA_PATH = (
    f"ncbi_dataset/data/{ACCESSION}/"
    f"{FASTA_NAME}"
)

FASTA_PAYLOAD = (
    f">{COMPONENT}\n"
    f"{SEQUENCE}\n"
).encode(
    "ascii"
)

FASTA_SHA = hashlib.sha256(
    FASTA_PAYLOAD
).hexdigest()

COMPONENT_SHA = hashlib.sha256(
    SEQUENCE.encode(
        "utf-8"
    )
).hexdigest()


def sha(
    payload,
):
    return hashlib.sha256(
        payload
    ).hexdigest()


def tsv_bytes(
    fields,
    rows,
):
    buffer = io.StringIO(
        newline=""
    )

    writer = csv.DictWriter(
        buffer,
        fieldnames=tuple(
            fields
        ),
        delimiter="\t",
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            row
        )

    return buffer.getvalue().encode(
        "utf-8"
    )


def candidate_row(
    *,
    biosample=BIOSAMPLE,
):
    row = {
        field:
            "0"
        for field in CANDIDATE_AUDIT_FIELDS
    }

    row.update(
        {
            "canonical_genbank_assembly_accession":
                ACCESSION,
            "expected_biosample":
                biosample,
            "observed_biosample":
                biosample,
            "assembly_status":
                "current",
            "current_accession":
                ACCESSION,
            "assembly_level":
                "Complete Genome",
            "sequence_report_records":
                "1",
            "sequence_report_length_present_records":
                "1",
            "sequence_report_length_missing_records":
                "0",
            "sequence_report_length_missing_components":
                "none",
            "primary_assembly_records":
                "1",
            "auxiliary_assembly_records":
                "0",
            "auxiliary_assembly_units":
                "none",
            "auxiliary_component_accessions":
                "none",
            "fasta_records":
                "1",
            "gbff_records":
                "1",
            "total_sequence_length":
                str(
                    len(
                        SEQUENCE
                    )
                ),
            "package_total_sequence_length":
                str(
                    len(
                        SEQUENCE
                    )
                ),
            "auxiliary_total_sequence_length":
                "0",
            "topology_circular_records":
                "1",
            "topology_linear_records":
                "0",
            "topology_unspecified_records":
                "0",
            "ambiguous_base_count":
                "0",
            "ambiguous_symbols":
                "none",
            "sequence_eligibility":
                "eligible",
            "exclusion_reasons":
                "none",
            "fasta_file":
                FASTA_NAME,
            "fasta_sha256":
                FASTA_SHA,
            "gbff_file":
                "genomic.gbff",
            "gbff_sha256":
                "1" * 64,
            "gbff_source":
                "datasets",
            "gbff_provenance_file":
                "none",
            "gbff_provenance_sha256":
                "none",
            "sequence_report_sha256":
                "2" * 64,
            "result":
                "PASS",
        }
    )

    return row


def component_row():
    return {
        "canonical_genbank_assembly_accession":
            ACCESSION,
        "component_genbank_accession":
            COMPONENT,
        "length":
            str(
                len(
                    SEQUENCE
                )
            ),
        "topology":
            "circular",
        "ambiguous_base_count":
            "0",
        "ambiguous_symbols":
            "none",
        "sequence_sha256":
            COMPONENT_SHA,
    }


def package_row(
    *,
    path=FASTA_PATH,
    payload=FASTA_PAYLOAD,
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


def write_object(
    root,
    payload,
    *,
    expected_sha=None,
):
    digest = (
        expected_sha
        if expected_sha
        is not None
        else sha(
            payload
        )
    )

    key = (
        monthly_authoritative_storage.object_key_for_sha256(
            digest
        )
    )

    path = (
        root
        / key
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        payload
    )

    return (
        digest,
        path,
    )


def synthetic_catalogue(
    object_root,
    *,
    write_fasta=True,
    corrupt_fasta=False,
    include_shared=False,
    write_shared=True,
    biosample=BIOSAMPLE,
    origin_eligible=True,
    malformed_completion=False,
    malformed_summary=False,
):
    candidate_payload = tsv_bytes(
        CANDIDATE_AUDIT_FIELDS,
        (
            candidate_row(
                biosample=(
                    biosample
                ),
            ),
        ),
    )

    component_payload = tsv_bytes(
        COMPONENT_AUDIT_FIELDS,
        (
            component_row(),
        ),
    )

    package_rows = [
        package_row(),
    ]

    shared_payload = (
        b'{"shared":true}\n'
    )

    shared_path = (
        "ncbi_dataset/data/"
        "assembly_data_report.jsonl"
    )

    if include_shared:
        package_rows.append(
            package_row(
                path=(
                    shared_path
                ),
                payload=(
                    shared_payload
                ),
            )
        )

    package_payload = tsv_bytes(
        PACKAGE_FILE_FIELDS,
        tuple(
            package_rows
        ),
    )

    candidate_sha = sha(
        candidate_payload
    )

    component_sha = sha(
        component_payload
    )

    package_manifest_sha = sha(
        package_payload
    )

    accessions_sha = sha(
        (
            ACCESSION
            + "\n"
        ).encode(
            "ascii"
        )
    )

    summary_record = {
        "accessions_sha256":
            accessions_sha,
        "attempt_origin_sha256":
            "4" * 64,
        "batch_count":
            1,
        "batch_index":
            1,
        "batch_size":
            module.completion_contract.FRESH_BATCH_SIZE,
        "batch_target_manifest_sha256":
            "8" * 64,
        "broad_rehydrate_exit_code":
            0,
        "candidate_records":
            1,
        "candidate_sequence_audit_sha256":
            candidate_sha,
        "component_records":
            1,
        "component_sequence_audit_sha256":
            component_sha,
        "datasets_version":
            module.completion_contract.DATASETS_VERSION,
        "dehydrated_zip_sha256":
            "5" * 64,
        "environment_explicit_sha256":
            "6" * 64,
        "execution_completed_at_utc":
            "2032-03-01T01:00:00Z",
        "fetch_entries":
            1,
        "fetch_txt_sha256":
            "7" * 64,
        "first_accession":
            ACCESSION,
        "full_target_count":
            1,
        "initial_unresolved_accessions":
            0,
        "last_accession":
            ACCESSION,
        "origin_git_commit":
            ORIGIN_COMMIT,
        "package_files":
            len(
                package_rows
            ),
        "package_files_sha256":
            package_manifest_sha,
        "requested_accessions":
            1,
        "result":
            "PASS",
        "schema":
            module.completion_contract.TRANSPORT_SUMMARY_SCHEMA,
        "source_snapshot_id":
            ORIGIN_SNAPSHOT,
        "source_snapshot_record_sha256":
            "7" * 64,
        "stage2_fresh_target_manifest_sha256":
            "8" * 64,
        "stage2_sequence_plan_record_sha256":
            "9" * 64,
        "targeted_retry_events":
            [],
        "targeted_retry_rounds":
            module.completion_contract.TARGETED_RETRY_ROUNDS,
    }

    if malformed_summary:
        summary_record[
            "unexpected_field"
        ] = True

    summary_payload = (
        canonical_json_bytes(
            summary_record
        )
    )

    summary_sha = sha(
        summary_payload
    )

    package_readback_sha = (
        "9" * 64
    )

    completion_record = {
        "batches":
            [
                {
                    "accessions_sha256":
                        accessions_sha,
                    "batch_id":
                        "batch-00001",
                    "batch_index":
                        1,
                    "batch_summary_sha256":
                        summary_sha,
                    "batch_target_manifest_sha256":
                        "8" * 64,
                    "candidate_sequence_audit_sha256":
                        candidate_sha,
                    "component_sequence_audit_sha256":
                        component_sha,
                    "fetch_entries":
                        1,
                    "first_accession":
                        ACCESSION,
                    "last_accession":
                        ACCESSION,
                    "package_file_readback_count":
                        len(
                            package_rows
                        ),
                    "package_file_readback_sha256":
                        package_readback_sha,
                    "package_files":
                        len(
                            package_rows
                        ),
                    "package_files_sha256":
                        package_manifest_sha,
                    "requested_accessions":
                        1,
                }
            ],
        "completed_accession_count":
            1,
        "completed_batch_count":
            1,
        "environment_explicit_sha256":
            "6" * 64,
        "expected_batch_count":
            1,
        "fresh_acquisition_count":
            1,
        "fresh_batch_size":
            500,
        "origin_git_commit":
            ORIGIN_COMMIT,
        "schema_version":
            (
                "bacselect-monthly-sequence-"
                "acquisition-completion-v1"
            ),
        "source_snapshot_id":
            ORIGIN_SNAPSHOT,
        "source_snapshot_record_sha256":
            "7" * 64,
        "stage2_fresh_target_manifest_sha256":
            "8" * 64,
        "stage2_sequence_plan_record_sha256":
            "9" * 64,
        "status":
            "SEQUENCE_ACQUISITION_COMPLETE",
    }

    if malformed_completion:
        completion_record[
            "unexpected_field"
        ] = True

    completion_payload = (
        canonical_json_bytes(
            completion_record
        )
    )

    completion_sha = sha(
        completion_payload
    )

    for payload in (
        summary_payload,
        candidate_payload,
        component_payload,
        package_payload,
        completion_payload,
    ):
        write_object(
            object_root,
            payload,
        )

    if write_fasta:
        payload = FASTA_PAYLOAD

        if corrupt_fasta:
            payload = (
                FASTA_PAYLOAD[
                    :-2
                ]
                + b"A\n"
            )

        write_object(
            object_root,
            payload,
            expected_sha=(
                FASTA_SHA
            ),
        )

    if (
        include_shared
        and write_shared
    ):
        write_object(
            object_root,
            shared_payload,
        )

    batch_provenance_sha = (
        "a" * 64
    )

    provenance = {
        "accessions_sha256":
            accessions_sha,
        "batch_id":
            "batch-00001",
        "batch_provenance_sha256":
            batch_provenance_sha,
        "batch_summary":
            {
                "logical_path":
                    (
                        "sequence-acquisition/"
                        "batch-00001/batch-summary.json"
                    ),
                "sha256":
                    summary_sha,
                "size_bytes":
                    len(
                        summary_payload
                    ),
            },
        "cache_origin_git_commit":
            ORIGIN_COMMIT,
        "cache_origin_release_id":
            ORIGIN_RELEASE,
        "cache_origin_source_snapshot_id":
            ORIGIN_SNAPSHOT,
        "candidate_audit":
            {
                "logical_path":
                    (
                        "sequence-acquisition/"
                        "batch-00001/"
                        "candidate-sequence-audit.tsv"
                    ),
                "sha256":
                    candidate_sha,
                "size_bytes":
                    len(
                        candidate_payload
                    ),
            },
        "component_audit":
            {
                "logical_path":
                    (
                        "sequence-acquisition/"
                        "batch-00001/"
                        "component-sequence-audit.tsv"
                    ),
                "sha256":
                    component_sha,
                "size_bytes":
                    len(
                        component_payload
                    ),
            },
        "origin_package_file_readback_sha256":
            package_readback_sha,
        "origin_sequence_acquisition_completion_sha256":
            completion_sha,
        "package_files_manifest":
            {
                "logical_path":
                    (
                        "sequence-acquisition/"
                        "batch-00001/package-files.tsv"
                    ),
                "sha256":
                    package_manifest_sha,
                "size_bytes":
                    len(
                        package_payload
                    ),
            },
        "requested_accessions":
            1,
    }

    eligibility = (
        "eligible"
        if origin_eligible
        else "ineligible"
    )

    exclusion = (
        "none"
        if origin_eligible
        else "unresolved_topology"
    )

    entry = {
        "biosample":
            biosample,
        "canonical_genbank_assembly_accession":
            ACCESSION,
        "entry_sha256":
            "b" * 64,
        "origin_batch_provenance_sha256":
            batch_provenance_sha,
        "origin_sequence_eligibility":
            eligibility,
        "origin_sequence_exclusion_reasons":
            exclusion,
        "package_artifacts":
            [
                {
                    "logical_path":
                        (
                            "sequence-acquisition/"
                            "batch-00001/package/"
                            f"{FASTA_PATH}"
                        ),
                    "package_path":
                        FASTA_PATH,
                    "sha256":
                        FASTA_SHA,
                    "size_bytes":
                        len(
                            FASTA_PAYLOAD
                        ),
                }
            ],
    }

    record = {
        "batch_provenance":
            [
                provenance
            ],
        "catalogue_entry_count":
            1,
        "entries":
            [
                entry
            ],
        "entries_sha256":
            "c" * 64,
    }

    item = SimpleNamespace(
        release_id=(
            ORIGIN_RELEASE
        ),
        origin_git_commit=(
            ORIGIN_COMMIT
        ),
        catalogue_sha256=(
            "d" * 64
        ),
        catalogue_record=(
            record
        ),
    )

    return (
        item,
        record,
    )


def current_context(
    stage1,
    *,
    biosample=BIOSAMPLE,
):
    return module.CurrentMetadataContext(
        release_id=(
            CURRENT_RELEASE
        ),
        source_snapshot_id=(
            CURRENT_SNAPSHOT
        ),
        stage1_root=(
            stage1
        ),
        source_snapshot_record_sha256=(
            "1" * 64
        ),
        metadata_record_sha256=(
            "2" * 64
        ),
        metadata_completion_sha256=(
            "3" * 64
        ),
        retained_metadata={
            ACCESSION:
                biosample,
        },
    )


def fake_git_reader(
    repo,
    *args,
):
    del repo

    if args in {
        (
            "rev-parse",
            "HEAD",
        ),
        (
            "rev-parse",
            "origin/main",
        ),
    }:
        return CURRENT_COMMIT

    if args == (
        "status",
        "--porcelain",
    ):
        return ""

    raise AssertionError(
        args
    )


def test_repository_preflight_accepts_exact_dependencies():
    module.repository_preflight(
        REPO,
        expected_commit=(
            CURRENT_COMMIT
        ),
        expected_wrapper_sha256=(
            module.sha256_file(
                WRAPPER_PATH
            )
        ),
        expected_wrapper_test_sha256=(
            module.sha256_file(
                Path(
                    __file__
                )
            )
        ),
        git_reader=(
            fake_git_reader
        ),
    )


def test_repository_preflight_rejects_dirty_tree():
    def dirty(
        repo,
        *args,
    ):
        if args == (
            "status",
            "--porcelain",
        ):
            return "M dirty"

        return fake_git_reader(
            repo,
            *args,
        )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="preflight",
    ):
        module.repository_preflight(
            REPO,
            expected_commit=(
                CURRENT_COMMIT
            ),
            expected_wrapper_sha256=(
                module.sha256_file(
                    WRAPPER_PATH
                )
            ),
            expected_wrapper_test_sha256=(
                module.sha256_file(
                    Path(
                        __file__
                    )
                )
            ),
            git_reader=(
                dirty
            ),
        )


def test_required_object_reads_exact_sha_address(
    tmp_path,
):
    root = (
        tmp_path
        / "objects-root"
    )

    root.mkdir()

    payload = b"abc\n"

    digest, _ = write_object(
        root,
        payload,
    )

    observed = module.read_required_object(
        root,
        sha256=digest,
        expected_size_bytes=len(
            payload
        ),
        label="test object",
    )

    assert observed.payload == payload
    assert observed.sha256 == digest


def test_optional_missing_object_is_explicit_cache_miss(
    tmp_path,
):
    root = (
        tmp_path
        / "objects-root"
    )

    root.mkdir()

    observed = module.observe_optional_object(
        root,
        sha256=(
            "f" * 64
        ),
    )

    assert observed.payload is None
    assert observed.observed_size_bytes is None
    assert observed.observed_sha256 is None


def test_first_release_proof_accepts_no_prior_sequence_evidence(
    tmp_path,
):
    module.prove_no_prior_sequence_evidence(
        tmp_path,
        current_release_id=(
            CURRENT_RELEASE
        ),
    )


def test_first_release_proof_rejects_prior_completion(
    tmp_path,
):
    prior = (
        tmp_path
        / ORIGIN_RELEASE
        / "production"
        / ORIGIN_COMMIT
    )

    prior.mkdir(
        parents=True
    )

    (
        prior
        / "sequence-acquisition-completion.json"
    ).write_text(
        "{}\n",
        encoding="ascii",
    )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="prior monthly sequence evidence",
    ):
        module.prove_no_prior_sequence_evidence(
            tmp_path,
            current_release_id=(
                CURRENT_RELEASE
            ),
        )


def test_materialize_verified_candidate(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root
    )

    materialized = (
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )
    )

    assert (
        materialized.retained_origin_eligible_count
        == 1
    )

    assert len(
        materialized.candidates
    ) == 1

    candidate = materialized.candidates[
        0
    ]

    assert candidate.batch_provenance_verified
    assert candidate.components[
        0
    ].sequence == SEQUENCE

    build = verify_cache_candidates(
        materialized.candidates,
        current_source_snapshot_id=(
            CURRENT_SNAPSHOT
        ),
        current_metadata={
            ACCESSION:
                BIOSAMPLE,
        },
    )

    assert build.results[
        0
    ].status == CACHE_VERIFIED

    assert len(
        build.verified_cache
    ) == 1


def test_missing_fasta_object_becomes_fresh_not_malformed(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        write_fasta=False,
    )

    materialized = (
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )
    )

    assert (
        materialized.candidates[
            0
        ].components[
            0
        ].sequence
        == ""
    )

    build = verify_cache_candidates(
        materialized.candidates,
        current_source_snapshot_id=(
            CURRENT_SNAPSHOT
        ),
        current_metadata={
            ACCESSION:
                BIOSAMPLE,
        },
    )

    assert build.results[
        0
    ].status == CACHE_FRESH_REQUIRED

    assert build.results[
        0
    ].reason == REASON_PACKAGE_MISSING


def test_corrupt_fasta_object_becomes_sha_cache_miss(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        corrupt_fasta=True,
    )

    materialized = (
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )
    )

    build = verify_cache_candidates(
        materialized.candidates,
        current_source_snapshot_id=(
            CURRENT_SNAPSHOT
        ),
        current_metadata={
            ACCESSION:
                BIOSAMPLE,
        },
    )

    assert build.results[
        0
    ].status == CACHE_FRESH_REQUIRED

    assert build.results[
        0
    ].reason == REASON_PACKAGE_SHA256


def test_missing_batch_common_package_object_fails_run(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        include_shared=True,
        write_shared=False,
    )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="batch-common",
    ):
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )


def test_origin_ineligible_entry_is_not_materialized(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        write_fasta=False,
        origin_eligible=False,
    )

    materialized = (
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )
    )

    assert materialized.candidates == ()
    assert (
        materialized.retained_origin_eligible_count
        == 0
    )


def test_catalogue_entry_outside_current_metadata_is_not_candidate(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        write_fasta=False,
    )

    materialized = (
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={},
        )
    )

    assert materialized.candidates == ()


def test_current_biosample_change_reaches_frozen_verifier(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root
    )

    materialized = (
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    OTHER_BIOSAMPLE,
            },
        )
    )

    build = verify_cache_candidates(
        materialized.candidates,
        current_source_snapshot_id=(
            CURRENT_SNAPSHOT
        ),
        current_metadata={
            ACCESSION:
                OTHER_BIOSAMPLE,
        },
    )

    assert build.results[
        0
    ].status == CACHE_FRESH_REQUIRED

    assert build.results[
        0
    ].reason == REASON_BIOSAMPLE


def test_malformed_origin_batch_summary_fails_closed(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        malformed_summary=True,
    )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match=(
            "origin Stage 3B "
            "batch-summary audit failed"
        ),
    ):
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )


def test_malformed_origin_completion_fails_closed(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root,
        malformed_completion=True,
    )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match=(
            "origin sequence-acquisition "
            "completion audit failed"
        ),
    ):
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )


def test_missing_batch_artifact_fails_run(
    tmp_path,
):
    root = (
        tmp_path
        / "authoritative"
    )

    root.mkdir()

    _, record = synthetic_catalogue(
        root
    )

    provenance = record[
        "batch_provenance"
    ][
        0
    ]

    digest = provenance[
        "candidate_audit"
    ][
        "sha256"
    ]

    path = (
        root
        / monthly_authoritative_storage.object_key_for_sha256(
            digest
        )
    )

    path.unlink()

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="candidate audit",
    ):
        module.materialize_cache_candidates(
            root,
            catalogue_record=(
                record
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )


def test_completion_receipt_rejects_bad_accounting():
    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="accounting",
    ):
        module.build_completion_receipt(
            release_id=(
                CURRENT_RELEASE
            ),
            source_snapshot_id=(
                CURRENT_SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                "1" * 64
            ),
            execution_commit=(
                CURRENT_COMMIT
            ),
            metadata_record_sha256=(
                "2" * 64
            ),
            metadata_completion_sha256=(
                "3" * 64
            ),
            retained_count=1,
            catalogue_history_mode=(
                module.HISTORY_NONE
            ),
            catalogue_chain_count=0,
            catalogue_chain_sha256_value=(
                "4" * 64
            ),
            source_catalogue_release_id=None,
            source_catalogue_sha256=None,
            source_catalogue_entries_sha256=None,
            source_catalogue_entry_count=0,
            candidate_input_count=1,
            verified_cache_count=1,
            fallback_to_fresh_count=1,
            results_sha256=(
                "5" * 64
            ),
            verified_cache_evidence_sha256=(
                "6" * 64
            ),
            record_sha256=(
                "7" * 64
            ),
        )


def test_execute_first_release_zero_candidates(
    tmp_path,
):
    production = (
        tmp_path
        / "production-root"
    )

    production.mkdir()

    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    stage1 = (
        production
        / CURRENT_RELEASE
        / "production"
        / CURRENT_COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    context = current_context(
        stage1
    )

    result = (
        module.execute_monthly_cache_verification(
            repo=REPO,
            production_root=(
                production
            ),
            stage1_root=(
                stage1
            ),
            authoritative_root=(
                authoritative
            ),
            execution_commit=(
                CURRENT_COMMIT
            ),
            current_context_loader=(
                lambda **kwargs:
                    context
            ),
            chain_loader=(
                lambda **kwargs:
                    ()
            ),
            no_prior_evidence_prover=(
                lambda *args, **kwargs:
                    None
            ),
        )
    )

    assert result.candidate_input_count == 0
    assert result.verified_cache_count == 0
    assert result.fallback_to_fresh_count == 0

    results = (
        result.stage_root
        / module.RESULTS_NAME
    ).read_bytes()

    verified = (
        result.stage_root
        / module.VERIFIED_CACHE_NAME
    ).read_bytes()

    record = (
        result.stage_root
        / module.RECORD_NAME
    ).read_bytes()

    assert results == b""
    assert verified == b""

    audit_cache_verification_results(
        results
    )

    audit_verified_cache_evidence(
        verified
    )

    audit_cache_verification_record(
        record,
        source_snapshot_id=(
            CURRENT_SNAPSHOT
        ),
        source_snapshot_record_sha256=(
            context.source_snapshot_record_sha256
        ),
        metadata_record_sha256=(
            context.metadata_record_sha256
        ),
        metadata_completion_sha256=(
            context.metadata_completion_sha256
        ),
        retained_count=1,
        results_payload=(
            results
        ),
        verified_cache_payload=(
            verified
        ),
    )

    completion = json.loads(
        result.completion_path.read_bytes()
    )

    assert completion[
        "catalogue_history_mode"
    ] == module.HISTORY_NONE

    assert completion[
        "catalogue_chain_count"
    ] == 0


def test_execute_verified_candidate(
    tmp_path,
):
    production = (
        tmp_path
        / "production-root"
    )

    production.mkdir()

    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    item, _ = synthetic_catalogue(
        authoritative
    )

    stage1 = (
        production
        / CURRENT_RELEASE
        / "production"
        / CURRENT_COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    context = current_context(
        stage1
    )

    result = (
        module.execute_monthly_cache_verification(
            repo=REPO,
            production_root=(
                production
            ),
            stage1_root=(
                stage1
            ),
            authoritative_root=(
                authoritative
            ),
            execution_commit=(
                CURRENT_COMMIT
            ),
            current_context_loader=(
                lambda **kwargs:
                    context
            ),
            chain_loader=(
                lambda **kwargs:
                    (
                        item,
                    )
            ),
        )
    )

    assert result.candidate_input_count == 1
    assert result.verified_cache_count == 1
    assert result.fallback_to_fresh_count == 0

    completion = json.loads(
        result.completion_path.read_bytes()
    )

    assert completion[
        "catalogue_history_mode"
    ] == module.HISTORY_CHAINED

    assert completion[
        "source_catalogue_release_id"
    ] == ORIGIN_RELEASE


def test_scientific_stage_publication_uses_hardlinks(
    tmp_path,
):
    partial = (
        tmp_path
        / module.CACHE_PARTIAL_STAGE_NAME
    )

    final = (
        tmp_path
        / module.CACHE_STAGE_NAME
    )

    partial.mkdir(
        mode=0o755
    )

    payloads = (
        b"results\n",
        b"verified\n",
        b"record\n",
    )

    names = (
        module.RESULTS_NAME,
        module.VERIFIED_CACHE_NAME,
        module.RECORD_NAME,
    )

    source_inodes = {}

    for name, payload in zip(
        names,
        payloads,
    ):
        source = (
            partial
            / name
        )

        module.write_fresh_file(
            source,
            payload,
        )

        source_inodes[
            name
        ] = (
            source.stat().st_dev,
            source.stat().st_ino,
        )

    observed = (
        module.promote_scientific_stage_no_clobber(
            partial=partial,
            final=final,
            expected_payloads=(
                payloads
            ),
        )
    )

    assert observed == payloads

    assert not partial.exists()

    assert final.is_dir()

    for name, payload in zip(
        names,
        payloads,
    ):
        target = (
            final
            / name
        )

        assert target.read_bytes() == payload

        assert (
            target.stat().st_dev,
            target.stat().st_ino,
        ) == source_inodes[
            name
        ]


def test_scientific_stage_publication_refuses_existing_empty_final(
    tmp_path,
):
    partial = (
        tmp_path
        / module.CACHE_PARTIAL_STAGE_NAME
    )

    final = (
        tmp_path
        / module.CACHE_STAGE_NAME
    )

    partial.mkdir(
        mode=0o755
    )

    final.mkdir(
        mode=0o755
    )

    payloads = (
        b"results\n",
        b"verified\n",
        b"record\n",
    )

    for name, payload in zip(
        (
            module.RESULTS_NAME,
            module.VERIFIED_CACHE_NAME,
            module.RECORD_NAME,
        ),
        payloads,
    ):
        module.write_fresh_file(
            partial
            / name,
            payload,
        )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="already exists",
    ):
        module.promote_scientific_stage_no_clobber(
            partial=partial,
            final=final,
            expected_payloads=(
                payloads
            ),
        )

    assert partial.is_dir()

    assert final.is_dir()

    assert list(
        final.iterdir()
    ) == []


def test_execute_refuses_existing_stage(
    tmp_path,
):
    production = (
        tmp_path
        / "production-root"
    )

    production.mkdir()

    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    stage1 = (
        production
        / CURRENT_RELEASE
        / "production"
        / CURRENT_COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    (
        stage1
        / module.CACHE_STAGE_NAME
    ).mkdir()

    context = current_context(
        stage1
    )

    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="already exists",
    ):
        module.execute_monthly_cache_verification(
            repo=REPO,
            production_root=(
                production
            ),
            stage1_root=(
                stage1
            ),
            authoritative_root=(
                authoritative
            ),
            execution_commit=(
                CURRENT_COMMIT
            ),
            current_context_loader=(
                lambda **kwargs:
                    context
            ),
            chain_loader=(
                lambda **kwargs:
                    ()
            ),
            no_prior_evidence_prover=(
                lambda *args, **kwargs:
                    None
            ),
        )


def test_main_requires_explicit_authorization():
    with pytest.raises(
        module.MonthlyCacheVerificationExecutionError,
        match="explicit authorization",
    ):
        module.main(
            (
                "--expected-commit",
                CURRENT_COMMIT,
                "--expected-wrapper-sha256",
                "1" * 64,
                "--expected-wrapper-test-sha256",
                "2" * 64,
                "--production-root",
                "/tmp/production",
                "--stage1-root",
                "/tmp/stage1",
                "--authoritative-root",
                "/tmp/objects",
            )
        )


def test_wrapper_contains_no_network_or_institution_bindings():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "requests",
        "urllib",
        "boto3",
        "google.cloud",
        "azure.storage",
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


def test_scientific_stage_names_are_exact():
    assert {
        module.RESULTS_NAME,
        module.VERIFIED_CACHE_NAME,
        module.RECORD_NAME,
    } == {
        "cache-verification-results.jsonl",
        "verified-cache-evidence.jsonl",
        "cache-verification-record.json",
    }

    assert (
        module.COMPLETION_NAME
        == "cache-verification-completion.json"
    )
