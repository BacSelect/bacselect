"""Deterministic public metadata contract for selector-v1 reference panels."""

from __future__ import annotations

from collections.abc import Mapping
import csv
import hashlib
import io
import json
import re
import tarfile
from typing import Any


REFERENCE_IDENTITY = "selector-v1-reference"
REFERENCE_ROW_COUNT = 500
CUSTOM_N_MIN = 10
CUSTOM_N_MAX = 500
PRESET_PANEL_SIZES = (
    10,
    20,
    50,
    100,
    200,
    500,
)

METADATA_SCHEMA_VERSION = (
    "bacselect-selector-v1-reference-public-metadata-v1"
)

REFERENCE_METADATA_FIELDS = (
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

_GCA_RE = re.compile(
    r"^GCA_[0-9]+\.[0-9]+$"
)

_BIOSAMPLE_RE = re.compile(
    r"^(SAMN[0-9]+|SAMEA[0-9]+|SAMD[0-9]+)$"
)

_SHA256_RE = re.compile(
    r"^[0-9a-f]{64}$"
)

_GIT_COMMIT_RE = re.compile(
    r"^[0-9a-f]{40}$"
)

_DATE_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
)


class PublicReferenceMetadataError(ValueError):
    """Raised when public reference metadata violates its frozen contract."""


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


def _require_sha256(
    value: str,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or _SHA256_RE.fullmatch(value) is None
    ):
        raise PublicReferenceMetadataError(
            f"{label} must be a lowercase SHA256"
        )

    return value


def _require_payload_sha256(
    payload: bytes,
    expected_sha256: str,
    *,
    label: str,
) -> None:
    expected = _require_sha256(
        expected_sha256,
        label=f"{label} expected SHA256",
    )

    observed = sha256_bytes(
        payload
    )

    if observed != expected:
        raise PublicReferenceMetadataError(
            f"{label} SHA256 mismatch: {observed}"
        )


