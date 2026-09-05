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
    / "run_monthly_biosample_reconciliation_v2.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "_test_monthly_biosample_v2_executor",
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


class FakeStage5V1:
    COMPLETION_SCHEMA = (
        "bacselect-monthly-biosample-reconciliation-completion-v1"
    )

    @staticmethod
    def _canonical_json_bytes(value):
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
            **kwargs,
            "execution_commit":
                execution_commit,
            "schema_version":
                FakeStage5V1.COMPLETION_SCHEMA,
            "status":
                "BIOSAMPLE_RECONCILIATION_EXECUTION_COMPLETE",
        }
        return FakeStage5V1._canonical_json_bytes(
            record
        )


def completion_kwargs():
    return {
        "release_id":
            "2026.09",
        "source_snapshot_id":
            "bacselect-source-2026.09-20260901T021652Z",
        "source_snapshot_record_sha256":
            "1" * 64,
        "metadata_record_sha256":
            "2" * 64,
        "metadata_completion_sha256":
            "3" * 64,
        "catalogue_chain_count":
            1,
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
            3,
        "nonrepresentative_count":
            1,
        "unresolved_count":
            0,
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


def v2_identity_kwargs():
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
        "sequence_acquisition_completion_sha256":
            "d" * 64,
    }


def test_completion_v2_keeps_execution_identities_separate():
    payload = module.build_completion_receipt_v2(
        FakeStage5V1,
        **v2_identity_kwargs(),
        **completion_kwargs(),
    )

    value = json.loads(payload)

    assert value["schema_version"] == module.COMPLETION_SCHEMA
    assert value["status"] == module.COMPLETION_STATUS
    assert "execution_commit" not in value

    for key, expected in v2_identity_kwargs().items():
        assert value[key] == expected

    observed = module.audit_completion_receipt_v2(
        FakeStage5V1,
        payload,
        **v2_identity_kwargs(),
        **completion_kwargs(),
    )

    assert observed == value


def test_completion_v2_rejects_changed_payload():
    payload = module.build_completion_receipt_v2(
        FakeStage5V1,
        **v2_identity_kwargs(),
        **completion_kwargs(),
    )

    value = json.loads(payload)
    value["continue_count"] = 99

    broken = FakeStage5V1._canonical_json_bytes(
        value
    )

    with pytest.raises(
        module.MonthlyBioSampleV2ExecutionError,
        match="changed",
    ):
        module.audit_completion_receipt_v2(
            FakeStage5V1,
            broken,
            **v2_identity_kwargs(),
            **completion_kwargs(),
        )


def test_wrapper_has_no_network_or_slurm():
    payload = WRAPPER.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "requests.",
        "urllib.request",
        "subprocess.run([\"sbatch\"",
        "subprocess.run(['sbatch'",
        "srun ",
    )

    for token in forbidden:
        assert token not in payload


def test_recovery_candidate_uses_authenticated_provider_path(
    monkeypatch,
    tmp_path,
):
    accession = "GCA_030436345.2"
    biosample = "SAMN00000001"

    provider_root = (
        tmp_path
        / "sequence-acquisition-recovery"
        / "recovery"
        / "source-production"
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

    fasta_relative = (
        "package/ncbi_dataset/data/"
        f"{accession}/genomic.fna"
    )
    fasta_path = (
        provider_root
        / fasta_relative
    )
    fasta_path.parent.mkdir(
        parents=True
    )
    fasta_payload = b">chr\nACGT\n"
    fasta_path.write_bytes(
        fasta_payload
    )
    fasta_sha = hashlib.sha256(
        fasta_payload
    ).hexdigest()

    provenance_sha = "a" * 64
    provenance = {
        "cache_origin_release_id":
            "2026.09",
        "batch_id":
            "batch-00072",
    }

    bridge = SimpleNamespace(
        accession=accession,
        biosample=biosample,
        fasta_package_path=fasta_relative,
        fasta_sha256=fasta_sha,
        fasta_size_bytes=len(
            fasta_payload
        ),
    )

    batch = SimpleNamespace()

    provider = SimpleNamespace(
        provider_root=provider_root,
        candidate_audit_path=candidate_audit,
        batch=batch,
        observations=(),
    )

    context = SimpleNamespace(
        release_id="2026.09",
        source_snapshot_id=(
            "bacselect-source-2026.09-20260901T021652Z"
        ),
        completion_v2_sha256="b" * 64,
        cache_execution=object(),
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
                    "c" * 64,
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
        "provider":
            0,
        "audit_path":
            None,
    }

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

        class source_truth_execution:
            @staticmethod
            def resolve_manifest_path(
                batch_dir,
                relative,
            ):
                return (
                    Path(batch_dir)
                    / relative
                )

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
                SimpleNamespace(
                    batch_dir=provider_root
                ),
                (),
                {},
            )

        @staticmethod
        def _observe_exact_file(
            path,
            *,
            expected_sha256,
            expected_size_bytes,
        ):
            assert Path(path).resolve() == (
                fasta_path.resolve()
            )
            assert expected_sha256 == fasta_sha
            assert expected_size_bytes == len(
                fasta_payload
            )

            return SimpleNamespace(
                path=Path(path),
                sha256=expected_sha256,
                size_bytes=expected_size_bytes,
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
            assert (
                kwargs["provenance"]
                is provenance
            )
            return provider

    class FakeStage5:
        source_truth = SimpleNamespace(
            SUITABLE="SUITABLE",
        )

        @staticmethod
        def fingerprint_stage2_candidate(
            *,
            candidate,
            component_rows,
            package_manifest,
            expected_source_evidence_sha256,
            biosample,
        ):
            assert biosample == "SAMN00000001"
            assert (
                expected_source_evidence_sha256
                == "c" * 64
            )

            return SimpleNamespace(
                accession=accession,
            )

    monkeypatch.setattr(
        module,
        "__file__",
        str(
            Path(__file__).resolve().parents[1]
            / "validation"
            / "selector-v1"
            / "run_monthly_biosample_reconciliation_v2.py"
        ),
    )

    fingerprints, observations = (
        module.fingerprint_population_v2(
            context=context,
            stage1_root=tmp_path,
            population=population,
            source_production_commit="1" * 40,
            completion_execution_commit="2" * 40,
            cache_execution_commit="3" * 40,
            stage5_v1=FakeStage5,
            stage4_v2=FakeStage4V2,
        )
    )

    assert len(fingerprints) == 1
    assert len(observations) == 1
    assert calls["provider"] == 1
    assert calls["audit_path"] == (
        candidate_audit.resolve()
    )
