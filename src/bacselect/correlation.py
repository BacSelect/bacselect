"""Feature-correlation helpers for BacSelect selector v1."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
import numpy.typing as npt
from scipy.stats import spearmanr


def spearman_correlation_matrix(
    values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
) -> npt.NDArray[np.float64]:
    """Return an exactly symmetric column-wise Spearman matrix.

    Each unique feature pair is evaluated once. The resulting coefficient
    is written to both symmetric matrix positions. The diagonal is exactly
    one by definition.
    """
    matrix = np.asarray(values, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError("values must be a two-dimensional matrix")

    if matrix.shape[0] < 2:
        raise ValueError("values must contain at least two rows")

    if matrix.shape[1] < 2:
        raise ValueError("values must contain at least two columns")

    if not np.all(np.isfinite(matrix)):
        raise ValueError("values must contain only finite numbers")

    constant_columns = np.all(
        matrix == matrix[0, :],
        axis=0,
    )

    if np.any(constant_columns):
        raise ValueError(
            "Spearman correlation is undefined for constant columns"
        )

    column_count = matrix.shape[1]

    correlation = np.eye(
        column_count,
        dtype=np.float64,
    )

    for left in range(column_count):
        for right in range(left + 1, column_count):
            result = spearmanr(
                matrix[:, left],
                matrix[:, right],
                nan_policy="raise",
            )

            rho = float(result.statistic)

            if not math.isfinite(rho):
                raise ValueError(
                    "Spearman correlation produced a non-finite value"
                )

            correlation[left, right] = rho
            correlation[right, left] = rho

    return correlation
