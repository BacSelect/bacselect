from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


WRAPPER = (
    Path(__file__).resolve().parents[
        1
    ]
    / "validation"
    / "selector-v1"
    / "run_monthly_biosample_reconciliation.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_test_monthly_biosample_executor",
        WRAPPER,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    sys.modules[
        spec.name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


module = load_module()


SHA = "a" * 64


def completion_kwargs():
    return {
        "release_id":
            "2034.05",
        "source_snapshot_id":
            "bacselect-source-2034.05-20340501T001700Z",
        "source_snapshot_record_sha256":
            "1" * 64,
        "execution_commit":
            "a" * 40,
        "metadata_record_sha256":
            "2" * 64,
        "metadata_completion_sha256":
            "3" * 64,
        "catalogue_chain_count":
            2,
        "catalogue_chain_sha256_value":
            "4" * 64,
        "sequence_cache_catalogue_sha256":
            "5" * 64,
        "sequence_cache_entries_sha256":
            "6" * 64,
        "source_truth_completion_sha256":
            "7" * 64,
        "source_truth_decisions_sha256":
            "8" * 64,
        "source_truth_record_sha256":
            "9" * 64,
        "suitable_count":
            4,
        "suitable_accessions_sha256":
            "a" * 64,
        "decision_count":
            4,
        "continue_count":
            2,
        "nonrepresentative_count":
            1,
        "unresolved_count":
            1,
        "group_count":
            3,
        "singleton_group_count":
            2,
        "repeated_group_count":
            1,
        "identical_repeated_group_count":
            1,
        "differing_repeated_group_count":
            0,
        "decisions_sha256":
            "b" * 64,
        "record_sha256":
            "c" * 64,
    }


def test_completion_roundtrip():
    kwargs = completion_kwargs()

    payload = module.build_completion_receipt(
        **kwargs
    )

    observed = module.audit_completion_receipt(
        payload,
        **kwargs
    )

    assert observed[
        "schema_version"
    ] == module.COMPLETION_SCHEMA

    assert observed[
        "status"
    ] == module.COMPLETION_STATUS


def test_completion_is_canonical_json():
    payload = module.build_completion_receipt(
        **completion_kwargs()
    )

    value = json.loads(
        payload
    )

    assert payload == (
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


def test_completion_rejects_decision_accounting():
    kwargs = completion_kwargs()

    kwargs[
        "continue_count"
    ] = 3

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="decision accounting",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_completion_rejects_group_accounting():
    kwargs = completion_kwargs()

    kwargs[
        "singleton_group_count"
    ] = 1

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="group accounting",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_completion_rejects_repeated_group_accounting():
    kwargs = completion_kwargs()

    kwargs[
        "differing_repeated_group_count"
    ] = 1

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="repeated-group accounting",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_completion_rejects_zero_catalogue_chain():
    kwargs = completion_kwargs()

    kwargs[
        "catalogue_chain_count"
    ] = 0

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="must be positive",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_completion_rejects_suitable_decision_mismatch():
    kwargs = completion_kwargs()

    kwargs[
        "decision_count"
    ] = 3

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="differs from suitable",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_completion_rejects_malformed_hash():
    kwargs = completion_kwargs()

    kwargs[
        "record_sha256"
    ] = "not-a-sha"

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="SHA256",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_completion_audit_rejects_changed_payload():
    kwargs = completion_kwargs()

    payload = module.build_completion_receipt(
        **kwargs
    )

    broken = payload.replace(
        b'"continue_count":2',
        b'"continue_count":3',
        1,
    )

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="changed",
    ):
        module.audit_completion_receipt(
            broken,
            **kwargs
        )


def test_origin_current():
    assert module.classify_origin_release(
        "2034.05",
        current_release_id="2034.05",
    ) == "CURRENT"


def test_origin_prior():
    assert module.classify_origin_release(
        "2034.04",
        current_release_id="2034.05",
    ) == "PRIOR"


def test_origin_prior_across_year_boundary():
    assert module.classify_origin_release(
        "2033.12",
        current_release_id="2034.01",
    ) == "PRIOR"


def test_origin_future_fails_closed():
    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="future release",
    ):
        module.classify_origin_release(
            "2034.06",
            current_release_id="2034.05",
        )


def test_origin_invalid_month_fails_closed():
    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="month",
    ):
        module.classify_origin_release(
            "2034.13",
            current_release_id="2034.05",
        )


