from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from bacselect.source_truth import (
    sha256_text,
)


WRAPPER = (
    Path(__file__).resolve().parents[1]
    / "validation"
    / "selector-v1"
    / "run_source_truth_execution.py"
)


def load_wrapper():
    spec = importlib.util.spec_from_file_location(
        "run_source_truth_execution",
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
            fieldnames=list(fields),
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def write_fasta(
    path: Path,
    accession: str,
    component: str,
    sequence: str,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        f">{component} synthetic\n{sequence}\n",
        encoding="ascii",
    )

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def make_batch(
    root: Path,
    *,
    batch: str,
    accession: str,
    sequence: str = "AACCGG",
    state: str = "eligible",
    package_name: str = "package-files.tsv",
):
    module = load_wrapper()

    batch_dir = (
        root
        / batch
    )

    batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    component = (
        "CP"
        + accession[
            4:
        ].replace(
            ".",
            ""
        )
        + ".1"
    )

    relative_fasta = (
        f"ncbi_dataset/data/"
        f"{accession}/"
        f"{accession}_genomic.fna"
    )

    fasta_path = (
        batch_dir
        / "package"
        / relative_fasta
    )

    if state == "eligible":
        fasta_sha = write_fasta(
            fasta_path,
            accession,
            component,
            sequence,
        )

        fasta_size = (
            fasta_path.stat().st_size
        )

        fasta_file = relative_fasta
        primary_records = "1"
    else:
        fasta_sha = ""
        fasta_size = 0
        fasta_file = ""
        primary_records = "0"

    candidate_path = (
        batch_dir
        / "candidate-sequence-audit.tsv"
    )

    candidate_fields = (
        "canonical_genbank_assembly_accession",
        "sequence_eligibility",
        "fasta_file",
        "fasta_sha256",
        "primary_assembly_records",
    )

    write_tsv(
        candidate_path,
        candidate_fields,
        [
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "sequence_eligibility":
                    state,
                "fasta_file":
                    fasta_file,
                "fasta_sha256":
                    fasta_sha,
                "primary_assembly_records":
                    primary_records,
            }
        ],
    )

    component_path = (
        batch_dir
        / "component-sequence-audit.tsv"
    )

    component_rows = []

    if state == "eligible":
        component_rows.append(
            {
                "canonical_genbank_assembly_accession":
                    accession,
                "component_genbank_accession":
                    component,
                "length":
                    str(
                        len(sequence)
                    ),
                "topology":
                    "linear",
                "ambiguous_base_count":
                    "0",
                "ambiguous_symbols":
                    "",
                "sequence_sha256":
                    sha256_text(
                        sequence
                    ),
            }
        )

    write_tsv(
        component_path,
        module.COMPONENT_FIELDS
        if hasattr(
            module,
            "COMPONENT_FIELDS",
        )
        else (
            "canonical_genbank_assembly_accession",
            "component_genbank_accession",
            "length",
            "topology",
            "ambiguous_base_count",
            "ambiguous_symbols",
            "sequence_sha256",
        ),
        component_rows,
    )

    package_path = (
        batch_dir
        / package_name
    )

    package_rows = []

    if state == "eligible":
        package_rows.append(
            {
                "path":
                    relative_fasta,
                "size_bytes":
                    str(
                        fasta_size
                    ),
                "sha256":
                    fasta_sha,
            }
        )
    else:
        package_rows.append(
            {
                "path":
                    "placeholder.txt",
                "size_bytes":
                    "0",
                "sha256":
                    "0" * 64,
            }
        )

    write_tsv(
        package_path,
        (
            "path",
            "size_bytes",
            "sha256",
        ),
        package_rows,
    )

    (
        batch_dir
        / "batch-summary.json"
    ).write_text(
        json.dumps(
            {
                "candidate_sequence_audit_sha256":
                    module.sha256_file(
                        candidate_path
                    ),
                "component_sequence_audit_sha256":
                    module.sha256_file(
                        component_path
                    ),
                "package_files_sha256":
                    module.sha256_file(
                        package_path
                    ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        candidate_path,
        component_path,
        package_path,
    )


def test_wrapper_import_has_no_production_access():
    module = load_wrapper()

    assert (
        module.EXPECTED_STAGE1_TOTAL
        == 68480
    )


def test_required_project_finch_roles_exact():
    module = load_wrapper()

    assert (
        module.REQUIRED_PROJECT_FINCH_ROLES
        == {
            "source_truth_worker",
            "source_truth_aggregate",
            "source_truth_adjudicator",
            "source_truth_worker_test",
            "source_truth_aggregate_test",
            "source_truth_adjudicator_test",
            "source_truth_containment_driver",
            "source_truth_containment_driver_test",
            "source_truth_production_wrapper",
        }
    )


def test_project_finch_reference_verification_uses_frozen_blob(
    tmp_path,
):
    module = load_wrapper()

    bacselect = (
        tmp_path
        / "bacselect"
    )

    finch = (
        tmp_path
        / "project-finch"
    )

    (
        bacselect
        / "validation"
        / "selector-v1"
    ).mkdir(
        parents=True
    )

    finch.mkdir()

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "init",
            "-q",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "config",
            "user.email",
            "test@example.invalid",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "config",
            "user.name",
            "BacSelect Test",
        ],
        check=True,
    )

    source = (
        finch
        / "worker.py"
    )

    source.write_text(
        "print('frozen')\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "add",
            "worker.py",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )

    commit = subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    sha = hashlib.sha256(
        source.read_bytes()
    ).hexdigest()

    inherited = (
        bacselect
        / module.INHERITED_REFERENCES_RELATIVE
    )

    transitive = (
        bacselect
        / module.TRANSITIVE_REFERENCES_RELATIVE
    )

    write_tsv(
        inherited,
        module.REFERENCE_FIELDS,
        [
            {
                "role":
                    "source_truth_worker",
                "project_finch_commit":
                    commit,
                "path":
                    "worker.py",
                "sha256":
                    sha,
            }
        ],
    )

    write_tsv(
        transitive,
        module.REFERENCE_FIELDS,
        [],
    )

    original_inherited = (
        module.EXPECTED_INHERITED_REFERENCES_SHA256
    )

    original_transitive = (
        module.EXPECTED_TRANSITIVE_REFERENCES_SHA256
    )

    module.EXPECTED_INHERITED_REFERENCES_SHA256 = (
        module.sha256_file(
            inherited
        )
    )

    module.EXPECTED_TRANSITIVE_REFERENCES_SHA256 = (
        module.sha256_file(
            transitive
        )
    )

    try:
        verified = (
            module.verify_project_finch_references(
                bacselect,
                finch,
                required_roles=frozenset(
                    {
                        "source_truth_worker",
                    }
                ),
            )
        )
    finally:
        module.EXPECTED_INHERITED_REFERENCES_SHA256 = (
            original_inherited
        )
        module.EXPECTED_TRANSITIVE_REFERENCES_SHA256 = (
            original_transitive
        )

    assert verified == (
        {
            "role":
                "source_truth_worker",
            "project_finch_commit":
                commit,
            "path":
                "worker.py",
            "sha256":
                sha,
        },
    )


def test_project_finch_reference_mismatch_fails_closed(
    tmp_path,
):
    module = load_wrapper()

    bacselect = tmp_path / "b"
    finch = tmp_path / "f"

    (
        bacselect
        / "validation"
        / "selector-v1"
    ).mkdir(
        parents=True
    )

    finch.mkdir()

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "init",
            "-q",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "config",
            "user.email",
            "test@example.invalid",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "config",
            "user.name",
            "BacSelect Test",
        ],
        check=True,
    )

    (finch / "x.py").write_text(
        "x = 1\n",
        encoding="utf-8",
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "add",
            "x.py",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "commit",
            "-q",
            "-m",
            "fixture",
        ],
        check=True,
    )

    commit = subprocess.run(
        [
            "git",
            "-C",
            str(finch),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    inherited = (
        bacselect
        / module.INHERITED_REFERENCES_RELATIVE
    )

    transitive = (
        bacselect
        / module.TRANSITIVE_REFERENCES_RELATIVE
    )

    write_tsv(
        inherited,
        module.REFERENCE_FIELDS,
        [
            {
                "role":
                    "source_truth_worker",
                "project_finch_commit":
                    commit,
                "path":
                    "x.py",
                "sha256":
                    "0" * 64,
            }
        ],
    )

    write_tsv(
        transitive,
        module.REFERENCE_FIELDS,
        [],
    )

    module.EXPECTED_INHERITED_REFERENCES_SHA256 = (
        module.sha256_file(
            inherited
        )
    )

    module.EXPECTED_TRANSITIVE_REFERENCES_SHA256 = (
        module.sha256_file(
            transitive
        )
    )

    with pytest.raises(
        module.ExecutionError,
        match="reference mismatch",
    ):
        module.verify_project_finch_references(
            bacselect,
            finch,
            required_roles=frozenset(
                {
                    "source_truth_worker",
                }
            ),
        )


def synthetic_cache_handoff(
    tmp_path,
):
    module = load_wrapper()

    accessions_path = (
        tmp_path
        / "cache-reuse-accessions.txt"
    )

    manifest_path = (
        tmp_path
        / "cache-reuse-manifest.tsv"
    )

    verification_path = (
        tmp_path
        / "cache-verification.tsv"
    )

    accessions = (
        "GCA_000000001.1",
        "GCA_000000002.1",
    )

    accessions_path.write_text(
        "".join(
            f"{value}\n"
            for value in accessions
        ),
        encoding="utf-8",
    )

    write_tsv(
        manifest_path,
        module.CACHE_MANIFEST_FIELDS,
        [
            {
                "canonical_genbank_assembly_accession":
                    accessions[0],
                "fresh_biosample":
                    "SAMN1",
                "historical_batch":
                    "batch-001",
                "historical_sequence_eligibility":
                    "eligible",
                "historical_exclusion_reasons":
                    "none",
            },
            {
                "canonical_genbank_assembly_accession":
                    accessions[1],
                "fresh_biosample":
                    "SAMN2",
                "historical_batch":
                    "batch-001",
                "historical_sequence_eligibility":
                    "ineligible",
                "historical_exclusion_reasons":
                    "synthetic",
            },
        ],
    )

    write_tsv(
        verification_path,
        module.CACHE_VERIFICATION_FIELDS,
        [
            {
                "batch":
                    "batch-001",
                "canonical_genbank_assembly_accession":
                    accessions[0],
                "package_file_count":
                    "3",
                "accession_package_files_pass":
                    "1",
                "batch_common_provenance_pass":
                    "1",
                "cache_content_verification":
                    "pass",
            },
            {
                "batch":
                    "batch-001",
                "canonical_genbank_assembly_accession":
                    accessions[1],
                "package_file_count":
                    "3",
                "accession_package_files_pass":
                    "1",
                "batch_common_provenance_pass":
                    "1",
                "cache_content_verification":
                    "pass",
            },
            {
                "batch":
                    "batch-001",
                "canonical_genbank_assembly_accession":
                    "GCA_000000003.1",
                "package_file_count":
                    "3",
                "accession_package_files_pass":
                    "1",
                "batch_common_provenance_pass":
                    "1",
                "cache_content_verification":
                    "pass",
            },
        ],
    )

    evidence = {
        "cache_reuse_accessions_sha256":
            module.sha256_file(
                accessions_path
            ),
        "cache_reuse_manifest_sha256":
            module.sha256_file(
                manifest_path
            ),
        "cache_verification_sha256":
            module.sha256_file(
                verification_path
            ),
    }

    contract = module.PopulationContract(
        historical_audit_rows=3,
        cache_reuse=2,
        historical_eligible=1,
        historical_ineligible=1,
        cache_verification_rows=3,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=2,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    return (
        accessions_path,
        manifest_path,
        verification_path,
        evidence,
        contract,
    )


def test_cache_handoff_uses_subset_not_full_verification(
    tmp_path,
):
    module = load_wrapper()

    (
        accessions,
        manifest,
        verification,
        evidence,
        contract,
    ) = synthetic_cache_handoff(
        tmp_path
    )

    eligible, ineligible, _ = (
        module.load_cache_handoff(
            cache_accessions_path=accessions,
            cache_manifest_path=manifest,
            cache_verification_path=verification,
            acquisition_evidence=evidence,
            contract=contract,
        )
    )

    assert eligible == {
        "GCA_000000001.1":
            "batch-001",
    }

    assert ineligible == {
        "GCA_000000002.1":
            "batch-001",
    }

    assert (
        "GCA_000000003.1"
        not in eligible
    )


def test_cache_handoff_nonpass_fails_closed(
    tmp_path,
):
    module = load_wrapper()

    (
        accessions,
        manifest,
        verification,
        evidence,
        contract,
    ) = synthetic_cache_handoff(
        tmp_path
    )

    fields, rows = module.read_tsv(
        verification
    )

    rows[0][
        "cache_content_verification"
    ] = "fail"

    write_tsv(
        verification,
        fields,
        rows,
    )

    evidence[
        "cache_verification_sha256"
    ] = module.sha256_file(
        verification
    )

    with pytest.raises(
        module.ExecutionError,
        match="non-pass",
    ):
        module.load_cache_handoff(
            cache_accessions_path=accessions,
            cache_manifest_path=manifest,
            cache_verification_path=verification,
            acquisition_evidence=evidence,
            contract=contract,
        )


def make_historical_fixture(
    tmp_path,
):
    module = load_wrapper()

    root = (
        tmp_path
        / "historical"
    )

    batch = (
        root
        / "batch-001"
    )

    batch.mkdir(
        parents=True
    )

    selected = "GCA_000000001.1"
    ineligible = "GCA_000000002.1"
    extra = "GCA_000000003.1"

    selected_relative = (
        f"ncbi_dataset/data/{selected}/{selected}_genomic.fna"
    )

    extra_relative = (
        f"ncbi_dataset/data/{extra}/{extra}_genomic.fna"
    )

    selected_fasta = (
        batch
        / "package"
        / selected_relative
    )

    extra_fasta = (
        batch
        / "package"
        / extra_relative
    )

    selected_sha = write_fasta(
        selected_fasta,
        selected,
        "CP000001.1",
        "AACCGG",
    )

    extra_sha = write_fasta(
        extra_fasta,
        extra,
        "CP000003.1",
        "TTGGCC",
    )

    write_tsv(
        batch
        / "candidate-sequence-audit.tsv",
        (
            "canonical_genbank_assembly_accession",
            "sequence_eligibility",
            "fasta_file",
            "fasta_sha256",
            "primary_assembly_records",
        ),
        [
            {
                "canonical_genbank_assembly_accession":
                    selected,
                "sequence_eligibility":
                    "eligible",
                "fasta_file":
                    selected_relative,
                "fasta_sha256":
                    selected_sha,
                "primary_assembly_records":
                    "1",
            },
            {
                "canonical_genbank_assembly_accession":
                    ineligible,
                "sequence_eligibility":
                    "ineligible",
                "fasta_file":
                    "",
                "fasta_sha256":
                    "",
                "primary_assembly_records":
                    "0",
            },
            {
                "canonical_genbank_assembly_accession":
                    extra,
                "sequence_eligibility":
                    "eligible",
                "fasta_file":
                    extra_relative,
                "fasta_sha256":
                    extra_sha,
                "primary_assembly_records":
                    "1",
            },
        ],
    )

    write_tsv(
        batch
        / "component-sequence-audit.tsv",
        (
            "canonical_genbank_assembly_accession",
            "component_genbank_accession",
            "length",
            "topology",
            "ambiguous_base_count",
            "ambiguous_symbols",
            "sequence_sha256",
        ),
        [
            {
                "canonical_genbank_assembly_accession":
                    selected,
                "component_genbank_accession":
                    "CP000001.1",
                "length":
                    "6",
                "topology":
                    "linear",
                "ambiguous_base_count":
                    "0",
                "ambiguous_symbols":
                    "",
                "sequence_sha256":
                    sha256_text(
                        "AACCGG"
                    ),
            },
            {
                "canonical_genbank_assembly_accession":
                    extra,
                "component_genbank_accession":
                    "CP000003.1",
                "length":
                    "6",
                "topology":
                    "linear",
                "ambiguous_base_count":
                    "0",
                "ambiguous_symbols":
                    "",
                "sequence_sha256":
                    sha256_text(
                        "TTGGCC"
                    ),
            },
        ],
    )

    write_tsv(
        batch
        / "package-files.tsv",
        (
            "path",
            "size_bytes",
            "sha256",
        ),
        [
            {
                "path":
                    selected_relative,
                "size_bytes":
                    str(
                        selected_fasta.stat().st_size
                    ),
                "sha256":
                    selected_sha,
            },
            {
                "path":
                    extra_relative,
                "size_bytes":
                    str(
                        extra_fasta.stat().st_size
                    ),
                "sha256":
                    extra_sha,
            },
        ],
    )

    candidate_path = (
        batch
        / "candidate-sequence-audit.tsv"
    )

    component_path = (
        batch
        / "component-sequence-audit.tsv"
    )

    package_path = (
        batch
        / "package-files.tsv"
    )

    (
        batch
        / "batch-summary.json"
    ).write_text(
        json.dumps(
            {
                "candidate_sequence_audit_sha256":
                    module.sha256_file(
                        candidate_path
                    ),
                "component_sequence_audit_sha256":
                    module.sha256_file(
                        component_path
                    ),
                "package_files_sha256":
                    module.sha256_file(
                        package_path
                    ),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return root


def test_historical_population_does_not_promote_nonreuse_eligible(
    tmp_path,
):
    module = load_wrapper()

    root = make_historical_fixture(
        tmp_path
    )

    contract = module.PopulationContract(
        historical_audit_rows=3,
        cache_reuse=2,
        historical_eligible=1,
        historical_ineligible=1,
        cache_verification_rows=3,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=2,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    candidate_path = (
        root
        / "batch-001"
        / "candidate-sequence-audit.tsv"
    )

    candidates, specs, _ = (
        module.build_historical_population(
            historical_root=root,
            eligible_batches={
                "GCA_000000001.1":
                    "batch-001",
            },
            ineligible_batches={
                "GCA_000000002.1":
                    "batch-001",
            },
            candidate_audit_sha256_by_batch={
                "batch-001":
                    module.sha256_file(
                        candidate_path
                    ),
            },
            contract=contract,
            expected_batch_count=1,
        )
    )

    assert [
        item.accession
        for item in candidates
    ] == [
        "GCA_000000001.1",
    ]

    assert len(
        specs
    ) == 1


def make_fresh_fixture(
    tmp_path,
):
    root = (
        tmp_path
        / "fresh"
    )

    make_batch(
        root,
        batch="batch-001",
        accession="GCA_000000004.1",
        sequence="ACGTAC",
    )

    return root


def test_fresh_population_reconstructs_exact_eligible_set(
    tmp_path,
):
    module = load_wrapper()

    root = make_fresh_fixture(
        tmp_path
    )

    recovery = (
        tmp_path
        / "recovery"
    )

    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=3,
        cache_reuse=2,
        historical_eligible=1,
        historical_ineligible=1,
        cache_verification_rows=3,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=2,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    candidates, specs, _ = (
        module.build_fresh_population(
            fresh_root=root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )
    )

    assert [
        item.accession
        for item in candidates
    ] == [
        "GCA_000000004.1",
    ]

    assert len(
        specs
    ) == 1


def test_population_bundle_rejects_historical_fresh_overlap(
    tmp_path,
):
    module = load_wrapper()

    root = make_fresh_fixture(
        tmp_path
    )

    recovery = tmp_path / "recovery"
    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=1,
        cache_reuse=1,
        historical_eligible=1,
        historical_ineligible=0,
        cache_verification_rows=1,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=2,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    fresh, specs, evidence = (
        module.build_fresh_population(
            fresh_root=root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )
    )

    with pytest.raises(
        module.ExecutionError,
        match="overlap",
    ):
        module.build_population_bundle(
            historical_candidates=fresh,
            fresh_candidates=fresh,
            historical_specs=specs,
            fresh_specs=specs,
            input_evidence_rows=evidence,
            expected_total=2,
        )


def test_output_root_inside_repo_rejected(
    tmp_path,
):
    module = load_wrapper()

    repo = tmp_path / "repo"
    repo.mkdir()

    with pytest.raises(
        module.ExecutionError,
        match="outside Git repository",
    ):
        module.ensure_output_root_outside_repo(
            repo,
            repo / "scratch",
        )


def test_preclassification_provenance_precedes_classification(
    tmp_path,
    monkeypatch,
):
    module = load_wrapper()

    fresh_root = make_fresh_fixture(
        tmp_path
    )

    recovery = tmp_path / "recovery"
    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=0,
        cache_reuse=0,
        historical_eligible=0,
        historical_ineligible=0,
        cache_verification_rows=0,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=1,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    fresh, specs, evidence = (
        module.build_fresh_population(
            fresh_root=fresh_root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )
    )

    bundle = (
        module.build_population_bundle(
            historical_candidates=(),
            fresh_candidates=fresh,
            historical_specs=(),
            fresh_specs=specs,
            input_evidence_rows=evidence,
            expected_total=1,
        )
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    output_root = (
        tmp_path
        / "outside"
    )

    original = (
        module.evaluate_population
    )

    observed = {
        "preclassification_exists":
            False,
    }

    def wrapped(
        supplied_bundle,
    ):
        partial = (
            output_root
            / (
                "."
                + "a" * 40
                + ".partial"
            )
            / "stage1-preclassification-provenance.json"
        )

        observed[
            "preclassification_exists"
        ] = partial.is_file()

        return original(
            supplied_bundle
        )

    monkeypatch.setattr(
        module,
        "evaluate_population",
        wrapped,
    )

    final_dir = (
        module.execute_to_scratch(
            repo=repo,
            expected_commit="a" * 40,
            output_root=output_root,
            bundle=bundle,
            frozen_repo_sha256={},
            project_finch_references=(),
            acquisition_evidence={
                "cache_reuse_accessions_sha256":
                    "1" * 64,
                "cache_reuse_manifest_sha256":
                    "2" * 64,
                "cache_verification_sha256":
                    "3" * 64,
            },
        )
    )

    assert (
        observed[
            "preclassification_exists"
        ]
        is True
    )

    assert final_dir.is_dir()


def test_end_to_end_synthetic_outputs_are_deterministic_and_blinded(
    tmp_path,
):
    module = load_wrapper()

    fresh_root = make_fresh_fixture(
        tmp_path
    )

    recovery = tmp_path / "recovery"
    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=0,
        cache_reuse=0,
        historical_eligible=0,
        historical_ineligible=0,
        cache_verification_rows=0,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=1,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    fresh, specs, evidence = (
        module.build_fresh_population(
            fresh_root=fresh_root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )
    )

    bundle = (
        module.build_population_bundle(
            historical_candidates=(),
            fresh_candidates=fresh,
            historical_specs=(),
            fresh_specs=specs,
            input_evidence_rows=evidence,
            expected_total=1,
        )
    )

    repo = tmp_path / "repo"
    repo.mkdir()

    final_dir = (
        module.execute_to_scratch(
            repo=repo,
            expected_commit="b" * 40,
            output_root=(
                tmp_path
                / "scratch"
            ),
            bundle=bundle,
            frozen_repo_sha256={},
            project_finch_references=(),
            acquisition_evidence={
                "cache_reuse_accessions_sha256":
                    "1" * 64,
                "cache_reuse_manifest_sha256":
                    "2" * 64,
                "cache_verification_sha256":
                    "3" * 64,
            },
        )
    )

    expected_files = {
        "stage1-input-evidence-manifest.tsv",
        "stage1-preclassification-provenance.json",
        "stage1-source-truth-decisions.tsv",
        "stage1-source-truth-relations.tsv",
        "stage1-execution-provenance.json",
        "stage1-aggregate-summary.json",
        "stage1-content-manifest.tsv",
    }

    assert {
        path.name
        for path in final_dir.iterdir()
    } == expected_files

    decision_text = (
        final_dir
        / "stage1-source-truth-decisions.tsv"
    ).read_text(
        encoding="utf-8",
    )

    assert (
        "GCA_000000004.1"
        in decision_text
    )

    summary = json.loads(
        (
            final_dir
            / "stage1-aggregate-summary.json"
        ).read_text(
            encoding="utf-8",
        )
    )

    assert (
        summary[
            "candidate_count"
        ]
        == 1
    )

    assert (
        sum(
            summary[
                "status_counts"
            ].values()
        )
        == 1
    )

    assert (
        summary[
            "stage2_repeated_biosample_generated"
        ]
        is False
    )

    assert (
        summary[
            "taxonomy_resolution_generated"
        ]
        is False
    )

    assert (
        summary[
            "selector_outcomes_calculated"
        ]
        is False
    )

    all_text = "\n".join(
        path.read_text(
            encoding="utf-8",
        )
        for path in final_dir.iterdir()
        if path.suffix in {
            ".tsv",
            ".json",
        }
    )

    assert "SAMN" not in all_text
    assert "species_taxid" not in all_text
    assert "OPS" not in all_text
    assert "SR" not in all_text


def test_historical_audit_manifest_binds_candidate_hashes(
    tmp_path,
):
    module = load_wrapper()

    path = (
        tmp_path
        / "historical-candidate-audits-sha256.tsv"
    )

    write_tsv(
        path,
        module.HISTORICAL_AUDIT_MANIFEST_FIELDS,
        [
            {
                "batch":
                    "batch-001",
                "candidate_sequence_audit_sha256":
                    "1" * 64,
            }
        ],
    )

    values, evidence = (
        module.load_historical_candidate_audit_manifest(
            path,
            expected_sha256=(
                module.sha256_file(
                    path
                )
            ),
            expected_count=1,
        )
    )

    assert values == {
        "batch-001":
            "1" * 64,
    }

    assert (
        evidence[
            "file_role"
        ]
        == "historical_candidate_audit_hash_manifest"
    )


def test_historical_population_rejects_candidate_audit_drift(
    tmp_path,
):
    module = load_wrapper()

    root = make_historical_fixture(
        tmp_path
    )

    candidate_path = (
        root
        / "batch-001"
        / "candidate-sequence-audit.tsv"
    )

    frozen_sha = module.sha256_file(
        candidate_path
    )

    candidate_path.write_text(
        candidate_path.read_text(
            encoding="utf-8"
        )
        + "\n",
        encoding="utf-8",
    )

    contract = module.PopulationContract(
        historical_audit_rows=3,
        cache_reuse=2,
        historical_eligible=1,
        historical_ineligible=1,
        cache_verification_rows=3,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=2,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    with pytest.raises(
        module.ExecutionError,
        match="historical batch-001 candidate audit SHA256 mismatch",
    ):
        module.build_historical_population(
            historical_root=root,
            eligible_batches={
                "GCA_000000001.1":
                    "batch-001",
            },
            ineligible_batches={
                "GCA_000000002.1":
                    "batch-001",
            },
            candidate_audit_sha256_by_batch={
                "batch-001":
                    frozen_sha,
            },
            contract=contract,
            expected_batch_count=1,
        )


def test_fresh_population_rejects_batch_summary_hash_drift(
    tmp_path,
):
    module = load_wrapper()

    root = make_fresh_fixture(
        tmp_path
    )

    component_path = (
        root
        / "batch-001"
        / "component-sequence-audit.tsv"
    )

    component_path.write_text(
        component_path.read_text(
            encoding="utf-8"
        )
        + "\n",
        encoding="utf-8",
    )

    recovery = (
        tmp_path
        / "recovery"
    )

    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=0,
        cache_reuse=0,
        historical_eligible=0,
        historical_ineligible=0,
        cache_verification_rows=0,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=1,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    with pytest.raises(
        module.ExecutionError,
        match="fresh batch-001 component audit SHA256 mismatch",
    ):
        module.build_fresh_population(
            fresh_root=root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )


def test_production_contract_is_exact():
    module = load_wrapper()

    contract = (
        module.PRODUCTION_CONTRACT
    )

    assert (
        contract.historical_eligible
        == 55145
    )

    assert (
        contract.fresh_eligible
        == 13335
    )

    assert (
        contract.total
        == 68480
    )

    assert len(
        contract.ordinary_fresh_batches
    ) == 29

    assert (
        contract.recovery_fresh_batches
        == (
            "batch-024",
            "batch-028",
        )
    )


def test_recovery_001_contract_is_exact():
    module = load_wrapper()

    assert (
        module.RECOVERY_001_CLARIFICATION_RELATIVE
        == Path(
            "validation/selector-v1/"
            "stage1-source-truth-recovery-001.md"
        )
    )

    assert (
        module.EXPECTED_EXECUTION_IMPLEMENTATION_SHA256
        == "83b8ec7fce774c0b68cb2af982aef13904c6b64b3ee695512c578f98e5de9b92"
    )

    assert (
        module.EXPECTED_EXECUTION_TEST_SHA256
        == "314b417ee05e2293ad37268963d9bdddb5bc58c9d6d6bc102a6cebe6ec926864"
    )

    assert (
        module.EXPECTED_RECOVERY_001_CLARIFICATION_SHA256
        == "a5c836a2b1e7d98b54d6264ad51c600acbbdc222706119b228bf6398fb8fecd0"
    )

    assert (
        module.FROZEN_REPO_FILES[
            module.RECOVERY_001_CLARIFICATION_RELATIVE
        ]
        == module.EXPECTED_RECOVERY_001_CLARIFICATION_SHA256
    )

    assert (
        module.RECOVERY_001_FAILED_ATTEMPT_COMMIT
        == "25e44f29072d951172784364e0b16c291ecb2331"
    )

    assert (
        module.RECOVERY_001_IMPLEMENTATION_COMMIT
        == "fa26abf4f69d061a1ff1917788e33e8b01168229"
    )

    assert (
        module.EXPECTED_HISTORICAL_ELIGIBLE
        == 55145
    )

    assert (
        module.EXPECTED_RECOVERY_001_HISTORICAL_MEMBERSHIP_SHA256
        == "ed659ac6f9cba972a819ea3fb291d738ddeaf55842feb787a7c8ebbcf467952c"
    )

    assert (
        module.EXPECTED_FRESH_ELIGIBLE
        == 13335
    )

    assert (
        module.EXPECTED_RECOVERY_001_FRESH_MEMBERSHIP_SHA256
        == "75a8312f090ffef9b2b0c0a41311c02c059a4f353491208c08d3cd64c8256e22"
    )

    assert (
        module.EXPECTED_STAGE1_TOTAL
        == 68480
    )

    assert (
        module.EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256
        == "810c584d578bad678e3a9ef3131e13777444961b906a57f5b2cbdcafd691e324"
    )


def test_recovery_001_membership_checkpoint_fails_closed(
    tmp_path,
    monkeypatch,
):
    module = load_wrapper()

    fresh_root = make_fresh_fixture(
        tmp_path
    )

    recovery = (
        tmp_path
        / "recovery"
    )

    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=0,
        cache_reuse=0,
        historical_eligible=0,
        historical_ineligible=0,
        cache_verification_rows=0,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=1,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    fresh, specs, evidence = (
        module.build_fresh_population(
            fresh_root=fresh_root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )
    )

    bundle = (
        module.build_population_bundle(
            historical_candidates=(),
            fresh_candidates=fresh,
            historical_specs=(),
            fresh_specs=specs,
            input_evidence_rows=evidence,
            expected_total=1,
        )
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_HISTORICAL_ELIGIBLE",
        0,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_FRESH_ELIGIBLE",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_STAGE1_TOTAL",
        1,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_RECOVERY_001_HISTORICAL_MEMBERSHIP_SHA256",
        bundle.historical_membership_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_RECOVERY_001_FRESH_MEMBERSHIP_SHA256",
        bundle.fresh_membership_sha256,
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256",
        bundle.combined_membership_sha256,
    )

    module.verify_recovery_001_membership(
        bundle
    )

    monkeypatch.setattr(
        module,
        "EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256",
        "0" * 64,
    )

    with pytest.raises(
        module.ExecutionError,
        match=(
            "combined Stage 1 recovery membership "
            "SHA256 mismatch"
        ),
    ):
        module.verify_recovery_001_membership(
            bundle
        )


def test_recovery_001_checkpoint_precedes_scratch_execution():
    import ast

    source = WRAPPER.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    main = next(
        node
        for node in tree.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "main"
        )
    )

    calls = {}

    for node in ast.walk(
        main
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        if node.func.id in {
            "verify_recovery_001_membership",
            "execute_to_scratch",
        }:
            calls[
                node.func.id
            ] = node.lineno

    assert (
        "verify_recovery_001_membership"
        in calls
    )

    assert (
        "execute_to_scratch"
        in calls
    )

    assert (
        calls[
            "verify_recovery_001_membership"
        ]
        < calls[
            "execute_to_scratch"
        ]
    )


def test_preclassification_records_recovery_001(
    tmp_path,
):
    module = load_wrapper()

    fresh_root = make_fresh_fixture(
        tmp_path
    )

    recovery = (
        tmp_path
        / "recovery"
    )

    recovery.mkdir()

    contract = module.PopulationContract(
        historical_audit_rows=0,
        cache_reuse=0,
        historical_eligible=0,
        historical_ineligible=0,
        cache_verification_rows=0,
        fresh_audit_rows=1,
        fresh_eligible=1,
        fresh_ineligible=0,
        total=1,
        ordinary_fresh_batches=(
            "batch-001",
        ),
        recovery_fresh_batches=(),
    )

    fresh, specs, evidence = (
        module.build_fresh_population(
            fresh_root=fresh_root,
            recovery_root=recovery,
            contract=contract,
            recovery_expected_sha256=None,
            recovery_summary_sha256=None,
        )
    )

    bundle = (
        module.build_population_bundle(
            historical_candidates=(),
            fresh_candidates=fresh,
            historical_specs=(),
            fresh_specs=specs,
            input_evidence_rows=evidence,
            expected_total=1,
        )
    )

    repo = (
        tmp_path
        / "repo"
    )

    repo.mkdir()

    final_dir = (
        module.execute_to_scratch(
            repo=repo,
            expected_commit="c" * 40,
            output_root=(
                tmp_path
                / "outside"
            ),
            bundle=bundle,
            frozen_repo_sha256={},
            project_finch_references=(),
            acquisition_evidence={
                "cache_reuse_accessions_sha256":
                    "1" * 64,
                "cache_reuse_manifest_sha256":
                    "2" * 64,
                "cache_verification_sha256":
                    "3" * 64,
            },
        )
    )

    payload = json.loads(
        (
            final_dir
            / "stage1-preclassification-provenance.json"
        ).read_text(
            encoding="utf-8"
        )
    )

    recovery_payload = (
        payload[
            "stage1_recovery"
        ]
    )

    assert (
        recovery_payload[
            "identifier"
        ]
        == module.RECOVERY_001_IDENTIFIER
    )

    assert (
        recovery_payload[
            "clarification_sha256"
        ]
        == module.EXPECTED_RECOVERY_001_CLARIFICATION_SHA256
    )

    assert (
        recovery_payload[
            "failed_attempt_bacselect_git_commit"
        ]
        == module.RECOVERY_001_FAILED_ATTEMPT_COMMIT
    )

    assert (
        recovery_payload[
            "recovery_implementation_bacselect_git_commit"
        ]
        == module.RECOVERY_001_IMPLEMENTATION_COMMIT
    )

    checkpoint = (
        recovery_payload[
            "required_membership_checkpoint"
        ]
    )

    assert (
        checkpoint[
            "historical"
        ][
            "sha256"
        ]
        == module.EXPECTED_RECOVERY_001_HISTORICAL_MEMBERSHIP_SHA256
    )

    assert (
        checkpoint[
            "fresh"
        ][
            "sha256"
        ]
        == module.EXPECTED_RECOVERY_001_FRESH_MEMBERSHIP_SHA256
    )

    assert (
        checkpoint[
            "combined"
        ][
            "sha256"
        ]
        == module.EXPECTED_RECOVERY_001_COMBINED_MEMBERSHIP_SHA256
    )

    assert (
        payload[
            "classification_started"
        ]
        is False
    )

    assert (
        payload[
            "selector_outcomes_calculated"
        ]
        is False
    )
