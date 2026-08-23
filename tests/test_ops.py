import numpy as np
import pytest

from bacselect.ops import (
    ops_ladder,
    ops_species_representatives,
)
from bacselect.tie import tie_key


def test_species_representative_is_nearest_centroid() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.1],
            [0.4],
            [0.8],
        ]
    )
    species = ["A", "A", "A", "B"]
    accessions = ["A0", "A1", "A2", "B0"]

    representatives = ops_species_representatives(
        coordinates,
        species,
        accessions,
    )

    selected = {
        accessions[index]
        for index in representatives
    }

    assert selected == {"A1", "B0"}


def test_within_species_exact_tie_uses_frozen_hash() -> None:
    coordinates = np.array(
        [
            [0.0],
            [1.0],
        ]
    )
    species = ["A", "A"]
    accessions = ["GCA_A", "GCA_B"]

    representatives = ops_species_representatives(
        coordinates,
        species,
        accessions,
    )

    expected = min(
        accessions,
        key=tie_key,
    )

    assert accessions[representatives[0]] == expected


def test_ops_ladder_starts_nearest_global_centroid() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.4],
            [1.0],
        ]
    )
    species = ["A", "B", "C"]
    accessions = ["A0", "B0", "C0"]

    ladder = ops_ladder(
        coordinates,
        species,
        accessions,
        max_n=3,
    )

    observed = [
        accessions[index]
        for index in ladder
    ]

    assert observed == ["B0", "C0", "A0"]


def test_ops_ladder_is_nested() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.2],
            [0.5],
            [0.8],
            [1.0],
        ]
    )
    species = ["A", "B", "C", "D", "E"]
    accessions = ["A0", "B0", "C0", "D0", "E0"]

    ladder_3 = ops_ladder(
        coordinates,
        species,
        accessions,
        max_n=3,
    )

    ladder_5 = ops_ladder(
        coordinates,
        species,
        accessions,
        max_n=5,
    )

    np.testing.assert_array_equal(
        ladder_3,
        ladder_5[:3],
    )


def test_ops_selects_distinct_species() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.1],
            [0.4],
            [0.6],
            [0.9],
            [1.0],
        ]
    )
    species = ["A", "A", "B", "B", "C", "C"]
    accessions = [
        "A0",
        "A1",
        "B0",
        "B1",
        "C0",
        "C1",
    ]

    ladder = ops_ladder(
        coordinates,
        species,
        accessions,
        max_n=3,
    )

    selected_species = [
        species[index]
        for index in ladder
    ]

    assert len(selected_species) == 3
    assert len(set(selected_species)) == 3


def test_ops_is_input_order_invariant() -> None:
    coordinates = np.array(
        [
            [0.0, 0.2],
            [0.2, 0.0],
            [0.7, 0.8],
            [1.0, 0.9],
            [0.5, 0.4],
            [0.55, 0.6],
        ]
    )
    species = np.array(
        ["A", "A", "B", "B", "C", "C"],
        dtype=object,
    )
    accessions = np.array(
        ["A0", "A1", "B0", "B1", "C0", "C1"],
        dtype=object,
    )

    expected_indices = ops_ladder(
        coordinates,
        species,
        accessions,
        max_n=3,
    )

    expected_accessions = [
        str(accessions[index])
        for index in expected_indices
    ]

    permutation = np.array([5, 2, 0, 4, 1, 3])

    observed_indices = ops_ladder(
        coordinates[permutation],
        species[permutation],
        accessions[permutation],
        max_n=3,
    )

    observed_accessions = [
        str(accessions[permutation][index])
        for index in observed_indices
    ]

    assert observed_accessions == expected_accessions


def test_ops_rejects_duplicate_accessions() -> None:
    with pytest.raises(ValueError, match="unique"):
        ops_ladder(
            [[0.0], [1.0]],
            ["A", "B"],
            ["same", "same"],
            max_n=1,
        )


def test_ops_rejects_panel_larger_than_species_count() -> None:
    with pytest.raises(ValueError, match="number of species representatives"):
        ops_ladder(
            [[0.0], [1.0]],
            ["A", "A"],
            ["A0", "A1"],
            max_n=2,
        )