def test_write_no_clobber_roundtrip(
    tmp_path,
):
    path = (
        tmp_path
        / "artifact.txt"
    )

    module.write_no_clobber(
        path,
        b"abc\n",
    )

    assert path.read_bytes() == b"abc\n"
    assert (
        path.stat().st_mode
        & 0o777
    ) == 0o644


def test_write_no_clobber_refuses_existing(
    tmp_path,
):
    path = (
        tmp_path
        / "artifact.txt"
    )

    path.write_bytes(
        b"existing"
    )

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="already exists",
    ):
        module.write_no_clobber(
            path,
            b"new",
        )


def test_exact_stage_inventory(
    tmp_path,
):
    stage = (
        tmp_path
        / "stage"
    )

    stage.mkdir()

    (
        stage
        / module.DECISIONS_NAME
    ).write_bytes(
        b"d"
    )

    (
        stage
        / module.RECORD_NAME
    ).write_bytes(
        b"r"
    )

    decisions, record = (
        module.read_exact_scientific_stage(
            stage
        )
    )

    assert decisions == b"d"
    assert record == b"r"


def test_exact_stage_inventory_rejects_extra(
    tmp_path,
):
    stage = (
        tmp_path
        / "stage"
    )

    stage.mkdir()

    (
        stage
        / module.DECISIONS_NAME
    ).write_bytes(
        b"d"
    )

    (
        stage
        / module.RECORD_NAME
    ).write_bytes(
        b"r"
    )

    (
        stage
        / "extra.txt"
    ).write_bytes(
        b"x"
    )

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="inventory",
    ):
        module.read_exact_scientific_stage(
            stage
        )


def test_exact_stage_inventory_rejects_symlink(
    tmp_path,
):
    stage = (
        tmp_path
        / "stage"
    )

    stage.mkdir()

    target = (
        tmp_path
        / "target"
    )

    target.write_bytes(
        b"d"
    )

    os.symlink(
        target,
        stage
        / module.DECISIONS_NAME,
    )

    (
        stage
        / module.RECORD_NAME
    ).write_bytes(
        b"r"
    )

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="regular file",
    ):
        module.read_exact_scientific_stage(
            stage
        )


def test_publish_stage_no_clobber(
    tmp_path,
):
    partial = (
        tmp_path
        / module.PARTIAL_NAME
    )

    final = (
        tmp_path
        / module.STAGE_NAME
    )

    partial.mkdir()

    decisions = b"decisions\n"
    record = b"record\n"

    module.write_no_clobber(
        partial
        / module.DECISIONS_NAME,
        decisions,
    )

    module.write_no_clobber(
        partial
        / module.RECORD_NAME,
        record,
    )

    audited = []
    stability = []

    module.publish_stage(
        stage1_root=tmp_path,
        partial=partial,
        final=final,
        expected_decisions=decisions,
        expected_record=record,
        auditor=lambda d, r:
            audited.append(
                (
                    d,
                    r,
                )
            ),
        stability_check=lambda:
            stability.append(
                True
            ),
    )

    assert not partial.exists()

    assert (
        final
        / module.DECISIONS_NAME
    ).read_bytes() == decisions

    assert (
        final
        / module.RECORD_NAME
    ).read_bytes() == record

    assert len(
        audited
    ) == 2

    assert len(
        stability
    ) == 2


