"""All-genome maximin diagnostic selector for BacSelect selector v1."""

from __future__ import annotations

from fractions import Fraction
from typing import Sequence

import numpy as np
import numpy.typing as npt

from bacselect.tie import tie_key


def _validate_inputs(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    accessions: Sequence[str],
) -> tuple[npt.NDArray[np.float64], list[str]]:
    """Validate AG selector inputs."""
    matrix = np.asarray(coordinates, dtype=np.float64)
    accession_list = list(accessions)

    if matrix.ndim != 2:
        raise ValueError("coordinates must be a two-dimensional matrix")

    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError("coordinates must not be empty")

    if len(accession_list) != matrix.shape[0]:
        raise ValueError(
            "coordinates and accessions must contain the same number of rows"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError("coordinates must contain only finite numbers")

    if any(not accession for accession in accession_list):
        raise ValueError("accessions must not contain empty values")

    if len(set(accession_list)) != len(accession_list):
        raise ValueError("accessions must be unique")

    return matrix, accession_list


def _exact_centroid(
    coordinates: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Return an order-invariant centroid of binary64 coordinates."""
    if coordinates.ndim != 2 or coordinates.shape[0] == 0:
        raise ValueError("centroid input must be a non-empty matrix")

    row_count = coordinates.shape[0]

    centroid = np.empty(
        coordinates.shape[1],
        dtype=np.float64,
    )

    for column in range(coordinates.shape[1]):
        total = sum(
            (
                Fraction.from_float(float(value))
                for value in coordinates[:, column]
            ),
            Fraction(0, 1),
        )

        centroid[column] = float(total / row_count)

    return centroid


def _squared_distances(
    coordinates: npt.NDArray[np.float64],
    point: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Return squared Euclidean distances from rows to one point."""
    differences = coordinates - point

    return np.einsum(
        "ij,ij->i",
        differences,
        differences,
    )


def _tie_resolved_minimum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    accessions: Sequence[str],
) -> int:
    """Return minimum-score candidate, then frozen genome tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.min(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: tie_key(accessions[index]),
    )


def _tie_resolved_maximum(
    values: npt.NDArray[np.float64],
    candidate_indices: npt.NDArray[np.int64],
    accessions: Sequence[str],
) -> int:
    """Return maximum-score candidate, then frozen genome tie key."""
    candidate_values = values[candidate_indices]
    best_value = np.max(candidate_values)

    tied = candidate_indices[candidate_values == best_value]

    return min(
        (int(index) for index in tied),
        key=lambda index: tie_key(accessions[index]),
    )


def ag_ladder(
    coordinates: Sequence[Sequence[float]] | npt.NDArray[np.floating],
    accessions: Sequence[str],
    max_n: int,
) -> npt.NDArray[np.int64]:
    """Return the deterministic all-genome maximin ladder."""
    matrix, accession_list = _validate_inputs(
        coordinates,
        accessions,
    )

    if not isinstance(max_n, int):
        raise TypeError("max_n must be an integer")

    if max_n < 1 or max_n > matrix.shape[0]:
        raise ValueError(
            "max_n must be between 1 and the number of eligible genomes"
        )

    centroid = _exact_centroid(matrix)

    first_distances = _squared_distances(
        matrix,
        centroid,
    )

    all_indices = np.arange(
        matrix.shape[0],
        dtype=np.int64,
    )

    first = _tie_resolved_minimum(
        first_distances,
        all_indices,
        accession_list,
    )

    selected = [first]

    selected_mask = np.zeros(
        matrix.shape[0],
        dtype=bool,
    )
    selected_mask[first] = True

    nearest_squared = _squared_distances(
        matrix,
        matrix[first],
    )
    nearest_squared[first] = 0.0

    while len(selected) < max_n:
        remaining = np.flatnonzero(~selected_mask)

        next_index = _tie_resolved_maximum(
            nearest_squared,
            remaining,
            accession_list,
        )

        selected.append(next_index)
        selected_mask[next_index] = True

        distances = _squared_distances(
            matrix,
            matrix[next_index],
        )

        nearest_squared = np.minimum(
            nearest_squared,
            distances,
        )

        nearest_squared[selected_mask] = 0.0

    return np.asarray(
        selected,
        dtype=np.int64,
    )
