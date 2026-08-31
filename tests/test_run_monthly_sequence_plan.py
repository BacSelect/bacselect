from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from bacselect import (
    monthly_cache_verification as cache_contract,
)
from bacselect import (
    monthly_metadata_eligibility as metadata_contract,
)
from bacselect import (
    monthly_sequence_plan as plan_contract,
)


REPO = Path(
    __file__
).resolve().parents[
    1
]

WRAPPER_PATH = (
    REPO
    / "validation/selector-v1/"
    "run_monthly_sequence_plan.py"
)

SPEC = importlib.util.spec_from_file_location(
    "_bacselect_test_monthly_sequence_plan_execution",
    WRAPPER_PATH,
)

assert SPEC is not None
assert SPEC.loader is not None

module = importlib.util.module_from_spec(
    SPEC
)

sys.modules[
    SPEC.name
] = module

SPEC.loader.exec_module(
    module
)


COMMIT = (
    "a9dd6fe1235b2209d926b9bae3d027092d629eff"
)

RELEASE = (
    "2032.03"
)

SNAPSHOT = (
    "bacselect-source-2032.03-20320301T001700Z"
)

SNAPSHOT_SHA = (
    "1" * 64
)

METADATA_RECORD_SHA = (
    "2" * 64
)

METADATA_COMPLETION_SHA = (
    "3" * 64
)

ACCESSION_1 = (
    "GCA_000000001.1"
)

ACCESSION_2 = (
    "GCA_000000002.1"
)

BIOSAMPLE_1 = (
    "SAMN00000001"
)

BIOSAMPLE_2 = (
    "SAMN00000002"
)

SOURCE_RELEASE = (
    "2032.02"
)

SOURCE_COMMIT = (
    "b" * 40
)

SOURCE_CATALOGUE_SHA = (
    "a" * 64
)

SOURCE_ENTRIES_SHA = (
    "b" * 64
)

CHAIN_SHA = (
    "c" * 64
)


def fake_git_reader(
    repo,
    args,
):
    assert Path(
        repo
    ).resolve() == REPO

    if tuple(
        args
    ) == (
        "rev-parse",
        "HEAD",
    ):
        return COMMIT

    if tuple(
        args
    ) == (
        "status",
        "--short",
    ):
        return ""

    raise AssertionError(
        args
    )


def sha(
    payload,
):
    return hashlib.sha256(
        payload
    ).hexdigest()


def retained_assessment(
    accession,
    biosample,
):
    return metadata_contract.MetadataAssessment(
        accession=accession,
        biosample=biosample,
        decision="RETAIN_METADATA",
        reasons=(),
        normalized_warnings=(),
    )


def assessment_payload(
    assessments,
):
    return (
        metadata_contract.serialize_metadata_assessments(
            assessments
        )
    )


def context_for(
    retained,
):
    return SimpleNamespace(
        release_id=RELEASE,
        source_snapshot_id=SNAPSHOT,
        stage1_root=None,
        source_snapshot_record_sha256=(
            SNAPSHOT_SHA
        ),
        metadata_record_sha256=(
            METADATA_RECORD_SHA
        ),
        metadata_completion_sha256=(
            METADATA_COMPLETION_SHA
        ),
        retained_metadata=dict(
            retained
        ),
    )


def verified_evidence(
    accession,
    biosample,
):
    return plan_contract.VerifiedMonthlyCacheEvidence(
        canonical_genbank_assembly_accession=(
            accession
        ),
        biosample=biosample,
        verified_source_snapshot_id=(
            SNAPSHOT
        ),
        component_identity_sha256=(
            "4" * 64
        ),
        assembly_fingerprint=(
            "5" * 64
        ),
        source_evidence_sha256=(
            "6" * 64
        ),
        package_manifest_sha256=(
            "7" * 64
        ),
        verification_record_sha256=(
            "8" * 64
        ),
    )


