import numpy as np
import pytest

from bacselect.sr import sr_ladder
from bacselect.tie import species_tie_key, tie_key


def test_first_species_uses_equal_weight_species_centroids() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.0],
            [0.0],
            [0.0],
            [0.6],
            [1.0],
        ]
    )
    species = ["A", "A", "A", "A", "B", "C"]
    accessions = ["A0", "A1", "A2", "A3", "B0", "C0"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=1,
    )

    assert accessions[ladder[0]] == "B0"


def test_first_species_exact_tie_uses_species_key() -> None:
    coordinates = np.array(
        [
            [0.0],
            [1.0],
        ]
    )
    species = ["A", "B"]
    accessions = ["A0", "B0"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=1,
    )

    expected_species = min(
        [
            ("A", species_tie_key(["A0"])),
            ("B", species_tie_key(["B0"])),
        ],
        key=lambda item: item[1],
    )[0]

    assert species[ladder[0]] == expected_species


def test_first_genome_exact_tie_uses_genome_key() -> None:
    coordinates = np.array(
        [
            [0.0],
            [1.0],
        ]
    )
    species = ["A", "A"]
    accessions = ["A0", "A1"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=1,
    )

    expected = min(
        accessions,
        key=tie_key,
    )

    assert accessions[ladder[0]] == expected


def test_subsequent_species_exact_tie_uses_species_key() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.5],
            [1.0],
        ]
    )
    species = ["A", "B", "C"]
    accessions = ["A0", "B0", "C0"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=2,
    )

    assert accessions[ladder[0]] == "B0"

    expected_second_species = min(
        [
            ("A", species_tie_key(["A0"])),
            ("C", species_tie_key(["C0"])),
        ],
        key=lambda item: item[1],
    )[0]

    assert species[ladder[1]] == expected_second_species


def test_selected_genomes_contribute_zero_to_species_residual() -> None:
    coordinates = np.array(
        [
            [0.0],
            [1.0],
            [0.2],
            [0.8],
        ]
    )
    species = ["A", "A", "B", "C"]
    accessions = ["A0", "A1", "B0", "C0"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=2,
    )

    assert species[ladder[0]] == "A"

    first_coordinate = coordinates[ladder[0], 0]

    if first_coordinate == 0.0:
        assert species[ladder[1]] == "C"
    else:
        assert first_coordinate == 1.0
        assert species[ladder[1]] == "B"


def test_species_can_be_selected_more_than_once() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.5],
            [1.0],
        ]
    )
    species = ["A", "A", "A"]
    accessions = ["A0", "A1", "A2"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=3,
    )

    assert len(ladder) == 3
    assert len(set(ladder.tolist())) == 3
    assert {species[index] for index in ladder} == {"A"}


def test_sr_ladder_is_nested() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.2],
            [0.4],
            [0.6],
            [0.8],
            [1.0],
        ]
    )
    species = ["A", "A", "B", "B", "C", "C"]
    accessions = ["A0", "A1", "B0", "B1", "C0", "C1"]

    ladder_3 = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=3,
    )

    ladder_6 = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=6,
    )

    np.testing.assert_array_equal(
        ladder_3,
        ladder_6[:3],
    )


def test_sr_never_reselects_genome() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.1],
            [0.5],
            [0.9],
            [1.0],
        ]
    )
    species = ["A", "A", "B", "C", "C"]
    accessions = ["A0", "A1", "B0", "C0", "C1"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=5,
    )

    assert len(set(ladder.tolist())) == 5


def test_sr_is_input_order_invariant() -> None:
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

    expected_indices = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=6,
    )

    expected_accessions = [
        str(accessions[index])
        for index in expected_indices
    ]

    permutation = np.array([5, 2, 0, 4, 1, 3])

    observed_indices = sr_ladder(
        coordinates[permutation],
        species[permutation],
        accessions[permutation],
        max_n=6,
    )

    observed_accessions = [
        str(accessions[permutation][index])
        for index in observed_indices
    ]

    assert observed_accessions == expected_accessions


def test_sr_rejects_duplicate_accessions() -> None:
    with pytest.raises(ValueError, match="unique"):
        sr_ladder(
            [[0.0], [1.0]],
            ["A", "B"],
            ["same", "same"],
            max_n=1,
        )


def test_sr_rejects_panel_larger_than_genome_count() -> None:
    with pytest.raises(ValueError, match="number of eligible genomes"):
        sr_ladder(
            [[0.0], [1.0]],
            ["A", "B"],
            ["A0", "B0"],
            max_n=3,
        )


def test_species_selection_uses_mean_residual_not_sum() -> None:
    coordinates = np.array(
        [
            [0.2],
            [0.2],
            [0.2],
            [0.2],
            [0.5],
            [1.0],
        ]
    )
    species = ["A", "A", "A", "A", "B", "C"]
    accessions = ["A0", "A1", "A2", "A3", "B0", "C0"]

    ladder = sr_ladder(
        coordinates,
        species,
        accessions,
        max_n=2,
    )

    # B is selected first. After that:
    # A mean residual = 0.09, A summed residual = 0.36.
    # C mean and summed residual = 0.25.
    # The frozen mean rule therefore selects C, whereas a sum would select A.
    assert accessions[ladder[0]] == "B0"
    assert species[ladder[1]] == "C"


def test_exhausted_species_is_removed_from_competition() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.5],
            [1.0],
        ]
    )
    species = ["A", "B", "C"]
    accessions = ["A0", "B0", "C0"]

    ladder = sr_ladder(
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
    assert set(selected_species) == {"A", "B", "C"}
