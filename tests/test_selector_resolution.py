"""Synthetic tests for blinded selector-v1 resolution primitives."""

from fractions import Fraction

import numpy as np
import pytest

from bacselect.geometry import (
    species_balanced_percentiles,
)
from bacselect.selector_resolution import (
    PANEL_SIZES,
    cross_matrix_nearest_panel_distances,
    exact_six_size_product,
    format_binary64,
    holdout_weighted_p95,
    project_matrix_through_baseline,
    project_values_through_baseline,
    projection_out_of_range_counts,
    resolve_exact_products,
)


def test_projection_reproduces_baseline_midpoint_geometry() -> None:
    baseline = np.array(
        [
            0.0,
            2.0,
            10.0,
        ]
    )

    species = [
        "A",
        "A",
        "B",
    ]

    observed = (
        project_values_through_baseline(
            baseline,
            species,
            baseline,
        )
    )

    expected = (
        species_balanced_percentiles(
            baseline,
            species,
        )
    )

    np.testing.assert_array_equal(
        observed,
        expected,
    )


def test_projection_below_minimum_maps_to_zero() -> None:
    observed = (
        project_values_through_baseline(
            [0.0, 2.0, 10.0],
            ["A", "A", "B"],
            [-1.0],
        )
    )

    np.testing.assert_array_equal(
        observed,
        [0.0],
    )


def test_projection_above_maximum_maps_to_one() -> None:
    observed = (
        project_values_through_baseline(
            [0.0, 2.0, 10.0],
            ["A", "A", "B"],
            [11.0],
        )
    )

    np.testing.assert_array_equal(
        observed,
        [1.0],
    )


def test_projection_between_values_has_no_interpolation() -> None:
    observed = (
        project_values_through_baseline(
            [0.0, 2.0, 10.0],
            ["A", "A", "B"],
            [1.0, 5.0],
        )
    )

    # Baseline weights are 1/2, 1/2 and 1.
    # Total species weight is 2.
    #
    # x=1: W_less=1/2 -> p=1/4.
    # x=5: W_less=1   -> p=1/2.
    np.testing.assert_array_equal(
        observed,
        [0.25, 0.5],
    )


def test_projection_exact_ties_use_midpoint_rule() -> None:
    observed = (
        project_values_through_baseline(
            [0.0, 2.0, 10.0],
            ["A", "A", "B"],
            [0.0, 2.0, 10.0],
        )
    )

    np.testing.assert_array_equal(
        observed,
        [
            0.125,
            0.375,
            0.75,
        ],
    )


def test_projection_unequal_species_sizes_are_exactly_balanced() -> None:
    baseline = [
        0.0,
        1.0,
        2.0,
        10.0,
        20.0,
        30.0,
    ]

    species = [
        "A",
        "A",
        "A",
        "B",
        "B",
        "C",
    ]

    observed = (
        project_values_through_baseline(
            baseline,
            species,
            [5.0, 15.0, 25.0],
        )
    )

    # Species weights:
    # A = 1 total
    # B = 1 total
    # C = 1 total
    #
    # x=5  => 1/3
    # x=15 => (1 + 1/2) / 3 = 1/2
    # x=25 => (1 + 1) / 3 = 2/3
    np.testing.assert_array_equal(
        observed,
        [
            float(Fraction(1, 3)),
            0.5,
            float(Fraction(2, 3)),
        ],
    )


def test_constant_baseline_feature_uses_midpoint_convention() -> None:
    observed = (
        project_values_through_baseline(
            [7.0, 7.0, 7.0, 7.0],
            ["A", "A", "B", "C"],
            [6.0, 7.0, 8.0],
        )
    )

    np.testing.assert_array_equal(
        observed,
        [
            0.0,
            0.5,
            1.0,
        ],
    )


def test_query_values_never_change_baseline_transform() -> None:
    baseline = [
        0.0,
        2.0,
        10.0,
    ]

    species = [
        "A",
        "A",
        "B",
    ]

    single = (
        project_values_through_baseline(
            baseline,
            species,
            [5.0],
        )
    )

    with_extra_queries = (
        project_values_through_baseline(
            baseline,
            species,
            [-100.0, 5.0, 100.0],
        )
    )

    assert (
        single[0]
        == with_extra_queries[1]
    )


def test_matrix_projection_is_columnwise() -> None:
    baseline = np.array(
        [
            [0.0, 10.0],
            [2.0, 10.0],
            [10.0, 20.0],
        ]
    )

    species = [
        "A",
        "A",
        "B",
    ]

    query = np.array(
        [
            [1.0, 10.0],
            [11.0, 15.0],
        ]
    )

    observed = (
        project_matrix_through_baseline(
            baseline,
            species,
            query,
        )
    )

    expected = np.array(
        [
            [0.25, 0.25],
            [1.0, 0.5],
        ]
    )

    np.testing.assert_array_equal(
        observed,
        expected,
    )


def test_projection_out_of_range_counts_are_per_feature() -> None:
    baseline = np.array(
        [
            [0.0, 10.0],
            [2.0, 20.0],
        ]
    )

    query = np.array(
        [
            [-1.0, 15.0],
            [1.0, 30.0],
            [3.0, 5.0],
        ]
    )

    below, above = (
        projection_out_of_range_counts(
            baseline,
            query,
        )
    )

    assert below == (
        1,
        1,
    )

    assert above == (
        1,
        1,
    )


