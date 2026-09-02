from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from bacselect import monthly_sequence_cache_catalogue as v1
from bacselect import monthly_sequence_acquisition_completion_v2 as completion_v2
from bacselect.monthly_sequence_cache_catalogue_v2 import (
    AuthoritativeSequenceCacheBatchEvidenceV2,
    BATCH_PROVENANCE_SET_V2_SCHEMA,
    BATCH_PROVENANCE_V2_SCHEMA,
    ENTRY_SET_V2_SCHEMA,
    ENTRY_V2_SCHEMA,
    GENESIS,
    MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA,
    MonthlySequenceCacheCatalogueV2Error,
    RECOVERY_CLASS_MISSING_DATASETS_GBFF,
    SOURCE_CLASS_FRESH,
    SOURCE_CLASS_FRESH_RECOVERY,
    audit_sequence_cache_catalogue_v2,
    build_sequence_cache_catalogue_v2,
    serialize_sequence_cache_catalogue_v2,
)
from bacselect.monthly_sequence_transport import (
    batch_accession_bytes,
    batch_target_manifest_sha256,
)


ROOT = Path(
    __file__
).resolve().parents[
    1
]

COMPLETION_COMMIT = (
    "b" * 40
)

CACHE_COMMIT = (
    "c" * 40
)

RECOVERY_COMMIT = (
    "d" * 40
)

TEST_RELEASE = (
    "2032.04"
)

TEST_SNAPSHOT = (
    "bacselect-source-2032.04-"
    "20320401T000000Z"
)


def load_fixture():
    path = (
        ROOT
        / "tests"
        / "test_monthly_sequence_acquisition_completion.py"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            "_bacselect_cache_v2_completion_fixture",
            path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "could not load frozen completion fixture"
        )

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


fixture = load_fixture()


def sha(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def canonical(
    value,
) -> bytes:
    return v1._canonical_json_bytes(
        value
    )


def make_scientific_payloads(
    targets,
):
    candidate_rows = []
    component_rows = []
    package_rows = []

    for index, target in enumerate(
        targets,
        1,
    ):
        accession = (
            target
            .canonical_genbank_assembly_accession
        )

        biosample = (
            target
            .source_biosample
        )

        fasta_basename = (
            f"{accession}_genomic.fna"
        )

        package_path = (
            "ncbi_dataset/data/"
            f"{accession}/"
            f"{fasta_basename}"
        )

        fasta_sha = sha(
            (
                accession
                + "\n"
            ).encode(
                "ascii"
            )
        )

        candidate = {
            field:
                "synthetic"
            for field
            in v1.CANDIDATE_AUDIT_FIELDS
        }

        candidate.update(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "expected_biosample":
                    biosample,
                "observed_biosample":
                    biosample,
                "exclusion_reasons":
                    "none",
                "fasta_file":
                    fasta_basename,
                "fasta_sha256":
                    fasta_sha,
                "primary_assembly_records":
                    "1",
                "result":
                    "PASS",
                "sequence_eligibility":
                    v1.SEQUENCE_ELIGIBLE,
            }
        )

        candidate_rows.append(
            candidate
        )

        component = {
            field:
                "synthetic"
            for field
            in v1.COMPONENT_AUDIT_FIELDS
        }

        component.update(
            {
                "ambiguous_base_count":
                    "0",
                "canonical_genbank_assembly_accession":
                    accession,
                "component_genbank_accession":
                    f"CP{index:06d}.1",
                "length":
                    "4",
                "sequence_sha256":
                    sha(
                        (
                            accession
                            + ":component\n"
                        ).encode(
                            "ascii"
                        )
                    ),
                "topology":
                    "circular",
            }
        )

        component_rows.append(
            component
        )

        package_rows.append(
            {
                "path":
                    package_path,
                "sha256":
                    fasta_sha,
                "size_bytes":
                    "4",
            }
        )

    candidate_rows.sort(
        key=lambda row:
            row[
                "canonical_genbank_assembly_accession"
            ]
    )

    component_rows.sort(
        key=lambda row:
            (
                row[
                    "canonical_genbank_assembly_accession"
                ],
                row[
                    "component_genbank_accession"
                ],
            )
    )

    package_rows.sort(
        key=lambda row:
            row[
                "path"
            ]
    )

    return (
        v1._serialize_tsv(
            candidate_rows,
            fields=(
                v1.CANDIDATE_AUDIT_FIELDS
            ),
        ),
        v1._serialize_tsv(
            component_rows,
            fields=(
                v1.COMPONENT_AUDIT_FIELDS
            ),
        ),
        v1._serialize_tsv(
            package_rows,
            fields=(
                v1.PACKAGE_FILE_FIELDS
            ),
        ),
    )


