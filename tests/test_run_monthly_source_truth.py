from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]

WRAPPER = (
    ROOT
    / "validation/selector-v1/"
    "run_monthly_source_truth.py"
)


def load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "_test_monthly_source_truth_execution",
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


def test_wrapper_import_has_no_execution_side_effect():
    module = load_wrapper()

    assert (
        module.COMPLETION_SCHEMA
        == "bacselect-monthly-source-truth-completion-v1"
    )

    assert (
        module.COMPLETION_STATUS
        == "SOURCE_TRUTH_EXECUTION_COMPLETE"
    )


def test_frozen_scientific_identities_are_exact():
    module = load_wrapper()

    assert (
        module.EXPECTED_MONTHLY_SOURCE_TRUTH_SHA256
        == "f30c5d67c6042d86f9eafa3b25d0c93b0bf9aefe1bb6208584256ab6275e89e1"
    )

    assert (
        module.EXPECTED_SOURCE_TRUTH_EXECUTION_SHA256
        == "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
    )

    assert (
        module.EXPECTED_CACHE_EXECUTOR_SHA256
        == "0a45ee60f06e102afba93cdc08f588f9bc547f7103279e59ffd4362cb5526c3e"
    )

    assert (
        module.EXPECTED_CATALOGUE_EXECUTOR_SHA256
        == "2cb7e162aa36b141d54b18fc29ffbaa9be3a5d9ca42a9e6b5bb1ff62e14cb3ea"
    )


def synthetic_batch(module):
    cache = module.load_frozen_cache_execution(
        ROOT
    )

    accession = "GCA_000000001.1"
    biosample = "SAMN00000001"

    candidate = {
        field:
            ""
        for field in cache.CANDIDATE_AUDIT_FIELDS
    }

    candidate.update(
        {
            "canonical_genbank_assembly_accession":
                accession,
            "expected_biosample":
                biosample,
            "observed_biosample":
                biosample,
            "sequence_eligibility":
                "eligible",
            "exclusion_reasons":
                "none",
            "result":
                "PASS",
            "fasta_file":
                "GCA_000000001.1_genomic.fna",
            "fasta_sha256":
                "1" * 64,
            "primary_assembly_records":
                "1",
        }
    )

    component = {
        "canonical_genbank_assembly_accession":
            accession,
        "component_genbank_accession":
            "CP000001.1",
        "length":
            "4",
        "topology":
            "linear",
        "ambiguous_base_count":
            "0",
        "ambiguous_symbols":
            "",
        "sequence_sha256":
            hashlib.sha256(
                b"ACGT"
            ).hexdigest(),
    }

    package_path = (
        "ncbi_dataset/data/"
        f"{accession}/"
        "GCA_000000001.1_genomic.fna"
    )

    package = {
        "path":
            package_path,
        "size_bytes":
            "20",
        "sha256":
            "1" * 64,
    }

    batch = cache.BatchEvidence(
        provenance={},
        candidate_rows=(
            candidate,
        ),
        component_rows=(
            component,
        ),
        package_rows=(
            package,
        ),
    )

    entry = {
        "canonical_genbank_assembly_accession":
            accession,
        "biosample":
            biosample,
        "package_artifacts": [
            {
                "package_path":
                    package_path,
                "logical_path":
                    (
                        "sequence-acquisition/"
                        "batch-00001/package/"
                        + package_path
                    ),
                "size_bytes":
                    20,
                "sha256":
                    "1" * 64,
            }
        ],
    }

    return (
        cache,
        batch,
        entry,
    )


def test_candidate_bridge_accepts_exact_origin_evidence():
    module = load_wrapper()

    cache, batch, entry = (
        synthetic_batch(
            module
        )
    )

    observed = (
        module.validate_candidate_bridge(
            cache,
            entry=entry,
            batch=batch,
        )
    )

    assert (
        observed.accession
        == "GCA_000000001.1"
    )

    assert (
        observed.primary_assembly_records
        == 1
    )


def test_candidate_bridge_rejects_biosample_drift():
    module = load_wrapper()

    cache, batch, entry = (
        synthetic_batch(
            module
        )
    )

    entry = dict(
        entry
    )

    entry[
        "biosample"
    ] = "SAMN99999999"

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="BioSample",
    ):
        module.validate_candidate_bridge(
            cache,
            entry=entry,
            batch=batch,
        )


def test_candidate_bridge_rejects_package_artifact_drift():
    module = load_wrapper()

    cache, batch, entry = (
        synthetic_batch(
            module
        )
    )

    entry = dict(
        entry
    )

    entry[
        "package_artifacts"
    ] = [
        dict(
            entry[
                "package_artifacts"
            ][
                0
            ],
            size_bytes=21,
        )
    ]

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="artifact identity",
    ):
        module.validate_candidate_bridge(
            cache,
            entry=entry,
            batch=batch,
        )


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
        "retained_count":
            3,
        "sequence_eligible_count":
            2,
        "sequence_ineligible_count":
            1,
        "retained_accessions_sha256":
            "7" * 64,
        "sequence_eligible_accessions_sha256":
            "8" * 64,
        "sequence_ineligible_accessions_sha256":
            "9" * 64,
        "decision_count":
            2,
        "relation_count":
            1,
        "decisions_sha256":
            "a" * 64,
        "relations_sha256":
            "b" * 64,
        "record_sha256":
            "c" * 64,
    }