def _text(
    value: object,
    *,
    label: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value
    ):
        raise PublicReferenceMetadataError(
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
        raise PublicReferenceMetadataError(
            f"{label} contains TSV control characters"
        )

    return value


def _positive_int(
    value: object,
    *,
    label: str,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise PublicReferenceMetadataError(
            f"{label} must be a positive integer"
        )

    try:
        parsed = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        raise PublicReferenceMetadataError(
            f"{label} must be a positive integer"
        ) from None

    if parsed <= 0:
        raise PublicReferenceMetadataError(
            f"{label} must be a positive integer"
        )

    return parsed


def _parse_json_object(
    payload: bytes,
    *,
    label: str,
) -> Mapping[str, Any]:
    try:
        value = json.loads(
            payload.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise PublicReferenceMetadataError(
            f"{label} is not valid UTF-8 JSON"
        ) from None

    if not isinstance(
        value,
        dict,
    ):
        raise PublicReferenceMetadataError(
            f"{label} must be a JSON object"
        )

    return value


def _expected_first_public_n(
    rank: int,
) -> int:
    for panel_size in PRESET_PANEL_SIZES:
        if rank <= panel_size:
            return panel_size

    raise PublicReferenceMetadataError(
        f"rank outside reference ladder: {rank}"
    )


def _parse_winning_ladder(
    payload: bytes,
) -> list[dict[str, object]]:
    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise PublicReferenceMetadataError(
            "winning ladder is not UTF-8"
        ) from None

    reader = csv.DictReader(
        io.StringIO(text),
        delimiter="\t",
    )

    expected_fields = [
        "rank",
        "accession",
        "first_public_panel_n",
    ]

    if reader.fieldnames != expected_fields:
        raise PublicReferenceMetadataError(
            "winning ladder schema changed"
        )

    rows: list[dict[str, object]] = []
    observed_accessions: set[str] = set()

    for expected_rank, row in enumerate(
        reader,
        1,
    ):
        try:
            rank = int(
                row["rank"]
            )
            first_public_n = int(
                row["first_public_panel_n"]
            )
        except (
            TypeError,
            ValueError,
        ):
            raise PublicReferenceMetadataError(
                "winning ladder contains non-integer rank metadata"
            ) from None

        if rank != expected_rank:
            raise PublicReferenceMetadataError(
                "winning ladder rank sequence changed"
            )

        accession = _text(
            row["accession"],
            label=f"rank {rank} accession",
        )

        if _GCA_RE.fullmatch(accession) is None:
            raise PublicReferenceMetadataError(
                f"rank {rank} accession is not canonical GCA"
            )

        if accession in observed_accessions:
            raise PublicReferenceMetadataError(
                f"duplicate ladder accession: {accession}"
            )

        if first_public_n != _expected_first_public_n(
            rank
        ):
            raise PublicReferenceMetadataError(
                f"rank {rank} first_public_panel_n changed"
            )

        observed_accessions.add(
            accession
        )

        rows.append(
            {
                "selection_rank": rank,
                "first_public_panel_n": first_public_n,
                "genbank_assembly_accession": accession,
            }
        )

    if len(rows) != REFERENCE_ROW_COUNT:
        raise PublicReferenceMetadataError(
            "winning ladder must contain exactly 500 rows"
        )

    return rows


def _parse_species_mapping(
    payload: bytes,
    *,
    expected_sha256: str,
    selected_accessions: set[str],
) -> dict[str, int]:
    _require_payload_sha256(
        payload,
        expected_sha256,
        label="species mapping",
    )

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise PublicReferenceMetadataError(
            "species mapping is not UTF-8"
        ) from None

    reader = csv.DictReader(
        io.StringIO(text),
        delimiter="\t",
    )

    required = {
        "canonical_genbank_assembly_accession",
        "species_taxid",
    }

    if not required.issubset(
        set(reader.fieldnames or ())
    ):
        raise PublicReferenceMetadataError(
            "species mapping schema lacks required fields"
        )

    mapping: dict[str, int] = {}

    for row in reader:
        accession = row[
            "canonical_genbank_assembly_accession"
        ]

        if accession not in selected_accessions:
            continue

        if accession in mapping:
            raise PublicReferenceMetadataError(
                f"duplicate species mapping: {accession}"
            )

        mapping[
            accession
        ] = _positive_int(
            row["species_taxid"],
            label=f"{accession} species TaxID",
        )

    if set(mapping) != selected_accessions:
        raise PublicReferenceMetadataError(
            "species mapping does not exactly cover selected accessions"
        )

    if len(
        set(mapping.values())
    ) != REFERENCE_ROW_COUNT:
        raise PublicReferenceMetadataError(
            "selected reference ladder must represent 500 distinct species"
        )

    return mapping


def _parse_source_records(
    payload: bytes,
    *,
    expected_sha256: str,
    selected_accessions: set[str],
) -> dict[str, dict[str, object]]:
    _require_payload_sha256(
        payload,
        expected_sha256,
        label="source snapshot",
    )

    records: dict[str, dict[str, object]] = {}

    try:
        text = payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise PublicReferenceMetadataError(
            "source snapshot is not UTF-8"
        ) from None

    for line_number, line in enumerate(
        text.splitlines(),
        1,
    ):
        if not line:
            continue

        try:
            record = json.loads(
                line
            )
        except json.JSONDecodeError:
            raise PublicReferenceMetadataError(
                f"invalid source JSON at line {line_number}"
            ) from None

        if not isinstance(
            record,
            dict,
        ):
            raise PublicReferenceMetadataError(
                f"source row {line_number} is not an object"
            )

        accession = record.get(
            "accession"
        )

        if accession not in selected_accessions:
            continue

        if accession in records:
            raise PublicReferenceMetadataError(
                f"duplicate source record: {accession}"
            )

        records[
            accession
        ] = record

    if set(records) != selected_accessions:
        raise PublicReferenceMetadataError(
            "source snapshot does not exactly cover selected accessions"
        )

    return records


def _taxonomy_scientific_names(
    payload: bytes,
    *,
    expected_sha256: str,
    wanted_taxids: set[int],
) -> dict[int, str]:
    _require_payload_sha256(
        payload,
        expected_sha256,
        label="taxonomy snapshot",
    )

    try:
        archive = tarfile.open(
            fileobj=io.BytesIO(payload),
            mode="r:gz",
        )
    except tarfile.TarError:
        raise PublicReferenceMetadataError(
            "taxonomy snapshot is not a valid gzip tar archive"
        ) from None

    with archive:
        try:
            member = archive.getmember(
                "names.dmp"
            )
        except KeyError:
            raise PublicReferenceMetadataError(
                "taxonomy snapshot lacks names.dmp"
            ) from None

        handle = archive.extractfile(
            member
        )

        if handle is None:
            raise PublicReferenceMetadataError(
                "taxonomy names.dmp could not be read"
            )

        names: dict[int, str] = {}

        for raw_line in handle:
            try:
                line = raw_line.decode(
                    "utf-8"
                )
            except UnicodeDecodeError:
                raise PublicReferenceMetadataError(
                    "taxonomy names.dmp is not UTF-8"
                ) from None

            fields = [
                value.strip()
                for value in line.split("|")
            ]

            if len(fields) < 4:
                raise PublicReferenceMetadataError(
                    "malformed taxonomy names.dmp row"
                )

            taxid_text = fields[0]
            name_text = fields[1]
            name_class = fields[3]

            if name_class != "scientific name":
                continue

            if not taxid_text.isdigit():
                raise PublicReferenceMetadataError(
                    "taxonomy names.dmp contains malformed TaxID"
                )

            taxid = int(
                taxid_text
            )

            if taxid not in wanted_taxids:
                continue

            if taxid in names:
                raise PublicReferenceMetadataError(
                    f"duplicate scientific name for TaxID {taxid}"
                )

            names[
                taxid
            ] = _text(
                name_text,
                label=f"TaxID {taxid} scientific name",
            )

    if set(names) != wanted_taxids:
        missing = sorted(
            wanted_taxids - set(names)
        )

        raise PublicReferenceMetadataError(
            "taxonomy snapshot lacks scientific names for TaxIDs: "
            + ",".join(
                str(value)
                for value in missing
            )
        )

    return names


def _source_public_fields(
    record: Mapping[str, object],
    *,
    accession: str,
) -> dict[str, object]:
    try:
        assembly_info = record[
            "assembly_info"
        ]
        organism = record[
            "organism"
        ]
    except KeyError:
        raise PublicReferenceMetadataError(
            f"{accession} source record lacks required object"
        ) from None

    if not isinstance(
        assembly_info,
        Mapping,
    ):
        raise PublicReferenceMetadataError(
            f"{accession} assembly_info is malformed"
        )

    if not isinstance(
        organism,
        Mapping,
    ):
        raise PublicReferenceMetadataError(
            f"{accession} organism is malformed"
        )

    biosample_obj = assembly_info.get(
        "biosample"
    )

    if not isinstance(
        biosample_obj,
        Mapping,
    ):
        raise PublicReferenceMetadataError(
            f"{accession} BioSample object is malformed"
        )

    biosample = _text(
        biosample_obj.get(
            "accession"
        ),
        label=f"{accession} BioSample",
    )

    if _BIOSAMPLE_RE.fullmatch(
        biosample
    ) is None:
        raise PublicReferenceMetadataError(
            f"{accession} BioSample is malformed"
        )

    release_date = _text(
        assembly_info.get(
            "release_date"
        ),
        label=f"{accession} assembly release date",
    )

    if _DATE_RE.fullmatch(
        release_date
    ) is None:
        raise PublicReferenceMetadataError(
            f"{accession} assembly release date is malformed"
        )

    return {
        "biosample_accession":
            biosample,
        "ncbi_organism_name":
            _text(
                organism.get(
                    "organism_name"
                ),
                label=f"{accession} NCBI organism name",
            ),
        "ncbi_organism_taxid":
            _positive_int(
                organism.get(
                    "tax_id"
                ),
                label=f"{accession} NCBI organism TaxID",
            ),
        "assembly_name":
            _text(
                assembly_info.get(
                    "assembly_name"
                ),
                label=f"{accession} assembly name",
            ),
        "submitter":
            _text(
                assembly_info.get(
                    "submitter"
                ),
                label=f"{accession} submitter",
            ),
        "assembly_release_date":
            release_date,
    }


def _serialize_rows(
    fields: tuple[str, ...],
    rows: list[Mapping[str, object]],
) -> bytes:
    lines = [
        "\t".join(
            fields
        )
    ]

    for row_number, row in enumerate(
        rows,
        1,
    ):
        if set(row) != set(fields):
            raise PublicReferenceMetadataError(
                f"row {row_number} schema changed"
            )

        values: list[str] = []

        for field in fields:
            value = str(
                row[field]
            )

            _text(
                value,
                label=f"row {row_number} field {field}",
            )

            values.append(
                value
            )

        lines.append(
            "\t".join(
                values
            )
        )

    return (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def build_reference_metadata_ladder(
    *,
    winning_ladder_payload: bytes,
    source_snapshot_payload: bytes,
    species_mapping_payload: bytes,
    taxonomy_snapshot_payload: bytes,
    panel_summary_payload: bytes,
    panel_provenance_payload: bytes,
    expected_winning_ladder_file_sha256: str,
    expected_winning_ladder_sha256: str,
    expected_panel_summary_sha256: str,
    expected_panel_provenance_sha256: str,
    expected_source_snapshot_sha256: str,
    expected_species_mapping_sha256: str,
    expected_taxonomy_snapshot_sha256: str,
) -> bytes:
    _require_payload_sha256(
        winning_ladder_payload,
        expected_winning_ladder_file_sha256,
        label="public winning-ladder TSV",
    )

    ladder = _parse_winning_ladder(
        winning_ladder_payload
    )

    selected_accessions = {
        str(
            row[
                "genbank_assembly_accession"
            ]
        )
        for row in ladder
    }

    species_by_accession = _parse_species_mapping(
        species_mapping_payload,
        expected_sha256=(
            expected_species_mapping_sha256
        ),
        selected_accessions=selected_accessions,
    )

    source_by_accession = _parse_source_records(
        source_snapshot_payload,
        expected_sha256=(
            expected_source_snapshot_sha256
        ),
        selected_accessions=selected_accessions,
    )

    _require_payload_sha256(
        panel_summary_payload,
        expected_panel_summary_sha256,
        label="panel generation summary",
    )

    _require_payload_sha256(
        panel_provenance_payload,
        expected_panel_provenance_sha256,
        label="panel generation provenance",
    )

    summary = _parse_json_object(
        panel_summary_payload,
        label="panel generation summary",
    )

    provenance = _parse_json_object(
        panel_provenance_payload,
        label="panel generation provenance",
    )

    logical_ladder_sha = _require_sha256(
        expected_winning_ladder_sha256,
        label="logical winning-ladder SHA256",
    )

    if summary.get(
        "winning_ladder_sha256"
    ) != logical_ladder_sha:
        raise PublicReferenceMetadataError(
            "panel summary logical winning-ladder SHA256 mismatch"
        )

    if provenance.get(
        "winning_ladder_sha256"
    ) != logical_ladder_sha:
        raise PublicReferenceMetadataError(
            "panel provenance logical winning-ladder SHA256 mismatch"
        )

    if summary.get(
        "winning_ladder_accession_count"
    ) != REFERENCE_ROW_COUNT:
        raise PublicReferenceMetadataError(
            "panel summary accession count changed"
        )

    if summary.get(
        "winning_ladder_n"
    ) != REFERENCE_ROW_COUNT:
        raise PublicReferenceMetadataError(
            "panel summary ladder N changed"
        )

    if summary.get(
        "monthly_release_assigned"
    ) is not False:
        raise PublicReferenceMetadataError(
            "reference panel must not carry a monthly release"
        )

    selector = _text(
        summary.get(
            "selector"
        ),
        label="selector",
    )

    if (
        selector != "OPS"
        or provenance.get(
            "winning_selector"
        ) != selector
    ):
        raise PublicReferenceMetadataError(
            "reference selector identity changed"
        )

    selector_version = _text(
        summary.get(
            "selector_version"
        ),
        label="selector version",
    )

    architecture_schema_version = _positive_int(
        summary.get(
            "architecture_schema_version"
        ),
        label="architecture schema version",
    )

    execution_commit = _text(
        provenance.get(
            "execution_commit"
        ),
        label="panel execution commit",
    )

    if _GIT_COMMIT_RE.fullmatch(
        execution_commit
    ) is None:
        raise PublicReferenceMetadataError(
            "panel execution commit is malformed"
        )

    source_sha = _require_sha256(
        expected_source_snapshot_sha256,
        label="source snapshot SHA256",
    )

    taxonomy_sha = _require_sha256(
        expected_taxonomy_snapshot_sha256,
        label="taxonomy snapshot SHA256",
    )

    species_names = _taxonomy_scientific_names(
        taxonomy_snapshot_payload,
        expected_sha256=taxonomy_sha,
        wanted_taxids=set(
            species_by_accession.values()
        ),
    )

    output_rows: list[dict[str, object]] = []

    for ladder_row in ladder:
        accession = str(
            ladder_row[
                "genbank_assembly_accession"
            ]
        )

        species_taxid = species_by_accession[
            accession
        ]

        source_fields = _source_public_fields(
            source_by_accession[
                accession
            ],
            accession=accession,
        )

        output_rows.append(
            {
                "selection_rank":
                    ladder_row[
                        "selection_rank"
                    ],
                "first_public_panel_n":
                    ladder_row[
                        "first_public_panel_n"
                    ],
                "genbank_assembly_accession":
                    accession,
                **source_fields,
                "bacselect_species_name":
                    species_names[
                        species_taxid
                    ],
                "bacselect_species_taxid":
                    species_taxid,
                "panel_identity":
                    REFERENCE_IDENTITY,
                "selector":
                    selector,
                "selector_version":
                    selector_version,
                "architecture_schema_version":
                    architecture_schema_version,
                "source_snapshot_sha256":
                    source_sha,
                "taxonomy_snapshot_sha256":
                    taxonomy_sha,
                "execution_git_commit":
                    execution_commit,
                "ncbi_assembly_url":
                    (
                        "https://www.ncbi.nlm.nih.gov/assembly/"
                        f"{accession}/"
                    ),
            }
        )

    return _serialize_rows(
        REFERENCE_METADATA_FIELDS,
        output_rows,
    )


def serialize_public_panel(
    metadata_ladder_payload: bytes,
    *,
    panel_size: int,
) -> bytes:
    if (
        isinstance(
            panel_size,
            bool,
        )
        or not isinstance(
            panel_size,
            int,
        )
        or panel_size < CUSTOM_N_MIN
        or panel_size > CUSTOM_N_MAX
    ):
        raise PublicReferenceMetadataError(
            "panel_size must be an integer from 10 through 500"
        )

    try:
        text = metadata_ladder_payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError:
        raise PublicReferenceMetadataError(
            "metadata ladder is not UTF-8"
        ) from None

    reader = csv.DictReader(
        io.StringIO(text),
        delimiter="\t",
    )

    if reader.fieldnames != list(
        REFERENCE_METADATA_FIELDS
    ):
        raise PublicReferenceMetadataError(
            "metadata ladder schema changed"
        )

    rows = list(
        reader
    )

    if len(rows) != REFERENCE_ROW_COUNT:
        raise PublicReferenceMetadataError(
            "metadata ladder must contain exactly 500 rows"
        )

    output: list[dict[str, object]] = []

    for expected_rank, row in enumerate(
        rows,
        1,
    ):
        try:
            rank = int(
                row[
                    "selection_rank"
                ]
            )
        except (
            TypeError,
            ValueError,
        ):
            raise PublicReferenceMetadataError(
                "metadata ladder rank is malformed"
            ) from None

        if rank != expected_rank:
            raise PublicReferenceMetadataError(
                "metadata ladder rank sequence changed"
            )

        if rank > panel_size:
            continue

        output.append(
            {
                "panel_identity":
                    row[
                        "panel_identity"
                    ],
                "panel_size":
                    panel_size,
                "selection_rank":
                    rank,
                "genbank_assembly_accession":
                    row[
                        "genbank_assembly_accession"
                    ],
                "biosample_accession":
                    row[
                        "biosample_accession"
                    ],
                "ncbi_organism_name":
                    row[
                        "ncbi_organism_name"
                    ],
                "ncbi_organism_taxid":
                    row[
                        "ncbi_organism_taxid"
                    ],
                "bacselect_species_name":
                    row[
                        "bacselect_species_name"
                    ],
                "bacselect_species_taxid":
                    row[
                        "bacselect_species_taxid"
                    ],
                "assembly_name":
                    row[
                        "assembly_name"
                    ],
                "submitter":
                    row[
                        "submitter"
                    ],
                "assembly_release_date":
                    row[
                        "assembly_release_date"
                    ],
                "selector":
                    row[
                        "selector"
                    ],
                "selector_version":
                    row[
                        "selector_version"
                    ],
                "architecture_schema_version":
                    row[
                        "architecture_schema_version"
                    ],
                "source_snapshot_sha256":
                    row[
                        "source_snapshot_sha256"
                    ],
                "taxonomy_snapshot_sha256":
                    row[
                        "taxonomy_snapshot_sha256"
                    ],
                "execution_git_commit":
                    row[
                        "execution_git_commit"
                    ],
                "ncbi_assembly_url":
                    row[
                        "ncbi_assembly_url"
                    ],
            }
        )

    if len(output) != panel_size:
        raise PublicReferenceMetadataError(
            "public panel serialization row count mismatch"
        )

    return _serialize_rows(
        PUBLIC_PANEL_FIELDS,
        output,
    )
