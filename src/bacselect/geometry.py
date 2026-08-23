"""Species-balanced feature geometry for BacSelect."""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
from typing import Hashable, Sequence

import numpy as np
import numpy.typing as npt


def _validate_feature_inputs(
    values: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> tuple[npt.NDArray[np.float64], list[Hashable]]:
    """Validate one feature vector and its species assignments."""
    array = np.asarray(values, dtype=np.float64)
    species = list(species_ids)

    if array.ndim != 1:
        raise ValueError("values must be one-dimensional")

    if array.size == 0:
        raise ValueError("values must not be empty")

    if len(species) != array.size:
        raise ValueError(
            "values and species_ids must contain the same number of rows"
        )

    if not np.all(np.isfinite(array)):
        raise ValueError("values must contain only finite numbers")

    if any(item is None or item == "" for item in species):
        raise ValueError("species_ids must not contain missing values")

    return array, species


def species_balanced_percentiles_exact(
    values: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> tuple[Fraction, ...]:
    """Return exact species-balanced midpoint percentile coordinates.

    Each species contributes total weight one. If species ``s`` contains
    ``n_s`` genomes, each member genome has exact weight ``1 / n_s``.

    For feature value ``x``:

        p(x) = [W_less(x) + 0.5 * W_equal(x)] / S

    where ``S`` is the number of distinct species groups.

    Tied raw feature values therefore receive exactly the same coordinate.
    """
    array, species = _validate_feature_inputs(values, species_ids)

    counts = Counter(species)
    species_count = len(counts)

    weights = [
        Fraction(1, counts[species_id])
        for species_id in species
    ]

    order = sorted(
        range(array.size),
        key=lambda index: (array[index], index),
    )

    result: list[Fraction | None] = [None] * array.size
    cumulative_weight = Fraction(0, 1)
    total_weight = Fraction(species_count, 1)

    start = 0

    while start < array.size:
        value = array[order[start]]
        stop = start
        equal_weight = Fraction(0, 1)

        while stop < array.size and array[order[stop]] == value:
            equal_weight += weights[order[stop]]
            stop += 1

        percentile = (
            cumulative_weight + equal_weight / 2
        ) / total_weight

        for position in range(start, stop):
            result[order[position]] = percentile

        cumulative_weight += equal_weight
        start = stop

    if cumulative_weight != total_weight:
        raise RuntimeError(
            "species-balanced feature weights do not sum to species count"
        )

    if any(value is None for value in result):
        raise RuntimeError("failed to assign every percentile coordinate")

    return tuple(value for value in result if value is not None)


def species_balanced_percentiles(
    values: Sequence[float] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> npt.NDArray[np.float64]:
    """Return float64 species-balanced percentile coordinates."""
    exact = species_balanced_percentiles_exact(values, species_ids)

    return np.fromiter(
        (float(value) for value in exact),
        dtype=np.float64,
        count=len(exact),
    )


def species_balanced_percentile_matrix(
    values: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> npt.NDArray[np.float64]:
    """Transform every feature column to species-balanced percentiles."""
    matrix = np.asarray(values, dtype=np.float64)

    if matrix.ndim != 2:
        raise ValueError("values must be a two-dimensional matrix")

    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("values matrix must not be empty")

    species = list(species_ids)

    if len(species) != matrix.shape[0]:
        raise ValueError(
            "matrix rows and species_ids must contain the same number of rows"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError("values matrix must contain only finite numbers")

    columns = [
        species_balanced_percentiles(matrix[:, column], species)
        for column in range(matrix.shape[1])
    ]

    return np.column_stack(columns)
