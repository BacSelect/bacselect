from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from bacselect.monthly_release_package import (
    ARCHITECTURE_SCHEMA_VERSION,
    EVIDENCE_MANIFEST_FIELDS,
    MAX_N,
    PANEL_SIZES,
    PUBLIC_PANEL_FIELDS,
    REFERENCE_FIELDS,
    SCHEMA_VERSION,
    SELECTOR,
    SELECTOR_VERSION,
    EvidenceFile,
    MonthlyReleasePackageError,
    PublicMetadataRow,
    audit_metadata_ladder,
    canonical_json_bytes,
    first_public_panel_n,
    metadata_ladder_filename,
    panel_filename,
    panel_identity,
    public_panel_rows,
    serialize_evidence_manifest,
    serialize_metadata_ladder,
    serialize_panel_accessions,
    serialize_panel_tsv,
    serialize_panel_xlsx,
    serialize_sha256sums,
)


RELEASE = "2026.09"

SOURCE_SHA = "1" * 64
TAXONOMY_SHA = "2" * 64
COMMIT = "3" * 40


def rows():
    values = []

    for rank in range(
        1,
        MAX_N + 1,
    ):
        accession = (
            f"GCA_{rank:09d}.1"
        )

        values.append(
            PublicMetadataRow(
                selection_rank=str(
                    rank
                ),
                first_public_panel_n=str(
                    first_public_panel_n(
                        rank
                    )
                ),
                genbank_assembly_accession=accession,
                biosample_accession=(
                    f"SAMN{rank:08d}"
                ),
                ncbi_organism_name=(
                    f"Organism {rank}"
                ),
                ncbi_organism_taxid=str(
                    100000
                    + rank
                ),
                bacselect_species_name=(
                    f"Species {rank}"
                ),
                bacselect_species_taxid=str(
                    200000
                    + rank
                ),
                assembly_name=(
                    f"ASM{rank}v1"
                ),
                submitter=(
                    f"Submitter {rank}"
                ),
                assembly_release_date=(
                    "2026-08-01"
                ),
                panel_identity=(
                    panel_identity(
                        RELEASE
                    )
                ),
                selector=SELECTOR,
                selector_version=(
                    SELECTOR_VERSION
                ),
                architecture_schema_version=(
                    ARCHITECTURE_SCHEMA_VERSION
                ),
                source_snapshot_sha256=(
                    SOURCE_SHA
                ),
                taxonomy_snapshot_sha256=(
                    TAXONOMY_SHA
                ),
                execution_git_commit=(
                    COMMIT
                ),
                ncbi_assembly_url=(
                    "https://www.ncbi.nlm.nih.gov/assembly/"
                    + accession
                    + "/"
                ),
            )
        )

    return tuple(
        values
    )


def test_schema_identity_is_frozen():
    assert (
        SCHEMA_VERSION
        == "bacselect-monthly-release-package-v1"
    )

    assert PANEL_SIZES == (
        10,
        20,
        50,
        100,
        200,
        500,
    )

    assert len(
        REFERENCE_FIELDS
    ) == 19

    assert len(
        PUBLIC_PANEL_FIELDS
    ) == 19


@pytest.mark.parametrize(
    ("rank", "expected"),
    (
        (1, 10),
        (10, 10),
        (11, 20),
        (20, 20),
        (21, 50),
        (50, 50),
        (51, 100),
        (100, 100),
        (101, 200),
        (200, 200),
        (201, 500),
        (500, 500),
    ),
)
def test_first_public_panel_n(
    rank,
    expected,
):
    assert (
        first_public_panel_n(
            rank
        )
        == expected
    )


def test_monthly_identity_and_filenames():
    assert (
        panel_identity(
            RELEASE
        )
        == "bacselect-2026.09"
    )

    assert (
        metadata_ladder_filename(
            RELEASE
        )
        == "bacselect-2026.09-metadata-ladder-n500.tsv"
    )

    assert (
        panel_filename(
            RELEASE,
            100,
            "xlsx",
        )
        == "bacselect-2026.09-n100.xlsx"
    )