def direct_inputs(
    *,
    assessments,
    verified=(),
):
    retained = {
        item.accession:
            item.biosample
        for item in assessments
        if item.decision
        == "RETAIN_METADATA"
    }

    context = context_for(
        retained
    )

    payload = assessment_payload(
        assessments
    )

    return module.SequencePlanInputs(
        metadata_context=context,
        metadata_identity=(
            RELEASE,
            SNAPSHOT,
            SNAPSHOT_SHA,
            METADATA_RECORD_SHA,
            METADATA_COMPLETION_SHA,
            tuple(
                sorted(
                    retained.items()
                )
            ),
        ),
        assessments_payload=payload,
        assessments=tuple(
            assessments
        ),
        cache_results_payload=b"",
        verified_cache_payload=b"",
        cache_record_payload=b"record\n",
        cache_completion_payload=b"completion\n",
        verified_cache=tuple(
            verified
        ),
        cache_record={},
        cache_completion={},
        catalogue_history_mode=(
            "NO_PRIOR_SEQUENCE_EVIDENCE"
        ),
        catalogue_chain_count=0,
        catalogue_chain_sha256=(
            "9" * 64
        ),
    )


def source_chain_item():
    return SimpleNamespace(
        release_id=(
            SOURCE_RELEASE
        ),
        origin_git_commit=(
            SOURCE_COMMIT
        ),
        catalogue_sha256=(
            SOURCE_CATALOGUE_SHA
        ),
        catalogue_record={
            "catalogue_entry_count":
                1,
            "entries_sha256":
                SOURCE_ENTRIES_SHA,
            "release_id":
                SOURCE_RELEASE,
        },
    )


