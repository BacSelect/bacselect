"""Tests for prospective selector-v1 repeat-scale calculations."""

from __future__ import annotations

import math

import numpy as np
import pytest

from bacselect.geometry import (
    species_balanced_percentiles,
)
from bacselect.repeat_scale import (
    K_GRID,
    REPEAT_FEATURE_FAMILIES,
    repeat_scale_percentile_tensor,
    score_scale_pairs,
    select_scale_pair,
    species_balanced_scale_distance_matrix,
)


def test_frozen_k_grid() -> None:
    assert K_GRID == (
        50,
        75,
        100,
        150,
        200,
        300,
        400,
        600,
        800,
        1200,
        1600,
        2400,
        3200,
    )


def test_frozen_repeat_feature_families() -> None:
    assert REPEAT_FEATURE_FAMILIES == (
        "non_unique_fraction",
        "maximum_multiplicity",
        "inter_replicon_shared_fraction",
    )


def test_repeat_scale_percentile_tensor() -> None:
    raw = np.asarray(
        [
            [[1, 4, 0], [5, 8, 1]],
            [[2, 3, 0], [4, 7, 1]],
            [[3, 2, 1], [3, 6, 0]],
            [[4, 1, 1], [2, 5, 0]],
        ],
        dtype=np.float64,
    )

    species = ["A", "A", "B", "C"]

    observed = repeat_scale_percentile_tensor(
        raw,
        species,
    )

    assert observed.shape == raw.shape

    for scale in range(raw.shape[1]):
        for family in range(raw.shape[2]):
            expected = species_balanced_percentiles(
                raw[:, scale, family],
                species,
            )

            assert np.array_equal(
                observed[:, scale, family],
                expected,
            )


def test_scale_distance_is_species_balanced() -> None:
    # Species A has two genomes and species B has one.
    # Scale 0 is all zero.
    # At scale 1, squared differences are:
    #
    # A: (0^2 + 1^2) / 2 = 0.5
    # B: 1^2 = 1
    #
    # Equal species weighting gives (0.5 + 1) / 2 = 0.75.
    # All three repeat families are identical, so the family mean
    # remains 0.75 and the reported distance is sqrt(0.75).
    percentiles = np.asarray(
        [
            [[0, 0, 0], [0, 0, 0]],
            [[0, 0, 0], [1, 1, 1]],
            [[0, 0, 0], [1, 1, 1]],
        ],
        dtype=np.float64,
    )

    observed = species_balanced_scale_distance_matrix(
        percentiles,
        ["A", "A", "B"],
    )

    expected = math.sqrt(0.75)

    assert observed.shape == (2, 2)
    assert observed[0, 0] == 0.0
    assert observed[1, 1] == 0.0
    assert observed[0, 1] == observed[1, 0]
    assert observed[0, 1] == pytest.approx(
        expected,
        rel=0.0,
        abs=1e-15,
    )


def test_scale_distance_is_input_order_invariant() -> None:
    percentiles = np.asarray(
        [
            [[0.1, 0.2, 0.3], [0.2, 0.2, 0.5], [0.3, 0.4, 0.5]],
            [[0.4, 0.5, 0.6], [0.3, 0.7, 0.6], [0.2, 0.6, 0.8]],
            [[0.7, 0.8, 0.9], [0.9, 0.6, 0.7], [0.8, 0.5, 0.4]],
            [[0.2, 0.3, 0.4], [0.4, 0.5, 0.2], [0.6, 0.7, 0.3]],
        ],
        dtype=np.float64,
    )

    species = ["A", "A", "B", "C"]

    reference = species_balanced_scale_distance_matrix(
        percentiles,
        species,
    )

    permutation = np.asarray(
        [2, 0, 3, 1],
        dtype=np.int64,
    )

    permuted = species_balanced_scale_distance_matrix(
        percentiles[permutation],
        [
            species[index]
            for index in permutation
        ],
    )

    assert np.array_equal(
        reference,
        permuted,
    )


def test_pair_selection_uses_frozen_tie_rule() -> None:
    positions = np.asarray(
        [0.0, 1.0, 2.0, 3.0],
        dtype=np.float64,
    )

    distances = np.abs(
        positions[:, None]
        - positions[None, :]
    )

    k_values = (
        10,
        20,
        30,
        40,
    )

    scores = score_scale_pairs(
        distances,
        k_values,
    )

    assert len(scores) == 6

    selected = select_scale_pair(
        distances,
        k_values,
    )

    # Several pairs tie on both minimax and mean nearest distance.
    # The frozen final tie-break is numerical lexicographic order.
    assert (
        selected.left_k,
        selected.right_k,
    ) == (10, 30)

    assert selected.maximum_nearest_distance == 1.0
    assert selected.mean_nearest_distance == 0.5
