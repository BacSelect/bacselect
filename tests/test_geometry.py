from fractions import Fraction

import numpy as np
import pytest

from bacselect.geometry import (
    species_balanced_percentile_matrix,
    species_balanced_percentiles,
    species_balanced_percentiles_exact,
)


def test_species_abundance_is_balanced_exactly() -> None:
    values = [0.0, 2.0, 10.0]
    species = ["A", "A", "B"]

    observed = species_balanced_percentiles_exact(values, species)

    assert observed == (
        Fraction(1, 8),
        Fraction(3, 8),
        Fraction(3, 4),
    )


def test_tied_values_receive_identical_coordinate() -> None:
    values = [1.0, 1.0, 1.0]
    species = ["A", "A", "B"]

    observed = species_balanced_percentiles_exact(values, species)

    assert observed == (
        Fraction(1, 2),
        Fraction(1, 2),
        Fraction(1, 2),
    )


def test_constant_feature_maps_to_half() -> None:
    observed = species_balanced_percentiles(
        [7.0, 7.0, 7.0, 7.0],
        ["A", "A", "B", "C"],
    )

    np.testing.assert_array_equal(
        observed,
        np.full(4, 0.5),
    )


def test_input_order_does_not_change_coordinates() -> None:
    values = np.array([8.0, 1.0, 4.0, 4.0, 10.0])
    species = np.array(["A", "A", "B", "C", "C"], dtype=object)

    expected = species_balanced_percentiles(values, species)

    permutation = np.array([4, 2, 0, 3, 1])
    permuted = species_balanced_percentiles(
        values[permutation],
        species[permutation],
    )

    restored = np.empty_like(permuted)
    restored[permutation] = permuted

    np.testing.assert_array_equal(restored, expected)


def test_matrix_transform_operates_columnwise() -> None:
    matrix = np.array(
        [
            [0.0, 10.0],
            [2.0, 10.0],
            [10.0, 20.0],
        ]
    )
    species = ["A", "A", "B"]

    observed = species_balanced_percentile_matrix(matrix, species)

    expected = np.array(
        [
            [0.125, 0.25],
            [0.375, 0.25],
            [0.75, 0.75],
        ]
    )

    np.testing.assert_array_equal(observed, expected)


def test_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        species_balanced_percentiles(
            [1.0, np.nan],
            ["A", "B"],
        )


def test_rejects_row_count_mismatch() -> None:
    with pytest.raises(ValueError, match="same number of rows"):
        species_balanced_percentiles(
            [1.0, 2.0],
            ["A"],
        )


def test_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        species_balanced_percentiles([], [])