def make_empty_cache_fixture(
    tmp_path,
    monkeypatch,
    *,
    assessments,
    chain=(),
    completion_source_override=None,
):
    production = (
        tmp_path
        / "production"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / COMMIT
    )

    metadata_stage = (
        stage1
        / module.METADATA_STAGE_NAME
    )

    cache_stage = (
        stage1
        / module.CACHE_STAGE_NAME
    )

    metadata_stage.mkdir(
        parents=True,
        mode=0o755,
    )

    cache_stage.mkdir(
        mode=0o755,
    )

    os.chmod(
        metadata_stage,
        0o755,
    )

    os.chmod(
        cache_stage,
        0o755,
    )

    assessments_bytes = (
        assessment_payload(
            assessments
        )
    )

    assessments_path = (
        metadata_stage
        / module.METADATA_ASSESSMENTS_NAME
    )

    assessments_path.write_bytes(
        assessments_bytes
    )

    os.chmod(
        assessments_path,
        0o644,
    )

    retained = {
        item.accession:
            item.biosample
        for item in assessments
        if item.decision
        == "RETAIN_METADATA"
    }

    cache_exec = (
        module.load_frozen_cache_execution(
            REPO
        )
    )

    context = cache_exec.CurrentMetadataContext(
        release_id=RELEASE,
        source_snapshot_id=SNAPSHOT,
        stage1_root=stage1.resolve(),
        source_snapshot_record_sha256=(
            SNAPSHOT_SHA
        ),
        metadata_record_sha256=(
            METADATA_RECORD_SHA
        ),
        metadata_completion_sha256=(
            METADATA_COMPLETION_SHA
        ),
        retained_metadata=(
            retained
        ),
    )

    results_payload = (
        cache_contract.serialize_cache_verification_results(
            ()
        )
    )

    verified_payload = (
        cache_contract.serialize_verified_cache_evidence(
            ()
        )
    )

    record = (
        cache_contract.build_cache_verification_record(
            source_snapshot_id=(
                SNAPSHOT
            ),
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
            retained_count=len(
                retained
            ),
            results_payload=(
                results_payload
            ),
            verified_cache_payload=(
                verified_payload
            ),
        )
    )

    record_payload = (
        cache_contract._canonical_json_bytes(
            record
        )
    )

    for name, payload in (
        (
            cache_exec.RESULTS_NAME,
            results_payload,
        ),
        (
            cache_exec.VERIFIED_CACHE_NAME,
            verified_payload,
        ),
        (
            cache_exec.RECORD_NAME,
            record_payload,
        ),
    ):
        path = (
            cache_stage
            / name
        )

        path.write_bytes(
            payload
        )

        os.chmod(
            path,
            0o644,
        )

    chain_values = tuple(
        chain
    )

    if chain_values:
        chain_sha = (
            CHAIN_SHA
        )

        source_item = chain_values[
            -1
        ]

        source_record = (
            source_item.catalogue_record
        )

        history_mode = (
            cache_exec.HISTORY_CHAINED
        )

        source_catalogue_release_id = (
            source_item.release_id
        )

        source_catalogue_sha256 = (
            source_item.catalogue_sha256
        )

        source_catalogue_entries_sha256 = (
            source_record[
                "entries_sha256"
            ]
        )

        source_catalogue_entry_count = (
            source_record[
                "catalogue_entry_count"
            ]
        )

    else:
        chain_sha = (
            cache_exec.catalogue_chain_sha256(
                ()
            )
        )

        history_mode = (
            cache_exec.HISTORY_NONE
        )

        source_catalogue_release_id = None
        source_catalogue_sha256 = None
        source_catalogue_entries_sha256 = None
        source_catalogue_entry_count = 0

    overrides = (
        {}
        if completion_source_override is None
        else dict(
            completion_source_override
        )
    )

    source_catalogue_release_id = overrides.get(
        "source_catalogue_release_id",
        source_catalogue_release_id,
    )

    source_catalogue_sha256 = overrides.get(
        "source_catalogue_sha256",
        source_catalogue_sha256,
    )

    source_catalogue_entries_sha256 = overrides.get(
        "source_catalogue_entries_sha256",
        source_catalogue_entries_sha256,
    )

    source_catalogue_entry_count = overrides.get(
        "source_catalogue_entry_count",
        source_catalogue_entry_count,
    )

    completion_payload = (
        cache_exec.build_completion_receipt(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            execution_commit=COMMIT,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
            retained_count=len(
                retained
            ),
            catalogue_history_mode=(
                history_mode
            ),
            catalogue_chain_count=len(
                chain_values
            ),
            catalogue_chain_sha256_value=(
                chain_sha
            ),
            source_catalogue_release_id=(
                source_catalogue_release_id
            ),
            source_catalogue_sha256=(
                source_catalogue_sha256
            ),
            source_catalogue_entries_sha256=(
                source_catalogue_entries_sha256
            ),
            source_catalogue_entry_count=(
                source_catalogue_entry_count
            ),
            candidate_input_count=0,
            verified_cache_count=0,
            fallback_to_fresh_count=0,
            results_sha256=(
                sha(
                    results_payload
                )
            ),
            verified_cache_evidence_sha256=(
                sha(
                    verified_payload
                )
            ),
            record_sha256=(
                sha(
                    record_payload
                )
            ),
        )
    )

    completion_path = (
        stage1
        / module.CACHE_COMPLETION_NAME
    )

    completion_path.write_bytes(
        completion_payload
    )

    os.chmod(
        completion_path,
        0o644,
    )

    proof_calls = []

    monkeypatch.setattr(
        cache_exec,
        "load_current_metadata_context",
        lambda **kwargs:
            context,
    )

    monkeypatch.setattr(
        cache_exec,
        "discover_prior_catalogue_chain",
        lambda **kwargs:
            chain_values,
    )

    if chain_values:
        monkeypatch.setattr(
            cache_exec,
            "catalogue_chain_sha256",
            lambda observed:
                CHAIN_SHA,
        )

    monkeypatch.setattr(
        cache_exec,
        "prove_no_prior_sequence_evidence",
        lambda *args, **kwargs:
            proof_calls.append(
                (
                    args,
                    kwargs,
                )
            ),
    )

    monkeypatch.setattr(
        module,
        "load_frozen_cache_execution",
        lambda repo:
            cache_exec,
    )

    return {
        "production":
            production.resolve(),
        "stage1":
            stage1.resolve(),
        "context":
            context,
        "cache_exec":
            cache_exec,
        "proof_calls":
            proof_calls,
        "results":
            results_payload,
        "verified":
            verified_payload,
        "record":
            record_payload,
        "completion":
            completion_payload,
    }