def test_publish_stage_refuses_existing_final(
    tmp_path,
):
    partial = (
        tmp_path
        / module.PARTIAL_NAME
    )

    final = (
        tmp_path
        / module.STAGE_NAME
    )

    partial.mkdir()
    final.mkdir()

    (
        partial
        / module.DECISIONS_NAME
    ).write_bytes(
        b"d"
    )

    (
        partial
        / module.RECORD_NAME
    ).write_bytes(
        b"r"
    )

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="already exists",
    ):
        module.publish_stage(
            stage1_root=tmp_path,
            partial=partial,
            final=final,
            expected_decisions=b"d",
            expected_record=b"r",
            auditor=lambda d, r:
                None,
            stability_check=lambda:
                None,
        )


def test_publish_completion_no_clobber(
    tmp_path,
):
    kwargs = completion_kwargs()

    payload = module.build_completion_receipt(
        **kwargs
    )

    stability = []

    path = module.publish_completion(
        stage1_root=tmp_path,
        payload=payload,
        auditor=lambda value:
            module.audit_completion_receipt(
                value,
                **kwargs
            ),
        stability_check=lambda:
            stability.append(
                True
            ),
    )

    assert path == (
        tmp_path
        / module.COMPLETION_NAME
    )

    assert path.read_bytes() == payload

    assert not (
        tmp_path
        / module.COMPLETION_TEMP_NAME
    ).exists()

    assert len(
        stability
    ) == 2


def test_publish_completion_refuses_existing(
    tmp_path,
):
    path = (
        tmp_path
        / module.COMPLETION_NAME
    )

    path.write_bytes(
        b"existing"
    )

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="already exists",
    ):
        module.publish_completion(
            stage1_root=tmp_path,
            payload=b"x",
            auditor=lambda value:
                None,
            stability_check=lambda:
                None,
        )


def test_executor_uses_frozen_fingerprint_primitive():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    assert (
        "fingerprint_stage2_candidate("
        in text
    )

    assert (
        ".validate_candidate_bridge("
        in text
    )

    assert (
        ".load_batch_evidence("
        in text
    )

    assert (
        "._current_batch_evidence("
        in text
    )


def test_executor_has_no_network_or_slurm():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "requests.",
        "urllib.",
        "boto3",
        "google.cloud",
        "azure.storage",
        "SLURM_",
        "sbatch",
        "srun",
        "/NGS/",
        "Rhys_wkdir",
    )

    for token in forbidden:
        assert token not in text

