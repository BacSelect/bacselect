import numpy as np
import pytest

from bacselect.ablation import (
    panel_overlap_count,
    remove_feature_column,
)
from bacselect.geometry import (
    species_balanced_percentile_matrix,
)


def test_remove_feature_column() -> None:
    values = np.asarray(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ]
    )

    observed = remove_feature_column(
        values,
        1,
    )

    expected = np.asarray(
        [
            [1.0, 3.0],
            [4.0, 6.0],
        ]
    )

    assert np.array_equal(
        observed,
        expected,
    )


def test_column_removal_does_not_modify_input() -> None:
    values = np.asarray(
        [
            [1.0, 2.0, 3.0],
            [4.0, 5.0, 6.0],
        ]
    )
    original = values.copy()

    remove_feature_column(
        values,
        0,
    )

    assert np.array_equal(
        values,
        original,
    )


def test_drop_after_transform_equals_transform_after_drop() -> None:
    raw = np.asarray(
        [
            [1.0, 8.0, 3.0],
            [2.0, 7.0, 4.0],
            [3.0, 7.0, 5.0],
            [4.0, 5.0, 5.0],
            [5.0, 4.0, 6.0],
            [6.0, 2.0, 7.0],
        ]
    )

    species = [
        "a",
        "a",
        "b",
        "c",
        "c",
        "d",
    ]

    full = species_balanced_percentile_matrix(
        raw,
        species,
    )

    dropped_after = remove_feature_column(
        full,
        1,
    )

    dropped_before = np.delete(
        raw,
        1,
        axis=1,
    )

    transformed_after_drop = (
        species_balanced_percentile_matrix(
            dropped_before,
            species,
        )
    )

    assert np.array_equal(
        dropped_after,
        transformed_after_drop,
    )


def test_remove_feature_rejects_bad_index() -> None:
    values = np.ones((3, 3))

    with pytest.raises(
        ValueError,
        match="out of range",
    ):
        remove_feature_column(
            values,
            3,
        )


def test_remove_feature_rejects_boolean_index() -> None:
    values = np.ones((3, 3))

    with pytest.raises(
        TypeError,
        match="integer",
    ):
        remove_feature_column(
            values,
            True,
        )


def test_remove_feature_rejects_nonfinite_values() -> None:
    values = np.asarray(
        [
            [1.0, 2.0],
            [3.0, np.nan],
        ]
    )

    with pytest.raises(
        ValueError,
        match="finite",
    ):
        remove_feature_column(
            values,
            0,
        )


def test_panel_overlap_is_unordered() -> None:
    assert panel_overlap_count(
        [1, 2, 3, 4],
        [4, 3, 8, 9],
    ) == 2


def test_panel_overlap_can_be_complete() -> None:
    assert panel_overlap_count(
        [1, 2, 3],
        [3, 1, 2],
    ) == 3


def test_panel_overlap_rejects_unequal_sizes() -> None:
    with pytest.raises(
        ValueError,
        match="equal size",
    ):
        panel_overlap_count(
            [1, 2],
            [1, 2, 3],
        )


def test_panel_overlap_rejects_duplicate_indices() -> None:
    with pytest.raises(
        ValueError,
        match="unique",
    ):
        panel_overlap_count(
            [1, 1, 2],
            [1, 2, 3],
        )