def test_repository_preflight_accepts_exact_dependencies():
    module.repository_preflight(
        REPO,
        expected_commit=COMMIT,
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
    def dirty_reader(
        repo,
        args,
    ):
        if tuple(
            args
        ) == (
            "rev-parse",
            "HEAD",
        ):
            return COMMIT

        if tuple(
            args
        ) == (
            "status",
            "--short",
        ):
            return "M changed"

        raise AssertionError(
            args
        )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="not clean",
    ):
        module.repository_preflight(
            REPO,
            expected_commit=COMMIT,
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
                dirty_reader
            ),
        )


def test_load_inputs_accepts_completed_empty_cache_and_proves_genesis(
    tmp_path,
    monkeypatch,
):
    fixture = make_empty_cache_fixture(
        tmp_path,
        monkeypatch,
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    observed = (
        module.load_sequence_plan_inputs(
            repo=REPO,
            production_root=(
                fixture[
                    "production"
                ]
            ),
            stage1_root=(
                fixture[
                    "stage1"
                ]
            ),
            execution_commit=COMMIT,
        )
    )

    assert observed.verified_cache == ()

    assert observed.cache_record[
        "verified_cache_count"
    ] == 0

    assert observed.catalogue_chain_count == 0

    assert len(
        fixture[
            "proof_calls"
        ]
    ) == 1


def test_load_inputs_accepts_independently_derived_chained_catalogue(
    tmp_path,
    monkeypatch,
):
    fixture = make_empty_cache_fixture(
        tmp_path,
        monkeypatch,
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
        chain=(
            source_chain_item(),
        ),
    )

    observed = (
        module.load_sequence_plan_inputs(
            repo=REPO,
            production_root=(
                fixture[
                    "production"
                ]
            ),
            stage1_root=(
                fixture[
                    "stage1"
                ]
            ),
            execution_commit=COMMIT,
        )
    )

    assert observed.catalogue_history_mode == (
        fixture[
            "cache_exec"
        ].HISTORY_CHAINED
    )

    assert observed.catalogue_chain_count == 1

    assert observed.catalogue_chain_sha256 == CHAIN_SHA

    assert fixture[
        "proof_calls"
    ] == []


def test_load_inputs_rejects_cache_receipt_source_catalogue_drift(
    tmp_path,
    monkeypatch,
):
    fixture = make_empty_cache_fixture(
        tmp_path,
        monkeypatch,
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
        chain=(
            source_chain_item(),
        ),
        completion_source_override={
            "source_catalogue_entries_sha256":
                "d" * 64,
        },
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="completion audit failed",
    ):
        module.load_sequence_plan_inputs(
            repo=REPO,
            production_root=(
                fixture[
                    "production"
                ]
            ),
            stage1_root=(
                fixture[
                    "stage1"
                ]
            ),
            execution_commit=COMMIT,
        )


def test_load_inputs_rejects_corrupt_verified_cache(
    tmp_path,
    monkeypatch,
):
    fixture = make_empty_cache_fixture(
        tmp_path,
        monkeypatch,
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    path = (
        fixture[
            "stage1"
        ]
        / module.CACHE_STAGE_NAME
        / fixture[
            "cache_exec"
        ].VERIFIED_CACHE_NAME
    )

    path.write_bytes(
        b"{not-json}\n"
    )

    os.chmod(
        path,
        0o644,
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="scientific evidence audit failed",
    ):
        module.load_sequence_plan_inputs(
            repo=REPO,
            production_root=(
                fixture[
                    "production"
                ]
            ),
            stage1_root=(
                fixture[
                    "stage1"
                ]
            ),
            execution_commit=COMMIT,
        )


def test_load_inputs_rejects_catalogue_history_drift(
    tmp_path,
    monkeypatch,
):
    fixture = make_empty_cache_fixture(
        tmp_path,
        monkeypatch,
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    monkeypatch.setattr(
        fixture[
            "cache_exec"
        ],
        "catalogue_chain_sha256",
        lambda chain:
            "f" * 64,
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="completion audit failed",
    ):
        module.load_sequence_plan_inputs(
            repo=REPO,
            production_root=(
                fixture[
                    "production"
                ]
            ),
            stage1_root=(
                fixture[
                    "stage1"
                ]
            ),
            execution_commit=COMMIT,
        )


def test_all_retained_without_verified_cache_are_fresh():
    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
            retained_assessment(
                ACCESSION_2,
                BIOSAMPLE_2,
            ),
        ),
    )

    observed = (
        module.build_sequence_plan_payloads(
            inputs
        )
    )

    assert observed.plan.retained_accessions == (
        ACCESSION_1,
        ACCESSION_2,
    )

    assert observed.plan.cache_reuse_accessions == ()

    assert observed.plan.fresh_acquisition_accessions == (
        ACCESSION_1,
        ACCESSION_2,
    )

    assert observed.plan_record[
        "fresh_acquisition_count"
    ] == 2


def test_verified_cache_is_reused_and_remaining_accession_is_fresh():
    evidence = verified_evidence(
        ACCESSION_1,
        BIOSAMPLE_1,
    )

    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
            retained_assessment(
                ACCESSION_2,
                BIOSAMPLE_2,
            ),
        ),
        verified=(
            evidence,
        ),
    )

    observed = (
        module.build_sequence_plan_payloads(
            inputs
        )
    )

    assert observed.plan.cache_reuse_accessions == (
        ACCESSION_1,
    )

    assert observed.plan.fresh_acquisition_accessions == (
        ACCESSION_2,
    )

    assert observed.plan_record[
        "cache_reuse_count"
    ] == 1

    assert observed.plan_record[
        "fresh_acquisition_count"
    ] == 1