def make_current(
    *,
    source_class=SOURCE_CLASS_FRESH,
):
    (
        plan,
        manifest,
        targets,
    ) = fixture.make_plan(
        1
    )

    old_snapshot_bytes = (
        fixture.SNAPSHOT.encode(
            "ascii"
        )
    )

    new_snapshot_bytes = (
        TEST_SNAPSHOT.encode(
            "ascii"
        )
    )

    if plan.count(
        old_snapshot_bytes
    ) != 1:
        raise RuntimeError(
            "frozen synthetic plan snapshot binding changed"
        )

    plan = plan.replace(
        old_snapshot_bytes,
        new_snapshot_bytes,
        1,
    )

    (
        candidate_payload,
        component_payload,
        package_payload,
    ) = make_scientific_payloads(
        targets
    )

    if source_class == SOURCE_CLASS_FRESH:
        provider_name = (
            completion_v2
            .FRESH_PROVIDER_SUMMARY_NAME
        )

        package_name = (
            completion_v2
            .FRESH_PACKAGE_MANIFEST_NAME
        )

        recovery_class = None
        source_partial_name = None
        recovery_commit = None
        source_batch_sha = None
        source_package_sha = None
        recovery_package_sha = None
        recovery_summary_sha = None
        cause_evidence_sha = None
        transport_record_sha = None

        provider_payload = canonical(
            {
                "status":
                    "SYNTHETIC_FRESH"
            }
        )

    else:
        provider_name = (
            completion_v2
            .RECOVERY_PROVIDER_SUMMARY_NAME
        )

        package_name = (
            completion_v2
            .RECOVERY_PACKAGE_MANIFEST_NAME
        )

        recovery_class = (
            RECOVERY_CLASS_MISSING_DATASETS_GBFF
        )

        source_partial_name = (
            "batch-00001.partial"
        )

        recovery_commit = (
            RECOVERY_COMMIT
        )

        source_batch_sha = (
            "1" * 64
        )

        source_package_sha = (
            "2" * 64
        )

        recovery_package_sha = sha(
            package_payload
        )

        cause_evidence_sha = (
            "3" * 64
        )

        transport_record_sha = None

        provider_payload = canonical(
            {
                "status":
                    "SYNTHETIC_RECOVERY"
            }
        )

        recovery_summary_sha = sha(
            provider_payload
        )

    if source_class == SOURCE_CLASS_FRESH:
        recovery_summary_sha = None

    target_sha = (
        batch_target_manifest_sha256(
            targets
        )
    )

    accessions_sha = sha(
        batch_accession_bytes(
            targets
        )
    )

    readback_sha = sha(
        b"synthetic-readback\n"
    )

    completion_evidence = (
        completion_v2
        .AuthoritativeCompletedBatchEvidence(
            batch_id="batch-00001",
            source_class=(
                source_class
            ),
            recovery_class=(
                recovery_class
            ),
            requested_accessions=1,
            first_accession=(
                targets[
                    0
                ].canonical_genbank_assembly_accession
            ),
            last_accession=(
                targets[
                    -1
                ].canonical_genbank_assembly_accession
            ),
            observed_batch_target_manifest_sha256=(
                target_sha
            ),
            observed_accessions_sha256=(
                accessions_sha
            ),
            observed_candidate_audit_sha256=(
                sha(
                    candidate_payload
                )
            ),
            observed_component_audit_sha256=(
                sha(
                    component_payload
                )
            ),
            provider_summary_name=(
                provider_name
            ),
            provider_summary_sha256=(
                sha(
                    provider_payload
                )
            ),
            package_manifest_name=(
                package_name
            ),
            package_manifest_sha256=(
                sha(
                    package_payload
                )
            ),
            package_file_count=1,
            package_file_readback_count=1,
            package_file_readback_sha256=(
                readback_sha
            ),
            source_partial_name=(
                source_partial_name
            ),
            recovery_commit=(
                recovery_commit
            ),
            source_batch_sha256=(
                source_batch_sha
            ),
            source_package_sha256=(
                source_package_sha
            ),
            recovery_package_sha256=(
                recovery_package_sha
            ),
            recovery_summary_sha256=(
                recovery_summary_sha
            ),
            cause_evidence_sha256=(
                cause_evidence_sha
            ),
            transport_record_sha256=(
                transport_record_sha
            ),
        )
    )

    completion_payload = (
        completion_v2
        .serialize_sequence_acquisition_completion_v2_record(
            source_snapshot_id=(
                TEST_SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                fixture.SNAPSHOT_SHA
            ),
            stage2_sequence_plan_record=(
                plan
            ),
            stage2_fresh_target_manifest=(
                manifest
            ),
            source_production_commit=(
                fixture.COMMIT
            ),
            completion_execution_commit=(
                COMPLETION_COMMIT
            ),
            environment_explicit_sha256=(
                fixture.ENVIRONMENT_SHA
            ),
            batches=(
                completion_evidence,
            ),
        )
    )

    cache_evidence = (
        AuthoritativeSequenceCacheBatchEvidenceV2(
            batch_id="batch-00001",
            source_class=(
                source_class
            ),
            recovery_class=(
                recovery_class
            ),
            provider_summary_name=(
                provider_name
            ),
            provider_summary_payload=(
                provider_payload
            ),
            candidate_audit_payload=(
                candidate_payload
            ),
            component_audit_payload=(
                component_payload
            ),
            package_manifest_name=(
                package_name
            ),
            package_manifest_payload=(
                package_payload
            ),
            source_partial_name=(
                source_partial_name
            ),
            recovery_commit=(
                recovery_commit
            ),
            source_batch_sha256=(
                source_batch_sha
            ),
            source_package_sha256=(
                source_package_sha
            ),
            recovery_package_sha256=(
                recovery_package_sha
            ),
            recovery_summary_sha256=(
                recovery_summary_sha
            ),
            cause_evidence_sha256=(
                cause_evidence_sha
            ),
            transport_record_sha256=(
                transport_record_sha
            ),
        )
    )

    return {
        "targets":
            targets,
        "completion":
            completion_payload,
        "evidence":
            cache_evidence,
    }