def test_fingerprint_population_current_origin(
    monkeypatch,
    tmp_path,
):
    accession = "GCA_000000001.1"
    biosample = "SAMN00000001"
    source_sha = "2" * 64
    provenance_sha = "1" * 64
    batch_id = "batch-00001"

    stage1 = (
        tmp_path
        / "stage1"
    )

    batch_dir = (
        stage1
        / "sequence-acquisition"
        / batch_id
    )

    fasta_relative = (
        "ncbi_dataset/data/"
        f"{accession}/genomic.fna"
    )

    fasta = (
        batch_dir
        / "package"
        / "ncbi_dataset"
        / "data"
        / accession
        / "genomic.fna"
    )

    fasta.parent.mkdir(
        parents=True
    )

    fasta_payload = (
        b">component\nACGT\n"
    )

    fasta.write_bytes(
        fasta_payload
    )

    fasta_sha = hashlib.sha256(
        fasta_payload
    ).hexdigest()

    materialization = (
        tmp_path
        / "materialization"
    )

    materialization.mkdir()

    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    provenance = {
        "cache_origin_release_id":
            "2034.05",
        "batch_id":
            batch_id,
    }

    entry = {
        "origin_batch_provenance_sha256":
            provenance_sha,
    }

    bridge = SimpleNamespace(
        accession=accession,
        biosample=biosample,
        candidate_row={},
        component_rows=(),
        package_rows=(),
        fasta_package_path=(
            fasta_relative
        ),
        fasta_sha256=fasta_sha,
        fasta_size_bytes=len(
            fasta_payload
        ),
        primary_assembly_records=1,
    )

    batch = SimpleNamespace(
        provenance=provenance,
        candidate_rows=(
            {
                "candidate":
                    "row",
            },
        ),
        component_rows=(
            {
                "component":
                    "row",
            },
        ),
        package_rows=(
            {
                "package":
                    "row",
            },
        ),
    )

    context = SimpleNamespace(
        entries_by_accession={
            accession:
                entry,
        },
        provenance_by_sha={
            provenance_sha:
                provenance,
        },
        release_id="2034.05",
        completion_context=object(),
        execution_commit="a" * 40,
        decision_by_accession={
            accession: {
                "source_truth_status":
                    module.source_truth.SUITABLE,
                "source_evidence_sha256":
                    source_sha,
            }
        },
    )

    population = SimpleNamespace(
        suitable_accessions=(
            accession,
        ),
        biosample_by_accession={
            accession:
                biosample,
        },
    )

    calls = {
        "current":
            0,
        "prior":
            0,
        "bridge":
            0,
        "fingerprint":
            0,
    }

    class FakeStage4:
        @staticmethod
        def _current_batch_evidence(
            **kwargs,
        ):
            calls[
                "current"
            ] += 1

            return batch

        @staticmethod
        def validate_candidate_bridge(
            cache_execution,
            *,
            entry,
            batch,
        ):
            calls[
                "bridge"
            ] += 1

            return bridge

        @staticmethod
        def _source_truth_objects(
            bridge,
            *,
            audit_path,
        ):
            assert (
                Path(
                    audit_path
                ).resolve()
                == batch_dir.resolve()
            )

            return (
                object(),
                (),
                {},
            )

    class FakeCache:
        @staticmethod
        def load_batch_evidence(
            *args,
            **kwargs,
        ):
            calls[
                "prior"
            ] += 1

            raise AssertionError(
                "prior loader called for current origin"
            )

    def fake_fingerprint(
        **kwargs,
    ):
        calls[
            "fingerprint"
        ] += 1

        assert (
            kwargs[
                "expected_source_evidence_sha256"
            ]
            == source_sha
        )

        assert (
            kwargs[
                "biosample"
            ]
            == biosample
        )

        return (
            module.VerifiedBioSampleFingerprint(
                accession=accession,
                biosample=biosample,
                source_evidence_sha256=(
                    source_sha
                ),
                assembly_fingerprint=(
                    "f" * 64
                ),
            )
        )

    monkeypatch.setattr(
        module,
        "fingerprint_stage2_candidate",
        fake_fingerprint,
    )

    (
        fingerprints,
        local_observations,
        authoritative_observations,
        current_batch_observations,
        prior_batch_observations,
    ) = module.fingerprint_population(
        context=context,
        stage1_root=stage1,
        authoritative_root=(
            authoritative
        ),
        materialization_root=(
            materialization
        ),
        population=population,
        stage4_execution=FakeStage4,
        cache_execution=FakeCache,
        catalogue_execution=(
            SimpleNamespace(
                SEQUENCE_ROOT_NAME=(
                    "sequence-acquisition"
                )
            )
        ),
    )

    assert tuple(
        value.accession
        for value in fingerprints
    ) == (
        accession,
    )

    assert len(
        local_observations
    ) == 1

    assert (
        local_observations[
            0
        ].sha256
        == fasta_sha
    )

    assert (
        authoritative_observations
        == ()
    )

    assert len(
        current_batch_observations
    ) == 1

    assert (
        prior_batch_observations
        == ()
    )

    module.verify_observations(
        stage4_execution=FakeStage4,
        cache_execution=FakeCache,
        current_completion_context=(
            object()
        ),
        execution_commit="a" * 40,
        authoritative_root=(
            authoritative
        ),
        local_observations=(
            local_observations
        ),
        authoritative_observations=(),
        current_batch_observations=(
            current_batch_observations
        ),
        prior_batch_observations=(),
    )

    assert calls == {
        "current":
            2,
        "prior":
            0,
        "bridge":
            1,
        "fingerprint":
            1,
    }