def test_completion_receipt_roundtrip():
    module = load_wrapper()

    kwargs = completion_kwargs()

    payload = (
        module.build_completion_receipt(
            **kwargs
        )
    )

    audited = (
        module.audit_completion_receipt(
            payload,
            **kwargs,
        )
    )

    assert (
        audited[
            "status"
        ]
        == module.COMPLETION_STATUS
    )

    assert (
        audited[
            "decision_count"
        ]
        == 2
    )


def test_completion_receipt_rejects_population_mismatch():
    module = load_wrapper()

    kwargs = completion_kwargs()

    kwargs[
        "sequence_ineligible_count"
    ] = 2

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="population accounting",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_scientific_publication_is_no_clobber(tmp_path):
    module = load_wrapper()

    payloads = {
        module.DECISIONS_NAME:
            b"decisions\n",
        module.RELATIONS_NAME:
            b"relations\n",
        module.RECORD_NAME:
            b"record\n",
    }

    observed = []

    def auditor(values):
        assert values == payloads
        observed.append(
            "audit"
        )

    final = (
        module.publish_scientific_stage(
            stage1_root=tmp_path,
            payloads=payloads,
            auditor=auditor,
            stability_check=lambda:
                observed.append(
                    "stable"
                ),
        )
    )

    assert final.is_dir()

    assert {
        path.name
        for path in final.iterdir()
    } == set(
        payloads
    )

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="already exists",
    ):
        module.publish_scientific_stage(
            stage1_root=tmp_path,
            payloads=payloads,
            auditor=auditor,
            stability_check=lambda:
                None,
        )


def test_completion_publication_is_no_clobber(tmp_path):
    module = load_wrapper()

    payload = b'{"synthetic":true}\n'

    final = (
        module.publish_completion(
            stage1_root=tmp_path,
            payload=payload,
            auditor=lambda value:
                value,
            stability_check=lambda:
                None,
        )
    )

    assert (
        final.read_bytes()
        == payload
    )

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="already exists",
    ):
        module.publish_completion(
            stage1_root=tmp_path,
            payload=payload,
            auditor=lambda value:
                value,
            stability_check=lambda:
                None,
        )


def test_wrapper_contains_no_rename_replace_network_or_slurm():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "os.rename(",
        "os.replace(",
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


def test_cli_requires_explicit_authorization():
    module = load_wrapper()

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="explicit authorization",
    ):
        module.main(
            [
                "--expected-commit",
                "a" * 40,
                "--expected-wrapper-sha256",
                "b" * 64,
                "--expected-wrapper-test-sha256",
                "c" * 64,
                "--production-root",
                "/tmp/production",
                "--stage1-root",
                "/tmp/stage1",
                "--authoritative-root",
                "/tmp/objects",
            ]
        )


def test_future_origin_release_is_rejected():
    module = load_wrapper()

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="future origin",
    ):
        module.classify_origin_release(
            "2034.06",
            "2034.05",
        )

    assert (
        module.classify_origin_release(
            "2034.05",
            "2034.05",
        )
        == "current"
    )

    assert (
        module.classify_origin_release(
            "2034.04",
            "2034.05",
        )
        == "prior"
    )


def test_current_origin_rejects_snapshot_drift():
    module = load_wrapper()

    completion = SimpleNamespace(
        release_id="2034.05",
        source_snapshot_id=(
            "bacselect-source-2034.05-20340501T001700Z"
        ),
        completion_payload=b"completion\n",
        completion_record={
            "batches": [],
        },
        batch_evidence=(),
    )

    provenance = {
        "cache_origin_release_id":
            "2034.05",
        "cache_origin_source_snapshot_id":
            "bacselect-source-2034.05-WRONG",
    }

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="source snapshot",
    ):
        module._current_batch_evidence(
            cache_execution=SimpleNamespace(),
            completion_context=completion,
            provenance=provenance,
            expected_commit="a" * 40,
        )


def test_output_paths_must_be_clear_before_science(
    tmp_path,
):
    module = load_wrapper()

    completion = (
        tmp_path
        / module.COMPLETION_NAME
    )

    completion.write_text(
        "existing\n",
        encoding="ascii",
    )

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="completion already exists",
    ):
        module.require_output_paths_clear(
            tmp_path
        )


def test_scientific_stage_inventory_is_exact(
    tmp_path,
):
    module = load_wrapper()

    for name in module.SCIENTIFIC_NAMES:
        (
            tmp_path
            / name
        ).write_text(
            name + "\n",
            encoding="ascii",
        )

    observed = (
        module.read_exact_scientific_stage(
            tmp_path
        )
    )

    assert set(
        observed
    ) == set(
        module.SCIENTIFIC_NAMES
    )

    (
        tmp_path
        / "unexpected.txt"
    ).write_text(
        "unexpected\n",
        encoding="ascii",
    )

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="inventory changed",
    ):
        module.read_exact_scientific_stage(
            tmp_path
        )


def test_completion_receipt_validates_counts():
    module = load_wrapper()

    kwargs = completion_kwargs()

    kwargs[
        "relation_count"
    ] = -1

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="relation count",
    ):
        module.build_completion_receipt(
            **kwargs
        )

    kwargs = completion_kwargs()

    kwargs[
        "catalogue_chain_count"
    ] = 0

    with pytest.raises(
        module.MonthlySourceTruthExecutionError,
        match="must be positive",
    ):
        module.build_completion_receipt(
            **kwargs
        )


def test_executor_preflight_chains_frozen_upstream_preflights():
    text = WRAPPER.read_text(
        encoding="utf-8"
    )

    assert (
        "cache_execution.repository_preflight("
        in text
    )

    assert (
        "catalogue_execution.repository_preflight("
        in text
    )
