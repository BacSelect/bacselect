from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


WRAPPER = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_monthly_chromosome_integrity_v2.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_test_monthly_chromosome_v2_executor",
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


class FakeStage6V1:
    COMPLETION_SCHEMA = (
        "bacselect-monthly-chromosome-integrity-completion-v1"
    )

    @staticmethod
    def _canonical_json(value):
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            )
            + "\n"
        ).encode("ascii")

    @staticmethod
    def build_completion_receipt(
        *,
        execution_commit,
        **kwargs,
    ):
        record = {
            key: value
            for key, value in kwargs.items()
            if key != "stage5_execution"
        }

        record.update(
            {
                "execution_commit":
                    execution_commit,
                "schema_version":
                    FakeStage6V1.COMPLETION_SCHEMA,
                "status":
                    "CHROMOSOME_INTEGRITY_EXECUTION_COMPLETE",
            }
        )

        return FakeStage6V1._canonical_json(
            record
        )


def completion_kwargs():
    return {
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "bacselect-source-2026.09-20260901T021652Z",
        "biosample_decisions_sha256":
            "1" * 64,
        "biosample_record_sha256":
            "2" * 64,
        "biosample_completion_sha256":
            "3" * 64,
        "continue_count":
            4,
        "continue_accessions_sha256":
            "4" * 64,
        "decision_count":
            4,
        "triggered_candidate_count":
            1,
        "nontriggered_candidate_count":
            3,
        "historical_adjudication_reuse_count":
            0,
        "pass_count":
            3,
        "excluded_count":
            0,
        "unresolved_count":
            1,
        "decisions_sha256":
            "5" * 64,
        "record_sha256":
            "6" * 64,
        "stage5_execution":
            object(),
    }


def identity_kwargs():
    return {
        "source_production_commit":
            "1" * 40,
        "completion_execution_commit":
            "2" * 40,
        "cache_execution_commit":
            "3" * 40,
        "source_truth_execution_commit":
            "4" * 40,
        "biosample_execution_commit":
            "5" * 40,
        "chromosome_execution_commit":
            "6" * 40,
        "sequence_acquisition_completion_sha256":
            "7" * 64,
        "source_truth_completion_sha256":
            "8" * 64,
    }


def test_completion_v2_keeps_execution_identities_separate():
    payload = module.build_completion_receipt_v2(
        FakeStage6V1,
        **identity_kwargs(),
        **completion_kwargs(),
    )

    value = json.loads(payload)

    assert (
        value["schema_version"]
        == module.COMPLETION_SCHEMA
    )
    assert (
        value["status"]
        == module.COMPLETION_STATUS
    )
    assert "execution_commit" not in value

    for key, expected in identity_kwargs().items():
        assert value[key] == expected

    observed = module.audit_completion_receipt_v2(
        FakeStage6V1,
        payload,
        **identity_kwargs(),
        **completion_kwargs(),
    )

    assert observed == value


def test_completion_v2_rejects_changed_payload():
    payload = module.build_completion_receipt_v2(
        FakeStage6V1,
        **identity_kwargs(),
        **completion_kwargs(),
    )

    value = json.loads(payload)
    value["pass_count"] = 99

    broken = FakeStage6V1._canonical_json(
        value
    )

    with pytest.raises(
        module.MonthlyChromosomeV2ExecutionError,
        match="changed",
    ):
        module.audit_completion_receipt_v2(
            FakeStage6V1,
            broken,
            **identity_kwargs(),
            **completion_kwargs(),
        )


def test_wrapper_has_no_network_or_slurm():
    payload = WRAPPER.read_text(
        encoding="utf-8"
    )

    for token in (
        "requests.",
        "urllib.request",
        "sbatch",
        "srun ",
    ):
        assert token not in payload