def test_fingerprint_population_prior_origin_and_reauthentication(
    monkeypatch,
    tmp_path,
):
    accession = "GCA_000000001.1"
    biosample = "SAMN00000001"
    source_sha = "2" * 64
    provenance_sha = "1" * 64

    fasta_relative = (
        "ncbi_dataset/data/"
        f"{accession}/genomic.fna"
    )

    fasta_payload = (
        b">component\nACGT\n"
    )

    fasta_sha = hashlib.sha256(
        fasta_payload
    ).hexdigest()

    stage1 = (
        tmp_path
        / "stage1"
    )

    stage1.mkdir()

    materialization = (
        tmp_path
        / "materialization"
    )

    materialization.mkdir()

    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    provenance = {
        "cache_origin_release_id":
            "2034.04",
        "batch_id":
            "batch-00001",
    }

    batch = SimpleNamespace(
        provenance=provenance,
        candidate_rows=(
            {
                "candidate":
                    "row",
            },
        ),
        component_rows=(
            {
                "component":
                    "row",
            },
        ),
        package_rows=(
            {
                "package":
                    "row",
            },
        ),
    )

    bridge = SimpleNamespace(
        accession=accession,
        biosample=biosample,
        candidate_row={},
        component_rows=(),
        package_rows=(),
        fasta_package_path=(
            fasta_relative
        ),
        fasta_sha256=fasta_sha,
        fasta_size_bytes=len(
            fasta_payload
        ),
        primary_assembly_records=1,
    )

    context = SimpleNamespace(
        entries_by_accession={
            accession: {
                "origin_batch_provenance_sha256":
                    provenance_sha,
            }
        },
        provenance_by_sha={
            provenance_sha:
                provenance,
        },
        release_id="2034.05",
        completion_context=object(),
        execution_commit="a" * 40,
        decision_by_accession={
            accession: {
                "source_truth_status":
                    module.source_truth.SUITABLE,
                "source_evidence_sha256":
                    source_sha,
            }
        },
    )

    population = SimpleNamespace(
        suitable_accessions=(
            accession,
        ),
        biosample_by_accession={
            accession:
                biosample,
        },
    )

    calls = {
        "load_batch":
            0,
        "required_object":
            0,
        "fingerprint":
            0,
    }

    class FakeCache:
        @staticmethod
        def load_batch_evidence(
            authoritative_root,
            *,
            provenance,
        ):
            calls[
                "load_batch"
            ] += 1

            return batch

        @staticmethod
        def read_required_object(
            authoritative_root,
            *,
            sha256,
            expected_size_bytes=None,
            label,
        ):
            calls[
                "required_object"
            ] += 1

            assert sha256 == fasta_sha

            assert (
                expected_size_bytes
                == len(
                    fasta_payload
                )
            )

            return SimpleNamespace(
                payload=fasta_payload,
                sha256=fasta_sha,
                size_bytes=len(
                    fasta_payload
                ),
            )

    class FakeStage4:
        @staticmethod
        def _current_batch_evidence(
            **kwargs,
        ):
            raise AssertionError(
                "current loader called for prior origin"
            )

        @staticmethod
        def validate_candidate_bridge(
            cache_execution,
            *,
            entry,
            batch,
        ):
            return bridge

        @staticmethod
        def _source_truth_objects(
            bridge,
            *,
            audit_path,
        ):
            expected = (
                Path(
                    audit_path
                )
                / "package"
                / "ncbi_dataset"
                / "data"
                / accession
                / "genomic.fna"
            )

            assert expected.is_file()

            assert (
                expected.read_bytes()
                == fasta_payload
            )

            return (
                object(),
                (),
                {},
            )

    def fake_fingerprint(
        **kwargs,
    ):
        calls[
            "fingerprint"
        ] += 1

        return (
            module.VerifiedBioSampleFingerprint(
                accession=accession,
                biosample=biosample,
                source_evidence_sha256=(
                    source_sha
                ),
                assembly_fingerprint=(
                    "f" * 64
                ),
            )
        )

    monkeypatch.setattr(
        module,
        "fingerprint_stage2_candidate",
        fake_fingerprint,
    )

    (
        fingerprints,
        local_observations,
        authoritative_observations,
        current_batch_observations,
        prior_batch_observations,
    ) = module.fingerprint_population(
        context=context,
        stage1_root=stage1,
        authoritative_root=(
            authoritative
        ),
        materialization_root=(
            materialization
        ),
        population=population,
        stage4_execution=FakeStage4,
        cache_execution=FakeCache,
        catalogue_execution=(
            SimpleNamespace(
                SEQUENCE_ROOT_NAME=(
                    "sequence-acquisition"
                )
            )
        ),
    )

    assert tuple(
        value.accession
        for value in fingerprints
    ) == (
        accession,
    )

    assert (
        local_observations
        == ()
    )

    assert len(
        authoritative_observations
    ) == 1

    assert (
        current_batch_observations
        == ()
    )

    assert len(
        prior_batch_observations
    ) == 1

    assert not any(
        materialization.iterdir()
    )

    module.verify_observations(
        stage4_execution=FakeStage4,
        cache_execution=FakeCache,
        current_completion_context=(
            object()
        ),
        execution_commit="a" * 40,
        authoritative_root=(
            authoritative
        ),
        local_observations=(),
        authoritative_observations=(
            authoritative_observations
        ),
        current_batch_observations=(),
        prior_batch_observations=(
            prior_batch_observations
        ),
    )

    assert calls[
        "load_batch"
    ] == 2

    assert calls[
        "required_object"
    ] == 2

    assert calls[
        "fingerprint"
    ] == 1


