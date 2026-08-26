from pathlib import Path

import pytest

from bacselect.source_taxonomy import (
    Taxonomy,
    TaxonomyError,
    dmp_fields,
)


def write_taxonomy(
    root: Path,
    *,
    nodes: str,
    merged: str = "",
    deleted: str = "",
) -> Taxonomy:
    nodes_path = root / "nodes.dmp"
    merged_path = root / "merged.dmp"
    delnodes_path = root / "delnodes.dmp"

    nodes_path.write_text(
        nodes,
        encoding="utf-8",
    )

    merged_path.write_text(
        merged,
        encoding="utf-8",
    )

    delnodes_path.write_text(
        deleted,
        encoding="utf-8",
    )

    return Taxonomy(
        nodes_path=nodes_path,
        merged_path=merged_path,
        delnodes_path=delnodes_path,
    )


def base_nodes() -> str:
    return (
        "1\t|\t1\t|\tno rank\t|\n"
        "2\t|\t1\t|\tsuperkingdom\t|\n"
        "10\t|\t2\t|\tgenus\t|\n"
        "11\t|\t10\t|\tspecies\t|\n"
        "12\t|\t11\t|\tstrain\t|\n"
        "13\t|\t11\t|\tsubspecies\t|\n"
    )


def test_dmp_fields_matches_frozen_parser():
    assert dmp_fields(
        "11\t|\t10\t|\tspecies\t|\n"
    ) == [
        "11",
        "10",
        "species",
        "",
    ]


def test_current_taxid_normalizes_without_steps(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
    )

    assert taxonomy.normalize(
        12
    ) == (
        12,
        "PASS",
        0,
    )


def test_single_merged_taxid(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
        merged=(
            "20\t|\t12\t|\n"
        ),
    )

    assert taxonomy.normalize(
        20
    ) == (
        12,
        "PASS",
        1,
    )


def test_multi_step_merged_taxid(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
        merged=(
            "20\t|\t21\t|\n"
            "21\t|\t12\t|\n"
        ),
    )

    assert taxonomy.normalize(
        20
    ) == (
        12,
        "PASS",
        2,
    )


def test_merged_cycle_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
        merged=(
            "20\t|\t21\t|\n"
            "21\t|\t20\t|\n"
        ),
    )

    assert taxonomy.normalize(
        20
    ) == (
        None,
        "MERGED_CYCLE",
        2,
    )


def test_deleted_taxid_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
        deleted=(
            "30\t|\n"
        ),
    )

    assert taxonomy.normalize(
        30
    ) == (
        None,
        "DELETED",
        0,
    )


def test_merged_to_deleted_taxid_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
        merged=(
            "20\t|\t30\t|\n"
        ),
        deleted=(
            "30\t|\n"
        ),
    )

    assert taxonomy.normalize(
        20
    ) == (
        None,
        "DELETED",
        1,
    )


def test_missing_taxid_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
    )

    assert taxonomy.normalize(
        999
    ) == (
        None,
        "MISSING",
        0,
    )


def test_species_resolves_to_itself(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
    )

    assert taxonomy.species_ancestor(
        11
    ) == (
        11,
        "PASS",
    )


@pytest.mark.parametrize(
    "taxid",
    [
        12,
        13,
    ],
)
def test_descendant_resolves_to_species(
    tmp_path,
    taxid,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
    )

    assert taxonomy.species_ancestor(
        taxid
    ) == (
        11,
        "PASS",
    )


def test_rank_must_be_exactly_species(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=(
            "1\t|\t1\t|\tno rank\t|\n"
            "2\t|\t1\t|\tsuperkingdom\t|\n"
            "10\t|\t2\t|\tspecies group\t|\n"
            "11\t|\t10\t|\tstrain\t|\n"
        ),
    )

    assert taxonomy.species_ancestor(
        11
    ) == (
        None,
        "NO_SPECIES_ANCESTOR",
    )


def test_root_without_species_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=base_nodes(),
    )

    assert taxonomy.species_ancestor(
        2
    ) == (
        None,
        "NO_SPECIES_ANCESTOR",
    )


def test_missing_lineage_node_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=(
            "1\t|\t1\t|\tno rank\t|\n"
            "20\t|\t999\t|\tstrain\t|\n"
        ),
    )

    assert taxonomy.species_ancestor(
        20
    ) == (
        None,
        "MISSING_NODE",
    )


def test_lineage_cycle_is_rejected(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=(
            "1\t|\t1\t|\tno rank\t|\n"
            "20\t|\t21\t|\tstrain\t|\n"
            "21\t|\t20\t|\tgenus\t|\n"
        ),
    )

    assert taxonomy.species_ancestor(
        20
    ) == (
        None,
        "LINEAGE_CYCLE",
    )


def test_malformed_root_is_rejected(
    tmp_path,
):
    with pytest.raises(
        TaxonomyError,
        match="root TaxID 1",
    ):
        write_taxonomy(
            tmp_path,
            nodes=(
                "1\t|\t2\t|\tno rank\t|\n"
                "2\t|\t2\t|\tspecies\t|\n"
            ),
        )


def test_missing_root_is_rejected(
    tmp_path,
):
    with pytest.raises(
        TaxonomyError,
        match="root TaxID 1",
    ):
        write_taxonomy(
            tmp_path,
            nodes=(
                "2\t|\t2\t|\tspecies\t|\n"
            ),
        )


def test_malformed_merged_line_is_rejected(
    tmp_path,
):
    with pytest.raises(
        TaxonomyError,
        match="malformed merged.dmp line",
    ):
        write_taxonomy(
            tmp_path,
            nodes=base_nodes(),
            merged="|\n",
        )


def test_malformed_deleted_line_is_rejected(
    tmp_path,
):
    with pytest.raises(
        TaxonomyError,
        match="malformed delnodes.dmp line",
    ):
        write_taxonomy(
            tmp_path,
            nodes=base_nodes(),
            deleted="|\n",
        )


def test_malformed_nodes_line_is_rejected(
    tmp_path,
):
    with pytest.raises(
        TaxonomyError,
        match="malformed nodes.dmp line",
    ):
        write_taxonomy(
            tmp_path,
            nodes=(
                "1\t|\t1\t|\tno rank\t|\n"
                "20\t|\n"
            ),
        )


def test_empty_rank_field_matches_frozen_parser(
    tmp_path,
):
    taxonomy = write_taxonomy(
        tmp_path,
        nodes=(
            "1\t|\t1\t|\tno rank\t|\n"
            "20\t|\t1\t|\t\t|\n"
        ),
    )

    assert taxonomy.normalize(
        20
    ) == (
        20,
        "PASS",
        0,
    )

    assert taxonomy.species_ancestor(
        20
    ) == (
        None,
        "NO_SPECIES_ANCESTOR",
    )
