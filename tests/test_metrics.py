from fractions import Fraction

import numpy as np
import pytest

from bacselect.metrics import (
    MEDIAN,
    P95,
    coverage_summary,
    inverse_ecdf_quantile,
    nearest_panel_distances,
    species_balanced_weighted_mean,
    species_balanced_weighted_quantile,
    species_distance_statistics,
)


def test_nearest_panel_distances_are_euclidean() -> None:
    coordinates = np.array(
        [
            [0.0, 0.0],
            [3.0, 4.0],
            [6.0, 8.0],
        ]
    )

    observed = nearest_panel_distances(
        coordinates,
        [0, 2],
    )

    np.testing.assert_array_equal(
        observed,
        np.array([0.0, 5.0, 0.0]),
    )


def test_species_balanced_weighted_mean() -> None:
    distances = [0.0, 2.0, 3.0]
    species = ["A", "A", "B"]

    # Species A mean = 1; species B mean = 3.
    # Equal species weighting therefore gives mean = 2.
    observed = species_balanced_weighted_mean(
        distances,
        species,
    )

    assert observed == 2.0


def test_weighted_median_uses_species_balancing() -> None:
    distances = [1.0, 3.0, 2.0]
    species = ["A", "A", "B"]

    # Weights are 1/2, 1/2, 1. Total species weight = 2.
    # Sorted cumulative weights:
    # 1 -> 1/2
    # 2 -> 3/2
    # 3 -> 2
    # Median threshold = 1, so Q(1/2) = 2.
    assert species_balanced_weighted_quantile(
        distances,
        species,
        MEDIAN,
    ) == 2.0


def test_weighted_p95_uses_inverse_ecdf_without_interpolation() -> None:
    distances = [1.0, 3.0, 2.0]
    species = ["A", "A", "B"]

    # P95 threshold = 19/20 * 2 = 1.9 species-weight units.
    # The threshold is first reached at distance 3.
    assert species_balanced_weighted_quantile(
        distances,
        species,
        P95,
    ) == 3.0


def test_exact_quantile_boundary_returns_observed_value() -> None:
    distances = [1.0, 2.0, 3.0, 4.0]
    species = ["A", "A", "B", "B"]

    # Every genome has weight 1/2; total weight = 2.
    # The median threshold of 1 is reached exactly at distance 2.
    assert species_balanced_weighted_quantile(
        distances,
        species,
        MEDIAN,
    ) == 2.0


def test_unweighted_inverse_ecdf_does_not_interpolate() -> None:
    values = [1.0, 2.0, 3.0, 4.0]

    assert inverse_ecdf_quantile(values, MEDIAN) == 2.0
    assert inverse_ecdf_quantile(values, P95) == 4.0


def test_per_species_distance_statistics() -> None:
    distances = [0.0, 2.0, 3.0]
    species = ["A", "A", "B"]

    means, maxima = species_distance_statistics(
        distances,
        species,
    )

    np.testing.assert_array_equal(
        np.sort(means),
        np.array([1.0, 3.0]),
    )

    np.testing.assert_array_equal(
        np.sort(maxima),
        np.array([2.0, 3.0]),
    )


def test_complete_coverage_summary() -> None:
    distances = [0.0, 2.0, 3.0]
    species = ["A", "A", "B"]

    observed = coverage_summary(
        distances,
        species,
    )

    assert observed.weighted_mean == 2.0
    assert observed.weighted_median == 2.0
    assert observed.weighted_p95 == 3.0
    assert observed.unweighted_max == 3.0

    # Species means are [1, 3].
    assert observed.median_species_mean == 1.0
    assert observed.p95_species_mean == 3.0
    assert observed.max_species_mean == 3.0

    # Species maxima are [2, 3].
    assert observed.median_species_max == 2.0
    assert observed.p95_species_max == 3.0
    assert observed.max_species_max == 3.0


def test_weighted_metrics_are_input_order_invariant() -> None:
    distances = np.array([0.0, 2.0, 1.0, 4.0, 3.0])
    species = np.array(
        ["A", "A", "B", "C", "C"],
        dtype=object,
    )

    expected = coverage_summary(
        distances,
        species,
    )

    permutation = np.array([4, 1, 3, 0, 2])

    observed = coverage_summary(
        distances[permutation],
        species[permutation],
    )

    assert observed == expected


def test_weighted_quantile_handles_tied_values() -> None:
    distances = [1.0, 1.0, 1.0, 2.0]
    species = ["A", "A", "B", "C"]

    assert species_balanced_weighted_quantile(
        distances,
        species,
        Fraction(1, 2),
    ) == 1.0


def test_rejects_negative_distance() -> None:
    with pytest.raises(ValueError, match="negative"):
        coverage_summary(
            [0.0, -1.0],
            ["A", "B"],
        )


def test_rejects_species_row_mismatch() -> None:
    with pytest.raises(ValueError, match="same number of rows"):
        coverage_summary(
            [0.0, 1.0],
            ["A"],
        )


def test_rejects_duplicate_panel_indices() -> None:
    with pytest.raises(ValueError, match="unique"):
        nearest_panel_distances(
            [[0.0], [1.0]],
            [0, 0],
        )


def test_quantile_requires_exact_fraction() -> None:
    with pytest.raises(TypeError, match="Fraction"):
        inverse_ecdf_quantile(
            [1.0, 2.0],
            0.5,  # type: ignore[arg-type]
        )


def test_inverse_ecdf_quantile_boundaries() -> None:
    values = [1.0, 2.0, 3.0]

    assert inverse_ecdf_quantile(values, Fraction(0, 1)) == 1.0
    assert inverse_ecdf_quantile(values, Fraction(1, 1)) == 3.0


def test_weighted_quantile_boundaries() -> None:
    distances = [1.0, 2.0, 3.0]
    species = ["A", "A", "B"]

    assert species_balanced_weighted_quantile(
        distances,
        species,
        Fraction(0, 1),
    ) == 1.0

    assert species_balanced_weighted_quantile(
        distances,
        species,
        Fraction(1, 1),
    ) == 3.0


def test_weighted_quantile_with_unequal_species_sizes() -> None:
    distances = [
        1.0,
        2.0,
        3.0,
        4.0,
        5.0,
        6.0,
    ]
    species = [
        "A",
        "A",
        "A",
        "B",
        "B",
        "C",
    ]

    # Weights:
    # A genomes = 1/3 each
    # B genomes = 1/2 each
    # C genome  = 1
    # Total species weight = 3.
    #
    # At distance 4 cumulative weight is:
    # 1 + 1/2 = 3/2, exactly the median threshold.
    assert species_balanced_weighted_quantile(
        distances,
        species,
        MEDIAN,
    ) == 4.0


def test_nearest_panel_distances_are_panel_order_invariant() -> None:
    coordinates = np.array(
        [
            [0.0, 0.0],
            [1.0, 1.0],
            [2.0, 0.0],
            [4.0, 3.0],
        ]
    )

    forward = nearest_panel_distances(
        coordinates,
        [0, 3],
    )

    reverse = nearest_panel_distances(
        coordinates,
        [3, 0],
    )

    np.testing.assert_array_equal(forward, reverse)


def test_quantile_rejects_out_of_range_fraction() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        inverse_ecdf_quantile(
            [1.0, 2.0],
            Fraction(21, 20),
        )