def test_historical_batch_stability_rejects_changed_evidence(
    tmp_path,
):
    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    provenance = {
        "cache_origin_release_id":
            "2034.04",
    }

    original = SimpleNamespace(
        provenance=provenance,
        candidate_rows=(
            {
                "value":
                    "original",
            },
        ),
        component_rows=(),
        package_rows=(),
    )

    changed = SimpleNamespace(
        provenance=provenance,
        candidate_rows=(
            {
                "value":
                    "changed",
            },
        ),
        component_rows=(),
        package_rows=(),
    )

    class FakeCache:
        @staticmethod
        def load_batch_evidence(
            authoritative_root,
            *,
            provenance,
        ):
            return changed

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="historical batch evidence changed",
    ):
        module.verify_observations(
            stage4_execution=(
                SimpleNamespace()
            ),
            cache_execution=FakeCache,
            current_completion_context=(
                object()
            ),
            execution_commit="a" * 40,
            authoritative_root=(
                authoritative
            ),
            local_observations=(),
            authoritative_observations=(),
            current_batch_observations=(),
            prior_batch_observations=(
                module.PriorBatchObservation(
                    provenance=provenance,
                    batch=original,
                ),
            ),
        )


def test_current_batch_stability_rejects_changed_evidence(
    tmp_path,
):
    authoritative = (
        tmp_path
        / "authoritative"
    )

    authoritative.mkdir()

    provenance = {
        "cache_origin_release_id":
            "2034.05",
    }

    original = SimpleNamespace(
        provenance=provenance,
        candidate_rows=(
            {
                "value":
                    "original",
            },
        ),
        component_rows=(),
        package_rows=(),
    )

    changed = SimpleNamespace(
        provenance=provenance,
        candidate_rows=(
            {
                "value":
                    "changed",
            },
        ),
        component_rows=(),
        package_rows=(),
    )

    class FakeStage4:
        @staticmethod
        def _current_batch_evidence(
            **kwargs,
        ):
            return changed

    with pytest.raises(
        module.MonthlyBioSampleExecutionError,
        match="current batch evidence changed",
    ):
        module.verify_observations(
            stage4_execution=FakeStage4,
            cache_execution=(
                SimpleNamespace()
            ),
            current_completion_context=(
                object()
            ),
            execution_commit="a" * 40,
            authoritative_root=(
                authoritative
            ),
            local_observations=(),
            authoritative_observations=(),
            current_batch_observations=(
                module.CurrentBatchObservation(
                    provenance=provenance,
                    batch=original,
                ),
            ),
            prior_batch_observations=(),
        )
