"""Repeat-scale selection helpers for BacSelect selector v1."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from typing import Hashable, Sequence

import numpy as np
import numpy.typing as npt

from bacselect.geometry import species_balanced_percentiles


K_GRID = (
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

REPEAT_FEATURE_FAMILIES = (
    "non_unique_fraction",
    "maximum_multiplicity",
    "inter_replicon_shared_fraction",
)


@dataclass(frozen=True)
class ScalePairScore:
    """Prospectively defined objective values for one candidate scale pair."""

    left_k: int
    right_k: int
    maximum_nearest_distance: float
    mean_nearest_distance: float


def _validate_species(
    species_ids: Sequence[Hashable],
    expected_rows: int,
) -> list[Hashable]:
    species = list(species_ids)

    if len(species) != expected_rows:
        raise ValueError(
            "species_ids and feature rows must have equal length"
        )

    if any(
        species_id is None or species_id == ""
        for species_id in species
    ):
        raise ValueError(
            "species_ids must not contain missing values"
        )

    return species


def _validate_k_values(
    k_values: Sequence[int],
) -> tuple[int, ...]:
    raw = list(k_values)

    if len(raw) < 2:
        raise ValueError(
            "at least two k values are required"
        )

    if any(
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, (int, np.integer))
        for value in raw
    ):
        raise TypeError(
            "k values must contain only integers"
        )

    values = tuple(
        int(value)
        for value in raw
    )

    if any(value <= 0 for value in values):
        raise ValueError(
            "k values must be positive"
        )

    if tuple(sorted(values)) != values:
        raise ValueError(
            "k values must be strictly increasing"
        )

    if len(set(values)) != len(values):
        raise ValueError(
            "k values must be unique"
        )

    return values


def repeat_scale_percentile_tensor(
    raw_values: Sequence[Sequence[Sequence[float]]]
    | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> npt.NDArray[np.float64]:
    """Transform every k/family column to species-balanced percentiles.

    Input dimensions are:

        genomes x scales x three repeat-feature families
    """
    matrix = np.asarray(
        raw_values,
        dtype=np.float64,
    )

    if matrix.ndim != 3:
        raise ValueError(
            "raw_values must be a three-dimensional tensor"
        )

    if matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(
            "raw_values must not be empty"
        )

    if matrix.shape[2] != len(REPEAT_FEATURE_FAMILIES):
        raise ValueError(
            "raw_values must contain exactly three repeat-feature families"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError(
            "raw_values must contain only finite values"
        )

    species = _validate_species(
        species_ids,
        matrix.shape[0],
    )

    result = np.empty_like(
        matrix,
        dtype=np.float64,
    )

    for scale_index in range(matrix.shape[1]):
        for family_index in range(matrix.shape[2]):
            result[:, scale_index, family_index] = (
                species_balanced_percentiles(
                    matrix[:, scale_index, family_index],
                    species,
                )
            )

    return result


def species_balanced_scale_distance_matrix(
    percentile_values: Sequence[Sequence[Sequence[float]]]
    | npt.NDArray[np.floating],
    species_ids: Sequence[Hashable],
) -> npt.NDArray[np.float64]:
    """Return pairwise scale distances under the frozen repeat-scale rule."""
    tensor = np.asarray(
        percentile_values,
        dtype=np.float64,
    )

    if tensor.ndim != 3:
        raise ValueError(
            "percentile_values must be a three-dimensional tensor"
        )

    if tensor.shape[0] == 0 or tensor.shape[1] < 2:
        raise ValueError(
            "percentile_values must contain genomes and at least two scales"
        )

    if tensor.shape[2] != len(REPEAT_FEATURE_FAMILIES):
        raise ValueError(
            "percentile_values must contain exactly three feature families"
        )

    if not np.all(np.isfinite(tensor)):
        raise ValueError(
            "percentile_values must contain only finite values"
        )

    if np.any(tensor < 0.0) or np.any(tensor > 1.0):
        raise ValueError(
            "percentile_values must lie in the closed unit interval"
        )

    species = _validate_species(
        species_ids,
        tensor.shape[0],
    )

    groups: defaultdict[
        Hashable,
        list[int],
    ] = defaultdict(list)

    for index, species_id in enumerate(species):
        groups[species_id].append(index)

    group_indices = tuple(
        np.asarray(indices, dtype=np.int64)
        for indices in groups.values()
    )

    species_count = len(group_indices)
    scale_count = tensor.shape[1]

    distances = np.zeros(
        (scale_count, scale_count),
        dtype=np.float64,
    )

    for left in range(scale_count):
        for right in range(left + 1, scale_count):
            family_squared_distances = []

            for family in range(tensor.shape[2]):
                species_squared_distances = []

                for indices in group_indices:
                    differences = (
                        tensor[indices, left, family]
                        - tensor[indices, right, family]
                    )

                    squared = sorted(
                        float(value * value)
                        for value in differences
                    )

                    species_squared_distances.append(
                        math.fsum(squared)
                        / indices.size
                    )

                family_squared_distances.append(
                    math.fsum(
                        sorted(
                            species_squared_distances
                        )
                    )
                    / species_count
                )

            mean_squared_distance = (
                math.fsum(
                    sorted(
                        family_squared_distances
                    )
                )
                / len(REPEAT_FEATURE_FAMILIES)
            )

            distance = math.sqrt(
                mean_squared_distance
            )

            distances[left, right] = distance
            distances[right, left] = distance

    return distances


def _validate_distance_matrix(
    distances: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    k_values: Sequence[int],
) -> tuple[
    npt.NDArray[np.float64],
    tuple[int, ...],
]:
    matrix = np.asarray(
        distances,
        dtype=np.float64,
    )

    values = _validate_k_values(
        k_values
    )

    if matrix.shape != (
        len(values),
        len(values),
    ):
        raise ValueError(
            "distance matrix shape does not match k values"
        )

    if not np.all(np.isfinite(matrix)):
        raise ValueError(
            "distance matrix must contain only finite values"
        )

    if np.any(matrix < 0.0):
        raise ValueError(
            "distance matrix must not contain negative values"
        )

    if not np.array_equal(
        matrix,
        matrix.T,
    ):
        raise ValueError(
            "distance matrix must be exactly symmetric"
        )

    if not np.all(
        np.diag(matrix) == 0.0
    ):
        raise ValueError(
            "distance matrix diagonal must be exactly zero"
        )

    return matrix, values


def score_scale_pairs(
    distances: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    k_values: Sequence[int] = K_GRID,
) -> tuple[ScalePairScore, ...]:
    """Score every unordered pair under the frozen minimax rule."""
    matrix, values = _validate_distance_matrix(
        distances,
        k_values,
    )

    scores = []

    for left, right in combinations(
        range(len(values)),
        2,
    ):
        nearest = np.minimum(
            matrix[:, left],
            matrix[:, right],
        )

        maximum = float(
            np.max(nearest)
        )

        mean = (
            math.fsum(
                sorted(
                    float(value)
                    for value in nearest
                )
            )
            / nearest.size
        )

        scores.append(
            ScalePairScore(
                left_k=values[left],
                right_k=values[right],
                maximum_nearest_distance=maximum,
                mean_nearest_distance=mean,
            )
        )

    return tuple(scores)


def select_scale_pair(
    distances: Sequence[Sequence[float]]
    | npt.NDArray[np.floating],
    k_values: Sequence[int] = K_GRID,
) -> ScalePairScore:
    """Return the deterministic two-scale choice."""
    scores = score_scale_pairs(
        distances,
        k_values,
    )

    return min(
        scores,
        key=lambda score: (
            score.maximum_nearest_distance,
            score.mean_nearest_distance,
            score.left_k,
            score.right_k,
        ),
    )
