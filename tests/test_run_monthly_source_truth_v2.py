from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


MODULE_PATH = (
    Path(
        __file__
    )
    .resolve()
    .parents[
        1
    ]
    / "validation"
    / "selector-v1"
    / "run_monthly_source_truth_v2.py"
)


def _load_module():
    name = (
        "_test_run_monthly_source_truth_v2"
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            MODULE_PATH,
        )
    )

    assert spec is not None
    assert spec.loader is not None

    module = (
        importlib.util
        .module_from_spec(
            spec
        )
    )

    sys.modules[
        name
    ] = module

    spec.loader.exec_module(
        module
    )

    return module


stage4_v2 = _load_module()


def _sha(
    payload: bytes,
) -> str:
    return (
        hashlib.sha256(
            payload
        ).hexdigest()
    )


def _receipt_kwargs():
    return {
        "release_id":
            "2026.09",
        "source_snapshot_id":
            (
                "bacselect-source-"
                "2026.09-test"
            ),
        "source_snapshot_record_sha256":
            "1" * 64,
        "source_production_commit":
            "1" * 40,
        "completion_execution_commit":
            "2" * 40,
        "cache_execution_commit":
            "3" * 40,
        "source_truth_execution_commit":
            "4" * 40,
        "metadata_record_sha256":
            "2" * 64,
        "metadata_completion_sha256":
            "3" * 64,
        "sequence_acquisition_completion_sha256":
            "4" * 64,
        "catalogue_chain_count":
            1,
        "catalogue_chain_sha256":
            "5" * 64,
        "sequence_cache_catalogue_sha256":
            "6" * 64,
        "sequence_cache_entries_sha256":
            "7" * 64,
        "retained_count":
            3,
        "sequence_eligible_count":
            2,
        "sequence_ineligible_count":
            1,
        "retained_accessions_sha256":
            "8" * 64,
        "sequence_eligible_accessions_sha256":
            "9" * 64,
        "sequence_ineligible_accessions_sha256":
            "a" * 64,
        "decision_count":
            2,
        "relation_count":
            1,
        "decisions_sha256":
            "b" * 64,
        "relations_sha256":
            "c" * 64,
        "record_sha256":
            "d" * 64,
    }


def test_completion_v2_keeps_execution_identities_separate():
    kwargs = (
        _receipt_kwargs()
    )

    payload = (
        stage4_v2
        .build_completion_receipt_v2(
            **kwargs
        )
    )

    observed = (
        stage4_v2
        .audit_completion_receipt_v2(
            payload,
            **kwargs
        )
    )

    assert (
        observed[
            "source_production_commit"
        ]
        == "1" * 40
    )

    assert (
        observed[
            "completion_execution_commit"
        ]
        == "2" * 40
    )

    assert (
        observed[
            "cache_execution_commit"
        ]
        == "3" * 40
    )

    assert (
        observed[
            "source_truth_execution_commit"
        ]
        == "4" * 40
    )

    assert (
        observed[
            "schema_version"
        ]
        == stage4_v2.COMPLETION_SCHEMA
    )

    assert (
        observed[
            "status"
        ]
        == stage4_v2.COMPLETION_STATUS
    )


def test_catalogue_chain_sha256_v2_binds_cache_execution_commit():
    one = (
        stage4_v2
        .catalogue_chain_sha256_v2(
            (
                (
                    "2026.09",
                    "1" * 40,
                    "a" * 64,
                ),
            )
        )
    )

    two = (
        stage4_v2
        .catalogue_chain_sha256_v2(
            (
                (
                    "2026.09",
                    "2" * 40,
                    "a" * 64,
                ),
            )
        )
    )

    assert (
        one
        != two
    )


@dataclass(
    frozen=True,
)
class FakeBatchEvidence:
    provenance: object
    candidate_rows: tuple
    component_rows: tuple
    package_rows: tuple


class FakeCacheExecution:
    CANDIDATE_AUDIT_FIELDS = (
        "candidate",
    )

    COMPONENT_AUDIT_FIELDS = (
        "component",
    )

    PACKAGE_FILE_FIELDS = (
        "package",
    )

    BatchEvidence = (
        FakeBatchEvidence
    )


