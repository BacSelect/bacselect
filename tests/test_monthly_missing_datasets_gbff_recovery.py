import hashlib
import json
from pathlib import Path

import pytest

from bacselect import monthly_sequence_validation as monthly
from bacselect import (
    monthly_missing_datasets_gbff_recovery
    as recovery,
)


ACC = "GCA_123456789.1"
BIO = "SAMN12345678"
COMP = "CP012345.1"
SEQUENCE = "ACGTACGT"


def make_target():
    return monthly.MonthlyFreshAcquisitionTarget(
        canonical_genbank_assembly_accession=ACC,
        source_biosample=BIO,
        acquisition_reason="no_verified_cache",
    )


def gbff_bytes():
    return (
        "LOCUS       CP012345                  8 bp    DNA     circular\n"
        "VERSION     CP012345.1\n"
        "ORIGIN\n"
        "        1 acgtacgt\n"
        "//\n"
    ).encode(
        "ascii"
    )


def make_package(
    tmp_path,
    *,
    datasets_gbff=False,
    fetch_gbff=False,
):
    package = (
        tmp_path
        / "package"
    )

    ncbi = (
        package
        / "ncbi_dataset"
    )

    data = (
        ncbi
        / "data"
    )

    acc_dir = (
        data
        / ACC
    )

    acc_dir.mkdir(
        parents=True
    )

    assembly_row = {
        "accession":
            ACC,
        "currentAccession":
            ACC,
        "assemblyInfo": {
            "assemblyStatus":
                "current",
            "assemblyLevel":
                "Complete Genome",
            "biosample": {
                "accession":
                    BIO,
            },
        },
    }

    (
        data
        / "assembly_data_report.jsonl"
    ).write_text(
        json.dumps(
            assembly_row,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    sequence_row = {
        "assemblyAccession":
            ACC,
        "assemblyUnit":
            "Primary Assembly",
        "genbankAccession":
            COMP,
        "length":
            len(
                SEQUENCE
            ),
    }

    (
        acc_dir
        / "sequence_report.jsonl"
    ).write_text(
        json.dumps(
            sequence_row,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        acc_dir
        / f"{ACC}_genomic.fna"
    ).write_text(
        f">{COMP}\n{SEQUENCE}\n",
        encoding="ascii",
    )

    if datasets_gbff:
        (
            acc_dir
            / f"{ACC}_genomic.gbff"
        ).write_bytes(
            gbff_bytes()
        )

    fetch_lines = [
        (
            "https://example.invalid/genome\t"
            f"data/{ACC}/{ACC}_genomic.fna"
        ),
        (
            "https://example.invalid/report\t"
            f"data/{ACC}/sequence_report.jsonl"
        ),
    ]

    if fetch_gbff:
        fetch_lines.append(
            (
                "https://example.invalid/gbff\t"
                f"data/{ACC}/{ACC}_genomic.gbff"
            )
        )

    (
        ncbi
        / "fetch.txt"
    ).write_text(
        "\n".join(
            fetch_lines
        )
        + "\n",
        encoding="utf-8",
    )

    return package


def add_efetch_payload(
    package,
):
    acc_dir = (
        package
        / "ncbi_dataset"
        / "data"
        / ACC
    )

    gbff = (
        acc_dir
        / f"{ACC}_efetch_components.gbff"
    )

    gbff.write_bytes(
        gbff_bytes()
    )

    response = gbff.read_bytes()

    payload = {
        "schema_version":
            1,
        "retrieval_method":
            "ncbi_efetch_nuccore",
        "endpoint":
            (
                "https://eutils.ncbi.nlm.nih.gov/"
                "entrez/eutils/efetch.fcgi"
            ),
        "db":
            "nuccore",
        "rettype":
            "gbwithparts",
        "retmode":
            "text",
        "assembly_accession":
            ACC,
        "requested_component_accessions":
            [COMP],
        "requested_component_count":
            1,
        "chunk_size":
            50,
        "chunk_count":
            1,
        "chunks": [
            {
                "chunk_index":
                    1,
                "requested_component_accessions":
                    [COMP],
                "response_size_bytes":
                    len(
                        response
                    ),
                "response_sha256":
                    hashlib.sha256(
                        response
                    ).hexdigest(),
            }
        ],
        "combined_gbff_size_bytes":
            len(
                response
            ),
        "combined_gbff_sha256":
            hashlib.sha256(
                response
            ).hexdigest(),
        "retrieved_at_utc":
            "2026-09-01T00:00:00Z",
    }

    provenance = (
        acc_dir
        / f"{ACC}_efetch_components.json"
    )

    provenance.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        gbff,
        provenance,
    )


def test_detects_exact_manifest_omission_class(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    result = (
        recovery
        .detect_missing_datasets_gbff_targets(
            package,
            (
                make_target(),
            ),
        )
    )

    assert len(result) == 1

    observed = result[0]

    assert observed.accession == ACC
    assert observed.observed_biosample == BIO
    assert observed.component_accessions == (
        COMP,
    )

    assert len(
        observed.fetch_destinations
    ) == 2

    assert all(
        not path.endswith(
            ".gbff"
        )
        for path
        in observed.fetch_destinations
    )


def test_detector_rejects_manifest_with_gbff_entry(
    tmp_path,
):
    package = make_package(
        tmp_path,
        fetch_gbff=True,
    )

    with pytest.raises(
        recovery.MonthlyMissingDatasetsGbffRecoveryError,
        match="contains a GBFF destination",
    ):
        recovery.detect_missing_datasets_gbff_targets(
            package,
            (
                make_target(),
            ),
        )


def test_detector_rejects_other_candidate_failure(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    fasta = next(
        (
            package
            / "ncbi_dataset"
            / "data"
            / ACC
        ).glob(
            "*.fna"
        )
    )

    fasta.unlink()

    with pytest.raises(
        recovery.MonthlyMissingDatasetsGbffRecoveryError,
        match="outside the frozen recovery class",
    ):
        recovery.detect_missing_datasets_gbff_targets(
            package,
            (
                make_target(),
            ),
        )


def test_recovered_candidate_reuses_monthly_science_exactly(
    tmp_path,
):
    ordinary = make_package(
        tmp_path
        / "ordinary",
        datasets_gbff=True,
    )

    target = make_target()

    (
        ordinary_data,
        ordinary_biosamples,
        _,
    ) = monthly.validate_metadata(
        ordinary,
        (
            target,
        ),
    )

    (
        ordinary_row,
        ordinary_components,
    ) = monthly.validate_candidate_payload(
        ordinary_data,
        target,
        ordinary_biosamples[
            ACC
        ],
    )

    recovered = make_package(
        tmp_path
        / "recovered"
    )

    add_efetch_payload(
        recovered
    )

    recovered_data = (
        recovered
        / "ncbi_dataset"
        / "data"
    )

    (
        recovered_row,
        recovered_components,
    ) = (
        recovery
        .validate_recovered_candidate(
            recovered_data,
            target,
            BIO,
        )
    )

    assert (
        recovered_components
        == ordinary_components
    )

    provenance_fields = {
        "gbff_file",
        "gbff_source",
        "gbff_provenance_file",
        "gbff_provenance_sha256",
    }

    assert {
        key:
            value
        for key, value
        in recovered_row.items()
        if key not in provenance_fields
    } == {
        key:
            value
        for key, value
        in ordinary_row.items()
        if key not in provenance_fields
    }

    assert (
        recovered_row[
            "gbff_source"
        ]
        == "ncbi_efetch_nuccore"
    )

    assert (
        recovered_row[
            "gbff_file"
        ]
        == f"{ACC}_efetch_components.gbff"
    )

    assert (
        recovered_row[
            "gbff_provenance_file"
        ]
        == f"{ACC}_efetch_components.json"
    )

    assert (
        recovered_row[
            "gbff_provenance_sha256"
        ]
        != "none"
    )


def test_recovery_rejects_gbff_hash_mismatch(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    (
        gbff,
        _,
    ) = add_efetch_payload(
        package
    )

    gbff.write_bytes(
        gbff.read_bytes()
        + b"\n"
    )

    with pytest.raises(
        recovery.MonthlyMissingDatasetsGbffRecoveryError,
        match="SHA256",
    ):
        recovery.validate_recovered_candidate(
            (
                package
                / "ncbi_dataset"
                / "data"
            ),
            make_target(),
            BIO,
        )


def test_whole_recovered_package_preserves_batch_order_and_schema(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    add_efetch_payload(
        package
    )

    result = (
        recovery
        .validate_recovered_package(
            package,
            (
                make_target(),
            ),
            (
                ACC,
            ),
        )
    )

    assert len(
        result.candidate_rows
    ) == 1

    assert (
        result.candidate_rows[
            0
        ][
            "canonical_genbank_assembly_accession"
        ]
        == ACC
    )

    assert (
        result.candidate_rows[
            0
        ][
            "gbff_source"
        ]
        == "ncbi_efetch_nuccore"
    )

    assert len(
        result.component_rows
    ) == 1

    package_paths = {
        row[
            "path"
        ]
        for row
        in result.package_file_rows
    }

    assert (
        "ncbi_dataset/data/"
        f"{ACC}/"
        f"{ACC}_efetch_components.gbff"
        in package_paths
    )

    assert (
        "ncbi_dataset/data/"
        f"{ACC}/"
        f"{ACC}_efetch_components.json"
        in package_paths
    )


def test_recovery_does_not_modify_ordinary_monthly_validator(
    tmp_path,
):
    package = make_package(
        tmp_path
    )

    add_efetch_payload(
        package
    )

    target = make_target()

    data_root = (
        package
        / "ncbi_dataset"
        / "data"
    )

    with pytest.raises(
        monthly.MonthlySequenceValidationError,
        match="EFetch fallback evidence is not permitted",
    ):
        monthly.validate_candidate_payload(
            data_root,
            target,
            BIO,
        )
