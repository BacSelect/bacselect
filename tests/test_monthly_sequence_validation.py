from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import bacselect.monthly_sequence_validation as module
from bacselect.monthly_sequence_plan import (
    MonthlyFreshAcquisitionTarget,
    NO_VERIFIED_CACHE,
)
from bacselect.monthly_sequence_validation import (
    CANDIDATE_AUDIT_FIELDS,
    COMPONENT_AUDIT_FIELDS,
    PACKAGE_FILE_FIELDS,
    MonthlySequenceValidationError,
    package_file_manifest,
    validate_hydrated_package,
)


ROOT = Path(__file__).resolve().parents[1]

HISTORICAL_WORKER = (
    ROOT
    / "validation"
    / "selector-v1"
    / "fresh_sequence_validation_batch.py"
)

ACCESSION = "GCA_000000001.1"
BIOSAMPLE = "SAMN00000001"
COMPONENT = "CP000001.1"


def target():
    return MonthlyFreshAcquisitionTarget(
        canonical_genbank_assembly_accession=(
            ACCESSION
        ),
        source_biosample=BIOSAMPLE,
        acquisition_reason=NO_VERIFIED_CACHE,
    )


def write_jsonl(
    path: Path,
    rows,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        "".join(
            json.dumps(
                row,
                sort_keys=True,
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def gbff_text(
    sequence: str,
    *,
    topology: str | None = "circular",
):
    topology_token = (
        f" {topology}"
        if topology is not None
        else ""
    )

    return (
        f"LOCUS       {COMPONENT.split('.')[0]}"
        f" {len(sequence)} bp DNA"
        f"{topology_token} BCT 01-JAN-2000\n"
        f"VERSION     {COMPONENT}\n"
        "ORIGIN\n"
        f"        1 {sequence.lower()}\n"
        "//\n"
    )


def make_package(
    root: Path,
    *,
    sequence: str = "ACGTACGT",
    gbff_sequence: str | None = None,
    topology: str | None = "circular",
    biosample: str = BIOSAMPLE,
    include_gbff: bool = True,
):
    package = root / "package"

    data = (
        package
        / "ncbi_dataset"
        / "data"
    )

    acc_dir = (
        data
        / ACCESSION
    )

    acc_dir.mkdir(
        parents=True
    )

    write_jsonl(
        data
        / "assembly_data_report.jsonl",
        [
            {
                "accession":
                    ACCESSION,
                "currentAccession":
                    ACCESSION,
                "assemblyInfo": {
                    "assemblyStatus":
                        "current",
                    "assemblyLevel":
                        "Complete Genome",
                    "biosample": {
                        "accession":
                            biosample,
                    },
                },
            }
        ],
    )

    write_jsonl(
        acc_dir
        / "sequence_report.jsonl",
        [
            {
                "assemblyAccession":
                    ACCESSION,
                "assemblyUnit":
                    "Primary Assembly",
                "genbankAccession":
                    COMPONENT,
                "length":
                    len(sequence),
            }
        ],
    )

    (
        acc_dir
        / f"{ACCESSION}_genomic.fna"
    ).write_text(
        f">{COMPONENT}\n"
        f"{sequence}\n",
        encoding="utf-8",
    )

    if include_gbff:
        observed_gbff_sequence = (
            sequence
            if gbff_sequence is None
            else gbff_sequence
        )

        (
            acc_dir
            / f"{ACCESSION}_genomic.gbff"
        ).write_text(
            gbff_text(
                observed_gbff_sequence,
                topology=topology,
            ),
            encoding="utf-8",
        )

    return package


def load_historical_worker():
    spec = importlib.util.spec_from_file_location(
        "bacselect_historical_sequence_worker",
        HISTORICAL_WORKER,
    )

    assert spec is not None
    assert spec.loader is not None

    loaded = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        loaded
    )

    return loaded


def historical_target():
    return {
        "canonical_genbank_assembly_accession":
            ACCESSION,
        "source_biosample":
            BIOSAMPLE,
        "fresh_biosample":
            BIOSAMPLE,
        "acquisition_reason":
            "not_in_historical_cache",
    }


def test_audit_schemas_match_historical_worker():
    historical = (
        load_historical_worker()
    )

    assert tuple(
        historical.CANDIDATE_AUDIT_FIELDS
    ) == CANDIDATE_AUDIT_FIELDS

    assert tuple(
        historical.COMPONENT_AUDIT_FIELDS
    ) == COMPONENT_AUDIT_FIELDS

    assert tuple(
        historical.PACKAGE_FILE_FIELDS
    ) == PACKAGE_FILE_FIELDS


def test_complete_local_payload_matches_historical_semantics(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    new_result = (
        validate_hydrated_package(
            package,
            (target(),),
        )
    )

    historical = (
        load_historical_worker()
    )

    (
        historical_data_root,
        historical_biosamples,
        _,
    ) = historical.validate_metadata(
        package,
        [historical_target()],
    )

    (
        historical_candidate,
        historical_components,
    ) = historical.validate_candidate_payload(
        historical_data_root,
        historical_target(),
        historical_biosamples[
            ACCESSION
        ],
    )

    historical_files = tuple(
        historical.package_file_manifest(
            package
        )
    )

    assert new_result.candidate_rows == (
        historical_candidate,
    )

    assert new_result.component_rows == tuple(
        historical_components
    )

    assert (
        new_result.package_file_rows
        == historical_files
    )


def test_expected_biosample_mismatch_fails_closed(
    tmp_path,
):
    package = make_package(
        tmp_path,
        biosample="SAMN00000002",
    )

    with pytest.raises(
        MonthlySequenceValidationError,
        match="BioSample mismatch",
    ):
        validate_hydrated_package(
            package,
            (target(),),
        )


def test_missing_gbff_fails_closed_without_fallback(
    tmp_path,
):
    package = make_package(
        tmp_path,
        include_gbff=False,
    )

    with pytest.raises(
        MonthlySequenceValidationError,
        match="expected exactly one NCBI Datasets GBFF",
    ):
        validate_hydrated_package(
            package,
            (target(),),
        )

    acc_dir = (
        package
        / "ncbi_dataset"
        / "data"
        / ACCESSION
    )

    assert not (
        acc_dir
        / f"{ACCESSION}_efetch_components.gbff"
    ).exists()

    assert not (
        acc_dir
        / f"{ACCESSION}_efetch_components.json"
    ).exists()


def test_efetch_fallback_artifacts_are_rejected(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    acc_dir = (
        package
        / "ncbi_dataset"
        / "data"
        / ACCESSION
    )

    (
        acc_dir
        / f"{ACCESSION}_efetch_components.json"
    ).write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        MonthlySequenceValidationError,
        match="EFetch fallback evidence",
    ):
        validate_hydrated_package(
            package,
            (target(),),
        )


def test_ambiguous_primary_sequence_is_ineligible(
    tmp_path,
):
    package = make_package(
        tmp_path,
        sequence="ACGTNCGT",
    )

    result = validate_hydrated_package(
        package,
        (target(),),
    )

    candidate = (
        result.candidate_rows[0]
    )

    component = (
        result.component_rows[0]
    )

    assert (
        candidate["sequence_eligibility"]
        == "ineligible"
    )

    assert (
        candidate["exclusion_reasons"]
        == "ambiguous_nucleotide"
    )

    assert (
        candidate["ambiguous_base_count"]
        == "1"
    )

    assert (
        component["ambiguous_symbols"]
        == "N"
    )


def test_unspecified_topology_is_ineligible(
    tmp_path,
):
    package = make_package(
        tmp_path,
        topology=None,
    )

    result = validate_hydrated_package(
        package,
        (target(),),
    )

    candidate = (
        result.candidate_rows[0]
    )

    component = (
        result.component_rows[0]
    )

    assert (
        candidate["sequence_eligibility"]
        == "ineligible"
    )

    assert (
        candidate["exclusion_reasons"]
        == "unresolved_topology"
    )

    assert (
        component["topology"]
        == "unspecified"
    )


def test_fasta_gbff_sequence_disagreement_fails_closed(
    tmp_path,
):
    package = make_package(
        tmp_path,
        sequence="ACGTACGT",
        gbff_sequence="ACGTTCGT",
    )

    with pytest.raises(
        MonthlySequenceValidationError,
        match="FASTA and GBFF ORIGIN sequences differ",
    ):
        validate_hydrated_package(
            package,
            (target(),),
        )


def test_package_manifest_is_deterministic(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    first = package_file_manifest(
        package
    )

    second = package_file_manifest(
        package
    )

    assert first == second

    assert tuple(
        row["path"]
        for row in first
    ) == tuple(
        sorted(
            row["path"]
            for row in first
        )
    )

    for row in first:
        assert len(
            row["sha256"]
        ) == 64


def test_stage3a_module_has_no_network_or_historical_bindings():
    text = Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )

    forbidden = (
        "subprocess",
        "urllib",
        "requests",
        "http.client",
        "urlopen",
        "EFETCH_ENDPOINT",
        "retrieve_efetch_gbff",
        "/NGS/",
        "Rhys_wkdir",
        "finch-ncbi-datasets",
        "Project Finch",
        "EXPECTED_TARGETS",
        "EXPECTED_BATCHES",
        "15_326",
        "31 batches",
    )

    for token in forbidden:
        assert token not in text