def build_kwargs(
    values,
    *,
    previous=None,
):
    return {
        "release_id":
            TEST_RELEASE,
        "source_snapshot_id":
            TEST_SNAPSHOT,
        "source_production_commit":
            fixture.COMMIT,
        "completion_execution_commit":
            COMPLETION_COMMIT,
        "cache_execution_commit":
            CACHE_COMMIT,
        "sequence_acquisition_completion_payload":
            values[
                "completion"
            ],
        "current_batches":
            (
                values[
                    "evidence"
                ],
            ),
        "previous_catalogue_payload":
            previous,
    }


def make_legacy_v1_catalogue(
    *,
    accession,
    biosample,
):
    batch = "batch-00001"

    summary_payload = canonical(
        {
            "status":
                "LEGACY"
        }
    )

    candidate_payload = b"legacy candidate\n"
    component_payload = b"legacy component\n"
    package_manifest_payload = b"legacy manifest\n"

    package_row = {
        "path":
            (
                "ncbi_dataset/data/"
                f"{accession}/"
                f"{accession}_genomic.fna"
            ),
        "sha256":
            "4" * 64,
        "size_bytes":
            "4",
    }

    provenance_base = {
        "accessions_sha256":
            sha(
                (
                    accession
                    + "\n"
                ).encode(
                    "ascii"
                )
            ),
        "batch_id":
            batch,
        "batch_summary":
            v1._artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "batch-summary.json"
                ),
                payload=(
                    summary_payload
                ),
            ),
        "cache_origin_git_commit":
            fixture.COMMIT,
        "cache_origin_release_id":
            "2026.08",
        "cache_origin_source_snapshot_id":
            (
                "bacselect-source-2026.08-"
                "20260801T000000Z"
            ),
        "candidate_audit":
            v1._artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "candidate-sequence-audit.tsv"
                ),
                payload=(
                    candidate_payload
                ),
            ),
        "component_audit":
            v1._artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "component-sequence-audit.tsv"
                ),
                payload=(
                    component_payload
                ),
            ),
        "origin_package_file_readback_sha256":
            "5" * 64,
        "origin_sequence_acquisition_completion_sha256":
            "6" * 64,
        "package_files_manifest":
            v1._artifact_reference(
                logical_path=(
                    f"sequence-acquisition/{batch}/"
                    "package-files.tsv"
                ),
                payload=(
                    package_manifest_payload
                ),
            ),
        "requested_accessions":
            1,
    }

    provenance_sha = sha(
        v1._batch_provenance_payload(
            provenance_base
        )
    )

    provenance = {
        **provenance_base,
        "batch_provenance_sha256":
            provenance_sha,
    }

    artifact = v1._package_artifact(
        package_row,
        batch_id=batch,
    )

    entry_base = {
        "biosample":
            biosample,
        "canonical_genbank_assembly_accession":
            accession,
        "origin_batch_provenance_sha256":
            provenance_sha,
        "origin_sequence_eligibility":
            v1.SEQUENCE_ELIGIBLE,
        "origin_sequence_exclusion_reasons":
            "none",
        "package_artifacts":
            [
                artifact
            ],
    }

    entry = {
        **entry_base,
        "entry_sha256":
            sha(
                v1._entry_payload(
                    entry_base
                )
            ),
    }

    batch_set_sha = sha(
        v1._canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-"
                "batch-provenance-set-v1"
            ),
            field="batch_provenance",
            values=(
                provenance,
            ),
        )
    )

    entry_set_sha = sha(
        v1._canonical_list_payload(
            schema_version=(
                "bacselect-monthly-sequence-cache-"
                "entry-set-v1"
            ),
            field="entries",
            values=(
                entry,
            ),
        )
    )

    record = {
        "batch_provenance":
            [
                provenance
            ],
        "batch_provenance_count":
            1,
        "batch_provenance_sha256":
            batch_set_sha,
        "carried_forward_entry_count":
            0,
        "catalogue_entry_count":
            1,
        "catalogue_mode":
            v1.GENESIS,
        "current_acquisition_count":
            1,
        "entries":
            [
                entry
            ],
        "entries_sha256":
            entry_set_sha,
        "new_entry_count":
            1,
        "origin_git_commit":
            fixture.COMMIT,
        "previous_catalogue_entry_count":
            0,
        "previous_catalogue_release_id":
            None,
        "previous_catalogue_sha256":
            None,
        "release_id":
            "2026.08",
        "replaced_entry_count":
            0,
        "schema_version":
            v1.MONTHLY_SEQUENCE_CACHE_CATALOGUE_SCHEMA,
        "sequence_acquisition_completion_sha256":
            "6" * 64,
        "sequence_acquisition_fresh_count":
            1,
        "source_snapshot_id":
            (
                "bacselect-source-2026.08-"
                "20260801T000000Z"
            ),
        "status":
            v1.MONTHLY_SEQUENCE_CACHE_CATALOGUE_STATUS,
    }

    payload = canonical(
        record
    )

    v1.audit_sequence_cache_catalogue(
        payload
    )

    return (
        payload,
        provenance,
        entry,
    )