def test_recovery_provider_resolves_from_authenticated_logical_paths(
    tmp_path,
    monkeypatch,
):
    stage1 = (
        tmp_path
        / "stage1"
    )

    provider = (
        stage1
        / "sequence-acquisition-recovery"
        / (
            "9"
            * 40
        )
        / (
            "source-"
            + "1" * 40
        )
        / "batch-00130"
    )

    provider.mkdir(
        parents=True
    )

    payloads = {
        "recovery-summary.json":
            b"summary\n",
        "candidate-sequence-audit.tsv":
            b"candidate\n",
        "component-sequence-audit.tsv":
            b"component\n",
        "recovery-package-files.tsv":
            b"package\n",
    }

    references = {}

    for name, payload in (
        payloads.items()
    ):
        path = (
            provider
            / name
        )

        path.write_bytes(
            payload
        )

        references[
            name
        ] = {
            "logical_path":
                (
                    path
                    .relative_to(
                        stage1
                    )
                    .as_posix()
                ),
            "sha256":
                _sha(
                    payload
                ),
            "size_bytes":
                len(
                    payload
                ),
        }

    monkeypatch.setattr(
        stage4_v2.cache_v1,
        "_parse_tsv",
        (
            lambda payload, *, fields, label:
                (
                    {
                        "payload":
                            (
                                payload
                                .decode(
                                    "ascii"
                                )
                                .strip()
                            ),
                        "label":
                            label,
                    },
                )
        ),
    )

    completion_sha = (
        "e"
        * 64
    )

    provenance = {
        "batch_id":
            "batch-00130",
        "cache_origin_release_id":
            "2026.09",
        "cache_origin_source_snapshot_id":
            "snapshot",
        "cache_origin_source_production_commit":
            "1" * 40,
        "cache_origin_completion_execution_commit":
            "2" * 40,
        "cache_origin_execution_commit":
            "3" * 40,
        "origin_sequence_acquisition_completion_sha256":
            completion_sha,
        "requested_accessions":
            3,
        "accessions_sha256":
            "a" * 64,
        "source_class":
            "fresh-recovery",
        "recovery_class":
            "accession-supersession",
        "recovery_commit":
            "9" * 40,
        "source_batch_sha256":
            "b" * 64,
        "source_package_sha256":
            "c" * 64,
        "recovery_package_sha256":
            "d" * 64,
        "recovery_summary_sha256":
            _sha(
                payloads[
                    "recovery-summary.json"
                ]
            ),
        "cause_evidence_sha256":
            "f" * 64,
        "transport_record_sha256":
            "0" * 64,
        "source_partial_name":
            "batch-00130.partial",
        "origin_package_file_readback_sha256":
            "6" * 64,
        "provider_summary":
            references[
                "recovery-summary.json"
            ],
        "candidate_audit":
            references[
                "candidate-sequence-audit.tsv"
            ],
        "component_audit":
            references[
                "component-sequence-audit.tsv"
            ],
        "package_manifest":
            references[
                "recovery-package-files.tsv"
            ],
    }

    completion_batch = {
        "batch_id":
            "batch-00130",
        "requested_accessions":
            3,
        "accessions_sha256":
            "a" * 64,
        "source_class":
            "fresh-recovery",
        "recovery_class":
            "accession-supersession",
        "recovery_commit":
            "9" * 40,
        "source_batch_sha256":
            "b" * 64,
        "source_package_sha256":
            "c" * 64,
        "recovery_package_sha256":
            "d" * 64,
        "recovery_summary_sha256":
            _sha(
                payloads[
                    "recovery-summary.json"
                ]
            ),
        "cause_evidence_sha256":
            "f" * 64,
        "transport_record_sha256":
            "0" * 64,
        "source_partial_name":
            "batch-00130.partial",
        "provider_summary_name":
            "recovery-summary.json",
        "provider_summary_sha256":
            _sha(
                payloads[
                    "recovery-summary.json"
                ]
            ),
        "candidate_sequence_audit_sha256":
            _sha(
                payloads[
                    "candidate-sequence-audit.tsv"
                ]
            ),
        "component_sequence_audit_sha256":
            _sha(
                payloads[
                    "component-sequence-audit.tsv"
                ]
            ),
        "package_manifest_name":
            "recovery-package-files.tsv",
        "package_manifest_sha256":
            _sha(
                payloads[
                    "recovery-package-files.tsv"
                ]
            ),
        "package_file_readback_sha256":
            "6" * 64,
    }

    observed = (
        stage4_v2
        ._provider_batch_context_v2(
            stage1_root=(
                stage1
            ),
            cache_execution=(
                FakeCacheExecution
            ),
            provenance=(
                provenance
            ),
            completion_batch=(
                completion_batch
            ),
            release_id=(
                "2026.09"
            ),
            source_snapshot_id=(
                "snapshot"
            ),
            source_production_commit=(
                "1" * 40
            ),
            completion_execution_commit=(
                "2" * 40
            ),
            cache_execution_commit=(
                "3" * 40
            ),
            completion_sha256=(
                completion_sha
            ),
        )
    )

    assert (
        observed.batch_id
        == "batch-00130"
    )

    assert (
        observed.provider_root
        == provider.resolve()
    )

    assert (
        observed.candidate_audit_path
        == (
            provider
            / "candidate-sequence-audit.tsv"
        )
    )

    assert (
        observed
        .batch
        .candidate_rows[
            0
        ][
            "payload"
        ]
        == "candidate"
    )

    assert (
        observed
        .batch
        .component_rows[
            0
        ][
            "payload"
        ]
        == "component"
    )

    assert (
        observed
        .batch
        .package_rows[
            0
        ][
            "payload"
        ]
        == "package"
    )

    assert (
        len(
            observed.observations
        )
        == 4
    )


