"""Feature-correlation helpers for BacSelect selector v1."""

from __future__ import annotations

from typing import Sequence

import numpy as np
import numpy.typing as npt
from scipy.stats import spearmanr


def spearman_correlation_matrix(
    values: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
) -> npt.NDArray[np.float64]:
    """Return the complete column-wise Spearman correlation matrix."""
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

    result = spearmanr(
        matrix,
        axis=0,
        nan_policy="raise",
    )

    correlation = np.asarray(
        result.statistic,
        dtype=np.float64,
    )

    column_count = matrix.shape[1]

    # scipy.stats.spearmanr returns a scalar when exactly two
    # variables are supplied.
    if column_count == 2 and correlation.ndim == 0:
        rho = float(correlation)
        correlation = np.asarray(
            [
                [1.0, rho],
                [rho, 1.0],
            ],
            dtype=np.float64,
        )

    if correlation.shape != (
        column_count,
        column_count,
    ):
        raise AssertionError(
            "unexpected Spearman correlation matrix shape: "
            f"{correlation.shape}"
        )

    if not np.all(np.isfinite(correlation)):
        raise ValueError(
            "Spearman correlation produced non-finite values"
        )

    return correlation