def test_schema_domains_are_v2():
    assert (
        MONTHLY_SEQUENCE_CACHE_CATALOGUE_V2_SCHEMA
        == "bacselect-monthly-sequence-cache-catalogue-v2"
    )

    assert (
        BATCH_PROVENANCE_V2_SCHEMA
        == "bacselect-monthly-sequence-cache-batch-provenance-v2"
    )

    assert (
        ENTRY_V2_SCHEMA
        == "bacselect-monthly-sequence-cache-entry-v2"
    )

    assert (
        BATCH_PROVENANCE_SET_V2_SCHEMA
        == "bacselect-monthly-sequence-cache-batch-provenance-set-v2"
    )

    assert (
        ENTRY_SET_V2_SCHEMA
        == "bacselect-monthly-sequence-cache-entry-set-v2"
    )


def test_fresh_genesis_round_trip():
    values = make_current()

    payload = (
        serialize_sequence_cache_catalogue_v2(
            **build_kwargs(
                values
            )
        )
    )

    audited = (
        audit_sequence_cache_catalogue_v2(
            payload
        )
    )

    assert (
        audited[
            "catalogue_mode"
        ]
        == GENESIS
    )

    assert (
        audited[
            "current_acquisition_count"
        ]
        == 1
    )

    assert audited[
        "sequence_acquisition_source_class_counts"
    ] == {
        SOURCE_CLASS_FRESH:
            1,
        SOURCE_CLASS_FRESH_RECOVERY:
            0,
    }

    provenance = audited[
        "batch_provenance"
    ][0]

    assert (
        provenance[
            "source_class"
        ]
        == SOURCE_CLASS_FRESH
    )

    assert (
        provenance[
            "recovery_class"
        ]
        is None
    )


