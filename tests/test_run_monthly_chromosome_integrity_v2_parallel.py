from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from bacselect import monthly_chromosome_integrity
from bacselect import source_chromosome_integrity
from bacselect import source_chromosome_integrity_execution


WRAPPER = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_chromosome_integrity_v2_parallel.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_test_stage6_v2_parallel",
        WRAPPER,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


module = load_module()


def test_batch_id_validation():
    assert (
        module._batch_id(
            "batch-00072"
        )
        == "batch-00072"
    )

    for value in (
        "72",
        "batch-72",
        "batch-000072",
        "../batch-00072",
    ):
        with pytest.raises(
            module.ParallelStage6Error
        ):
            module._batch_id(
                value
            )


def test_subset_population_preserves_frozen_identity():
    full = (
        monthly_chromosome_integrity
        .MonthlyChromosomePopulation(
            release_id="2026.09",
            source_snapshot_id="snapshot",
            origin_git_commit="a" * 40,
            biosample_decisions_sha256=(
                "b" * 64
            ),
            continue_accessions=(
                "GCA_000000001.1",
                "GCA_000000002.1",
            ),
            continue_accessions_sha256=(
                "c" * 64
            ),
            source_evidence_sha256_by_accession={
                "GCA_000000001.1":
                    "1" * 64,
                "GCA_000000002.1":
                    "2" * 64,
            },
        )
    )

    runtime = SimpleNamespace(
        population=full,
        stage6_v1=SimpleNamespace(
            monthly_chromosome_integrity=(
                monthly_chromosome_integrity
            )
        ),
    )

    selection = module.BatchSelection(
        batch_id="batch-00001",
        provenance_sha256="d" * 64,
        accessions=(
            "GCA_000000002.1",
        ),
    )

    observed = module.subset_population(
        runtime,
        selection,
    )

    assert observed.release_id == (
        full.release_id
    )
    assert observed.origin_git_commit == (
        full.origin_git_commit
    )
    assert observed.continue_accessions == (
        "GCA_000000002.1",
    )
    assert set(
        observed
        .source_evidence_sha256_by_accession
    ) == {
        "GCA_000000002.1"
    }


def test_shard_decisions_roundtrip_to_frozen_evaluation():
    accession = "GCA_000000001.1"
    source_sha = "1" * 64

    population = (
        monthly_chromosome_integrity
        .MonthlyChromosomePopulation(
            release_id="2026.09",
            source_snapshot_id="snapshot",
            origin_git_commit="a" * 40,
            biosample_decisions_sha256=(
                "b" * 64
            ),
            continue_accessions=(
                accession,
            ),
            continue_accessions_sha256=(
                monthly_chromosome_integrity
                .accession_membership_sha256(
                    (
                        accession,
                    )
                )
            ),
            source_evidence_sha256_by_accession={
                accession:
                    source_sha
            },
        )
    )

    components = (
        source_chromosome_integrity
        .PrimaryComponentEvidence(
            molecule_class="chromosome",
            topology="circular",
            definition="complete genome",
        ),
    )

    trigger = (
        source_chromosome_integrity
        .assess_trigger(
            components
        )
    )

    decision = (
        source_chromosome_integrity
        .evaluate(
            accession=accession,
            components=components,
            historical=None,
        )
    )

    evaluation = (
        source_chromosome_integrity_execution
        .Stage3CandidateEvaluation(
            accession=accession,
            source_evidence_sha256=(
                source_sha
            ),
            primary_component_count=1,
            trigger=trigger,
            decision=decision,
        )
    )

    build = (
        monthly_chromosome_integrity
        .build_monthly_chromosome_integrity(
            population,
            (
                evaluation,
            ),
        )
    )

    payload = (
        monthly_chromosome_integrity
        .serialize_monthly_chromosome_decisions(
            build
        )
    )

    rows = (
        monthly_chromosome_integrity
        .audit_monthly_chromosome_decisions(
            payload
        )
    )

    reconstructed = (
        monthly_chromosome_integrity
        ._evaluation_from_row(
            rows[0]
        )
    )

    assert reconstructed == (
        evaluation
    )


def test_shard_receipt_binds_all_upstream_identities():
    evaluation = module.BatchEvaluation(
        selection=module.BatchSelection(
            batch_id="batch-00072",
            provenance_sha256="1" * 64,
            accessions=(
                "GCA_030436345.2",
            ),
        ),
        decisions_payload=b"x\n",
        candidate_count=1,
        triggered_count=0,
        pass_count=1,
        excluded_count=0,
        unresolved_count=0,
        provider_class="fresh-recovery",
    )

    context = SimpleNamespace(
        release_id="2026.09",
        source_snapshot_id="snapshot",
        completion_sha256="2" * 64,
        stage4_context=SimpleNamespace(
            completion_v2_sha256="3" * 64,
            catalogue_sha256="4" * 64,
            source_truth_completion_sha256=(
                "5" * 64
            ),
        ),
    )

    runtime = SimpleNamespace(
        context=context,
        stage4_v1=SimpleNamespace(
            validate_sha256=(
                lambda value, *, label:
                    value
            ),
        ),
    )

    payload = module.build_shard_receipt(
        runtime=runtime,
        evaluation=evaluation,
        source_production_commit="a" * 40,
        completion_execution_commit="b" * 40,
        cache_execution_commit="c" * 40,
        source_truth_execution_commit="d" * 40,
        biosample_execution_commit="e" * 40,
        chromosome_execution_commit="f" * 40,
        work_manifest_sha256="9" * 64,
    )

    value = json.loads(
        payload
    )

    assert (
        value["schema_version"]
        == module.SHARD_SCHEMA
    )
    assert (
        value["status"]
        == module.SHARD_STATUS
    )
    assert (
        value["provider_class"]
        == "fresh-recovery"
    )
    assert (
        value["decisions_sha256"]
        == hashlib.sha256(
            b"x\n"
        ).hexdigest()
    )


