from __future__ import annotations

import hashlib
import io
import json
import tarfile

import pytest

from bacselect.public_reference_metadata import (
    METADATA_SCHEMA_VERSION,
    PUBLIC_PANEL_FIELDS,
    REFERENCE_METADATA_FIELDS,
    PublicReferenceMetadataError,
    build_reference_metadata_ladder,
    serialize_public_panel,
)


def sha256(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def first_public_n(
    rank: int,
) -> int:
    for n in (
        10,
        20,
        50,
        100,
        200,
        500,
    ):
        if rank <= n:
            return n

    raise AssertionError


def build_taxdump(
    species_taxids: list[int],
) -> bytes:
    names = ""

    for index, taxid in enumerate(
        species_taxids,
        1,
    ):
        names += (
            f"{taxid}\t|\tSpecies {index}\t|\t\t|\t"
            "scientific name\t|\n"
        )

    data = names.encode(
        "utf-8"
    )

    output = io.BytesIO()

    with tarfile.open(
        fileobj=output,
        mode="w:gz",
    ) as archive:
        info = tarfile.TarInfo(
            "names.dmp"
        )
        info.size = len(
            data
        )
        info.mtime = 0

        archive.addfile(
            info,
            io.BytesIO(
                data
            ),
        )

    return output.getvalue()


def build_inputs():
    accessions = [
        f"GCA_{index:09d}.1"
        for index in range(
            1,
            501,
        )
    ]

    species_taxids = [
        100000 + index
        for index in range(
            1,
            501,
        )
    ]

    ladder_lines = [
        "rank\taccession\tfirst_public_panel_n"
    ]

    species_lines = [
        "canonical_genbank_assembly_accession\tspecies_taxid"
    ]

    source_lines = []

    for rank, (
        accession,
        species_taxid,
    ) in enumerate(
        zip(
            accessions,
            species_taxids,
            strict=True,
        ),
        1,
    ):
        ladder_lines.append(
            f"{rank}\t{accession}\t{first_public_n(rank)}"
        )

        species_lines.append(
            f"{accession}\t{species_taxid}"
        )

        source_lines.append(
            json.dumps(
                {
                    "accession":
                        accession,
                    "assembly_info": {
                        "assembly_name":
                            f"ASM{rank}v1",
                        "biosample": {
                            "accession":
                                f"SAMN{rank:08d}",
                        },
                        "release_date":
                            "2025-01-01",
                        "submitter":
                            f"Submitter {rank}",
                    },
                    "organism": {
                        "organism_name":
                            (
                                "Source label differs"
                                if rank == 1
                                else f"Species {rank}"
                            ),
                        "tax_id":
                            (
                                999999
                                if rank == 1
                                else species_taxid
                            ),
                    },
                },
                sort_keys=True,
            )
        )

    ladder = (
        "\n".join(
            ladder_lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    species = (
        "\n".join(
            species_lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    source = (
        "\n".join(
            source_lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    taxdump = build_taxdump(
        species_taxids
    )

    ladder_file_sha = sha256(
        ladder
    )

    logical_ladder_sha = "f" * 64

    summary = (
        json.dumps(
            {
                "architecture_schema_version":
                    1,
                "monthly_release_assigned":
                    False,
                "selector":
                    "OPS",
                "selector_version":
                    "1.0.0",
                "winning_ladder_accession_count":
                    500,
                "winning_ladder_n":
                    500,
                "winning_ladder_sha256":
                    logical_ladder_sha,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    provenance = (
        json.dumps(
            {
                "execution_commit":
                    "a" * 40,
                "winning_ladder_sha256":
                    logical_ladder_sha,
                "winning_selector":
                    "OPS",
            },
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    return {
        "winning_ladder_payload":
            ladder,
        "source_snapshot_payload":
            source,
        "species_mapping_payload":
            species,
        "taxonomy_snapshot_payload":
            taxdump,
        "panel_summary_payload":
            summary,
        "panel_provenance_payload":
            provenance,
        "expected_winning_ladder_file_sha256":
            ladder_file_sha,
        "expected_winning_ladder_sha256":
            logical_ladder_sha,
        "expected_panel_summary_sha256":
            sha256(
                summary
            ),
        "expected_panel_provenance_sha256":
            sha256(
                provenance
            ),
        "expected_source_snapshot_sha256":
            sha256(
                source
            ),
        "expected_species_mapping_sha256":
            sha256(
                species
            ),
        "expected_taxonomy_snapshot_sha256":
            sha256(
                taxdump
            ),
    }


def test_schema_identity():
    assert (
        METADATA_SCHEMA_VERSION
        == "bacselect-selector-v1-reference-public-metadata-v1"
    )

    assert REFERENCE_METADATA_FIELDS[:3] == (
        "selection_rank",
        "first_public_panel_n",
        "genbank_assembly_accession",
    )

    assert PUBLIC_PANEL_FIELDS[:3] == (
        "panel_identity",
        "panel_size",
        "selection_rank",
    )


def test_build_reference_metadata_ladder():
    inputs = build_inputs()

    assert (
        inputs["expected_winning_ladder_file_sha256"]
        != inputs["expected_winning_ladder_sha256"]
    )

    payload = build_reference_metadata_ladder(
        **inputs
    )

    lines = payload.decode(
        "utf-8"
    ).splitlines()

    assert len(
        lines
    ) == 501

    assert lines[0].split(
        "\t"
    ) == list(
        REFERENCE_METADATA_FIELDS
    )

    first = dict(
        zip(
            REFERENCE_METADATA_FIELDS,
            lines[1].split(
                "\t"
            ),
            strict=True,
        )
    )

    assert first[
        "panel_identity"
    ] == "selector-v1-reference"

    assert first[
        "ncbi_organism_name"
    ] == "Source label differs"

    assert first[
        "bacselect_species_name"
    ] == "Species 1"

    assert first[
        "ncbi_organism_taxid"
    ] == "999999"

    assert first[
        "bacselect_species_taxid"
    ] == "100001"


def test_custom_n_panel_serialization():
    ladder = build_reference_metadata_ladder(
        **build_inputs()
    )

    panel = serialize_public_panel(
        ladder,
        panel_size=73,
    )

    lines = panel.decode(
        "utf-8"
    ).splitlines()

    assert len(
        lines
    ) == 74

    assert lines[0].split(
        "\t"
    ) == list(
        PUBLIC_PANEL_FIELDS
    )

    rows = [
        dict(
            zip(
                PUBLIC_PANEL_FIELDS,
                line.split(
                    "\t"
                ),
                strict=True,
            )
        )
        for line in lines[1:]
    ]

    assert {
        row[
            "panel_size"
        ]
        for row in rows
    } == {
        "73",
    }

    assert [
        int(
            row[
                "selection_rank"
            ]
        )
        for row in rows
    ] == list(
        range(
            1,
            74,
        )
    )

    assert "first_public_panel_n" not in rows[0]


@pytest.mark.parametrize(
    "panel_size",
    [
        9,
        501,
        True,
        73.0,
    ],
)
def test_invalid_panel_size_fails(
    panel_size,
):
    ladder = build_reference_metadata_ladder(
        **build_inputs()
    )

    with pytest.raises(
        PublicReferenceMetadataError,
        match="panel_size",
    ):
        serialize_public_panel(
            ladder,
            panel_size=panel_size,
        )


def test_source_snapshot_hash_mismatch_fails():
    inputs = build_inputs()

    inputs[
        "expected_source_snapshot_sha256"
    ] = "0" * 64

    with pytest.raises(
        PublicReferenceMetadataError,
        match="source snapshot SHA256 mismatch",
    ):
        build_reference_metadata_ladder(
            **inputs
        )


def test_duplicate_selected_species_fails():
    inputs = build_inputs()

    species = inputs[
        "species_mapping_payload"
    ].decode(
        "utf-8"
    )

    lines = species.splitlines()

    second = lines[2].split(
        "\t"
    )

    first = lines[1].split(
        "\t"
    )

    second[1] = first[1]

    lines[2] = "\t".join(
        second
    )

    modified = (
        "\n".join(
            lines
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    inputs[
        "species_mapping_payload"
    ] = modified

    inputs[
        "expected_species_mapping_sha256"
    ] = sha256(
        modified
    )

    with pytest.raises(
        PublicReferenceMetadataError,
        match="500 distinct species",
    ):
        build_reference_metadata_ladder(
            **inputs
        )


def test_logical_ladder_fingerprint_mismatch_fails():
    inputs = build_inputs()

    inputs[
        "expected_winning_ladder_sha256"
    ] = "0" * 64

    with pytest.raises(
        PublicReferenceMetadataError,
        match="logical winning-ladder SHA256 mismatch",
    ):
        build_reference_metadata_ladder(
            **inputs
        )


def test_panel_summary_hash_mismatch_fails():
    inputs = build_inputs()

    inputs[
        "expected_panel_summary_sha256"
    ] = "0" * 64

    with pytest.raises(
        PublicReferenceMetadataError,
        match="panel generation summary SHA256 mismatch",
    ):
        build_reference_metadata_ladder(
            **inputs
        )