def test_recovery_genesis_preserves_authority_and_logical_paths():
    values = make_current(
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        )
    )

    payload = (
        serialize_sequence_cache_catalogue_v2(
            **build_kwargs(
                values
            )
        )
    )

    audited = (
        audit_sequence_cache_catalogue_v2(
            payload
        )
    )

    provenance = audited[
        "batch_provenance"
    ][0]

    assert (
        provenance[
            "source_class"
        ]
        == SOURCE_CLASS_FRESH_RECOVERY
    )

    assert (
        provenance[
            "recovery_class"
        ]
        == RECOVERY_CLASS_MISSING_DATASETS_GBFF
    )

    assert (
        provenance[
            "source_partial_name"
        ]
        == "batch-00001.partial"
    )

    expected_prefix = (
        "sequence-acquisition-recovery/"
        f"{RECOVERY_COMMIT}/"
        f"source-{fixture.COMMIT}/"
        "batch-00001/"
    )

    assert (
        provenance[
            "provider_summary"
        ][
            "logical_path"
        ]
        == (
            expected_prefix
            + "recovery-summary.json"
        )
    )

    assert (
        provenance[
            "package_manifest"
        ][
            "logical_path"
        ]
        == (
            expected_prefix
            + "recovery-package-files.tsv"
        )
    )

    artifact = audited[
        "entries"
    ][0][
        "package_artifacts"
    ][0]

    assert artifact[
        "logical_path"
    ].startswith(
        expected_prefix
        + "package/"
    )

    assert (
        "sequence-acquisition/batch-00001/"
        not in artifact[
            "logical_path"
        ]
    )


def test_recovery_source_class_is_not_duplicated_into_entry():
    values = make_current(
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        )
    )

    record = (
        build_sequence_cache_catalogue_v2(
            **build_kwargs(
                values
            )
        )
    )

    entry = record[
        "entries"
    ][0]

    assert "source_class" not in entry
    assert "recovery_class" not in entry

    origin = entry[
        "origin_batch_provenance_sha256"
    ]

    assert origin == (
        record[
            "batch_provenance"
        ][0][
            "batch_provenance_sha256"
        ]
    )


