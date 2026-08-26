from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from bacselect.source_repeated_biosample_execution import (
    VerifiedBioSampleFingerprint,
)
from bacselect.source_truth_execution import (
    CandidateAudit,
    source_evidence_sha256,
)


REPO = Path(__file__).resolve().parents[1]

WRAPPER = (
    REPO
    / "validation"
    / "selector-v1"
    / "run_repeated_biosample_execution.py"
)


def load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "run_repeated_biosample_execution",
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

    try:
        spec.loader.exec_module(
            module
        )
    except BaseException:
        sys.modules.pop(
            spec.name,
            None,
        )
        raise

    return module


def write_tsv(
    path: Path,
    fields,
    rows,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                fields
            ),
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                row
            )


def file_sha(
    path: Path,
):
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def decision_row(
    accession,
    status,
    *,
    source_symbol="1",
    sequence_symbol="2",
):
    return {
        "canonical_genbank_assembly_accession":
            accession,
        "source_evidence_sha256":
            source_symbol * 64,
        "sequence_set_sha256":
            sequence_symbol * 64,
        "duplicate_relation_count":
            "0",
        "containment_relation_count":
            "0",
        "source_truth_status":
            status,
        "source_truth_reason":
            (
                "NO_SOURCE_REDUNDANCY"
                if status == "SUITABLE"
                else "LINEAR_COMPONENT_FULLY_CONTAINED"
            ),
    }


def test_stage1_wrapper_load_is_exact_and_side_effect_free():
    module = load_wrapper()

    stage1 = module.load_stage1_wrapper(
        REPO
    )

    assert (
        stage1.EXPECTED_STAGE1_TOTAL
        == 68480
    )