def test_publish_shard_is_no_clobber(
    tmp_path,
):
    writes = []

    class Stage5:
        @staticmethod
        def write_no_clobber(
            path,
            payload,
        ):
            path = Path(
                path
            )
            assert not path.exists()
            path.write_bytes(
                payload
            )
            writes.append(
                path.name
            )

        @staticmethod
        def fsync_directory(
            path,
        ):
            return None

    evaluation = module.BatchEvaluation(
        selection=module.BatchSelection(
            batch_id="batch-00001",
            provenance_sha256="1" * 64,
            accessions=(
                "GCA_000000001.1",
            ),
        ),
        decisions_payload=b"d\n",
        candidate_count=1,
        triggered_count=0,
        pass_count=1,
        excluded_count=0,
        unresolved_count=0,
        provider_class="fresh",
    )

    final = module.publish_shard(
        shard_root=tmp_path,
        evaluation=evaluation,
        receipt_payload=b"{}\n",
        stage5_v1=Stage5,
    )

    assert final.is_dir()
    assert not (
        tmp_path
        / "batch-00001.partial"
    ).exists()

    assert sorted(
        writes
    ) == sorted(
        (
            module.SHARD_DECISIONS_NAME,
            module.SHARD_RECEIPT_NAME,
        )
    )

    with pytest.raises(
        module.ParallelStage6Error,
        match="already exists",
    ):
        module.publish_shard(
            shard_root=tmp_path,
            evaluation=evaluation,
            receipt_payload=b"{}\n",
            stage5_v1=Stage5,
        )


def test_parallel_wrapper_does_not_call_full_package_observer():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    assert (
        "observe_current_package"
        not in text
    )


def test_work_manifest_is_deterministic_and_exact():
    accession = "GCA_000000001.1"
    provenance_sha = "7" * 64

    runtime = SimpleNamespace(
        context=SimpleNamespace(
            release_id="test",
            stage4_context=SimpleNamespace(
                entries_by_accession={
                    accession: {
                        "origin_batch_provenance_sha256":
                            provenance_sha,
                    }
                },
                provenance_by_sha={
                    provenance_sha: {
                        "cache_origin_release_id":
                            "test",
                        "batch_id":
                            "batch-00001",
                    }
                },
            ),
        ),
        population=SimpleNamespace(
            continue_accessions=(
                accession,
            ),
        ),
        stage4_v1=SimpleNamespace(
            validate_sha256=(
                lambda value, *, label:
                    value
            ),
        ),
    )

    first = module.build_work_manifest(
        runtime
    )

    second = module.build_work_manifest(
        runtime
    )

    assert first == second

    assert module.audit_work_manifest(
        runtime,
        first,
    )[0].accessions == (
        accession,
    )

    assert first.startswith(
        b"task_id\tbatch_id\t"
    )


def test_work_manifest_rejects_changed_bytes():
    accession = "GCA_000000001.1"
    provenance_sha = "7" * 64

    runtime = SimpleNamespace(
        context=SimpleNamespace(
            release_id="test",
            stage4_context=SimpleNamespace(
                entries_by_accession={
                    accession: {
                        "origin_batch_provenance_sha256":
                            provenance_sha,
                    }
                },
                provenance_by_sha={
                    provenance_sha: {
                        "cache_origin_release_id":
                            "test",
                        "batch_id":
                            "batch-00001",
                    }
                },
            ),
        ),
        population=SimpleNamespace(
            continue_accessions=(
                accession,
            ),
        ),
        stage4_v1=SimpleNamespace(
            validate_sha256=(
                lambda value, *, label:
                    value
            ),
        ),
    )

    payload = module.build_work_manifest(
        runtime
    )

    with pytest.raises(
        module.ParallelStage6Error,
        match="differs",
    ):
        module.audit_work_manifest(
            runtime,
            payload + b"x",
        )


def test_slurm_parallel_contract():
    repo = WRAPPER.parents[2]

    worker = (
        repo
        / "validation/selector-v1/"
        "run_monthly_chromosome_integrity_v2.slurm"
    ).read_text(
        encoding="utf-8"
    )

    aggregate = (
        repo
        / "validation/selector-v1/"
        "aggregate_monthly_chromosome_integrity_v2.slurm"
    ).read_text(
        encoding="utf-8"
    )

    submit = (
        repo
        / "validation/selector-v1/"
        "submit_monthly_chromosome_integrity_v2.sh"
    ).read_text(
        encoding="utf-8"
    )

    assert "#SBATCH --partition=prod" in worker
    assert "#SBATCH --cpus-per-task=1" in worker
    assert "#SBATCH --mem=4G" in worker
    assert "#SBATCH --array=1-142%24" in worker

    assert "SLURM_ARRAY_TASK_ID" in worker
    assert " worker " in worker

    assert "#SBATCH --partition=prod" in aggregate
    assert " aggregate " in aggregate

    assert 'afterok:${array_job}' in submit

    assert (
        "printf 'field\\tvalue\\n'"
        in submit
    )

    assert (
        "printf 'candidate_count\\t%s\\n' '68595'"
        in submit
    )

    assert (
        "printf 'array_spec\\t%s\\n' '1-142%24'"
        in submit
    )

    assert (
        "printf 'dependency\\t%s\\n' \"afterok:$array_job\""
        in submit
    )