def test_provider_summary_tamper_fails_closed():
    values = make_current()

    changed = replace(
        values[
            "evidence"
        ],
        provider_summary_payload=(
            values[
                "evidence"
            ].provider_summary_payload
            + b"x"
        ),
    )

    kwargs = build_kwargs(
        values
    )

    kwargs[
        "current_batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="provider summary identity differs",
    ):
        build_sequence_cache_catalogue_v2(
            **kwargs
        )


def test_candidate_audit_tamper_fails_closed():
    values = make_current()

    changed = replace(
        values[
            "evidence"
        ],
        candidate_audit_payload=(
            values[
                "evidence"
            ].candidate_audit_payload
            + b"x"
        ),
    )

    kwargs = build_kwargs(
        values
    )

    kwargs[
        "current_batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="candidate audit identity differs",
    ):
        build_sequence_cache_catalogue_v2(
            **kwargs
        )


def test_package_manifest_tamper_fails_closed():
    values = make_current(
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        )
    )

    changed = replace(
        values[
            "evidence"
        ],
        package_manifest_payload=(
            values[
                "evidence"
            ].package_manifest_payload
            + b"x"
        ),
    )

    kwargs = build_kwargs(
        values
    )

    kwargs[
        "current_batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="package manifest identity differs",
    ):
        build_sequence_cache_catalogue_v2(
            **kwargs
        )


def test_source_class_mismatch_fails_closed():
    values = make_current()

    changed = replace(
        values[
            "evidence"
        ],
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        ),
    )

    kwargs = build_kwargs(
        values
    )

    kwargs[
        "current_batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="source class differs",
    ):
        build_sequence_cache_catalogue_v2(
            **kwargs
        )


def test_recovery_identity_mismatch_fails_closed():
    values = make_current(
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        )
    )

    changed = replace(
        values[
            "evidence"
        ],
        recovery_commit=(
            "e" * 40
        ),
    )

    kwargs = build_kwargs(
        values
    )

    kwargs[
        "current_batches"
    ] = (
        changed,
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="recovery_commit differs",
    ):
        build_sequence_cache_catalogue_v2(
            **kwargs
        )


def test_previous_v1_entry_is_carried_without_rehash():
    values = make_current()

    (
        legacy_payload,
        legacy_provenance,
        legacy_entry,
    ) = make_legacy_v1_catalogue(
        accession="GCA_900000001.1",
        biosample="SAMN90000001",
    )

    payload = (
        serialize_sequence_cache_catalogue_v2(
            **build_kwargs(
                values,
                previous=(
                    legacy_payload
                ),
            )
        )
    )

    audited = (
        audit_sequence_cache_catalogue_v2(
            payload
        )
    )

    carried = next(
        entry
        for entry in audited[
            "entries"
        ]
        if (
            entry[
                "canonical_genbank_assembly_accession"
            ]
            == "GCA_900000001.1"
        )
    )

    assert (
        carried[
            "entry_sha256"
        ]
        == legacy_entry[
            "entry_sha256"
        ]
    )

    legacy_batch = next(
        row
        for row in audited[
            "batch_provenance"
        ]
        if (
            row[
                "batch_provenance_sha256"
            ]
            == legacy_provenance[
                "batch_provenance_sha256"
            ]
        )
    )

    assert legacy_batch == (
        legacy_provenance
    )

    assert (
        audited[
            "carried_forward_entry_count"
        ]
        == 1
    )

    assert (
        audited[
            "new_entry_count"
        ]
        == 1
    )

    assert (
        audited[
            "replaced_entry_count"
        ]
        == 0
    )


