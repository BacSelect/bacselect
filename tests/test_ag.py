import numpy as np
import pytest

from bacselect.ag import ag_ladder
from bacselect.tie import tie_key


def test_ag_starts_nearest_global_centroid() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.4],
            [1.0],
        ]
    )
    accessions = ["A0", "B0", "C0"]

    ladder = ag_ladder(
        coordinates,
        accessions,
        max_n=3,
    )

    observed = [
        accessions[index]
        for index in ladder
    ]

    assert observed == ["B0", "C0", "A0"]


def test_ag_uses_all_genomes_in_global_centroid() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.0],
            [0.0],
            [0.8],
            [1.0],
        ]
    )
    accessions = ["A0", "A1", "A2", "B0", "C0"]

    ladder = ag_ladder(
        coordinates,
        accessions,
        max_n=1,
    )

    assert coordinates[ladder[0], 0] == 0.0


def test_ag_exact_tie_uses_frozen_hash() -> None:
    coordinates = np.array(
        [
            [0.0],
            [1.0],
        ]
    )
    accessions = ["GCA_A", "GCA_B"]

    ladder = ag_ladder(
        coordinates,
        accessions,
        max_n=1,
    )

    expected = min(
        accessions,
        key=tie_key,
    )

    assert accessions[ladder[0]] == expected


def test_ag_is_farthest_first_after_initial_selection() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.5],
            [1.0],
        ]
    )
    accessions = ["A0", "B0", "C0"]

    ladder = ag_ladder(
        coordinates,
        accessions,
        max_n=2,
    )

    assert accessions[ladder[0]] == "B0"

    expected_second = min(
        ["A0", "C0"],
        key=tie_key,
    )

    assert accessions[ladder[1]] == expected_second


def test_ag_ladder_is_nested() -> None:
    coordinates = np.array(
        [
            [0.0],
            [0.2],
            [0.5],
            [0.8],
            [1.0],
        ]
    )
    accessions = ["A0", "B0", "C0", "D0", "E0"]

    ladder_3 = ag_ladder(
        coordinates,
        accessions,
        max_n=3,
    )

    ladder_5 = ag_ladder(
        coordinates,
        accessions,
        max_n=5,
    )

    np.testing.assert_array_equal(
        ladder_3,
        ladder_5[:3],
    )


def test_ag_is_input_order_invariant() -> None:
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
    accessions = np.array(
        ["A0", "A1", "B0", "B1", "C0", "C1"],
        dtype=object,
    )

    expected_indices = ag_ladder(
        coordinates,
        accessions,
        max_n=6,
    )

    expected_accessions = [
        str(accessions[index])
        for index in expected_indices
    ]

    permutation = np.array([5, 2, 0, 4, 1, 3])

    observed_indices = ag_ladder(
        coordinates[permutation],
        accessions[permutation],
        max_n=6,
    )

    observed_accessions = [
        str(accessions[permutation][index])
        for index in observed_indices
    ]

    assert observed_accessions == expected_accessions


def test_ag_never_reselects_genome() -> None:
    ladder = ag_ladder(
        [[0.0], [0.2], [0.5], [0.8], [1.0]],
        ["A0", "B0", "C0", "D0", "E0"],
        max_n=5,
    )

    assert len(set(ladder.tolist())) == 5


def test_ag_rejects_duplicate_accessions() -> None:
    with pytest.raises(ValueError, match="unique"):
        ag_ladder(
            [[0.0], [1.0]],
            ["same", "same"],
            max_n=1,
        )


def test_ag_rejects_panel_larger_than_genome_count() -> None:
    with pytest.raises(ValueError, match="number of eligible genomes"):
        ag_ladder(
            [[0.0], [1.0]],
            ["A0", "B0"],
            max_n=3,
        )