def test_metadata_ladder_is_exact_500_row_tsv():
    payload = (
        serialize_metadata_ladder(
            rows(),
            release_id=RELEASE,
        )
    )

    lines = payload.decode(
        "utf-8"
    ).splitlines()

    assert (
        lines[
            0
        ]
        == "\t".join(
            REFERENCE_FIELDS
        )
    )

    assert len(
        lines
    ) == 501

    assert lines[
        1
    ].split(
        "\t"
    )[
        0
    ] == "1"

    assert lines[
        -1
    ].split(
        "\t"
    )[
        0
    ] == "500"

    assert payload.endswith(
        b"\n"
    )


def test_metadata_ladder_refuses_duplicate_species():
    values = list(
        rows()
    )

    values[
        -1
    ] = PublicMetadataRow(
        **{
            **values[
                -1
            ].__dict__,
            "bacselect_species_taxid":
                values[
                    0
                ].bacselect_species_taxid,
        }
    )

    with pytest.raises(
        MonthlyReleasePackageError,
        match="distinct species",
    ):
        audit_metadata_ladder(
            values,
            release_id=RELEASE,
        )


def test_metadata_ladder_refuses_tsv_control_character():
    values = list(
        rows()
    )

    values[
        0
    ] = PublicMetadataRow(
        **{
            **values[
                0
            ].__dict__,
            "submitter":
                "bad\tvalue",
        }
    )

    with pytest.raises(
        MonthlyReleasePackageError,
        match="TSV control",
    ):
        audit_metadata_ladder(
            values,
            release_id=RELEASE,
        )


def test_metadata_ladder_refuses_empty_public_field():
    values = list(
        rows()
    )

    values[
        0
    ] = PublicMetadataRow(
        **{
            **values[
                0
            ].__dict__,
            "assembly_name":
                "",
        }
    )

    with pytest.raises(
        MonthlyReleasePackageError,
        match="non-empty",
    ):
        audit_metadata_ladder(
            values,
            release_id=RELEASE,
        )


def test_panel_rows_are_exact_prefix():
    values = rows()

    panel = public_panel_rows(
        values,
        release_id=RELEASE,
        panel_size=50,
    )

    assert len(
        panel
    ) == 50

    assert [
        row[
            3
        ]
        for row in panel
    ] == [
        value.genbank_assembly_accession
        for value in values[
            :50
        ]
    ]

    assert {
        row[
            1
        ]
        for row in panel
    } == {
        "50"
    }


def test_panel_tsv_uses_public_panel_schema():
    payload = serialize_panel_tsv(
        rows(),
        release_id=RELEASE,
        panel_size=20,
    )

    lines = payload.decode(
        "utf-8"
    ).splitlines()

    assert lines[
        0
    ] == "\t".join(
        PUBLIC_PANEL_FIELDS
    )

    assert len(
        lines
    ) == 21

    assert all(
        len(
            line.split(
                "\t"
            )
        )
        == 19
        for line in lines
    )


@pytest.mark.parametrize(
    "panel_size",
    PANEL_SIZES,
)
def test_accession_list_is_exact_ladder_prefix(
    panel_size,
):
    values = rows()

    payload = (
        serialize_panel_accessions(
            values,
            release_id=RELEASE,
            panel_size=panel_size,
        )
    )

    assert payload == (
        "\n".join(
            value.genbank_assembly_accession
            for value in values[
                :panel_size
            ]
        )
        + "\n"
    ).encode(
        "ascii"
    )


def test_xlsx_is_byte_deterministic():
    first = serialize_panel_xlsx(
        rows(),
        release_id=RELEASE,
        panel_size=10,
    )

    second = serialize_panel_xlsx(
        rows(),
        release_id=RELEASE,
        panel_size=10,
    )

    assert first == second

    assert hashlib.sha256(
        first
    ).hexdigest() == hashlib.sha256(
        second
    ).hexdigest()


def test_xlsx_contains_exact_frozen_member_inventory():
    payload = serialize_panel_xlsx(
        rows(),
        release_id=RELEASE,
        panel_size=10,
    )

    with zipfile.ZipFile(
        io.BytesIO(
            payload
        )
    ) as archive:
        assert archive.namelist() == [
            "[Content_Types].xml",
            "_rels/.rels",
            "docProps/app.xml",
            "docProps/core.xml",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/styles.xml",
            "xl/worksheets/sheet1.xml",
        ]

        for info in archive.infolist():
            assert (
                info.compress_type
                == zipfile.ZIP_STORED
            )

            assert (
                info.date_time
                == (
                    1980,
                    1,
                    1,
                    0,
                    0,
                    0,
                )
            )

        worksheet = archive.read(
            "xl/worksheets/sheet1.xml"
        ).decode(
            "utf-8"
        )

    assert (
        '<pane ySplit="1"'
        in worksheet
    )

    assert (
        '<autoFilter ref="A1:S11"/>'
        in worksheet
    )

    assert (
        '<fgColor rgb="FF6846C7"/>'
        in archive_member(
            payload,
            "xl/styles.xml",
        )
    )