def test_stage1_decision_loader_filters_only_suitable(
    tmp_path,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    path = tmp_path / "stage1.tsv"

    rows = (
        decision_row(
            "GCA_000000001.1",
            "SUITABLE",
            source_symbol="1",
        ),
        decision_row(
            "GCA_000000002.1",
            "EXCLUDE_SOURCE_TRUTH",
            source_symbol="2",
        ),
        decision_row(
            "GCA_000000003.1",
            "SUITABLE",
            source_symbol="3",
        ),
    )

    write_tsv(
        path,
        stage1.DECISION_FIELDS,
        rows,
    )

    observed = (
        module.load_stage1_decisions(
            path,
            stage1=stage1,
            expected_sha256=(
                file_sha(
                    path
                )
            ),
            expected_total=3,
            expected_suitable=2,
            expected_excluded=1,
            expected_unresolved=0,
        )
    )

    assert tuple(
        observed.suitable_source_sha256
    ) == (
        "GCA_000000001.1",
        "GCA_000000003.1",
    )

    assert (
        observed.status_counts
        == {
            "EXCLUDE_SOURCE_TRUTH":
                1,
            "SUITABLE":
                2,
        }
    )


def test_stage1_decision_schema_drift_fails_closed(
    tmp_path,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    path = tmp_path / "stage1.tsv"

    write_tsv(
        path,
        (
            "canonical_genbank_assembly_accession",
            "source_truth_status",
        ),
        (
            {
                "canonical_genbank_assembly_accession":
                    "GCA_000000001.1",
                "source_truth_status":
                    "SUITABLE",
            },
        ),
    )

    with pytest.raises(
        stage1.ExecutionError,
        match="schema mismatch",
    ):
        module.load_stage1_decisions(
            path,
            stage1=stage1,
            expected_sha256=(
                file_sha(
                    path
                )
            ),
            expected_total=1,
            expected_suitable=1,
            expected_excluded=0,
            expected_unresolved=0,
        )


def test_biosample_mapping_is_exact_and_disjoint(
    tmp_path,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    cache = tmp_path / "cache.tsv"
    fresh = tmp_path / "fresh.tsv"

    write_tsv(
        cache,
        module.CACHE_BIOSAMPLE_FIELDS,
        (
            {
                "canonical_genbank_assembly_accession":
                    "GCA_000000001.1",
                "fresh_biosample":
                    "SAMN1",
                "historical_batch":
                    "batch-001",
                "historical_sequence_eligibility":
                    "eligible",
                "historical_exclusion_reasons":
                    "",
            },
            {
                "canonical_genbank_assembly_accession":
                    "GCA_000000002.1",
                "fresh_biosample":
                    "SAMEA2",
                "historical_batch":
                    "batch-002",
                "historical_sequence_eligibility":
                    "ineligible",
                "historical_exclusion_reasons":
                    "ambiguous_nucleotide",
            },
        ),
    )

    write_tsv(
        fresh,
        module.FRESH_BIOSAMPLE_FIELDS,
        (
            {
                "canonical_genbank_assembly_accession":
                    "GCA_000000003.1",
                "fresh_biosample":
                    "SAMD3",
                "acquisition_reason":
                    "fresh_download",
            },
        ),
    )

    observed = (
        module.load_biosample_mapping(
            cache_manifest_path=cache,
            fresh_manifest_path=fresh,
            stage1=stage1,
            expected_cache_sha256=(
                file_sha(
                    cache
                )
            ),
            expected_fresh_sha256=(
                file_sha(
                    fresh
                )
            ),
            expected_cache_rows=2,
            expected_fresh_rows=1,
            expected_total=3,
        )
    )

    assert observed.biosample_by_accession == {
        "GCA_000000001.1":
            "SAMN1",
        "GCA_000000002.1":
            "SAMEA2",
        "GCA_000000003.1":
            "SAMD3",
    }


def test_biosample_mapping_rejects_malformed_accession(
    tmp_path,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    cache = tmp_path / "cache.tsv"
    fresh = tmp_path / "fresh.tsv"

    write_tsv(
        cache,
        module.CACHE_BIOSAMPLE_FIELDS,
        (
            {
                "canonical_genbank_assembly_accession":
                    "GCA_000000001.1",
                "fresh_biosample":
                    "BAD1",
                "historical_batch":
                    "batch-001",
                "historical_sequence_eligibility":
                    "eligible",
                "historical_exclusion_reasons":
                    "",
            },
        ),
    )

    write_tsv(
        fresh,
        module.FRESH_BIOSAMPLE_FIELDS,
        (),
    )

    with pytest.raises(
        module.Stage2WrapperError,
        match="BioSample",
    ):
        module.load_biosample_mapping(
            cache_manifest_path=cache,
            fresh_manifest_path=fresh,
            stage1=stage1,
            expected_cache_sha256=(
                file_sha(
                    cache
                )
            ),
            expected_fresh_sha256=(
                file_sha(
                    fresh
                )
            ),
            expected_cache_rows=1,
            expected_fresh_rows=0,
            expected_total=1,
        )


def synthetic_decisions(
    module,
    accessions,
):
    source = {
        accession:
            hashlib.sha256(
                (
                    "source:"
                    + accession
                ).encode(
                    "ascii"
                )
            ).hexdigest()
        for accession in accessions
    }

    return module.Stage1DecisionBundle(
        all_accessions=tuple(
            sorted(
                accessions
            )
        ),
        suitable_source_sha256=source,
        all_membership_sha256=(
            module.accession_membership_sha256(
                accessions
            )
        ),
        suitable_membership_sha256=(
            module.accession_membership_sha256(
                accessions
            )
        ),
        status_counts={
            "SUITABLE":
                len(
                    accessions
                ),
        },
    )


def test_population_binding_requires_exact_stage1_membership():
    module = load_wrapper()

    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    bundle = SimpleNamespace(
        historical_candidates=(
            SimpleNamespace(
                accession=accessions[0]
            ),
        ),
        fresh_candidates=(
            SimpleNamespace(
                accession=accessions[1]
            ),
        ),
        combined_membership_sha256=(
            module.accession_membership_sha256(
                accessions
            )
        ),
    )

    decisions = synthetic_decisions(
        module,
        accessions,
    )

    biosamples = (
        module.BioSampleMappingBundle(
            biosample_by_accession={
                accessions[0]:
                    "SAMN1",
                accessions[1]:
                    "SAMN2",
            },
            cache_row_count=1,
            fresh_row_count=1,
        )
    )

    module.verify_stage2_population_binding(
        bundle=bundle,
        decisions=decisions,
        biosamples=biosamples,
        expected_stage1_total=2,
        expected_stage2_total=2,
    )


def test_population_binding_rejects_missing_biosample():
    module = load_wrapper()

    accessions = (
        "GCA_000000001.1",
    )

    bundle = SimpleNamespace(
        historical_candidates=(
            SimpleNamespace(
                accession=accessions[0]
            ),
        ),
        fresh_candidates=(),
        combined_membership_sha256=(
            module.accession_membership_sha256(
                accessions
            )
        ),
    )

    decisions = synthetic_decisions(
        module,
        accessions,
    )

    biosamples = (
        module.BioSampleMappingBundle(
            biosample_by_accession={},
            cache_row_count=0,
            fresh_row_count=0,
        )
    )

    with pytest.raises(
        module.Stage2WrapperError,
        match="BioSample",
    ):
        module.verify_stage2_population_binding(
            bundle=bundle,
            decisions=decisions,
            biosamples=biosamples,
            expected_stage1_total=1,
            expected_stage2_total=1,
        )


def test_group_accounting_exact():
    module = load_wrapper()

    records = (
        VerifiedBioSampleFingerprint(
            accession="GCA_000000001.1",
            biosample="SAMN1",
            source_evidence_sha256="1" * 64,
            assembly_fingerprint="a" * 64,
        ),
        VerifiedBioSampleFingerprint(
            accession="GCA_000000002.1",
            biosample="SAMN1",
            source_evidence_sha256="2" * 64,
            assembly_fingerprint="a" * 64,
        ),
        VerifiedBioSampleFingerprint(
            accession="GCA_000000003.1",
            biosample="SAMN2",
            source_evidence_sha256="3" * 64,
            assembly_fingerprint="b" * 64,
        ),
        VerifiedBioSampleFingerprint(
            accession="GCA_000000004.1",
            biosample="SAMN2",
            source_evidence_sha256="4" * 64,
            assembly_fingerprint="c" * 64,
        ),
        VerifiedBioSampleFingerprint(
            accession="GCA_000000005.1",
            biosample="SAMN3",
            source_evidence_sha256="5" * 64,
            assembly_fingerprint="d" * 64,
        ),
    )

    decisions = (
        module.reconcile_verified_candidates(
            records
        )
    )

    rows, counts = (
        module.build_group_rows(
            records,
            decisions,
        )
    )

    assert len(
        rows
    ) == 3

    assert counts == {
        "all":
            3,
        "singleton":
            1,
        "repeated":
            2,
        "identical_repeated":
            1,
        "differing_repeated":
            1,
    }


def test_predecision_exists_before_fingerprinting(
    tmp_path,
    monkeypatch,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    output_root = tmp_path / "scratch"

    stage1_decisions_path = (
        tmp_path
        / "stage1-decisions.tsv"
    )

    fresh_manifest_path = (
        tmp_path
        / "fresh-manifest.tsv"
    )

    stage1_decisions_path.write_text(
        "synthetic\n",
        encoding="utf-8",
    )

    fresh_manifest_path.write_text(
        "synthetic\n",
        encoding="utf-8",
    )

    accessions = tuple(
        f"GCA_{index:09d}.1"
        for index in range(
            1,
            6,
        )
    )

    decisions = synthetic_decisions(
        module,
        accessions,
    )

    biosamples = (
        module.BioSampleMappingBundle(
            biosample_by_accession={
                accessions[0]:
                    "SAMN1",
                accessions[1]:
                    "SAMN1",
                accessions[2]:
                    "SAMN2",
                accessions[3]:
                    "SAMN2",
                accessions[4]:
                    "SAMN3",
            },
            cache_row_count=2,
            fresh_row_count=3,
        )
    )

    bundle = SimpleNamespace(
        historical_candidates=tuple(
            SimpleNamespace(
                accession=accession
            )
            for accession in accessions
        ),
        fresh_candidates=(),
        batches=(),
        historical_membership_sha256=(
            decisions.all_membership_sha256
        ),
        fresh_membership_sha256=(
            module.accession_membership_sha256(
                ()
            )
        ),
        combined_membership_sha256=(
            decisions.all_membership_sha256
        ),
        input_evidence_rows=(),
    )

    expected_commit = "a" * 40

    observed = {
        "predecision":
            False,
    }

    def fake_fingerprint_population(
        *,
        bundle,
        decisions,
        biosamples,
    ):
        predecision_path = (
            output_root
            / (
                "."
                + expected_commit
                + ".partial"
            )
            / "stage2-predecision-provenance.json"
        )

        observed[
            "predecision"
        ] = predecision_path.is_file()

        return (
            VerifiedBioSampleFingerprint(
                accession=accessions[0],
                biosample="SAMN1",
                source_evidence_sha256=(
                    decisions.suitable_source_sha256[
                        accessions[0]
                    ]
                ),
                assembly_fingerprint="a" * 64,
            ),
            VerifiedBioSampleFingerprint(
                accession=accessions[1],
                biosample="SAMN1",
                source_evidence_sha256=(
                    decisions.suitable_source_sha256[
                        accessions[1]
                    ]
                ),
                assembly_fingerprint="a" * 64,
            ),
            VerifiedBioSampleFingerprint(
                accession=accessions[2],
                biosample="SAMN2",
                source_evidence_sha256=(
                    decisions.suitable_source_sha256[
                        accessions[2]
                    ]
                ),
                assembly_fingerprint="b" * 64,
            ),
            VerifiedBioSampleFingerprint(
                accession=accessions[3],
                biosample="SAMN2",
                source_evidence_sha256=(
                    decisions.suitable_source_sha256[
                        accessions[3]
                    ]
                ),
                assembly_fingerprint="c" * 64,
            ),
            VerifiedBioSampleFingerprint(
                accession=accessions[4],
                biosample="SAMN3",
                source_evidence_sha256=(
                    decisions.suitable_source_sha256[
                        accessions[4]
                    ]
                ),
                assembly_fingerprint="d" * 64,
            ),
        )

    monkeypatch.setattr(
        module,
        "fingerprint_population",
        fake_fingerprint_population,
    )

    final_dir = (
        module.execute_to_scratch(
            repo=repo,
            expected_commit=expected_commit,
            output_root=output_root,
            stage1=stage1,
            bundle=bundle,
            decisions=decisions,
            biosamples=biosamples,
            frozen_repo_sha256={},
            stage1_decisions_path=(
                stage1_decisions_path
            ),
            fresh_manifest_path=(
                fresh_manifest_path
            ),
        )
    )

    assert observed[
        "predecision"
    ] is True

    assert final_dir.is_dir()

    expected_files = {
        "stage2-input-evidence-manifest.tsv",
        "stage2-predecision-provenance.json",
        "stage2-repeated-biosample-decisions.tsv",
        "stage2-biosample-groups.tsv",
        "stage2-execution-provenance.json",
        "stage2-aggregate-summary.json",
        "stage2-content-manifest.tsv",
    }

    assert {
        path.name
        for path in final_dir.iterdir()
    } == expected_files

    summary = json.loads(
        (
            final_dir
            / "stage2-aggregate-summary.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    assert summary[
        "stage2_input_candidate_count"
    ] == 5

    assert summary[
        "biosample_group_count"
    ] == 3

    assert summary[
        "singleton_group_count"
    ] == 1

    assert summary[
        "repeated_group_count"
    ] == 2

    assert summary[
        "identical_repeated_group_count"
    ] == 1

    assert summary[
        "differing_repeated_group_count"
    ] == 1

    assert summary[
        "status_counts"
    ] == {
        "CONTINUE":
            2,
        "NONREPRESENTATIVE":
            1,
        "REVIEW_UNRESOLVED":
            2,
    }

    summary_text = json.dumps(
        summary,
        sort_keys=True,
    )

    assert "GCA_" not in summary_text
    assert "SAMN" not in summary_text


def test_failed_execution_preserves_partial_predecision(
    tmp_path,
    monkeypatch,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    output_root = tmp_path / "scratch"

    stage1_decisions_path = (
        tmp_path
        / "stage1-decisions.tsv"
    )

    fresh_manifest_path = (
        tmp_path
        / "fresh-manifest.tsv"
    )

    stage1_decisions_path.write_text(
        "synthetic\n",
        encoding="utf-8",
    )

    fresh_manifest_path.write_text(
        "synthetic\n",
        encoding="utf-8",
    )

    accessions = (
        "GCA_000000001.1",
    )

    decisions = synthetic_decisions(
        module,
        accessions,
    )

    biosamples = (
        module.BioSampleMappingBundle(
            biosample_by_accession={
                accessions[0]:
                    "SAMN1",
            },
            cache_row_count=1,
            fresh_row_count=0,
        )
    )

    bundle = SimpleNamespace(
        historical_candidates=(
            SimpleNamespace(
                accession=accessions[0]
            ),
        ),
        fresh_candidates=(),
        batches=(),
        historical_membership_sha256=(
            decisions.all_membership_sha256
        ),
        fresh_membership_sha256=(
            module.accession_membership_sha256(
                ()
            )
        ),
        combined_membership_sha256=(
            decisions.all_membership_sha256
        ),
        input_evidence_rows=(),
    )

    def fail_fingerprint(
        **_,
    ):
        raise RuntimeError(
            "synthetic fingerprint failure"
        )

    monkeypatch.setattr(
        module,
        "fingerprint_population",
        fail_fingerprint,
    )

    expected_commit = "b" * 40

    with pytest.raises(
        RuntimeError,
        match="synthetic fingerprint failure",
    ):
        module.execute_to_scratch(
            repo=repo,
            expected_commit=expected_commit,
            output_root=output_root,
            stage1=stage1,
            bundle=bundle,
            decisions=decisions,
            biosamples=biosamples,
            frozen_repo_sha256={},
            stage1_decisions_path=(
                stage1_decisions_path
            ),
            fresh_manifest_path=(
                fresh_manifest_path
            ),
        )

    partial = (
        output_root
        / (
            "."
            + expected_commit
            + ".partial"
        )
    )

    assert partial.is_dir()

    assert (
        partial
        / "stage2-predecision-provenance.json"
    ).is_file()

    assert not (
        output_root
        / expected_commit
    ).exists()


def make_sequence_batch(
    tmp_path,
    *,
    stage1,
):
    accession = (
        "GCA_000000001.1"
    )

    component = (
        "CP000001.1"
    )

    sequence = (
        "AACCGGTT"
    )

    batch = (
        tmp_path
        / "batch-001"
    )

    package_relative = (
        Path("ncbi_dataset")
        / "data"
        / accession
        / f"{accession}_genomic.fna"
    )

    fasta = (
        batch
        / package_relative
    )

    fasta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fasta.write_text(
        f">{component}\n{sequence}\n",
        encoding="ascii",
    )

    fasta_sha = hashlib.sha256(
        fasta.read_bytes()
    ).hexdigest()

    candidate_audit = (
        batch
        / "candidate-sequence-audit.tsv"
    )

    candidate_audit.write_text(
        "synthetic\n",
        encoding="utf-8",
    )

    component_audit = (
        batch
        / "component-sequence-audit.tsv"
    )

    sequence_sha = hashlib.sha256(
        sequence.encode(
            "ascii"
        )
    ).hexdigest()

    write_tsv(
        component_audit,
        (
            "canonical_genbank_assembly_accession",
            "component_genbank_accession",
            "length",
            "topology",
            "ambiguous_base_count",
            "ambiguous_symbols",
            "sequence_sha256",
        ),
        (
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "component_genbank_accession":
                    component,
                "length":
                    str(
                        len(
                            sequence
                        )
                    ),
                "topology":
                    "linear",
                "ambiguous_base_count":
                    "0",
                "ambiguous_symbols":
                    "none",
                "sequence_sha256":
                    sequence_sha,
            },
        ),
    )

    package_manifest = (
        batch
        / "package-files.tsv"
    )

    write_tsv(
        package_manifest,
        (
            "path",
            "size_bytes",
            "sha256",
        ),
        (
            {
                "path":
                    str(
                        package_relative
                    ),
                "size_bytes":
                    str(
                        fasta.stat().st_size
                    ),
                "sha256":
                    fasta_sha,
            },
        ),
    )

    candidate = CandidateAudit(
        accession=accession,
        audit_path=candidate_audit,
        fasta_file=fasta.name,
        fasta_sha256=fasta_sha,
        primary_assembly_records=1,
    )

    component_index = (
        __import__(
            "bacselect.source_truth_execution",
            fromlist=[
                "load_component_index",
            ],
        ).load_component_index(
            component_audit,
            accessions=(
                accession,
            ),
        )
    )

    package_index = (
        __import__(
            "bacselect.source_truth_execution",
            fromlist=[
                "load_package_manifest",
            ],
        ).load_package_manifest(
            package_manifest
        )
    )

    source_sha = (
        source_evidence_sha256(
            candidate,
            component_index[
                accession
            ],
            package_index,
        )
    )

    spec = stage1.BatchSpec(
        source_group="synthetic",
        batch="batch-001",
        candidate_audit=candidate_audit,
        component_audit=component_audit,
        package_manifest=package_manifest,
        candidates=(
            candidate,
        ),
    )

    bundle = SimpleNamespace(
        historical_candidates=(
            candidate,
        ),
        fresh_candidates=(),
        batches=(
            spec,
        ),
        historical_membership_sha256=(
            __import__(
                "bacselect.source_truth_execution",
                fromlist=[
                    "accession_membership_sha256",
                ],
            ).accession_membership_sha256(
                (
                    accession,
                )
            )
        ),
        fresh_membership_sha256=(
            __import__(
                "bacselect.source_truth_execution",
                fromlist=[
                    "accession_membership_sha256",
                ],
            ).accession_membership_sha256(
                ()
            )
        ),
        combined_membership_sha256=(
            __import__(
                "bacselect.source_truth_execution",
                fromlist=[
                    "accession_membership_sha256",
                ],
            ).accession_membership_sha256(
                (
                    accession,
                )
            )
        ),
        input_evidence_rows=(),
    )

    return (
        accession,
        source_sha,
        bundle,
    )


def test_fingerprint_population_integrates_frozen_batch_loader(
    tmp_path,
):
    module = load_wrapper()
    stage1 = module.load_stage1_wrapper(
        REPO
    )

    (
        accession,
        source_sha,
        bundle,
    ) = make_sequence_batch(
        tmp_path,
        stage1=stage1,
    )

    decisions = (
        module.Stage1DecisionBundle(
            all_accessions=(
                accession,
            ),
            suitable_source_sha256={
                accession:
                    source_sha,
            },
            all_membership_sha256=(
                module.accession_membership_sha256(
                    (
                        accession,
                    )
                )
            ),
            suitable_membership_sha256=(
                module.accession_membership_sha256(
                    (
                        accession,
                    )
                )
            ),
            status_counts={
                "SUITABLE":
                    1,
            },
        )
    )

    biosamples = (
        module.BioSampleMappingBundle(
            biosample_by_accession={
                accession:
                    "SAMN1",
            },
            cache_row_count=1,
            fresh_row_count=0,
        )
    )

    observed = (
        module.fingerprint_population(
            bundle=bundle,
            decisions=decisions,
            biosamples=biosamples,
        )
    )

    assert len(
        observed
    ) == 1

    assert observed[
        0
    ].accession == accession

    assert observed[
        0
    ].source_evidence_sha256 == source_sha

    assert len(
        observed[
            0
        ].assembly_fingerprint
    ) == 64



def test_group_reporting_cannot_override_frozen_reconciliation():
    module = load_wrapper()

    records = (
        VerifiedBioSampleFingerprint(
            accession="GCA_000000001.1",
            biosample="SAMN1",
            source_evidence_sha256="1" * 64,
            assembly_fingerprint="a" * 64,
        ),
        VerifiedBioSampleFingerprint(
            accession="GCA_000000002.1",
            biosample="SAMN1",
            source_evidence_sha256="2" * 64,
            assembly_fingerprint="a" * 64,
        ),
    )

    decisions = (
        module.reconcile_verified_candidates(
            records
        )
    )

    rows, counts = (
        module.build_group_rows(
            records,
            decisions,
        )
    )

    assert rows == (
        {
            "biosample":
                "SAMN1",
            "member_count":
                2,
            "distinct_fingerprint_count":
                1,
            "group_class":
                "IDENTICAL_REPEAT",
        },
    )

    assert counts[
        "identical_repeated"
    ] == 1