def test_cross_matrix_distance_matches_hand_oracle() -> None:
    query = np.array(
        [
            [3.0, 4.0],
            [6.0, 8.0],
        ]
    )

    panel = np.array(
        [
            [0.0, 0.0],
            [6.0, 8.0],
        ]
    )

    observed = (
        cross_matrix_nearest_panel_distances(
            query,
            panel,
        )
    )

    np.testing.assert_array_equal(
        observed,
        [
            5.0,
            0.0,
        ],
    )


def test_cross_matrix_panel_is_not_augmented_with_queries() -> None:
    query = np.array(
        [
            [1.0, 1.0],
        ]
    )

    panel = np.array(
        [
            [0.0, 0.0],
        ]
    )

    observed = (
        cross_matrix_nearest_panel_distances(
            query,
            panel,
        )
    )

    assert observed[0] == pytest.approx(
        np.sqrt(2.0)
    )

    assert observed[0] != 0.0


def test_cross_matrix_chunk_size_does_not_change_arithmetic() -> None:
    query = np.array(
        [
            [0.0, 0.0],
            [1.0, 2.0],
            [3.0, 4.0],
            [5.0, 6.0],
        ]
    )

    panel = np.array(
        [
            [0.0, 1.0],
            [7.0, 8.0],
        ]
    )

    one_row = (
        cross_matrix_nearest_panel_distances(
            query,
            panel,
            chunk_size=1,
        )
    )

    all_rows = (
        cross_matrix_nearest_panel_distances(
            query,
            panel,
            chunk_size=100,
        )
    )

    np.testing.assert_array_equal(
        one_row,
        all_rows,
    )


def test_cross_matrix_rejects_invalid_chunk_size() -> None:
    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        cross_matrix_nearest_panel_distances(
            [[0.0]],
            [[1.0]],
            chunk_size=0,
        )


def test_holdout_weighted_p95_uses_species_balancing() -> None:
    distances = [
        1.0,
        3.0,
        2.0,
    ]

    species = [
        "A",
        "A",
        "B",
    ]

    # Exact inverse-ECDF weighted p95 reaches its
    # threshold at observed distance 3.
    assert holdout_weighted_p95(
        distances,
        species,
    ) == 3.0


def test_holdout_weighted_p95_has_no_interpolation() -> None:
    observed = holdout_weighted_p95(
        [
            1.0,
            2.0,
            9.0,
        ],
        [
            "A",
            "B",
            "C",
        ],
    )

    assert observed == 9.0


def test_panel_sizes_are_exact_frozen_prefix_sizes() -> None:
    assert PANEL_SIZES == (
        10,
        20,
        50,
        100,
        200,
        500,
    )


def test_exact_six_size_product_uses_fraction_from_float() -> None:
    values = {
        10: 0.5,
        20: 0.25,
        50: 0.125,
        100: 0.5,
        200: 0.25,
        500: 0.125,
    }

    observed = (
        exact_six_size_product(
            values
        )
    )

    expected = Fraction(
        1,
        1,
    )

    for panel_size in PANEL_SIZES:
        expected *= Fraction.from_float(
            float(
                values[
                    panel_size
                ]
            )
        )

    assert observed == expected


def test_exact_product_requires_all_six_sizes() -> None:
    with pytest.raises(
        ValueError,
        match="exactly",
    ):
        exact_six_size_product(
            {
                10: 1.0,
                20: 1.0,
            }
        )


def test_exact_product_rejects_nonfinite_value() -> None:
    values = {
        panel_size: 1.0
        for panel_size in PANEL_SIZES
    }

    values[100] = np.nan

    with pytest.raises(
        ValueError,
        match="finite",
    ):
        exact_six_size_product(
            values
        )


def test_exact_product_tie_is_unresolved() -> None:
    product = Fraction(
        7,
        13,
    )

    assert resolve_exact_products(
        product,
        product,
    ) == "UNRESOLVED"


def test_exact_product_selects_strictly_lower_ops() -> None:
    assert resolve_exact_products(
        Fraction(1, 3),
        Fraction(1, 2),
    ) == "OPS"


def test_exact_product_selects_strictly_lower_sr() -> None:
    assert resolve_exact_products(
        Fraction(2, 3),
        Fraction(1, 2),
    ) == "SR"


def test_resolve_products_requires_exact_fractions() -> None:
    with pytest.raises(
        TypeError,
        match="Fraction",
    ):
        resolve_exact_products(
            0.1,  # type: ignore[arg-type]
            Fraction(1, 2),
        )


def test_binary64_format_is_deterministic_17g() -> None:
    value = 0.1

    assert format_binary64(
        value
    ) == format(
        float(value),
        ".17g",
    )


def test_projection_rejects_nonfinite_input() -> None:
    with pytest.raises(
        ValueError,
        match="finite",
    ):
        project_values_through_baseline(
            [0.0, np.nan],
            ["A", "B"],
            [1.0],
        )


def test_matrix_projection_rejects_dimension_mismatch() -> None:
    with pytest.raises(
        ValueError,
        match="same number of features",
    ):
        project_matrix_through_baseline(
            [[0.0, 1.0]],
            ["A"],
            [[0.0, 1.0, 2.0]],
        )
