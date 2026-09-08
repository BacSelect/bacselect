"""Pure deterministic serialization contract for BacSelect monthly releases.

This module defines presentation/package bytes only.

It performs no filesystem publication, source acquisition, taxonomy resolution,
selector execution, network access, Git mutation, or Zenodo interaction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import binascii
import hashlib
import json
from pathlib import PurePosixPath
import re
import struct
from typing import Any


SCHEMA_VERSION = "bacselect-monthly-release-package-v1"

METADATA_SCHEMA_VERSION = (
    "bacselect-monthly-public-metadata-v1"
)

EVIDENCE_MANIFEST_SCHEMA_VERSION = (
    "bacselect-monthly-release-evidence-manifest-v1"
)

CHECKSUM_SCHEMA_VERSION = (
    "bacselect-monthly-release-sha256-v1"
)

PANEL_SIZES = (
    10,
    20,
    50,
    100,
    200,
    500,
)

MIN_N = 10
MAX_N = 500

SELECTOR = "OPS"
SELECTOR_VERSION = "1.0.0"
ARCHITECTURE_SCHEMA_VERSION = "1"

REFERENCE_FIELDS = (
    "selection_rank",
    "first_public_panel_n",
    "genbank_assembly_accession",
    "biosample_accession",
    "ncbi_organism_name",
    "ncbi_organism_taxid",
    "bacselect_species_name",
    "bacselect_species_taxid",
    "assembly_name",
    "submitter",
    "assembly_release_date",
    "panel_identity",
    "selector",
    "selector_version",
    "architecture_schema_version",
    "source_snapshot_sha256",
    "taxonomy_snapshot_sha256",
    "execution_git_commit",
    "ncbi_assembly_url",
)

PUBLIC_PANEL_FIELDS = (
    "panel_identity",
    "panel_size",
    "selection_rank",
    "genbank_assembly_accession",
    "biosample_accession",
    "ncbi_organism_name",
    "ncbi_organism_taxid",
    "bacselect_species_name",
    "bacselect_species_taxid",
    "assembly_name",
    "submitter",
    "assembly_release_date",
    "selector",
    "selector_version",
    "architecture_schema_version",
    "source_snapshot_sha256",
    "taxonomy_snapshot_sha256",
    "execution_git_commit",
    "ncbi_assembly_url",
)

COLUMN_WIDTHS = (
    23,
    12,
    15,
    24,
    20,
    35,
    19,
    35,
    22,
    25,
    40,
    19,
    12,
    17,
    27,
    68,
    68,
    43,
    56,
)

EVIDENCE_MANIFEST_FIELDS = (
    "role",
    "relative_path",
    "sha256",
    "bytes",
)

EVIDENCE_ROLES = frozenset({
    "source_snapshot_metadata",
    "metadata_eligibility",
    "source_truth_eligibility",
    "biosample_reconciliation",
    "chromosome_integrity_review",
    "taxonomy_snapshot_identity",
    "species_resolution",
    "raw_structural_features",
    "percentile_geometry",
    "species_representatives",
    "complete_diversity_ladder",
    "selector_trace",
    "public_panel_coverage",
})

RELEASE_ID_RE = re.compile(
    r"^[0-9]{4}\.(?:0[1-9]|1[0-2])$"
)

GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

BIOSAMPLE_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
)

SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

SAFE_PACKAGE_NAME_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$"
)


class MonthlyReleasePackageError(
    ValueError
):
    """Raised when the frozen Stage 15 serialization contract is violated."""


@dataclass(
    frozen=True,
)
class PublicMetadataRow:
    selection_rank: str
    first_public_panel_n: str
    genbank_assembly_accession: str
    biosample_accession: str
    ncbi_organism_name: str
    ncbi_organism_taxid: str
    bacselect_species_name: str
    bacselect_species_taxid: str
    assembly_name: str
    submitter: str
    assembly_release_date: str
    panel_identity: str
    selector: str
    selector_version: str
    architecture_schema_version: str
    source_snapshot_sha256: str
    taxonomy_snapshot_sha256: str
    execution_git_commit: str
    ncbi_assembly_url: str


@dataclass(
    frozen=True,
    order=True,
)
class EvidenceFile:
    role: str
    relative_path: str
    sha256: str
    size_bytes: int


def sha256_bytes(
    payload: bytes,
) -> str:
    if not isinstance(
        payload,
        bytes,
    ):
        raise TypeError(
            "payload must be bytes"
        )

    return hashlib.sha256(
        payload
    ).hexdigest()


def canonical_json_bytes(
    payload: Mapping[
        str,
        Any,
    ],
) -> bytes:
    if not isinstance(
        payload,
        Mapping,
    ):
        raise TypeError(
            "canonical JSON payload must be a mapping"
        )

    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    ).encode(
        "ascii"
    )


def validate_release_id(
    value: object,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or RELEASE_ID_RE.fullmatch(
            value
        )
        is None
    ):
        raise MonthlyReleasePackageError(
            "release ID must have YYYY.MM form"
        )

    return value


def panel_identity(
    release_id: str,
) -> str:
    return (
        "bacselect-"
        + validate_release_id(
            release_id
        )
    )


def validate_panel_size(
    value: object,
) -> int:
    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < MIN_N
        or value > MAX_N
    ):
        raise MonthlyReleasePackageError(
            "panel size must be an integer from 10 through 500"
        )

    return value


def first_public_panel_n(
    rank: object,
) -> int:
    if (
        isinstance(
            rank,
            bool,
        )
        or not isinstance(
            rank,
            int,
        )
        or rank < 1
        or rank > MAX_N
    ):
        raise MonthlyReleasePackageError(
            "selection rank must be from 1 through 500"
        )

    for panel_size in PANEL_SIZES:
        if rank <= panel_size:
            return panel_size

    raise AssertionError(
        "unreachable public-panel rank"
    )


def _safe_text(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(
            value,
            str,
        )
        or not value
    ):
        raise MonthlyReleasePackageError(
            f"{label} must be non-empty text"
        )

    if any(
        token in value
        for token in (
            "\t",
            "\n",
            "\r",
        )
    ):
        raise MonthlyReleasePackageError(
            f"{label} contains a TSV control character"
        )

    return value


def _sha256(
    value: object,
    *,
    label: str,
) -> str:
    text = _safe_text(
        value,
        label=label,
    )

    if SHA256_RE.fullmatch(
        text
    ) is None:
        raise MonthlyReleasePackageError(
            f"{label} must be a lowercase SHA256"
        )

    return text


def _commit(
    value: object,
) -> str:
    text = _safe_text(
        value,
        label="execution Git commit",
    )

    if COMMIT_RE.fullmatch(
        text
    ) is None:
        raise MonthlyReleasePackageError(
            "execution Git commit must be a lowercase 40-character SHA"
        )

    return text


def _positive_decimal_text(
    value: object,
    *,
    label: str,
) -> str:
    text = _safe_text(
        value,
        label=label,
    )

    if (
        not text.isdigit()
        or int(
            text
        ) <= 0
    ):
        raise MonthlyReleasePackageError(
            f"{label} must be positive decimal text"
        )

    return text


def _audit_row(
    row: PublicMetadataRow,
    *,
    release_id: str | None = None,
) -> PublicMetadataRow:
    if not isinstance(
        row,
        PublicMetadataRow,
    ):
        raise TypeError(
            "metadata row has wrong type"
        )

    rank_text = _positive_decimal_text(
        row.selection_rank,
        label="selection rank",
    )

    rank = int(
        rank_text
    )

    if rank > MAX_N:
        raise MonthlyReleasePackageError(
            "selection rank exceeds public maximum"
        )

    first_n_text = _positive_decimal_text(
        row.first_public_panel_n,
        label="first public panel N",
    )

    if int(
        first_n_text
    ) != first_public_panel_n(
        rank
    ):
        raise MonthlyReleasePackageError(
            "first public panel N does not match selection rank"
        )

    accession = _safe_text(
        row.genbank_assembly_accession,
        label="GenBank assembly accession",
    )

    if GCA_RE.fullmatch(
        accession
    ) is None:
        raise MonthlyReleasePackageError(
            "GenBank assembly accession is not canonical GCA accession.version"
        )

    biosample = _safe_text(
        row.biosample_accession,
        label="BioSample accession",
    )

    if BIOSAMPLE_RE.fullmatch(
        biosample
    ) is None:
        raise MonthlyReleasePackageError(
            "BioSample accession is invalid"
        )

    ncbi_taxid = _positive_decimal_text(
        row.ncbi_organism_taxid,
        label="NCBI organism TaxID",
    )

    species_taxid = _positive_decimal_text(
        row.bacselect_species_taxid,
        label="BacSelect species TaxID",
    )

    identity = _safe_text(
        row.panel_identity,
        label="panel identity",
    )

    if release_id is not None:
        expected_identity = panel_identity(
            release_id
        )

        if identity != expected_identity:
            raise MonthlyReleasePackageError(
                "panel identity does not match monthly release"
            )

    if row.selector != SELECTOR:
        raise MonthlyReleasePackageError(
            "selector must be OPS"
        )

    if (
        row.selector_version
        != SELECTOR_VERSION
    ):
        raise MonthlyReleasePackageError(
            "selector version changed"
        )

    if (
        row.architecture_schema_version
        != ARCHITECTURE_SCHEMA_VERSION
    ):
        raise MonthlyReleasePackageError(
            "architecture schema version changed"
        )

    source_sha = _sha256(
        row.source_snapshot_sha256,
        label="source snapshot SHA256",
    )

    taxonomy_sha = _sha256(
        row.taxonomy_snapshot_sha256,
        label="taxonomy snapshot SHA256",
    )

    commit = _commit(
        row.execution_git_commit
    )

    expected_url = (
        "https://www.ncbi.nlm.nih.gov/assembly/"
        + accession
        + "/"
    )

    if (
        row.ncbi_assembly_url
        != expected_url
    ):
        raise MonthlyReleasePackageError(
            "NCBI assembly URL does not match accession"
        )

    return PublicMetadataRow(
        selection_rank=rank_text,
        first_public_panel_n=first_n_text,
        genbank_assembly_accession=accession,
        biosample_accession=biosample,
        ncbi_organism_name=_safe_text(
            row.ncbi_organism_name,
            label="NCBI organism name",
        ),
        ncbi_organism_taxid=ncbi_taxid,
        bacselect_species_name=_safe_text(
            row.bacselect_species_name,
            label="BacSelect species name",
        ),
        bacselect_species_taxid=species_taxid,
        assembly_name=_safe_text(
            row.assembly_name,
            label="assembly name",
        ),
        submitter=_safe_text(
            row.submitter,
            label="submitter",
        ),
        assembly_release_date=_safe_text(
            row.assembly_release_date,
            label="assembly release date",
        ),
        panel_identity=identity,
        selector=SELECTOR,
        selector_version=SELECTOR_VERSION,
        architecture_schema_version=(
            ARCHITECTURE_SCHEMA_VERSION
        ),
        source_snapshot_sha256=source_sha,
        taxonomy_snapshot_sha256=taxonomy_sha,
        execution_git_commit=commit,
        ncbi_assembly_url=expected_url,
    )


def audit_metadata_ladder(
    rows: Sequence[
        PublicMetadataRow
    ],
    *,
    release_id: str,
) -> tuple[
    PublicMetadataRow,
    ...,
]:
    release = validate_release_id(
        release_id
    )

    if (
        isinstance(
            rows,
            (
                str,
                bytes,
            ),
        )
        or not isinstance(
            rows,
            Sequence,
        )
    ):
        raise TypeError(
            "metadata ladder must be a sequence"
        )

    checked = tuple(
        _audit_row(
            row,
            release_id=release,
        )
        for row in rows
    )

    if len(
        checked
    ) != MAX_N:
        raise MonthlyReleasePackageError(
            "metadata ladder must contain exactly 500 rows"
        )

    for index, row in enumerate(
        checked,
        start=1,
    ):
        if row.selection_rank != str(
            index
        ):
            raise MonthlyReleasePackageError(
                "metadata ladder rank sequence changed"
            )

    accessions = tuple(
        row.genbank_assembly_accession
        for row in checked
    )

    if len(
        set(
            accessions
        )
    ) != MAX_N:
        raise MonthlyReleasePackageError(
            "metadata ladder assembly accessions must be unique"
        )

    species_taxids = tuple(
        row.bacselect_species_taxid
        for row in checked
    )

    if len(
        set(
            species_taxids
        )
    ) != MAX_N:
        raise MonthlyReleasePackageError(
            "metadata ladder must contain 500 distinct species TaxIDs"
        )

    common_fields = (
        "panel_identity",
        "selector",
        "selector_version",
        "architecture_schema_version",
        "source_snapshot_sha256",
        "taxonomy_snapshot_sha256",
        "execution_git_commit",
    )

    first = checked[
        0
    ]

    for row in checked[
        1:
    ]:
        for field in common_fields:
            if getattr(
                row,
                field,
            ) != getattr(
                first,
                field,
            ):
                raise MonthlyReleasePackageError(
                    f"metadata ladder common field changed: {field}"
                )

    return checked


def _row_fields(
    row: PublicMetadataRow,
) -> tuple[
    str,
    ...,
]:
    return tuple(
        getattr(
            row,
            field,
        )
        for field in REFERENCE_FIELDS
    )


def serialize_metadata_ladder(
    rows: Sequence[
        PublicMetadataRow
    ],
    *,
    release_id: str,
) -> bytes:
    checked = audit_metadata_ladder(
        rows,
        release_id=release_id,
    )

    lines = [
        "\t".join(
            REFERENCE_FIELDS
        )
    ]

    lines.extend(
        "\t".join(
            _row_fields(
                row
            )
        )
        for row in checked
    )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def public_panel_rows(
    rows: Sequence[
        PublicMetadataRow
    ],
    *,
    release_id: str,
    panel_size: int,
) -> tuple[
    tuple[
        str,
        ...,
    ],
    ...,
]:
    checked = audit_metadata_ladder(
        rows,
        release_id=release_id,
    )

    n = validate_panel_size(
        panel_size
    )

    output = []

    for row in checked[
        :n
    ]:
        output.append(
            (
                row.panel_identity,
                str(
                    n
                ),
                row.selection_rank,
                row.genbank_assembly_accession,
                row.biosample_accession,
                row.ncbi_organism_name,
                row.ncbi_organism_taxid,
                row.bacselect_species_name,
                row.bacselect_species_taxid,
                row.assembly_name,
                row.submitter,
                row.assembly_release_date,
                row.selector,
                row.selector_version,
                row.architecture_schema_version,
                row.source_snapshot_sha256,
                row.taxonomy_snapshot_sha256,
                row.execution_git_commit,
                row.ncbi_assembly_url,
            )
        )

    return tuple(
        output
    )


def serialize_panel_tsv(
    rows: Sequence[
        PublicMetadataRow
    ],
    *,
    release_id: str,
    panel_size: int,
) -> bytes:
    panel = public_panel_rows(
        rows,
        release_id=release_id,
        panel_size=panel_size,
    )

    lines = [
        "\t".join(
            PUBLIC_PANEL_FIELDS
        )
    ]

    lines.extend(
        "\t".join(
            row
        )
        for row in panel
    )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def serialize_panel_accessions(
    rows: Sequence[
        PublicMetadataRow
    ],
    *,
    release_id: str,
    panel_size: int,
) -> bytes:
    checked = audit_metadata_ladder(
        rows,
        release_id=release_id,
    )

    n = validate_panel_size(
        panel_size
    )

    return (
        "\n".join(
            row.genbank_assembly_accession
            for row in checked[
                :n
            ]
        )
        + "\n"
    ).encode(
        "ascii"
    )


def _xml_escape(
    value: str,
) -> str:
    text = str(
        value
    )

    for character in text:
        code = ord(
            character
        )

        if (
            code < 0x20
            and code not in {
                0x09,
                0x0A,
                0x0D,
            }
        ):
            raise MonthlyReleasePackageError(
                "workbook value contains an illegal XML control character"
            )

    return (
        text
        .replace(
            "&",
            "&amp;",
        )
        .replace(
            "<",
            "&lt;",
        )
        .replace(
            ">",
            "&gt;",
        )
    )


def _excel_column_name(
    index: int,
) -> str:
    value = index + 1
    name = ""

    while value > 0:
        remainder = (
            value - 1
        ) % 26

        name = (
            chr(
                65 + remainder
            )
            + name
        )

        value = (
            value - 1
        ) // 26

    return name


def _inline_cell(
    row_index: int,
    column_index: int,
    value: str,
    style: int = 0,
) -> str:
    reference = (
        f"{_excel_column_name(column_index)}{row_index}"
    )

    style_attribute = (
        ""
        if style == 0
        else f' s="{style}"'
    )

    return (
        f'<c r="{reference}" t="inlineStr"{style_attribute}>'
        '<is><t xml:space="preserve">'
        + _xml_escape(
            value
        )
        + "</t></is></c>"
    )


def _worksheet_xml(
    rows: Sequence[
        Sequence[
            str
        ]
    ],
) -> str:
    last_row = len(
        rows
    ) + 1

    last_column = _excel_column_name(
        len(
            PUBLIC_PANEL_FIELDS
        )
        - 1
    )

    columns = "".join(
        (
            f'<col min="{index + 1}" max="{index + 1}" '
            f'width="{width}" customWidth="1"/>'
        )
        for index, width
        in enumerate(
            COLUMN_WIDTHS
        )
    )

    header_cells = "".join(
        _inline_cell(
            1,
            index,
            field,
            1,
        )
        for index, field
        in enumerate(
            PUBLIC_PANEL_FIELDS
        )
    )

    data_rows = []

    for row_offset, row in enumerate(
        rows
    ):
        row_number = (
            row_offset
            + 2
        )

        cells = "".join(
            _inline_cell(
                row_number,
                column_index,
                value,
                0,
            )
            for column_index, value
            in enumerate(
                row
            )
        )

        data_rows.append(
            f'<row r="{row_number}">{cells}</row>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main">'
        f'<dimension ref="A1:{last_column}{last_row}"/>'
        '<sheetViews>'
        '<sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/>'
        '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/>'
        '</sheetView>'
        '</sheetViews>'
        '<sheetFormatPr defaultRowHeight="18"/>'
        f'<cols>{columns}</cols>'
        '<sheetData>'
        f'<row r="1" ht="32" customHeight="1">{header_cells}</row>'
        + "".join(
            data_rows
        )
        + '</sheetData>'
        f'<autoFilter ref="A1:{last_column}{last_row}"/>'
        '</worksheet>'
    )


def _workbook_files(
    rows: Sequence[
        Sequence[
            str
        ]
    ],
) -> tuple[
    tuple[
        str,
        bytes,
    ],
    ...,
]:
    text_files = (
        (
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" '
            'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'extended-properties+xml"/>'
            '</Types>',
        ),
        (
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/package/2006/'
            'relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/extended-properties" Target="docProps/app.xml"/>'
            '</Relationships>',
        ),
        (
            "docProps/app.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/'
            'officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/'
            '2006/docPropsVTypes">'
            '<Application>BacSelect</Application>'
            '</Properties>',
        ),
        (
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
            'metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>BacSelect panel metadata</dc:title>'
            '<dc:creator>BacSelect</dc:creator>'
            '</cp:coreProperties>',
        ),
        (
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships">'
            '<sheets>'
            '<sheet name="Panel metadata" sheetId="1" r:id="rId1"/>'
            '</sheets>'
            '</workbook>',
        ),
        (
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>',
        ),
        (
            "xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main">'
            '<fonts count="2">'
            '<font><sz val="11"/><name val="Aptos"/></font>'
            '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/>'
            '<name val="Aptos"/></font>'
            '</fonts>'
            '<fills count="3">'
            '<fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid">'
            '<fgColor rgb="FF6846C7"/><bgColor indexed="64"/>'
            '</patternFill></fill>'
            '</fills>'
            '<borders count="2">'
            '<border><left/><right/><top/><bottom/><diagonal/></border>'
            '<border><left/><right/><top/>'
            '<bottom style="thin"><color rgb="FFD8D3E4"/></bottom>'
            '<diagonal/></border>'
            '</borders>'
            '<cellStyleXfs count="1">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
            '</cellStyleXfs>'
            '<cellXfs count="2">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" '
            'xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" '
            'xfId="0" applyFont="1" applyFill="1" applyBorder="1" '
            'applyAlignment="1">'
            '<alignment vertical="center" wrapText="1"/>'
            '</xf>'
            '</cellXfs>'
            '<cellStyles count="1">'
            '<cellStyle name="Normal" xfId="0" builtinId="0"/>'
            '</cellStyles>'
            '</styleSheet>',
        ),
        (
            "xl/worksheets/sheet1.xml",
            _worksheet_xml(
                rows
            ),
        ),
    )

    return tuple(
        (
            name,
            text.encode(
                "utf-8"
            ),
        )
        for name, text
        in text_files
    )


def _local_header(
    name_bytes: bytes,
    data_bytes: bytes,
    checksum: int,
) -> bytes:
    header = bytearray(
        30
        + len(
            name_bytes
        )
    )

    struct.pack_into(
        "<IHHHHHIIIHH",
        header,
        0,
        0x04034B50,
        20,
        0x0800,
        0,
        0,
        0x0021,
        checksum,
        len(
            data_bytes
        ),
        len(
            data_bytes
        ),
        len(
            name_bytes
        ),
        0,
    )

    header[
        30:
    ] = name_bytes

    return bytes(
        header
    )


def _central_header(
    name_bytes: bytes,
    data_bytes: bytes,
    checksum: int,
    local_offset: int,
) -> bytes:
    header = bytearray(
        46
        + len(
            name_bytes
        )
    )

    struct.pack_into(
        "<IHHHHHHIIIHHHHHII",
        header,
        0,
        0x02014B50,
        20,
        20,
        0x0800,
        0,
        0,
        0x0021,
        checksum,
        len(
            data_bytes
        ),
        len(
            data_bytes
        ),
        len(
            name_bytes
        ),
        0,
        0,
        0,
        0,
        0,
        local_offset,
    )

    header[
        46:
    ] = name_bytes

    return bytes(
        header
    )


def _end_of_central_directory(
    file_count: int,
    central_size: int,
    central_offset: int,
) -> bytes:
    return struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        file_count,
        file_count,
        central_size,
        central_offset,
        0,
    )


def _zip_stored(
    files: Sequence[
        tuple[
            str,
            bytes,
        ]
    ],
) -> bytes:
    local_parts = []
    central_parts = []

    local_offset = 0

    for name, data_bytes in files:
        name_bytes = name.encode(
            "utf-8"
        )

        checksum = (
            binascii.crc32(
                data_bytes
            )
            & 0xFFFFFFFF
        )

        local = _local_header(
            name_bytes,
            data_bytes,
            checksum,
        )

        local_parts.extend(
            (
                local,
                data_bytes,
            )
        )

        central_parts.append(
            _central_header(
                name_bytes,
                data_bytes,
                checksum,
                local_offset,
            )
        )

        local_offset += (
            len(
                local
            )
            + len(
                data_bytes
            )
        )

    central = b"".join(
        central_parts
    )

    end = _end_of_central_directory(
        len(
            files
        ),
        len(
            central
        ),
        local_offset,
    )

    return b"".join(
        (
            *local_parts,
            central,
            end,
        )
    )


def serialize_panel_xlsx(
    rows: Sequence[
        PublicMetadataRow
    ],
    *,
    release_id: str,
    panel_size: int,
) -> bytes:
    panel = public_panel_rows(
        rows,
        release_id=release_id,
        panel_size=panel_size,
    )

    return _zip_stored(
        _workbook_files(
            panel
        )
    )


def metadata_ladder_filename(
    release_id: str,
) -> str:
    release = validate_release_id(
        release_id
    )

    return (
        f"bacselect-{release}-metadata-ladder-n500.tsv"
    )


def panel_filename(
    release_id: str,
    panel_size: int,
    suffix: str,
) -> str:
    release = validate_release_id(
        release_id
    )

    n = validate_panel_size(
        panel_size
    )

    if suffix not in {
        "txt",
        "tsv",
        "xlsx",
    }:
        raise MonthlyReleasePackageError(
            "unsupported public panel suffix"
        )

    return (
        f"bacselect-{release}-n{n}.{suffix}"
    )


def _safe_relative_path(
    value: object,
) -> str:
    text = _safe_text(
        value,
        label="evidence relative path",
    )

    path = PurePosixPath(
        text
    )

    if (
        path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or str(
            path
        ) != text
    ):
        raise MonthlyReleasePackageError(
            "evidence relative path is unsafe"
        )

    return text


def _evidence_file(
    value: EvidenceFile,
) -> EvidenceFile:
    if not isinstance(
        value,
        EvidenceFile,
    ):
        raise TypeError(
            "release evidence entry has wrong type"
        )

    role = _safe_text(
        value.role,
        label="evidence role",
    )

    if role not in EVIDENCE_ROLES:
        raise MonthlyReleasePackageError(
            "release evidence role is not frozen"
        )

    if (
        isinstance(
            value.size_bytes,
            bool,
        )
        or not isinstance(
            value.size_bytes,
            int,
        )
        or value.size_bytes < 0
    ):
        raise MonthlyReleasePackageError(
            "evidence byte size must be a non-negative integer"
        )

    return EvidenceFile(
        role=role,
        relative_path=_safe_relative_path(
            value.relative_path
        ),
        sha256=_sha256(
            value.sha256,
            label="evidence SHA256",
        ),
        size_bytes=value.size_bytes,
    )


def serialize_evidence_manifest(
    values: Sequence[
        EvidenceFile
    ],
) -> bytes:
    if (
        isinstance(
            values,
            (
                str,
                bytes,
            ),
        )
        or not isinstance(
            values,
            Sequence,
        )
    ):
        raise TypeError(
            "release evidence manifest must be a sequence"
        )

    checked = tuple(
        _evidence_file(
            value
        )
        for value in values
    )

    if not checked:
        raise MonthlyReleasePackageError(
            "release evidence manifest cannot be empty"
        )

    paths = tuple(
        value.relative_path
        for value in checked
    )

    if len(
        paths
    ) != len(
        set(
            paths
        )
    ):
        raise MonthlyReleasePackageError(
            "release evidence paths must be unique"
        )

    ordered = tuple(
        sorted(
            checked,
            key=lambda value:
                (
                    value.role,
                    value.relative_path,
                ),
        )
    )

    lines = [
        "\t".join(
            EVIDENCE_MANIFEST_FIELDS
        )
    ]

    lines.extend(
        "\t".join(
            (
                value.role,
                value.relative_path,
                value.sha256,
                str(
                    value.size_bytes
                ),
            )
        )
        for value in ordered
    )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "ascii"
    )


def serialize_sha256sums(
    artifacts: Mapping[
        str,
        bytes,
    ],
) -> bytes:
    if not isinstance(
        artifacts,
        Mapping,
    ):
        raise TypeError(
            "package artifacts must be a mapping"
        )

    if not artifacts:
        raise MonthlyReleasePackageError(
            "package artifact mapping cannot be empty"
        )

    rows = []

    for name in sorted(
        artifacts
    ):
        if (
            not isinstance(
                name,
                str,
            )
            or SAFE_PACKAGE_NAME_RE.fullmatch(
                name
            )
            is None
        ):
            raise MonthlyReleasePackageError(
                "package filename is invalid"
            )

        payload = artifacts[
            name
        ]

        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError(
                "package artifact payload must be bytes"
            )

        rows.append(
            sha256_bytes(
                payload
            )
            + "  "
            + name
        )

    return (
        "\n".join(
            rows
        )
        + "\n"
    ).encode(
        "ascii"
    )