def test_provider_candidate_evaluation_uses_recovery_audit_path(
    tmp_path,
):
    provider_root = (
        tmp_path
        / "recovery"
        / "batch-00072"
    )

    provider_root.mkdir(
        parents=True
    )

    audit_path = (
        provider_root
        / "candidate-sequence-audit.tsv"
    )

    audit_path.write_text(
        "audit\n",
        encoding="ascii",
    )

    fasta = (
        provider_root
        / "package"
        / "ncbi_dataset"
        / "data"
        / "GCA_1.1"
        / "genomic.fna"
    )

    fasta.parent.mkdir(
        parents=True
    )

    fasta.write_bytes(
        b">x\nACGT\n"
    )

    bridge = (
        SimpleNamespace(
            accession=(
                "GCA_1.1"
            ),
            fasta_package_path=(
                "ncbi_dataset/data/"
                "GCA_1.1/genomic.fna"
            ),
            fasta_sha256=(
                _sha(
                    fasta.read_bytes()
                )
            ),
            fasta_size_bytes=(
                fasta.stat().st_size
            ),
        )
    )

    candidate = (
        SimpleNamespace(
            batch_dir=(
                provider_root
                / "package"
            )
        )
    )

    seen = {}

    def source_truth_objects(
        observed_bridge,
        *,
        audit_path,
    ):
        assert (
            observed_bridge
            is bridge
        )

        seen[
            "audit_path"
        ] = audit_path

        return (
            candidate,
            (),
            {},
        )

    def resolve_manifest_path(
        batch_dir,
        relative_path,
    ):
        assert (
            batch_dir
            == (
                provider_root
                / "package"
            )
        )

        return (
            batch_dir
            / relative_path
        )

    def observe_exact_file(
        path,
        *,
        expected_sha256,
        expected_size_bytes,
    ):
        assert (
            path
            == fasta
        )

        assert (
            expected_sha256
            == bridge.fasta_sha256
        )

        assert (
            expected_size_bytes
            == bridge.fasta_size_bytes
        )

        return (
            "observation"
        )

    fake_stage4 = (
        SimpleNamespace(
            _source_truth_objects=(
                source_truth_objects
            ),
            source_truth_execution=(
                SimpleNamespace(
                    evaluate_candidate=(
                        lambda candidate, components, manifest:
                            "decision"
                    ),
                    resolve_manifest_path=(
                        resolve_manifest_path
                    ),
                )
            ),
            _observe_exact_file=(
                observe_exact_file
            ),
        )
    )

    provider = (
        stage4_v2
        .ProviderBatchContextV2(
            batch_id=(
                "batch-00072"
            ),
            provider_root=(
                provider_root
            ),
            candidate_audit_path=(
                audit_path
            ),
            batch=(
                object()
            ),
            observations=(),
        )
    )

    (
        decision,
        observation,
    ) = (
        stage4_v2
        ._evaluate_provider_candidate(
            fake_stage4,
            bridge=(
                bridge
            ),
            provider=(
                provider
            ),
        )
    )

    assert (
        seen[
            "audit_path"
        ]
        == audit_path
    )

    assert (
        decision
        == "decision"
    )

    assert (
        observation
        == "observation"
    )