def archive_member(
    payload,
    name,
):
    with zipfile.ZipFile(
        io.BytesIO(
            payload
        )
    ) as archive:
        return archive.read(
            name
        ).decode(
            "utf-8"
        )


def test_xlsx_escapes_xml_text():
    values = list(
        rows()
    )

    values[
        0
    ] = PublicMetadataRow(
        **{
            **values[
                0
            ].__dict__,
            "submitter":
                "A & B <C>",
        }
    )

    payload = serialize_panel_xlsx(
        values,
        release_id=RELEASE,
        panel_size=10,
    )

    worksheet = archive_member(
        payload,
        "xl/worksheets/sheet1.xml",
    )

    assert (
        "A &amp; B &lt;C&gt;"
        in worksheet
    )


def test_evidence_manifest_is_sorted_and_deterministic():
    values = (
        EvidenceFile(
            role="species_resolution",
            relative_path=(
                "taxonomy-resolution/"
                "taxonomy-resolution-decisions.tsv"
            ),
            sha256="b" * 64,
            size_bytes=20,
        ),
        EvidenceFile(
            role="source_snapshot_metadata",
            relative_path=(
                "source-snapshot-record.json"
            ),
            sha256="a" * 64,
            size_bytes=10,
        ),
    )

    first = serialize_evidence_manifest(
        values
    )

    second = serialize_evidence_manifest(
        tuple(
            reversed(
                values
            )
        )
    )

    assert first == second

    lines = first.decode(
        "ascii"
    ).splitlines()

    assert lines[
        0
    ] == "\t".join(
        EVIDENCE_MANIFEST_FIELDS
    )

    assert lines[
        1
    ].startswith(
        "source_snapshot_metadata\t"
    )


def test_evidence_manifest_refuses_path_traversal():
    with pytest.raises(
        MonthlyReleasePackageError,
        match="unsafe",
    ):
        serialize_evidence_manifest(
            (
                EvidenceFile(
                    role=(
                        "source_snapshot_metadata"
                    ),
                    relative_path=(
                        "../secret"
                    ),
                    sha256="a" * 64,
                    size_bytes=1,
                ),
            )
        )


def test_sha256sums_is_sorted_and_exact():
    payload = serialize_sha256sums(
        {
            "b.txt":
                b"B\n",
            "a.txt":
                b"A\n",
        }
    )

    expected = (
        hashlib.sha256(
            b"A\n"
        ).hexdigest()
        + "  a.txt\n"
        + hashlib.sha256(
            b"B\n"
        ).hexdigest()
        + "  b.txt\n"
    ).encode(
        "ascii"
    )

    assert payload == expected


def test_canonical_json_is_deterministic():
    first = canonical_json_bytes(
        {
            "b": 2,
            "a": 1,
        }
    )

    second = canonical_json_bytes(
        {
            "a": 1,
            "b": 2,
        }
    )

    assert first == second

    assert json.loads(
        first.decode(
            "ascii"
        )
    ) == {
        "a": 1,
        "b": 2,
    }


def test_pure_contract_contains_no_execution_dependencies():
    path = (
        Path(
            __file__
        ).resolve().parents[
            1
        ]
        / "src"
        / "bacselect"
        / "monthly_release_package.py"
    )

    text = path.read_text(
        encoding="utf-8"
    )

    forbidden = (
        "/NGS/",
        "Rhys_wkdir",
        "Project Finch",
        "subprocess",
        "requests",
        "urllib",
        "urlopen",
        "openpyxl",
        "xlsxwriter",
        "sbatch",
        "srun",
        "ZENODO_ACCESS_TOKEN",
        "build_reference_panel_artifacts",
        "serialize_generation_summary",
    )

    for token in forbidden:
        assert token not in text