def test_verified_cache_outside_retained_population_fails_closed():
    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
        verified=(
            verified_evidence(
                ACCESSION_2,
                BIOSAMPLE_2,
            ),
        ),
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="cache-reuse population differs",
    ):
        module.build_sequence_plan_payloads(
            inputs
        )


def test_zero_fresh_plan_is_valid():
    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
        verified=(
            verified_evidence(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    observed = (
        module.build_sequence_plan_payloads(
            inputs
        )
    )

    assert observed.plan_record[
        "fresh_acquisition_count"
    ] == 0

    assert observed.plan_record[
        "fresh_batch_count"
    ] == 0

    assert observed.fresh_target_manifest == (
        b"canonical_genbank_assembly_accession"
        b"\tsource_biosample"
        b"\tacquisition_reason\n"
    )


def test_completion_receipt_is_exactly_rebuildable():
    payload = (
        module.build_completion_receipt(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            execution_commit=COMMIT,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
            cache_verification_results_sha256=(
                "4" * 64
            ),
            verified_cache_evidence_sha256=(
                "5" * 64
            ),
            cache_verification_record_sha256=(
                "6" * 64
            ),
            cache_verification_completion_sha256=(
                "7" * 64
            ),
            retained_count=2,
            cache_reuse_count=1,
            fresh_acquisition_count=1,
            fresh_batch_count=1,
            fresh_target_manifest_sha256=(
                "8" * 64
            ),
            sequence_plan_record_sha256=(
                "9" * 64
            ),
        )
    )

    record = module.audit_completion_receipt(
        payload,
        release_id=RELEASE,
        source_snapshot_id=SNAPSHOT,
        source_snapshot_record_sha256=(
            SNAPSHOT_SHA
        ),
        execution_commit=COMMIT,
        metadata_record_sha256=(
            METADATA_RECORD_SHA
        ),
        metadata_completion_sha256=(
            METADATA_COMPLETION_SHA
        ),
        cache_verification_results_sha256=(
            "4" * 64
        ),
        verified_cache_evidence_sha256=(
            "5" * 64
        ),
        cache_verification_record_sha256=(
            "6" * 64
        ),
        cache_verification_completion_sha256=(
            "7" * 64
        ),
        retained_count=2,
        cache_reuse_count=1,
        fresh_acquisition_count=1,
        fresh_batch_count=1,
        fresh_target_manifest_sha256=(
            "8" * 64
        ),
        sequence_plan_record_sha256=(
            "9" * 64
        ),
    )

    assert record[
        "status"
    ] == module.COMPLETION_STATUS


def test_completion_receipt_rejects_partition_drift():
    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="partition accounting",
    ):
        module.build_completion_receipt(
            release_id=RELEASE,
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
            execution_commit=COMMIT,
            metadata_record_sha256=(
                METADATA_RECORD_SHA
            ),
            metadata_completion_sha256=(
                METADATA_COMPLETION_SHA
            ),
            cache_verification_results_sha256=(
                "4" * 64
            ),
            verified_cache_evidence_sha256=(
                "5" * 64
            ),
            cache_verification_record_sha256=(
                "6" * 64
            ),
            cache_verification_completion_sha256=(
                "7" * 64
            ),
            retained_count=3,
            cache_reuse_count=1,
            fresh_acquisition_count=1,
            fresh_batch_count=1,
            fresh_target_manifest_sha256=(
                "8" * 64
            ),
            sequence_plan_record_sha256=(
                "9" * 64
            ),
        )


def test_scientific_stage_publication_uses_hardlinks(
    tmp_path,
):
    partial = (
        tmp_path
        / module.SEQUENCE_PLAN_PARTIAL_STAGE_NAME
    )

    final = (
        tmp_path
        / module.SEQUENCE_PLAN_STAGE_NAME
    )

    partial.mkdir(
        mode=0o755
    )

    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    payloads = (
        module.build_sequence_plan_payloads(
            inputs
        )
    )

    module.write_fresh_file(
        partial
        / module.FRESH_TARGETS_NAME,
        payloads.fresh_target_manifest,
    )

    module.write_fresh_file(
        partial
        / module.PLAN_RECORD_NAME,
        payloads.plan_record_payload,
    )

    source_inodes = {
        name:
            (
                partial
                / name
            ).stat().st_ino
        for name in (
            module.FRESH_TARGETS_NAME,
            module.PLAN_RECORD_NAME,
        )
    }

    (
        fresh,
        record,
        _,
    ) = module.promote_scientific_stage_no_clobber(
        partial=partial,
        final=final,
        expected_payloads=(
            payloads.fresh_target_manifest,
            payloads.plan_record_payload,
        ),
        source_snapshot_id=SNAPSHOT,
        source_snapshot_record_sha256=(
            SNAPSHOT_SHA
        ),
    )

    assert fresh == (
        payloads.fresh_target_manifest
    )

    assert record == (
        payloads.plan_record_payload
    )

    assert not partial.exists()

    for name in (
        module.FRESH_TARGETS_NAME,
        module.PLAN_RECORD_NAME,
    ):
        assert (
            final
            / name
        ).stat().st_ino == source_inodes[
            name
        ]


def test_scientific_stage_publication_refuses_existing_final(
    tmp_path,
):
    partial = (
        tmp_path
        / module.SEQUENCE_PLAN_PARTIAL_STAGE_NAME
    )

    final = (
        tmp_path
        / module.SEQUENCE_PLAN_STAGE_NAME
    )

    partial.mkdir(
        mode=0o755
    )

    final.mkdir(
        mode=0o755
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="already exists",
    ):
        module.promote_scientific_stage_no_clobber(
            partial=partial,
            final=final,
            expected_payloads=(
                b"a",
                b"b",
            ),
            source_snapshot_id=SNAPSHOT,
            source_snapshot_record_sha256=(
                SNAPSHOT_SHA
            ),
        )


def test_execute_publishes_exact_stage_and_completion(
    tmp_path,
):
    production = (
        tmp_path
        / "production"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
            retained_assessment(
                ACCESSION_2,
                BIOSAMPLE_2,
            ),
        ),
        verified=(
            verified_evidence(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    calls = []

    def loader(
        **kwargs,
    ):
        calls.append(
            kwargs
        )

        return inputs

    result = (
        module.execute_monthly_sequence_plan(
            repo=REPO,
            production_root=(
                production
            ),
            stage1_root=(
                stage1
            ),
            execution_commit=COMMIT,
            input_loader=loader,
        )
    )

    assert len(
        calls
    ) == 2

    assert result.retained_count == 2

    assert result.cache_reuse_count == 1

    assert result.fresh_acquisition_count == 1

    assert result.fresh_batch_count == 1

    assert (
        result.stage_root
        / module.FRESH_TARGETS_NAME
    ).is_file()

    assert (
        result.stage_root
        / module.PLAN_RECORD_NAME
    ).is_file()

    assert (
        result.completion_path
    ).is_file()

    assert sorted(
        item.name
        for item in result.stage_root.iterdir()
    ) == sorted(
        (
            module.FRESH_TARGETS_NAME,
            module.PLAN_RECORD_NAME,
        )
    )


def test_execute_allows_zero_fresh_release(
    tmp_path,
):
    production = (
        tmp_path
        / "production"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    inputs = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
        verified=(
            verified_evidence(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    result = (
        module.execute_monthly_sequence_plan(
            repo=REPO,
            production_root=production,
            stage1_root=stage1,
            execution_commit=COMMIT,
            input_loader=(
                lambda **kwargs:
                    inputs
            ),
        )
    )

    assert result.fresh_acquisition_count == 0

    assert result.fresh_batch_count == 0


def test_execute_rejects_upstream_change_between_passes(
    tmp_path,
):
    production = (
        tmp_path
        / "production"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    first = direct_inputs(
        assessments=(
            retained_assessment(
                ACCESSION_1,
                BIOSAMPLE_1,
            ),
        ),
    )

    second = replace(
        first,
        cache_completion_payload=(
            b"changed\n"
        ),
    )

    values = iter(
        (
            first,
            second,
        )
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="upstream evidence changed",
    ):
        module.execute_monthly_sequence_plan(
            repo=REPO,
            production_root=production,
            stage1_root=stage1,
            execution_commit=COMMIT,
            input_loader=(
                lambda **kwargs:
                    next(
                        values
                    )
            ),
        )


def test_execute_refuses_existing_stage(
    tmp_path,
):
    production = (
        tmp_path
        / "production"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    (
        stage1
        / module.SEQUENCE_PLAN_STAGE_NAME
    ).mkdir()

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="stage already exists",
    ):
        module.execute_monthly_sequence_plan(
            repo=REPO,
            production_root=production,
            stage1_root=stage1,
            execution_commit=COMMIT,
            input_loader=(
                lambda **kwargs:
                    pytest.fail(
                        "loader must not run"
                    )
            ),
        )


def test_execute_refuses_existing_completion(
    tmp_path,
):
    production = (
        tmp_path
        / "production"
    )

    stage1 = (
        production
        / RELEASE
        / "production"
        / COMMIT
    )

    stage1.mkdir(
        parents=True
    )

    (
        stage1
        / module.COMPLETION_NAME
    ).write_bytes(
        b"existing\n"
    )

    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="completion already exists",
    ):
        module.execute_monthly_sequence_plan(
            repo=REPO,
            production_root=production,
            stage1_root=stage1,
            execution_commit=COMMIT,
            input_loader=(
                lambda **kwargs:
                    pytest.fail(
                        "loader must not run"
                    )
            ),
        )


def test_main_requires_explicit_authorization():
    with pytest.raises(
        module.MonthlySequencePlanExecutionError,
        match="explicit authorization",
    ):
        module.main(
            (
                "--expected-commit",
                COMMIT,
                "--expected-wrapper-sha256",
                "1" * 64,
                "--expected-wrapper-test-sha256",
                "2" * 64,
                "--production-root",
                "/tmp/production",
                "--stage1-root",
                "/tmp/stage1",
            )
        )


def test_stage_names_match_existing_stage3b_vocabulary():
    assert (
        module.SEQUENCE_PLAN_STAGE_NAME
        == "sequence-plan"
    )

    assert (
        module.FRESH_TARGETS_NAME
        == "fresh-targets.tsv"
    )

    assert (
        module.PLAN_RECORD_NAME
        == "monthly-sequence-plan-record.json"
    )

    assert (
        module.COMPLETION_NAME
        == "sequence-plan-completion.json"
    )


def test_executor_is_portable_and_offline():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/NGS/",
        "Rhys_wkdir",
        "SLURM_",
        "sbatch",
        "srun",
        "Project Finch",
        "finch-ncbi-datasets",
        "requests",
        "urllib",
        "boto3",
        "google.cloud",
        "azure.storage",
    )

    for token in forbidden:
        assert token not in text


def test_executor_does_not_use_overwrite_publication_primitives():
    text = WRAPPER_PATH.read_text(
        encoding="utf-8"
    )

    assert "os.rename(" not in text
    assert "os.replace(" not in text