def test_current_v2_entry_replaces_same_legacy_accession():
    values = make_current()

    target = values[
        "targets"
    ][0]

    legacy_payload, _, legacy_entry = (
        make_legacy_v1_catalogue(
            accession=(
                target
                .canonical_genbank_assembly_accession
            ),
            biosample=(
                target
                .source_biosample
            ),
        )
    )

    audited = (
        audit_sequence_cache_catalogue_v2(
            serialize_sequence_cache_catalogue_v2(
                **build_kwargs(
                    values,
                    previous=(
                        legacy_payload
                    ),
                )
            )
        )
    )

    assert (
        audited[
            "catalogue_entry_count"
        ]
        == 1
    )

    assert (
        audited[
            "carried_forward_entry_count"
        ]
        == 0
    )

    assert (
        audited[
            "new_entry_count"
        ]
        == 0
    )

    assert (
        audited[
            "replaced_entry_count"
        ]
        == 1
    )

    current = audited[
        "entries"
    ][0]

    assert (
        current[
            "entry_sha256"
        ]
        != legacy_entry[
            "entry_sha256"
        ]
    )

    assert (
        current[
            "origin_batch_provenance_sha256"
        ]
        == audited[
            "batch_provenance"
        ][0][
            "batch_provenance_sha256"
        ]
    )


def test_noncanonical_previous_v1_catalogue_fails_closed():
    values = make_current()

    legacy_payload, _, _ = (
        make_legacy_v1_catalogue(
            accession="GCA_900000001.1",
            biosample="SAMN90000001",
        )
    )

    changed = (
        legacy_payload
        + b"\n"
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="previous cache-v1 catalogue audit failed",
    ):
        build_sequence_cache_catalogue_v2(
            **build_kwargs(
                values,
                previous=(
                    changed
                ),
            )
        )


def test_tampered_v2_recovery_logical_path_fails_self_audit():
    values = make_current(
        source_class=(
            SOURCE_CLASS_FRESH_RECOVERY
        )
    )

    payload = (
        serialize_sequence_cache_catalogue_v2(
            **build_kwargs(
                values
            )
        )
    )

    record = json.loads(
        payload.decode(
            "ascii"
        )
    )

    record[
        "entries"
    ][0][
        "package_artifacts"
    ][0][
        "logical_path"
    ] = (
        "sequence-acquisition/"
        "batch-00001/package/"
        + record[
            "entries"
        ][0][
            "package_artifacts"
        ][0][
            "package_path"
        ]
    )

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="package logical path",
    ):
        audit_sequence_cache_catalogue_v2(
            canonical(
                record
            )
        )


def test_tampered_v2_entry_hash_fails_self_audit():
    values = make_current()

    record = (
        build_sequence_cache_catalogue_v2(
            **build_kwargs(
                values
            )
        )
    )

    record[
        "entries"
    ][0][
        "entry_sha256"
    ] = "f" * 64

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="entry SHA256 changed",
    ):
        audit_sequence_cache_catalogue_v2(
            canonical(
                record
            )
        )


def test_tampered_source_class_counts_fail_self_audit():
    values = make_current()

    record = (
        build_sequence_cache_catalogue_v2(
            **build_kwargs(
                values
            )
        )
    )

    record[
        "sequence_acquisition_source_class_counts"
    ] = {
        SOURCE_CLASS_FRESH:
            0,
        SOURCE_CLASS_FRESH_RECOVERY:
            1,
    }

    with pytest.raises(
        MonthlySequenceCacheCatalogueV2Error,
        match="source-class counts changed",
    ):
        audit_sequence_cache_catalogue_v2(
            canonical(
                record
            )
        )


def test_core_has_no_filesystem_network_or_incident_bindings():
    text = (
        ROOT
        / "src"
        / "bacselect"
        / "monthly_sequence_cache_catalogue_v2.py"
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "pathlib",
        "Path(",
        "os.",
        "subprocess",
        "requests.",
        "urllib.",
        "socket.",
        "/NGS/",
        "Rhys_wkdir",
        "batch-00072",
        "batch-00118",
        "batch-00130",
        "GCA_030436345.2",
        "GCA_055419085.2",
        "GCA_059637575.1",
        "resolve_authoritative_sequence_batches",
        "audit_authoritative_recovery_provider",
        "audit_completed_transport_provider",
    ):
        assert token not in text
