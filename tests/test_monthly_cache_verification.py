"""Synthetic tests for the pure monthly verified-cache evidence contract."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

import bacselect.monthly_cache_verification as module
from bacselect.monthly_cache_verification import (
    CACHE_FRESH_REQUIRED,
    CACHE_VERIFIED,
    MonthlyCacheCandidate,
    MonthlyCacheComponent,
    MonthlyCachePackageFileObservation,
    audit_cache_verification_record,
    audit_cache_verification_results,
    audit_verified_cache_evidence,
    assembly_fingerprint_for_candidate,
    build_cache_verification_record,
    component_identity_sha256,
    package_manifest_sha256,
    serialize_cache_verification_record,
    serialize_cache_verification_results,
    serialize_verified_cache_evidence,
    source_evidence_sha256_for_candidate,
    verify_cache_candidate,
    verify_cache_candidates,
)
from bacselect.source_fingerprint import (
    assembly_fingerprint,
    component_sequence_hash,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    ComponentAudit,
    PackageFile,
    source_evidence_sha256,
)


ACCESSION = "GCA_000000001.1"
BIOSAMPLE = "SAMN00000001"
SNAPSHOT = "source-snapshot-20320401T001700Z"
ORIGIN_SNAPSHOT = "source-snapshot-20320301T001700Z"
ORIGIN_RELEASE = "2032.03"
COMMIT = "a" * 40

SEQUENCE = "ACGTACGT"
COMPONENT = "CP000001.1"

COMPONENT_RAW_SHA = hashlib.sha256(
    SEQUENCE.encode(
        "utf-8"
    )
).hexdigest()

FASTA_BYTES = (
    f">{COMPONENT}\n"
    f"{SEQUENCE}\n"
).encode(
    "utf-8"
)

FASTA_SHA = hashlib.sha256(
    FASTA_BYTES
).hexdigest()


def observation(
    path: str,
    payload: bytes,
):
    sha = hashlib.sha256(
        payload
    ).hexdigest()

    return MonthlyCachePackageFileObservation(
        path=path,
        expected_size_bytes=len(
            payload
        ),
        expected_sha256=sha,
        observed_size_bytes=len(
            payload
        ),
        observed_sha256=sha,
    )


def candidate(
    *,
    accession: str = ACCESSION,
    biosample: str = BIOSAMPLE,
    batch_verified: bool = True,
):
    fasta_path = (
        f"ncbi_dataset/data/{accession}/"
        f"{accession}_genomic.fna"
    )

    gbff_payload = b"synthetic gbff\n"
    report_payload = b'{"synthetic":"sequence-report"}\n'
    shared_payload = b'{"synthetic":"assembly-report"}\n'

    files = (
        MonthlyCachePackageFileObservation(
            path=fasta_path,
            expected_size_bytes=len(
                FASTA_BYTES
            ),
            expected_sha256=(
                FASTA_SHA
            ),
            observed_size_bytes=len(
                FASTA_BYTES
            ),
            observed_sha256=(
                FASTA_SHA
            ),
        ),
        observation(
            f"ncbi_dataset/data/{accession}/"
            f"{accession}_genomic.gbff",
            gbff_payload,
        ),
        observation(
            f"ncbi_dataset/data/{accession}/"
            "sequence_report.jsonl",
            report_payload,
        ),
        observation(
            "ncbi_dataset/data/assembly_data_report.jsonl",
            shared_payload,
        ),
    )

    return MonthlyCacheCandidate(
        canonical_genbank_assembly_accession=(
            accession
        ),
        biosample=(
            biosample
        ),
        cache_origin_release_id=(
            ORIGIN_RELEASE
        ),
        cache_origin_source_snapshot_id=(
            ORIGIN_SNAPSHOT
        ),
        cache_origin_git_commit=(
            COMMIT
        ),
        origin_batch_summary_sha256=(
            "1" * 64
        ),
        origin_candidate_audit_sha256=(
            "2" * 64
        ),
        origin_component_audit_sha256=(
            "3" * 64
        ),
        origin_package_files_sha256=(
            "4" * 64
        ),
        batch_provenance_verified=(
            batch_verified
        ),
        candidate_fasta_file=(
            f"{accession}_genomic.fna"
        ),
        candidate_fasta_sha256=(
            FASTA_SHA
        ),
        primary_assembly_records=1,
        components=(
            MonthlyCacheComponent(
                component_accession=(
                    COMPONENT
                ),
                length=len(
                    SEQUENCE
                ),
                topology="circular",
                sequence_sha256=(
                    COMPONENT_RAW_SHA
                ),
                sequence=(
                    SEQUENCE
                ),
            ),
        ),
        package_files=files,
    )


def build_payloads(
    candidates,
    *,
    metadata=None,
):
    if metadata is None:
        metadata = {
            ACCESSION:
                BIOSAMPLE,
        }

    build = verify_cache_candidates(
        candidates,
        current_source_snapshot_id=(
            SNAPSHOT
        ),
        current_metadata=(
            metadata
        ),
    )

    results = (
        serialize_cache_verification_results(
            build.results
        )
    )

    verified = (
        serialize_verified_cache_evidence(
            build.verified_cache
        )
    )

    record = (
        serialize_cache_verification_record(
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                "5" * 64
            ),
            metadata_record_sha256=(
                "6" * 64
            ),
            metadata_completion_sha256=(
                "7" * 64
            ),
            retained_count=len(
                metadata
            ),
            results_payload=(
                results
            ),
            verified_cache_payload=(
                verified
            ),
        )
    )

    return (
        build,
        results,
        verified,
        record,
    )


def test_first_release_zero_cache_is_explicit():
    (
        build,
        results,
        verified,
        record_payload,
    ) = build_payloads(
        ()
    )

    assert build.results == ()
    assert build.verified_cache == ()

    assert results == b""
    assert verified == b""

    record = json.loads(
        record_payload
    )

    assert record[
        "candidate_input_count"
    ] == 0

    assert record[
        "verified_cache_count"
    ] == 0

    assert record[
        "fallback_to_fresh_count"
    ] == 0

    assert record[
        "retained_count"
    ] == 1

    assert record[
        "results_sha256"
    ] == hashlib.sha256(
        b""
    ).hexdigest()

    assert record[
        "verified_cache_evidence_sha256"
    ] == hashlib.sha256(
        b""
    ).hexdigest()


def test_verified_candidate_produces_stage2_evidence():
    (
        build,
        _,
        _,
        _,
    ) = build_payloads(
        (
            candidate(),
        )
    )

    assert len(
        build.results
    ) == 1

    result = build.results[
        0
    ]

    assert result.status == (
        CACHE_VERIFIED
    )

    assert result.reason == (
        module.REASON_VERIFIED
    )

    assert len(
        build.verified_cache
    ) == 1

    evidence = build.verified_cache[
        0
    ]

    assert (
        evidence.canonical_genbank_assembly_accession
        == ACCESSION
    )

    assert evidence.biosample == (
        BIOSAMPLE
    )

    assert (
        evidence.verified_source_snapshot_id
        == SNAPSHOT
    )

    assert (
        evidence.verification_record_sha256
        == result.verification_record_sha256
    )


def test_unverified_batch_provenance_falls_back_to_fresh():
    result, evidence = (
        verify_cache_candidate(
            candidate(
                batch_verified=False
            ),
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )
    )

    assert result.status == (
        CACHE_FRESH_REQUIRED
    )

    assert result.reason == (
        module.REASON_BATCH_PROVENANCE
    )

    assert evidence is None


def test_current_biosample_mismatch_falls_back_to_fresh():
    result, evidence = (
        verify_cache_candidate(
            candidate(),
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                "SAMN00000002"
            ),
        )
    )

    assert result.status == (
        CACHE_FRESH_REQUIRED
    )

    assert result.reason == (
        module.REASON_BIOSAMPLE
    )

    assert evidence is None


def test_missing_package_file_falls_back_to_fresh():
    item = candidate()

    first = item.package_files[
        0
    ]

    changed = replace(
        first,
        observed_size_bytes=None,
        observed_sha256=None,
    )

    item = replace(
        item,
        package_files=(
            changed,
            *item.package_files[
                1:
            ],
        ),
    )

    result, evidence = (
        verify_cache_candidate(
            item,
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )
    )

    assert result.reason == (
        module.REASON_PACKAGE_MISSING
    )

    assert evidence is None


def test_package_size_mismatch_falls_back_to_fresh():
    item = candidate()

    first = item.package_files[
        0
    ]

    changed = replace(
        first,
        observed_size_bytes=(
            first.expected_size_bytes
            + 1
        ),
    )

    item = replace(
        item,
        package_files=(
            changed,
            *item.package_files[
                1:
            ],
        ),
    )

    result, evidence = (
        verify_cache_candidate(
            item,
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )
    )

    assert result.reason == (
        module.REASON_PACKAGE_SIZE
    )

    assert evidence is None


def test_package_sha_mismatch_falls_back_to_fresh():
    item = candidate()

    first = item.package_files[
        0
    ]

    changed = replace(
        first,
        observed_sha256=(
            "f" * 64
        ),
    )

    item = replace(
        item,
        package_files=(
            changed,
            *item.package_files[
                1:
            ],
        ),
    )

    result, evidence = (
        verify_cache_candidate(
            item,
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )
    )

    assert result.reason == (
        module.REASON_PACKAGE_SHA256
    )

    assert evidence is None


def test_component_sequence_mismatch_falls_back_to_fresh():
    item = candidate()

    component = replace(
        item.components[
            0
        ],
        sequence="ACGTACGA",
    )

    item = replace(
        item,
        components=(
            component,
        ),
    )

    result, evidence = (
        verify_cache_candidate(
            item,
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )
    )

    assert result.reason == (
        module.REASON_COMPONENT_SHA256
    )

    assert evidence is None


def test_component_identity_is_component_order_independent():
    first = candidate()

    second_sequence = "AAAACCCC"

    second_component = (
        MonthlyCacheComponent(
            component_accession=(
                "CP000002.1"
            ),
            length=len(
                second_sequence
            ),
            topology="linear",
            sequence_sha256=(
                hashlib.sha256(
                    second_sequence.encode(
                        "utf-8"
                    )
                ).hexdigest()
            ),
            sequence=(
                second_sequence
            ),
        )
    )

    forward = replace(
        first,
        primary_assembly_records=2,
        components=(
            first.components[
                0
            ],
            second_component,
        ),
    )

    reverse = replace(
        forward,
        components=tuple(
            reversed(
                forward.components
            )
        ),
    )

    assert (
        component_identity_sha256(
            forward
        )
        == component_identity_sha256(
            reverse
        )
    )


def test_package_identity_excludes_batch_shared_file():
    first = candidate()

    shared = first.package_files[
        -1
    ]

    changed_shared = replace(
        shared,
        expected_size_bytes=999,
        expected_sha256=(
            "9" * 64
        ),
        observed_size_bytes=999,
        observed_sha256=(
            "9" * 64
        ),
    )

    second = replace(
        first,
        package_files=(
            *first.package_files[
                :-1
            ],
            changed_shared,
        ),
    )

    assert (
        package_manifest_sha256(
            first
        )
        == package_manifest_sha256(
            second
        )
    )


def test_source_evidence_identity_calls_frozen_semantics():
    item = candidate()

    expected_candidate = CandidateAudit(
        accession=ACCESSION,
        audit_path=Path(
            "candidate-sequence-audit.tsv"
        ),
        fasta_file=(
            item.candidate_fasta_file
        ),
        fasta_sha256=(
            item.candidate_fasta_sha256
        ),
        primary_assembly_records=1,
    )

    expected_components = (
        ComponentAudit(
            accession=ACCESSION,
            component_accession=(
                COMPONENT
            ),
            length=len(
                SEQUENCE
            ),
            topology="circular",
            sequence_sha256=(
                COMPONENT_RAW_SHA
            ),
        ),
    )

    expected_package = {
        row.path:
            PackageFile(
                relative_path=(
                    row.path
                ),
                size_bytes=(
                    row.expected_size_bytes
                ),
                sha256=(
                    row.expected_sha256
                ),
            )
        for row in item.package_files
    }

    expected = source_evidence_sha256(
        expected_candidate,
        expected_components,
        expected_package,
    )

    assert (
        source_evidence_sha256_for_candidate(
            item
        )
        == expected
    )


def test_assembly_fingerprint_calls_frozen_topology_semantics():
    item = candidate()

    expected = assembly_fingerprint(
        (
            (
                "circular",
                component_sequence_hash(
                    SEQUENCE,
                    "circular",
                ),
            ),
        )
    )

    assert (
        assembly_fingerprint_for_candidate(
            item
        )
        == expected
    )


def test_duplicate_candidate_accession_fails_closed():
    item = candidate()

    with pytest.raises(
        module.MonthlyCacheVerificationError,
        match="duplicate monthly cache candidate",
    ):
        verify_cache_candidates(
            (
                item,
                item,
            ),
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_metadata={
                ACCESSION:
                    BIOSAMPLE,
            },
        )


def test_candidate_outside_current_metadata_fails_closed():
    with pytest.raises(
        module.MonthlyCacheVerificationError,
        match="not in current metadata-retained",
    ):
        verify_cache_candidates(
            (
                candidate(),
            ),
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_metadata={
                "GCA_000000002.1":
                    "SAMN00000002",
            },
        )


def test_unsafe_package_path_fails_closed():
    item = candidate()

    changed = replace(
        item.package_files[
            1
        ],
        path=(
            "../escape"
        ),
    )

    item = replace(
        item,
        package_files=(
            item.package_files[
                0
            ],
            changed,
            *item.package_files[
                2:
            ],
        ),
    )

    with pytest.raises(
        module.MonthlyCacheVerificationError,
        match="unsafe",
    ):
        verify_cache_candidate(
            item,
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )


def test_duplicate_package_path_fails_closed():
    item = candidate()

    item = replace(
        item,
        package_files=(
            *item.package_files,
            item.package_files[
                0
            ],
        ),
    )

    with pytest.raises(
        module.MonthlyCacheVerificationError,
        match="duplicate package path",
    ):
        verify_cache_candidate(
            item,
            current_source_snapshot_id=(
                SNAPSHOT
            ),
            current_biosample=(
                BIOSAMPLE
            ),
        )


def test_verified_evidence_serialization_is_canonical_and_sorted():
    first = candidate()

    second = candidate(
        accession=(
            "GCA_000000002.1"
        ),
        biosample=(
            "SAMN00000002"
        ),
    )

    build = verify_cache_candidates(
        (
            second,
            first,
        ),
        current_source_snapshot_id=(
            SNAPSHOT
        ),
        current_metadata={
            ACCESSION:
                BIOSAMPLE,
            "GCA_000000002.1":
                "SAMN00000002",
        },
    )

    payload = (
        serialize_verified_cache_evidence(
            reversed(
                build.verified_cache
            )
        )
    )

    audited = (
        audit_verified_cache_evidence(
            payload
        )
    )

    assert tuple(
        item.canonical_genbank_assembly_accession
        for item in audited
    ) == (
        ACCESSION,
        "GCA_000000002.1",
    )

    assert (
        serialize_verified_cache_evidence(
            audited
        )
        == payload
    )


def test_bound_verified_evidence_tamper_is_rejected():
    (
        build,
        results,
        verified,
        record_payload,
    ) = build_payloads(
        (
            candidate(),
        )
    )

    assert build.verified_cache

    changed = verified.replace(
        b'"biosample":"SAMN00000001"',
        b'"biosample":"SAMN00000002"',
    )

    # The Stage 2 payload is structurally valid on its own.
    # Its exact scientific provenance is authenticated by the
    # cache-verification record that binds its payload SHA256.
    structurally_audited = (
        audit_verified_cache_evidence(
            changed
        )
    )

    assert (
        structurally_audited[
            0
        ].biosample
        == "SAMN00000002"
    )

    with pytest.raises(
        module.MonthlyCacheVerificationError,
        match="verified cache evidence differs from verification result",
    ):
        audit_cache_verification_record(
            record_payload,
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                "5" * 64
            ),
            metadata_record_sha256=(
                "6" * 64
            ),
            metadata_completion_sha256=(
                "7" * 64
            ),
            retained_count=1,
            results_payload=(
                results
            ),
            verified_cache_payload=(
                changed
            ),
        )


def test_result_serialization_is_canonical_and_sorted():
    first = candidate()

    second = candidate(
        accession=(
            "GCA_000000002.1"
        ),
        biosample=(
            "SAMN00000002"
        ),
    )

    build = verify_cache_candidates(
        (
            second,
            first,
        ),
        current_source_snapshot_id=(
            SNAPSHOT
        ),
        current_metadata={
            ACCESSION:
                BIOSAMPLE,
            "GCA_000000002.1":
                "SAMN00000002",
        },
    )

    payload = (
        serialize_cache_verification_results(
            reversed(
                build.results
            )
        )
    )

    audited = (
        audit_cache_verification_results(
            payload
        )
    )

    assert tuple(
        record[
            "canonical_genbank_assembly_accession"
        ]
        for record in audited
    ) == (
        ACCESSION,
        "GCA_000000002.1",
    )


def test_record_binds_current_metadata_and_verified_payloads():
    (
        _,
        results,
        verified,
        record_payload,
    ) = build_payloads(
        (
            candidate(),
        )
    )

    record = (
        audit_cache_verification_record(
            record_payload,
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                "5" * 64
            ),
            metadata_record_sha256=(
                "6" * 64
            ),
            metadata_completion_sha256=(
                "7" * 64
            ),
            retained_count=1,
            results_payload=(
                results
            ),
            verified_cache_payload=(
                verified
            ),
        )
    )

    assert record[
        "candidate_input_count"
    ] == 1

    assert record[
        "verified_cache_count"
    ] == 1

    assert record[
        "fallback_to_fresh_count"
    ] == 0

    assert record[
        "source_snapshot_id"
    ] == SNAPSHOT


def test_record_tamper_is_rejected():
    (
        _,
        results,
        verified,
        record_payload,
    ) = build_payloads(
        (
            candidate(),
        )
    )

    changed = record_payload.replace(
        b'"verified_cache_count":1',
        b'"verified_cache_count":0',
    )

    with pytest.raises(
        module.MonthlyCacheVerificationError,
        match="derived identity",
    ):
        audit_cache_verification_record(
            changed,
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                "5" * 64
            ),
            metadata_record_sha256=(
                "6" * 64
            ),
            metadata_completion_sha256=(
                "7" * 64
            ),
            retained_count=1,
            results_payload=(
                results
            ),
            verified_cache_payload=(
                verified
            ),
        )


def test_module_is_pure_and_has_no_historical_binding():
    text = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "subprocess",
        "requests",
        "urllib",
        "urlopen",
        "http.client",
        "socket.",
        "/NGS/",
        "Rhys_wkdir",
        "Project Finch",
        "EXPECTED_HISTORICAL",
        "55_426",
        "111",
        "166_844",
    ):
        assert token not in text
