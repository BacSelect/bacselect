"""Feature-ablation helpers for BacSelect selector validation."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt


def remove_feature_column(
    coordinates: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    feature_index: int,
) -> npt.NDArray[np.float64]:
    """Return coordinates with exactly one feature column removed."""
    matrix = np.asarray(coordinates, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError(
            "coordinates must be a two-dimensional matrix"
        )

    if matrix.shape[0] == 0:
        raise ValueError(
            "coordinates must contain at least one row"
        )

    if matrix.shape[1] < 2:
        raise ValueError(
            "coordinates must contain at least two columns"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError(
            "coordinates must contain only finite numbers"
        )

    if (
        isinstance(feature_index, (bool, np.bool_))
        or not isinstance(feature_index, (int, np.integer))
    ):
        raise TypeError(
            "feature_index must be an integer"
        )

    index = int(feature_index)

    if index < 0 or index >= matrix.shape[1]:
        raise ValueError(
            "feature_index is out of range"
        )

    return np.delete(
        matrix,
        index,
        axis=1,
    )


def remove_feature_columns(
    coordinates: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    feature_indices: Sequence[int],
) -> npt.NDArray[np.float64]:
    """Return coordinates with a specified set of feature columns removed."""
    matrix = np.asarray(
        coordinates,
        dtype=np.float64,
    )

    if matrix.ndim != 2:
        raise ValueError(
            "coordinates must be a two-dimensional matrix"
        )

    if matrix.shape[0] == 0:
        raise ValueError(
            "coordinates must contain at least one row"
        )

    if matrix.shape[1] < 2:
        raise ValueError(
            "coordinates must contain at least two columns"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError(
            "coordinates must contain only finite numbers"
        )

    try:
        raw_indices = list(feature_indices)
    except TypeError as exc:
        raise TypeError(
            "feature_indices must be a sequence of integers"
        ) from exc

    if not raw_indices:
        raise ValueError(
            "feature_indices must not be empty"
        )

    if any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        for value in raw_indices
    ):
        raise TypeError(
            "feature_indices must contain only integers"
        )

    indices = [
        int(value)
        for value in raw_indices
    ]

    if len(set(indices)) != len(indices):
        raise ValueError(
            "feature_indices must contain unique indices"
        )

    if any(
        index < 0 or index >= matrix.shape[1]
        for index in indices
    ):
        raise ValueError(
            "feature index is out of range"
        )

    if len(indices) >= matrix.shape[1]:
        raise ValueError(
            "at least one feature column must remain"
        )

    return np.delete(
        matrix,
        sorted(indices),
        axis=1,
    )


def panel_overlap_count(
    reference_panel: Sequence[int]
    | npt.NDArray[np.integer],
    ablated_panel: Sequence[int]
    | npt.NDArray[np.integer],
) -> int:
    """Return unordered panel intersection size for equal-sized panels."""
    reference_raw = list(reference_panel)
    ablated_raw = list(ablated_panel)

    if not reference_raw or not ablated_raw:
        raise ValueError(
            "panels must not be empty"
        )

    if len(reference_raw) != len(ablated_raw):
        raise ValueError(
            "panels must have equal size"
        )

    for values in (reference_raw, ablated_raw):
        if any(
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, np.integer))
            for value in values
        ):
            raise TypeError(
                "panel indices must contain only integers"
            )

    reference = [
        int(value)
        for value in reference_raw
    ]
    ablated = [
        int(value)
        for value in ablated_raw
    ]

    if len(set(reference)) != len(reference):
        raise ValueError(
            "reference_panel must contain unique indices"
        )

    if len(set(ablated)) != len(ablated):
        raise ValueError(
            "ablated_panel must contain unique indices"
        )

    return len(
        set(reference).intersection(ablated)
    )