def test_recovery_provider_root_drives_package_evaluation(
    tmp_path,
):
    accession = "GCA_030436345.2"
    source_sha = "a" * 64

    provider_root = (
        tmp_path
        / "sequence-acquisition-recovery"
        / "recovery"
        / "source"
        / "batch-00072"
    )
    provider_root.mkdir(
        parents=True
    )

    candidate_audit = (
        provider_root
        / "candidate-sequence-audit.tsv"
    )
    candidate_audit.write_text(
        "candidate\n",
        encoding="ascii",
    )

    provenance_sha = "b" * 64
    provenance = {
        "cache_origin_release_id":
            "2026.09",
        "batch_id":
            "batch-00072",
    }

    bridge = SimpleNamespace(
        accession=accession,
        package_rows=(),
    )

    provider = SimpleNamespace(
        provider_root=provider_root,
        candidate_audit_path=candidate_audit,
        batch=object(),
        observations=(),
    )

    stage4 = SimpleNamespace(
        cache_execution=object(),
        completion_v2_sha256="c" * 64,
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
        completion_by_batch={
            "batch-00072": {
                "batch_id":
                    "batch-00072",
            }
        },
        decision_by_accession={
            accession: {
                "source_truth_status":
                    "SUITABLE",
                "source_evidence_sha256":
                    source_sha,
            }
        },
    )

    context = SimpleNamespace(
        release_id="2026.09",
        source_snapshot_id=(
            "bacselect-source-2026.09-20260901T021652Z"
        ),
        stage4_context=stage4,
    )

    population = SimpleNamespace(
        continue_accessions=(
            accession,
        ),
        source_evidence_sha256_by_accession={
            accession:
                source_sha,
        },
    )

    calls = {
        "provider":
            0,
        "package_root":
            None,
        "audit_path":
            None,
    }

    evaluated = SimpleNamespace(
        accession=accession,
        source_evidence_sha256=source_sha,
    )

    class FakeStage5V1:
        source_truth = SimpleNamespace(
            SUITABLE="SUITABLE",
        )

    class FakeStage4V1:
        class InputObservation:
            def __init__(
                self,
                *,
                path,
                sha256,
                size_bytes,
            ):
                self.path = path
                self.sha256 = sha256
                self.size_bytes = size_bytes

        @staticmethod
        def validate_sha256(
            value,
            *,
            label,
        ):
            return value

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
            calls["audit_path"] = (
                Path(audit_path).resolve()
            )
            return (
                object(),
                (),
                {},
            )

    class FakeStage4V2:
        @staticmethod
        def load_stage4_v1(repo):
            return FakeStage4V1

        @staticmethod
        def _provider_batch_context_v2(
            **kwargs,
        ):
            calls["provider"] += 1
            return provider

    class FakeStage5V2:
        @staticmethod
        def load_stage5_v1(repo):
            return FakeStage5V1

        @staticmethod
        def load_stage4_v2(repo):
            return FakeStage4V2

    class FakeStage6V1:
        source_chromosome_integrity_execution = (
            SimpleNamespace(
                evaluate_stage3_candidate=(
                    lambda **kwargs:
                        evaluated
                )
            )
        )

        @staticmethod
        def monthly_historical_provider(
            accession,
        ):
            return None

        @staticmethod
        def observe_current_package(
            *,
            batch_dir,
            bridge,
            stage5_execution,
        ):
            calls["package_root"] = (
                Path(batch_dir).resolve()
            )
            return ()

    (
        evaluations,
        package_observations,
        provider_observations,
        provider_count,
    ) = module.evaluate_population_v2(
        repo=tmp_path,
        context=context,
        stage1_root=tmp_path,
        population=population,
        source_production_commit="1" * 40,
        completion_execution_commit="2" * 40,
        cache_execution_commit="3" * 40,
        stage6_v1=FakeStage6V1,
        stage5_v2=FakeStage5V2,
    )

    assert evaluations == (
        evaluated,
    )
    assert package_observations == ()
    assert provider_observations == ()
    assert provider_count == 1

    assert calls["provider"] == 1
    assert calls["package_root"] == (
        provider_root.resolve()
    )
    assert calls["audit_path"] == (
        candidate_audit.resolve()
    )


def test_stage5_identity_binds_completion_v2():
    stage4 = SimpleNamespace(
        release_id="2026.09",
        source_snapshot_id="snapshot",
        completion_v2_sha256="1" * 64,
        catalogue_sha256="2" * 64,
        catalogue_chain_signature=(
            (
                "2026.09",
                "a" * 40,
                "2" * 64,
            ),
        ),
        source_truth_completion_sha256="3" * 64,
        decisions_payload=b"stage4 decisions\n",
        record_payload=b"stage4 record\n",
    )

    context = SimpleNamespace(
        stage4_context=stage4,
        decisions_payload=b"stage5 decisions\n",
        record_payload=b"stage5 record\n",
        completion_sha256="4" * 64,
    )

    first = module.stage5_identity_v2(
        context
    )

    context_changed = SimpleNamespace(
        stage4_context=stage4,
        decisions_payload=b"stage5 decisions\n",
        record_payload=b"stage5 record\n",
        completion_sha256="5" * 64,
    )

    assert (
        module.stage5_identity_v2(
            context_changed
        )
        != first
    )
